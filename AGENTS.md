# Babel City — Agent Guide

## Project Overview

Babel City is a local Web Novel & EPUB Translation Organizer. It provides a React + FastAPI web UI for managing translation projects, configuring LLM tasks, and running background translation/QA jobs.

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, SQLite (WAL mode, `timeout=30.0`)
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS 3, AG-Grid React, React Query (TanStack Query v5), Lucide React
- **Real-time**: WebSocket (`/ws/jobs`) for job progress broadcasts
- **EPUB**: `zipfile` + `lxml` (no `ebooklib`)
- **Translation**: `opencc-python-reimplemented` for Traditional Chinese conversion

## Project Structure

```
babelcity/
├── babelcity/              # FastAPI backend package
│   ├── main.py             # FastAPI app, CORS, static files, lifespan
│   ├── api/                # API route modules
│   │   ├── projects.py     # CRUD for projects, volumes, EPUB import/export
│   │   ├── tasks.py        # CRUD for task definitions (Glossary/Translation/QA)
│   │   ├── jobs.py         # Job queue CRUD, start/pause, reorder, repeat
│   │   ├── glossary.py     # Glossary read/write per project
│   │   ├── chapters.py     # Chapter/Nav/TOC serving with resource path rewriting
│   │   └── resources.py    # Serve EPUB resources (CSS/images) for IFrame
│   ├── ws.py               # WebSocket endpoint for job progress broadcast
│   ├── database.py         # SQLite engine, thread-safe session factory, init/close
│   ├── models.py           # SQLAlchemy ORM models (Project, BookVolume, FileItem, ItemTranslation, TaskDefinition)
│   ├── epub_handler.py     # EPUB parse/import/export
│   ├── llm_handler.py      # LLM API calls (streaming + non-streaming)
│   ├── text_processor.py   # Text utilities (ruby extraction, XML parse/serialize, chunking, glossary)
│   ├── translation_processor.py  # Translation logic (chunk translation, document processing, TOC)
│   ├── qa_processor.py     # QA logic (multi-pass, ThreadPoolExecutor)
│   ├── glossary_processor.py     # Glossary scanning & merging
│   ├── job_queue.py        # In-memory job queue singleton
│   └── job_executors.py    # Background job executors (glossary, translation, QA)
├── web/                    # React + Vite frontend
│   └── src/
│       ├── main.tsx
│       ├── App.tsx         # Conditional rendering (no React Router), React Query provider
│       ├── components/     # ConfirmDialog, ErrorToast, Navbar, etc.
│       ├── pages/          # ProjectsPage, TasksPage, JobsPage
│       ├── hooks/          # useJobWebSocket
│       ├── services/       # api.ts — Axios client, base URL /api/v1
│       ├── types/          # TypeScript interfaces
│       └── utils/
├── requirements.txt
├── .gitignore
└── requirements.md
```

## Key Conventions

### Backend
- All API endpoints are under `/api/v1/`
- UUID primary keys: `default=lambda: str(uuid.uuid4())`
- Content storage: `FileItem.content` and `ItemTranslation.content` are `zlib`-compressed `LargeBinary`
- `Project.glossary` is stored as a `JSON` column (SQLAlchemy returns `dict`)
- Database sessions are thread-safe via thread-local engine; use `database.get_session()` context manager
- SQLite uses WAL mode with `timeout=30.0`
- `serialize_xml()` returns `bytes` (not `str`)
- Job queue is a singleton: `job_queue = JobQueue()` in `job_queue.py`
- `JobStatus` enum values are capitalized strings: `"Pending"`, `"Running"`, `"Completed"`, `"Failed"`
- Chapter HTML resource paths are rewritten inline (Approach B): relative `href`/`src` replaced with absolute API paths

### Frontend
- **No React Router** — `App.tsx` uses conditional rendering based on active tab
- **Server state**: React Query (`useQuery`, `useMutation`) for all API data
- **UI state**: `useState`/`useContext` for modals, theme, selected items
- **WebSocket**: `useJobWebSocket()` hook auto-reconnects every 3s, invalidates React Query cache
- **Theme**: Tailwind `darkMode: 'class'`; persisted to `localStorage` under `babelcity-theme`
- **Tables**: AG-Grid v32 for GlossaryEditor; use `onCellEditStopped` (not `onCellChanged`)
- **`useQuery` pattern**: `queryFn` must be zero-arg — wrap API calls with `() => apiCall()`
- **Error handling**: Use `ErrorToast` component, never `alert()`
- **Vite dev proxy**: `/api` and `/ws` proxied to backend on port 8000

