#!/bin/bash
set -e

docker stop test-postgres test-redis 2>/dev/null || true
docker rm test-postgres test-redis 2>/dev/null || true

echo "✅ Test environment cleaned"
