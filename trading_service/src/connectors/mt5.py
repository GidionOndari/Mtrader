from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None

logger = logging.getLogger(__name__)

RETCODE_MAPPING: Dict[int, str] = {i: f"MT5 retcode {i}" for i in range(10004, 10070)}
RETCODE_MAPPING.update(
    {
        10004: "Requote",
        10006: "Request rejected",
        10007: "Request canceled by trader",
        10008: "Order placed",
        10009: "Order modified",
        10010: "Request accepted",
        10011: "System order placed",
        10012: "Order filled partially",
        10013: "Order filled fully",
        10014: "Order canceled",
        10015: "Order deleted",
        10016: "Order modified partially",
        10017: "Order rejected",
        10018: "Order activation triggered",
        10019: "Order placed by external system",
        10030: "Invalid stops",
        10031: "Invalid volume",
        10032: "Market closed",
        10033: "No money",
        10034: "Price changed",
        10035: "Off quotes",
        10036: "Broker busy",
        10039: "Too many requests",
        10041: "Trade disabled",
        10046: "Invalid price",
        10051: "Position closed",
        10060: "Connection lost",
        10069: "Trade timeout",
    }
)


@dataclass(slots=True)
class MT5Credentials:
    account_id: int
    password: str
    server: str
    path: Optional[str] = None


@dataclass(slots=True)
class MT5ConnectionConfig:
    reconnect_attempts: int = 10
    reconnect_delay: float = 1
    backoff_multiplier: float = 2
    heartbeat_interval: int = 5
    timeout_ms: int = 30000


