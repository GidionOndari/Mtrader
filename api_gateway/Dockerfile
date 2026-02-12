FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/requirements-dev.txt
COPY . /app
RUN pytest -q

FROM python:3.11-slim
RUN useradd -r -u 10001 appuser && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8000/api/health/readiness || exit 1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--limit-concurrency","2000"]
