"""Task definition CRUD."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import TaskDefinition
from pydantic import BaseModel

router = APIRouter(prefix="/tasks")


def get_db():
    with get_session() as session:
        yield session


class TaskDefinitionCreate(BaseModel):
    config_name: str
    config_type: str
    base_url: str = "http://localhost:8080/v1"
    api_key: str = "not-needed"
    model: str = "default"
    max_tokens: int = 8192
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    min_p: Optional[float] = None
    top_k: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    chunk_size: int = 12
    history: Optional[int] = None
    use_mini_glossary: Optional[bool] = None
    threads: int = 1
    synchronize_quotes: bool = True
    traditional_chinese: bool = True
    model_type: Optional[str] = None
    retry_attempts: int = 2
    override_system_prompt: Optional[str] = None


class TaskDefinitionUpdate(BaseModel):
    config_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    min_p: Optional[float] = None
    top_k: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    chunk_size: Optional[int] = None
    history: Optional[int] = None
    use_mini_glossary: Optional[bool] = None
    threads: Optional[int] = None
    synchronize_quotes: Optional[bool] = None
    traditional_chinese: Optional[bool] = None
    model_type: Optional[str] = None
    retry_attempts: Optional[int] = None
    override_system_prompt: Optional[str] = None


@router.get("")
def list_tasks(task_type: Optional[str] = None, db: Session = Depends(get_db)):
    query = select(TaskDefinition).order_by(TaskDefinition.config_type, TaskDefinition.config_name)
    if task_type:
        query = query.where(TaskDefinition.config_type == task_type)
    tasks = db.execute(query).scalars().all()
    return [
        {
            "id": t.id,
            "config_name": t.config_name,
            "config_type": t.config_type,
            "base_url": t.base_url,
            "api_key": t.api_key,
            "model": t.model,
            "max_tokens": t.max_tokens,
            "temperature": t.temperature,
            "top_p": t.top_p,
            "min_p": t.min_p,
            "top_k": t.top_k,
            "presence_penalty": t.presence_penalty,
            "frequency_penalty": t.frequency_penalty,
            "repetition_penalty": t.repetition_penalty,
            "chunk_size": t.chunk_size,
            "history": t.history,
            "use_mini_glossary": t.use_mini_glossary,
            "threads": t.threads,
            "synchronize_quotes": t.synchronize_quotes,
            "traditional_chinese": t.traditional_chinese,
            "model_type": t.model_type,
            "retry_attempts": t.retry_attempts,
            "override_system_prompt": t.override_system_prompt,
            "is_default": t.is_default,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in tasks
    ]


@router.post("")
def create_task(data: TaskDefinitionCreate, db: Session = Depends(get_db)):
    if data.config_type not in ("Glossary", "Translation", "QA"):
        raise HTTPException(400, "config_type must be Glossary, Translation, or QA")
    task = TaskDefinition(
        id=str(uuid.uuid4()),
        config_name=data.config_name,
        config_type=data.config_type,
        base_url=data.base_url,
        api_key=data.api_key,
        model=data.model,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        top_p=data.top_p,
        min_p=data.min_p,
        top_k=data.top_k,
        presence_penalty=data.presence_penalty,
        frequency_penalty=data.frequency_penalty,
        repetition_penalty=data.repetition_penalty,
        chunk_size=data.chunk_size,
        history=data.history,
        use_mini_glossary=data.use_mini_glossary,
        threads=data.threads,
        synchronize_quotes=data.synchronize_quotes,
        traditional_chinese=data.traditional_chinese,
        model_type=data.model_type,
        retry_attempts=data.retry_attempts,
        override_system_prompt=data.override_system_prompt,
        is_default=False,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": task.id, "config_name": task.config_name, "message": "Task definition created"}


@router.put("/{task_id}")
def update_task(task_id: str, data: TaskDefinitionUpdate, db: Session = Depends(get_db)):
    task = db.get(TaskDefinition, task_id)
    if not task:
        raise HTTPException(404, "Task definition not found")
    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return {"id": task.id, "message": "Task definition updated"}


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(TaskDefinition, task_id)
    if not task:
        raise HTTPException(404, "Task definition not found")
    db.delete(task)
    db.commit()
    return {"message": "Task definition deleted"}


@router.post("/{task_id}/default")
def set_default(task_id: str, db: Session = Depends(get_db)):
    task = db.get(TaskDefinition, task_id)
    if not task:
        raise HTTPException(404, "Task definition not found")
    db.execute(
        TaskDefinition.__table__.update()
        .where(TaskDefinition.config_type == task.config_type)
        .values(is_default=False)
    )
    task.is_default = True
    db.commit()
    return {"message": "Default task set"}