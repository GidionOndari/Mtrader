from __future__ import annotations

from typing import Dict, List

from trading_service.src.storage.postgres_repository import PostgresRepository


class PostgresOrderRepository(PostgresRepository):
    async def get_open_positions(self, account_id: str) -> List[Dict]:
        assert self.pool
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM positions WHERE account_id=$1::uuid AND closed_at IS NULL", account_id)
            return [dict(r) for r in rows]

    async def get_account_state(self, account_id: str) -> Dict:
        assert self.pool
        async with self.pool.acquire() as conn:
            account = await conn.fetchrow("SELECT id FROM broker_accounts WHERE id=$1::uuid", account_id)
            open_orders = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE account_id=$1::uuid AND status IN ('PENDING','VALIDATED','SUBMITTED','PARTIAL')", account_id)
            open_positions = await conn.fetchval("SELECT COUNT(*) FROM positions WHERE account_id=$1::uuid AND closed_at IS NULL", account_id)
            return {
                "account_id": str(account["id"]) if account else account_id,
                "open_orders": int(open_orders or 0),
                "open_positions": int(open_positions or 0),
            }

    async def save_audit_log(self, payload: Dict) -> None:
        assert self.pool
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO trade_audit_log (id, order_id, event_type, payload, created_at) VALUES (gen_random_uuid(), $1::uuid, $2, $3::jsonb, NOW())",
                payload.get("order_id"),
                payload.get("event_type", "event"),
                payload.get("payload", {}),
            )


class PostgresPositionRepository(PostgresOrderRepository):
    pass
