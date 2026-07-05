"""Job queue CRUD, start/pause, reorder."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Project, BookVolume, TaskDefinition
from ..job_queue import job_queue, Job, JobStatus
from pydantic import BaseModel

router = APIRouter(prefix="/jobs")


def get_db():
    with get_session() as session:
        yield session


class GlossaryJobCreate(BaseModel):
    project_id: str
    volume_number: str
    task_id: str
    resume: bool = True
    add_only: bool = False
    pre_translated_terms: Optional[str] = None


class TranslationJobCreate(BaseModel):
    project_id: str
    volume_number: str
    task_id: str
    resume: bool = True


class QAJobCreate(BaseModel):
    project_id: str
    volume_number: str
    task_id: str
    start_version: int = 0
    num_passes: int = 1


class JobMove(BaseModel):
    direction: str


@router.get("")
def list_jobs(status: Optional[str] = None, db: Session = Depends(get_db)):
    all_jobs = job_queue.get_all_jobs()
    jobs = []
    for j in all_jobs:
        if status and j.status.value != status:
            continue
        jobs.append({
            "id": j.id,
            "job_type": j.job_type,
            "project_id": j.project_id,
            "project_name": j.project_name,
            "volume_number": j.volume_number,
            "config_id": j.config_id,
            "status": j.status.value,
            "current": j.progress_completed,
            "total": j.progress_total,
            "message": j.result_message,
            "created_at": j.created_at,
        })
    return jobs


@router.post("/glossary")
def add_glossary_job(data: GlossaryJobCreate, db: Session = Depends(get_db)):
    project, volume, task = _validate(db, data.project_id, data.volume_number, data.task_id, "Glossary")
    job = Job(
        id=str(uuid.uuid4()),
        job_type="Glossary",
        project_id=project.id,
        project_name=project.project_name,
        volume_id=volume.id,
        volume_number=volume.volume_number,
        config_id=task.id,
        params={
            "resume": data.resume,
            "add_only": data.add_only,
            "pre_translated_terms": data.pre_translated_terms,
        },
    )
    job_queue.add_job(job)
    return {"id": job.id, "message": "Glossary job added"}


@router.post("/translation")
def add_translation_job(data: TranslationJobCreate, db: Session = Depends(get_db)):
    project, volume, task = _validate(db, data.project_id, data.volume_number, data.task_id, "Translation")
    job = Job(
        id=str(uuid.uuid4()),
        job_type="Translation",
        project_id=project.id,
        project_name=project.project_name,
        volume_id=volume.id,
        volume_number=volume.volume_number,
        config_id=task.id,
        params={"resume": data.resume},
    )
    job_queue.add_job(job)
    return {"id": job.id, "message": "Translation job added"}


@router.post("/qa")
def add_qa_job(data: QAJobCreate, db: Session = Depends(get_db)):
    project, volume, task = _validate(db, data.project_id, data.volume_number, data.task_id, "QA")
    job = Job(
        id=str(uuid.uuid4()),
        job_type="QA",
        project_id=project.id,
        project_name=project.project_name,
        volume_id=volume.id,
        volume_number=volume.volume_number,
        config_id=task.id,
        params={
            "start_version": data.start_version,
            "num_passes": data.num_passes,
        },
    )
    job_queue.add_job(job)
    return {"id": job.id, "message": "QA job added"}


@router.post("/start")
def start_queue():
    job_queue.start()
    return {"message": "Job queue started"}


@router.post("/pause")
def pause_queue():
    job_queue.pause()
    return {"message": "Job queue paused"}


@router.delete("/{job_id}")
def remove_job(job_id: str):
    if not job_queue.delete_job(job_id):
        raise HTTPException(400, "Cannot delete a running job")
    return {"message": "Job removed"}


@router.delete("")
def remove_all_jobs(status: str = "pending"):
    if status == "completed":
        job_queue.clear_completed()
    elif status == "failed":
        job_queue.clear_failed()
    else:
        job_queue.clear_pending()
    return {"message": f"All {status} jobs removed"}


@router.post("/{job_id}/move")
def move_job(job_id: str, data: JobMove):
    direction = data.direction
    if direction == "up":
        job_queue.move_up(job_id)
    elif direction == "down":
        job_queue.move_down(job_id)
    elif direction == "top":
        job_queue.move_to_top(job_id)
    elif direction == "bottom":
        job_queue.move_to_bottom(job_id)
    else:
        raise HTTPException(400, "direction must be up, down, top, or bottom")
    return {"message": "Job moved"}


@router.post("/{job_id}/repeat")
def repeat_job(job_id: str):
    job_queue.repeat_job(job_id)
    return {"message": "Job repeated"}


def _validate(db: Session, project_id: str, volume_number: str, task_id: str, expected_type: str):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    volume = db.execute(
        select(BookVolume).where(
            BookVolume.project_id == project_id,
            BookVolume.volume_number == volume_number,
        )
    ).scalar_one_or_none()
    if not volume:
        raise HTTPException(404, "Volume not found")
    task = db.get(TaskDefinition, task_id)
    if not task:
        raise HTTPException(404, "Task definition not found")
    if task.config_type != expected_type:
        raise HTTPException(400, f"Task definition must be type {expected_type}")
    return project, volume, task