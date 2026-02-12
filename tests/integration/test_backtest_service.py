import pytest
import pandas as pd
from datetime import datetime

from backtest_service.src.engine.backtester import BacktestEngine


def strategy(df: pd.DataFrame, **_):
    out = df.copy()
    out["signal"] = 1
    return out


@pytest.mark.asyncio
async def test_walk_forward_and_monte_carlo():
    engine = BacktestEngine()
    idx = pd.date_range(end=datetime.utcnow(), periods=400, freq="D")
    data = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0}, index=idx)
    wf = await engine.run_walk_forward(strategy, data, optimization_iterations=1)
    mc = await engine.monte_carlo([{"pnl": 1.0}, {"pnl": -0.5}], iterations=100)
    assert isinstance(wf, list)
    assert "mean" in mc