### Data Models
- **Project**: `project_type` CHECK `IN ('Light Novel', 'Web Novel')`; Web Novel always has volume "1"
- **BookVolume**: unique constraint on `(project_id, volume_number)`
- **FileItem**: `item_type` CHECK `IN ('Chapter', 'Nav', 'Resource')`; unique on `(volume_id, full_path)`
- **ItemTranslation**: unique on `(item_id, model_type, qa_round)`; `qa_round=0` is initial translation
- **TaskDefinition**: `config_type` CHECK `IN ('Glossary', 'Translation', 'QA')`; `config_name` is UNIQUE

## Development Commands

### Backend
```bash
python3.11 -m venv .venv
./.venv/bin/pip install -r requirements.txt
python -m babelcity.main        # or: python main.py
```

### Frontend
```bash
cd web
npm install
npm run dev                     # dev server with proxy to :8000
npx vite build                  # production build → web/dist/
npx tsc --noEmit                # type check
```

### Testing
- Use a separate temporary database for testing, never the main `babelcity.db`
- EPUB import/export can be verified with a sample `.epub` file

## Important Rules

1. **Never use Reflex** — it was removed entirely. No `state.py`, `rxconfig.py`, `.web/`, or `reflex.lock/`
2. **Preserve existing processor logic** — `epub_handler.py`, `llm_handler.py`, `text_processor.py`, `translation_processor.py`, `qa_processor.py`, `glossary_processor.py` contain battle-tested logic from the PoC. Enhance, don't rewrite.
3. **Japanese-specific logic** — `has_japanese()`, ruby tag handling, Traditional Chinese conversion are enabled by default
4. **OAuth2-ready but not enforced** — endpoints accept optional `current_user` dependency; no auth required currently
5. **`translate_epubs_new.py`** — kept locally as reference, excluded from git via `.gitignore`
6. **Python 3.9+ compatible** — all dependencies must work on Python 3.9+
7. **Confirmation dialogs** — all destructive actions (delete project/volume/job) must use `ConfirmDialog`
8. **Sorted dropdowns and tables** — all `<select>` elements and table rows must be sorted
9. **Obsolete items excluded** — glossary scanning, translation, and QA jobs must skip `FileItem.obsolete=True`
10. **Export fallback order** — exact `(model_type, qa_round)` match → `(model_type, qa_round=0)` → original `FileItem` content
11. **This project uses AG Grid v32.2+ JS Theming API (theme={themeObject}). Do NOT use or suggest legacy ag-grid/styles/*.css imports or ag-theme-* wrapper classes.**
12. **If you have run python -m babelcity.main to start the server for testing, please stop it after testing.**

## API Quick Reference

| Area | Base Path | Key Endpoints |
|------|-----------|---------------|
| Projects | `/api/v1/projects` | CRUD, `/volumes`, `/import`, `/export`, `/glossary` |
| Tasks | `/api/v1/tasks` | CRUD, `/default`, filter by `?task_type=` |
| Jobs | `/api/v1/jobs` | CRUD, `/glossary`, `/translation`, `/qa`, `/start`, `/pause`, `/move`, `/repeat` |
| Chapters | `/api/v1/chapters` | `/volumes/{id}/nav`, `/toc`, `/items/{path}`, `/items/{id}/meta`, `/obsolete`, `/status` |
| Resources | `/api/v1/resources` | `/volumes/{id}/items/{path}` — CSS/images for IFrame |
| WebSocket | `/ws/jobs` | Pushes `progress`, `completed`, `job_list` events |

## Implementation Status

All phases (1-12) are complete. The application is production-ready with:
- Full backend API with all endpoints
- Complete frontend with Projects/Tasks/Jobs tabs
- Book Viewer with TOC, IFrame, chapter navigation, keyboard shortcuts
- Real-time job progress via WebSocket
- Dark/light theme with persistence
- Error toast notifications
- Confirmation dialogs for destructive actions
- LLM streaming with token metrics
- Full translation/QA job execution with resume, multi-threading, Nav updates