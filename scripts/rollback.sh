#!/usr/bin/env bash
set -euo pipefail
INCIDENT_ID=${1:?incident ticket id required}
TS=$(date -Iseconds)
LOG="rollback_${INCIDENT_ID}_$(date +%s).log"

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

log "emergency rollback start incident=${INCIDENT_ID}"

curl -fsS -X POST "${LB_API_URL}/traffic" -H "Authorization: Bearer ${LB_API_TOKEN}" -H "Content-Type: application/json" -d '{"target":"blue","weight":100}'
curl -fsS -X POST "${LB_API_URL}/traffic" -H "Authorization: Bearer ${LB_API_TOKEN}" -H "Content-Type: application/json" -d '{"target":"green","weight":0}'

docker compose -f docker-compose.prod.yml --profile green down || true

curl -fsS -X POST "${NOTIFY_WEBHOOK_URL}" -H 'Content-Type: application/json' -d "{\"incident\":\"${INCIDENT_ID}\",\"status\":\"rollback-complete\",\"timestamp\":\"${TS}\"}"

log "rollback completed"
