from __future__ import annotations

import os
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from trading_service.src.connectors.mt5 import MT5ConnectionConfig, MT5Connector, MT5Credentials
from trading_service.src.execution.engine import ExecutionEngine, Order, OrderSide, OrderType
from trading_service.src.repositories.postgres_repository import PostgresOrderRepository
from trading_service.src.risk.engine import RiskEngine

if __name__ != "__main__" and not os.getenv("DATABASE_URL"):
    raise RuntimeError(
        "Trading service initialized without DATABASE_URL. "
        "This service requires database configuration at startup."
    )

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("CRITICAL: DATABASE_URL environment variable is required")


class OrderIn(BaseModel):
    account_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    strategy_id: str | None = None
    model_id: str | None = None


repository = PostgresOrderRepository(DATABASE_URL)
connector = MT5Connector(
    MT5Credentials(
        account_id=int(os.getenv("MT5_DEFAULT_ACCOUNT_ID", "0")),
        password=os.getenv("MT5_DEFAULT_PASSWORD", ""),
        server=os.getenv("MT5_DEFAULT_SERVER", ""),
        path=os.getenv("MT5_TERMINAL_PATH") or None,
    ),
    MT5ConnectionConfig(),
)
risk_engine = RiskEngine(repository=repository, connector=connector)
execution_engine = ExecutionEngine(connector=connector, risk_engine=risk_engine, db_repository=repository)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await repository.connect()
    yield
    await repository.close()


app = FastAPI(title="trading_service", lifespan=lifespan)


@app.post("/orders")
async def execute_order(payload: OrderIn):
    try:
        order = Order(
            id=str(uuid4()),
            client_order_id=str(uuid4()),
            account_id=payload.account_id,
            strategy_id=payload.strategy_id,
            model_id=payload.model_id,
            symbol=payload.symbol,
            side=OrderSide(payload.side.upper()),
            order_type=OrderType(payload.order_type.upper()),
            quantity=payload.quantity,
        )
        await repository.save_order(order.to_dict())
        await execution_engine.submit_order(order)
        return order.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = await execution_engine.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order.to_dict() if hasattr(order, "to_dict") else order


@app.get("/account/{account_id}")
async def get_account_info(account_id: str):
    account_info = await connector.get_account_info()
    account_state = await repository.get_account_state(account_id)
    return {"broker": account_info, "state": account_state}


@app.get("/health")
async def health():
    return {"status": "ok"}
