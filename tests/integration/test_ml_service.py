import pytest

from ml_service.src.registry.manager import ModelRegistry


@pytest.mark.asyncio
async def test_model_training_and_promotion():
    r = ModelRegistry()
    model = await r.register(
        name="alpha",
        model_type="classification",
        artifact_path="s3://models/a",
        metrics={"sharpe": 2.0, "max_drawdown": 0.1, "win_rate": 0.7, "in_sample_sharpe": 2.0, "out_sample_sharpe": 1.6, "trades": 200},
        parameters={},
        features=["f1"],
        targets=["y"],
        created_by="tester",
    )
    assert model.id
    ok = await r.promote_to_production(model.id, approved_by="tester")
    assert ok
