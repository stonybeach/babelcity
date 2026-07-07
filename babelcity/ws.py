"""WebSocket endpoint for real-time job progress."""

import json
import asyncio
import threading
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .job_queue import job_queue

router = APIRouter()

connected_clients: list = []
_main_loop = None
_main_loop_lock = threading.Lock()


def set_main_loop(loop):
    global _main_loop
    with _main_loop_lock:
        _main_loop = loop


def get_main_loop():
    with _main_loop_lock:
        return _main_loop


@router.websocket("/jobs")
async def job_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
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
                "config_id": j.config_id,
                "status": j.status.value,
                "current": j.progress_completed,
                "total": j.progress_total,
                "message": j.result_message,
            }
            for j in jobs
        ],
    }))


async def _broadcast(msg: str):
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


def broadcast_progress(job_id: str, current: int, total: int):
    """Thread-safe: can be called from worker thread or main thread."""
    msg = json.dumps({
        "type": "progress",
        "job_id": job_id,
        "current": current,
        "total": total,
    })
    loop = get_main_loop()
    if loop and not loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(msg), loop)
    else:
        try:
            asyncio.run(_broadcast(msg))
        except Exception:
            pass


def broadcast_status(job_id: str, status: str):
    """Thread-safe: can be called from worker thread or main thread."""
    msg = json.dumps({
        "type": "status_change",
        "job_id": job_id,
        "status": status,
    })
    loop = get_main_loop()
    if loop and not loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(msg), loop)
    else:
        try:
            asyncio.run(_broadcast(msg))
        except Exception:
            pass