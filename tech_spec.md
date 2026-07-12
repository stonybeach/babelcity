# Babel City — Backend Technical Specification

## Overview

Babel City is a local Web Novel & EPUB Translation Organizer. Backend: FastAPI + SQLAlchemy + SQLite. Frontend: React 18 + TypeScript + Vite + Tailwind CSS 3.

- Python 3.11 (`.venv`), SQLite WAL mode (`timeout=30.0`)
- `zipfile` for EPUB, `opencc-python-reimplemented` for Traditional Chinese, `lxml` for XML
- WebSocket for real-time job progress; `job_queue.py` runs in-memory worker loop
- All UUID primary keys use `default=lambda: str(uuid.uuid4())`

---

## Database Models (`models.py`)

### `Project` (table: `projects`)

| Column | Type | Constraints | Meaning |
|--------|------|-------------|---------|
| `id` | `String(36)` | PK, default `uuid4()` | Project UUID |
| `project_type` | `String(20)` | NOT NULL, CHECK `IN ('Light Novel', 'Web Novel')` | Type of project |
| `project_name` | `String(255)` | NOT NULL | Display name |
| `source_title` | `String(255)` | NOT NULL | Original title |
| `source_language` | `String(10)` | NOT NULL, default `"ja"` | Source lang code |
| `target_language` | `String(10)` | NOT NULL, default `"zh"` | Target lang code |
| `glossary` | `JSON` | NOT NULL, default `{}` | Project glossary dict |
| `created_at` | `DateTime` | NOT NULL, default `utcnow` | Creation timestamp |
| `updated_at` | `DateTime` | NOT NULL, default `utcnow`, onupdate | Last update timestamp |

### `BookVolume` (table: `book_volumes`)

| Column | Type | Constraints | Meaning |
|--------|------|-------------|---------|
| `id` | `String(36)` | PK, default `uuid4()` | Volume UUID |
| `project_id` | `String(36)` | FK `projects.id`, NOT NULL | Parent project |
| `volume_number` | `String(20)` | NOT NULL | Volume number (e.g. "1") |
| `source_volume_title` | `String(255)` | NULLABLE | Original volume title |
| `target_volume_title` | `String(255)` | NULLABLE | Translated volume title |
| `created_at` | `DateTime` | NOT NULL, default `utcnow` | Creation timestamp |
| `updated_at` | `DateTime` | NOT NULL, default `utcnow`, onupdate | Last update timestamp |

**Unique constraint:** `(project_id, volume_number)`

### `FileItem` (table: `file_items`)

| Column | Type | Constraints | Meaning |
|--------|------|-------------|---------|
| `id` | `String(36)` | PK, default `uuid4()` | Item UUID |
| `volume_id` | `String(36)` | FK `book_volumes.id`, NOT NULL | Parent volume |
| `full_path` | `String(500)` | NOT NULL | EPUB item path |
| `content` | `LargeBinary` | NOT NULL | `zlib`-compressed content bytes |
| `item_type` | `String(10)` | NOT NULL, CHECK `IN ('Chapter', 'Nav', 'Resource')` | Item type |
| `glossary_scanned` | `Boolean` | NOT NULL, default `False` | Whether glossary has been scanned |
| `obsolete` | `Boolean` | NOT NULL, default `False` | Whether item is obsolete |
| `created_at` | `DateTime` | NOT NULL, default `utcnow` | Creation timestamp |

**Unique constraint:** `(volume_id, full_path)`

### `ItemTranslation` (table: `item_translations`)

| Column | Type | Constraints | Meaning |
|--------|------|-------------|---------|
| `id` | `String(36)` | PK, default `uuid4()` | Translation UUID |
| `item_id` | `String(36)` | FK `file_items.id`, NOT NULL | Source item |
| `model_type` | `String(100)` | NOT NULL | Model name used for translation |
| `qa_round` | `Integer` | NOT NULL, default `0` | QA round number (0 = initial translation) |
| `content` | `LargeBinary` | NOT NULL | `zlib`-compressed translated content bytes |
| `status` | `Boolean` | NOT NULL, default `True` | Active/inactive flag |
| `last_translation_start` | `DateTime` | NULLABLE | Last translation start time |
| `last_translation_end` | `DateTime` | NULLABLE | Last translation end time |
| `qa_model` | `String(100)` | NULLABLE | QA model name |

