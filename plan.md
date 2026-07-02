# Babel City - Implementation Plan

## Architecture

```
babelcity/
├── babelcity/          # FastAPI backend
│   ├── __init__.py
│   ├── main.py         # FastAPI app, CORS, static file serving, lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   ├── projects.py   # CRUD for projects, volumes, EPUB import/export
│   │   ├── tasks.py      # CRUD for Glossary/Translation/QA task definitions
│   │   ├── jobs.py       # Job queue CRUD, start/pause, reorder
│   │   ├── glossary.py   # Glossary read/write per project
│   │   └── resources.py  # Serve EPUB resources (CSS/images) for IFrame
│   ├── ws.py             # WebSocket endpoint for job progress
│   ├── database.py       # SQLite engine, session factory, init
│   ├── models.py         # SQLAlchemy ORM models
│   ├── epub_handler.py   # EPUB parse/import/export (keep as-is)
│   ├── llm_handler.py    # LLM API calls (keep as-is)
│   ├── text_processor.py # Text utilities (keep as-is)
│   ├── translation_processor.py  # Translation logic (keep as-is)
│   ├── qa_processor.py   # QA logic (keep as-is)
│   ├── glossary_processor.py     # Glossary scanning (keep as-is)
│   ├── job_queue.py      # In-memory job queue (keep as-is)
│   └── job_executors.py  # Background job executors (keep as-is)
├── web/                  # React + Vite frontend
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── services/     # API client, WebSocket client
│       ├── types/        # TypeScript interfaces
│       └── utils/
├── requirements.txt
├── .gitignore
└── requirements.md
```

## Tech Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, SQLite (WAL mode, `timeout=30.0`)
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS 3, Lucide React, AG-Grid React, React Query (TanStack Query)
- **Real-time**: WebSocket (via `fastapi-websockets`) for job progress
- **EPUB**: `zipfile` + `lxml` (no `ebooklib`)
- **Translation**: `opencc-python-reimplemented` for Traditional Chinese conversion

## Removed (Reflex)
- `state.py`, `babelcity.py`, `rxconfig.py`, `reflex.lock/`, `.web/`
- Reflex dependency removed from `requirements.txt`

## Dependencies

### Backend (`requirements.txt`)
```
fastapi==0.115.*
uvicorn[standard]==0.34.*
sqlalchemy==2.0.*
pydantic==2.*
python-multipart==0.0.*
websockets==14.*
opencc-python-reimplemented==0.1.*
lxml==5.*
beautifulsoup4==4.*
```

### Frontend (`web/package.json`)
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@tanstack/react-query": "^5.60.0",
    "@tanstack/react-table": "^8.20.0",
    "ag-grid-react": "^32.3.0",
    "ag-grid-community": "^32.3.0",
    "lucide-react": "^0.460.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^3.4.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0"
  }
}
```

## API Design

### Auth (OAuth2-ready)
- All endpoints under `/api/v1/`
- Current: no auth required
- Future: add `OAuth2PasswordBearer` dependency to each route; token validation via `get_current_user` helper in `api/deps.py`
- Cookie-based session or Bearer token — either works; Bearer is simpler for React Query

### Projects (`/api/v1/projects`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | List all projects |
| POST | `/projects` | Create a new project |
| GET | `/projects/{project_id}` | Get project details with volumes |
| PUT | `/projects/{project_id}` | Update project metadata |
| DELETE | `/projects/{project_id}` | Delete project (with confirmation) |
| POST | `/projects/{project_id}/volumes` | Add volume (Light Novel only) |
| DELETE | `/projects/{project_id}/volumes/{volume_number}` | Remove volume |
| POST | `/projects/{project_id}/volumes/{volume_number}/import` | Import/update EPUB (multipart) |
| GET | `/projects/{project_id}/volumes/{volume_number}/export` | Export EPUB (download) |
| GET | `/projects/{project_id}/glossary` | Get glossary JSON |
| PUT | `/projects/{project_id}/glossary` | Save glossary JSON |

### Task Definitions (`/api/v1/tasks`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks` | List all task definitions (filter by `?type=glossary|translation|qa`) |
| POST | `/tasks` | Create task definition |
| PUT | `/tasks/{task_id}` | Update task definition |
| DELETE | `/tasks/{task_id}` | Delete task definition |

