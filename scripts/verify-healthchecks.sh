#!/bin/bash
set -euo pipefail

# Comma-separated URLs; defaults are local service health endpoints.
URLS="${HEALTHCHECK_URLS:-http://localhost:8000/health,http://localhost:8001/health,http://localhost:8002/health}"

IFS=',' read -r -a targets <<< "$URLS"
for url in "${targets[@]}"; do
  if ! curl -fsS --max-time 5 "$url" >/dev/null; then
    echo "healthcheck failed: $url"
    exit 1
  fi
done

echo "healthchecks ok"
