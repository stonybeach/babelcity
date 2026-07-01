"""Serve EPUB resources (CSS, images) for IFrame rendering."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import FileItem

router = APIRouter(prefix="/resources")


def get_db():
    with get_session() as session:
        yield session


@router.get("/volumes/{volume_id}/items/{full_path:path}")
def get_resource(volume_id: str, full_path: str, db: Session = Depends(get_db)):
    item = db.execute(
        select(FileItem).where(
            FileItem.volume_id == volume_id,
            FileItem.full_path == full_path,
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Resource not found")

    content_bytes = item.content
    if isinstance(content_bytes, str):
        content_bytes = content_bytes.encode("utf-8")

    media_type = "application/octet-stream"
    fp = full_path.lower()
    if fp.endswith(".css"):
        media_type = "text/css"
    elif fp.endswith(".js"):
        media_type = "application/javascript"
    elif fp.endswith(".png"):
        media_type = "image/png"
    elif fp.endswith(".jpg") or fp.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif fp.endswith(".gif"):
        media_type = "image/gif"
    elif fp.endswith(".svg"):
        media_type = "image/svg+xml"
    elif fp.endswith(".webp"):
        media_type = "image/webp"
    elif fp.endswith(".xhtml") or fp.endswith(".html"):
        media_type = "application/xhtml+xml"
    elif fp.endswith(".xml"):
        media_type = "application/xml"
    elif fp.endswith(".opf"):
        media_type = "application/oebps-package+xml"

    return Response(content=content_bytes, media_type=media_type)