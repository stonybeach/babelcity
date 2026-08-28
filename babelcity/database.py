"""Database initialization and session management."""

import os
from contextlib import contextmanager
from threading import local

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = os.environ.get("BABELCITY_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "babelcity.db"))

_thread_local = local()


def get_engine():
    """Create SQLAlchemy engine with WAL mode and timeout=30.0."""
    url = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30.0},
        pool_pre_ping=True,
    )
    # Enable WAL mode
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))
    return engine


def _get_thread_engine():
    """Get or create a thread-local engine."""
    if not hasattr(_thread_local, "engine"):
        _thread_local.engine = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False, "timeout": 30.0},
            pool_pre_ping=True,
        )
    return _thread_local.engine


def _get_thread_session_factory():
    """Get or create a thread-local session factory."""
    if not hasattr(_thread_local, "session_factory"):
        engine = _get_thread_engine()
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))
        _thread_local.session_factory = sessionmaker(bind=engine)
    return _thread_local.session_factory


@contextmanager
def get_session():
    """Thread-safe context manager yielding a DB session."""
    factory = _get_thread_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


Base = declarative_base()


def init_db():
    """Create all tables if they don't exist, and apply migrations."""
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Migration: add spine_order column to file_items if it doesn't exist
    with engine.connect() as conn:
        inspector = sqlalchemy.inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("file_items")] if "file_items" in inspector.get_table_names() else []
        conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))
        if "file_items" in inspector.get_table_names() and "spine_order" not in columns:
            try:
                conn.execute(sqlalchemy.text("ALTER TABLE file_items ADD COLUMN spine_order INTEGER DEFAULT NULL"))
                conn.commit()
            except Exception:
                conn.rollback()
                pass

        # Migration: allow 'Generic' project_type and widen language columns.
        # SQLite cannot ALTER CHECK constraints or column types, so rebuild.
        if "projects" in inspector.get_table_names():
            ddl = conn.execute(
                sqlalchemy.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='projects'")
            ).scalar() or ""
            if "'Generic'" not in ddl:
                try:
                    old_cols = [col["name"] for col in inspector.get_columns("projects")]
                    canonical_cols = [
                        "id", "project_type", "project_name", "source_title",
                        "source_language", "target_language", "glossary",
                        "created_at", "updated_at",
                    ]
                    cols = [c for c in canonical_cols if c in old_cols]
                    col_list = ", ".join(cols)
                    conn.execute(sqlalchemy.text("""
                        CREATE TABLE projects_new (
                            id VARCHAR(36) NOT NULL,
                            project_type VARCHAR(20) NOT NULL,
                            project_name VARCHAR(255) NOT NULL,
                            source_title VARCHAR(255) NOT NULL,
                            source_language VARCHAR(40) NOT NULL,
                            target_language VARCHAR(40) NOT NULL,
                            glossary JSON NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL,
                            PRIMARY KEY (id),
                            CONSTRAINT ck_project_type CHECK (project_type IN ('Light Novel', 'Web Novel', 'Generic'))
                        )
                    """))
                    conn.execute(sqlalchemy.text(
                        f"INSERT INTO projects_new ({col_list}) SELECT {col_list} FROM projects"
                    ))
                    conn.execute(sqlalchemy.text("DROP TABLE projects"))
                    conn.execute(sqlalchemy.text("ALTER TABLE projects_new RENAME TO projects"))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise


def close_db():
    """Dispose engine connections."""
    if hasattr(_thread_local, "engine"):
        _thread_local.engine.dispose()
        del _thread_local.engine
    if hasattr(_thread_local, "session_factory"):
        del _thread_local.session_factory