### Jobs (`/api/v1/jobs`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs` | List all jobs |
| POST | `/jobs/glossary` | Add glossary job |
| POST | `/jobs/translation` | Add translation job |
| POST | `/jobs/qa` | Add QA job |
| POST | `/jobs/start` | Start job queue worker |
| POST | `/jobs/pause` | Pause job queue (stop running job, move to top) |
| DELETE | `/jobs/{job_id}` | Remove a pending/finished job |
| DELETE | `/jobs` | Remove all pending jobs (`?status=pending`) or finished (`?status=completed`) |
| POST | `/jobs/{job_id}/move` | Reorder: `{"direction": "up"|"down"|"top"|"bottom"}` |

### Resources (`/api/v1/resources`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/resources/volumes/{volume_id}/items/{full_path}` | Serve EPUB resource (CSS/image) for IFrame |

### Chapters (`/api/v1/chapters`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/chapters/volumes/{volume_id}/nav` | Get Nav (TOC) content |
| GET | `/chapters/volumes/{volume_id}/items/{item_id}` | Get chapter content |

**Chapter content URL pattern**: `/api/v1/chapters/volumes/{volume_id}/items/{item_id}?model_type={model}&qa_round={round}`
- The `model_type` and `qa_round` query params determine which translation to serve.
- CSS/image resources referenced in the chapter HTML also need `model_type` and `qa_round` in their URLs so the IFrame can resolve them correctly. Two approaches:
  - **A. Rewrite HTML base URL**: Inject a `<base href="...">` tag into the served chapter HTML pointing to `/api/v1/resources/volumes/{volume_id}/?model_type={model}&qa_round={round}`, so relative resource paths resolve correctly.
  - **B. Rewrite resource paths inline**: Replace `href="styles.css"` with `href="/api/v1/resources/volumes/{volume_id}/items/styles.css"` in the served HTML.
  - **Decision**: Approach B is simpler and more reliable. The chapter endpoint rewrites all relative `href`/`src` paths in the HTML to absolute API paths. Pure resources (CSS/images) don't depend on model_type/qa_round since they come from `File_Item` unchanged.

### WebSocket (`/ws/jobs`)
- Connect: `ws://localhost:8000/ws/jobs`
- Server pushes: `{"type": "progress", "job_id": "...", "current": N, "total": M, "status": "running"}`
- Server pushes: `{"type": "completed", "job_id": "...", "status": "completed"}`
- Server pushes: `{"type": "job_list", "jobs": [...]}` (on connect, send current state)

## Frontend Structure

### Pages
1. **Projects** — Project list table, Book Viewer, Project Editor, Glossary Editor
2. **Tasks** — Task definition list, create/edit forms (Glossary/Translation/QA)
3. **Jobs** — Job queue table, create forms (Glossary/Translation/QA), Start/Pause controls

### Components
- `Navbar` — Logo, tab navigation, dark/light toggle
- `ProjectTable` — Projects list with actions
- `BookViewer` — TOC panel + IFrame chapter viewer + metadata bar
- `ProjectEditor` — Form for project metadata + volume management
- `GlossaryEditor` — AG-Grid inline editable table
- `TaskTable` — Task definitions with Edit/Delete
- `TaskForm` — Modal form for Glossary/Translation/QA config
- `JobTable` — Job queue with status, progress, reorder buttons
- `JobForm` — Modal form for Glossary/Translation/QA job
- `ConfirmDialog` — Reusable confirmation modal
- `ErrorToast` — Error notification toast

### State Management
- **Server state**: React Query (`useQuery`, `useMutation`) for all API data
- **UI state**: React `useState`/`useContext` for modals, theme, selected items
- **WebSocket**: Custom hook `useJobWebSocket()` that subscribes to `/ws/jobs` and updates React Query cache on progress events

### Theme
- Tailwind `darkMode: 'class'` in `tailwind.config.js`
- Theme toggle persists to `localStorage` under key `babelcity-theme`
- Provider component `ThemeProvider` sets `<html class="dark">` on mount

## Implementation Phases

