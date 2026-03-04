from datetime import datetime, timedelta
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from .config import SETTINGS
from .database import Base, engine, get_db, SessionLocal
from .models import Agent, Work, Company, Task, AgentWorkCooldown
from . import schemas


app = FastAPI(title=SETTINGS.get("app_name", "Commercial Empire API"))


@app.on_event("startup")
def on_startup():
    # Create tables
    Base.metadata.create_all(bind=engine)
    # Seed works from config if missing
    seed = SETTINGS.get("seed_works", [])
    if not seed:
        return
    db = SessionLocal()
    try:
        for w in seed:
            wt = w.get("work_type")
            if not wt:
                continue
            exists = db.execute(select(Work).where(Work.work_type == wt)).scalar_one_or_none()
            if not exists:
                db.add(
                    Work(
                        work_type=wt,
                        reward=int(w.get("reward", 0)),
                        cooldown_minutes=int(w.get("cooldown_minutes", 0)),
                    )
                )
        db.commit()
    finally:
        db.close()


# Agents
@app.post("/agents/register", response_model=schemas.AgentOut, status_code=status.HTTP_201_CREATED)
def register_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    existing = db.execute(select(Agent).where(Agent.name == payload.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Agent name already exists")
    agent = Agent(name=payload.name)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@app.get("/agents/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# Companies
@app.post("/companies", response_model=schemas.CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(payload: schemas.CompanyCreate, db: Session = Depends(get_db)):
    exists = db.execute(select(Company).where(Company.name == payload.name)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Company name already exists")
    company = Company(name=payload.name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


# Work
@app.post("/work/do", response_model=schemas.DoWorkResult)
def do_work(payload: schemas.DoWorkRequest, db: Session = Depends(get_db)):
    agent = db.get(Agent, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    work = db.execute(select(Work).where(Work.work_type == payload.work_type)).scalar_one_or_none()
    if not work:
        raise HTTPException(status_code=404, detail="Work type not found")

    # Cooldown enforcement
    cooldown = db.execute(
        select(AgentWorkCooldown).where(
            AgentWorkCooldown.agent_id == agent.id,
            AgentWorkCooldown.work_id == work.id,
        )
    ).scalar_one_or_none()

    now = datetime.utcnow()
    if cooldown:
        next_available = cooldown.last_performed_at + timedelta(minutes=work.cooldown_minutes)
        if now < next_available:
            # Still on cooldown
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Work is on cooldown",
                    "next_available_at": next_available.isoformat(),
                },
            )
        cooldown.last_performed_at = now
    else:
        cooldown = AgentWorkCooldown(agent_id=agent.id, work_id=work.id, last_performed_at=now)
        db.add(cooldown)

    # Apply rewards (MVP: reward adds gold, experience from settings)
    gained_gold = int(work.reward)
    agent.gold_coins += gained_gold

    exp_gain = int(SETTINGS.get("experience_per_work", 10))
    agent.experience += exp_gain

    # Level up logic: simple threshold, carry remainder
    threshold = int(SETTINGS.get("level_threshold", 100))
    while agent.experience >= threshold:
        agent.level += 1
        agent.experience -= threshold

    db.commit()
    db.refresh(agent)

    next_available_at = cooldown.last_performed_at + timedelta(minutes=work.cooldown_minutes)

    return schemas.DoWorkResult(
        agent=agent,
        work=work,
        gained_gold=gained_gold,
        next_available_at=next_available_at,
    )


# Optional helper endpoint to list work types for clients
@app.get("/work", response_model=List[schemas.WorkOut])
def list_work(db: Session = Depends(get_db)):
    rows = db.execute(select(Work).order_by(Work.id)).scalars().all()
    return rows
