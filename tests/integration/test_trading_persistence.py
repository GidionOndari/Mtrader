import os
import uuid

import pytest

from trading_service.src.repositories.postgres_repository import PostgresOrderRepository


@pytest.mark.asyncio
async def test_postgres_repository_save_order_roundtrip():
    dsn = os.getenv("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL not set")

    repo = PostgresOrderRepository(dsn)
    await repo.connect()
    try:
        order = {
            "id": str(uuid.uuid4()),
            "client_order_id": str(uuid.uuid4()),
            "account_id": None,
            "strategy_id": None,
            "model_id": None,
            "symbol": "EURUSD",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 0.1,
            "filled_quantity": 0.0,
            "status": "PENDING",
        }
        oid = await repo.save_order(order)
        assert oid
    finally:
        await repo.close()
