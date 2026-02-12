from __future__ import annotations

import base64
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    development = "development"
    staging = "staging"
    production = "production"


class SSLMode(str, Enum):
    disable = "disable"
    allow = "allow"
    prefer = "prefer"
    require = "require"
    verify_ca = "verify-ca"
    verify_full = "verify-full"


def _read_from_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise ValueError("Configured key path does not exist")
    return p.read_text(encoding="utf-8")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    environment: Environment = Environment.production

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    ssl_mode: SSLMode = Field(alias="DB_SSL_MODE")

    jwt_issuer: str = Field(alias="JWT_ISSUER")
    jwt_audience: str = Field(alias="JWT_AUDIENCE")
    jwt_access_ttl_minutes: int = Field(alias="JWT_ACCESS_TTL_MINUTES")
    jwt_refresh_ttl_days: int = Field(alias="JWT_REFRESH_TTL_DAYS")

    jwt_private_key: Optional[str] = Field(default=None, alias="JWT_PRIVATE_KEY")
    jwt_private_key_path: Optional[str] = Field(default=None, alias="JWT_PRIVATE_KEY_PATH")
    jwt_public_key: Optional[str] = Field(default=None, alias="JWT_PUBLIC_KEY")
    jwt_public_key_path: Optional[str] = Field(default=None, alias="JWT_PUBLIC_KEY_PATH")

    encryption_master_key: str = Field(alias="ENCRYPTION_MASTER_KEY")

    ws_rate_limit_per_minute: int = Field(alias="WS_RATE_LIMIT_PER_MINUTE")
    ws_max_connections_per_ip: int = Field(alias="WS_MAX_CONNECTIONS_PER_IP")

    app_port: int = Field(alias="APP_PORT")

    @field_validator("database_url")
    @classmethod
    def _validate_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("FATAL: DATABASE_URL must be postgresql scheme")
        return v

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("FATAL: REDIS_URL must be redis:// or rediss://")
        return v

    @field_validator("app_port")
    @classmethod
    def _validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("FATAL: APP_PORT out of range")
        return v

    @field_validator("jwt_access_ttl_minutes", "jwt_refresh_ttl_days")
    @classmethod
    def _validate_ttls(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("FATAL: token TTL values must be positive")
        return v

    @field_validator("encryption_master_key")
    @classmethod
    def _validate_master_key(cls, v: str) -> str:
        try:
            raw = base64.b64decode(v)
        except Exception as exc:
            raise ValueError("FATAL: ENCRYPTION_MASTER_KEY must be valid base64") from exc
        if len(raw) != 32:
            raise ValueError("FATAL: ENCRYPTION_MASTER_KEY must decode to exactly 32 bytes")
        return v

    @model_validator(mode="after")
    def _load_and_validate_keys(self) -> "Settings":
        priv = self.jwt_private_key or _read_from_path(self.jwt_private_key_path)
        pub = self.jwt_public_key or _read_from_path(self.jwt_public_key_path)

        if not priv:
            raise ValueError("FATAL: JWT_PRIVATE_KEY environment variable is required")
        if not pub:
            raise ValueError("FATAL: JWT_PUBLIC_KEY environment variable is required")

        try:
            priv_bytes = base64.b64decode(priv)
            pub_bytes = base64.b64decode(pub)
        except Exception as exc:
            raise ValueError("FATAL: JWT keys must be base64-encoded PEM data") from exc

        try:
            loaded_priv = serialization.load_pem_private_key(priv_bytes, password=None)
            loaded_pub = serialization.load_pem_public_key(pub_bytes)
            if not isinstance(loaded_priv, rsa.RSAPrivateKey):
                raise ValueError("invalid private key type")
            if not isinstance(loaded_pub, rsa.RSAPublicKey):
                raise ValueError("invalid public key type")
        except Exception as exc:
            raise ValueError("FATAL: JWT_PRIVATE_KEY/JWT_PUBLIC_KEY are not valid RSA keys") from exc

        self.jwt_private_key = priv
        self.jwt_public_key = pub
        return self


try:
    settings = Settings()
except ValidationError as exc:
    raise RuntimeError("FATAL: invalid configuration; verify required environment variables") from exc
except ValueError as exc:
    raise RuntimeError(str(exc)) from exc
