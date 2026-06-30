# Babel City - Implementation Plan

## 1. Python Packages

| Package | Purpose |
|---|---|
| `reflex` (reflex-dev/reflex) | UI framework (reactive web app) |
| `reflex-aggrid` | AG-Grid component for Reflex (glossary editor: inline editing, row deletion, bulk save) |
| `sqlite3` (stdlib) | Database engine |
| `sqlalchemy` (>=2.0) | ORM for thread-safe DB access |
| `zipfile` (stdlib) | EPUB parsing and generation (handles non-English EPUBs) |
| `openai` | LLM API client (OpenAI-compatible) |
| `opencc-python-reimplemented` | Simplified to Traditional Chinese conversion |
| `lxml` | XHTML/XML parsing and serialization |
| `concurrent.futures` (stdlib) | Thread pool for parallel chapter translation/QA |
| `threading` (stdlib) | Job queue locking and worker coordination |
| `zlib` (stdlib) | Compression for XHTML content in DB |
| `pydantic` | Data validation for task definitions |
| `uuid` (stdlib) | ID generation for entities |
| `python-dateutil` | Timestamp handling |

---

## 2. Database Schema Design (SQLite)

Database runs in **WAL mode** (`PRAGMA journal_mode=WAL`) with `timeout=30.0` on all connections. SQLite handles multi-GB databases well; with zlib compression on content BLOBs, storage is efficient.

### Table: `projects`
| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT (UUID) | PRIMARY KEY |
| `project_type` | TEXT | NOT NULL CHECK (IN ('Light Novel', 'Web Novel')) |
| `project_name` | TEXT | NOT NULL |
| `source_title` | TEXT | NOT NULL |
| `source_language` | TEXT | NOT NULL DEFAULT 'ja' |
| `target_language` | TEXT | NOT NULL DEFAULT 'zh' |
| `glossary` | TEXT (JSON) | NOT NULL DEFAULT '{}' |
| `created_at` | TIMESTAMP | NOT NULL |
| `updated_at` | TIMESTAMP | NOT NULL |

### Table: `book_volumes`
| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT (UUID) | PRIMARY KEY |
| `project_id` | TEXT | NOT NULL, FK -> projects.id |
| `volume_number` | TEXT | NOT NULL |
| `source_volume_title` | TEXT | NULLABLE |
| `target_volume_title` | TEXT | NULLABLE |
| `created_at` | TIMESTAMP | NOT NULL |
| `updated_at` | TIMESTAMP | NOT NULL |

Unique constraint: `(project_id, volume_number)`

### Table: `file_items`
| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT (UUID) | PRIMARY KEY |
| `volume_id` | TEXT | NOT NULL, FK -> book_volumes.id |
| `full_path` | TEXT | NOT NULL |
| `content` | BLOB | NOT NULL (zlib-compressed original content) |
| `item_type` | TEXT | NOT NULL CHECK (IN ('Chapter', 'Nav', 'Resource')) |
| `glossary_scanned` | BOOLEAN | NOT NULL DEFAULT FALSE |
| `obsolete` | BOOLEAN | NOT NULL DEFAULT FALSE |
| `created_at` | TIMESTAMP | NOT NULL |

Unique constraint: `(volume_id, full_path)`

### Table: `item_translations`
| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT (UUID) | PRIMARY KEY |
| `item_id` | TEXT | NOT NULL, FK -> file_items.id |
| `model_type` | TEXT | NOT NULL |
| `qa_round` | INTEGER | NOT NULL DEFAULT 0 |
| `content` | BLOB | NOT NULL (zlib-compressed full modified XHTML: original + translated paragraphs) |
| `status` | BOOLEAN | NOT NULL DEFAULT TRUE |
| `last_translation_start` | TIMESTAMP | NULLABLE |
| `last_translation_end` | TIMESTAMP | NULLABLE |
| `qa_model` | TEXT | NULLABLE (used when qa_round > 0) |

Unique constraint: `(item_id, model_type, qa_round)`