**Unique constraint:** `(item_id, model_type, qa_round)`

### `TaskDefinition` (table: `task_definitions`)

| Column | Type | Constraints | Meaning |
|--------|------|-------------|---------|
| `id` | `String(36)` | PK, default `uuid4()` | Task UUID |
| `config_name` | `String(100)` | NOT NULL, UNIQUE | Display name (unique) |
| `config_type` | `String(20)` | NOT NULL, CHECK `IN ('Glossary', 'Translation', 'QA')` | Task type |
| `base_url` | `String(255)` | NOT NULL, default `http://localhost:8080/v1` | LLM API base URL |
| `api_key` | `String(255)` | NOT NULL, default `not-needed` | LLM API key |
| `model` | `String(100)` | NOT NULL, default `default` | LLM model name |
| `max_tokens` | `Integer` | NOT NULL, default `8192` | Max output tokens |
| `temperature` | `Float` | NULLABLE | Sampling temperature |
| `top_p` | `Float` | NULLABLE | Nucleus sampling top_p |
| `min_p` | `Float` | NULLABLE | Minimum probability filter |
| `top_k` | `Integer` | NULLABLE | Top-k sampling |
| `presence_penalty` | `Float` | NULLABLE | Presence penalty |
| `frequency_penalty` | `Float` | NULLABLE | Frequency penalty |
| `repetition_penalty` | `Float` | NULLABLE | Repetition penalty |
| `chunk_size` | `Integer` | NOT NULL, default `12` | Paragraphs per LLM chunk |
| `history` | `Integer` | NULLABLE, default `5` | History context rounds |
| `use_mini_glossary` | `Boolean` | NULLABLE, default `True` | Use mini-glossary per chunk |
| `threads` | `Integer` | NULLABLE, default `1` | Worker threads (QA jobs) |
| `synchronize_quotes` | `Boolean` | NULLABLE, default `True` | Sync quotes in translation |
| `traditional_chinese` | `Boolean` | NULLABLE, default `True` | Convert to Traditional Chinese |
| `model_type` | `String(100)` | NULLABLE | Model type label |
| `retry_attempts` | `Integer` | NOT NULL, default `2` | LLM retry count |
| `override_system_prompt` | `Text` | NULLABLE | Custom system prompt |
| `is_default` | `Boolean` | NOT NULL, default `False` | Default config flag |
| `created_at` | `DateTime` | NOT NULL, default `utcnow` | Creation timestamp |
| `updated_at` | `DateTime` | NOT NULL, default `utcnow`, onupdate | Last update timestamp |

---

## Database (`database.py`)

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `get_engine()` | None | `Engine` | Creates engine with WAL mode, `timeout=30.0` |
| `_get_thread_engine()` | None | `Engine` | Thread-local engine (lazy init) |
| `_get_thread_session_factory()` | None | `sessionmaker` | Thread-local session factory |
| `get_session()` | None | ContextManager[Session] | Thread-safe session context manager; commits on success, rolls back on error |
| `init_db()` | None | None | Creates all tables via `Base.metadata.create_all()` |
| `close_db()` | None | None | Disposes thread-local engine |

**Module-level:**
- `DB_PATH`: `str` — DB file path from `BABELCITY_DB` env var or `babelcity.db`
- `Base`: `declarative_base` — SQLAlchemy base class

---

## LLM Handler (`llm_handler.py`)

### `ask_llm`

Call LLM API with streaming. Returns text response.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | — | LLM API base URL |
| `api_key` | `str` | — | API key |
| `model` | `str` | — | Model name |
| `system_prompt` | `str` | — | System message |
| `user_prompt` | `str` | — | User message |
| `max_tokens` | `int` | `8192` | Max output tokens |
| `temperature` | `float` | `1.0` | Sampling temperature |
| `top_p` | `float` | `0.92` | Nucleus sampling |
| `min_p` | `float` | `0.05` | Min probability (extra_body) |
| `repetition_penalty` | `float` | `1.04` | Repetition penalty (extra_body) |
| `frequency_penalty` | `float` | `0.05` | Frequency penalty |
| `presence_penalty` | `float` | `0.0` | Presence penalty (0 if `is_json`) |
| `top_k` | `int \| None` | `None` | Top-k sampling (extra_body) |
| `is_json` | `bool` | `False` | Set presence_penalty to 0 |
| `verbose` | `bool` | `False` | Print full response |

