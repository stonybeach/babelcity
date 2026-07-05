"""SQLAlchemy ORM models for Babel City."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Float, ForeignKey, Integer, LargeBinary, String, Text, DateTime, UniqueConstraint, CheckConstraint, JSON
)

from .database import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("project_type IN ('Light Novel', 'Web Novel')", name="ck_project_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_type = Column(String(20), nullable=False)
    project_name = Column(String(255), nullable=False)
    source_title = Column(String(255), nullable=False)
    source_language = Column(String(10), nullable=False, default="ja")
    target_language = Column(String(10), nullable=False, default="zh")
    glossary = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class BookVolume(Base):
    __tablename__ = "book_volumes"
    __table_args__ = (
        UniqueConstraint("project_id", "volume_number", name="uq_volume_project_number"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    volume_number = Column(String(20), nullable=False)
    source_volume_title = Column(String(255), nullable=True)
    target_volume_title = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class FileItem(Base):
    __tablename__ = "file_items"
    __table_args__ = (
        UniqueConstraint("volume_id", "full_path", name="uq_item_volume_path"),
        CheckConstraint("item_type IN ('Chapter', 'Nav', 'Resource')", name="ck_item_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    volume_id = Column(String(36), ForeignKey("book_volumes.id"), nullable=False)
    full_path = Column(String(500), nullable=False)
    content = Column(LargeBinary, nullable=False)
    item_type = Column(String(10), nullable=False)
    glossary_scanned = Column(Boolean, nullable=False, default=False)
    obsolete = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ItemTranslation(Base):
    __tablename__ = "item_translations"
    __table_args__ = (
        UniqueConstraint("item_id", "model_type", "qa_round", name="uq_translation_item_model_round"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String(36), ForeignKey("file_items.id"), nullable=False)
    model_type = Column(String(100), nullable=False)
    qa_round = Column(Integer, nullable=False, default=0)
    content = Column(LargeBinary, nullable=False)
    status = Column(Boolean, nullable=False, default=True)
    last_translation_start = Column(DateTime, nullable=True)
    last_translation_end = Column(DateTime, nullable=True)
    qa_model = Column(String(100), nullable=True)


class TaskDefinition(Base):
    __tablename__ = "task_definitions"
    __table_args__ = (
        CheckConstraint("config_type IN ('Glossary', 'Translation', 'QA')", name="ck_task_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_name = Column(String(100), nullable=False, unique=True)
    config_type = Column(String(20), nullable=False)
    base_url = Column(String(255), nullable=False, default="http://localhost:8080/v1")
    api_key = Column(String(255), nullable=False, default="not-needed")
    model = Column(String(100), nullable=False, default="default")
    max_tokens = Column(Integer, nullable=False, default=8192)
    temperature = Column(Float, nullable=True)
    top_p = Column(Float, nullable=True)
    min_p = Column(Float, nullable=True)
    top_k = Column(Integer, nullable=True)
    presence_penalty = Column(Float, nullable=True)
    frequency_penalty = Column(Float, nullable=True)
    repetition_penalty = Column(Float, nullable=True)
    chunk_size = Column(Integer, nullable=False, default=12)
    history = Column(Integer, nullable=True, default=5)
    use_mini_glossary = Column(Boolean, nullable=True, default=True)
    threads = Column(Integer, nullable=True, default=1)
    synchronize_quotes = Column(Boolean, nullable=True, default=True)
    traditional_chinese = Column(Boolean, nullable=True, default=True)
    model_type = Column(String(100), nullable=True)
    retry_attempts = Column(Integer, nullable=False, default=2)
    override_system_prompt = Column(Text, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)