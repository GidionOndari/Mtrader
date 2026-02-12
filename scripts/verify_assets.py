#!/usr/bin/env python3
from pathlib import Path
import os
import re
import sys

compose = Path('docker-compose.prod.yml').read_text()
mounts = re.findall(r'-\s+\./([^:]+):', compose)
missing = []
for m in mounts:
    p = Path(m)
    if str(p).startswith('deploy/certs'):
        continue
    if not p.exists():
        missing.append(str(p))

crt = Path('deploy/certs/tls.crt')
if not crt.exists() and os.environ.get('ENVIRONMENT') == 'production':
    print('❌ Production requires certificates: deploy/certs/tls.crt missing')
    sys.exit(1)
elif not crt.exists():
    print('⚠️ Certificates not found, will generate at runtime')

if missing:
    print('Missing deployment assets:')
    for m in missing:
        print(f'- {m}')
    sys.exit(1)
print('All deployment assets present.')
