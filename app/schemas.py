from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# Agent
class AgentBase(BaseModel):
    name: str = Field(..., max_length=100)


class AgentCreate(AgentBase):
    pass


class AgentOut(AgentBase):
    id: int
    silicon_points: int
    gold_coins: int
    level: int
    experience: int

    class Config:
        from_attributes = True


# Work
class WorkBase(BaseModel):
    work_type: str
    reward: int
    cooldown_minutes: int


class WorkOut(WorkBase):
    id: int

    class Config:
        from_attributes = True


# Company
class CompanyCreate(BaseModel):
    name: str


class CompanyOut(CompanyCreate):
    id: int

    class Config:
        from_attributes = True


# Task
class TaskBase(BaseModel):
    company_id: int
    title: str
    reward_per_agent: int
    max_agents: int


class TaskOut(TaskBase):
    id: int

    class Config:
        from_attributes = True


# Gameplay
class DoWorkRequest(BaseModel):
    agent_id: int
    work_type: str


class DoWorkResult(BaseModel):
    agent: AgentOut
    work: WorkOut
    gained_gold: int
    next_available_at: datetime