**Returns:** `str` — LLM text response (think tags removed)

**Metrics:** Logs `prefill_tps` (prompt_tokens / time to first chunk) and `gen_tps` (completion_tokens / time from first chunk to end). Falls back to non-streaming on error.

### `ask_llm_json`

Call LLM and extract JSON response. Retries on failure.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | — | LLM API base URL |
| `api_key` | `str` | — | API key |
| `model` | `str` | — | Model name |
| `system_prompt` | `str` | — | System message |
| `user_prompt` | `str` | — | User message |
| `max_retries` | `int` | `3` | Retry count |
| `max_tokens` | `int` | `8192` | Max output tokens |
| `temperature` | `float` | `1.0` | Temperature |
| `top_p` | `float` | `0.92` | Top-p |
| `min_p` | `float` | `0.05` | Min-p |
| `repetition_penalty` | `float` | `1.04` | Repetition penalty |
| `frequency_penalty` | `float` | `0.05` | Frequency penalty |
| `presence_penalty` | `float` | `0.0` | Presence penalty |
| `top_k` | `int \| None` | `None` | Top-k |

**Returns:** `dict` — Parsed JSON, or `{}` on all retries exhausted

### `extract_json`

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Raw LLM output |

**Returns:** `dict \| list` — Extracted JSON object. Strips markdown fences, finds `{}` or `[]` boundaries.

### `remove_think_tags`

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Raw LLM output |

**Returns:** `str` — Text with `<anth>`, `<channel|>`, `<|channel|>thought` tags removed.

### `_create_client`

| Parameter | Type | Description |
|-----------|------|-------------|
| `base_url` | `str` | API base URL |
| `api_key` | `str` | API key |

**Returns:** `OpenAI` client instance.

### `_p`

| Parameter | Type | Description |
|-----------|------|-------------|
| `val` | any | Value to check |
| `default` | any | Default if `val` is `None` |

**Returns:** `val` if not `None`, else `default`.

---

## Text Processor (`text_processor.py`)

### `has_japanese`

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Input text |

**Returns:** `bool` — True if text contains Japanese hiragana/katakana.

### `extract_text_with_ruby`

| Parameter | Type | Description |
|-----------|------|-------------|
| `tag` | `lxml._Element` | XML element containing ruby tags |

**Returns:** `str` — Text with ruby annotations as `base(rt)` format.

### `parse_xml`

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `str \| bytes` | XHTML content |

**Returns:** `lxml._Element` — Parsed XML tree (recover mode).

### `serialize_xml`

| Parameter | Type | Description |
|-----------|------|-------------|
| `tree` | `lxml._Element` | XML tree |

**Returns:** `bytes` — Serialized XML with declaration and optional doctype.

### `load_dictionary`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dict_path` | `str \| None` | `None` | Path to `=>`-formatted dict file |
| `pre_translated_text` | `str \| None` | `None` | Pre-translated text with `#` comments |

**Returns:** `dict[str, str]` — Merged dictionary (`jp_name` → `zh_name`).

### `build_mini_glossary`

| Parameter | Type | Description |
|-----------|------|-------------|
| `jp_texts` | `str \| list[str]` | Japanese text(s) for current chunk |
| `global_glossary` | `dict` | Full project glossary |
| `chapter_abbrevs` | `dict \| None` | Chapter abbreviation map |

**Returns:** `dict` — Subset of glossary containing only terms present in `jp_texts`.

### `sync_quotes`

| Parameter | Type | Description |
|-----------|------|-------------|
| `trans_text` | `str` | Translated text |
| `source_text` | `str` | Source text (quote reference) |

**Returns:** `str` — Translated text with quotes synchronized to source.

### `finalize_text`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | — | Translated text |
| `source_text` | `str \| None` | `None` | Source text for quote sync |
| `to_traditional` | `bool` | `True` | Convert to Traditional Chinese |

