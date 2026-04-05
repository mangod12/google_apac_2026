"""
SQLAlchemy ORM models for TaskForge.
Tables: tasks, agent_logs, memory_entries
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector
import enum


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ── Enums ────────────────────────────────────────────────


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RESOURCE_ASSESSMENT = "resource_assessment"
    PLANNING = "planning"
    EXECUTING = "executing"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    FAILED = "failed"


class MemoryEntryType(str, enum.Enum):
    CONTEXT = "context"
    RESOURCE = "resource"
    DECISION = "decision"
    PLAN = "plan"
    BLOCKER = "blocker"


# ── Models ───────────────────────────────────────────────


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(
        SAEnum(TaskStatus, name="task_status", create_constraint=True),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    priority = Column(String(20), default="medium")  # critical, high, medium, low

    # Structured output fields
    result_plan = Column(JSONB, nullable=True)       # The response plan
    result_tasks = Column(JSONB, nullable=True)       # Task breakdown
    result_schedule = Column(JSONB, nullable=True)    # Timeline / milestones
    result_reasoning = Column(JSONB, nullable=True)   # Chain-of-thought reasoning

    # Hierarchy
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    subtasks = relationship("Task", backref="parent_task", remote_side=[id], lazy="selectin")
    logs = relationship("AgentLog", back_populates="task", lazy="selectin", cascade="all, delete-orphan")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(100), nullable=False)
    action = Column(String(200), nullable=False)
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    reasoning = Column(Text, nullable=True)
    token_usage = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    task = relationship("Task", back_populates="logs")


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    entry_type = Column(
        SAEnum(MemoryEntryType, name="memory_entry_type", create_constraint=True),
        default=MemoryEntryType.CONTEXT,
        nullable=False,
    )
    metadata_ = Column("metadata", JSONB, nullable=True)
    embedding = Column(Vector(3072), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
