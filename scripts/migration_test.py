from __future__ import annotations

import os
import subprocess
import sys

import psycopg2


def run(cmd: list[str], env: dict) -> None:
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr)
        raise RuntimeError(f"command failed: {' '.join(cmd)}")


def fetch_columns(conn, table: str) -> dict[str, str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,),
    )
    return {r[0]: r[1] for r in cur.fetchall()}


def assert_columns(conn):
    orders = fetch_columns(conn, "orders")
    positions = fetch_columns(conn, "positions")
    expected_orders = {
        "client_order_id": "text",
        "version": "integer",
        "idempotency_key": "text",
        "parent_order_id": "uuid",
    }
    expected_positions = {
        "version": "integer",
        "unrealized_pnl": "numeric",
        "realized_pnl": "numeric",
    }
    for k, v in expected_orders.items():
        if k == "parent_order_id":
            assert orders.get(k) in {"uuid", "text"}, f"orders.{k} expected uuid/text got {orders.get(k)}"
        else:
            assert orders.get(k) == v, f"orders.{k} missing/type mismatch"
    for k, v in expected_positions.items():
        assert positions.get(k) == v, f"positions.{k} missing/type mismatch"


def insert_and_verify(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO users (email,password_hash,role,is_active) VALUES ('t@e.com','x','USER',true) ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO broker_accounts (user_id,broker_name,account_login,server,environment,encrypted_credentials,credentials_nonce,status) VALUES (1,'b','a','s','demo','\\x00','\\x00','ok') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO orders (opened_at, account_id, symbol, side, order_type, quantity, status, client_order_id, version) VALUES (NOW(), (SELECT id FROM broker_accounts LIMIT 1), 'EURUSD','BUY','MARKET',1,'PENDING','cid-1',1)")
    cur.execute("INSERT INTO positions (opened_at, account_id, symbol, side, quantity, entry_price, version, unrealized_pnl, realized_pnl) VALUES (NOW(), (SELECT id FROM broker_accounts LIMIT 1), 'EURUSD','BUY',1,1.1,1,0,0)")
    conn.commit()


def main():
    dsn = os.environ.get("MIGRATION_TEST_DSN")
    if not dsn:
        raise RuntimeError("MIGRATION_TEST_DSN required")

    env = os.environ.copy()
    env["DATABASE_URL"] = dsn

    run(["alembic", "upgrade", "002_timescale_trading_core"], env)
    run(["alembic", "upgrade", "003_align_trading_schema"], env)

    conn = psycopg2.connect(dsn)
    assert_columns(conn)
    insert_and_verify(conn)

    run(["alembic", "downgrade", "002_timescale_trading_core"], env)
    conn2 = psycopg2.connect(dsn)
    cols = fetch_columns(conn2, "orders")
    assert "client_order_id" not in cols

    run(["alembic", "upgrade", "head"], env)
    conn3 = psycopg2.connect(dsn)
    assert_columns(conn3)
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
