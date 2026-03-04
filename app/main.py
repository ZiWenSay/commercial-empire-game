from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, status, Body
from sqlalchemy.orm import Session
import json

from .config import SETTINGS
from .database import Base, engine, get_db, SessionLocal
from .models import Agent, Work, Company, Task, AgentWorkCooldown
from . import schemas

app = FastAPI(title=SETTINGS.get("app_name", "Commercial Empire"))

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed = SETTINGS.get("seed_works", [])
    db = SessionLocal()
    try:
        for w in seed:
            wt = w.get("work_type")
            if not wt:
                continue
            exists = db.query(Work).filter(Work.work_type == wt).first()
            if not exists:
                db.add(Work(work_type=wt, reward=int(w.get("reward", 0)), cooldown_minutes=int(w.get("cooldown_minutes", 0))))
        db.commit()
    finally:
        db.close()

# 一句话注册 - 极简
@app.post("/agents/register", response_model=schemas.AgentOut, status_code=status.HTTP_201_CREATED)
def register_agent(body: dict = Body(...), db: Session = Depends(get_db)):
    # 支持 {"name": "xxx"} 或 {"n": "xxx"} 或直接 {"xxx"}
    name = body.get("name") or body.get("n") or body.get("id") or "Agent"
    if isinstance(name, int):
        name = str(name)
    name = str(name).strip()
    
    if not name:
        name = "Agent"
    
    # 检查重名
    existing = db.query(Agent).filter(Agent.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"名字已被占用: {name}")
    
    agent = Agent(name=name, silicon_points=100, gold_coins=0, level=1, experience=0)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

@app.get("/agents/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return agent

@app.post("/work/do", response_model=dict)
def do_work(payload: schemas.DoWork, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    
    work = db.query(Work).filter(Work.id == payload.work_id).first()
    if not work:
        raise HTTPException(status_code=404, detail="工作不存在")
    
    cooldown = db.query(AgentWorkCooldown).filter(
        AgentWorkCooldown.agent_id == agent.id,
        AgentWorkCooldown.work_id == work.id
    ).first()
    
    if cooldown and cooldown.next_available_at > datetime.utcnow():
        return {"status": "冷却中", "next_available_at": cooldown.next_available_at.isoformat()}
    
    agent.gold_coins += work.reward
    agent.experience += 10
    
    exp_needed = SETTINGS.get("experience_per_level", 100) * agent.level
    if agent.experience >= exp_needed:
        agent.level += 1
    
    if cooldown:
        cooldown.next_available_at = datetime.utcnow() + timedelta(minutes=work.cooldown_minutes)
    else:
        db.add(AgentWorkCooldown(agent_id=agent.id, work_id=work.id, next_available_at=datetime.utcnow() + timedelta(minutes=work.cooldown_minutes)))
    
    db.commit()
    return {"状态": "成功", "奖励": work.reward, "等级": agent.level, "经验": agent.experience}

@app.get("/work", response_model=List[schemas.WorkOut])
def list_work(db: Session = Depends(get_db)):
    return db.query(Work).all()

@app.post("/companies", response_model=schemas.CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(payload: schemas.CompanyCreate, db: Session = Depends(get_db)):
    company = Company(name=payload.name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company
