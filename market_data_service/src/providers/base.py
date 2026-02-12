from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


@dataclass(slots=True)
class Tick:
    symbol: str
    bid: float
    ask: float
    time: datetime
    volume: int
    provider: str


@dataclass(slots=True)
class OHLCV:
    symbol: str
    timeframe: Timeframe
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_volume: int
    spread: int
    provider: str


class MarketDataProvider(ABC):
    @abstractmethod
    async def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_ticks(self, symbol, start, end=None, limit=10000) -> List[Tick]:
        raise NotImplementedError

    @abstractmethod
    async def get_ohlcv(self, symbol, timeframe, start, end=None, limit=1000) -> List[OHLCV]:
        raise NotImplementedError

    @abstractmethod
    async def subscribe_ticks(self, symbols: List[str], callback: Callable) -> Dict[str, bool]:
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe_ticks(self, symbols: List[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_instrument_info(self, symbol: str) -> Dict:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError


class MT5Provider(MarketDataProvider):
    def __init__(self, account: int, password: str, server: str, path: Optional[str] = None) -> None:
        self.account = account
        self.password = password
        self.server = server
        self.path = path
        self._connected = False
        self._tasks: Dict[str, asyncio.Task] = {}

    async def connect(self) -> bool:
        if mt5 is None:
            return False
        ok = mt5.initialize(path=self.path) if self.path else mt5.initialize()
        if not ok:
            return False
        self._connected = mt5.login(self.account, password=self.password, server=self.server)
        return self._connected

    async def disconnect(self) -> None:
        for task in self._tasks.values():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._tasks.clear()
        if mt5:
            mt5.shutdown()
        self._connected = False

    async def get_ticks(self, symbol, start, end=None, limit=10000) -> List[Tick]:
        data = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL) if end else mt5.copy_ticks_from(symbol, start, limit, mt5.COPY_TICKS_ALL)
        if data is None:
            return []
        return [Tick(symbol=symbol, bid=float(r["bid"]), ask=float(r["ask"]), time=datetime.utcfromtimestamp(int(r["time"])), volume=int(r["volume"]), provider=self.name) for r in data]

    async def get_ohlcv(self, symbol, timeframe, start, end=None, limit=1000) -> List[OHLCV]:
        tf_map = {
            Timeframe.M1: mt5.TIMEFRAME_M1,
            Timeframe.M5: mt5.TIMEFRAME_M5,
            Timeframe.M15: mt5.TIMEFRAME_M15,
            Timeframe.M30: mt5.TIMEFRAME_M30,
            Timeframe.H1: mt5.TIMEFRAME_H1,
            Timeframe.H4: mt5.TIMEFRAME_H4,
            Timeframe.D1: mt5.TIMEFRAME_D1,
            Timeframe.W1: mt5.TIMEFRAME_W1,
            Timeframe.MN1: mt5.TIMEFRAME_MN1,
        }
        tfi = tf_map[Timeframe(timeframe)] if not isinstance(timeframe, Timeframe) else tf_map[timeframe]
        data = mt5.copy_rates_range(symbol, tfi, start, end) if end else mt5.copy_rates_from(symbol, tfi, start, limit)
        if data is None:
            return []
        tf = Timeframe(timeframe) if not isinstance(timeframe, Timeframe) else timeframe
        return [OHLCV(symbol=symbol, timeframe=tf, time=datetime.utcfromtimestamp(int(r["time"])), open=float(r["open"]), high=float(r["high"]), low=float(r["low"]), close=float(r["close"]), volume=float(r["real_volume"]), tick_volume=int(r["tick_volume"]), spread=int(r["spread"]), provider=self.name) for r in data]

    async def subscribe_ticks(self, symbols: List[str], callback: Callable) -> Dict[str, bool]:
        result = {}
        for s in symbols:
            ok = mt5.symbol_select(s, True)
            result[s] = bool(ok)
            if ok and s not in self._tasks:
                self._tasks[s] = asyncio.create_task(self._stream(s, callback))
        return result

    async def _stream(self, symbol: str, callback: Callable) -> None:
        while self._connected:
            ticks = mt5.copy_ticks_from(symbol, datetime.utcnow(), 1, mt5.COPY_TICKS_ALL)
            if ticks is not None and len(ticks):
                row = ticks[-1]
                tick = Tick(symbol=symbol, bid=float(row["bid"]), ask=float(row["ask"]), time=datetime.utcfromtimestamp(int(row["time"])), volume=int(row["volume"]), provider=self.name)
                out = callback(tick)
                if asyncio.iscoroutine(out):
                    await out
            await asyncio.sleep(1)

    async def unsubscribe_ticks(self, symbols: List[str]) -> None:
        for s in symbols:
            task = self._tasks.pop(s, None)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            mt5.symbol_select(s, False)

    async def get_instrument_info(self, symbol: str) -> Dict:
        info = mt5.symbol_info(symbol)
        return info._asdict() if info else {}

    @property
    def name(self) -> str:
        return "mt5"

    @property
    def is_connected(self) -> bool:
        return self._connected
