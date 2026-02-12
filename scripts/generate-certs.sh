#!/bin/bash
set -e

CERT_DIR="deploy/certs"
mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_DIR/tls.crt" ] || [ ! -f "$CERT_DIR/tls.key" ]; then
    echo "Generating self-signed certificates..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/tls.key" \
        -out "$CERT_DIR/tls.crt" \
        -subj "/CN=lifehq.local/O=LifeHQ Development"
    echo "✅ Certificates generated"
else
    echo "✅ Certificates already exist"
fi
