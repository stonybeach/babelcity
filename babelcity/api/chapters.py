"""Serve chapter content with optional translation and resource path rewriting."""

import os
import re
import zlib
from urllib.parse import quote
from typing import Optional

import lxml.etree as lxml_etree

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
        chapter_items = db.execute(
            select(FileItem).where(
                FileItem.volume_id == volume_id,
                FileItem.item_type == "Chapter",
                FileItem.obsolete == False,
            )
        ).scalars().all()
        html_parts = ['<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>']
        for ch in chapter_items:
            html_parts.append(
                f'<p><a href="/chapters/volumes/{volume_id}/items/{ch.id}">{ch.full_path}</a></p>'
            )
        html_parts.append('</body></html>')
        return Response(content=''.join(html_parts), media_type="application/xhtml+xml")

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

    is_ncx = nav_item.full_path.lower().endswith(".ncx")
    if is_ncx:
        return Response(content=content, media_type="application/xml")

    content = rewrite_resource_paths(content, volume_id, "/api/v1", nav_item.full_path)
    return Response(content=content, media_type="application/xhtml+xml")


@router.get("/volumes/{volume_id}/toc")
def get_toc(
    volume_id: str,
    model_type: Optional[str] = Query(None),
    qa_round: int = Query(0),
    db: Session = Depends(get_db),
):
    """Build TOC from Chapter items (spine) + Nav name mapping."""
    all_items = db.execute(
        select(FileItem).where(
            FileItem.volume_id == volume_id,
            FileItem.obsolete == False,
        )
    ).scalars().all()

    # Build name_map: full_path -> link text from Nav file
    nav_item = next((item for item in all_items if item.item_type == "Nav"), None)
    name_map = {}

    if nav_item:
        nav_content = nav_item.content
        if isinstance(nav_content, bytes):
            nav_content = decompress(nav_content)

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
                nav_content = translation.content
                if isinstance(nav_content, bytes):
                    nav_content = decompress(nav_content)

        nav_dir = os.path.dirname(nav_item.full_path)
        is_ncx = nav_item.full_path.lower().endswith(".ncx")
        try:
            nav_tree = lxml_etree.fromstring(nav_content if isinstance(nav_content, bytes) else nav_content.encode("utf-8"))

            if is_ncx:
                ncx_ns = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
                nav_points = nav_tree.xpath('//ncx:navPoint', namespaces=ncx_ns)
                if not nav_points:
                    nav_points = nav_tree.xpath('//*[local-name()="navPoint"]')
                for np in nav_points:
                    label = np.xpath('.//ncx:navLabel/ncx:text', namespaces=ncx_ns)
                    if not label:
                        label = np.xpath('.//*[local-name()="navLabel"]/*[local-name()="text"]')
                    if not label:
                        continue
                    link_text = "".join(label[0].itertext()).strip()
                    content_el = np.xpath('.//ncx:content', namespaces=ncx_ns)
                    if not content_el:
                        content_el = np.xpath('.//*[local-name()="content"]')
                    if not content_el:
                        continue
                    href = content_el[0].get("src", "")
                    if not href:
                        continue
                    path_only = href.split("#")[0]
                    full_path = os.path.normpath(os.path.join(nav_dir, path_only)).replace("\\", "/")
                    if link_text:
                        name_map[full_path] = link_text
            else:
                ns = {'h': 'http://www.w3.org/1999/xhtml'}
                for link in nav_tree.xpath('//h:a[@href]', namespaces=ns) or nav_tree.xpath('//a[@href]'):
                    href = link.get("href", "")
                    link_text = link.text or ""
                    for child in link:
                        if child.text:
                            link_text += child.text
                        for gc in child.iter():
                            if gc.text:
                                link_text += gc.text
                    link_text = link_text.strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        full_path = href.split("#")[0]
                    else:
                        path_only = href.split("#")[0]
                        full_path = os.path.normpath(os.path.join(nav_dir, path_only)).replace("\\", "/")
                    if link_text:
                        name_map[full_path] = link_text
        except Exception:
            pass

    # Build TOC from Chapter items, ordered by spine_order
    chapter_items = sorted(
        [item for item in all_items if item.item_type == "Chapter"],
        key=lambda item: item.spine_order if item.spine_order is not None else 999999
    )
    toc = []
    for item in chapter_items:
        path_no_fragment = item.full_path.split("#")[0]
        title = name_map.get(path_no_fragment, item.full_path)
        toc.append({"id": item.id, "full_path": item.full_path, "title": title})

    return {"toc": toc}


@router.get("/volumes/{volume_id}/items/{item_id}/meta")
def get_chapter_meta(volume_id: str, item_id: str, db: Session = Depends(get_db)):
    item = db.get(FileItem, item_id)
    if not item:
        raise HTTPException(404, "Chapter not found")
    if item.volume_id != volume_id:
        raise HTTPException(404, "Item not found in this volume")

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
                "status": t.status,
                "last_translation_start": t.last_translation_start.isoformat() + "Z" if t.last_translation_start else None,
                "last_translation_end": t.last_translation_end.isoformat() + "Z" if t.last_translation_end else None,
                "qa_model": t.qa_model,
            }
            for t in translations
        ],
    }


@router.patch("/volumes/{volume_id}/items/{item_id}/obsolete")
def toggle_obsolete(volume_id: str, item_id: str, db: Session = Depends(get_db)):
    item = db.get(FileItem, item_id)
    if not item or item.volume_id != volume_id:
        raise HTTPException(404, "Item not found")
    item.obsolete = not item.obsolete
    db.commit()
    return {"obsolete": item.obsolete}



@router.get("/volumes/{volume_id}/items/{item_path:path}")
def get_chapter(
    volume_id: str,
    item_path: str,
    model_type: Optional[str] = Query(None),
    qa_round: int = Query(0),
    db: Session = Depends(get_db),
):
    # Try UUID lookup first (TOC now passes item.id)
    item = db.get(FileItem, item_path)

    # Fallback: exact full_path match
    if not item:
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


@router.patch("/volumes/{volume_id}/items/{item_id}/translations/{translation_id}/status")
def toggle_translation_status(volume_id: str, item_id: str, translation_id: str, db: Session = Depends(get_db)):
    translation = db.get(ItemTranslation, translation_id)
    if not translation:
        raise HTTPException(404, "Translation not found")
    item = db.get(FileItem, item_id)
    if not item or item.volume_id != volume_id:
        raise HTTPException(404, "Item not found")
    translation.status = not translation.status
    db.commit()
    return {"status": translation.status}