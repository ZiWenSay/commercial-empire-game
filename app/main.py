from datetime import datetime
from typing import List
from fastapi import FastAPI, HTTPException, Body, Header, Depends, Query, Request
from sqlalchemy.orm import Session
import secrets

from .config import SETTINGS
from .database import Base, engine, get_db, SessionLocal
from .models import Agent, Work, Company, Task

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

def get_uid(request: Request) -> str:
    """自动获取唯一标识 - 优先从Header获取，其次用IP"""
    # 1. 从Telegram @username 获取
    if request.headers.get("X-Telegram-User-ID"):
        return f"tg_{request.headers.get('X-Telegram-User-ID')}"
    # 2. 从URL参数获取
    if request.query_params.get("uid"):
        return request.query_params.get("uid")
    # 3. 用客户端IP
    client_ip = request.client.host if request.client else "unknown"
    return f"ip_{client_ip.replace('.', '_')}"

@app.get("/")
def welcome(request: Request, db: Session = Depends(get_db)):
    uid = get_uid(request)
    
    agent = db.query(Agent).filter(Agent.uid == uid).first()
    if agent:
        task_count = db.query(Task).count()
        msg = f"👋 欢迎回来，{agent.name}！"
        if task_count > 0:
            msg += f" 📋 有 {task_count} 个任务"
        return {
            "message": msg,
            "agent": {"name": agent.name, "level": agent.level, "coins": agent.gold_coins, "exp": agent.experience},
            "api_key": agent.api_key,
            "hint": "接任务 or 创建公司"
        }
    
    # 新用户
    api_key = f"ce_{secrets.token_hex(8)}"
    name = f"新用户{uid[-4:]}"
    agent = Agent(uid=uid, name=name, silicon_points=100, gold_coins=0, level=1, experience=0, api_key=api_key)
    db.add(agent)
    db.commit()
    
    return {
        "message": f"🌟 注册成功！{name}，欢迎来到商业帝国！",
        "agent": {"name": name, "level": 1, "coins": 0},
        "api_key": api_key,
        "hint": "查看任务 or 创建公司"
    }

@app.get("/status")
def get_status(x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key", "hint": "访问首页自动登录"}
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        return {"error": "无效API Key"}
    return {"name": agent.name, "level": agent.level, "coins": agent.gold_coins, "exp": f"{agent.experience}/{agent.level*100}"}

@app.post("/work")
def do_work(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key", "hint": "访问首页自动登录"}
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        return {"error": "无效API Key"}
    tasks = db.query(Task).all()
    if not tasks:
        return {"message": "⏳ 暂无任务", "hint": "创建公司发布任务"}
    task = tasks[0]
    agent.gold_coins += task.reward_per_agent
    agent.experience += 10
    if agent.experience >= agent.level*100:
        agent.level += 1
    db.commit()
    return {"message": f"✅ 完成[{task.title}]，+{task.reward_per_agent}金币", "coins": agent.gold_coins, "level": agent.level}

@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    if not tasks:
        return {"message": "📋 暂无任务", "hint": "创建公司发布任务"}
    return {"tasks": [{"title": t.title, "reward": t.reward_per_agent} for t in tasks]}

@app.post("/company")
def create_company(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    company = Company(name=payload.get("name") if payload else "我的公司")
    db.add(company)
    db.commit()
    return {"message": f"🏢 {company.name} 创建成功！", "hint": "发布任务"}

@app.post("/task")
def create_task(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    task = Task(company_id=payload.get("company_id", 1), title=payload.get("title", "新任务"), reward_per_agent=payload.get("reward", 10), max_agents=5)
    db.add(task)
    db.commit()
    return {"message": f"📋 任务[{task.title}]已发布！", "reward": task.reward_per_agent}
