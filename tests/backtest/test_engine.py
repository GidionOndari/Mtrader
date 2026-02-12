import numpy as np
import pandas as pd
import pytest

from backtest_service.src.engine.backtester import BacktestEngine


def strategy(df, **kwargs):
    if len(df) < 3: return None
    if df['close'].iloc[-1] > df['close'].iloc[-2]: return 'buy'
    return 'close'


@pytest.mark.asyncio
async def test_backtest_metrics():
    idx = pd.date_range('2024-01-01', periods=200, freq='H')
    close = np.cumsum(np.random.randn(200)) + 100
    data = pd.DataFrame({'close': close, 'volume': np.random.randint(10, 100, size=200)}, index=idx)
    engine = BacktestEngine()
    res = await engine.run(strategy, data)
    assert isinstance(res.sharpe_ratio, float)
    assert res.total_trades >= 0
