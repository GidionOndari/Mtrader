from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models import ApiKeyVault, AuditAction
from app.services.audit_service import record_audit


def upsert_key(db: Session, user_id: int, provider: str, api_key: str) -> ApiKeyVault:
    encrypted = encrypt_secret(api_key)
    row = db.scalar(select(ApiKeyVault).where(ApiKeyVault.user_id == user_id, ApiKeyVault.provider == provider))
    if row is None:
        row = ApiKeyVault(
            user_id=user_id,
            provider=provider,
            key_last4=api_key[-4:],
            **encrypted,
        )
        db.add(row)
    else:
        row.key_last4 = api_key[-4:]
        row.encrypted_dek = encrypted['encrypted_dek']
        row.dek_nonce = encrypted['dek_nonce']
        row.ciphertext = encrypted['ciphertext']
        row.data_nonce = encrypted['data_nonce']
    db.commit()
    db.refresh(row)
    record_audit(db, user_id=user_id, action=AuditAction.SETTINGS_CHANGED, resource_type='vault', resource_id=str(row.id), details={'provider': provider})
    return row


def list_keys(db: Session, user_id: int) -> list[ApiKeyVault]:
    return list(db.scalars(select(ApiKeyVault).where(ApiKeyVault.user_id == user_id).order_by(ApiKeyVault.provider.asc())))


def delete_key(db: Session, user_id: int, key_id: int) -> None:
    row = db.scalar(select(ApiKeyVault).where(ApiKeyVault.id == key_id, ApiKeyVault.user_id == user_id))
    if not row:
        raise HTTPException(status_code=404, detail='Key not found')
    db.delete(row)
    db.commit()
    record_audit(db, user_id=user_id, action=AuditAction.SETTINGS_CHANGED, resource_type='vault', resource_id=str(key_id), details={'event': 'delete'})


def get_key_for_runtime(db: Session, user_id: int, provider: str) -> str:
    row = db.scalar(select(ApiKeyVault).where(ApiKeyVault.user_id == user_id, ApiKeyVault.provider == provider))
    if not row:
        raise HTTPException(status_code=404, detail='Provider key not found')
    record_audit(db, user_id=user_id, action=AuditAction.KEY_ACCESS, resource_type='vault', resource_id=str(row.id), details={'provider': provider})
    return decrypt_secret(row.encrypted_dek, row.dek_nonce, row.ciphertext, row.data_nonce)