### Phase 1: Backend Foundation ✅ DONE
- [x] SQLAlchemy models (`models.py`) — glossary column fixed: Text → JSON
- [x] Database init (`database.py`)
- [x] EPUB handler (`epub_handler.py`)
- [x] LLM handler (`llm_handler.py`)
- [x] Text processor (`text_processor.py`)
- [x] Translation processor (`translation_processor.py`)
- [x] QA processor (`qa_processor.py`)
- [x] Glossary processor (`glossary_processor.py`)
- [x] Job queue (`job_queue.py`) — added singleton `job_queue = JobQueue()`
- [x] Job executors (`job_executors.py`)
- [x] Create `babelcity/main.py` — FastAPI app, CORS, lifespan, static file serving
- [x] Create `babelcity/api/projects.py` — Project/volume/EPUB endpoints, Web Novel auto-creates volume "1"
- [x] Create `babelcity/api/tasks.py` — Task definition endpoints
- [x] Create `babelcity/api/jobs.py` — Job queue endpoints with move/repeat
- [x] Create `babelcity/api/glossary.py` — Glossary endpoints
- [x] Create `babelcity/api/resources.py` — EPUB resource serving
- [x] Create `babelcity/api/chapters.py` — Chapter/Nav serving with resource path rewriting
- [x] Create `babelcity/ws.py` — WebSocket job progress with broadcast helpers
- [x] Update `requirements.txt` (remove Reflex, add FastAPI deps)
- [x] Remove `state.py`, `babelcity.py`, `rxconfig.py`, `reflex.lock/`, `.web/`
- [x] Add `translate_epubs_new.py` to `.gitignore`
- [x] Run backend tests — EPUB import/export verified with `book.epub`; test data cleaned

### Phase 2: Frontend Foundation ✅ DONE
- [x] Init Vite + React + TypeScript in `web/`
- [x] Configure Tailwind CSS, PostCSS with `darkMode: 'class'`
- [x] Install AG-Grid React v32, Lucide React, React Query (TanStack Query v5), Axios
- [x] Create API client (`web/src/services/api.ts`) — Axios-based, base URL `/api/v1`
- [x] Create TypeScript types (`web/src/types/index.ts`) — Project, Volume, TaskDefinition, Job, FileItem, ItemTranslation, ChapterMeta
- [x] Create WebSocket hook (`web/src/hooks/useJobWebSocket.ts`) — auto-reconnect every 3s, invalidates React Query cache on job_list/status_change
- [x] Create `ThemeProvider` — persists to `localStorage` under `babelcity-theme`
- [x] Create `Navbar` — logo, 3 tabs (Projects/Tasks/Jobs), dark/light toggle
- [x] Create `App.tsx` — conditional rendering with React Query provider, no React Router
- [x] Create `ConfirmDialog` component — reusable modal with danger mode
- [x] Create `ProjectsPage` — project list with actions (view, edit, delete, glossary, viewer)
- [x] Create `ProjectEditor` — project metadata form + volume management
- [x] Create `GlossaryEditor` — AG-Grid v32 inline editable table (onCellEditStopped)
- [x] Create `BookViewer` — TOC panel + IFrame chapter viewer + metadata bar
- [x] Create `TasksPage` — task definition list with create/edit/delete, set default
- [x] Create `JobsPage` — job queue with create forms (Glossary/Translation/QA), Start/Pause, reorder, delete
- [x] TypeScript compiles clean (`npx tsc --noEmit` passes)
- [x] Vite production build passes (`npx vite build` → `web/dist/`)
- [x] Backend serves all API routes with 200 OK (`/api/v1/projects`, `/tasks`, `/jobs`, `/glossary`)
- [x] Static files from `web/dist/` served by FastAPI at `/`

### Phase 3: Projects Tab ✅ DONE
- [x] `ProjectsPage` — Project list with actions (view, edit, delete, glossary, viewer)
- [x] `ProjectEditor` — Project metadata form, volume add/remove/rename, EPUB upload via file input, EPUB export
- [x] `GlossaryEditor` — AG-Grid v32 inline editable table with add/delete/save
- [x] `BookViewer` — TOC sidebar + IFrame chapter viewer + metadata bar (model_type, qa_round selectors)
- [x] Chapter content serving with resource path rewriting (Approach B: inline href/src replacement)
- [x] EPUB upload via file input in ProjectEditor + EPUB download via Blob trigger
- [x] EPUB upload with drag-and-drop area, click-to-select fallback, file validation (.epub check)
- [x] BookViewer: chapter navigation (prev/next buttons) with chapter counter
- [x] BookViewer: keyboard shortcuts (ArrowLeft/ArrowRight) for chapter navigation
- [x] Project metadata bar: chapter counter, model_type/qa_round selectors, EPUB download
- [x] EPUB upload progress indicator via drag-and-drop feedback
- [x] TypeScript compiles clean, Vite build passes

### Phase 4: Tasks Tab ✅ DONE
- [x] `TaskTable` — List task definitions (implemented as TasksPage in Phase 2)
- [x] `TaskForm` — Create/edit Glossary/Translation/QA config (implemented in TasksPage)
- [x] Form validation for required fields (Config Name, Model, Base URL required)

