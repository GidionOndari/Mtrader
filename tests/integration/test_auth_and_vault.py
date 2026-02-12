def test_auth_and_vault_flow(client):
    register = client.post('/api/v1/auth/register', json={'email': 'user@example.com', 'password': 'ComplexPass123!'})
    assert register.status_code == 200, register.text

    login = client.post(
        '/api/v1/auth/login',
        json={'email': 'user@example.com', 'password': 'ComplexPass123!', 'device_fingerprint': 'device-abc-001'},
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert 'access_token' in tokens and 'refresh_token' in tokens

    headers = {'Authorization': f"Bearer {tokens['access_token']}"}

    save = client.post('/api/v1/vault/keys', headers=headers, json={'provider': 'newsapi', 'api_key': 'news-key-123456'})
    assert save.status_code == 200, save.text
    body = save.json()
    assert body['key_last4'] == '3456'

    lst = client.get('/api/v1/vault/keys', headers=headers)
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    test_key = client.post('/api/v1/vault/test', headers=headers, json={'provider': 'newsapi'})
    assert test_key.status_code == 200
    assert test_key.json()['ok'] is True

    refreshed = client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token'], 'device_fingerprint': 'device-abc-001'})
    assert refreshed.status_code == 200
