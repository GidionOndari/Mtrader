#!/bin/bash
set -e

RUNBOOKS=(
  "docs/runbooks/kill-switch.md"
  "docs/runbooks/database-recovery.md"
  "docs/runbooks/mt5-troubleshooting.md"
  "docs/runbooks/certificate-rotation.md"
  "docs/runbooks/on-call-handoff.md"
)

FAILED=0
for runbook in "${RUNBOOKS[@]}"; do
  if [ ! -f "$runbook" ]; then
    echo "❌ Missing: $runbook"
    FAILED=$((FAILED+1))
  else
    grep -q "## Procedure" "$runbook" || echo "⚠️ $runbook missing Procedure section"
    grep -q "## Verification" "$runbook" || echo "⚠️ $runbook missing Verification section"
    echo "✅ $runbook exists"
  fi
done

exit $FAILED
