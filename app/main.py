"""
Bounty Board API Server
Start: uvicorn app.main:app --host 0.0.0.0 --port 8000
Swagger: http://localhost:8000/docs
"""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import Database
from app.state import AppState
from app.routers import repos, bounties, claims, agents
from app.models import HealthOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "schema.sql")
    db = Database(settings.db, schema_path)
    app_state = AppState(db)

    # Pre-load GitHub clients for registered repos
    for repo in db.get_repos():
        try:
            app_state.get_or_create_gh(repo["slug"])
        except Exception:
            pass

    app.state.app_state = app_state
    yield

    # Shutdown: stop all workers
    for worker in list(app_state.workers.values()):
        worker.stop()
    for worker in list(app_state.workers.values()):
        worker.join(timeout=10)

    db.close()


app = FastAPI(
    title="Bounty Board",
    description="Multi-agent software development system. "
                "Manage repos, bounties, claims, and agent workers via REST API.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(repos.router, prefix="/repos", tags=["Repos"])
app.include_router(bounties.router, prefix="/bounties", tags=["Bounties"])
app.include_router(claims.router, prefix="/claims", tags=["Claims"])
app.include_router(agents.router, prefix="/agents", tags=["Agents"])


@app.get("/health", response_model=HealthOut, tags=["System"])
def health_check():
    state = app.state.app_state
    return HealthOut(
        status="ok",
        repos=len(state.db.get_repos()),
        active_claims=len(state.db.list_claims()),
        active_agents=sum(1 for w in state.workers.values() if w.is_alive()),
    )
