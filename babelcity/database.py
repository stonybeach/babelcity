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
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def close_db():
    """Dispose engine connections."""
    if hasattr(_thread_local, "engine"):
        _thread_local.engine.dispose()
        del _thread_local.engine
    if hasattr(_thread_local, "session_factory"):
        del _thread_local.session_factory