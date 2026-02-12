from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI

from news_service.src.calendar.engine import EconomicCalendarEngine

app = FastAPI(title="news_service")
engine = EconomicCalendarEngine(providers=[])


@app.get("/events")
async def fetch_events(days: int = 1):
    start = datetime.utcnow()
    end = start + timedelta(days=days)
    events = await engine.fetch_events(start, end)
    return [e.__dict__ for e in events]


@app.post("/bias")
async def predict_bias(payload: dict):
    event = await engine.get_event_by_id(payload.get("event_id", ""))
    if not event:
        return {"bias": "neutral", "confidence": 0.0}
    return engine.predict_bias(event)


@app.get("/health")
async def health():
    return {"status": "ok"}
