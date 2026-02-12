from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

import numpy as np
import pandas as pd


@dataclass
class Model:
    id: str
    name: str
    version: int
    description: Optional[str]
    status: str
    stage: str
    model_type: str
    framework: Optional[str]
    artifact_path: str
    metrics: Dict
    parameters: Dict
    features: List[str]
    targets: List[str]
    training_start: Optional[datetime]
    training_end: Optional[datetime]
    trained_at: Optional[datetime]
    approved_at: Optional[datetime]
    approved_by: Optional[str]
    rejected_at: Optional[datetime]
    rejected_reason: Optional[str]
    deployed_at: Optional[datetime]
    deployed_by: Optional[str]
    performance_metrics: Dict
    created_at: datetime
    created_by: str


class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, Model] = {}

    async def register(self, name, model_type, artifact_path, metrics, parameters, features, targets, created_by, description=None, framework=None) -> Model:
        versions = [m.version for m in self._models.values() if m.name == name]
        version = max(versions) + 1 if versions else 1
        model = Model(
            id=str(uuid4()),
            name=name,
            version=version,
            description=description,
            status="development",
            stage="development",
            model_type=model_type,
            framework=framework,
            artifact_path=artifact_path,
            metrics=metrics,
            parameters=parameters,
            features=features,
            targets=targets,
            training_start=None,
            training_end=None,
            trained_at=datetime.utcnow(),
            approved_at=None,
            approved_by=None,
            rejected_at=None,
            rejected_reason=None,
            deployed_at=None,
            deployed_by=None,
            performance_metrics={},
            created_at=datetime.utcnow(),
            created_by=created_by,
        )
        self._models[model.id] = model
        return model

    async def get_model(self, model_id) -> Optional[Model]:
        return self._models.get(model_id)

    async def get_models_by_name(self, name) -> List[Model]:
        return sorted([m for m in self._models.values() if m.name == name], key=lambda x: x.version)

    async def get_production_model(self, name) -> Optional[Model]:
        prod = [m for m in self._models.values() if m.name == name and m.stage == "production" and m.status == "approved"]
        return sorted(prod, key=lambda x: x.version)[-1] if prod else None

    async def promote_to_staging(self, model_id, promoted_by) -> bool:
        model = self._models.get(model_id)
        if not model or not self._passes_gates(model.metrics):
            return False
        model.stage = "staging"
        model.status = "approved"
        model.approved_at = datetime.utcnow()
        model.approved_by = promoted_by
        return True

    async def promote_to_production(self, model_id, approved_by) -> bool:
        model = self._models.get(model_id)
        if not model or not self._passes_gates(model.metrics):
            return False
        for m in self._models.values():
            if m.name == model.name and m.stage == "production":
                m.stage = "archived"
        model.stage = "production"
        model.status = "approved"
        model.deployed_at = datetime.utcnow()
        model.deployed_by = approved_by
        model.approved_at = datetime.utcnow()
        model.approved_by = approved_by
        return True

    async def rollback(self, model_name) -> Model:
        versions = [m for m in self._models.values() if m.name == model_name and m.status == "approved"]
        if len(versions) < 2:
            raise ValueError("No rollback candidate")
        versions.sort(key=lambda x: x.version)
        current = versions[-1]
        previous = versions[-2]
        current.stage = "archived"
        previous.stage = "production"
        previous.deployed_at = datetime.utcnow()
        return previous

    async def reject(self, model_id, rejected_by, reason) -> None:
        model = self._models.get(model_id)
        if not model:
            raise ValueError("model not found")
        model.status = "rejected"
        model.stage = "rejected"
        model.rejected_at = datetime.utcnow()
        model.rejected_reason = f"{rejected_by}: {reason}"

    async def detect_drift(self, model_id, recent_data: pd.DataFrame) -> Dict:
        model = self._models.get(model_id)
        if not model:
            raise ValueError("model not found")
        report = {"psi": {}, "feature_drift": {}, "concept_drift": False}
        baseline = model.metrics.get("feature_baseline", {})
        for f in model.features:
            if f not in recent_data.columns:
                continue
            curr = recent_data[f].dropna().values
            if len(curr) == 0:
                continue
            ref = np.array(baseline.get(f, curr[: min(500, len(curr))]), dtype=float)
            bins = np.histogram_bin_edges(np.concatenate([ref, curr]), bins=10)
            ref_hist, _ = np.histogram(ref, bins=bins)
            cur_hist, _ = np.histogram(curr, bins=bins)
            ref_pct = np.clip(ref_hist / max(ref_hist.sum(), 1), 1e-6, None)
            cur_pct = np.clip(cur_hist / max(cur_hist.sum(), 1), 1e-6, None)
            psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
            report["psi"][f] = psi
            report["feature_drift"][f] = psi > 0.2
        rolling_expectancy = float(recent_data.get("strategy_pnl", pd.Series(dtype=float)).tail(100).mean() if "strategy_pnl" in recent_data else 0)
        baseline_expectancy = float(model.metrics.get("expectancy", 0))
        report["concept_drift"] = rolling_expectancy < baseline_expectancy * 0.5
        return report

    def _passes_gates(self, metrics) -> bool:
        return all(
            [
                self._gate_minimum_sharpe(metrics),
                self._gate_maximum_drawdown(metrics),
                self._gate_minimum_win_rate(metrics),
                self._gate_out_of_sample_consistency(metrics),
                self._gate_minimum_trades(metrics),
            ]
        )

    def _gate_minimum_sharpe(self, metrics) -> bool:
        return float(metrics.get("sharpe", 0)) > 1.5

    def _gate_maximum_drawdown(self, metrics) -> bool:
        return float(metrics.get("max_drawdown", 1)) < 0.25

    def _gate_minimum_win_rate(self, metrics) -> bool:
        return float(metrics.get("win_rate", 0)) > 0.55

    def _gate_out_of_sample_consistency(self, metrics) -> bool:
        in_s = float(metrics.get("in_sample_sharpe", 0))
        out_s = float(metrics.get("out_sample_sharpe", 0))
        return out_s > 0.7 * in_s if in_s > 0 else False

    def _gate_minimum_trades(self, metrics) -> bool:
        return int(metrics.get("trades", 0)) >= 100
