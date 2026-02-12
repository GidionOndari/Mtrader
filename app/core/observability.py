from prometheus_client import Counter, Histogram

AUTH_REQUESTS = Counter('mtrader_auth_requests_total', 'Total auth requests', ['route', 'status'])
VAULT_OPS = Counter('mtrader_vault_ops_total', 'Vault operations', ['operation', 'status'])
REQUEST_LATENCY = Histogram('mtrader_request_latency_seconds', 'Request latency', ['route'])
