"""Agents router — start, stop, and list worker threads."""

import time

from fastapi import APIRouter, HTTPException, Request

from app.models import AgentStart, AgentStop, AgentOut
from app.workers.be_worker import BEWorker
from app.workers.fe_worker import FEWorker
from app.workers.qa_worker import QAWorker
from app.workers.pm_worker import PMWorker

router = APIRouter()

WORKER_CLASSES = {
    "be": BEWorker,
    "fe": FEWorker,
    "qa": QAWorker,
    "pm": PMWorker,
}


def _get_state(request: Request):
    return request.app.state.app_state


@router.post("/start", response_model=AgentOut, status_code=201)
def start_agent(body: AgentStart, request: Request):
    state = _get_state(request)

    repo = state.db.get_repo(body.repo_slug)
    if not repo:
        raise HTTPException(404, f"Repo not registered: {body.repo_slug}")

    if body.agent_type not in WORKER_CLASSES:
        raise HTTPException(400, f"Unknown agent type: {body.agent_type}. "
                           f"Valid: {list(WORKER_CLASSES.keys())}")

    agent_id = body.agent_id or f"{body.agent_type}-{body.repo_slug.split('/')[-1]}-{int(time.time())}"

    if agent_id in state.workers and state.workers[agent_id].is_alive():
        raise HTTPException(409, f"Agent {agent_id} is already running")

    worker_cls = WORKER_CLASSES[body.agent_type]
    worker = worker_cls(agent_id=agent_id, repo_slug=body.repo_slug, app_state=state)
    state.workers[agent_id] = worker
    worker.start()

    return AgentOut(
        agent_id=agent_id,
        agent_type=body.agent_type,
        repo_slug=body.repo_slug,
        status="running",
        started_at=worker.started_at,
    )


@router.post("/stop")
def stop_agent(body: AgentStop, request: Request):
    state = _get_state(request)

    worker = state.workers.get(body.agent_id)
    if not worker:
        raise HTTPException(404, f"Agent not found: {body.agent_id}")

    worker.stop()
    worker.join(timeout=5)

    return {"agent_id": body.agent_id, "status": worker.status}


@router.get("", response_model=list[AgentOut])
def list_agents(request: Request, repo_slug: str | None = None):
    state = _get_state(request)

    agents = []
    for aid, worker in state.workers.items():
        if repo_slug and worker.repo_slug != repo_slug:
            continue

        # Update status based on thread state
        if not worker.is_alive() and worker.status != "stopped":
            worker.status = "stopped"

        agents.append(AgentOut(
            agent_id=aid,
            agent_type=worker.agent_type,
            repo_slug=worker.repo_slug,
            status=worker.status,
            started_at=worker.started_at,
        ))

    return agents
