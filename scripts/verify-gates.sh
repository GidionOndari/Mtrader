#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
FAILED=0
WARNED=0

pass() { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; FAILED=$((FAILED+1)); }
warn() { echo -e "${YELLOW}⚠️ $1${NC}"; WARNED=$((WARNED+1)); }

require_file() {
  local gate="$1"
  local file="$2"
  if [ -f "$file" ]; then
    pass "$gate"
  else
    fail "$gate missing required file: $file"
  fi
}

echo "🔍 VERIFYING PRODUCTION GO-LIVE GATES"
echo "======================================="

echo -e "\n${YELLOW}GATE 1: Code & Configuration${NC}"
if [ -f frontend/package.json ]; then
  if [ -f frontend/package-lock.json ]; then
    npm --prefix frontend ci --dry-run >/dev/null 2>&1 && pass "G1.1" || fail "G1.1 npm ci --dry-run failed"
  else
    fail "G1.1 frontend/package-lock.json missing while frontend/package.json exists"
  fi
else
  warn "G1.1 not applicable: frontend/package.json missing"
fi

grep -r "postgres:postgres" trading_service/ >/dev/null && fail "G1.2 hardcoded postgres:postgres found" || pass "G1.2"
[ "$(ls migrations/versions/*.sql 2>/dev/null | wc -l)" -eq 0 ] && pass "G1.3" || fail "G1.3 SQL migrations found in migrations/versions"

echo -e "\n${YELLOW}GATE 2: CI & Branch Protection${NC}"
if command -v gh >/dev/null 2>&1; then
  gh run list --limit 1 --json conclusion | grep -q '"conclusion":"success"' && pass "G2.1" || fail "G2.1 latest CI run is not success"
  gh api repos/:owner/:repo/branches/main/protection >/dev/null 2>&1 && pass "G2.2" || fail "G2.2 branch protection not verified"
else
  fail "G2.1/G2.2 gh CLI unavailable"
fi
require_file "G2.3" ".baseline/run/latest-run-id.txt"

echo -e "\n${YELLOW}GATE 3: Security & Encryption${NC}"
pytest tests/unit/test_crypto.py -q >/dev/null && pass "G3.1" || fail "G3.1 crypto tests failed"
pytest tests/unit/test_backup_verification.py -q >/dev/null && pass "G3.2" || fail "G3.2 backup verification tests failed"
rg -n "in_memory" trading_service/ >/dev/null && fail "G3.3 in_memory repository reference found" || pass "G3.3"

echo -e "\n${YELLOW}GATE 4: Operational Readiness${NC}"
find docs/operations -name "burnin-*.md" -mtime -7 | grep -q . && pass "G4.1" || fail "G4.1 missing fresh burn-in report"
find docs/operations -name "dr-drill-*.md" -mtime -30 | grep -q . && pass "G4.2" || fail "G4.2 missing recent DR drill report"
grep -q "$(date +%Y)-W" docs/operations/oncall.md && pass "G4.3" || fail "G4.3 on-call schedule not current"

echo -e "\n${YELLOW}GATE 5: Deployment & Runtime${NC}"
if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f docker-compose.prod.yml config >/dev/null && pass "G5.1" || fail "G5.1 docker-compose config failed"
else
  fail "G5.1 docker/docker-compose unavailable"
fi

if [ -f scripts/verify-healthchecks.sh ]; then
  bash scripts/verify-healthchecks.sh >/dev/null && pass "G5.2" || fail "G5.2 healthcheck verification failed"
else
  fail "G5.2 scripts/verify-healthchecks.sh missing"
fi
python scripts/verify_migration.py --environment production >/dev/null && pass "G5.3" || fail "G5.3 migration verification failed"

echo -e "\n${YELLOW}GATE 6: Compliance & Legal${NC}"
if [ -f docs/compliance/traceability-matrix.md ] && grep -q "✅" docs/compliance/traceability-matrix.md; then
  pass "G6.1"
else
  fail "G6.1 traceability matrix missing/incomplete"
fi

grep -q "SIGNATORIES" docs/compliance/production-certificate.md && pass "G6.2" || fail "G6.2 production certificate signatory block missing"
ls docs/security/incident-response-verified-*.md >/dev/null 2>&1 && pass "G6.3" || fail "G6.3 incident response verification file missing"

if [ $FAILED -eq 0 ]; then
  echo -e "\n${GREEN}✅ ALL HARD GATES PASSED${NC}"
  [ $WARNED -gt 0 ] && echo -e "${YELLOW}⚠️ $WARNED warning(s) present for non-applicable checks${NC}"
  exit 0
else
  echo -e "\n${RED}❌ $FAILED HARD GATE(S) FAILED${NC}"
  [ $WARNED -gt 0 ] && echo -e "${YELLOW}⚠️ $WARNED warning(s) present${NC}"
  exit 1
fi
