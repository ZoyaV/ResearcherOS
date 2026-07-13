"""FastAPI application — thin HTTP layer over koi services."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import agents, composites, cursor, knowledge, library, meta, paper, programs, projects, review, sync

app = FastAPI(
    title="KOI API",
    description="Agile for Science — hypothesis tree + kanban, persisted as Markdown",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    meta.router,
    library.router,
    programs.router,
    composites.router,
    projects.router,
    knowledge.router,
    paper.router,
    review.router,
    agents.router,
    cursor.router,
    sync.router,
):
    app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    from koi.adapters.project_discovery_watch import start_project_discovery_watch
    from koi.adapters.settings_store import load_env_file

    load_env_file()
    start_project_discovery_watch()


@app.on_event("shutdown")
def _shutdown() -> None:
    from koi.adapters.project_discovery_watch import stop_project_discovery_watch

    stop_project_discovery_watch()