### Table: `task_definitions`
| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT (UUID) | PRIMARY KEY |
| `config_name` | TEXT | NOT NULL UNIQUE |
| `config_type` | TEXT | NOT NULL CHECK (IN ('Glossary', 'Translation', 'QA')) |
| `base_url` | TEXT | NOT NULL DEFAULT 'http://localhost:8080/v1' |
| `api_key` | TEXT | NOT NULL DEFAULT 'not-needed' |
| `model` | TEXT | NOT NULL DEFAULT 'default' |
| `max_tokens` | INTEGER | NOT NULL DEFAULT 8192 |
| `temperature` | REAL | NULLABLE |
| `top_p` | REAL | NULLABLE |
| `min_p` | REAL | NULLABLE |
| `top_k` | INTEGER | NULLABLE |
| `presence_penalty` | REAL | NULLABLE |
| `frequency_penalty` | REAL | NULLABLE |
| `repetition_penalty` | REAL | NULLABLE |
| `chunk_size` | INTEGER | NOT NULL DEFAULT 12 |
| `history` | INTEGER | NULLABLE DEFAULT 5 (Translation only; not used for QA) |
| `use_mini_glossary` | BOOLEAN | NULLABLE DEFAULT TRUE (Translation/QA only) |
| `threads` | INTEGER | NULLABLE DEFAULT 1 (Translation/QA only) |
| `synchronize_quotes` | BOOLEAN | NULLABLE DEFAULT TRUE (Translation/QA only) |
| `traditional_chinese` | BOOLEAN | NULLABLE DEFAULT TRUE (Translation/QA only) |
| `model_type` | TEXT | NULLABLE (optional override; if empty, use `model` name) |
| `retry_attempts` | INTEGER | NOT NULL DEFAULT 2 |
| `override_system_prompt` | TEXT | NULLABLE |
| `is_default` | BOOLEAN | NOT NULL DEFAULT FALSE |
| `created_at` | TIMESTAMP | NOT NULL |
| `updated_at` | TIMESTAMP | NOT NULL |

---

## 3. Python Files and Descriptions

### `babelcity/__init__.py`
Package init. Imports the Reflex app.

### `babelcity/main.py`
Reflex app entry point. Initializes DB, sets up routing (including `/volume/{volume_id}/resource/{path}` for IFrame CSS serving), creates the Reflex app.

**Classes and functions:**
- `AppState(rx.State)` - Top-level state: current tab, theme (light/dark), job queue reference
- `index()` - Root page: renders navbar + dispatches to Projects/Tasks/Jobs tab
- `serve_volume_resource(volume_id, resource_path)` - Reflex route handler: decompresses and serves File_Item resource content (CSS, images) for IFrame rendering. Rewrites relative paths in chapter XHTML to absolute `/volume/{volume_id}/resource/{path}` URLs.
- `app = rx.App(state=AppState)` - Reflex app instance

### `babelcity/database.py`
Database initialization, SQLAlchemy engine/session factory. WAL mode enabled. Thread-safe session context manager.

**Functions:**
- `get_engine()` - SQLAlchemy engine: `check_same_thread=False`, `timeout=30.0`, `PRAGMA journal_mode=WAL`
- `get_session()` - Context manager yielding a thread-local session
- `init_db()` - Create all tables via `Base.metadata.create_all`
- `close_db()` - Dispose engine connections

### `babelcity/models.py`
SQLAlchemy ORM models.

**Classes:**
- `Base` - Declarative base
- `Project` - ORM model for projects
- `BookVolume` - ORM model for book_volumes
- `FileItem` - ORM model for file_items (content as zlib-compressed BLOB)
- `ItemTranslation` - ORM model for item_translations (content as zlib-compressed BLOB)
- `TaskDefinition` - ORM model for task_definitions

### `babelcity/epub_handler.py`
EPUB import/export using `zipfile`. Parses container.xml -> content.opf. Classifies items. Generates EPUB bytes for browser download.

**Functions:**
- `import_epub(volume_id, file_bytes)` - Open EPUB via zipfile, parse metadata, classify items, compress/store content, mark old items obsolete. Nav selection: nav.xhtml > toc.xhtml > first manifest entry with `property="nav"`. Extra nav-like files become Resource.
- `export_epub(volume_id, model_type, qa_round)` - Build EPUB bytes. Fallback per item: `(model_type, qa_round)` -> `(model_type, 0)` -> original. Returns bytes for download.
- `get_epub_metadata(zip_file)` - Parse content.opf: spine, TOC, manifest
- `classify_item(manifest_entry, spine, all_entries)` - Chapter (in spine, not Nav), Nav, or Resource
- `mark_items_obsolete(volume_id)` - Mark existing FileItems obsolete
- `select_nav_file(manifest_entries)` - Single Nav: nav.xhtml > toc.xhtml > first `property="nav"`

