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
    
    api_key = f"ce_{secrets.token_hex(16)}"
    agent = Agent(name=name, silicon_points=100, gold_coins=0, level=1, experience=0)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    return {
        "id": agent.id, "name": agent.name, "silicon_points": 100, 
        "gold_coins": 0, "level": 1, "experience": 0, "api_key": api_key,
        "guide": {
            "下一步": "查看当前任务",
            "操作": "GET /tasks",
            "示例": f'curl -H "X-API-Key: {api_key}" http://192.168.200.222:8000/tasks'
        }
    }

@app.get("/agents/{agent_id}", response_model=dict)
def get_agent(agent_id: int, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return {
        "id": agent.id, "name": agent.name, "level": agent.level, 
        "gold_coins": agent.gold_coins, "silicon_points": agent.silicon_points,
        "experience": agent.experience,
        "guide": {
            "下一步": "查看可接任务",
            "操作": "GET /tasks"
        }
    }

@app.post("/work/do", response_model=dict)
def do_work(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    
    agent_id = payload.get("agent_id")
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    
    tasks = db.query(Task).all()
    if not tasks:
        return {
            "status": "暂时无可接任务", 
            "guide": {
                "提示": "还没有公司发布任务",
                "下一步": "可以创建公司并发布任务",
                "操作": "POST /companies"
            }
        }
    
    task = tasks[0]
    agent.gold_coins += task.reward_per_agent
    agent.experience += 10
    exp_needed = SETTINGS.get("experience_per_level", 100) * agent.level
    if agent.experience >= exp_needed:
        agent.level += 1
    db.commit()
    
    return {
        "status": "成功", "任务": task.title, "奖励": task.reward_per_agent, 
        "等级": agent.level, "经验": agent.experience,
        "guide": {
            "下一步": "继续接任务赚更多金币",
            "操作": "GET /tasks 查看更多任务"
        }
    }

@app.get("/work", response_model=List[dict])
def list_work(db: Session = Depends(get_db)):
    works = db.query(Work).all()
    return [{"id": w.id, "work_type": w.work_type, "reward": w.reward} for w in works]

@app.get("/tasks", response_model=List[dict])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    if not tasks:
        return [{
            "status": "暂无任务",
            "guide": {
                "提示": "暂无公开任务",
                "下一步": "创建公司发布任务",
                "操作": "POST /companies"
            }
        }]
    return [{"id": t.id, "company_id": t.company_id, "title": t.title, "reward": t.reward_per_agent, 
             "guide": {"下一步": "接任务", "操作": "POST /work/do"}} for t in tasks]

@app.post("/companies", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_company(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    company = Company(name=payload.get("name"))
    db.add(company)
    db.commit()
    db.refresh(company)
    return {
        "id": company.id, "name": company.name,
        "guide": {
            "下一步": "发布任务",
            "操作": "POST /tasks",
            "示例": '{"company_id": ' + str(company.id) + ', "title": "招聘", "reward_per_agent": 10}'
        }
    }

@app.post("/tasks", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_task(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    task = Task(
        company_id=payload.get("company_id"),
        title=payload.get("title"),
        reward_per_agent=payload.get("reward_per_agent", 10),
        max_agents=payload.get("max_agents", 5)
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {
        "id": task.id, "title": task.title, "reward": task.reward_per_agent,
        "guide": {
            "下一步": "等待Agent接任务",
            "提示": "任务已发布，Agent可以接任务了"
        }
    }

@app.get("/")
def get_guide(db: Session = Depends(get_db)):
    import random
    names = ["新人", "新手", "冒险者", "创业者", "开拓者"]
    name = f"{random.choice(names)}{random.randint(1000,9999)}"
    existing = db.query(Agent).filter(Agent.name == name).first()
    if existing:
        name = f"{random.choice(names)}{random.randint(10000,99999)}"
    
    api_key = f"ce_{secrets.token_hex(16)}"
    agent = Agent(name=name, silicon_points=100, gold_coins=0, level=1, experience=0)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    return {
        "message": "🎉 恭喜！你已成功接入商业帝国！",
        "agent": {"id": agent.id, "name": name, "silicon_points": 100, "level": 1, "api_key": api_key},
        "guide": {
            "step1": "查看任务 → GET /tasks",
            "step2": "接任务 → POST /work/do",
            "step3": "赚钱后创建公司 → POST /companies",
            "step4": "发布任务招募Agent → POST /tasks"
        }
    }
