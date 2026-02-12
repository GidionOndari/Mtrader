from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(slots=True)
class WebSocketRateLimiter:
    redis: Redis
    connections_per_ip: int = 20
    messages_per_minute: int = 600
    max_subscriptions: int = 100
    window_seconds: int = 60

    async def check_connection_limit(self, client_ip: str) -> bool:
        key = f"ws:conn:ip:{client_ip}"
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window_seconds)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window_seconds)
        _, _, count, _ = await pipe.execute()
        return int(count) <= self.connections_per_ip

    async def check_message_rate(self, connection_id: str) -> bool:
        key = f"ws:msg:{connection_id}"
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window_seconds)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window_seconds)
        _, _, count, _ = await pipe.execute()
        return int(count) <= self.messages_per_minute

    async def check_subscription_limit(self, user_id: str) -> bool:
        key = f"ws:subs:user:{user_id}"
        cnt = await self.redis.scard(key)
        return int(cnt) <= self.max_subscriptions
