from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass(slots=True)
class CommissionModel:
    commission_per_lot: float = 7.0
    currency: str = "USD"
    min_commission: float = 0.0

    def calculate(self, volume, price) -> float:
        return max(self.min_commission, abs(float(volume)) * self.commission_per_lot)


@dataclass(slots=True)
class SlippageModel:
    base_slippage: float = 0.0001
    volatility_multiplier: bool = True

    def calculate(self, price, volume, volatility=None) -> float:
        mult = 1.0 + (abs(float(volatility)) if (self.volatility_multiplier and volatility is not None) else 0)
        return float(price) * self.base_slippage * mult * np.log1p(abs(float(volume)))


@dataclass(slots=True)
class MarginModel:
    margin_rates: Dict[str, float] = field(default_factory=lambda: {"forex": 0.02, "indices": 0.05, "commodities": 0.10, "stocks": 0.20})

    def calculate_required(self, symbol, volume, price, asset_class="forex") -> float:
        rate = self.margin_rates.get(asset_class, self.margin_rates["forex"])
        return abs(float(volume) * float(price)) * rate


@dataclass
class BacktestResult:
    strategy_id: str
    strategy_name: str
    symbols: List[str]
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_percent: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    expectancy: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    parameters: Dict
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    monthly_returns: pd.Series
    trades: List[Dict]
    execution_time_ms: int
    optimization_iterations: int


