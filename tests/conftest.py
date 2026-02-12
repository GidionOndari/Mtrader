from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session", autouse=True)
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    os.environ["JWT_PRIVATE_KEY"] = base64.b64encode(priv_pem).decode()
    os.environ["JWT_PUBLIC_KEY"] = base64.b64encode(pub_pem).decode()
    os.environ["JWT_ISSUER"] = "test-issuer"
    os.environ["JWT_AUDIENCE"] = "test-aud"
    os.environ["JWT_ACCESS_TTL_MINUTES"] = "15"
    os.environ["JWT_REFRESH_TTL_DAYS"] = "7"
    os.environ["ENCRYPTION_MASTER_KEY"] = base64.b64encode(b"a" * 32).decode()
    os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mtrader_test")
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"
    os.environ["DB_SSL_MODE"] = "disable"
    os.environ["WS_RATE_LIMIT_PER_MINUTE"] = "5000"
    os.environ["WS_MAX_CONNECTIONS_PER_IP"] = "500"
    os.environ["APP_PORT"] = "8000"
    yield


@pytest.fixture(scope="session")
def db_engine(rsa_keys):
    from app.db import Base

    eng = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture(scope="session")
def redis_client(rsa_keys):
    client = Redis.from_url("redis://localhost:6379/15")
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def client(db_engine):
    from app.db import get_db
    from app.main import app

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    email = f"u{int(datetime.now().timestamp())}@example.com"
    password = "ComplexPass123!"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password, "device_fingerprint": "dev-fp-1"})
    token = r.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_mt5(monkeypatch):
    class Dummy:
        def __getattr__(self, name):
            return 1

    monkeypatch.setattr("trading_service.src.connectors.mt5.mt5", Dummy())
    return Dummy()
