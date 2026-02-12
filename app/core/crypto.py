import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _master_key() -> bytes:
    raw = settings.encryption_master_key.encode()
    if len(raw) == 32:
        return raw
    return raw.ljust(32, b'0')[:32]


def encrypt_secret(plaintext: str) -> dict[str, bytes]:
    dek = os.urandom(32)

    data_nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(data_nonce, plaintext.encode(), None)

    dek_nonce = os.urandom(12)
    encrypted_dek = AESGCM(_master_key()).encrypt(dek_nonce, dek, None)

    return {
        'encrypted_dek': encrypted_dek,
        'dek_nonce': dek_nonce,
        'ciphertext': ciphertext,
        'data_nonce': data_nonce,
    }


def decrypt_secret(encrypted_dek: bytes, dek_nonce: bytes, ciphertext: bytes, data_nonce: bytes) -> str:
    dek = AESGCM(_master_key()).decrypt(dek_nonce, encrypted_dek, None)
    plaintext = AESGCM(dek).decrypt(data_nonce, ciphertext, None)
    return plaintext.decode()
