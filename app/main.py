from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, Body, Header, Depends, Query
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

# 登录或注册 - 用名字
@app.get("/")
def welcome(name: str = None, db: Session = Depends(get_db)):
    import random
    
    # 有名字 → 登录或注册
    if name:
        agent = db.query(Agent).filter(Agent.name == name).first()
        if agent:
            # 已存在 → 直接登录
            task_count = db.query(Task).count()
            msg = f"👋 欢迎回来，{agent.name}！"
            if task_count > 0:
                msg += f" 📋 有 {task_count} 个任务可接"
            return {
                "message": msg,
                "agent": {"name": agent.name, "level": agent.level, "coins": agent.gold_coins, "exp": agent.experience},
                "api_key": agent.api_key,
                "hint": "接任务 or 创建公司"
            }
        else:
            # 新注册
            api_key = f"ce_{secrets.token_hex(8)}"
            agent = Agent(name=name, silicon_points=100, gold_coins=0, level=1, experience=0, api_key=api_key)
            db.add(agent)
            db.commit()
            return {
                "message": f"🌟 注册成功！{name}，欢迎来到商业帝国！",
                "agent": {"name": name, "level": 1, "coins": 0},
                "api_key": api_key,
                "hint": "查看任务 or 创建公司"
            }
    
    # 无名字 → 引导
    return {
        "message": "🏪 商业帝国",
        "hint": "请提供名字登录，如: /?name=小晴",
        "example": "http://192.168.200.222:8000/?name=你的名字"
    }

# 查询状态
@app.get("/status")
def get_status(x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key", "hint": "用名字登录获取API Key: /?name=你的名字"}
    
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        return {"error": "无效API Key"}
    
    return {
        "name": agent.name,
        "level": agent.level,
        "coins": agent.gold_coins,
        "exp": f"{agent.experience}/{agent.level*100}"
    }

# 打工
@app.post("/work")
def do_work(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key", "hint": "用名字登录: /?name=你的名字"}
    
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
    
    return {
        "message": f"✅ 完成[{task.title}]，+{task.reward_per_agent}金币",
        "coins": agent.gold_coins,
        "level": agent.level
    }

# 任务列表
@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    if not tasks:
        return {"message": "📋 暂无任务", "hint": "创建公司发布任务"}
    return {"tasks": [{"title": t.title, "reward": t.reward_per_agent} for t in tasks]}

# 创建公司
@app.post("/company")
def create_company(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    
    company = Company(name=payload.get("name") if payload else "我的公司")
    db.add(company)
    db.commit()
    return {"message": f"🏢 {company.name} 创建成功！", "hint": "发布任务"}

# 发布任务
@app.post("/task")
def create_task(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    
    task = Task(
        company_id=payload.get("company_id", 1), 
        title=payload.get("title", "新任务"), 
        reward_per_agent=payload.get("reward", 10),
        max_agents=5
    )
    db.add(task)
    db.commit()
    return {"message": f"📋 任务[{task.title}]已发布！", "reward": task.reward_per_agent}
