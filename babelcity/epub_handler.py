"""EPUB import/export using zipfile."""

import io
import os
import re
import zipfile
import zlib
import uuid
from xml.etree import ElementTree as ET

import lxml.etree as lxml_etree

# EPUB namespace
NSMAP = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "nav": "http://www.idpf.org/2001/ontd#",
}


def _parse_xml_bytes(xml_bytes):
    """Parse XML from bytes, handling encoding."""
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    parser = lxml_etree.XMLParser(encoding="utf-8")
    return lxml_etree.fromstring(xml_bytes, parser)


def _resolve_href(base_href, href):
    """Resolve a relative href against a base path."""
    if href.startswith("/"):
        return href
    base_dir = os.path.dirname(base_href)
    return os.path.normpath(os.path.join(base_dir, href)).replace("\\", "/")


def get_epub_metadata(zip_file):
    """Parse content.opf from zipfile to extract spine order, TOC, and manifest."""
    # Find container.xml
    container_path = "META-INF/container.xml"
    container_xml = _parse_xml_bytes(zip_file.read(container_path))
    # Container namespace
    ns = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfiles = container_xml.findall(".//container:rootfile", ns)
    opf_path = None
    for rf in rootfiles:
        opf_path = rf.get("full-path")
        break

    if not opf_path:
        raise ValueError("Could not find content.opf in EPUB")

    # Parse content.opf
    opf_xml = _parse_xml_bytes(zip_file.read(opf_path))

    # Extract manifest using local-name() to avoid namespace issues
    manifest = {}
    for item in opf_xml.xpath('//*[local-name()="manifest"]/*[local-name()="item"]'):
        item_id = item.get("id")
        href = item.get("href")
        media_type = item.get("media-type", "")
        properties = item.get("properties", "")
        if href:
            full_href = _resolve_href(opf_path, href)
            manifest[item_id] = {
                "href": full_href,
                "media_type": media_type,
                "properties": properties,
            }

    # Extract spine
    spine = []
    for itemref in opf_xml.xpath('//*[local-name()="spine"]/*[local-name()="itemref"]'):
        idref = itemref.get("idref")
        if idref and idref in manifest:
            spine.append(manifest[idref]["href"])

    return manifest, spine, opf_path


def select_nav_file(manifest):
    """Select single Nav file from manifest entries.

    Priority: property='nav' > nav.xhtml > toc.xhtml.
    Returns (nav_id, nav_href) or (None, None).
    """
    nav_candidates = []
    nav_xhtml = None
    toc_xhtml = None

    for item_id, info in manifest.items():
        href = info.get("href", "")
        props = info.get("properties", "")

        # Check for nav property
        if "nav" in props.split():
            nav_candidates.append((item_id, href))

        # Check filename patterns
        basename = os.path.basename(href).lower()
        if basename == "nav.xhtml":
            nav_xhtml = (item_id, href)
        elif basename == "toc.xhtml":
            toc_xhtml = (item_id, href)

    # Priority selection: property='nav' > nav.xhtml > toc.xhtml
    if nav_candidates:
        return nav_candidates[0]
    if nav_xhtml:
        return nav_xhtml
    if toc_xhtml:
        return toc_xhtml

    return None, None


def classify_item(item_id, info, spine, nav_id):
    """Classify an item as Chapter, Nav, or Resource."""
    href = info.get("href", "")
    media_type = info.get("media_type", "")
    props = info.get("properties", "")

    # Nav file
    if item_id == nav_id:
        return "Nav"

    # Chapter: in spine, xhtml, and not nav
    if href in spine and "xhtml" in media_type:
        return "Chapter"

    # Resource: everything else
    return "Resource"


