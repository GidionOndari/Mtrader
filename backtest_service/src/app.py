from __future__ import annotations

from datetime import datetime

import pandas as pd
from fastapi import FastAPI

from backtest_service.src.engine.backtester import BacktestEngine

app = FastAPI(title="backtest_service")
engine = BacktestEngine()


def _strategy(df: pd.DataFrame, **_):
    out = df.copy()
    out["signal"] = (out["close"].pct_change().fillna(0) > 0).astype(int) * 2 - 1
    return out


@app.post("/walk-forward")
async def run_walk_forward():
    idx = pd.date_range(end=datetime.utcnow(), periods=360, freq="D")
    data = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0}, index=idx)
    results = await engine.run_walk_forward(_strategy, data, optimization_iterations=2, param_space={"window": [5, 10]})
    return {"segments": len(results)}


@app.post("/monte-carlo")
async def monte_carlo():
    result = await engine.monte_carlo([{"pnl": 1.0}, {"pnl": -0.5}, {"pnl": 0.8}], iterations=200)
    return {"mean": result["mean"], "std": result["std"]}


@app.get("/health")
async def health():
    return {"status": "ok"}