class BacktestEngine:
    def __init__(self, commission_model=None, slippage_model=None, margin_model=None):
        self.commission_model = commission_model or CommissionModel()
        self.slippage_model = slippage_model or SlippageModel()
        self.margin_model = margin_model or MarginModel()

    async def run(self, strategy: Callable, data: pd.DataFrame, initial_capital=10000, commission=True, slippage=True, margin=True, **strategy_params) -> BacktestResult:
        start_ms = time.time()
        df = data.copy().sort_index()
        equity = initial_capital
        equity_curve = []
        trades = []
        position = None

        for i, (ts, row) in enumerate(df.iterrows()):
            signal = strategy(df.iloc[: i + 1], **strategy_params)
            price = float(row["close"])
            vol = float(row.get("volume", 1.0))

            if position is None and signal in ("buy", "sell"):
                qty = float(strategy_params.get("size", 1.0))
                required_margin = self.margin_model.calculate_required("SYMBOL", qty, price)
                if margin and required_margin > equity:
                    equity_curve.append(equity)
                    continue
                entry_price = price
                if slippage:
                    entry_price += self.slippage_model.calculate(price, qty, row.get("volatility", None)) * (1 if signal == "buy" else -1)
                position = {"side": signal, "qty": qty, "entry": entry_price, "time": ts}
            elif position is not None and signal == "close":
                exit_price = price
                if slippage:
                    exit_price -= self.slippage_model.calculate(price, position["qty"], row.get("volatility", None)) * (1 if position["side"] == "buy" else -1)
                pnl = (exit_price - position["entry"]) * position["qty"] * (1 if position["side"] == "buy" else -1)
                fee = self.commission_model.calculate(position["qty"], exit_price) if commission else 0.0
                pnl -= fee
                equity += pnl
                trades.append({"entry_time": position["time"], "exit_time": ts, "side": position["side"], "entry": position["entry"], "exit": exit_price, "qty": position["qty"], "pnl": pnl, "commission": fee})
                position = None
            equity_curve.append(equity)

        eq = pd.Series(equity_curve, index=df.index)
        ret = eq.pct_change().fillna(0)
        dd_curve = (eq / eq.cummax()) - 1
        max_dd = float(dd_curve.min()) if not dd_curve.empty else 0.0
        ann = (1 + ret.mean()) ** 252 - 1 if len(ret) else 0
        sharpe = (ret.mean() / (ret.std() + 1e-9)) * np.sqrt(252)
        downside = ret[ret < 0]
        sortino = (ret.mean() / (downside.std() + 1e-9)) * np.sqrt(252)
        calmar = ann / (abs(max_dd) + 1e-9)
        wins = [t["pnl"] for t in trades if t["pnl"] > 0]
        losses = [t["pnl"] for t in trades if t["pnl"] <= 0]
        profit_factor = (sum(wins) / abs(sum(losses))) if losses else float("inf")
        expectancy = np.mean([t["pnl"] for t in trades]) if trades else 0.0
        monthly = ret.resample("M").apply(lambda x: (1 + x).prod() - 1)

        return BacktestResult(
            strategy_id=strategy_params.get("strategy_id", "unknown"),
            strategy_name=strategy_params.get("strategy_name", getattr(strategy, "__name__", "strategy")),
            symbols=[strategy_params.get("symbol", "SYMBOL")],
            timeframe=strategy_params.get("timeframe", "M1"),
            start_date=df.index.min().to_pydatetime() if not df.empty else datetime.utcnow(),
            end_date=df.index.max().to_pydatetime() if not df.empty else datetime.utcnow(),
            initial_capital=float(initial_capital),
            final_capital=float(eq.iloc[-1] if not eq.empty else initial_capital),
            total_return=float((eq.iloc[-1] / initial_capital - 1) if not eq.empty else 0),
            annualized_return=float(ann),
            sharpe_ratio=float(sharpe),
            sortino_ratio=float(sortino),
            calmar_ratio=float(calmar),
            max_drawdown=float(abs(max_dd)),
            max_drawdown_percent=float(abs(max_dd) * 100),
            max_drawdown_duration=int((dd_curve < 0).sum()),
            win_rate=float((len(wins) / len(trades)) if trades else 0),
            profit_factor=float(profit_factor),
            expectancy=float(expectancy),
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            avg_win=float(np.mean(wins) if wins else 0),
            avg_loss=float(np.mean(losses) if losses else 0),
            largest_win=float(max(wins) if wins else 0),
            largest_loss=float(min(losses) if losses else 0),
            parameters=strategy_params,
            equity_curve=eq,
            drawdown_curve=dd_curve,
            monthly_returns=monthly,
            trades=trades,
            execution_time_ms=int((time.time() - start_ms) * 1000),
            optimization_iterations=int(strategy_params.get("optimization_iterations", 0)),
        )

    async def run_walk_forward(self, strategy, data, in_sample_years=3, out_sample_months=6, optimization_iterations=1000, param_space=None) -> List[BacktestResult]:
        df = data.sort_index()
        results = []
        start = df.index.min()
        end = df.index.max()
        cursor = start
        while cursor < end:
            in_end = cursor + pd.DateOffset(years=in_sample_years)
            out_end = in_end + pd.DateOffset(months=out_sample_months)
            in_sample = df[(df.index >= cursor) & (df.index < in_end)]
            out_sample = df[(df.index >= in_end) & (df.index < out_end)]
            if len(in_sample) < 50 or len(out_sample) < 20:
                break
            best_params = {}
            best_sharpe = -1e9
            for _ in range(optimization_iterations if param_space else 1):
                params = {k: np.random.choice(v) for k, v in (param_space or {}).items()}
                res = await self.run(strategy, in_sample, **params)
                if res.sharpe_ratio > best_sharpe:
                    best_sharpe = res.sharpe_ratio
                    best_params = params
            results.append(await self.run(strategy, out_sample, optimization_iterations=optimization_iterations, **best_params))
            cursor = cursor + pd.DateOffset(months=out_sample_months)
        return results

    async def monte_carlo(self, trades: List[Dict], iterations=10000, confidence_levels=[0.95, 0.99]) -> Dict:
        pnl = np.array([t.get("pnl", 0) for t in trades], dtype=float)
        if len(pnl) == 0:
            return {"distribution": [], "VaR": {}, "CVaR": {}}
        dist = []
        for _ in range(iterations):
            sample = np.random.choice(pnl, size=len(pnl), replace=True)
            dist.append(sample.sum())
        dist = np.array(dist)
        var = {str(c): float(np.quantile(dist, 1 - c)) for c in confidence_levels}
        cvar = {str(c): float(dist[dist <= np.quantile(dist, 1 - c)].mean()) for c in confidence_levels}
        return {"distribution": dist.tolist(), "mean": float(dist.mean()), "std": float(dist.std()), "VaR": var, "CVaR": cvar}

    async def stress_test(self, strategy, base_data, scenarios: List[Dict]) -> Dict:
        out = {}
        for s in scenarios:
            name = s.get("name", "scenario")
            shocked = base_data.copy()
            if s.get("type") == "price_shock":
                shocked["close"] = shocked["close"] * (1 + float(s.get("shock", -0.1)))
            elif s.get("type") == "volatility_spike":
                shocked["volatility"] = shocked.get("volatility", 0.01) * float(s.get("multiplier", 2))
            res = await self.run(strategy, shocked, strategy_name=f"stress_{name}")
            out[name] = {"total_return": res.total_return, "max_drawdown": res.max_drawdown, "sharpe": res.sharpe_ratio}
        return out
