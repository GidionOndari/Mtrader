import pytest

from trading_service.src.connectors.mt5 import MT5ConnectionConfig, MT5Connector, MT5Credentials
from trading_service.src.execution.engine import ExecutionEngine, Order, OrderSide, OrderType
from trading_service.src.risk.engine import RiskEngine


class Repo:
    def __init__(self):
        self.orders = {}

    async def save_order(self, order):
        self.orders[order["id"]] = order
        return order["id"]

    async def get_order(self, oid):
        return self.orders.get(oid)

    async def update_order_status(self, oid, status, **kwargs):
        self.orders[oid].update({"status": status, **kwargs})
        return True

    async def save_risk_incident(self, incident):
        return "1"


@pytest.mark.asyncio
async def test_order_submission_flow(monkeypatch):
    conn = MT5Connector(MT5Credentials(0, "", ""), MT5ConnectionConfig())
    monkeypatch.setattr(conn, "get_account_info", lambda: {"balance": 10000, "equity": 10000, "profit": 0})
    monkeypatch.setattr(conn, "get_positions", lambda symbol=None: [])
    monkeypatch.setattr(conn, "execute_order", lambda order: {"ok": True, "result": {"retcode": 10008, "deal": 1}})

    repo = Repo()
    risk = RiskEngine(repository=repo, connector=conn)
    engine = ExecutionEngine(connector=conn, risk_engine=risk, db_repository=repo)

    order = Order(id="o1", client_order_id="c1", account_id="a1", strategy_id=None, model_id=None, symbol="EURUSD", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=0.1)
    await repo.save_order(order.to_dict())
    out = await engine.submit_order(order)
    assert out.id == "o1"
