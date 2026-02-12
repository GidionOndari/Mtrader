from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from argon2 import PasswordHasher
from jose import JWTError, jwt
from redis.asyncio import Redis

from app.core.config import settings

ph = PasswordHasher()


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_jti: str
    refresh_jti: str
    family_id: str


def _private_key_bytes() -> bytes:
    return base64.b64decode(settings.jwt_private_key or "")


def _public_key_bytes() -> bytes:
    return base64.b64decode(settings.jwt_public_key or "")


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except Exception:
        return False


def _build_claims(subject: str, ttl: timedelta, token_type: str, family_id: Optional[str] = None, fingerprint: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    claims = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": jti,
        "typ": token_type,
    }
    if family_id:
        claims["fid"] = family_id
    if fingerprint:
        claims["fp"] = hashlib.sha256(fingerprint.encode()).hexdigest()
    return claims


def create_access_token(subject: str, fingerprint: str) -> tuple[str, str]:
    claims = _build_claims(subject, timedelta(minutes=settings.jwt_access_ttl_minutes), "access", fingerprint=fingerprint)
    token = jwt.encode(claims, _private_key_bytes(), algorithm="RS256")
    return token, claims["jti"]


def create_refresh_token(subject: str, family_id: str, fingerprint: str) -> tuple[str, str]:
    claims = _build_claims(subject, timedelta(days=settings.jwt_refresh_ttl_days), "refresh", family_id=family_id, fingerprint=fingerprint)
    token = jwt.encode(claims, _private_key_bytes(), algorithm="RS256")
    return token, claims["jti"]


async def create_token_pair(subject: str, fingerprint: str) -> TokenPair:
    family_id = str(uuid4())
    access_token, access_jti = create_access_token(subject, fingerprint)
    refresh_token, refresh_jti = create_refresh_token(subject, family_id, fingerprint)
    return TokenPair(access_token, refresh_token, access_jti, refresh_jti, family_id)


def decode_payload(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            _public_key_bytes(),
            algorithms=["RS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require_jti": True, "require_exp": True, "require_iat": True},
        )
    except JWTError as exc:
        raise ValueError("invalid token") from exc


async def is_token_revoked(redis: Redis, jti: str) -> bool:
    return bool(await redis.exists(f"jwt:revoked:{jti}"))


async def revoke_token(redis: Redis, jti: str, expires_in: int) -> None:
    if expires_in <= 0:
        expires_in = 1
    await redis.set(f"jwt:revoked:{jti}", "1", ex=expires_in)


async def revoke_all_user_tokens(redis: Redis, user_id: str, reason: str) -> None:
    marker = f"jwt:user:revoke_after:{user_id}"
    await redis.set(marker, int(datetime.now(timezone.utc).timestamp()), ex=60 * 60 * 24 * 90)
    await redis.lpush(f"audit:token_revocations:{user_id}", f"{datetime.now(timezone.utc).isoformat()}|{reason}")


async def verify_token(redis: Redis, token: str, fingerprint: Optional[str] = None) -> Dict[str, Any]:
    payload = decode_payload(token)
    jti = str(payload.get("jti"))
    if not jti:
        raise ValueError("missing jti")
    if await is_token_revoked(redis, jti):
        raise ValueError("token revoked")

    revoke_after = await redis.get(f"jwt:user:revoke_after:{payload['sub']}")
    if revoke_after and int(payload.get("iat", 0)) <= int(revoke_after.decode()):
        raise ValueError("token globally revoked")

    if fingerprint:
        fp = hashlib.sha256(fingerprint.encode()).hexdigest()
        if payload.get("fp") != fp:
            raise ValueError("fingerprint mismatch")
    return payload


async def rotate_refresh_token(redis: Redis, refresh_token: str, fingerprint: str) -> TokenPair:
    payload = await verify_token(redis, refresh_token, fingerprint)
    if payload.get("typ") != "refresh":
        raise ValueError("not refresh token")

    jti = payload["jti"]
    family_id = payload.get("fid")
    used_key = f"jwt:refresh:used:{jti}"
    if await redis.exists(used_key):
        if family_id:
            await redis.set(f"jwt:refresh:family:revoked:{family_id}", "1", ex=60 * 60 * 24 * settings.jwt_refresh_ttl_days)
        raise ValueError("refresh token reuse detected")

    if family_id and await redis.exists(f"jwt:refresh:family:revoked:{family_id}"):
        raise ValueError("token family revoked")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    exp_ts = int(payload.get("exp", now_ts + 1))
    ttl = max(1, exp_ts - now_ts)
    await redis.set(used_key, "1", ex=ttl)
    await revoke_token(redis, jti, ttl)

    access, access_jti = create_access_token(str(payload["sub"]), fingerprint)
    new_refresh, refresh_jti = create_refresh_token(str(payload["sub"]), str(family_id), fingerprint)
    return TokenPair(access, new_refresh, access_jti, refresh_jti, str(family_id))
