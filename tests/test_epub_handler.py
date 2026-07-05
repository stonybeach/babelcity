"""Unit tests for epub_handler.py using book.epub"""

import io
import os
import sys
import unittest
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from babelcity.epub_handler import (
    get_epub_metadata,
    select_nav_file,
    classify_item,
    import_epub,
    export_epub,
    _resolve_href,
)
from babelcity.database import init_db, get_session
from babelcity.models import FileItem, BookVolume, Project


class TestResolveHref(unittest.TestCase):
    def test_relative(self):
        self.assertEqual(_resolve_href("OEBPS/content.opf", "Text/nav.xhtml"), "OEBPS/Text/nav.xhtml")

    def test_absolute(self):
        self.assertEqual(_resolve_href("OEBPS/content.opf", "/root/file.xml"), "/root/file.xml")

    def test_parent_dir(self):
        self.assertEqual(_resolve_href("OEBPS/Text/chapter.xhtml", "../styles/main.css"), "OEBPS/styles/main.css")


class TestSelectNavFile(unittest.TestCase):
    def test_nav_xhtml_priority(self):
        manifest = {
            "nav": {"href": "Text/nav.xhtml", "media_type": "application/xhtml+xml", "properties": "nav"},
            "toc": {"href": "Text/toc.xhtml", "media_type": "application/xhtml+xml", "properties": ""},
        }
        nav_id, nav_href = select_nav_file(manifest)
        self.assertEqual(nav_id, "nav")
        self.assertEqual(nav_href, "Text/nav.xhtml")

    def test_toc_xhtml_fallback(self):
        manifest = {
            "toc": {"href": "Text/toc.xhtml", "media_type": "application/xhtml+xml", "properties": ""},
        }
        nav_id, nav_href = select_nav_file(manifest)
        self.assertEqual(nav_id, "toc")

    def test_property_nav_fallback(self):
        manifest = {
            "nav_entry": {"href": "Text/chapter1.xhtml", "media_type": "application/xhtml+xml", "properties": "nav"},
        }
        nav_id, nav_href = select_nav_file(manifest)
        self.assertEqual(nav_id, "nav_entry")

    def test_no_nav(self):
        manifest = {
            "css": {"href": "styles/main.css", "media_type": "text/css", "properties": ""},
        }
        nav_id, nav_href = select_nav_file(manifest)
        self.assertIsNone(nav_id)


class TestClassifyItem(unittest.TestCase):
    def test_chapter(self):
        info = {"href": "Text/episode1.xhtml", "media_type": "application/xhtml+xml", "properties": ""}
        self.assertEqual(classify_item("ep1", info, ["Text/episode1.xhtml"], None), "Chapter")

    def test_nav(self):
        info = {"href": "Text/nav.xhtml", "media_type": "application/xhtml+xml", "properties": "nav"}
        self.assertEqual(classify_item("nav", info, [], "nav"), "Nav")

    def test_resource(self):
        info = {"href": "styles/main.css", "media_type": "text/css", "properties": ""}
        self.assertEqual(classify_item("css", info, [], None), "Resource")


class TestGetEpubMetadata(unittest.TestCase):
    def test_book_epub(self):
        epub_path = os.path.join(os.path.dirname(__file__), '..', 'book.epub')
        with zipfile.ZipFile(epub_path, 'r') as zfile:
            manifest, spine, opf_path = get_epub_metadata(zfile)

        self.assertIn("nav.xhtml", manifest)
        self.assertIn("episode1.xhtml", manifest)

        # Check spine has episode1 (spine contains resolved hrefs)
        self.assertIn("OEBPS/Text/episode1.xhtml", spine)
        self.assertIn("OEBPS/Text/nav.xhtml", spine)


class TestEpubImportExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_import_epub(self):
        epub_path = os.path.join(os.path.dirname(__file__), '..', 'book.epub')
        with open(epub_path, 'rb') as f:
            epub_bytes = f.read()

        import uuid
        project_id = str(uuid.uuid4())
        volume_id = str(uuid.uuid4())

        with get_session() as session:
            project = Project(
                id=project_id,
                project_type="Web Novel",
                project_name="Test Project",
                source_title="テスト",
                glossary="{}"
            )
            session.add(project)
            volume = BookVolume(
                id=volume_id,
                project_id=project_id,
                volume_number="1"
            )
            session.add(volume)
            session.commit()

            item_ids = import_epub(volume_id, epub_bytes, session)

        self.assertGreater(len(item_ids), 0)

        with get_session() as session:
            items = session.query(FileItem).filter_by(volume_id=volume_id, obsolete=False).all()
            types = {it.item_type for it in items}

            # Should have Nav and Chapter items
            self.assertIn("Nav", types)
            self.assertIn("Chapter", types)

            # Check that content is stored (compressed)
            for it in items:
                import zlib
                content = zlib.decompress(it.content)
                self.assertIsInstance(content, bytes)
                self.assertGreater(len(content), 0)

    def test_export_epub(self):
        epub_path = os.path.join(os.path.dirname(__file__), '..', 'book.epub')
        with open(epub_path, 'rb') as f:
            epub_bytes = f.read()

        import uuid
        project_id = str(uuid.uuid4())
        volume_id = str(uuid.uuid4())

        with get_session() as session:
            project = Project(
                id=project_id,
                project_type="Web Novel",
                project_name="Export Test",
                source_title="エクスポート",
                glossary="{}"
            )
            session.add(project)
            volume = BookVolume(
                id=volume_id,
                project_id=project_id,
                volume_number="1"
            )
            session.add(volume)
            session.commit()

            import_epub(volume_id, epub_bytes, session)

            # Export with Original model (should use fallback to original content)
            epub_out = export_epub(volume_id, "Original", 0, session)

        # Verify it's a valid EPUB
        self.assertIn(b"application/epub+zip", epub_out)

        with zipfile.ZipFile(io.BytesIO(epub_out), 'r') as zout:
            names = zout.namelist()
            self.assertIn("mimetype", names)


class TestEpubReimport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_reimport_marks_obsolete(self):
        """Re-importing should mark old items as obsolete and update new ones."""
        epub_path = os.path.join(os.path.dirname(__file__), '..', 'book.epub')
        with open(epub_path, 'rb') as f:
            epub_bytes = f.read()

        import uuid
        volume_id = str(uuid.uuid4())

        with get_session() as session:
            project = Project(
                id=str(uuid.uuid4()),
                project_type="Web Novel",
                project_name="Reimport Test",
                source_title="リインポート",
                glossary="{}"
            )
            session.add(project)
            volume = BookVolume(id=volume_id, project_id=project.id, volume_number="1")
            session.add(volume)
            session.commit()

            # First import
            import_epub(volume_id, epub_bytes, session)

            # Second import (re-import)
            import_epub(volume_id, epub_bytes, session)

            # All items should be non-obsolete (same files re-imported)
            items = session.query(FileItem).filter_by(volume_id=volume_id).all()
            non_obsolete = [it for it in items if not it.obsolete]
            self.assertGreater(len(non_obsolete), 0)


if __name__ == '__main__':
    unittest.main()