### `babelcity/llm_handler.py`
LLM API calls with retry. Ports PoC `extract_json` and `remove_think_tags`.

**Functions:**
- `ask_llm(base_url, api_key, model, messages, max_tokens, **params)` - OpenAI-compatible call with retries
- `extract_json(text)` - Extract JSON from LLM output
- `validate_json_response(text)` - Valid JSON object check
- `remove_think_tags(text)` - Strip reasoning tags

### `babelcity/text_processor.py`
Text utilities: chunking, glossary filtering, quote sync, OpenCC, ruby handling.

**Functions:**
- `build_mini_glossary(text, full_glossary)` - Filter glossary to terms in text
- `sync_quotes(source, translated)` - Sync quotes/brackets
- `finalize_text(text, traditional_chinese)` - OpenCC conversion if enabled
- `extract_text_with_ruby(tree)` - Ruby tags to `(ruby)` format
- `has_japanese(text)` - Hiragana/katakana check
- `parse_xml(text)` - XHTML to lxml tree
- `serialize_xml(tree)` - lxml tree to string
- `load_dictionary(pre_translated_text)` - Parse pre-translated terms (one per line: `Source => Translation`). Drop everything after `#`.
- `chunk_paragraphs(paragraphs, chunk_size)` - Group paragraphs into chunks

### `babelcity/glossary_processor.py`
Glossary scanning via LLM.

**Functions:**
- `scan_for_entities(text_chunk, llm_config, pre_translated)` - Extract terms from chunk
- `filter_glossary_terms(terms, source_language)` - Discard >30 chars or non-Japanese (source=ja)
- `merge_glossary(existing, new_terms, pre_translated)` - Merge terms, apply overrides

### `babelcity/translation_processor.py`
Chapter and Nav translation. Exact PoC logic: delimiter/paragraph validation, recovery, line-by-line fallback. Parallel chapter translation via ThreadPoolExecutor (matching `run_translation_pass`).

**Functions:**
- `translate_chunk(paragraphs, history_paragraphs, glossary, llm_config)` - Translate chunk; validate; retry; line-by-line fallback
- `translate_single_line(line, glossary, llm_config)` - Fallback line translation
- `apply_translation_to_chunk(tree, translated_paragraphs)` - Inject below original; dim with `opacity:0.4`
- `process_document(item_content, glossary, llm_config, model_type, resume)` - Full chapter: decompress, parse, chunk, translate, inject, serialize, compress. Returns (modified_xhtml_bytes, heading_map). Resume=True skips valid translations.
- `run_translation_on_chapters(chapter_items, glossary, llm_config, model_type, threads, resume)` - Parallel chapter translation. threads>1: ThreadPoolExecutor assigns whole chapters to threads (chunks within chapter stay sequential for history context). threads=1: sequential.
- `translate_toc_content(nav_tree, chapter_headers, llm_config)` - Translate TOC; reuse chapter headers; single-line fallback
- `process_toc(item_content, chapter_translations, llm_config, model_type)` - Nav translation at QA round 0
- `update_toc_after_qa(item_content, chapter_translations, qa_round, model_type)` - Update Nav after QA: use headers from that round; if not found, leave as-is

### `babelcity/qa_processor.py`
QA correction. Multi-threaded per `run_qa_pass`. Exact PoC JSON validation.

**Functions:**
- `process_qa_document(item_content, qa_config, start_round)` - QA single chapter
- `run_qa_on_chapters(chapter_items, qa_config, start_round, threads)` - Parallel QA. ThreadPoolExecutor if threads>1.
- `run_qa_passes(volume_id, qa_config, start_round, num_passes)` - N sequential passes. After each: update Nav via `update_toc_after_qa`.

### `babelcity/job_queue.py`
In-memory job queue. Thread-safe. Lost on restart.

