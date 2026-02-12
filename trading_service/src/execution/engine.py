from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass
class Order:
    id: str
    client_order_id: str
    account_id: str
    strategy_id: Optional[str]
    model_id: Optional[str]
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    filled_quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    rejection_reason: Optional[str] = None
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        data = asdict(self)
        for k in ("side", "order_type", "status"):
            data[k] = data[k].value
        for k in ("opened_at", "closed_at", "created_at", "updated_at"):
            if data.get(k):
                data[k] = data[k].isoformat()
        return data


class ExecutionEngine:
    VALID_TRANSITIONS = {
        OrderStatus.PENDING: {OrderStatus.VALIDATED, OrderStatus.REJECTED, OrderStatus.CANCELED},
        OrderStatus.VALIDATED: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELED},
        OrderStatus.SUBMITTED: {OrderStatus.PARTIAL, OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELED, OrderStatus.EXPIRED},
        OrderStatus.PARTIAL: {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED},
        OrderStatus.FILLED: set(),
        OrderStatus.REJECTED: set(),
        OrderStatus.CANCELED: set(),
        OrderStatus.EXPIRED: set(),
    }

    def __init__(self, connector, risk_engine, db_repository):
        self.connector = connector
        self.risk_engine = risk_engine
        self.repo = db_repository
        self._callbacks: Dict[str, set[Callable]] = {
            "order_created": set(),
            "order_updated": set(),
            "order_filled": set(),
            "order_rejected": set(),
            "order_canceled": set(),
        }
        self._lock = asyncio.Lock()

    async def submit_order(self, order: Order) -> Order:
        async with self._lock:
            if order.status != OrderStatus.PENDING:
                raise ValueError("Order must be pending")
            if order.quantity <= 0:
                await self.update_order_status(order.id, OrderStatus.REJECTED, rejection_reason="quantity must be positive")
                return order

            account_info = await self.connector.get_account_info()
            positions = await self.connector.get_positions(order.symbol)
            approval = await self.risk_engine.pre_trade_check(order.to_dict(), account_info, positions, market_data=None)
            if not approval.approved:
                await self.update_order_status(order.id, OrderStatus.REJECTED, rejection_reason=approval.reason)
                return order

            await self.update_order_status(order.id, OrderStatus.VALIDATED)
            await self.repo.save_order(order.to_dict())
            await self._emit("order_created", order.to_dict())

            broker_response = await self.connector.execute_order(order.to_dict())
            if not broker_response.get("ok"):
                await self.update_order_status(order.id, OrderStatus.REJECTED, rejection_reason=broker_response.get("error", "broker rejected"))
                return order

            result = broker_response.get("result", {})
            retcode = int(result.get("retcode", 0))
            if retcode:
                await self.update_order_status(order.id, OrderStatus.SUBMITTED, opened_at=datetime.utcnow())
                deal = result.get("deal")
                if deal:
                    await self.update_order_status(order.id, OrderStatus.FILLED, filled_quantity=order.quantity, closed_at=datetime.utcnow())
                    await self._emit("order_filled", order.to_dict())
            return order

    async def cancel_order(self, order_id: str) -> bool:
        order = await self.get_order(order_id)
        if not order:
            return False
        if order.status not in {OrderStatus.PENDING, OrderStatus.VALIDATED, OrderStatus.SUBMITTED, OrderStatus.PARTIAL}:
            return False
        ok = await self.connector.cancel_order(order_id)
        if ok:
            await self.update_order_status(order_id, OrderStatus.CANCELED)
            await self._emit("order_canceled", order.to_dict())
        return ok

    async def update_order_status(self, order_id: str, status: OrderStatus, **kwargs) -> None:
        order = await self.get_order(order_id)
        if not order:
            raise ValueError("order not found")
        allowed = self.VALID_TRANSITIONS[order.status]
        if status not in allowed and status != order.status:
            raise ValueError(f"invalid status transition {order.status} -> {status}")
        order.status = status
        for k, v in kwargs.items():
            if hasattr(order, k):
                setattr(order, k, v)
        order.updated_at = datetime.utcnow()
        await self.repo.update_order(order_id, order.to_dict())
        await self._emit("order_updated", order.to_dict())
        if status == OrderStatus.REJECTED:
            await self._emit("order_rejected", order.to_dict())

    async def get_order(self, order_id: str) -> Optional[Order]:
        data = await self.repo.get_order(order_id)
        if not data:
            return None
        return self._hydrate(data)

    async def get_orders(self, account_id: str, status: Optional[OrderStatus] = None) -> List[Order]:
        rows = await self.repo.get_orders(account_id=account_id, status=status.value if status else None)
        return [self._hydrate(r) for r in rows]

    def on(self, event: str, callback: Callable) -> None:
        self._callbacks.setdefault(event, set()).add(callback)

    def off(self, event: str, callback: Callable) -> None:
        self._callbacks.get(event, set()).discard(callback)

    async def _emit(self, event: str, payload: Dict) -> None:
        for cb in list(self._callbacks.get(event, set())):
            try:
                out = cb(payload)
                if asyncio.iscoroutine(out):
                    await out
            except Exception:
                logger.exception("execution callback failed event=%s", event)

    @staticmethod
    def _hydrate(data: Dict) -> Order:
        return Order(
            id=data["id"],
            client_order_id=data.get("client_order_id", data["id"]),
            account_id=data["account_id"],
            strategy_id=data.get("strategy_id"),
            model_id=data.get("model_id"),
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            order_type=OrderType(data["order_type"]),
            quantity=float(data["quantity"]),
            filled_quantity=float(data.get("filled_quantity", 0)),
            price=data.get("price"),
            stop_price=data.get("stop_price"),
            limit_price=data.get("limit_price"),
            status=OrderStatus(data["status"]),
            rejection_reason=data.get("rejection_reason"),
            commission=float(data.get("commission", 0)),
            swap=float(data.get("swap", 0)),
            profit=float(data.get("profit", 0)),
            opened_at=datetime.fromisoformat(data["opened_at"]) if data.get("opened_at") else None,
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow()),
            updated_at=datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else data.get("updated_at", datetime.utcnow()),
        )
