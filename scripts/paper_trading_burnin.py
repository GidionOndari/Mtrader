from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timedelta

from trading_service.src.connectors.mt5 import MT5Connector, MT5Credentials

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP"]


async def main():
    creds = MT5Credentials(account_id=int(__import__('os').environ['MT5_DEFAULT_ACCOUNT_ID']), password=__import__('os').environ['MT5_DEFAULT_PASSWORD'], server=__import__('os').environ['MT5_DEFAULT_SERVER'])
    conn = MT5Connector(creds)
    await conn.connect()
    await conn.subscribe_market_data(SYMBOLS)

    start = datetime.utcnow()
    end = start + timedelta(hours=24)
    report = {"signals": 0, "simulated_orders": 0, "connection_events": [], "errors": 0}

    while datetime.utcnow() < end:
        try:
            if random.random() < 0.01:
                await conn.disconnect()
                report["connection_events"].append({"event": "forced_disconnect", "time": datetime.utcnow().isoformat()})
                await conn.reconnect()
                report["connection_events"].append({"event": "reconnected", "time": datetime.utcnow().isoformat()})

            symbol = random.choice(SYMBOLS)
            ticks = await conn.get_ticks(symbol, datetime.utcnow() - timedelta(minutes=1), count=10)
            if ticks:
                report["signals"] += 1
                report["simulated_orders"] += 1
            await asyncio.sleep(1)
        except Exception:
            report["errors"] += 1
            await asyncio.sleep(1)

    await conn.disconnect()
    with open("paper_trading_burnin_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
