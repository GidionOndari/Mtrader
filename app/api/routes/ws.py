from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket

router = APIRouter(tags=['ws'])


@router.websocket('/ws/heartbeat')
async def ws_heartbeat(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({'service': 'api_gateway', 'connected': True, 'ts': datetime.now(timezone.utc).isoformat()})
    await websocket.close()
