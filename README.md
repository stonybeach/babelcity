# Babel City

Local Web Novel & EPUB Translation Organizer. Provides a web UI for managing translation projects, configuring LLM tasks, and running background translation/QA jobs.

**Notes: currently only the "Generic" project type supports different languages. "Light Novel" and "Web Novel" project types are specific for Japanese -> Chinese translation only.**

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS 3
- **Translation**: OpenAI-compatible LLM APIs, Traditional Chinese conversion via OpenCC

## Quick Start

### Before you start

- Install git
- Install python 3.11 or newer
- Install Node JS 18 or newer

### 1. Clone the Repository

```bash
git clone https://github.com/stonybeach/babelcity.git
cd babelcity
```

### 2. Build the Application

```bash
python3.11 -m venv .venv
source .venv/bin/activate
./build.sh
```

### 3. Start the Application

```bash
./start.sh
```

The application will be available at `http://localhost:8000`.

## How to Use

- Create a new Project and add volumes
- Import the EPUB file for each volume
- Configure LLM task definitions (Glossary, Translation, QA)
- Add a Glossary job to the queue and start
- Add a Translation job to the queue and start 
- Preview translated chapters in the built-in Book Viewer as it is translated
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

## Screenshots

![Projects](/screenshots/projects.png)
![Book Viewer](/screenshots/book_viewer.png)
![Glossary Editor](/screenshots/glossary_editor.png)
![Jobs Queue](/screenshots/jobs_queue.png)
