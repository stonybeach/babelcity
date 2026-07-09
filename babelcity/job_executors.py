"""Job execution functions called by the worker loop."""

import json
import zlib
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List, Union

from .database import get_session
from .models import FileItem, ItemTranslation, Project, BookVolume, TaskDefinition
from .glossary_processor import scan_for_entities, merge_glossary
from .text_processor import chunk_paragraphs, extract_paragraphs, load_dictionary


def _load_project_and_config(session, job) -> Tuple[Project, TaskDefinition]:
    """Load project and task definition config for a job, raising ValueError if not found."""
    project = session.query(Project).filter_by(id=job.project_id).first()
    if not project:
        raise ValueError(f"Project {job.project_id} not found")

    config = session.query(TaskDefinition).filter_by(id=job.config_id).first()
    if not config:
        raise ValueError(f"Config {job.config_id} not found")

    return project, config


def _build_llm_config(config: TaskDefinition, full_params: bool = False) -> Dict[str, Any]:
    """Build the LLM or QA config dictionary from a TaskDefinition.

    Args:
        config: The TaskDefinition instance.
        full_params: Whether to include advanced/translation-specific parameters.
    """
    llm_config = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": config.model,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "min_p": config.min_p,
        "top_k": config.top_k,
        "presence_penalty": config.presence_penalty,
        "frequency_penalty": config.frequency_penalty,
        "repetition_penalty": config.repetition_penalty,
        "retry_attempts": config.retry_attempts,
    }
    if full_params:
        llm_config.update({
            "chunk_size": config.chunk_size,
            "history": config.history,
            "use_mini_glossary": config.use_mini_glossary,
            "traditional_chinese": config.traditional_chinese,
            "synchronize_quotes": config.synchronize_quotes,
            "threads": config.threads,
        })
    return llm_config


def _get_project_glossary(project: Project) -> Dict[str, Any]:
    """Retrieve and parse the glossary dictionary from a Project."""
    if project.glossary is None:
        return {}
    if isinstance(project.glossary, dict):
        return project.glossary
    return json.loads(project.glossary)


def _decompress_content(compressed_content: bytes) -> str:
    """Decompress and decode bytes using zlib and UTF-8."""
    return zlib.decompress(compressed_content).decode("utf-8", errors="replace")


def _compress_content(content: Union[bytes, str]) -> bytes:
    """Compress content string or bytes using zlib."""
    if isinstance(content, bytes):
        return zlib.compress(content)
    return zlib.compress(content.encode("utf-8"))


def save_or_update_translation(
    session,
    item_id: str,
    model_type: str,
    qa_round: int,
    content: bytes,
    qa_model: Optional[str] = None,
) -> None:
    """Save or update an ItemTranslation record in the database.

    Args:
        session: SQLAlchemy session object.
        item_id: The ID of the FileItem being translated.
        model_type: The model type/identifier.
        qa_round: The index of the QA round (0 for initial translation).
        content: Zlib-compressed translated content bytes.
        qa_model: Optional name of the model that executed the QA.
    """
    existing = session.query(ItemTranslation).filter_by(
        item_id=item_id,
        model_type=model_type,
        qa_round=qa_round,
    ).first()

    now = datetime.utcnow()
    if existing:
        existing.content = content
        existing.last_translation_start = now
        existing.last_translation_end = now
        existing.qa_model = qa_model
    else:
        translation = ItemTranslation(
            item_id=item_id,
            model_type=model_type,
            qa_round=qa_round,
            content=content,
            last_translation_start=now,
            last_translation_end=now,
            qa_model=qa_model,
        )
        session.add(translation)
    session.commit()


