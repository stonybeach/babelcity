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
            "min_p": config.min_p,
            "top_k": config.top_k,
            "presence_penalty": config.presence_penalty,
            "frequency_penalty": config.frequency_penalty,
            "repetition_penalty": config.repetition_penalty,
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
        project.glossary = merged
        session.commit()


def execute_translation_job(job, progress_callback):
    """Execute translation job with full LLM processing and multi-threading."""
    from .translation_processor import process_document
    import zlib
    import json

    with get_session() as session:
        # Load project and config
        project = session.query(Project).filter_by(id=job.project_id).first()
        if not project:
            raise ValueError(f"Project {job.project_id} not found")

        config = session.query(TaskDefinition).filter_by(id=job.config_id).first()
        if not config:
            raise ValueError(f"Config {job.config_id} not found")

        # Build LLM config with all parameters
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
            "chunk_size": config.chunk_size,
            "history": config.history,
            "use_mini_glossary": config.use_mini_glossary,
            "traditional_chinese": config.traditional_chinese,
            "threads": config.threads,
        }

        # Get project glossary
        glossary = json.loads(project.glossary) if project.glossary else {}

        # Get chapters
        chapters = session.query(FileItem).filter_by(
            volume_id=job.volume_id,
            item_type="Chapter",
            obsolete=False
        ).all()

        total = len(chapters)
        completed = 0
        model_type = config.model_type or config.config_name

        for ch in chapters:
            # Decompress content
            content = zlib.decompress(ch.content)
            text = content.decode("utf-8", errors="replace")

            # Translate
            modified_xml, heading_map = process_document(text, glossary, llm_config)

            if modified_xml:
                # Compress and save translation
                import zlib
                compressed = zlib.compress(modified_xml.encode("utf-8"))

                translation = ItemTranslation(
                    item_id=ch.id,
                    volume_id=job.volume_id,
                    model_type=model_type,
                    qa_round=0,
                    content=compressed,
                )
                session.add(translation)
                session.commit()

            completed += 1
            progress_callback(completed, total)

        # Translate Nav files
        nav_items = session.query(FileItem).filter_by(
            volume_id=job.volume_id,
            item_type="Nav",
            obsolete=False
        ).all()

        for nav in nav_items:
            content = zlib.decompress(nav.content)
            text = content.decode("utf-8", errors="replace")

            from .translation_processor import process_toc
            modified_nav = process_toc(text, llm_config.get("chunk_size", 12), {}, glossary, llm_config)

            if modified_nav:
                compressed = zlib.compress(modified_nav.encode("utf-8"))
                translation = ItemTranslation(
                    item_id=nav.id,
                    volume_id=job.volume_id,
                    model_type=model_type,
                    qa_round=0,
                    content=compressed,
                )
                session.add(translation)
                session.commit()


def execute_qa_job(job, progress_callback):
    """Execute QA job with multi-pass correction and multi-threading support."""
    from .qa_processor import process_qa_document, run_qa_on_chapters
    import zlib
    import json

    with get_session() as session:
        # Load project and config
        project = session.query(Project).filter_by(id=job.project_id).first()
        if not project:
            raise ValueError(f"Project {job.project_id} not found")

        config = session.query(TaskDefinition).filter_by(id=job.config_id).first()
        if not config:
            raise ValueError(f"Config {job.config_id} not found")

        # Build QA config with all LLM parameters
        qa_config = {
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
            "chunk_size": config.chunk_size,
            "use_mini_glossary": config.use_mini_glossary,
            "traditional_chinese": config.traditional_chinese,
            "threads": config.threads,
        }

        # Get project glossary
        glossary = json.loads(project.glossary) if project.glossary else {}

        start_version = job.params.get("start_version", 0)
        num_passes = job.params.get("num_passes", 1)
        model_type = config.model_type or config.config_name
        threads = config.threads or 1

        for pass_idx in range(num_passes):
            qa_round = start_version + pass_idx

            # Get chapters that have a translation at the previous QA round
            prev_round = qa_round - 1 if qa_round > 0 else 0
            prev_translations = session.query(ItemTranslation).filter_by(
                volume_id=job.volume_id,
                model_type=model_type,
                qa_round=prev_round,
            ).all()

            if not prev_translations:
                print(f"      [!] No translations found for qa_round {prev_round}. Skipping pass {pass_idx}.")
                continue

            # Prepare chapter items for QA
            chapter_items = []
            for trans in prev_translations:
                content = zlib.decompress(trans.content)
                text = content.decode("utf-8", errors="replace")
                chapter_items.append((trans.item_id, text))

            total = len(chapter_items)
            results = []

            if threads > 1:
                # Multi-threaded QA
                from concurrent.futures import ThreadPoolExecutor, as_completed

                def process_single(args):
                    item_id, content = args
                    modified, heading_map = process_qa_document(content, glossary, qa_config)
                    return (item_id, modified, heading_map)

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
                for item_id, content in chapter_items:
                    modified, heading_map = process_qa_document(content, glossary, qa_config)
                    results.append((item_id, modified, heading_map))

            # Save QA results
            for item_id, modified_xml, heading_map in results:
                if modified_xml:
                    compressed = zlib.compress(modified_xml.encode("utf-8"))
                    # Check if translation already exists for this round
                    existing = session.query(ItemTranslation).filter_by(
                        item_id=item_id,
                        model_type=model_type,
                        qa_round=qa_round,
                    ).first()

                    if existing:
                        existing.content = compressed
                    else:
                        new_trans = ItemTranslation(
                            item_id=item_id,
                            volume_id=job.volume_id,
                            model_type=model_type,
                            qa_round=qa_round,
                            content=compressed,
                        )
                        session.add(new_trans)
                    session.commit()

            # Progress callback after each pass
            progress_callback((pass_idx + 1) * total, num_passes * total)

            # Update Nav after each pass