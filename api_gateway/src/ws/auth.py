from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict

from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.security import verify_token


async def authenticate_websocket(websocket: WebSocket, redis: Redis) -> Dict:
    token = websocket.query_params.get("token")
    fingerprint = websocket.query_params.get("fp")
    if not token:
        raise ValueError("missing token")
    return await verify_token(redis, token, fingerprint)


async def periodic_revalidate(websocket: WebSocket, redis: Redis, token: str, fingerprint: str | None, interval_seconds: int = 300):
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await verify_token(redis, token, fingerprint)
        except Exception:
            await websocket.close(code=4003)
            return