def _translate_nav_items(
    session,
    volume_id: str,
    glossary: Dict[str, Any],
    config_dict: Dict[str, Any],
    model_type: str,
    qa_round: int,
    qa_model: Optional[str] = None,
) -> None:
    """Translate all non-obsolete Nav items for a volume and save the translations.

    Args:
        session: SQLAlchemy session object.
        volume_id: The ID of the BookVolume.
        glossary: Dictionary representing the project glossary.
        config_dict: Configuration parameters for the LLM.
        model_type: The model type or configuration name identifier.
        qa_round: The current QA round index (0 for initial translation).
        qa_model: The QA model name if applicable.
    """
    from .translation_processor import process_toc

    nav_items = session.query(FileItem).filter_by(
        volume_id=volume_id,
        item_type="Nav",
        obsolete=False
    ).all()

    for nav in nav_items:
        text = _decompress_content(nav.content)
        modified_nav = process_toc(text, config_dict.get("chunk_size", 12), {}, glossary, config_dict)

        if modified_nav:
            compressed = _compress_content(modified_nav)
            save_or_update_translation(
                session=session,
                item_id=nav.id,
                model_type=model_type,
                qa_round=qa_round,
                content=compressed,
                qa_model=qa_model,
            )


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
        # Load project and config
        project, config = _load_project_and_config(session, job)

        # Build LLM config
        llm_config = _build_llm_config(config, full_params=False)

        # Get chapters
        chapters = session.query(FileItem).filter_by(
            volume_id=job.volume_id,
            item_type="Chapter",
            obsolete=False
        ).all()

        resume = job.params.get("resume", True)
        add_only = job.params.get("add_only", False)
        pre_translated_text = job.params.get("pre_translated_terms", "")

        pre_translated = load_dictionary(pre_translated_text)

        # Reset if not add_only and not resuming
        if not add_only and not resume:
            project.glossary = {}
            for ch in chapters:
                ch.glossary_scanned = False
            session.commit()

        # Filter chapters based on resume parameter
        if resume:
            chapters = [ch for ch in chapters if not ch.glossary_scanned]
            if not chapters:
                progress_callback(len(chapters), len(chapters))
                return

        # Get project glossary
        existing_glossary = _get_project_glossary(project)

        merged = dict(existing_glossary)
        total = len(chapters)
        completed = 0
        progress_callback(0, total)

        for ch in chapters:
            # Decompress content
            text = _decompress_content(ch.content)

            # Extract paragraphs and chunk
            paragraphs = extract_paragraphs(text)
            chunks = chunk_paragraphs(paragraphs, config.chunk_size)
            for chunk in chunks:
                chunk_text = "\n".join(chunk)
                terms = scan_for_entities(chunk_text, llm_config, existing_glossary=merged, pre_translated=pre_translated)
                merged = merge_glossary(merged, terms)

            ch.glossary_scanned = True
            completed += 1
            progress_callback(completed, total)
            session.commit()

        # Force all pre_translated entries into glossary (PoC run_lore_pass lines 527-534)
        if pre_translated:
            for jp_name, zh_name in pre_translated.items():
                if jp_name not in merged:
                    merged[jp_name] = {
                        "translated_name": zh_name,
                        "gender": "未知",
                        "type": ""
                    }

        # Save glossary
        project.glossary = merged
        session.commit()


def execute_translation_job(job, progress_callback):
    """Execute translation job with full LLM processing and multi-threading."""
    from .translation_processor import process_document

    with get_session() as session:
        # Load project and config
        project, config = _load_project_and_config(session, job)

        # Build LLM config with all parameters
        llm_config = _build_llm_config(config, full_params=True)

        # Get project glossary
        glossary = _get_project_glossary(project)

        # Get chapters
        chapters = session.query(FileItem).filter_by(
            volume_id=job.volume_id,
            item_type="Chapter",
            obsolete=False
        ).all()

        total = len(chapters)
        completed = 0
        model_type = config.model_type or config.config_name
        threads = config.threads or 1

        progress_callback(0, total)

        def process_chapter(ch):
            text = _decompress_content(ch.content)
            modified_xml, heading_map = process_document(text, glossary, llm_config)
            return ch, modified_xml, heading_map

        if threads > 1:
            # Multi-threaded translation using ThreadPoolExecutor
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading

            completed_counter = threading.atomic(0) if hasattr(threading, 'atomic') else {'value': 0}
            counter_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {executor.submit(process_chapter, ch): ch for ch in chapters}
                for future in as_completed(futures):
                    ch = futures[future]
                    try:
                        _, modified_xml, heading_map = future.result()
                        if modified_xml:
                            compressed = _compress_content(modified_xml)
                            with get_session() as save_session:
                                save_or_update_translation(
                                    session=save_session,
                                    item_id=ch.id,
                                    model_type=model_type,
                                    qa_round=0,
                                    content=compressed,
                                    qa_model=None,
                                )
                    except Exception as e:
                        print(f"Error translating chapter {ch.full_path}: {e}")

                    with counter_lock:
                        completed_counter['value'] += 1
                        completed = completed_counter['value']
                    progress_callback(completed, total)
        else:
            for ch in chapters:
                _, modified_xml, heading_map = process_chapter(ch)
                if modified_xml:
                    compressed = _compress_content(modified_xml)
                    save_or_update_translation(
                        session=session,
                        item_id=ch.id,
                        model_type=model_type,
                        qa_round=0,
                        content=compressed,
                        qa_model=None,
                    )

                completed += 1
                progress_callback(completed, total)

        # Translate Nav files
        _translate_nav_items(
            session=session,
            volume_id=job.volume_id,
            glossary=glossary,
            config_dict=llm_config,
            model_type=model_type,
            qa_round=0,
            qa_model=None,
        )


