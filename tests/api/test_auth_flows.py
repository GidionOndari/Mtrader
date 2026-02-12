from __future__ import annotations

import pytest

from app.core.security import create_token_pair, rotate_refresh_token, revoke_all_user_tokens, verify_token


@pytest.mark.asyncio
async def test_login_refresh_flow(redis_client):
    pair = await create_token_pair("user-1", "fp-1")
    payload = await verify_token(redis_client, pair.access_token, "fp-1")
    assert payload["sub"] == "user-1"

    rotated = await rotate_refresh_token(redis_client, pair.refresh_token, "fp-1")
    assert rotated.family_id == pair.family_id


@pytest.mark.asyncio
async def test_invalid_fingerprint_rejected(redis_client):
    pair = await create_token_pair("user-1", "fp-1")
    with pytest.raises(ValueError):
        await verify_token(redis_client, pair.access_token, "fp-2")


@pytest.mark.asyncio
async def test_token_reuse_detection(redis_client):
    pair = await create_token_pair("user-1", "fp-1")
    await rotate_refresh_token(redis_client, pair.refresh_token, "fp-1")
    with pytest.raises(ValueError):
        await rotate_refresh_token(redis_client, pair.refresh_token, "fp-1")


@pytest.mark.asyncio
async def test_revoke_all_user_tokens(redis_client):
    pair = await create_token_pair("user-1", "fp-1")
    await revoke_all_user_tokens(redis_client, "user-1", "incident")
    with pytest.raises(ValueError):
        await verify_token(redis_client, pair.access_token, "fp-1")