**Classes:**
- `Job` - Dataclass: `id`, `job_type`, `project_id`, `project_name`, `volume_id`, `volume_number`, `config_id`, `params`, `status` (Pending/Running/Completed/Failed), `progress_completed`, `progress_total`, `created_at`, `result_message`
- `JobQueue` - Singleton:
  - `add_job(job)` - Append to pending (locked)
  - `start()` - Start daemon worker thread
  - `pause()` - Interrupt running job; move to top of pending
  - `remove_job(job_id)` - Remove Pending only (Running cannot be deleted)
  - `clear_pending()` - Remove all pending
  - `move_up/down/top/bottom(job_id)` - Reorder pending
  - `repeat_job(job_id)` - Completed -> Pending
  - `remove_completed(job_id)`, `clear_completed()` - Cleanup
  - `get_all_jobs()` - All jobs for UI
  - `is_running()` - Worker active check
  - `worker_loop()` - Pick next pending -> Running -> execute -> Completed/Failed

### `babelcity/job_executors.py`
Job execution functions.

**Functions:**
- `execute_glossary_job(job, progress_callback)` - Scan volume. Add Only=False: reset glossary. Scan non-obsolete items (all if Resume=False, unscanned if Resume=True). Merge, save.
- `execute_translation_job(job, progress_callback)` - Translate non-obsolete chapters. Resume=True: skip valid translations; translate missing or Invalid items. After chapters: translate Nav (QA round 0). Parallel if config.threads > 1.
- `execute_qa_job(job, progress_callback)` - N sequential QA passes. Each: parallel QA on chapters, then update Nav. Store at incremented QA round.
- `update_job_progress(job_id, completed, total)` - Thread-safe progress update

### `babelcity/state.py`
Reflex state classes.

**Classes:**
- `ProjectState(rx.State)` - Projects tab state
  - `load_projects()` - Query all projects
  - `create_project(project_type, name, source_title, src_lang, tgt_lang)` - Create; auto-create Volume "1" for Web Novel
  - `update_project(...)` - Update fields
  - `delete_project(project_id)` - Delete with confirmation
  - `import_epub(volume_id, file_upload)` - Import EPUB
  - `export_epub(volume_id, model_type, qa_round)` - Generate EPUB bytes for download. Model/round selection based on Nav Item_Translations only (if Nav exists for that model+round, the set is complete).
  - `open_book_viewer(volume_id)` - Load chapter list
  - `select_chapter(chapter_id)` - Load chapter for IFrame (rewrite CSS paths to `/volume/{vol_id}/resource/{path}`)
  - `update_chapter_status(chapter_id, field, value)` - Toggle obsolete/status
  - `get_available_models_and_rounds(volume_id)` - Nav-based: query distinct (model_type, qa_round) from Item_Translations where item_type=Nav. "Original" always available with round 0 only.
- `GlossaryState(rx.State)` - Glossary editor state: AG-Grid entries, validation errors
  - `load_glossary(project_id)` - Load glossary JSON into AG-Grid rows
  - `add_entry()` - Add empty row to grid
  - `delete_entry(index)` - Delete row from grid
  - `save_glossary()` - Validate grid data: duplicates in Source Term, empty Source Term, empty Translated Name -> warning, cancel. Empty Type/Gender -> "未知". Convert to JSON, persist.
- `TaskState(rx.State)` - Tasks tab state
  - `load_task_definitions()` - Query all
  - `create_task_def(config_type, **fields)` - Create
  - `update_task_def(task_id, **fields)` - Update
  - `delete_task_def(task_id)` - Delete
  - `set_default(task_id)` - Mark default (unmark same type)
- `JobState(rx.State)` - Jobs tab state
  - `get_job_queue()` - Get/create singleton
  - `load_jobs()` - All jobs
  - `add_glossary_job(...)` / `add_translation_job(...)` / `add_qa_job(...)` - Add jobs
  - `start_queue()` / `pause_queue()` - Worker control
  - `move_job(job_id, direction)` - Reorder
  - `repeat_job(job_id)` - Completed -> Pending
  - `delete_job(job_id)` - Delete Pending/Completed (not Running)
  - `clear_completed()` - Cleanup

### `babelcity/components/navbar.py`
Top navigation bar.

