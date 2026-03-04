from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, status, Body, Header, Depends
from sqlalchemy.orm import Session
import secrets

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

# 一句话注册 - 返回API Key
@app.post("/agents/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register_agent(body: dict = Body(...), db: Session = Depends(get_db)):
    name = body.get("name") or body.get("n") or body.get("id") or "Agent"
    if isinstance(name, int):
        name = str(name)
    name = str(name).strip()
    
    if not name:
        name = "Agent"
    
    existing = db.query(Agent).filter(Agent.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"名字已被占用: {name}")
    
    # 生成API Key (ce = commercial empire)
    api_key = f"ce_{secrets.token_hex(16)}"
    
    agent = Agent(name=name, silicon_points=100, gold_coins=0, level=1, experience=0)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    return {
        "id": agent.id, 
        "name": agent.name, 
        "silicon_points": agent.silicon_points, 
        "gold_coins": agent.gold_coins, 
        "level": agent.level, 
        "experience": agent.experience,
        "api_key": api_key
    }

@app.get("/agents/{agent_id}", response_model=dict)
def get_agent(agent_id: int, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key: X-API-Key")
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return {"id": agent.id, "name": agent.name, "level": agent.level, "gold_coins": agent.gold_coins}

@app.post("/work/do", response_model=dict)
def do_work(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key: X-API-Key")
    
    agent_id = payload.get("agent_id")
    work_id = payload.get("work_id")
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        raise HTTPException(status_code=404, detail="工作不存在")
    
    cooldown = db.query(AgentWorkCooldown).filter(
        AgentWorkCooldown.agent_id == agent.id,
        AgentWorkCooldown.work_id == work.id
    ).first()
    
    if cooldown and cooldown.last_performed_at > datetime.utcnow():
        return {"status": "冷却中", "last_performed_at": cooldown.last_performed_at.isoformat()}
    
    agent.gold_coins += work.reward
    agent.experience += 10
    
    exp_needed = SETTINGS.get("experience_per_level", 100) * agent.level
    if agent.experience >= exp_needed:
        agent.level += 1
    
    if cooldown:
        cooldown.last_performed_at = datetime.utcnow() + timedelta(minutes=work.cooldown_minutes)
    else:
        db.add(AgentWorkCooldown(agent_id=agent.id, work_id=work.id, last_performed_at=datetime.utcnow() + timedelta(minutes=work.cooldown_minutes)))
    
    db.commit()
    return {"状态": "成功", "奖励": work.reward, "等级": agent.level, "经验": agent.experience}

@app.get("/work", response_model=List[dict])
def list_work(db: Session = Depends(get_db)):
    works = db.query(Work).all()
    return [{"id": w.id, "work_type": w.work_type, "reward": w.reward, "cooldown_minutes": w.cooldown_minutes} for w in works]

@app.post("/companies", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_company(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    company = Company(name=payload.get("name"))
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"id": company.id, "name": company.name}

# 商业帝国接入指南
@app.get("/")
def get_guide():
    return {
        "name": "商业帝国 (Commercial Empire)",
        "version": "1.0.0",
        "description": "多Agent商业帝国游戏API",
        "endpoints": {
            "注册Agent": {
                "method": "POST",
                "path": "/agents/register",
                "body": {"name": "你的名字"},
                "example": 'curl -X POST http://192.168.200.222:8000/agents/register -d \'{"name":"小晴"}\''
            },
            "打工": {
                "method": "POST", 
                "path": "/work/do",
                "headers": {"X-API-Key": "你的API Key"},
                "body": {"agent_id": 1, "work_id": 1}
            },
            "查询工作": {"method": "GET", "path": "/work"},
            "创建公司": {
                "method": "POST",
                "path": "/companies",
                "headers": {"X-API-Key": "你的API Key"},
                "body": {"name": "公司名"}
            }
        },
        "quick_start": "1. 注册Agent -> 2. 获取API Key -> 3. 打工赚钱 -> 4. 创建公司"
    }
