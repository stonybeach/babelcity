"""Project CRUD, volume management, EPUB import/export."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Project, BookVolume, FileItem, ItemTranslation
from .. import epub_handler
from pydantic import BaseModel
from urllib.parse import quote as url_quote
from typing import Any

router = APIRouter(prefix="/projects")


def get_db():
    with get_session() as session:
        yield session


class ProjectCreate(BaseModel):
    project_name: str
    source_title: str = ""
    project_type: str = "Light Novel"
    source_language: str = "ja"
    target_language: str = "zh"
    glossary: Optional[dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    source_title: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None


class VolumeCreate(BaseModel):
    volume_number: str
    source_volume_title: Optional[str] = None
    target_volume_title: Optional[str] = None


class VolumeUpdate(BaseModel):
    source_volume_title: Optional[str] = None
    target_volume_title: Optional[str] = None


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = db.execute(select(Project).order_by(Project.project_name)).scalars().all()
    result = []
    for p in projects:
        volumes = db.execute(
            select(BookVolume)
            .where(BookVolume.project_id == p.id)
            .order_by(BookVolume.volume_number)
        ).scalars().all()
        result.append({
            "id": p.id,
            "project_name": p.project_name,
            "source_title": p.source_title,
            "project_type": p.project_type,
            "source_language": p.source_language,
            "target_language": p.target_language,
            "glossary": p.glossary,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "volumes": [
                {
                    "id": v.id,
                    "volume_number": v.volume_number,
                    "project_id": v.project_id,
                    "source_volume_title": v.source_volume_title,
                    "target_volume_title": v.target_volume_title,
                    "created_at": v.created_at,
                    "updated_at": v.updated_at,
                }
                for v in volumes
            ],
        })
    return result


@router.post("")
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        id=str(uuid.uuid4()),
        project_name=data.project_name,
        source_title=data.source_title,
        project_type=data.project_type,
        source_language=data.source_language,
        target_language=data.target_language,
        glossary=data.glossary or {},
    )
    db.add(project)
    db.flush()

    # Auto-create default volume for Web Novel
    if data.project_type == "Web Novel":
        volume = BookVolume(
            id=str(uuid.uuid4()),
            project_id=project.id,
            volume_number="1",
        )
        db.add(volume)

    db.commit()
    db.refresh(project)

    result = {"id": project.id, "project_name": project.project_name, "message": "Project created"}
    if data.project_type == "Web Novel":
        result["default_volume"] = {"id": volume.id, "volume_number": "1"}
    return result


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    volumes = db.execute(
        select(BookVolume)
        .where(BookVolume.project_id == project_id)
        .order_by(BookVolume.volume_number)
    ).scalars().all()
    return {
        "id": project.id,
        "project_name": project.project_name,
        "source_title": project.source_title,
        "project_type": project.project_type,
        "source_language": project.source_language,
        "target_language": project.target_language,
        "glossary": project.glossary,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "volumes": [
            {
                "id": v.id,
                "volume_number": v.volume_number,
                "source_volume_title": v.source_volume_title,
                "target_volume_title": v.target_volume_title,
                "created_at": v.created_at,
                "updated_at": v.updated_at,
            }
            for v in volumes
        ],
    }


@router.put("/{project_id}")
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if data.project_name is not None:
        project.project_name = data.project_name
    if data.source_title is not None:
        project.source_title = data.source_title
    if data.source_language is not None:
        project.source_language = data.source_language
    if data.target_language is not None:
        project.target_language = data.target_language
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return {"id": project.id, "message": "Project updated"}


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}


@router.post("/{project_id}/volumes")
def add_volume(project_id: str, data: VolumeCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.project_type == "Web Novel":
        raise HTTPException(400, "Web Novel projects cannot have multiple volumes")
    existing = db.execute(
        select(BookVolume).where(
            BookVolume.project_id == project_id,
            BookVolume.volume_number == data.volume_number,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"Volume {data.volume_number} already exists")
    volume = BookVolume(
        id=str(uuid.uuid4()),
        project_id=project_id,
        volume_number=data.volume_number,
        source_volume_title=data.source_volume_title,
        target_volume_title=data.target_volume_title,
    )
    db.add(volume)
    db.commit()
    db.refresh(volume)
    return {"id": volume.id, "volume_number": volume.volume_number, "message": "Volume added"}


@router.put("/{project_id}/volumes/{volume_number}")
def update_volume(
    project_id: str, volume_number: str, data: VolumeUpdate, db: Session = Depends(get_db)
):
    volume = db.execute(
        select(BookVolume).where(
            BookVolume.project_id == project_id,
            BookVolume.volume_number == volume_number,
        )
    ).scalar_one_or_none()
    if not volume:
        raise HTTPException(404, "Volume not found")
    if data.source_volume_title is not None:
        volume.source_volume_title = data.source_volume_title
    if data.target_volume_title is not None:
        volume.target_volume_title = data.target_volume_title
    volume.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Volume updated"}


@router.delete("/{project_id}/volumes/{volume_number}")
def remove_volume(project_id: str, volume_number: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.project_type == "Web Novel":
        raise HTTPException(400, "Cannot remove the only volume of a Web Novel")
    volume = db.execute(
        select(BookVolume).where(
            BookVolume.project_id == project_id,
            BookVolume.volume_number == volume_number,
        )
    ).scalar_one_or_none()
    if not volume:
        raise HTTPException(404, "Volume not found")
    db.delete(volume)
    db.commit()
    return {"message": "Volume removed"}


@router.post("/{project_id}/volumes/{volume_number}/import")
def import_epub(
    project_id: str,
    volume_number: str,
    epub_file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db),
):
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

    file_bytes = epub_file.file.read()
    # epub_handler.import_epub handles: mark existing obsolete, parse EPUB,
    # create/update FileItems, and commit.
    created_ids = epub_handler.import_epub(volume.id, file_bytes, db)
    return {"message": "EPUB imported", "items_count": len(created_ids)}


@router.get("/{project_id}/volumes/{volume_number}/export")
def export_epub(
    project_id: str,
    volume_number: str,
    model_type: str = "",
    qa_round: int = 0,
    db: Session = Depends(get_db),
):
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

    filename_base = volume.target_volume_title or f"{project.project_name}_{volume.volume_number}"
    ascii_filename = "".join(c for c in filename_base if c.isascii() and c.isalnum() or c in " _-").replace(" ", "_")
    filename = f"{ascii_filename}_{model_type}_{qa_round}.epub"
    utf8_filename = f"{filename_base}_{model_type}_{qa_round}.epub"

    epub_bytes = epub_handler.export_epub(volume.id, model_type, qa_round, db)

    return Response(
        content=epub_bytes,
        media_type="application/epub+zip",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{url_quote(utf8_filename)}"},
    )