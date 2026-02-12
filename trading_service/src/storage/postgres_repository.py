from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, List, Optional

import asyncpg
from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)


class PostgresRepository:
    def __init__(self, dsn: str, min_size: int = 2, max_size: int = 20):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=self.min_size, max_size=self.max_size, command_timeout=30)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def _execute_retry(self, fn, retries: int = 3):
        last_exc = None
        for attempt in range(retries):
            try:
                return await fn()
            except (asyncpg.PostgresConnectionError, asyncpg.TooManyConnectionsError) as exc:
                last_exc = exc
                await asyncio.sleep(0.2 * (2**attempt))
        raise last_exc

    async def save_order(self, order: Dict) -> str:
        async def _run():
            assert self.pool
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    existing = await conn.fetchrow("SELECT id FROM orders WHERE client_order_id=$1", order.get("client_order_id"))
                    if existing:
                        return str(existing["id"])
                    row = await conn.fetchrow(
                        """
                        INSERT INTO orders (id, client_order_id, account_id, strategy_id, model_id, symbol, side, order_type, quantity, filled_quantity, price, stop_price, limit_price, status, rejection_reason, commission, swap, profit, opened_at, closed_at, created_at, updated_at, version)
                        VALUES (COALESCE($1::uuid, gen_random_uuid()), $2, $3::uuid, $4::uuid, $5::uuid, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, NOW(), NOW(), 1)
                        RETURNING id
                        """,
                        order.get("id"), order.get("client_order_id"), order.get("account_id"), order.get("strategy_id"), order.get("model_id"), order.get("symbol"), order.get("side"), order.get("order_type"), float(order.get("quantity", 0)), float(order.get("filled_quantity", 0)), order.get("price"), order.get("stop_price"), order.get("limit_price"), order.get("status"), order.get("rejection_reason"), float(order.get("commission", 0)), float(order.get("swap", 0)), float(order.get("profit", 0)), order.get("opened_at"), order.get("closed_at"),
                    )
                    return str(row["id"])
        return await self._execute_retry(_run)

    async def get_order(self, order_id: str) -> Optional[Dict]:
        assert self.pool
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM orders WHERE id=$1::uuid", order_id)
            return dict(row) if row else None

    async def update_order_status(self, order_id: str, status: str, **kwargs) -> bool:
        async def _run():
            assert self.pool
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow("SELECT version FROM orders WHERE id=$1::uuid FOR UPDATE", order_id)
                    if not row:
                        return False
                    version = int(row["version"])
                    updates = {"status": status, "updated_at": "NOW()", "version": version + 1}
                    updates.update(kwargs)
                    set_parts = []
                    vals = [order_id]
                    idx = 2
                    for k, v in updates.items():
                        if v == "NOW()":
                            set_parts.append(f"{k}=NOW()")
                        else:
                            set_parts.append(f"{k}=${idx}")
                            vals.append(v)
                            idx += 1
                    vals.append(version)
                    sql = f"UPDATE orders SET {', '.join(set_parts)} WHERE id=$1::uuid AND version=${idx}"
                    result = await conn.execute(sql, *vals)
                    return result.endswith("1")
        return await self._execute_retry(_run)

    async def get_open_orders(self, account_id: str) -> List[Dict]:
        assert self.pool
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM orders WHERE account_id=$1::uuid AND status IN ('PENDING','VALIDATED','SUBMITTED','PARTIAL')", account_id)
            return [dict(r) for r in rows]

    async def save_trade(self, trade: Dict) -> str:
        assert self.pool
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO trades (id, order_id, account_id, position_id, symbol, side, volume, price, commission, swap, profit, created_at) VALUES (COALESCE($1::uuid, gen_random_uuid()), $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8, $9, $10, $11, NOW()) RETURNING id", trade.get("id"), trade.get("order_id"), trade.get("account_id"), trade.get("position_id"), trade.get("symbol"), trade.get("side"), float(trade.get("volume", 0)), float(trade.get("price", 0)), float(trade.get("commission", 0)), float(trade.get("swap", 0)), float(trade.get("profit", 0)))
            return str(row["id"])

    async def get_position(self, position_id: str) -> Optional[Dict]:
        assert self.pool
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM positions WHERE id=$1::uuid", position_id)
            return dict(row) if row else None

    async def update_position(self, position_id: str, **kwargs) -> bool:
        if not kwargs:
            return True
        assert self.pool
        async with self.pool.acquire() as conn:
            set_parts = []
            vals = [position_id]
            idx = 2
            for k, v in kwargs.items():
                set_parts.append(f"{k}=${idx}")
                vals.append(v)
                idx += 1
            sql = f"UPDATE positions SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=$1::uuid"
            result = await conn.execute(sql, *vals)
            return result.endswith("1")

    async def close_position(self, position_id: str, exit_price: float) -> bool:
        return await self.update_position(position_id, current_price=exit_price, closed_at="now")

    async def save_risk_incident(self, incident: Dict) -> str:
        assert self.pool
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO risk_incidents (id, rule_type, parameters, actual_values, order_id, account_id, action_taken, created_at) VALUES (gen_random_uuid(), $1, $2::jsonb, $3::jsonb, $4, $5, $6, NOW()) RETURNING id", incident.get("rule_type"), json.dumps(incident.get("parameters", {})), json.dumps(incident.get("actual_values", {})), incident.get("order_id"), incident.get("account_id"), incident.get("action_taken"))
            return str(row["id"])
