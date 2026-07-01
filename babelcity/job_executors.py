"""Job execution functions called by the worker loop."""

from datetime import datetime

from .database import get_session
from .models import FileItem, ItemTranslation, Project, BookVolume, TaskDefinition
from .glossary_processor import scan_for_entities, filter_glossary_terms, merge_glossary
from .text_processor import chunk_paragraphs, load_dictionary


def execute_job(job, progress_callback):
    """Dispatch job to appropriate executor."""
    if job.job_type == "Glossary":
        execute_glossary_job(job, progress_callback)
    elif job.job_type == "Translation":
        execute_translation_job(job, progress_callback)
    elif job.job_type == "QA":
        execute_qa_job(job, progress_callback)
    else:
        raise ValueError(f"Unknown job type: {job.job_type}")


def execute_glossary_job(job, progress_callback):
    """Execute glossary scanning job."""
    with get_session() as session:
        # Load project
        project = session.query(Project).filter_by(id=job.project_id).first()
        if not project:
            raise ValueError(f"Project {job.project_id} not found")

        # Load config
        config = session.query(TaskDefinition).filter_by(id=job.config_id).first()
        if not config:
            raise ValueError(f"Config {job.config_id} not found")

        # Build LLM config
        llm_config = {
            "base_url": config.base_url,
            "api_key": config.api_key,
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "retry_attempts": config.retry_attempts,
        }

        # Get chapters
        chapters = session.query(FileItem).filter_by(
            volume_id=job.volume_id,
            item_type="Chapter",
            obsolete=False
        ).all()

        resume = job.params.get("resume", True)
        add_only = job.params.get("add_only", False)
        pre_translated_text = job.params.get("pre_translated", "")

        pre_translated = load_dictionary(pre_translated_text)

        # Reset if not add_only
        if not add_only:
            project.glossary = "{}"
            for ch in chapters:
                ch.glossary_scanned = False
            session.commit()

        # Existing glossary
        import json
        existing_glossary = json.loads(project.glossary) if project.glossary else {}

        merged = dict(existing_glossary)
        total = len(chapters)
        completed = 0

        for ch in chapters:
            if resume and ch.glossary_scanned:
                completed += 1
                progress_callback(completed, total)
                continue

            # Decompress content
            import zlib
            content = zlib.decompress(ch.content)
            text = content.decode("utf-8", errors="replace")

            # Chunk and scan
            chunks = chunk_paragraphs([text], config.chunk_size)
            for chunk in chunks:
                terms = scan_for_entities(chunk, llm_config, existing_glossary=merged, pre_translated=pre_translated)
                filtered = filter_glossary_terms(terms, project.source_language)
                merged = merge_glossary(merged, filtered, pre_translated)

            ch.glossary_scanned = True
            completed += 1
            progress_callback(completed, total)
            session.commit()

        # Save glossary
        project.glossary = json.dumps(merged, ensure_ascii=False)
        session.commit()


def execute_translation_job(job, progress_callback):
    """Execute translation job."""
    # Placeholder - full implementation in translation_processor
    with get_session() as session:
        config = session.query(TaskDefinition).filter_by(id=job.config_id).first()
        if not config:
            raise ValueError(f"Config {job.config_id} not found")

        chapters = session.query(FileItem).filter_by(
            volume_id=job.volume_id,
            item_type="Chapter",
            obsolete=False
        ).all()

        total = len(chapters)
        completed = 0

        for ch in chapters:
            completed += 1
            progress_callback(completed, total)

        # Nav translation after chapters
        nav_items = session.query(FileItem).filter_by(
            volume_id=job.volume_id,
            item_type="Nav",
            obsolete=False
        ).all()


def execute_qa_job(job, progress_callback):
    """Execute QA job."""
    # Placeholder - full implementation in qa_processor
    with get_session() as session:
        config = session.query(TaskDefinition).filter_by(id=job.config_id).first()
        if not config:
            raise ValueError(f"Config {job.config_id} not found")

        start_version = job.params.get("start_version", 0)
        num_passes = job.params.get("num_passes", 1)

        for pass_idx in range(num_passes):
            chapters = session.query(FileItem).filter_by(
                volume_id=job.volume_id,
                item_type="Chapter",
                obsolete=False
            ).all()

            total = len(chapters)
            for i, ch in enumerate(chapters, 1):
                progress_callback(i, total)

            # Update Nav after each pass