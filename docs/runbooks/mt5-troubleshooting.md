# MT5 Troubleshooting Runbook

## Common Error Codes
- `10004 Requote`: retry order with updated market price/deviation.
- `10017 Order rejected`: verify symbol session, volume, stops, and account permissions.
- `10032 Market closed`: check session calendar/holiday schedule.
- `10033 No money`: reduce volume or free margin.
- `10035 Off quotes`: broker stream unavailable; reconnect terminal.
- `10041 Trade disabled`: symbol/account trade mode restrictions.
- `10060 Connection lost`: trigger reconnect flow and re-authenticate.

## Reconnection Procedure
1. Verify terminal process is alive.
2. Reinitialize MT5 API.
3. Login with stored account/server credentials.
4. Validate `account_info()` and `terminal_info()`.
5. Re-subscribe active symbols.

## Symbol Not Found
1. Confirm exact broker symbol suffix/prefix.
2. Call symbol list and validate visibility.
3. Execute `symbol_select(symbol, True)`.
4. Retry quote fetch.

## Margin Call Prevention
- Monitor margin level and free margin continuously.
- Enforce max exposure and per-trade risk caps.
- Auto-reduce positions on threshold breaches.

## Weekend/Holiday Handling
- Suspend order placement outside sessions.
- Keep heartbeat/reconnect active.
- Resume trading only after session open and spread normalization.


## Procedure
1. Follow documented mitigation steps in this runbook.
2. Execute commands in order and capture output.
3. Escalate if issue persists.

## Verification
- Confirm service health endpoints return success.
- Confirm monitoring alerts return to normal.
