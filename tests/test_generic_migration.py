"""Migration tests for Generic project type support."""

import os
import shutil
import tempfile
import unittest

import sqlalchemy
from sqlalchemy.exc import IntegrityError

import babelcity.database as database
from babelcity.database import Base


OLD_PROJECTS_DDL = """
CREATE TABLE projects (
    id VARCHAR(36) NOT NULL,
    project_type VARCHAR(20) NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    source_title VARCHAR(255) NOT NULL,
    source_language VARCHAR(20) NOT NULL DEFAULT 'ja',
    target_language VARCHAR(20) NOT NULL DEFAULT 'zh',
    glossary JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_project_type CHECK (project_type IN ('Light Novel', 'Web Novel'))
)
"""


class GenericProjectMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_path = database.DB_PATH
        cls.temp_dir = tempfile.mkdtemp(prefix="babelcity-migration-")
        database.DB_PATH = os.path.join(cls.temp_dir, "migration.db")
        database.close_db()

        cls.engine = sqlalchemy.create_engine(
            f"sqlite:///{database.DB_PATH}",
            connect_args={"check_same_thread": False},
        )
        with cls.engine.begin() as conn:
            conn.execute(sqlalchemy.text(OLD_PROJECTS_DDL))
            conn.execute(sqlalchemy.text(
                """
                INSERT INTO projects (id, project_type, project_name, source_title, source_language, target_language, glossary, created_at, updated_at)
                VALUES ('p1', 'Light Novel', 'Kept Project', 'Original', 'ja', 'zh', '{}', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
                """
            ))

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        database.close_db()
        database.DB_PATH = cls.previous_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_init_db_rebuilds_projects_table_preserves_rows_and_allows_generic(self):
        database.init_db()

        with self.engine.connect() as conn:
            ddl = conn.execute(
                sqlalchemy.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='projects'")
            ).scalar() or ""

        self.assertIn("'Generic'", ddl)
        self.assertIn("VARCHAR(40)", ddl)

        with self.engine.connect() as conn:
            name = conn.execute(
                sqlalchemy.text("SELECT project_name FROM projects WHERE id='p1'")
            ).scalar()
        self.assertEqual(name, "Kept Project")

        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                """
                INSERT INTO projects (id, project_type, project_name, source_title, source_language, target_language, glossary, created_at, updated_at)
                VALUES ('generic1', 'Generic', 'Generic Project', 'Original', 'Korean', 'Spanish', '{}', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
                """
            ))
            stored = conn.execute(
                sqlalchemy.text("SELECT source_language, target_language FROM projects WHERE id='generic1'")
            ).one()
        self.assertEqual(stored, ("Korean", "Spanish"))

        with self.assertRaises(IntegrityError):
            with self.engine.begin() as conn:
                conn.execute(sqlalchemy.text(
                    """
                    INSERT INTO projects (id, project_type, project_name, source_title, source_language, target_language, glossary, created_at, updated_at)
                    VALUES ('invalid', 'Comic', 'Invalid', 'Original', 'ja', 'zh', '{}', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
                    """
                ))


if __name__ == "__main__":
    unittest.main()
