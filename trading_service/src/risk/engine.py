from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskRuleType(str, Enum):
    MAX_POSITION_SIZE = "MAX_POSITION_SIZE"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    MAX_DAILY_LOSS = "MAX_DAILY_LOSS"
    MAX_LEVERAGE = "MAX_LEVERAGE"
    MIN_TIME_BETWEEN_TRADES = "MIN_TIME_BETWEEN_TRADES"
    CORRELATION_LIMIT = "CORRELATION_LIMIT"
    MAX_SYMBOL_CONCENTRATION = "MAX_SYMBOL_CONCENTRATION"
    MAX_OPEN_POSITIONS = "MAX_OPEN_POSITIONS"
    MAX_ORDER_COUNT = "MAX_ORDER_COUNT"
    MAX_EXPOSURE = "MAX_EXPOSURE"
    STOP_LOSS_REQUIRED = "STOP_LOSS_REQUIRED"
    TAKE_PROFIT_REQUIRED = "TAKE_PROFIT_REQUIRED"
    MAX_SPREAD = "MAX_SPREAD"
    MAX_SLIPPAGE = "MAX_SLIPPAGE"
    TRADING_HOURS_ONLY = "TRADING_HOURS_ONLY"


@dataclass(slots=True)
class RiskRule:
    type: RiskRuleType
    parameters: Dict
    severity: str = "hard"
    enabled: bool = True
    error_message: str = "Risk rule violated"


@dataclass(slots=True)
class TradeApproval:
    approved: bool
    reason: Optional[str] = None
    rule_violated: Optional[RiskRuleType] = None
    warning: Optional[str] = None


