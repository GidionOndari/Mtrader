FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY requirements-dev.txt /app/requirements-dev.txt
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/requirements-dev.txt MetaTrader5
COPY . /app
RUN python -m compileall trading_service

FROM python:3.11-slim
RUN useradd -r -u 10002 appuser && apt-get update && apt-get install -y --no-install-recommends curl netcat-traditional && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . /app
USER appuser
EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8010/health || exit 1
CMD ["sh","-c","./scripts/wait-for-it.sh db:5432 -- ./scripts/wait-for-it.sh redis:6379 -- uvicorn trading_service.src.app:app --host 0.0.0.0 --port 8010"]