def import_epub(volume_id, file_bytes, session):
    """Import EPUB: parse, classify items, store content, mark old items obsolete.

    Returns list of created FileItem IDs.
    """
    from .models import FileItem
    import uuid

    # Mark existing items as obsolete
    existing_items = session.query(FileItem).filter_by(volume_id=volume_id).all()
    for item in existing_items:
        item.obsolete = True

    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zfile:
        manifest, spine, opf_path = get_epub_metadata(zfile)
        nav_id, nav_href = select_nav_file(manifest)

        created_ids = []
        for item_id, info in manifest.items():
            href = info["href"]
            item_type = classify_item(item_id, info, spine, nav_id)

            # Read and compress content
            raw_content = zfile.read(href)
            compressed = zlib.compress(raw_content)

            # Check if item already exists (same volume + path)
            existing = session.query(FileItem).filter_by(
                volume_id=volume_id, full_path=href
            ).first()

            if existing:
                # Update existing item (unmark obsolete, update content)
                existing.content = compressed
                existing.obsolete = False
                existing.item_type = item_type
                created_ids.append(existing.id)
            else:
                import uuid
                new_item = FileItem(
                    id=str(uuid.uuid4()),
                    volume_id=volume_id,
                    full_path=href,
                    content=compressed,
                    item_type=item_type,
                    glossary_scanned=False,
                    obsolete=False,
                )
                session.add(new_item)
                created_ids.append(new_item.id)

        # Store structural files not in manifest: META-INF/container.xml and OPF file
        structural_files = [("META-INF/container.xml", "Resource")]
        if opf_path:
            structural_files.append((opf_path, "Resource"))
        for struct_path, struct_type in structural_files:
            # Skip if already in manifest
            if any(info["href"] == struct_path for info in manifest.values()):
                continue

            try:
                struct_content = zfile.read(struct_path)
                struct_compressed = zlib.compress(struct_content)

                struct_existing = session.query(FileItem).filter_by(
                    volume_id=volume_id, full_path=struct_path
                ).first()

                if struct_existing:
                    struct_existing.content = struct_compressed
                    struct_existing.obsolete = False
                    struct_existing.item_type = struct_type
                    created_ids.append(struct_existing.id)
                else:
                    struct_item = FileItem(
                        id=str(uuid.uuid4()),
                        volume_id=volume_id,
                        full_path=struct_path,
                        content=struct_compressed,
                        item_type=struct_type,
                        glossary_scanned=False,
                        obsolete=False,
                    )
                    session.add(struct_item)
                    created_ids.append(struct_item.id)
            except Exception:
                pass  # Structural file not found in archive; ignore

    session.commit()
    return created_ids


def export_epub(volume_id, model_type, qa_round, session):
    """Build EPUB bytes for download.

    Fallback: (model_type, qa_round) -> (model_type, 0) -> original File_Item.
    """
    from .models import FileItem, ItemTranslation, BookVolume

    volume = session.query(BookVolume).filter_by(id=volume_id).first()
    if not volume:
        raise ValueError(f"Volume {volume_id} not found")

    items = session.query(FileItem).filter_by(
        volume_id=volume_id, obsolete=False
    ).all()

    # Also include all Resource items (even if obsolete) for META-INF/container.xml, OPF, etc.
    resource_items = session.query(FileItem).filter_by(
        volume_id=volume_id, item_type="Resource"
    ).all()

    # Combine and deduplicate by full_path (non-obsolete takes precedence)
    seen = {item.full_path: item for item in items}
    for item in resource_items:
        if item.full_path not in seen:
            seen[item.full_path] = item
    items = list(seen.values())

    # Build output buffer
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        # mimetype first, uncompressed
        zout.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        for item in items:
            raw_content = None

            if item.item_type in ("Chapter", "Nav"):
                # Try translation at target QA round
                translation = session.query(ItemTranslation).filter_by(
                    item_id=item.id, model_type=model_type, qa_round=qa_round
                ).first()

                if not translation:
                    # Fallback to QA round 0
                    translation = session.query(ItemTranslation).filter_by(
                        item_id=item.id, model_type=model_type, qa_round=0
                    ).first()

                if translation:
                    raw_content = zlib.decompress(translation.content)
                else:
                    # Fallback to original
                    raw_content = zlib.decompress(item.content)
            else:
                # Resource: use original
                raw_content = zlib.decompress(item.content)

            zout.writestr(item.full_path, raw_content)

    output.seek(0)
    return output.read()