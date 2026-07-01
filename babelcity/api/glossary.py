"""Glossary read/write per project."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Project
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/projects")


def get_db():
    with get_session() as session:
        yield session


class GlossaryUpdate(BaseModel):
    glossary: dict[str, Any]


@router.get("/{project_id}/glossary")
def get_glossary(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {"project_id": project_id, "glossary": project.glossary or {}}


@router.put("/{project_id}/glossary")
def save_glossary(project_id: str, data: GlossaryUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.glossary = data.glossary
    db.commit()
    return {"message": "Glossary saved"}