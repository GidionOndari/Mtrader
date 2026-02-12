from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from market_data_service.src.providers.base import MT5Provider, Timeframe

app = FastAPI(title="market_data_service")
provider = None


class SubscriptionIn(BaseModel):
    symbols: List[str]


@app.on_event("startup")
async def startup():
    global provider
    provider = MT5Provider(account=0, password="", server="")


@app.get("/ticks/{symbol}")
async def ticks(symbol: str, start: str, end: str | None = None, limit: int = 10000):
    if not provider:
        raise HTTPException(503, "provider unavailable")
    st = datetime.fromisoformat(start)
    ed = datetime.fromisoformat(end) if end else None
    data = await provider.get_ticks(symbol, st, ed, limit)
    return [d.__dict__ for d in data]


@app.get("/ohlcv/{symbol}/{timeframe}")
async def ohlcv(symbol: str, timeframe: str, start: str, end: str | None = None, limit: int = 1000):
    st = datetime.fromisoformat(start)
    ed = datetime.fromisoformat(end) if end else None
    tf = Timeframe(timeframe)
    data = await provider.get_ohlcv(symbol, tf, st, ed, limit)
    return [d.__dict__ | {"timeframe": d.timeframe.value} for d in data]


@app.post("/subscriptions")
async def subscribe(payload: SubscriptionIn):
    out = await provider.subscribe_ticks(payload.symbols, lambda _: None)
    return out


@app.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket):
    await websocket.accept()
    active: List[str] = []

    async def callback(tick):
        await websocket.send_json(tick.__dict__)

    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")
            symbols = msg.get("symbols", [])
            if action == "subscribe":
                await provider.subscribe_ticks(symbols, callback)
                active.extend(symbols)
            elif action == "unsubscribe":
                await provider.unsubscribe_ticks(symbols)
                active = [s for s in active if s not in symbols]
    except WebSocketDisconnect:
        if active:
            await provider.unsubscribe_ticks(active)


@app.get("/health")
async def health():
    return {"status": "ok"}
