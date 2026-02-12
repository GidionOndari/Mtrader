import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from trading_service.src.connectors.mt5 import MT5Connector, MT5Credentials


@pytest.mark.asyncio
async def test_connect_failure_no_module(monkeypatch):
    creds = MT5Credentials(account_id=1, password="x", server="s")
    c = MT5Connector(creds)
    with patch('trading_service.src.connectors.mt5.mt5', None):
        assert await c.connect() is False


@pytest.mark.asyncio
async def test_duplicate_idempotency(monkeypatch):
    creds = MT5Credentials(account_id=1, password='x', server='s')
    c = MT5Connector(creds)
    c._idempotency['abc'] = 123
    out = await c.execute_order({'symbol':'EURUSD','volume':0.1,'side':'BUY','type':'MARKET','client_order_id':'abc'})
    assert out['duplicate'] is True


@pytest.mark.asyncio
async def test_get_ticks_no_data(monkeypatch):
    creds = MT5Credentials(account_id=1, password='x', server='s')
    c = MT5Connector(creds)
    with patch('trading_service.src.connectors.mt5.mt5') as m:
        m.copy_ticks_from.return_value = []
        out = await c.get_ticks('EURUSD', datetime.utcnow() - timedelta(minutes=1), count=10)
        assert out == []
