from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.observability import AUTH_REQUESTS
from app.db import get_db
from app.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserOut
from app.services import auth_service

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/register', response_model=UserOut)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, payload)
    AUTH_REQUESTS.labels(route='register', status='ok').inc()
    return UserOut(id=user.id, email=user.email, role=user.role)


@router.post('/login', response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    tokens = auth_service.login(db, payload, request.client.host if request.client else None)
    AUTH_REQUESTS.labels(route='login', status='ok').inc()
    return tokens


@router.post('/refresh', response_model=TokenPair)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    tokens = auth_service.refresh_tokens(db, payload.refresh_token, payload.device_fingerprint, request.client.host if request.client else None)
    AUTH_REQUESTS.labels(route='refresh', status='ok').inc()
    return tokens
