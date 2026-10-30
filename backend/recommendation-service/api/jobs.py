"""Recommendations asked agent by agent, in the background.

Some agents take 15 s or more to answer (the PowerGrid GNN agent). Held open
that long, a request can be cut on the way - by a VPN, a proxy, a gateway -
whatever the timeouts of this service and its nginx. So a job is started, the
request returns at once, and the client polls the job: each agent's
recommendations are there as soon as it has answered.

Jobs are kept in the database, not in memory, so any instance of the service
can answer a poll.
"""

import threading
import uuid
from datetime import datetime, timedelta

from settings import logger

from .exceptions import AgentError
from .models import RecommendationJob, RecommendationJobAgent, db

# Time an agent is given past its own timeout before a pending answer is
# reported failed
DEADLINE_MARGIN = timedelta(seconds=10)
# Timeout of use cases that do not ask their agents one by one
DEFAULT_TIMEOUT = 120
# Jobs older than this are deleted when a new one starts
RETENTION = timedelta(hours=1)


def _units(manager, request_data):
    """What a job asks, one unit per agent: (id, name, timeout, ask)."""
    if hasattr(manager, "select_agents") and hasattr(manager, "recommend_from"):
        agents = manager.select_agents(request_data)
        alone = len(agents) == 1
        return [
            (
                agent["id"],
                agent["name"],
                agent["timeout"],
                lambda agent=agent: manager.recommend_from(agent, request_data, alone),
            )
            for agent in agents
        ]
    # A use case with a single, built-in agent
    return [
        ("default", None, DEFAULT_TIMEOUT, lambda: manager.get_recommendation(request_data))
    ]


def start_job(app, manager, use_case, request_data):
    """Start asking the agents of a request, and return the job."""
    now = datetime.utcnow()
    _delete_old_jobs(now)

    job = RecommendationJob(id=str(uuid.uuid4()), use_case=use_case, created_at=now)
    db.session.add(job)
    units = _units(manager, request_data)
    rows = [
        RecommendationJobAgent(
            job_id=job.id,
            position=position,
            agent_id=agent_id,
            agent_name=name,
            status="pending",
            deadline=now + timedelta(seconds=timeout) + DEADLINE_MARGIN,
        )
        for position, (agent_id, name, timeout, _) in enumerate(units)
    ]
    db.session.add_all(rows)
    db.session.commit()

    for row, (_, _, _, ask) in zip(rows, units):
        threading.Thread(target=_run, args=(app, row.id, ask), daemon=True).start()
    return job_state(job.id)


def _run(app, row_id, ask):
    """Ask one agent and store its answer."""
    try:
        recommendations, status = ask(), "done"
    except AgentError:
        # Already logged by the manager
        recommendations, status = None, "failed"
    except Exception:
        logger.exception("Recommendation job agent %s failed", row_id)
        recommendations, status = None, "failed"
    with app.app_context():
        try:
            row = db.session.get(RecommendationJobAgent, row_id)
            row.status = status
            row.recommendations = recommendations
            db.session.commit()
        finally:
            db.session.remove()


def job_state(job_id):
    """The job as the client sees it, None if there is no such job.

    {"id", "use_case", "status": "running" | "done",
     "agents": [{"id", "name", "status": "pending" | "done" | "failed"}],
     "recommendations": [those of the agents that have answered, in order]}
    """
    job = db.session.get(RecommendationJob, job_id)
    if job is None:
        return None
    rows = (
        RecommendationJobAgent.query.filter_by(job_id=job_id)
        .order_by(RecommendationJobAgent.position)
        .all()
    )
    now = datetime.utcnow()
    agents = []
    recommendations = []
    for row in rows:
        status = row.status
        if status == "pending" and now > row.deadline:
            status = "failed"
        agents.append({"id": row.agent_id, "name": row.agent_name, "status": status})
        if status == "done":
            recommendations.extend(row.recommendations or [])
    return {
        "id": job.id,
        "use_case": job.use_case,
        "status": "running" if any(a["status"] == "pending" for a in agents) else "done",
        "agents": agents,
        "recommendations": recommendations,
    }


def _delete_old_jobs(now):
    old = [
        job_id
        for (job_id,) in db.session.query(RecommendationJob.id).filter(
            RecommendationJob.created_at < now - RETENTION
        )
    ]
    if not old:
        return
    RecommendationJobAgent.query.filter(RecommendationJobAgent.job_id.in_(old)).delete(
        synchronize_session=False
    )
    RecommendationJob.query.filter(RecommendationJob.id.in_(old)).delete(
        synchronize_session=False
    )