class RiskEngine:
    def __init__(self, repository=None, connector=None, execution_engine=None, notifier=None, broadcaster=None, scheduler_controller=None):
        self.repository = repository
        self.connector = connector
        self.execution_engine = execution_engine
        self.notifier = notifier
        self.broadcaster = broadcaster
        self.scheduler_controller = scheduler_controller
        self._kill_switch = False
        self._daily_loss_by_account: Dict[str, float] = {}
        self.rules: Dict[RiskRuleType, RiskRule] = {
            RiskRuleType.MAX_POSITION_SIZE: RiskRule(RiskRuleType.MAX_POSITION_SIZE, {"max_percent": 0.05}, error_message="Max position size exceeded"),
            RiskRuleType.MAX_DRAWDOWN: RiskRule(RiskRuleType.MAX_DRAWDOWN, {"max_drawdown": 0.2}, error_message="Max drawdown exceeded"),
            RiskRuleType.MAX_DAILY_LOSS: RiskRule(RiskRuleType.MAX_DAILY_LOSS, {"max_daily_loss": 0.1}, error_message="Max daily loss exceeded"),
            RiskRuleType.MAX_LEVERAGE: RiskRule(RiskRuleType.MAX_LEVERAGE, {"max_leverage": 50}, error_message="Max leverage exceeded"),
            RiskRuleType.MIN_TIME_BETWEEN_TRADES: RiskRule(RiskRuleType.MIN_TIME_BETWEEN_TRADES, {"seconds": 1}, error_message="Too many trades")
        }
        self._last_trade_ts: Optional[datetime] = None

    def add_rule(self, rule: RiskRule) -> None:
        self.rules[rule.type] = rule

    def remove_rule(self, rule_type: RiskRuleType) -> None:
        self.rules.pop(rule_type, None)

    async def _persist_incident(self, incident: Dict) -> None:
        if self.repository:
            await self.repository.save_risk_incident(incident)

    async def pre_trade_check(self, order: Dict, account_info: Dict, positions: List[Dict], market_data: Optional[Dict] = None) -> TradeApproval:
        if self._kill_switch:
            return TradeApproval(False, reason="Kill switch active")

        now = datetime.utcnow()
        account_id = str(order.get("account_id", "unknown"))
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            violated = False
            actual_values = {}
            if rule.type == RiskRuleType.MAX_DRAWDOWN:
                bal = float(account_info.get("balance", 0) or 0)
                eq = float(account_info.get("equity", 0) or 0)
                dd = (bal - eq) / bal if bal > 0 else 0
                actual_values = {"drawdown": dd}
                violated = dd > float(rule.parameters.get("max_drawdown", 0.2))
            elif rule.type == RiskRuleType.MAX_DAILY_LOSS:
                bal = float(account_info.get("balance", 0) or 0)
                pnl = float(account_info.get("profit", 0) or 0)
                daily = abs(min(pnl, 0)) / bal if bal > 0 else 0
                actual_values = {"daily_loss": daily}
                violated = daily > float(rule.parameters.get("max_daily_loss", 0.1))
            elif rule.type == RiskRuleType.MIN_TIME_BETWEEN_TRADES and self._last_trade_ts:
                delta = (now - self._last_trade_ts).total_seconds()
                actual_values = {"seconds_since_last_trade": delta}
                violated = delta < float(rule.parameters.get("seconds", 1))

            if violated:
                incident = {
                    "rule_type": rule.type.value,
                    "parameters": rule.parameters,
                    "actual_values": actual_values,
                    "order_id": order.get("id"),
                    "account_id": account_id,
                    "action_taken": "reject" if rule.severity == "hard" else "warning",
                    "created_at": datetime.utcnow().isoformat(),
                }
                await self._persist_incident(incident)
                if rule.severity == "hard":
                    return TradeApproval(False, reason=rule.error_message, rule_violated=rule.type)
                return TradeApproval(True, warning=rule.error_message)

        self._last_trade_ts = now
        return TradeApproval(True)

    async def monitor_positions(self, get_positions_callback: Callable[[str], Awaitable[List[Dict]]], account_id: str) -> None:
        while True:
            positions = await get_positions_callback(account_id)
            total_pnl = sum(float(p.get("profit", 0) or 0) for p in positions)
            self._daily_loss_by_account[account_id] = abs(min(total_pnl, 0))

            exposure = sum(abs(float(p.get("volume", 0) or 0) * float(p.get("price_current", p.get("entry_price", 0)) or 0)) for p in positions)
            if exposure > 0 and len(positions) > 0:
                if exposure > float(self.rules.get(RiskRuleType.MAX_POSITION_SIZE, RiskRule(RiskRuleType.MAX_POSITION_SIZE, {"max_percent": 0.05})).parameters.get("max_percent", 0.05)) * max(1.0, exposure):
                    if self.connector:
                        await self.connector.close_all_positions()
                    await self._persist_incident({"rule_type": RiskRuleType.MAX_EXPOSURE.value, "parameters": {}, "actual_values": {"exposure": exposure}, "order_id": None, "account_id": account_id, "action_taken": "position_reduced", "created_at": datetime.utcnow().isoformat()})

            if self.notifier and self._daily_loss_by_account[account_id] > 0:
                await self.notifier.notify(account_id, f"Daily loss monitor: {self._daily_loss_by_account[account_id]:.2f}")
            await asyncio.sleep(2)

    async def kill_switch(self, reason: str, triggered_by: str) -> None:
        self._kill_switch = True
        incident = {
            "rule_type": "KILL_SWITCH",
            "parameters": {"reason": reason},
            "actual_values": {},
            "order_id": None,
            "account_id": "global",
            "action_taken": "kill_switch",
            "created_at": datetime.utcnow().isoformat(),
            "triggered_by": triggered_by,
            "severity": "CRITICAL",
        }
        await self._persist_incident(incident)

        for _ in range(3):
            try:
                if self.execution_engine:
                    await self.execution_engine.cancel_all_orders()
                if self.connector:
                    await self.connector.close_all_positions()
                break
            except Exception:
                logger.exception("kill switch action failed; retrying")
                await asyncio.sleep(1)

        if self.broadcaster:
            await self.broadcaster.broadcast("risk_events", {"event": "kill_switch", "reason": reason, "triggered_by": triggered_by})

        if self.scheduler_controller:
            await self.scheduler_controller.disable_all_strategies()

    async def release_kill_switch(self) -> bool:
        self._kill_switch = False
        await self._persist_incident({"rule_type": "KILL_SWITCH_RELEASE", "parameters": {}, "actual_values": {}, "order_id": None, "account_id": "global", "action_taken": "warning", "created_at": datetime.utcnow().isoformat()})
        return True
