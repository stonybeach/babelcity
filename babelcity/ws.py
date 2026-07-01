"""WebSocket endpoint for real-time job progress."""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .job_queue import job_queue

router = APIRouter()

# Connected WebSocket clients
connected_clients: list = []


@router.websocket("/jobs")
async def job_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    # Send current job list on connect
    await _send_job_list(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


async def _send_job_list(ws: WebSocket):
    jobs = job_queue.get_all_jobs()
    await ws.send_text(json.dumps({
        "type": "job_list",
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "project_id": j.project_id,
                "volume_number": j.volume_number,
                "status": j.status.value,
                "current": j.progress_completed,
                "total": j.progress_total,
                "message": j.result_message,
            }
            for j in jobs
        ],
    }))


async def broadcast_progress(job_id: str, current: int, total: int):
    msg = json.dumps({
        "type": "progress",
        "job_id": job_id,
        "current": current,
        "total": total,
    })
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


async def broadcast_status(job_id: str, status: str):
    msg = json.dumps({
        "type": "status_change",
        "job_id": job_id,
        "status": status,
    })
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)