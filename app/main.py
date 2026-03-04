from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, status, Body, Header, Depends
from sqlalchemy.orm import Session
import secrets

from .config import SETTINGS
from .database import Base, engine, get_db, SessionLocal
from .models import Agent, Work, Company, Task, AgentWorkCooldown

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

# 友好版接入
@app.get("/")
def welcome(db: Session = Depends(get_db)):
    import random
    names = ["创业者", "开拓者", "梦想家", "冒险家", "奋斗者", "追梦人"]
    adjectives = ["勇敢的", "智慧的", "勤劳的", "幸运的", "热情的", "执着的"]
    
    adj = random.choice(adjectives)
    name = f"{adj}{random.choice(names)}{random.randint(1,99)}"
    
    existing = db.query(Agent).filter(Agent.name == name).first()
    if existing:
        name = f"{random.choice(names)}{random.randint(100,999)}"
    
    api_key = f"ce_{secrets.token_hex(8)}"
    agent = Agent(name=name, silicon_points=100, gold_coins=0, level=1, experience=0)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    # 检查是否有任务
    task_count = db.query(Task).count()
    
    msg = f"🌟 欢迎来到商业帝国，{name}！"
    if task_count > 0:
        msg += f"\n📋 当前有 {task_count} 个任务可接！"
        hint = "说「我要接任务」开始赚钱！"
    else:
        msg += "\n💡 暂无任务发布，快去创建公司吧！"
        hint = "说「创建公司」自己当老板！"
    
    return {
        "message": msg,
        "hint": hint,
        "agent": {"name": name, "level": 1, "coins": 0},
        "quick": ["查看任务", "创建公司", "我的状态"]
    }

# ... 保留其他端点 ...
@app.post("/agents/register")
def register_agent(body: dict = Body(...), db: Session = Depends(get_db)):
    name = body.get("name") or body.get("n") or "Agent"
    name = str(name).strip()
    if not name: name = "Agent"
    
    existing = db.query(Agent).filter(Agent.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"名字已被占用")
    
    api_key = f"ce_{secrets.token_hex(8)}"
    agent = Agent(name=name, silicon_points=100, gold_coins=0, level=1, experience=0)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    return {
        "message": f"✅ 注册成功！{name}，欢迎加入商业帝国！",
        "agent": {"id": agent.id, "name": name, "level": 1, "coins": 0},
        "hint": "查看任务 or 创建公司"
    }

@app.get("/agents/{agent_id}")
def get_agent(agent_id: int, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="找不到")
    
    return {
        "name": agent.name,
        "level": agent.level,
        "coins": agent.gold_coins,
        "exp": f"{agent.experience}/{agent.level*100}"
    }

@app.post("/work/do")
def do_work(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    
    agent_id = payload.get("agent_id")
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="找不到")
    
    tasks = db.query(Task).all()
    if not tasks:
        return {"message": "⏳ 暂时没有任务可接", "hint": "创建公司发布任务吧！"}
    
    task = tasks[0]
    agent.gold_coins += task.reward_per_agent
    agent.experience += 10
    if agent.experience >= agent.level*100:
        agent.level += 1
    db.commit()
    
    return {
        "message": f"✅ 完成[{task.title}]，获得 {task.reward_per_agent} 金币！",
        "coins": agent.gold_coins,
        "exp": agent.experience,
        "level": agent.level
    }

@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    if not tasks:
        return {"message": "📋 暂无任务", "hint": "创建公司发布任务"}
    return {"tasks": [{"title": t.title, "reward": t.reward_per_agent} for t in tasks]}

@app.post("/companies")
def create_company(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    company = Company(name=payload.get("name"))
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"message": f"🏢 {company.name} 创建成功！", "hint": "发布任务招募Agent"}

@app.post("/tasks")
def create_task(payload: dict, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="需要API Key")
    task = Task(company_id=payload.get("company_id"), title=payload.get("title"), reward_per_agent=payload.get("reward_per_agent", 10), max_agents=5)
    db.add(task)
    db.commit()
    return {"message": f"📋 任务[{task.title}]已发布！", "reward": task.reward_per_agent}