**Functions:**
- `navbar()` - Logo (tower + warm orange sunset) + "Babel City" (left); Projects/Tasks/Jobs tabs (center); Light/Dark toggle (right)

### `babelcity/components/projects.py`
Projects tab components.

**Functions:**
- `projects_tab()` - Main view
- `project_list()` - Table: ID, Name, Type, Volume dropdown, Glossary/Modify/Delete icons. "Add" button top-left.
- `project_editor(project)` - Name, Source Title, Langs editable. Type read-only. "Add Book Volume" (hidden for Web Novel), "Glossary". Volumes table: Number, titles, View/Upload, Delete (Light Novel only).
- `book_viewer(volume)` - Top bar: Model Type dropdown (includes "Original"), QA Round dropdown (dependent on model). Left: chapter list (spine order). Right: IFrame with chapter XHTML (CSS paths rewritten to `/volume/{vol_id}/resource/{path}`). Bottom: Obsolete/Status checkboxes, timestamps, QA Model.
- `volume_upload_dialog(project)` - EPUB upload
- `export_dialog(volume)` - Model/round dropdowns (based on Nav translations). Download button.

### `babelcity/components/glossary.py`
Glossary editor with AG-Grid.

**Functions:**
- `glossary_editor(project)` - AG-Grid table: Source Term, Translated Name, Type, Gender columns (inline editable). Row deletion via AG-Grid row removal. "Add Entry" button. "Save" button validates all rows (duplicates, empty source/translation -> warning; empty type/gender -> "未知"), converts to JSON, persists.

### `babelcity/components/tasks.py`
Tasks tab components.

**Functions:**
- `tasks_tab()` - Main view
- `task_definitions_list()` - Table: Name, Type, Model, Edit/Delete, Default
- `glossary_task_form(task=None)` - Name, URL, Key, Model, Tokens, Temp/top_p/min_p/top_k, penalties, Chunk, Retry, Prompt
- `translation_task_form(task=None)` - All Glossary + History, Mini-Glossary, Threads, Sync Quotes, Traditional Chinese, Model Type
- `qa_task_form(task=None)` - All Glossary + Mini-Glossary, Threads, Sync Quotes, Traditional Chinese, Model Type, Retry, Prompt (no History)

### `babelcity/components/jobs.py`
Jobs tab components.

**Functions:**
- `jobs_tab()` - Main view
- `job_button_bar()` - Left: Glossary/Translation/QA Job (+). Right: Start/Pause.
- `glossary_job_form()` - Project/Volume/Config, Resume, Add Only, Pre-translated textarea
- `translation_job_form()` - Project/Volume/Config, Resume
- `qa_job_form()` - Project/Volume/Config, Start Version, Num Passes
- `job_status_table()` - Type, Project, Volume, Status, Progress. Up/Down/Top/Bottom (Pending), Repeat (Completed), Delete (Pending/Completed; disabled for Running)

### `babelcity/assets/logo.svg`
SVG logo: generic ancient tower silhouette on a hill, warm orange sunset behind, transparent background.

---

## 4. UI Design

### Navigation Bar
- **Left**: Logo + "Babel City"
- **Center**: `Projects` | `Tasks` | `Jobs`
- **Right**: Light/Dark theme toggle

### Tab 1: Projects

#### Project List
- **Top-left**: "Add" (+ icon)
- **Table**: ID (clickable), Name (clickable), Type, Volume dropdown, Glossary/Modify/Delete icons
- **New Project**: Type, Name, Source Title, Source/Target Lang. Web Novel auto-creates Volume "1".

#### Project Editor
- **Section 1**: Name, Source Title, Langs (Type read-only)
- **Section 2**: "Add Book Volume" (+ hidden for Web Novel), "Glossary"
- **Volumes**: Number, titles (editable), View/Upload, Delete (Light Novel only)

#### Book Viewer
- **Top bar**: Model Type dropdown ("Original" + available model types from Nav translations), QA Round dropdown (dependent: "Original" -> 0 only; other models show their Nav rounds)
- **Left panel**: Chapter list (spine order)
- **Right panel**: IFrame with chapter XHTML. CSS resources served via `/volume/{vol_id}/resource/{path}` route.
- **Bottom bar**: Obsolete/Status checkboxes, timestamps, QA Model