class MT5Connector:
    def __init__(self, credentials: MT5Credentials, config: Optional[MT5ConnectionConfig] = None):
        self.credentials = credentials
        self.config = config or MT5ConnectionConfig()
        self._connected = False
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._started_at: Optional[float] = None
        self._last_heartbeat: Optional[datetime] = None
        self._reconnect_count = 0
        self._idempotency: Dict[str, int] = {}

    async def connect(self) -> bool:
        async with self._lock:
            if self._connected:
                return True
            if mt5 is None:
                logger.error("MetaTrader5 module unavailable")
                return False
            ok = mt5.initialize(path=self.credentials.path, timeout=self.config.timeout_ms) if self.credentials.path else mt5.initialize(timeout=self.config.timeout_ms)
            if not ok:
                logger.error("mt5 initialize failed: %s", mt5.last_error())
                return False
            if not mt5.login(self.credentials.account_id, password=self.credentials.password, server=self.credentials.server):
                logger.error("mt5 login failed: %s", mt5.last_error())
                mt5.shutdown()
                return False
            self._connected = True
            self._started_at = time.time()
            self._last_heartbeat = datetime.utcnow()
            self._heartbeat_task = asyncio.create_task(self.heartbeat())
            return True

    async def disconnect(self) -> None:
        async with self._lock:
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                await asyncio.gather(self._heartbeat_task, return_exceptions=True)
            if mt5:
                mt5.shutdown()
            self._connected = False

    async def reconnect(self) -> bool:
        delay = self.config.reconnect_delay
        for _ in range(self.config.reconnect_attempts):
            self._reconnect_count += 1
            await asyncio.sleep(delay)
            if await self.connect():
                return True
            delay *= self.config.backoff_multiplier
        return False

    async def heartbeat(self) -> None:
        while self._connected:
            try:
                info = mt5.terminal_info() if mt5 else None
                if not info:
                    self._connected = False
                    await self.reconnect()
                else:
                    self._last_heartbeat = datetime.utcnow()
            except Exception:
                logger.exception("heartbeat failure")
            await asyncio.sleep(self.config.heartbeat_interval)

    async def subscribe_market_data(self, symbols: List[str]) -> Dict[str, bool]:
        return {s: bool(mt5 and mt5.symbol_select(s, True)) for s in symbols}

    async def unsubscribe_market_data(self, symbols: List[str]) -> None:
        for s in symbols:
            if mt5:
                mt5.symbol_select(s, False)

    async def get_ticks(self, symbol, from_date, to_date=None, count=10000) -> List[Dict]:
        data = mt5.copy_ticks_range(symbol, from_date, to_date, mt5.COPY_TICKS_ALL) if to_date else mt5.copy_ticks_from(symbol, from_date, count, mt5.COPY_TICKS_ALL)
        return [d.item() if hasattr(d, 'item') else {k: (v.item() if hasattr(v, 'item') else v) for k, v in dict(d).items()} for d in (data or [])]

    async def get_rates(self, symbol, timeframe, from_date, to_date=None, count=10000) -> List[Dict]:
        data = mt5.copy_rates_range(symbol, timeframe, from_date, to_date) if to_date else mt5.copy_rates_from(symbol, timeframe, from_date, count)
        return [d.item() if hasattr(d, 'item') else {k: (v.item() if hasattr(v, 'item') else v) for k, v in dict(d).items()} for d in (data or [])]

    def _validate_symbol(self, symbol: str) -> tuple[bool, str, Any]:
        info = mt5.symbol_info(symbol) if mt5 else None
        if not info:
            return False, "symbol not found", None
        if getattr(info, "trade_mode", 0) == getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", -1):
            return False, "symbol trade mode disabled", None
        if getattr(info, "trade_mode", 0) == getattr(mt5, "SYMBOL_TRADE_MODE_CLOSEONLY", -2):
            return False, "symbol is close-only", None
        return True, "ok", info

    def _validate_volume(self, info: Any, volume: float) -> tuple[bool, str]:
        if volume < info.volume_min or volume > info.volume_max:
            return False, "volume outside range"
        step = float(info.volume_step)
        if step > 0 and abs((volume / step) - round(volume / step)) > 1e-9:
            return False, "volume step invalid"
        return True, "ok"

    def _validate_price_tick(self, info: Any, price: float) -> tuple[bool, str]:
        tick_size = float(getattr(info, "trade_tick_size", 0) or 0)
        if tick_size <= 0:
            return True, "ok"
        ticks = price / tick_size
        if abs(ticks - round(ticks)) > 1e-9:
            return False, "price not aligned to tick size"
        return True, "ok"

    def _validate_stops(self, info: Any, price: float, sl: float | None, tp: float | None) -> tuple[bool, str]:
        stops_level = float(getattr(info, "trade_stops_level", 0) or 0) * float(info.point)
        if sl and abs(price - sl) < stops_level:
            return False, "stop loss too close"
        if tp and abs(price - tp) < stops_level:
            return False, "take profit too close"
        return True, "ok"

    async def execute_order(self, order: Dict) -> Dict:
        client_id = str(order.get("client_order_id") or order.get("idempotency_key") or "")
        if client_id and client_id in self._idempotency:
            return {"ok": True, "duplicate": True, "broker_order_id": self._idempotency[client_id]}

        symbol = order.get("symbol")
        volume = float(order.get("volume") or order.get("quantity") or 0)
        side = str(order.get("side", "BUY")).upper()
        otype = str(order.get("type", "MARKET")).upper()
        if not symbol or volume <= 0:
            return {"ok": False, "error": "invalid order payload"}

        ok, msg, info = self._validate_symbol(symbol)
        if not ok:
            return {"ok": False, "error": msg}
        ok, msg = self._validate_volume(info, volume)
        if not ok:
            return {"ok": False, "error": msg}

        tick = mt5.symbol_info_tick(symbol) if mt5 else None
        if not tick:
            return {"ok": False, "error": "no market tick"}
        price = float(order.get("price") or (tick.ask if side == "BUY" else tick.bid))
        ok, msg = self._validate_price_tick(info, price)
        if not ok:
            return {"ok": False, "error": msg}
        ok, msg = self._validate_stops(info, price, order.get("stop_price"), order.get("limit_price"))
        if not ok:
            return {"ok": False, "error": msg}

        if not mt5.symbol_select(symbol, True):
            return {"ok": False, "error": "symbol select failed"}

        margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL, symbol, volume, price)
        acct = mt5.account_info()
        if margin is None or not acct or float(acct.margin_free) < float(margin):
            return {"ok": False, "error": "insufficient margin"}

        req = {
            "action": mt5.TRADE_ACTION_DEAL if otype == "MARKET" else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": float(order.get("stop_price") or 0),
            "tp": float(order.get("limit_price") or 0),
            "deviation": int(order.get("deviation", 10)),
            "magic": int(order.get("magic", 100001)),
            "comment": str(client_id or order.get("comment", "mtrader"))[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        result = mt5.order_send(req)
        if result is None:
            return {"ok": False, "error": f"order_send failed {mt5.last_error()}"}

        retcode = int(getattr(result, "retcode", 0) or 0)
        payload = result._asdict() if hasattr(result, "_asdict") else {"retcode": retcode}
        broker_order_id = int(payload.get("order") or payload.get("deal") or 0)
        if client_id and broker_order_id:
            self._idempotency[client_id] = broker_order_id

        success_codes = {10008, 10009, 10010, 10011, 10012, 10013, 10018, 10019}
        return {
            "ok": retcode in success_codes,
            "retcode": retcode,
            "retcode_message": RETCODE_MAPPING.get(retcode, f"Unknown retcode {retcode}"),
            "broker_order_id": broker_order_id,
            "result": payload,
        }

    async def modify_order(self, order_id, price=None, stop_price=None, limit_price=None, quantity=None) -> Dict:
        req = {"action": mt5.TRADE_ACTION_MODIFY, "order": int(order_id)}
        if price is not None:
            req["price"] = float(price)
        if stop_price is not None:
            req["sl"] = float(stop_price)
        if limit_price is not None:
            req["tp"] = float(limit_price)
        if quantity is not None:
            req["volume"] = float(quantity)
        res = mt5.order_send(req)
        if not res:
            return {"ok": False, "error": "modify failed"}
        retcode = int(getattr(res, "retcode", 0))
        return {"ok": retcode in {10009, 10016}, "retcode": retcode, "retcode_message": RETCODE_MAPPING.get(retcode, str(retcode)), "result": res._asdict()}

    async def cancel_order(self, order_id) -> bool:
        res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_id)})
        return bool(res and int(getattr(res, "retcode", 0)) in {10014, 10015})

    async def close_position(self, position_id, deviation=10) -> Dict:
        positions = mt5.positions_get(ticket=int(position_id))
        if not positions:
            return {"ok": False, "error": "position not found"}
        pos = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        req = {"action": mt5.TRADE_ACTION_DEAL, "position": int(position_id), "symbol": pos.symbol, "volume": float(pos.volume), "type": close_type, "price": float(price), "deviation": int(deviation), "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
        res = mt5.order_send(req)
        if not res:
            return {"ok": False, "error": "close failed"}
        retcode = int(getattr(res, "retcode", 0))
        return {"ok": retcode in {10013, 10012}, "retcode": retcode, "retcode_message": RETCODE_MAPPING.get(retcode, str(retcode)), "result": res._asdict()}

    async def close_all_positions(self, symbol=None) -> List[Dict]:
        rows = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return [await self.close_position(r.ticket) for r in (rows or [])]

    async def get_account_info(self) -> Dict:
        info = mt5.account_info()
        if not info:
            return {}
        d = info._asdict()
        return {"balance": d.get("balance"), "equity": d.get("equity"), "margin": d.get("margin"), "free_margin": d.get("margin_free"), "margin_level": d.get("margin_level"), "profit": d.get("profit"), "leverage": d.get("leverage"), "currency": d.get("currency")}

    async def get_positions(self, symbol=None) -> List[Dict]:
        rows = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return [r._asdict() for r in (rows or [])]

    async def get_orders(self, symbol=None) -> List[Dict]:
        rows = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
        return [r._asdict() for r in (rows or [])]

    def on(self, event, callback):
        return None

    def off(self, event, callback):
        return None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def connection_health(self) -> Dict:
        return {"uptime": int(time.time() - self._started_at) if self._started_at else 0, "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None, "reconnect_count": self._reconnect_count}
