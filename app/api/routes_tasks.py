"""
Task API routes.

Endpoints:
  POST   /api/v1/tasks           — Create task + start agent pipeline (202)
  GET    /api/v1/tasks           — List tasks (paginated)
  GET    /api/v1/tasks/{id}      — Get task details + subtasks
  GET    /api/v1/tasks/{id}/logs — Get agent execution logs
  DELETE /api/v1/tasks/{id}      — Delete a task
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.database import async_session_factory
from app.db.repositories import AgentLogRepository, TaskRepository
from app.schemas.task_schemas import (
    AgentLogResponse,
    ExecuteRequest,
    ExecuteResponse,
    TaskCreateRequest,
    TaskCreatedResponse,
    TaskListResponse,
    TaskResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
demo_router = APIRouter(tags=["demo"])


# ── Helper: Run pipeline in background ───────────────────

async def _run_pipeline(task_id: uuid.UUID, task_title: str, task_description: str) -> None:
    """Background worker: runs the full orchestrator pipeline for a task."""
    from app.agents.orchestrator import OrchestratorAgent
    from app.db.models import TaskStatus

    # Import tools to trigger registration
    import app.tools.task_tools       # noqa: F401
    import app.tools.knowledge_tool   # noqa: F401
    import app.tools.calendar_tool    # noqa: F401
    import app.tools.weather_tool     # noqa: F401

    orchestrator = OrchestratorAgent()
    try:
        result = await orchestrator.run(
            task_id=task_id,
            task_title=task_title,
            task_description=task_description,
        )
        if not result.success:
            logger.error(f"[pipeline] task {task_id} failed: {result.error}")
            async with async_session_factory() as session:
                repo = TaskRepository(session)
                await repo.update_status(task_id, TaskStatus.FAILED)
    except Exception as e:
        logger.exception(f"[pipeline] unhandled exception for task {task_id}: {e}")
        try:
            async with async_session_factory() as session:
                repo = TaskRepository(session)
                await repo.update_status(task_id, TaskStatus.FAILED)
        except Exception:
            pass


def _extract_schedule_entries(result_schedule: dict | None) -> list[dict]:
    """Convert stored schedule data into a simple list for demo responses."""
    if not result_schedule:
        return []

    adjusted_timeline = result_schedule.get("adjusted_timeline")
    if isinstance(adjusted_timeline, dict):
        milestones = adjusted_timeline.get("milestones")
        if isinstance(milestones, list):
            return milestones

    milestones = result_schedule.get("milestones")
    if isinstance(milestones, list):
        return milestones

    total_days = result_schedule.get("total_days")
    if total_days is not None:
        return [{"day": total_days, "time": "08:00", "description": "Planned completion"}]

    return []


def _build_execute_response(
    task,
    agent_flow: list[str],
    replanning: dict | None,
    summary: str,
    confidence_score: float,
    crisis_context: dict,
    insights: list[str],
    risk_notes: list[str],
    decision_comparison: str | None = None,
    system_state: dict | None = None,
    execution_time: str = "0.00s",
    impact_analysis: dict | None = None,
    outcome_summary: str = "",
    system_reliability: dict | None = None,
    reasoning_trace: list[dict] | None = None,
) -> ExecuteResponse:
    """Build a clean synchronous demo response from stored task results."""
    from app.schemas.task_schemas import SystemReliability

    result_plan = task.result_plan or {}
    result_tasks = task.result_tasks or []
    result_schedule = task.result_schedule or {}

    return ExecuteResponse(
        summary=summary,
        crisis_context=crisis_context,
        plan=result_plan.get("strategy", ""),
        tasks=result_tasks,
        schedule=_extract_schedule_entries(result_schedule),
        agent_flow=agent_flow,
        confidence_score=confidence_score,
        insights=insights,
        risk_notes=risk_notes,
        decision_comparison=decision_comparison,
        system_state=system_state,
        execution_time=execution_time,
        impact_analysis=impact_analysis,
        replanning=replanning,
        outcome_summary=outcome_summary,
        system_reliability=SystemReliability(**(system_reliability or {})),
        reasoning_trace=reasoning_trace or [],
    )


# ── Endpoints ─────────────────────────────────────────────

@router.post(
    "",
    response_model=TaskCreatedResponse,
    status_code=202,
    summary="Create a task and start the agent pipeline",
    description="Creates a new task and immediately triggers the multi-agent orchestration pipeline in the background. Returns a task ID to poll for results.",
)
async def create_task(
    payload: TaskCreateRequest,
    background_tasks: BackgroundTasks,
) -> TaskCreatedResponse:
    """
    Accept a task and kick off the agent pipeline asynchronously.
    Returns 202 Accepted immediately with the task_id.
    """
    async with async_session_factory() as session:
        repo = TaskRepository(session)
        task = await repo.create(
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
        )
        task_id = task.id

    logger.info(f"[api] created task {task_id}: {payload.title!r}")

    background_tasks.add_task(
        _run_pipeline, task_id, payload.title, payload.description
    )

    return TaskCreatedResponse(
        task_id=task_id,
        status="pending",
        message="Task accepted. Agent pipeline is running — poll GET /api/v1/tasks/{id} for results.",
    )


@demo_router.post(
    "/execute",
    response_model=ExecuteResponse,
    summary="Execute a task synchronously for demos",
)
async def execute_task(payload: ExecuteRequest) -> ExecuteResponse:
    """Run the existing orchestrator pipeline synchronously and return a clean result."""
    from app.agents.orchestrator import OrchestratorAgent
    from app.db.models import TaskStatus

    import app.tools.task_tools       # noqa: F401
    import app.tools.knowledge_tool   # noqa: F401
    import app.tools.calendar_tool    # noqa: F401
    import app.tools.weather_tool     # noqa: F401

    async with async_session_factory() as session:
        repo = TaskRepository(session)
        task = await repo.create(
            title=payload.query,
            description=payload.query,
            priority="medium",
        )
        task_id = task.id

    t_start = time.monotonic()

    orchestrator = OrchestratorAgent()
    result = await orchestrator.run(
        task_id=task_id,
        task_title=payload.query,
        task_description=payload.query,
    )

    if not result.success:
        async with async_session_factory() as session:
            repo = TaskRepository(session)
            await repo.update_status(task_id, TaskStatus.FAILED)
        raise HTTPException(status_code=500, detail=result.error or "Execution failed")

    async with async_session_factory() as session:
        repo = TaskRepository(session)
        task = await repo.get(task_id)

    if not task:
        raise HTTPException(status_code=500, detail="Task result not found")

    execution_time = f"{time.monotonic() - t_start:.2f}s"

    return _build_execute_response(
        task=task,
        agent_flow=result.output.get("agent_flow", []),
        replanning=result.output.get("replanning"),
        summary=result.output.get("summary", ""),
        confidence_score=result.output.get("confidence_score", 0.0),
        crisis_context=result.output.get("crisis_context", {}),
        insights=result.output.get("insights", []),
        risk_notes=result.output.get("risk_notes", []),
        decision_comparison=result.output.get("decision_comparison"),
        system_state=result.output.get("system_state"),
        execution_time=execution_time,
        impact_analysis=result.output.get("impact_analysis"),
        outcome_summary=result.output.get("outcome_summary", ""),
        system_reliability=result.output.get("system_reliability"),
        reasoning_trace=result.output.get("reasoning_trace", []),
    )


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List all top-level tasks",
)
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> TaskListResponse:
    """Return a paginated list of top-level tasks (excludes subtasks)."""
    async with async_session_factory() as session:
        repo = TaskRepository(session)
        tasks = await repo.list_all(limit=limit, offset=offset)

    return TaskListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=len(tasks),
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task details",
)
async def get_task(task_id: uuid.UUID) -> TaskResponse:
    """Return full task details including subtasks and structured results."""
    async with async_session_factory() as session:
        repo = TaskRepository(session)
        task = await repo.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskResponse.model_validate(task)


@router.get(
    "/{task_id}/logs",
    response_model=list[AgentLogResponse],
    summary="Get agent execution logs for a task",
)
async def get_task_logs(task_id: uuid.UUID) -> list[AgentLogResponse]:
    """Return all agent log entries for a task, ordered chronologically."""
    async with async_session_factory() as session:
        task_repo = TaskRepository(session)
        task = await task_repo.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        log_repo = AgentLogRepository(session)
        logs = await log_repo.list_by_task(task_id)

    return [AgentLogResponse.model_validate(log) for log in logs]


@router.delete(
    "/{task_id}",
    status_code=200,
    summary="Delete a task",
)
async def delete_task(task_id: uuid.UUID) -> None:
    """Permanently delete a task and all its subtasks and logs (cascade)."""
    async with async_session_factory() as session:
        repo = TaskRepository(session)
        task = await repo.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        await repo.delete_task(task_id)

    logger.info(f"[api] deleted task {task_id}")
