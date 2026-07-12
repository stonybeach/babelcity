"""FastAPI application entry point for Babel City."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import typer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db


WEB_DIST = Path(__file__).parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .ws import set_main_loop
    set_main_loop(asyncio.get_running_loop())
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

def _mount_static(dist: Path):
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")


_mount_static(WEB_DIST)


cli = typer.Typer()


@cli.command()
def main(
    web_dist: Path | None = typer.Option(None, "--web-dist", help="Static files directory"),
    web_host: str = typer.Option("127.0.0.1", "--web-host", help="Bind host"),
    web_port: int = typer.Option(8000, "--web-port", help="Bind port"),
):
    """Babel City — Web Novel & EPUB Translation Organizer."""
    if web_dist is not None:
        _mount_static(web_dist)
    import uvicorn
    uvicorn.run("babelcity.main:app", host=web_host, port=web_port, reload=True)


if __name__ == "__main__":
    cli()