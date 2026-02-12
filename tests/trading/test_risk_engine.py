import pytest

from trading_service.src.risk.engine import RiskEngine


@pytest.mark.asyncio
async def test_pre_trade_reject_drawdown():
    engine = RiskEngine()
    approval = await engine.pre_trade_check({'account_id':'a'}, {'balance':1000,'equity':700}, [])
    assert approval.approved is False


@pytest.mark.asyncio
async def test_kill_switch_blocks_trades():
    engine = RiskEngine()
    await engine.kill_switch('test', 'tester')
    approval = await engine.pre_trade_check({}, {'balance':1000,'equity':1000}, [])
    assert approval.approved is False