**Returns:** `str` — Finalized text (quotes synced, Traditional Chinese applied).

### `chunk_paragraphs`

| Parameter | Type | Description |
|-----------|------|-------------|
| `paragraphs` | `list[str]` | List of paragraphs |
| `chunk_size` | `int` | Max paragraphs per chunk |

**Returns:** `list[list[str]]` — Chunked paragraphs.

---

## Translation Processor (`translation_processor.py`)

### `system_prompt_header`

| Parameter | Type | Description |
|-----------|------|-------------|
| `is_single` | `bool` | Single-line vs multi-line mode |

**Returns:** `str` — System prompt header with numbered rules.

### `translate_single_line`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `jp_text` | `str` | — | Japanese text to translate |
| `current_glossary` | `dict` | — | Glossary for this chunk |
| `chapter_abbrevs` | `dict` | — | Chapter abbreviation map |
| `llm_config` | `dict` | — | LLM config (base_url, api_key, model, etc.) |
| `history_context` | `str` | `""` | Previous translation context |

**Returns:** `str \| None` — Translated text.

### `translate_chunk`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `jp_texts` | `list[str]` | — | Japanese paragraphs to translate |
| `current_glossary` | `dict` | — | Glossary for this chunk |
| `chapter_abbrevs` | `dict` | — | Chapter abbreviation map |
| `llm_config` | `dict` | — | LLM config dict |
| `history_context` | `str` | `""` | Previous translation context |

**Returns:** `list[str] \| None` — Translated paragraphs.

### `apply_translations_to_chunk`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunk` | `list[lxml._Element]` | — | XML elements to update |
| `zh_batch` | `list[str] \| None` | — | Translated texts |
| `local_heading_map` | `dict \| None` | `None` | Heading translation map |

**Returns:** `None` — Mutates chunk elements in place.

### `process_document`

Translate a full chapter document.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | — | Chapter XHTML content |
| `glossary` | `dict` | — | Project glossary |
| `llm_config` | `dict` | — | LLM config dict |
| `resume` | `bool` | `False` | Resume from existing translation |

**Returns:** `tuple[bytes \| None, dict]` — `(serialized_xml_bytes, heading_map)`.

### `translate_toc_content`

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `str` | TOC XHTML content |
| `chunk_size` | `int` | Paragraphs per chunk |
| `heading_map` | `dict` | Pre-translated headings |
| `glossary` | `dict` | Project glossary |
| `llm_config` | `dict` | LLM config |

**Returns:** `bytes` — Translated TOC XML.

### `process_toc`

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `str` | TOC XHTML content |
| `chunk_size` | `int` | Paragraphs per chunk |
| `heading_map` | `dict` | Pre-translated headings |
| `glossary` | `dict` | Project glossary |
| `llm_config` | `dict` | LLM config |

**Returns:** `bytes` — Translated TOC XML. Calls `translate_toc_content`.

---

## QA Processor (`qa_processor.py`)

### `process_qa_document`

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `str` | Translated chapter XHTML |
| `glossary` | `dict` | Project glossary |
| `llm_config` | `dict` | LLM config dict |

**Returns:** `tuple[bytes \| None, dict]` — `(serialized_xml_bytes, heading_map)`.

### `run_qa_on_chapters`

| Parameter | Type | Description |
|-----------|------|-------------|
| `chapter_items` | `list[tuple[str, bytes]]` | List of `(item_id, compressed_content)` |
| `glossary` | `dict` | Project glossary |
| `qa_config` | `dict` | QA LLM config |
| `threads` | `int` | Number of worker threads |

**Returns:** `list[tuple[str, bytes \| None, dict]]` — List of `(item_id, modified_xml, heading_map)`.

Uses `ThreadPoolExecutor` when `threads > 1`.

---

## Glossary Processor (`glossary_processor.py`)

### `build_system_prompt`

| Parameter | Type | Description |
|-----------|------|-------------|
| `existing_glossary` | `dict` | Current glossary for context |
| `pre_translated` | `dict \| None` | Pre-translated terms |

**Returns:** `str` — System prompt for entity extraction.

### `build_user_prompt`

| Parameter | Type | Description |
|-----------|------|-------------|
| `text_chunk` | `str` | Japanese text to scan |

