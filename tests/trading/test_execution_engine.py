import pytest

from trading_service.src.execution.engine import ExecutionEngine, Order, OrderSide, OrderStatus, OrderType


class Repo:
    def __init__(self):
        self.db = {}
    async def save_order(self, order): self.db[order['id']] = order; return order['id']
    async def get_order(self, oid): return self.db.get(oid)
    async def update_order(self, oid, order): self.db[oid] = order
    async def get_orders(self, account_id, status=None): return [v for v in self.db.values() if v['account_id']==account_id and (status is None or v['status']==status)]

class Connector:
    async def get_account_info(self): return {'balance':10000,'equity':10000}
    async def get_positions(self, symbol=None): return []
    async def execute_order(self, order): return {'ok':True,'result':{'retcode':10010,'deal':1}}
    async def cancel_order(self, oid): return True

class Risk:
    async def pre_trade_check(self, *args, **kwargs):
        from trading_service.src.risk.engine import TradeApproval
        return TradeApproval(True)


@pytest.mark.asyncio
async def test_state_machine_submit_and_fill():
    e = ExecutionEngine(Connector(), Risk(), Repo())
    o = Order(id='1', client_order_id='c1', account_id='a1', strategy_id=None, model_id=None, symbol='EURUSD', side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=1)
    await e.repo.save_order(o.to_dict())
    out = await e.submit_order(o)
    assert out.status in {OrderStatus.SUBMITTED, OrderStatus.FILLED}
