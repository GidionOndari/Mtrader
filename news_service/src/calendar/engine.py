from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EconomicEvent:
    id: str
    provider: str
    time: datetime
    country: str
    region: str
    event_name: str
    category: str
    impact: str
    forecast: Optional[str] = None
    actual: Optional[str] = None
    previous: Optional[str] = None
    revised: Optional[str] = None
    unit: Optional[str] = None
    sentiment_score: float = 0.0
    bias_prediction: Optional[str] = None
    confidence: float = 0.0
    importance: int = 1


class EconomicCalendar:
    def __init__(self, db_repository=None, ws_broadcaster=None) -> None:
        self.providers: List = []
        self.db_repository = db_repository
        self.ws_broadcaster = ws_broadcaster
        self._running = False

    def register_provider(self, provider) -> None:
        self.providers.append(provider)

    async def fetch_events(self, start_date, end_date=None, countries=None, impact=None) -> List[EconomicEvent]:
        tasks = [p.fetch_events(start_date, end_date=end_date) for p in self.providers]
        all_batches = await asyncio.gather(*tasks, return_exceptions=True)
        merged: Dict[str, EconomicEvent] = {}
        priority = {"bloomberg": 3, "reuters": 2, "forexfactory": 1}
        for batch in all_batches:
            if isinstance(batch, Exception):
                logger.exception("calendar provider failed: %s", batch)
                continue
            for e in batch:
                if countries and e.country not in countries:
                    continue
                if impact and e.impact not in impact:
                    continue
                current = merged.get(e.id)
                if not current or priority.get(e.provider, 0) > priority.get(current.provider, 0):
                    merged[e.id] = e
        return sorted(merged.values(), key=lambda x: x.time)

    async def start_live_updates(self, interval: int = 60) -> None:
        self._running = True
        while self._running:
            now = datetime.utcnow()
            events = await self.fetch_events(now, now + timedelta(hours=6), impact=["high"])
            for event in events:
                old_actual = None
                if self.db_repository:
                    old_actual = await self.db_repository.get_event_actual(event.id)
                if old_actual != event.actual:
                    if self.db_repository:
                        await self.db_repository.upsert_event(event.__dict__)
                    if self.ws_broadcaster:
                        await self.ws_broadcaster.broadcast("calendar_updates", {"event": event.__dict__})
            await asyncio.sleep(interval)

    def predict_bias(self, event: EconomicEvent) -> Dict:
        def to_num(v: Optional[str]) -> Optional[float]:
            if v is None:
                return None
            v = str(v).replace("%", "").replace(",", "").strip()
            try:
                return float(v)
            except ValueError:
                return None

        actual = to_num(event.actual)
        forecast = to_num(event.forecast)
        if actual is None or forecast is None:
            return {"bias": "neutral", "confidence": 0.2, "reasoning": "Insufficient numeric data"}

        bias = "bullish" if actual > forecast else "bearish" if actual < forecast else "neutral"
        reason = "Actual compared with forecast"
        confidence = min(0.95, 0.5 + abs(actual - forecast) / (abs(forecast) + 1e-9))

        name = event.event_name.lower()
        if "interest rate" in name:
            bias = "bullish" if actual > forecast else "bearish" if actual < forecast else "neutral"
            reason = "Higher rates generally support currency"
        elif "cpi" in name:
            bias = "bullish" if actual > forecast else "bearish" if actual < forecast else "neutral"
            reason = "Inflation surprise and policy expectations"
        elif "non-farm" in name or "nfp" in name:
            bias = "bullish" if actual > forecast else "bearish" if actual < forecast else "neutral"
            reason = "Labor market surprise signal"

        return {"bias": bias, "confidence": float(confidence), "reasoning": reason}

    def calculate_impact(self, event: EconomicEvent) -> str:
        if event.importance >= 5 or event.impact.lower() == "high":
            return "high"
        if event.importance >= 3:
            return "medium"
        return "low"


class ForexFactoryProvider:
    name = "forexfactory"

    async def fetch_events(self, start_date, end_date=None) -> List[EconomicEvent]:
        url = "https://www.forexfactory.com/calendar"
        events: List[EconomicEvent] = []
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("tr.calendar__row")
            for r in rows:
                try:
                    time_text = (r.select_one("td.calendar__time") or {}).get_text(strip=True)
                    country = (r.select_one("td.calendar__currency") or {}).get_text(strip=True)
                    event_name = (r.select_one("td.calendar__event") or {}).get_text(strip=True)
                    impact_node = r.select_one("td.calendar__impact span")
                    impact_class = " ".join(impact_node.get("class", [])) if impact_node else ""
                    impact = "high" if "--high" in impact_class else "medium" if "--medium" in impact_class else "low"
                    event_id = (r.get("data-eventid") or f"ff-{country}-{event_name}-{time_text}").strip()
                    event_time = datetime.utcnow()
                    events.append(EconomicEvent(id=event_id, provider=self.name, time=event_time, country=country, region=country, event_name=event_name, category="macro", impact=impact, importance=5 if impact == "high" else 3 if impact == "medium" else 1))
                except Exception:
                    logger.exception("failed to parse forexfactory row")
        return events


class BloombergProvider:
    name = "bloomberg"

    async def fetch_events(self, start_date, end_date=None) -> List[EconomicEvent]:
        logger.info("Bloomberg provider mock active; returning no events")
        return []


class ReutersProvider:
    name = "reuters"

    async def fetch_events(self, start_date, end_date=None) -> List[EconomicEvent]:
        logger.info("Reuters provider mock active; returning no events")
        return []
