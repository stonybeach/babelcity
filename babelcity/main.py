"""FastAPI application entry point for Babel City."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db


WEB_DIST = Path(__file__).parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Babel City",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .api import projects, tasks, jobs, glossary, resources, chapters  # noqa: E402
from .ws import router as ws_router  # noqa: E402

app.include_router(projects.router, prefix="/api/v1", tags=["Projects"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
app.include_router(glossary.router, prefix="/api/v1", tags=["Glossary"])
app.include_router(resources.router, prefix="/api/v1", tags=["Resources"])
app.include_router(chapters.router, prefix="/api/v1", tags=["Chapters"])
app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])

if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="static")


def run():
    import uvicorn
    uvicorn.run("babelcity.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()