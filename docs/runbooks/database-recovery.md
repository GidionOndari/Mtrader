# Database Recovery Runbook

1. Identify recovery point (timestamp / transaction id).
2. Stop writer services (`api_gateway`, `trading_service`, schedulers).
3. Restore from latest backup to standby instance.
4. Replay WAL to recovery target.
5. Validate schema migrations and extension health.
6. Run row-count and checksum verification on critical tables.
7. Reconcile positions/orders against broker API.
8. Bring services up in read-only mode.
9. Run synthetic health checks and smoke tests.
10. Promote to read-write and monitor elevated alerts for 30 minutes.


## Procedure
1. Follow documented mitigation steps in this runbook.
2. Execute commands in order and capture output.
3. Escalate if issue persists.

## Verification
- Confirm service health endpoints return success.
- Confirm monitoring alerts return to normal.
