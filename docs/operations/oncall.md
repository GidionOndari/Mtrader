# LifeHQ On-Call Policy

## Rotation Schedule
| Week | Primary | Secondary | Escalation |
|------|---------|-----------|------------|
| 2026-W07 | @jane.doe | @john.smith | @emily.chen |
| 2026-W08 | @john.smith | @mike.wang | @jane.doe |
| 2026-W09 | @mike.wang | @sarah.jones | @john.smith |
| 2026-W10 | @sarah.jones | @jane.doe | @mike.wang |

## Escalation Policy
| Level | Responder | Response Time | Method |
|-------|-----------|---------------|--------|
| 1 | Primary | 15 minutes | PagerDuty push + SMS |
| 2 | Secondary | 30 minutes | PagerDuty push |
| 3 | Engineering Manager | 60 minutes | Phone call |

## PagerDuty Integration
- **Service ID:** PXXXXXX
- **Schedule ID:** SCHEDULE-XXXXXX
- **Escalation Policy ID:** EPXXXXXX
- **Auto-acknowledge:** 2 minutes
- **Auto-resolve:** 4 hours (with verification)

## Opsgenie Fallback
- **Schedule ID:** lifehq-primary, lifehq-secondary
- **Heartbeat monitoring:** Enabled

## Alert Integration
- **PagerDuty Service ID:** PLH7XYZ
- **Slack Channel:** #oncall-lifehq
- **Opsgenie Schedule:** lifehq-primary, lifehq-secondary

## Handoff Procedure
**Weekly, Monday 09:00 UTC**

1. Outgoing primary reviews open incidents
2. Outgoing primary verifies dashboard health
3. Outgoing primary confirms last backup succeeded
4. Incoming primary acknowledges schedule in PagerDuty
5. Handoff documented in #oncall-lifehq
