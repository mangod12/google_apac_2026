"""
Data access layer — async CRUD for tasks, agent_logs, and memory_entries.
"""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task, AgentLog, MemoryEntry, TaskStatus


# ── Task Repository ──────────────────────────────────────


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, title: str, description: str, priority: str = "medium", parent_task_id: Optional[uuid.UUID] = None) -> Task:
        task = Task(
            title=title,
            description=description,
            priority=priority,
            parent_task_id=parent_task_id,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get(self, task_id: uuid.UUID) -> Optional[Task]:
        result = await self.session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 50, offset: int = 0) -> Sequence[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.parent_task_id.is_(None))
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def update_status(self, task_id: uuid.UUID, status: TaskStatus) -> None:
        await self.session.execute(
            update(Task).where(Task.id == task_id).values(status=status)
        )
        await self.session.commit()

    async def update_results(
        self,
        task_id: uuid.UUID,
        *,
        status: Optional[TaskStatus] = None,
        result_plan: Optional[dict] = None,
        result_tasks: Optional[list] = None,
        result_schedule: Optional[dict] = None,
        result_reasoning: Optional[list] = None,
    ) -> None:
        values: dict = {}
        if status is not None:
            values["status"] = status
        if result_plan is not None:
            values["result_plan"] = result_plan
        if result_tasks is not None:
            values["result_tasks"] = result_tasks
        if result_schedule is not None:
            values["result_schedule"] = result_schedule
        if result_reasoning is not None:
            values["result_reasoning"] = result_reasoning
        if values:
            await self.session.execute(update(Task).where(Task.id == task_id).values(**values))
            await self.session.commit()

    async def delete_task(self, task_id: uuid.UUID) -> None:
        await self.session.execute(delete(Task).where(Task.id == task_id))
        await self.session.commit()


# ── AgentLog Repository ──────────────────────────────────


class AgentLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        task_id: uuid.UUID,
        agent_name: str,
        action: str,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        reasoning: Optional[str] = None,
        token_usage: int = 0,
    ) -> AgentLog:
        log = AgentLog(
            task_id=task_id,
            agent_name=agent_name,
            action=action,
            input_data=input_data,
            output_data=output_data,
            reasoning=reasoning,
            token_usage=token_usage,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def list_by_task(self, task_id: uuid.UUID) -> Sequence[AgentLog]:
        result = await self.session.execute(
            select(AgentLog)
            .where(AgentLog.task_id == task_id)
            .order_by(AgentLog.created_at.asc())
        )
        return result.scalars().all()


# ── Memory Repository ────────────────────────────────────


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, content: str, entry_type: str, task_id: Optional[uuid.UUID] = None, metadata: Optional[dict] = None) -> MemoryEntry:
        entry = MemoryEntry(
            task_id=task_id,
            content=content,
            entry_type=entry_type,
            metadata_=metadata,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def search(self, query: str, limit: int = 10) -> Sequence[MemoryEntry]:
        """Semantic vector search with keyword fallback.

        Tries pgvector cosine similarity first (if embeddings exist).
        Falls back to keyword ILIKE search if vector search fails or
        returns no results.
        """
        # Try vector search first
        try:
            results = await self._vector_search(query, limit)
            if results:
                return results
        except Exception:
            pass

        # Fallback: keyword search (OR across words)
        return await self._keyword_search(query, limit)

    async def _vector_search(self, query: str, limit: int) -> Sequence[MemoryEntry]:
        """Search using pgvector cosine distance on embeddings."""
        from app.llm.embeddings import generate_embedding

        query_embedding = await generate_embedding(query)
        result = await self.session.execute(
            select(MemoryEntry)
            .where(MemoryEntry.embedding.isnot(None))
            .order_by(MemoryEntry.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        return result.scalars().all()

    async def _keyword_search(self, query: str, limit: int) -> Sequence[MemoryEntry]:
        """Fallback keyword search — splits query into words, OR logic."""
        from sqlalchemy import or_

        keywords = [w.strip() for w in query.split() if len(w.strip()) >= 3]
        if not keywords:
            keywords = [query]

        conditions = [MemoryEntry.content.ilike(f"%{kw}%") for kw in keywords]
        result = await self.session.execute(
            select(MemoryEntry)
            .where(or_(*conditions))
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_task(self, task_id: uuid.UUID, limit: int = 20) -> Sequence[MemoryEntry]:
        result = await self.session.execute(
            select(MemoryEntry)
            .where(MemoryEntry.task_id == task_id)
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
