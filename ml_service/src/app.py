from __future__ import annotations

from fastapi import FastAPI, HTTPException

from ml_service.src.registry.manager import ModelRegistry

app = FastAPI(title="ml_service")
registry = ModelRegistry()


@app.post("/train")
async def train_model(payload: dict):
    model = await registry.register(
        name=payload.get("name", "default-model"),
        model_type=payload.get("model_type", "classification"),
        artifact_path=payload.get("artifact_path", "s3://models/default"),
        metrics=payload.get("metrics", {"sharpe": 2.0, "max_drawdown": 0.1, "win_rate": 0.6, "in_sample_sharpe": 2.0, "out_sample_sharpe": 1.5, "trades": 200}),
        parameters=payload.get("parameters", {}),
        features=payload.get("features", ["f1"]),
        targets=payload.get("targets", ["y"]),
        created_by=payload.get("created_by", "system"),
    )
    return {"model_id": model.id, "version": model.version}


@app.post("/promote/{model_id}")
async def promote_to_production(model_id: str):
    ok = await registry.promote_to_production(model_id, approved_by="system")
    if not ok:
        raise HTTPException(status_code=400, detail="promotion gates failed")
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
