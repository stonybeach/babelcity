"""Serve chapter content with optional translation and resource path rewriting."""

import zlib
from urllib.parse import quote
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import FileItem, ItemTranslation


def decompress(content: bytes) -> str:
    return zlib.decompress(content).decode("utf-8")

router = APIRouter(prefix="/chapters")


def get_db():
    with get_session() as session:
        yield session


def rewrite_resource_paths(
    html: str, volume_id: str, base_url: str, base_path: str = ""
) -> str:
    """Rewrite relative href/src paths in HTML to absolute API paths.

    base_path: the full_path of the current FileItem (e.g. 'EPUB/nav.xhtml').
    Relative paths in the HTML are resolved against its directory so they
    match the full_path values stored in the DB.
    """
    import re
    import os
    pattern = r'(href|src)\s*=\s*["\']([^"\']+)["\']'

    # Directory of the current item (e.g. 'EPUB' from 'EPUB/nav.xhtml')
    base_dir = os.path.dirname(base_path)

    def replacer(match):
        attr = match.group(1)
        path = match.group(2)
        # Strip fragment for path resolution
        path_only, _, fragment = path.partition('#')
        if path_only.startswith(("http://", "https://", "data:", "#", "/")):
            return match.group(0)
        # Resolve relative path against the item's directory
        if base_dir:
            path_only = os.path.normpath(os.path.join(base_dir, path_only))
        resolved = path_only + fragment
        encoded = quote(resolved, safe="/_.-")
        return f'{attr}="{base_url}/resources/volumes/{volume_id}/items/{encoded}"'

    return re.sub(pattern, replacer, html)


@router.get("/volumes/{volume_id}/nav")
def get_nav(
    volume_id: str,
    model_type: Optional[str] = Query(None),
    qa_round: int = Query(0),
    db: Session = Depends(get_db),
):
    nav_item = db.execute(
        select(FileItem).where(
            FileItem.volume_id == volume_id,
            FileItem.item_type == "Nav",
            FileItem.obsolete == False,
        )
    ).scalar_one_or_none()
    if not nav_item:
        raise HTTPException(404, "Nav not found")

    content = nav_item.content
    if isinstance(content, bytes):
        content = decompress(content)

    if model_type:
        translation = db.execute(
            select(ItemTranslation).where(
                ItemTranslation.item_id == nav_item.id,
                ItemTranslation.model_type == model_type,
                ItemTranslation.qa_round == qa_round,
            )
        ).scalar_one_or_none()
        if not translation:
            translation = db.execute(
                select(ItemTranslation).where(
                    ItemTranslation.item_id == nav_item.id,
                    ItemTranslation.model_type == model_type,
                    ItemTranslation.qa_round == 0,
                )
            ).scalar_one_or_none()
        if translation and translation.content:
            content = translation.content
            if isinstance(content, bytes):
                content = decompress(content)

    content = rewrite_resource_paths(content, volume_id, "/api/v1", nav_item.full_path)
    return Response(content=content, media_type="application/xhtml+xml")


@router.get("/volumes/{volume_id}/items/{item_path:path}")
def get_chapter(
    volume_id: str,
    item_path: str,
    model_type: Optional[str] = Query(None),
    qa_round: int = Query(0),
    db: Session = Depends(get_db),
):
    item = db.execute(
        select(FileItem).where(
            FileItem.volume_id == volume_id,
            FileItem.full_path == item_path,
        )
    ).scalar_one_or_none()

    # Fallback: nav links may use relative paths (e.g. "episode1.xhtml")
    # while the manifest stores them with a dir prefix (e.g. "EPUB/episode1.xhtml")
    if not item:
        item = db.execute(
            select(FileItem).where(
                FileItem.volume_id == volume_id,
                FileItem.full_path.like(f"%/{item_path}"),
            )
        ).scalar_one_or_none()

    # Fallback: match by filename only (e.g. "episode1.xhtml" matches "EPUB/episode1.xhtml")
    if not item:
        import os
        filename = os.path.basename(item_path)
        item = db.execute(
            select(FileItem).where(
                FileItem.volume_id == volume_id,
                FileItem.full_path.like(f"%{filename}"),
            )
        ).scalar_one_or_none()

    if not item:
        raise HTTPException(404, "Chapter not found")

    content = item.content
    if isinstance(content, bytes):
        content = decompress(content)

    if model_type:
        translation = db.execute(
            select(ItemTranslation).where(
                ItemTranslation.item_id == item.id,
                ItemTranslation.model_type == model_type,
                ItemTranslation.qa_round == qa_round,
            )
        ).scalar_one_or_none()
        if not translation:
            translation = db.execute(
                select(ItemTranslation).where(
                    ItemTranslation.item_id == item.id,
                    ItemTranslation.model_type == model_type,
                    ItemTranslation.qa_round == 0,
                )
            ).scalar_one_or_none()
        if translation and translation.content:
            content = translation.content
            if isinstance(content, bytes):
                content = decompress(content)

    content = rewrite_resource_paths(content, volume_id, "/api/v1", item.full_path)
    return Response(content=content, media_type="application/xhtml+xml")


@router.get("/volumes/{volume_id}/items/{item_id}/meta")
def get_chapter_meta(item_id: str, db: Session = Depends(get_db)):
    item = db.get(FileItem, item_id)
    if not item:
        raise HTTPException(404, "Chapter not found")

    translations = db.execute(
        select(ItemTranslation).where(ItemTranslation.item_id == item_id)
    ).scalars().all()

    return {
        "item_id": item.id,
        "full_path": item.full_path,
        "item_type": item.item_type,
        "obsolete": item.obsolete,
        "glossary_scanned": item.glossary_scanned,
        "translations": [
            {
                "id": t.id,
                "model_type": t.model_type,
                "qa_round": t.qa_round,
            }
            for t in translations
        ],
    }


@router.get("/volumes/{volume_id}/available_translations")
def get_available_translations(volume_id: str, db: Session = Depends(get_db)):
    rows = db.execute(
        select(ItemTranslation.model_type, ItemTranslation.qa_round)
        .join(FileItem, FileItem.id == ItemTranslation.item_id)
        .where(
            FileItem.volume_id == volume_id,
            FileItem.obsolete == False,
        )
    ).all()
    seen = set()
    result: dict = {}
    for model_type, qa_round in rows:
        key = (model_type, qa_round)
        if key not in seen:
            seen.add(key)
            result.setdefault(model_type, []).append(qa_round)
    for v in result.values():
        v.sort()
    return {"available": result}