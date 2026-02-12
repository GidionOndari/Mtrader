from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import WebSocket
from redis.asyncio import Redis


@dataclass(slots=True)
class ConnectionMeta:
    user_id: str
    session_id: str
    connection_id: str
    connected_at: str
    last_heartbeat: str
    instance_id: str


class RedisConnectionManager:
    def __init__(self, redis_client: Redis, instance_id: str):
        self.redis = redis_client
        self.instance_id = instance_id
        self.pubsub = None
        self._local_connections: Dict[str, WebSocket] = {}
        self._listener_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        await self.pubsub.psubscribe("ws:broadcast:*")
        self._listener_task = asyncio.create_task(self._listen_pubsub())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            await asyncio.gather(self._listener_task, return_exceptions=True)
        if self.pubsub:
            await self.pubsub.close()

    async def connect(self, websocket: WebSocket, user_id: str, connection_id: str, session_id: str):
        await websocket.accept()
        now = datetime.now(timezone.utc).isoformat()
        self._local_connections[connection_id] = websocket
        key = f"ws:connections:{connection_id}"
        await self.redis.hset(
            key,
            mapping={
                "user_id": user_id,
                "session_id": session_id,
                "connection_id": connection_id,
                "connected_at": now,
                "last_heartbeat": now,
                "instance_id": self.instance_id,
            },
        )
        await self.redis.expire(key, 60 * 60 * 24)
        await self.redis.sadd(f"ws:user:{user_id}:connections", connection_id)

    async def disconnect(self, connection_id: str):
        key = f"ws:connections:{connection_id}"
        user_id = await self.redis.hget(key, "user_id")
        if user_id:
            await self.redis.srem(f"ws:user:{user_id.decode()}:connections", connection_id)
        await self.redis.delete(key)
        self._local_connections.pop(connection_id, None)

    async def publish(self, channel: str, message: Dict):
        await self.redis.publish(f"ws:broadcast:{channel}", json.dumps(message))

    async def subscribe_user(self, user_id: str, topics: List[str]):
        key = f"ws:subs:user:{user_id}"
        if topics:
            await self.redis.sadd(key, *topics)
        await self.redis.expire(key, 60 * 60 * 24)

    async def unsubscribe_user(self, user_id: str, topics: List[str]):
        if topics:
            await self.redis.srem(f"ws:subs:user:{user_id}", *topics)

    async def broadcast_to_user(self, user_id: str, topic: str, data: Dict):
        conn_ids = [c.decode() for c in await self.redis.smembers(f"ws:user:{user_id}:connections")]
        message = {"topic": topic, "data": data}
        for cid in conn_ids:
            ws = self._local_connections.get(cid)
            if ws:
                await ws.send_json(message)

    async def get_presence(self, user_id: str) -> List[Dict]:
        out: List[Dict] = []
        conn_ids = [c.decode() for c in await self.redis.smembers(f"ws:user:{user_id}:connections")]
        for cid in conn_ids:
            data = await self.redis.hgetall(f"ws:connections:{cid}")
            if data:
                out.append({k.decode(): v.decode() for k, v in data.items()})
        return out

    async def touch_heartbeat(self, connection_id: str):
        await self.redis.hset(
            f"ws:connections:{connection_id}",
            "last_heartbeat",
            datetime.now(timezone.utc).isoformat(),
        )

    async def _listen_pubsub(self):
        while True:
            msg = await self.pubsub.get_message(timeout=1.0)
            if not msg:
                await asyncio.sleep(0.05)
                continue
            channel = msg["channel"].decode().split("ws:broadcast:", 1)[-1]
            payload = json.loads(msg["data"])
            user_id = payload.get("user_id")
            if user_id:
                await self.broadcast_to_user(user_id, channel, payload)