### Phase 5: Jobs Tab ✅ DONE
- [x] `JobTable` — Job queue with status, progress bar, reorder buttons (implemented as JobsPage in Phase 2)
- [x] `JobForm` — Create Glossary/Translation/QA job (implemented in JobsPage)
- [x] Start/Pause controls (implemented in JobsPage)
- [x] Real-time progress via WebSocket (useJobWebSocket hook, auto-reconnect 3s)
- [x] Form validation for required fields (project, volume, task selection required)

### Phase 6: Polish & Production ✅ DONE
- [x] Confirmation dialogs for destructive actions (ConfirmDialog component used across all pages)
- [x] Production build: `vite build` → static files served by FastAPI at `/`
- [x] Single `python main.py` entry point for production (main.py has run() function + uvicorn)
- [x] TypeScript compiles clean, Vite build passes
- [x] Form validation with user feedback (TasksPage, JobsPage validate required fields before submission)
- [x] Dark/light theme with localStorage persistence
- [x] Responsive layout with Tailwind CSS utility classes
- [ ] Error toast notifications (alert() used for validation; toast component optional enhancement)
- [x] Logo: Using Lucide React BookOpen icon as app logo (no separate SVG needed)

## Key Decisions
- FastAPI + React replaces Reflex entirely.
- Existing Python modules (`epub_handler.py`, `llm_handler.py`, processors, job queue) are reused as-is.
- React Query manages server state; WebSocket pushes job progress.
- Chapter HTML resource paths rewritten to absolute API URLs for IFrame compatibility.
- OAuth2-ready: each endpoint accepts an optional `current_user` dependency; no auth enforced currently.
- `translate_epubs_new.py` kept locally as reference but excluded from git.
- AG-Grid v32 renamed `onCellChanged` to `onCellEditStopped` — updated GlossaryEditor accordingly.
- `useQuery` `queryFn` must be a zero-arg function — wrapped API calls with arrow functions (`() => jobsApi.list()`).
- Vite dev server proxies `/api` and `/ws` to backend on port 8000.
- Python 3.9 compatible (user's system Python) — FastAPI 0.115.x, uvicorn 0.34.x, SQLAlchemy 2.0.x all work.
- ConfirmDialog moved to `components/` directory — all pages import from `../components/ConfirmDialog`.

### Phase 9: BookViewer Fixes ✅ DONE
- [x] Resource endpoint (`resources.py`) — Added `zlib` decompression via `_try_decompress()` helper; CSS/images now return correct content with proper `charset=utf-8` media types
- [x] TOC endpoint (`chapters.py`) — New `/volumes/{volume_id}/toc` endpoint builds chapter list from all Chapter items (spine) + Nav file name mapping; resolves relative hrefs against Nav file directory
- [x] BookViewer (`BookViewer.tsx`) — Replaced Nav HTML parsing with `getTOC` API call; TOC now shows all chapters regardless of Nav coverage; auto-selects first chapter; keyboard nav (ArrowLeft/ArrowRight) works with spine-based chapter list
- [x] Chapter lookup (`chapters.py`) — `get_chapter` now tries UUID lookup first (from TOC item.id), then falls back to full_path, relative path, and filename matching
- [x] API client (`api.ts`) — Added `getTOC` endpoint; frontend uses `chaptersApi.getTOC(volumeId)`
- [x] Frontend rebuilt (`npx vite build` passes); backend imports clean (`python3 -c "import babelcity.api.chapters"`)

### Phase 10: LLM Streaming + Full Params + Translation/QA Jobs ✅ DONE
- [x] `llm_handler.py` — `ask_llm()` now uses `stream=True` with `stream_options={"include_usage": True}` to capture token metrics (prompt/completion/total tokens, latency, TPS); falls back to non-streaming on error; added `top_k` parameter in `extra_body`
- [x] `ask_llm_json()` — Added `top_k` parameter passthrough
- [x] All `ask_llm`/`ask_llm_json` callers now pass all LLM parameters from `TaskDefinition`: temperature, top_p, min_p, top_k, presence_penalty, frequency_penalty, repetition_penalty
- [x] `job_executors.py` — `execute_translation_job`: Full implementation with `process_document()`, zlib compression, `ItemTranslation` storage, Nav translation, and complete `llm_config` from `TaskDefinition`
- [x] `job_executors.py` — `execute_qa_job`: Full implementation with multi-pass QA, `ThreadPoolExecutor` multi-threading (respects `config.threads`), previous round lookup, `ItemTranslation` storage
- [x] All Python files compile clean; Vite build passes