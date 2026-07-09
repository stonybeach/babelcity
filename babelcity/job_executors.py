"""Job execution functions called by the worker loop."""

from datetime import datetime

from .database import get_session
from .models import FileItem, ItemTranslation, Project, BookVolume, TaskDefinition
from .glossary_processor import scan_for_entities, merge_glossary
from .text_processor import chunk_paragraphs, extract_paragraphs, load_dictionary


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
        pre_translated_text = job.params.get("pre_translated_terms", "")

        pre_translated = load_dictionary(pre_translated_text)
        print(f"Loaded pre-translated items: {len(pre_translated)}")

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

        # Existing glossary
        import json
        # Get project glossary (may be dict or JSON string)
        if project.glossary is None:
            existing_glossary = {}
        elif isinstance(project.glossary, dict):
            existing_glossary = project.glossary
        else:
            existing_glossary = json.loads(project.glossary)

        merged = dict(existing_glossary)
        total = len(chapters)
        completed = 0
        progress_callback(0, total)

        for ch in chapters:
            # Decompress content
            import zlib
            content = zlib.decompress(ch.content)
            text = content.decode("utf-8", errors="replace")

            # Extract paragraphs and chunk
            paragraphs = extract_paragraphs(text)
            chunks = chunk_paragraphs(paragraphs, config.chunk_size)
            for chunk in chunks:
                chunk_text = "\n".join(chunk)
                terms = scan_for_entities(chunk_text, llm_config, existing_glossary=merged, pre_translated=pre_translated)
                merged = merge_glossary(merged, terms)
                print(f"Glossary count: {len(merged)}")

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
            "synchronize_quotes": config.synchronize_quotes,
            "threads": config.threads,
        }

        # Get project glossary (may be dict or JSON string)
        if project.glossary is None:
            glossary = {}
        elif isinstance(project.glossary, dict):
            glossary = project.glossary
        else:
            glossary = json.loads(project.glossary)

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

        if threads > 1:
            # Multi-threaded translation using ThreadPoolExecutor
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading

            completed_counter = threading.atomic(0) if hasattr(threading, 'atomic') else {'value': 0}
            counter_lock = threading.Lock()

            def process_chapter(ch):
                from .translation_processor import process_document
                import zlib
                content = zlib.decompress(ch.content)
                text = content.decode("utf-8", errors="replace")
                modified_xml, heading_map = process_document(text, glossary, llm_config)
                return ch, modified_xml, heading_map

            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {executor.submit(process_chapter, ch): ch for ch in chapters}
                for future in as_completed(futures):
                    ch = futures[future]
                    try:
                        _, modified_xml, heading_map = future.result()
                        if modified_xml:
                            import zlib
                            compressed = zlib.compress(modified_xml) if isinstance(modified_xml, bytes) else zlib.compress(modified_xml.encode("utf-8"))
                            with get_session() as save_session:
                                existing = save_session.query(ItemTranslation).filter_by(
                                    item_id=ch.id,
                                    model_type=model_type,
                                    qa_round=0,
                                ).first()
                                if existing:
                                    existing.content = compressed
                                    existing.last_translation_start = datetime.utcnow()
                                    existing.last_translation_end = datetime.utcnow()
                                    existing.qa_model = None
                                else:
                                    translation = ItemTranslation(
                                        item_id=ch.id,
                                        model_type=model_type,
                                        qa_round=0,
                                        content=compressed,
                                        last_translation_start=datetime.utcnow(),
                                        last_translation_end=datetime.utcnow(),
                                        qa_model=None,
                                    )
                                    save_session.add(translation)
                                save_session.commit()
                    except Exception as e:
                        print(f"Error translating chapter {ch.full_path}: {e}")

                    with counter_lock:
                        completed_counter['value'] += 1
                        completed = completed_counter['value']
                    progress_callback(completed, total)
        else:
            for ch in chapters:
                # Decompress content
                content = zlib.decompress(ch.content)
                text = content.decode("utf-8", errors="replace")

                # Translate
                modified_xml, heading_map = process_document(text, glossary, llm_config)

                if modified_xml:
                    # serialize_xml() returns bytes; compress directly
                    import zlib
                    compressed = zlib.compress(modified_xml) if isinstance(modified_xml, bytes) else zlib.compress(modified_xml.encode("utf-8"))

                    existing = session.query(ItemTranslation).filter_by(
                        item_id=ch.id,
                        model_type=model_type,
                        qa_round=0,
                    ).first()
                    if existing:
                        existing.content = compressed
                        existing.last_translation_start = datetime.utcnow()
                        existing.last_translation_end = datetime.utcnow()
                        existing.qa_model = None
                    else:
                        translation = ItemTranslation(
                            item_id=ch.id,
                            model_type=model_type,
                            qa_round=0,
                            content=compressed,
                            last_translation_start=datetime.utcnow(),
                            last_translation_end=datetime.utcnow(),
                            qa_model=None,
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
                compressed = zlib.compress(modified_nav) if isinstance(modified_nav, bytes) else zlib.compress(modified_nav.encode("utf-8"))
                existing = session.query(ItemTranslation).filter_by(
                    item_id=nav.id,
                    model_type=model_type,
                    qa_round=0,
                ).first()
                if existing:
                    existing.content = compressed
                    existing.last_translation_start = datetime.utcnow()
                    existing.last_translation_end = datetime.utcnow()
                    existing.qa_model = None
                else:
                    translation = ItemTranslation(
                        item_id=nav.id,
                        model_type=model_type,
                        qa_round=0,
                        content=compressed,
                        last_translation_start=datetime.utcnow(),
                        last_translation_end=datetime.utcnow(),
                        qa_model=None,
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
            "synchronize_quotes": config.synchronize_quotes,
            "history": config.history,
            "threads": config.threads,
        }

        # Get project glossary (may be dict or JSON string)
        if project.glossary is None:
            glossary = {}
        elif isinstance(project.glossary, dict):
            glossary = project.glossary
        else:
            glossary = json.loads(project.glossary)

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
                    compressed = zlib.compress(modified_xml) if isinstance(modified_xml, bytes) else zlib.compress(modified_xml.encode("utf-8"))
                    # Check if translation already exists for this round
                    existing = session.query(ItemTranslation).filter_by(
                        item_id=item_id,
                        model_type=translation_model_type,
                        qa_round=qa_round,
                    ).first()

                    if existing:
                        existing.content = compressed
                        existing.last_translation_start = datetime.utcnow()
                        existing.last_translation_end = datetime.utcnow()
                        existing.qa_model = config.model_type or config.config_name
                    else:
                        new_trans = ItemTranslation(
                            item_id=item_id,
                            model_type=translation_model_type,
                            qa_round=qa_round,
                            content=compressed,
                            last_translation_start=datetime.utcnow(),
                            last_translation_end=datetime.utcnow(),
                            qa_model=config.model_type or config.config_name,
                        )
                        session.add(new_trans)
                    session.commit()

            # Progress callback after each pass
            progress_callback((pass_idx + 1) * total, num_passes * total)

            # Update Nav after each QA pass
            nav_items = session.query(FileItem).filter_by(
                volume_id=job.volume_id,
                item_type="Nav",
                obsolete=False
            ).all()

            for nav in nav_items:
                content = zlib.decompress(nav.content)
                text = content.decode("utf-8", errors="replace")

                from .translation_processor import process_toc
                modified_nav = process_toc(text, qa_config.get("chunk_size", 12), {}, glossary, qa_config)

                if modified_nav:
                    compressed_nav = zlib.compress(modified_nav) if isinstance(modified_nav, bytes) else zlib.compress(modified_nav.encode("utf-8"))
                    existing_nav = session.query(ItemTranslation).filter_by(
                        item_id=nav.id,
                        model_type=translation_model_type,
                        qa_round=qa_round,
                    ).first()
                    if existing_nav:
                        existing_nav.content = compressed_nav
                        existing_nav.last_translation_start = datetime.utcnow()
                        existing_nav.last_translation_end = datetime.utcnow()
                        existing_nav.qa_model = config.model_type or config.config_name
                    else:
                        nav_trans = ItemTranslation(
                            item_id=nav.id,
                            model_type=translation_model_type,
                            qa_round=qa_round,
                            content=compressed_nav,
                            last_translation_start=datetime.utcnow(),
                            last_translation_end=datetime.utcnow(),
                            qa_model=config.model_type or config.config_name,
                        )
                        session.add(nav_trans)
                    session.commit()