#!/bin/bash
set -e

echo "🔧 Setting up test environment..."

docker run -d --name test-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=lifehq_test \
  -p 5433:5432 \
  timescale/timescaledb:2.11.2-pg14

docker run -d --name test-redis \
  -p 6380:6379 \
  redis:7-alpine

sleep 5

pip install -r requirements-dev.txt
pip install -r requirements.txt

export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/lifehq_test
export REDIS_URL=redis://localhost:6380/0
export ENVIRONMENT=test

alembic upgrade head

echo "✅ Test environment ready"
