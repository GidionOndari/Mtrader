# Certificate Rotation Runbook

## Procedure
1. Generate new certificate and private key.
2. Validate certificate subject and expiry.
3. Deploy certificate files to `deploy/certs`.
4. Reload nginx and verify HTTPS endpoint.

## Verification
- `openssl x509 -in deploy/certs/tls.crt -noout -dates`
- `curl -vk https://localhost/health`
