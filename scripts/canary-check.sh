#!/usr/bin/env bash
set -euo pipefail
VERSION=${1:?version required}
METRICS_URL=${METRICS_URL:-http://localhost:9090/api/v1/query}
MAX_ERROR_RATE=${MAX_ERROR_RATE:-0.01}
MAX_LATENCY=${MAX_LATENCY:-0.5}
MIN_SUCCESS_RATE=${MIN_SUCCESS_RATE:-0.99}

query_metric() {
  local query=$1
  curl -fsS --get "$METRICS_URL" --data-urlencode "query=$query" | python - <<'PY'
import json,sys
obj=json.load(sys.stdin)
res=obj.get('data',{}).get('result',[])
print(float(res[0]['value'][1]) if res else 0.0)
PY
}

log_file="canary_${VERSION}_$(date +%s).log"

for attempt in {1..10}; do
  error_rate=$(query_metric 'rate(order_status_changes_total{status="rejected"}[5m]) / rate(order_status_changes_total[5m])')
  p95_latency=$(query_metric 'histogram_quantile(0.95, sum(rate(order_processing_duration_seconds_bucket[5m])) by (le))')
  success_rate=$(query_metric '1 - (rate(order_status_changes_total{status="rejected"}[5m]) / rate(order_status_changes_total[5m]))')

  ts=$(date -Iseconds)
  echo "$ts version=$VERSION error_rate=$error_rate p95_latency=$p95_latency success_rate=$success_rate" | tee -a "$log_file"

  if python - <<PY
import sys
err=float('$error_rate')
lat=float('$p95_latency')
succ=float('$success_rate')
max_err=float('$MAX_ERROR_RATE')
max_lat=float('$MAX_LATENCY')
min_succ=float('$MIN_SUCCESS_RATE')
sys.exit(0 if (err < max_err and lat < max_lat and succ > min_succ) else 1)
PY
  then
    echo "canary PASS" | tee -a "$log_file"
    exit 0
  fi

  sleep $((2**attempt))
done

echo "canary FAIL" | tee -a "$log_file"
exit 1
