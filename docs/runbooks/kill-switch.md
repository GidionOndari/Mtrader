# Kill Switch Runbook

## Trigger Criteria
- Drawdown exceeds policy threshold
- Broker/API instability causing execution uncertainty
- Position reconciliation mismatch
- Security incident affecting trading integrity

## Trigger Methods
- UI: Risk Controls → Kill Switch
- API: `POST /api/v1/risk/kill-switch`
- DB emergency flag: update `risk_controls.kill_switch=true`

## Immediate Actions
1. Confirm kill switch event in audit trail.
2. Verify all open orders canceled.
3. Verify all positions closed (or manually flatten at broker).
4. Notify on-call + stakeholders.

## Investigation
- Collect logs/traces for last 30 minutes.
- Confirm trigger reason and data source validity.
- Reconcile broker positions vs local DB.
- Produce incident timeline.

## Resume Procedure
1. Fix root cause.
2. Run paper-mode validation for 30 minutes.
3. Release kill switch via admin workflow.
4. Resume strategies gradually with exposure caps.

## Post-Mortem Template
- Incident ID
- Trigger reason
- Impact window
- Financial impact
- Root cause
- Corrective actions
- Preventive actions


## Procedure
1. Follow documented mitigation steps in this runbook.
2. Execute commands in order and capture output.
3. Escalate if issue persists.

## Verification
- Confirm service health endpoints return success.
- Confirm monitoring alerts return to normal.
