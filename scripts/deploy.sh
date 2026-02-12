#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT=${1:?environment required}
VERSION=${2:?version required}
export PROFILE=$ENVIRONMENT
DEPLOY_ID="deploy-${VERSION}-$(date +%s)"
LOG="${DEPLOY_ID}.log"

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

switch_traffic(){
  local target=$1
  local weight=$2
  log "switching traffic target=${target} weight=${weight}%"
  curl -fsS -X POST "${LB_API_URL}/traffic" -H "Authorization: Bearer ${LB_API_TOKEN}" -H "Content-Type: application/json" -d "{\"target\":\"${target}\",\"weight\":${weight}}"
}

wait_ready(){
  local stack=$1
  for i in {1..60}; do
    if curl -fsS "${STACK_HEALTH_BASE}/${stack}/ready" >/dev/null; then
      return 0
    fi
    sleep 5
  done
  return 1
}

smoke_tests(){
  local base=$1
  curl -fsS "${base}/api/health/readiness" >/dev/null
  curl -fsS "${base}/health" >/dev/null
  python scripts/validate_mt5_demo.py --mode smoke
}

rollback(){
  local reason=$1
  log "ROLLBACK reason=${reason}"
  switch_traffic blue 100
  switch_traffic green 0
  docker compose -f docker-compose.prod.yml --profile green down || true
  log "rollback complete"
  exit 1
}

log "starting deployment id=${DEPLOY_ID} env=${ENVIRONMENT} version=${VERSION}"

echo "🔍 Verifying deployment assets..."
python scripts/verify_assets.py

if ! command -v alembic >/dev/null 2>&1; then
  echo "❌ Alembic CLI not found. Please install: pip install alembic"
  exit 1
fi

./scripts/generate-certs.sh

if [[ "$ENVIRONMENT" == "staging" ]]; then
  docker compose -f docker-compose.prod.yml --profile staging up -d --build
  alembic upgrade head
  python scripts/verify_migration.py --environment production
  if [ $? -ne 0 ]; then
    echo "❌ Migration verification failed. Initiating rollback..."
    alembic downgrade -1
    exit 1
  fi
  wait_ready staging || rollback "staging not ready"
  smoke_tests "${STAGING_BASE_URL}" || rollback "staging smoke tests failed"
  log "staging deploy successful"
  exit 0
fi

if [[ "$ENVIRONMENT" == "canary" ]]; then
  docker compose -f docker-compose.prod.yml --profile green up -d --build
  alembic upgrade head
  python scripts/verify_migration.py --environment production
  if [ $? -ne 0 ]; then
    echo "❌ Migration verification failed. Initiating rollback..."
    alembic downgrade -1
    exit 1
  fi
  wait_ready green || rollback "green not ready"
  smoke_tests "${GREEN_BASE_URL}" || rollback "green smoke tests failed"
  switch_traffic green 10
  switch_traffic blue 90
  log "canary running for 15 minutes"
  sleep 900
  bash scripts/canary-check.sh "$VERSION" || rollback "canary metrics breached"
  log "canary passed"
  exit 0
fi

if [[ "$ENVIRONMENT" == "production" ]]; then
  switch_traffic green 100
  switch_traffic blue 0
  docker compose -f docker-compose.prod.yml --profile blue down || true
  log "production cutover complete"
  exit 0
fi

log "unknown environment"
exit 1