**Returns:** `str` — User prompt with text chunk.

### `scan_for_entities`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text_chunk` | `str` | — | Japanese text to scan |
| `llm_config` | `dict` | — | LLM config dict |
| `existing_glossary` | `dict \| None` | `None` | Existing glossary for context |
| `pre_translated` | `dict \| None` | `None` | Pre-translated terms |

**Returns:** `dict` — Extracted entities: `{jp_name: {translated_name, type, gender}}`.

### `filter_glossary_terms`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `terms` | `dict` | — | Extracted terms |
| `source_language` | `str` | `"ja"` | Source language code |

**Returns:** `dict` — Filtered terms (only those matching source language).

### `merge_glossary`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `existing` | `dict` | — | Existing glossary |
| `new_terms` | `dict` | — | New extracted terms |
| `pre_translated` | `dict \| None` | `None` | Pre-translated fallback |

**Returns:** `dict` — Merged glossary. New terms override existing; pre_translated fills missing entries.

---

## EPUB Handler (`epub_handler.py`)

### `_parse_xml_bytes`

| Parameter | Type | Description |
|-----------|------|-------------|
| `xml_bytes` | `bytes` | Raw XML bytes |

**Returns:** `lxml._Element` — Parsed XML tree.

### `_resolve_href`

| Parameter | Type | Description |
|-----------|------|-------------|
| `base_href` | `str` | Base path |
| `href` | `str` | Relative href |

**Returns:** `str` — Resolved absolute path.

### `get_epub_metadata`

| Parameter | Type | Description |
|-----------|------|-------------|
| `zip_file` | `zipfile.ZipFile` | Open EPUB file |

**Returns:** `dict` — `{title, author, language, manifest, spine, cover_id, nav_id}`.

### `select_nav_file`

| Parameter | Type | Description |
|-----------|------|-------------|
| `manifest` | `dict` | EPUB manifest |

**Returns:** `str \| None` — Nav file path (NCX or HTML nav).

### `classify_item`

| Parameter | Type | Description |
|-----------|------|-------------|
| `item_id` | `str` | EPUB item ID |
| `info` | `dict` | Item metadata (media_type, etc.) |
| `spine` | `list` | EPUB spine order |
| `nav_id` | `str \| None` | Nav file ID |

**Returns:** `str` — `"Chapter"`, `"Nav"`, or `"Resource"`.

### `import_epub`

| Parameter | Type | Description |
|-----------|------|-------------|
| `volume_id` | `str` | Target volume UUID |
| `file_bytes` | `bytes` | EPUB file bytes |
| `session` | `Session` | SQLAlchemy session |

**Returns:** `None` — Imports all items into `FileItem` table; content is `zlib`-compressed.

### `export_epub`

| Parameter | Type | Description |
|-----------|------|-------------|
| `volume_id` | `str` | Source volume UUID |
| `model_type` | `str` | Model type for translation lookup |
| `qa_round` | `int` | QA round number |
| `session` | `Session` | SQLAlchemy session |

**Returns:** `bytes` — Exported EPUB file bytes. Uses `ItemTranslation` content when available.

---

## Job Queue (`job_queue.py`)

### `Job` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Job UUID |
| `job_type` | `str` | `"Glossary"`, `"Translation"`, `"QA"` |
| `project_id` | `str` | Project UUID |
| `project_name` | `str` | Project name |
| `volume_id` | `str` | Volume UUID |
| `volume_number` | `str` | Volume number |
| `config_id` | `str` | Task definition UUID |
| `params` | `dict` | Extra job parameters |
| `status` | `JobStatus` | Enum: `"Pending"`, `"Running"`, `"Completed"`, `"Failed"` |
| `progress_completed` | `int` | Completed count |
| `progress_total` | `int` | Total count |
| `created_at` | `datetime` | Creation time |
| `result_message` | `str` | Result/error message |

