# Babel City

Local Web Novel & EPUB Translation Organizer. Provides a web UI for managing translation projects, configuring LLM tasks, and running background translation/QA jobs.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS 3
- **Translation**: OpenAI-compatible LLM APIs, Traditional Chinese conversion via OpenCC

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd babelcity
```

### 2. Backend Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd web
npm install
npm run build
cd ..
```

### 4. Start the Application

```bash
python -m babelcity.main
```

The application will be available at `http://localhost:8000`.

## How It Works

- Import EPUB files or web novels as projects
- Configure LLM task definitions (Glossary, Translation, QA)
- Create and queue translation/QA jobs
- Monitor job progress in real-time via WebSocket
- Preview translated chapters in the built-in Book Viewer
- Export translated content as EPUB files

## Configuration

LLM endpoints are configured per task definition through the web UI. Any OpenAI-compatible API (Ollama, vLLM, LM Studio, etc.) is supported.

## Development

For development mode with hot-reloading:

```bash
# Terminal 1 — Backend
source .venv/bin/activate
python -m babelcity.main

# Terminal 2 — Frontend (with proxy to backend)
cd web
npm run dev
```
