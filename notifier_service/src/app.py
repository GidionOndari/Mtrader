from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Dict

import httpx
from fastapi import FastAPI, HTTPException
from jinja2 import Template
from pydantic import BaseModel

app = FastAPI(title="notifier_service")


class NotifyIn(BaseModel):
    channel: str
    recipient: str
    template: str
    context: Dict


RATE: Dict[str, int] = {}


def _limited(recipient: str) -> bool:
    RATE[recipient] = RATE.get(recipient, 0) + 1
    return RATE[recipient] > 60


@app.post("/notify")
async def notify(payload: NotifyIn):
    if _limited(payload.recipient):
        raise HTTPException(429, "rate limit")
    body = Template(payload.template).render(**payload.context)
    for attempt in range(3):
        try:
            if payload.channel == "email":
                msg = MIMEText(body)
                msg["Subject"] = "MTrader Notification"
                msg["From"] = "noreply@mtrader.local"
                msg["To"] = payload.recipient
                with smtplib.SMTP("localhost", 25, timeout=5) as s:
                    s.send_message(msg)
            elif payload.channel == "sms":
                async with httpx.AsyncClient(timeout=5) as c:
                    await c.post(payload.recipient, json={"message": body})
            elif payload.channel == "webhook":
                async with httpx.AsyncClient(timeout=5) as c:
                    await c.post(payload.recipient, json={"message": body})
            else:
                raise HTTPException(400, "unsupported channel")
            return {"ok": True}
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(0.5 * (2**attempt))


@app.get("/health")
async def health():
    return {"status": "ok"}
