from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="scheduler_service")
scheduler = AsyncIOScheduler()
_jobs: Dict[str, dict] = {}


class ScheduleIn(BaseModel):
    name: str
    type: str
    cron: str | None = None
    seconds: int | None = None
    timeout_seconds: int = 60
    retries: int = 3


@app.on_event("startup")
async def startup():
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)


async def _execute_job(job_id: str):
    cfg = _jobs[job_id]
    for attempt in range(cfg["retries"]):
        try:
            await asyncio.wait_for(asyncio.sleep(0.01), timeout=cfg["timeout_seconds"])
            cfg["last_run"] = datetime.utcnow().isoformat()
            return
        except Exception:
            if attempt == cfg["retries"] - 1:
                cfg["dead_letter"] = True


@app.post("/schedules")
async def create_schedule(payload: ScheduleIn):
    sid = str(uuid4())
    if payload.type == "cron":
        if not payload.cron:
            raise HTTPException(400, "cron expression required")
        minute, hour, day, month, dow = payload.cron.split()
        trigger = CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)
    elif payload.type == "interval":
        if not payload.seconds:
            raise HTTPException(400, "seconds required")
        trigger = IntervalTrigger(seconds=payload.seconds)
    else:
        raise HTTPException(400, "unsupported schedule type")
    _jobs[sid] = payload.model_dump() | {"id": sid, "created_at": datetime.utcnow().isoformat(), "dead_letter": False}
    scheduler.add_job(_execute_job, trigger=trigger, id=sid, args=[sid], replace_existing=True)
    return _jobs[sid]


@app.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    if schedule_id not in _jobs:
        raise HTTPException(404, "not found")
    scheduler.remove_job(schedule_id)
    _jobs.pop(schedule_id, None)
    return {"ok": True}


@app.get("/schedules")
async def list_schedules() -> List[dict]:
    return list(_jobs.values())