### `JobQueue` class

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `add_job` | `job_type`, `project_id`, `project_name`, `volume_id`, `volume_number`, `config_id`, `params` | `Job` | Adds job to queue |
| `get_all_jobs` | None | `list[Job]` | Returns all jobs (running, pending, completed) |
| `get_job` | `job_id: str` | `Job \| None` | Get job by ID |
| `update_progress` | `job_id`, `completed`, `total` | None | Update job progress |
| `update_status` | `job_id`, `status`, `message` | None | Update job status + message |
| `start` | `daemon: bool = True` | None | Start background worker thread |
| `pause` | None | None | Pause worker (stop running job, move to top of pending) |
| `remove_job` | `job_id` | None | Remove job from pending list |
| `clear_pending` | None | None | Clear all pending jobs |
| `clear_failed` | None | None | Remove failed jobs from completed list |
| `clear_completed` | None | None | Clear all completed jobs |
| `move_up` | `job_id` | None | Move job up in pending queue |
| `move_down` | `job_id` | None | Move job down in pending queue |
| `move_to_top` | `job_id` | None | Move job to top of pending queue |
| `move_to_bottom` | `job_id` | None | Move job to bottom of pending queue |
| `delete_job` | `job_id` | `bool` | Delete job (running jobs cannot be deleted) |
| `repeat_job` | `job_id` | `Job \| None` | Create new job with same params, status=pending |

**Module-level:** `job_queue = JobQueue()` — Singleton instance.

---

## Job Executors (`job_executors.py`)

### `execute_job`

Routes job to correct executor based on `job.job_type`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `job` | `Job` | Job object from queue |
| `progress_callback` | `Callable[[int, int], None]` | `(completed, total)` callback |

**Returns:** `None`

### `execute_glossary_job`

| Parameter | Type | Description |
|-----------|------|-------------|
| `job` | `Job` | Glossary job |
| `progress_callback` | `Callable[[int, int], None]` | Progress callback |

**Returns:** `None` — Scans chapters for entities, merges glossary, saves to `Project.glossary`.

### `execute_translation_job`

| Parameter | Type | Description |
|-----------|------|-------------|
| `job` | `Job` | Translation job |
| `progress_callback` | `Callable[[int, int], None]` | Progress callback |

**Returns:** `None` — Translates chapters + Nav, stores `ItemTranslation` (qa_round=0).

### `execute_qa_job`

| Parameter | Type | Description |
|-----------|------|-------------|
| `job` | `Job` | QA job |
| `progress_callback` | `Callable[[int, int], None]` | Progress callback |

**Returns:** `None` — Multi-pass QA with `ThreadPoolExecutor` (respects `config.threads`). Reads `job.params["start_version"]` and `["num_passes"]`.

---

## WebSocket (`ws.py`)

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `job_websocket` | `websocket: WebSocket` | `None` (async) | WebSocket endpoint at `/ws/jobs`; sends job list on connect |
| `_send_job_list` | `ws: WebSocket` | `None` (async) | Sends current job list as JSON |
| `broadcast_progress` | `job_id: str`, `current: int`, `total: int` | `None` (async) | Broadcasts progress update to all clients |
| `broadcast_status` | `job_id: str`, `status: str` | `None` (async) | Broadcasts status change to all clients |

**Module-level:** `connected_clients: list` — Active WebSocket connections.

---

## API — Projects (`api/projects.py`)

### Pydantic Models

**`ProjectCreate`**: `project_type: str`, `project_name: str`, `source_title: str`, `source_language: str = "ja"`, `target_language: str = "zh"`, `glossary: dict | None = None`

**`ProjectUpdate`**: `project_name: str`, `source_title: str`, `source_language: str`, `target_language: str` — all optional

**`VolumeCreate`**: `volume_number: str`, `source_volume_title: str | None = None`, `target_volume_title: str | None = None`

**`VolumeUpdate`**: `source_volume_title: str | None`, `target_volume_title: str | None`

### Endpoints

