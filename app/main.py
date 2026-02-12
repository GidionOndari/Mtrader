from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis

from app.api.routes import auth, health, vault
from app.core.config import settings
from app.db import Base, engine
from api_gateway.src.routes.ws import router as distributed_ws_router

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_PRIVATE_KEY",
    "JWT_PUBLIC_KEY",
    "ENCRYPTION_MASTER_KEY",
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    for k in REQUIRED_ENV_VARS:
        v = os.getenv(k)
        if not v:
            raise RuntimeError(f"FATAL: required environment variable missing: {k}")
    redis = Redis.from_url(settings.redis_url)
    try:
        pong = await redis.ping()
        if not pong:
            raise RuntimeError("FATAL: redis ping failed")
    finally:
        await redis.close()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="MTrader API Gateway", lifespan=lifespan)
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(vault.router, prefix="/api/v1")
app.include_router(distributed_ws_router)


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/health/readiness")
def readiness() -> JSONResponse:
    return JSONResponse({"status": "ready"})


@app.websocket("/ws/heartbeat")
async def deprecated_heartbeat(_):
    return


@app.get("/ws/heartbeat")
def deprecated_ws_endpoint() -> RedirectResponse:
    return RedirectResponse(url="/ws", status_code=410)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        workers=max(2, (os.cpu_count() or 2) // 2),
        proxy_headers=True,
        limit_concurrency=2000,
        backlog=2048,
        timeout_keep_alive=20,
    )