#### Glossary Editor (AG-Grid)
- **AG-Grid table**: Source Term, Translated Name, Type, Gender (inline editable). Row delete via grid actions.
- **Top**: "Add Entry", "Save" (bulk save with validation)
- **Validation**: Duplicate Source Terms, empty Source Term, empty Translated Name -> warning, cancel. Empty Type/Gender -> "未知".

### Tab 2: Tasks

#### Task Definitions
- **Buttons**: Add Glossary/Translation/QA Task
- **Table**: Name, Type, Model, Edit/Delete, Default

#### Task Forms (modal)
- **Glossary**: Name, URL, Key, Model, Tokens, Temp/top_p/min_p/top_k, penalties, Chunk, Retry, Prompt
- **Translation**: All Glossary + History, Mini-Glossary, Threads, Sync Quotes, Traditional Chinese, Model Type
- **QA**: All Glossary + Mini-Glossary, Threads, Sync Quotes, Traditional Chinese, Model Type, Retry, Prompt

### Tab 3: Jobs

#### Job Management
- **Left**: Glossary/Translation/QA Job (+)
- **Right**: Start/Pause
- **Table**: Type, Project, Volume, Status, Progress. Up/Down/Top/Bottom (Pending), Repeat (Completed), Delete (Pending/Completed; NOT Running)

#### Job Forms (modal)
- **Glossary**: Project/Volume/Config, Resume, Add Only, Pre-translated textarea
- **Translation**: Project/Volume/Config, Resume
- **QA**: Project/Volume/Config, Start Version, Num Passes

---

## 5. Key Architectural Decisions

### Reflex Framework
- Reactive model (Vite/Next.js backend): no full script re-execution
- Background worker threads persist naturally (long-lived process)
- State mutations trigger targeted re-renders for job progress updates
- Hot-reload in development restarts process (acceptable)

### Parallel Translation (matching `run_translation_pass`)
- `threads > 1`: ThreadPoolExecutor assigns whole chapters to threads. Chunks within a chapter remain sequential in the same thread to preserve history context.
- `threads = 1`: Sequential processing.
- Pre-read all chapter contents before parallel processing (zipfile thread safety).

### Nav Translation and Export Completeness
- After original translation completes: Nav translated at QA round 0 (reuse chapter headers or single-line fallback).
- After each QA pass: Nav updated at that QA round (reuse chapter headers; if not found, leave as-is).
- **Export Model/round selection is based on Nav Item_Translations only**: if a (model_type, qa_round) exists for Nav, the entire set for that model+round is complete. Fallback chain `(model, round)` -> `(model, 0)` -> original is a fail-safe.

### Translation Resume
Resume=True: translate only items that (a) have no translation for model_type at QA round 0, OR (b) have translation marked Invalid. Valid translations skipped.

### IFrame CSS Serving
Reflex route `/volume/{volume_id}/resource/{path}` serves decompressed resource files (CSS, images). Chapter XHTML paths rewritten from relative (`../styles/xxx.css`) to absolute (`/volume/{vol_id}/resource/styles/xxx.css`) before IFrame rendering.

### EPUB Export
Browser download via Reflex download component. Takes seconds for large volumes (acceptable).

### Pre-translated Terms
One per line: `Source => Translation # Comment`. Everything after `#` dropped (gender determined by LLM).

### Glossary Editor - AG-Grid
AG-Grid via `reflex-aggrid` provides: inline cell editing, row deletion (grid action column), bulk save (all changes in grid until Save clicked), validation on save.

---

## 6. Potential Issues and Concerns

1. **Reflex hot-reload**: Development hot-reload restarts the Python process, killing worker threads. Acceptable for development; production process is stable.

2. **SQLite multi-GB databases**: SQLite handles several GB well. WAL mode + zlib compression on content BLOBs keeps I/O efficient. No full-text search needed on content.

3. **EPUB re-import for Web Novels**: `full_path` matches for existing chapters on re-upload. Old items marked obsolete. User can Invalid + Resume to retranslate specific chapters.

4. **AG-Grid with Reflex**: `reflex-aggrid` supports inline editing, row deletion, and bulk operations. The grid state (rows) is managed in Reflex state; changes are temporary until Save is clicked, which validates and persists to JSON.
