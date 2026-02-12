from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.observability import VAULT_OPS
from app.db import get_db
from app.models import User
from app.schemas import VaultKeyUpsertRequest, VaultKeyView, VaultTestRequest, VaultTestResponse
from app.services.vault_service import delete_key, get_key_for_runtime, list_keys, upsert_key

router = APIRouter(prefix='/vault', tags=['vault'])


@router.get('/keys', response_model=list[VaultKeyView])
def get_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list_keys(db, user.id)
    return [VaultKeyView(id=r.id, provider=r.provider, key_last4=r.key_last4, updated_at=r.updated_at) for r in rows]


@router.post('/keys', response_model=VaultKeyView)
def put_key(payload: VaultKeyUpsertRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = upsert_key(db, user.id, payload.provider, payload.api_key)
    VAULT_OPS.labels(operation='upsert', status='ok').inc()
    return VaultKeyView(id=row.id, provider=row.provider, key_last4=row.key_last4, updated_at=row.updated_at)


@router.delete('/keys/{key_id}', status_code=204)
def remove_key(key_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_key(db, user.id, key_id)
    VAULT_OPS.labels(operation='delete', status='ok').inc()


@router.post('/test', response_model=VaultTestResponse)
def test_key(payload: VaultTestRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = get_key_for_runtime(db, user.id, payload.provider)
    ok = len(secret) >= 8
    return VaultTestResponse(provider=payload.provider, ok=ok, detail='Provider key loaded and decrypted for runtime use')