| Method | Path | Parameters | Returns |
|--------|------|-----------|---------|
| `POST` | `/projects` | `data: ProjectCreate` | Created project |
| `GET` | `/projects` | None | `list[Project]` |
| `GET` | `/projects/{project_id}` | `project_id: str` | Project with volumes |
| `PUT` | `/projects/{project_id}` | `project_id: str`, `data: ProjectUpdate` | Updated project |
| `DELETE` | `/projects/{project_id}` | `project_id: str` | `{"deleted": true}` |
| `POST` | `/projects/{project_id}/volumes` | `project_id: str`, `data: VolumeCreate` | Created volume |
| `GET` | `/projects/{project_id}/volumes` | `project_id: str` | `list[Volume]` |
| `PUT` | `/projects/{project_id}/volumes/{volume_number}` | `volume_number: str`, `data: VolumeUpdate` | Updated volume |
| `DELETE` | `/projects/{project_id}/volumes/{volume_number}` | `volume_id: str`, `data: VolumeUpdate` | Updated volume |
| `DELETE` | `/projects/{project_id}/volumes/{volume_number}` | `volume_number: str` | `{"deleted": true}` |
| `POST` | `/projects/{project_id}/volumes/{volume_number}/import` | `volume_number: str`, `file: UploadFile` | `{"status": "ok"}` |
| `GET` | `/projects/{project_id}/volumes/{volume_number}/export` | `volume_number: str`, `model_type: str`, `qa_round: int = 0` | EPUB file |

---

## API — Tasks (`api/tasks.py`)

### Pydantic Models

**`TaskDefinitionCreate`**: `config_name: str`, `config_type: str` (must be `'Glossary'`, `'Translation'` or `'QA'`), `base_url: str`, `api_key: str`, `model: str`, `max_tokens: int`, `temperature: float | None`, `top_p: float | None`, `min_p: float | None`, `top_k: int | None`, `presence_penalty: float | None`, `frequency_penalty: float | None`, `repetition_penalty: float | None`, `chunk_size: int`, `history: int | None`, `use_mini_glossary: bool | None`, `threads: int | None`, `synchronize_quotes: bool | None`, `traditional_chinese: bool | None`, `model_type: str | None`, `retry_attempts: int`, `override_system_prompt: str | None`

**`TaskDefinitionUpdate`**: Same fields — all optional.

### Endpoints

| Method | Path | Parameters | Returns |
|--------|------|-----------|---------|
| `POST` | `/tasks` | `data: TaskDefinitionCreate` | Created task |
| `GET` | `/tasks` | `task_type: str | None` | `list[Task]` |
| `GET` | `/tasks/{task_id}` | `task_id: str` | Task |
| `PUT` | `/tasks/{task_id}` | `task_id: str`, `data: TaskDefinitionUpdate` | Updated task |
| `DELETE` | `/tasks/{task_id}` | `task_id: str` | `{"deleted": true}` |
| `POST` | `/tasks/{task_id}/default` | `task_id: str` | `{"message": "ok"}` |

---

## API — Jobs (`api/jobs.py`)

### Pydantic Models

**`GlossaryJobCreate`**: `project_id: str`, `volume_number: str`, `task_id: str`, `resume: bool = True`, `add_only: bool = False`, `pre_translated_terms: str | None = None`

**`TranslationJobCreate`**: `project_id: str`, `volume_number: str`, `task_id: str`, `resume: bool = True`

**`QAJobCreate`**: `project_id: str`, `volume_number: str`, `task_id: str`, `start_version: int = 0`, `num_passes: int = 1`

**`JobMove`**: `direction: str` — `"up"`, `"down"`, `"top"`, or `"bottom"`

### Endpoints

| Method | Path | Parameters | Returns |
|--------|------|-----------|---------|
| `GET` | `/jobs` | `status: str | None` | `list[Job]` |
| `POST` | `/jobs/glossary` | `data: GlossaryJobCreate` | Created job |
| `POST` | `/jobs/translation` | `data: TranslationJobCreate` | Created job |
| `POST` | `/jobs/qa` | `data: QAJobCreate` | Created job |
| `POST` | `/jobs/{job_id}/move` | `job_id: str`, `data: JobMove` | `{"moved": true}` |
| `DELETE` | `/jobs/{job_id}` | `job_id: str` | `{"deleted": true}` |
| `POST` | `/jobs/{job_id}/repeat` | `job_id: str` | Repeated job |
| `DELETE` | `/jobs` | `status: str = "pending"` | Remove all pending or completed jobs |
| `POST` | `/jobs/start` | None | Start job queue worker |
| `POST` | `/jobs/pause` | None | Pause job queue |

---

## API — Glossary (`api/glossary.py`)

### Pydantic Models

**`GlossaryUpdate`**: `glossary: dict[str, Any]`

