from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta

from trading_service.src.connectors.mt5 import MT5Connector, MT5Credentials, RETCODE_MAPPING


async def run(mode: str) -> int:
    creds = MT5Credentials(account_id=int(os.environ["MT5_DEFAULT_ACCOUNT_ID"]), password=os.environ["MT5_DEFAULT_PASSWORD"], server=os.environ["MT5_DEFAULT_SERVER"], path=os.environ.get("MT5_TERMINAL_PATH"))
    conn = MT5Connector(creds)
    if not await conn.connect():
        print("connect failed")
        return 1

    failures = []
    symbols = ["EURUSD", "GBPUSD"]

    async def expect_ok(name, coro):
        try:
            res = await coro
            if isinstance(res, dict) and not res.get("ok", True):
                failures.append((name, res))
        except Exception as exc:
            failures.append((name, str(exc)))

    await expect_ok("market_buy", conn.execute_order({"symbol":"EURUSD","volume":0.01,"side":"BUY","type":"MARKET","client_order_id":"demo-buy"}))
    await expect_ok("market_sell", conn.execute_order({"symbol":"EURUSD","volume":0.01,"side":"SELL","type":"MARKET","client_order_id":"demo-sell"}))
    await expect_ok("limit_order", conn.execute_order({"symbol":"EURUSD","volume":0.01,"side":"BUY","type":"LIMIT","price":1.0,"stop_price":0.9,"limit_price":1.1,"client_order_id":"demo-limit"}))
    await expect_ok("stop_order", conn.execute_order({"symbol":"EURUSD","volume":0.01,"side":"BUY","type":"STOP","price":1.1,"client_order_id":"demo-stop"}))
    await expect_ok("stop_limit_order", conn.execute_order({"symbol":"EURUSD","volume":0.01,"side":"BUY","type":"STOP_LIMIT","price":1.1,"limit_price":1.2,"client_order_id":"demo-stop-limit"}))

    orders = await conn.get_orders()
    if orders:
        oid = orders[0].get("ticket") or orders[0].get("order")
        if oid:
            await expect_ok("modify_order", conn.modify_order(oid, price=orders[0].get("price_open", orders[0].get("price_current", 1.0))))
            await expect_ok("cancel_order", conn.cancel_order(oid))

    positions = await conn.get_positions()
    if positions:
        pid = positions[0].get("ticket")
        if pid:
            await expect_ok("close_position", conn.close_position(pid))
    await expect_ok("close_all_positions", conn.close_all_positions())

    bad = await conn.execute_order({"symbol":"INVALIDSYM","volume":0.01,"side":"BUY","type":"MARKET","client_order_id":"bad-sym"})
    if bad.get("ok"):
        failures.append(("invalid_symbol", bad))

    bad2 = await conn.execute_order({"symbol":"EURUSD","volume":999999,"side":"BUY","type":"MARKET","client_order_id":"bad-vol"})
    if bad2.get("ok"):
        failures.append(("invalid_volume", bad2))

    if mode != "smoke":
        print("retcode coverage:")
        for k,v in sorted(RETCODE_MAPPING.items()):
            if not v:
                failures.append(("retcode_map", k))

    await conn.disconnect()

    if failures:
        print("FAILURES")
        for f in failures:
            print(f)
        return 1
    print("ALL MT5 DEMO TESTS PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full","smoke"], default="full")
    args = parser.parse_args()
    return asyncio.run(run(args.mode))


if __name__ == "__main__":
    sys.exit(main())
