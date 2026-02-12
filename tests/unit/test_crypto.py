from app.core.crypto import decrypt_secret, encrypt_secret


def test_encrypt_decrypt_roundtrip():
    secret = 'abc123-super-secret'
    blob = encrypt_secret(secret)
    out = decrypt_secret(blob['encrypted_dek'], blob['dek_nonce'], blob['ciphertext'], blob['data_nonce'])
    assert out == secret
