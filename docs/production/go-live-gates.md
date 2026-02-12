# LIFE HQ — PRODUCTION GO-LIVE GATES

## GATE 1 — Code & Configuration
| Gate | Requirement | Verification Command | Status |
|---|---|---|---|
| G1.1 | If frontend is present, lockfile exists and matches | `npm --prefix frontend ci --dry-run` | ☐ |
| G1.2 | No hardcoded secrets | `grep -r "postgres:postgres" trading_service/` | ☐ |
| G1.3 | All migrations are Alembic Python revisions | `ls migrations/versions/*.sql \| wc -l` | ☐ |

## GATE 2 — CI & Branch Protection
| Gate | Requirement | Verification Command | Status |
|---|---|---|---|
| G2.1 | Last CI run successful | `gh run list --limit=1 --json conclusion` | ☐ |
| G2.2 | Branch protection enforced | `gh api repos/:owner/:repo/branches/main/protection` | ☐ |
| G2.3 | Baseline artifacts exist | `test -f .baseline/run/latest-run-id.txt` | ☐ |

## GATE 3 — Security & Encryption
| Gate | Requirement | Verification Command | Status |
|---|---|---|---|
| G3.1 | Crypto tests pass | `pytest tests/unit/test_crypto.py -q` | ☐ |
| G3.2 | Backup verification tests pass | `pytest tests/unit/test_backup_verification.py -q` | ☐ |
| G3.3 | No in-memory repositories | `grep -r "in_memory" trading_service/` | ☐ |

## GATE 4 — Operational Readiness
| Gate | Requirement | Verification Command | Status |
|---|---|---|---|
| G4.1 | Burn-in report < 7 days old | `find docs/operations -name "burnin-*.md" -mtime -7` | ☐ |
| G4.2 | DR drill < 30 days old | `find docs/operations -name "dr-drill-*.md" -mtime -30` | ☐ |
| G4.3 | On-call schedule current | `grep -q "$(date +%Y)-W" docs/operations/oncall.md` | ☐ |

## GATE 5 — Deployment & Runtime
| Gate | Requirement | Verification Command | Status |
|---|---|---|---|
| G5.1 | Compose configuration validates | `docker-compose -f docker-compose.prod.yml config` | ☐ |
| G5.2 | Healthchecks pass | `./scripts/verify-healthchecks.sh` | ☐ |
| G5.3 | Migration verification passes | `python scripts/verify_migration.py --environment production` | ☐ |

## GATE 6 — Compliance & Legal
| Gate | Requirement | Verification Command | Status |
|---|---|---|---|
| G6.1 | Traceability matrix complete | `grep -q "✅" docs/compliance/traceability-matrix.md` | ☐ |
| G6.2 | Production certificate signed | `grep -q "SIGNATORIES" docs/compliance/production-certificate.md` | ☐ |
| G6.3 | Incident response verified | `test -f docs/security/incident-response-verified-*.md` | ☐ |

## ✅ FINAL GO-LIVE AUTHORIZATION
All gates must be PASS before deployment.

Engineering Lead: _________________ Date: _____________
SRE Lead: _________________ Date: _____________
Security Officer: _________________ Date: _____________
Product Manager: _________________ Date: _____________
