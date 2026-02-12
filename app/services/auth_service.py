from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password, hash_refresh_token, verify_password
from app.models import AuditAction, RefreshToken, Role, User
from app.schemas import LoginRequest, RegisterRequest, TokenPair
from app.services.audit_service import record_audit


def register_user(db: Session, payload: RegisterRequest) -> User:
    exists = db.scalar(select(User).where(User.email == payload.email.lower()))
    if exists:
        raise HTTPException(status_code=409, detail='Email already registered')

    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), role=Role.USER)
    db.add(user)
    db.commit()
    db.refresh(user)
    record_audit(db, user_id=user.id, action=AuditAction.SETTINGS_CHANGED, resource_type='user', resource_id=str(user.id), details={'event': 'register'})
    return user


def login(db: Session, payload: LoginRequest, ip: str | None) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')

    refresh = create_refresh_token()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh),
        device_fingerprint=payload.device_fingerprint,
        expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(rt)
    db.commit()

    record_audit(db, user_id=user.id, action=AuditAction.LOGIN, resource_type='session', resource_id=str(rt.id), ip_address=ip)
    return TokenPair(access_token=create_access_token(str(user.id), user.role.value), refresh_token=refresh)


def refresh_tokens(db: Session, refresh_token: str, device_fingerprint: str, ip: str | None) -> TokenPair:
    token_hash = hash_refresh_token(refresh_token)
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False)))
    if not rt:
        raise HTTPException(status_code=401, detail='Invalid refresh token')

    now = datetime.utcnow()
    if rt.expires_at < now:
        rt.revoked = True
        db.commit()
        raise HTTPException(status_code=401, detail='Refresh token expired')

    inactive_minutes = (now - rt.last_activity_at).total_seconds() / 60
    if inactive_minutes > settings.inactivity_timeout_minutes:
        rt.revoked = True
        db.commit()
        raise HTTPException(status_code=401, detail='Session inactive')

    if rt.device_fingerprint != device_fingerprint:
        raise HTTPException(status_code=401, detail='Device mismatch')

    user = db.get(User, rt.user_id)
    rt.revoked = True

    new_refresh = create_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(new_refresh),
            device_fingerprint=device_fingerprint,
            expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    db.commit()

    record_audit(db, user_id=user.id, action=AuditAction.TOKEN_REFRESH, resource_type='session', ip_address=ip)
    return TokenPair(access_token=create_access_token(str(user.id), user.role.value), refresh_token=new_refresh)
