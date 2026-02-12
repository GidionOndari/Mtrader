from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from api_gateway.src.middleware.rate_limit import WebSocketRateLimiter
from api_gateway.src.ws.auth import authenticate_websocket, periodic_revalidate
from api_gateway.src.ws.manager import RedisConnectionManager
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws"])


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=False)


def _topic_allowed(topic: str, claims: dict) -> bool:
    allowed_prefixes = [
        f"user:{claims['sub']}",
        f"account_updates:{claims['sub']}",
        f"position_updates:{claims['sub']}",
        f"order_updates:{claims['sub']}",
        f"market_data:{claims['sub']}",
        f"calendar_updates:{claims['sub']}",
        f"strategy_signals:{claims['sub']}",
    ]
    return any(topic.startswith(p) for p in allowed_prefixes)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    redis = _redis()
    rate_limiter = WebSocketRateLimiter(redis, connections_per_ip=settings.ws_max_connections_per_ip, messages_per_minute=settings.ws_rate_limit_per_minute)
    conn_id = str(uuid4())
    manager = RedisConnectionManager(redis, instance_id="api_gateway")

    try:
        client_ip = websocket.client.host if websocket.client else "unknown"
        if not await rate_limiter.check_connection_limit(client_ip):
            await websocket.close(code=4002)
            return

        claims = await authenticate_websocket(websocket, redis)
        user_id = str(claims["sub"])
        session_id = str(claims.get("jti"))

        await manager.start()
        await manager.connect(websocket, user_id=user_id, connection_id=conn_id, session_id=session_id)

        token = websocket.query_params.get("token") or ""
        fp = websocket.query_params.get("fp")
        revalidate_task = asyncio.create_task(periodic_revalidate(websocket, redis, token, fp), name=f"ws-revalidate-{conn_id}")

        async def heartbeat_monitor():
            while True:
                await asyncio.sleep(30)
                presence = await redis.hgetall(f"ws:connections:{conn_id}")
                if not presence:
                    await websocket.close(code=1001)
                    return
                last = presence.get(b"last_heartbeat")
                if last:
                    elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last.decode())
                    if elapsed.total_seconds() > 90:
                        await websocket.close(code=1001)
                        return

        hb_task = asyncio.create_task(heartbeat_monitor(), name=f"ws-heartbeat-monitor-{conn_id}")

        while True:
            msg = await websocket.receive_json()
            if not await rate_limiter.check_message_rate(conn_id):
                await websocket.close(code=4002)
                break

            event = msg.get("event")
            if event == "heartbeat":
                await manager.touch_heartbeat(conn_id)
                await websocket.send_json({"event": "heartbeat_ack", "ts": datetime.now(timezone.utc).isoformat()})
            elif event == "subscribe":
                topic = str(msg.get("topic", ""))
                if not topic or not _topic_allowed(topic, claims):
                    await websocket.close(code=4001)
                    break
                await manager.subscribe_user(user_id, [topic])
                if not await rate_limiter.check_subscription_limit(user_id):
                    await websocket.close(code=4002)
                    break
                await websocket.send_json({"event": "subscribed", "topic": topic})
            elif event == "unsubscribe":
                topic = str(msg.get("topic", ""))
                await manager.unsubscribe_user(user_id, [topic])
                await websocket.send_json({"event": "unsubscribed", "topic": topic})
            else:
                await websocket.send_json({"event": "error", "detail": "unsupported event"})

    except WebSocketDisconnect:
        logger.info("ws disconnect conn=%s", conn_id)
    except ValueError:
        await websocket.close(code=4001)
    except Exception:
        logger.exception("ws failure conn=%s", conn_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        try:
            await manager.disconnect(conn_id)
            await manager.stop()
            await redis.close()
        except Exception:
            pass


@router.get("/heartbeat")
async def deprecated_heartbeat():
    """
    Deprecated WebSocket endpoint.

    Returns 410 GONE with instructions to migrate.
    Clients MUST upgrade to /ws/v1/connect.
    """
    return JSONResponse(
        status_code=410,
        content={
            "error": "WebSocket endpoint moved",
            "message": "This endpoint is deprecated and no longer accepts connections",
            "new_endpoint": "/ws/v1/connect",
            "deprecation_date": "2024-01-01",
            "sunset_date": "2024-04-01",
            "documentation": "https://docs.lifehq.io/websocket-migration"
        },
        headers={
            "Deprecation": "True",
            "Sunset": "Sun, 01 Apr 2024 00:00:00 GMT",
            "Link": "</ws/v1/connect>; rel=\"alternate\""
        }
    )