def execute_qa_job(job, progress_callback):
    """Execute QA job with multi-pass correction and multi-threading support."""
    from .qa_processor import process_qa_document, run_qa_on_chapters

    with get_session() as session:
        # Load project and config
        project, config = _load_project_and_config(session, job)

        # Build QA config with all LLM parameters
        qa_config = _build_llm_config(config, full_params=True)

        # Get project glossary
        glossary = _get_project_glossary(project)

        start_version = job.params.get("start_version", 0)
        num_passes = job.params.get("num_passes", 1)
        translation_model_type = job.params.get("translation_model_type", "")
        threads = config.threads or 1

        # Get total chapters for progress tracking
        initial_translations = (
            session.query(ItemTranslation)
            .join(FileItem, FileItem.id == ItemTranslation.item_id)
            .filter(
                FileItem.volume_id == job.volume_id,
                FileItem.item_type == "Chapter",
                FileItem.obsolete == False,
                ItemTranslation.model_type == translation_model_type,
                ItemTranslation.qa_round == start_version,
            )
            .all()
        )
        total_chapters = len(initial_translations)
        progress_callback(0, num_passes * total_chapters)

        def process_single(args):
            item_id, content = args
            modified, heading_map = process_qa_document(content, glossary, qa_config)
            return (item_id, modified, heading_map)

        for pass_idx in range(num_passes):
            qa_round = start_version + pass_idx + 1

            # Get chapters that have a translation at the previous QA round
            prev_round = qa_round - 1
            prev_translations = (
                session.query(ItemTranslation)
                .join(FileItem, FileItem.id == ItemTranslation.item_id)
                .filter(
                    FileItem.volume_id == job.volume_id,
                    ItemTranslation.model_type == translation_model_type,
                    ItemTranslation.qa_round == prev_round,
                )
                .all()
            )

            if not prev_translations:
                print(f"      [!] No translations found for qa_round {prev_round}. Skipping pass {pass_idx}.")
                continue

            # Prepare chapter items for QA
            chapter_items = []
            for trans in prev_translations:
                text = _decompress_content(trans.content)
                chapter_items.append((trans.item_id, text))

            total = len(chapter_items)
            results = []

            if threads > 1:
                # Multi-threaded QA
                from concurrent.futures import ThreadPoolExecutor, as_completed

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    futures = {
                        executor.submit(process_single, item): item
                        for item in chapter_items
                    }
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            item_id, _ = futures[future]
                            print(f"Error processing item {item_id}: {e}")
            else:
                # Single-threaded QA
                for item in chapter_items:
                    results.append(process_single(item))

            # Save QA results
            qa_model_name = config.model_type or config.config_name
            for item_id, modified_xml, heading_map in results:
                if modified_xml:
                    compressed = _compress_content(modified_xml)
                    save_or_update_translation(
                        session=session,
                        item_id=item_id,
                        model_type=translation_model_type,
                        qa_round=qa_round,
                        content=compressed,
                        qa_model=qa_model_name,
                    )

            # Progress callback after each pass
            progress_callback((pass_idx + 1) * total, num_passes * total)

            # Update Nav after each QA pass
            _translate_nav_items(
                session=session,
                volume_id=job.volume_id,
                glossary=glossary,
                config_dict=qa_config,
                model_type=translation_model_type,
                qa_round=qa_round,
                qa_model=qa_model_name,
            )