from datetime import datetime
from typing import List

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    silicon_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gold_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    api_key: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=True)
    uid: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=True)

    cooldowns: Mapped[List["AgentWorkCooldown"]] = relationship("AgentWorkCooldown", back_populates="agent", cascade="all, delete-orphan")


class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_type: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    reward: Mapped[int] = mapped_column(Integer, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    cooldowns: Mapped[List["AgentWorkCooldown"]] = relationship("AgentWorkCooldown", back_populates="work", cascade="all, delete-orphan")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reward: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    publisher_id: Mapped[int] = mapped_column(Integer, nullable=True)


class AgentWorkCooldown(Base):
    __tablename__ = "agent_work_cooldowns"
    __table_args__ = (
        UniqueConstraint("agent_id", "work_id", name="uq_agent_work"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), nullable=False)
    last_performed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    agent: Mapped[Agent] = relationship("Agent", back_populates="cooldowns")
    work: Mapped[Work] = relationship("Work", back_populates="cooldowns")