### Endpoints

| Method | Path | Parameters | Returns |
|--------|------|-----------|---------|
| `GET` | `/projects/{project_id}/glossary` | `project_id: str` | `{project_id, glossary}` |
| `PUT` | `/projects/{project_id}/glossary` | `project_id: str`, `data: GlossaryUpdate` | `{message}` |

---

## API — Chapters (`api/chapters.py`)

### Endpoints

| Method | Path | Parameters | Returns |
|--------|------|-----------|---------|
| `GET` | `/volumes/{volume_id}/nav` | `volume_id: str`, `model_type: str | None`, `qa_round: int = 0` | Nav HTML (decompressed, resource paths rewritten) |
| `GET` | `/volumes/{volume_id}/toc` | `volume_id: str` | TOC: spine-based chapter list with Nav name mapping |
| `GET` | `/volumes/{volume_id}/items/{item_path:path}` | `volume_id: str`, `item_path: str`, `model_type: str | None`, `qa_round: int = 0` | Chapter content (decompressed, resource paths rewritten) |
| `GET` | `/volumes/{volume_id}/items/{item_id}/meta` | `volume_id: str`, `item_id: str` | Chapter metadata + translations list |
| `GET` | `/volumes/{volume_id}/available_translations` | `volume_id: str` | `{available: {model_type: [qa_rounds]}}` |
| `PATCH` | `/volumes/{volume_id}/items/{item_id}/obsolete` | `volume_id: str`, `item_id: str` | `{obsolete: bool}` |
| `PATCH` | `/volumes/{volume_id}/items/{item_id}/translations/{translation_id}/status` | `volume_id: str`, `item_id: str`, `translation_id: str` | `{status: bool}` |

---

## API — Resources (`api/resources.py`)

### Endpoints

| Method | Path | Parameters | Returns |
|--------|------|-----------|---------|
| `GET` | `/resources/volumes/{volume_id}/items/{path:path}` | `volume_id: str`, `path: str` | Resource bytes (CSS, images, etc.) |

`_try_decompress()` helper handles `zlib`-compressed content with `charset=utf-8` media types.

---

## Main Entry Point (`main.py`)

| Function | Description |
|----------|-------------|
| `lifespan` | Async context manager: calls `init_db()` on startup |
| `_mount_static(dist)` | Mounts `StaticFiles` at `/` if `dist` is a directory |
| `cli` | Typer CLI with `--web-dist`, `--web-host`, `--web-port` options |

**CLI options:**
- `--web-dist PATH`: Override static files directory (default: `web/dist/`)
- `--web-host HOST`: Override bind host (default: `127.0.0.1`)
- `--web-port PORT`: Override bind port (default: `8000`)

**App:** FastAPI with CORS middleware. Mounts static files from `web/dist/` if present. Routes: `/api/v1` (projects, tasks, jobs, glossary, resources, chapters), `/ws` (WebSocket).

---

## Key Data Flow

1. **EPUB Import:** `projects.py` → `epub_handler.import_epub()` → `FileItem` rows (zlib-compressed)
2. **Glossary Scan:** `job_executors.execute_glossary_job()` → `glossary_processor.scan_for_entities()` → `ask_llm_json()` → `merge_glossary()` → `Project.glossary`
3. **Translation:** `job_executors.execute_translation_job()` → `translation_processor.process_document()` → `ask_llm()` → `ItemTranslation` (qa_round=0)
4. **QA:** `job_executors.execute_qa_job()` → `qa_processor.process_qa_document()` → `ask_llm_json()` → `ItemTranslation` (qa_round incremented)
5. **Chapter Serving:** `chapters.py` → decompress zlib → rewrite resource paths → serve HTML
6. **EPUB Export:** `projects.py` → `epub_handler.export_epub()` → uses `ItemTranslation` content when available

## Content Storage

- `FileItem.content`: `zlib.compress(bytes)` — stored as `LargeBinary`
- `ItemTranslation.content`: `zlib.compress(bytes)` — stored as `LargeBinary`
- `Project.glossary`: `dict` — stored as `JSON` column (SQLAlchemy returns `dict`)
- `serialize_xml()` returns `bytes` (not `str`) — `etree.tostring(..., encoding='utf-8')`