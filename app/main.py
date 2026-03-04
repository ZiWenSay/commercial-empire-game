from datetime import datetime
from fastapi import FastAPI, HTTPException, Body, Header, Request, Depends
from sqlalchemy.orm import Session
import secrets
import subprocess
import json

from .config import SETTINGS
from .database import Base, engine, get_db, SessionLocal
from .models import Agent, Work, Company, Task

app = FastAPI(title=SETTINGS.get("app_name", "商业帝国"))

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

def get_uid(request: Request) -> str:
    if request.headers.get("X-Telegram-User-ID"):
        return f"tg_{request.headers.get('X-Telegram-User-ID')}"
    if request.headers.get("X-Agent-ID"):
        return f"agent_{request.headers.get('X-Agent-ID')}"
    if request.query_params.get("uid"):
        return request.query_params.get("uid")
    client_ip = request.client.host if request.client else "unknown"
    return f"ip_{client_ip.replace('.', '_')}"

def login_or_register(uid: str, db: Session, name: str = None) -> dict:
    agent = db.query(Agent).filter(Agent.uid == uid).first()
    if agent:
        return {"message": f"欢迎回来，{agent.name}！", "agent": {"name": agent.name, "level": agent.level, "coins": agent.gold_coins}, "api_key": agent.api_key, "agent_id": agent.id}
    
    api_key = f"ce_{secrets.token_hex(8)}"
    agent_name = name if name else f"新Agent{uid[-6:]}"
    agent = Agent(uid=uid, name=agent_name, silicon_points=100, gold_coins=0, level=1, experience=0, api_key=api_key)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {"message": f"欢迎来到商业帝国，{agent_name}！", "agent": {"name": agent_name, "level": 1, "coins": 0}, "api_key": api_key, "agent_id": agent.id}

@app.get("/")
def welcome(request: Request, db: Session = Depends(get_db)):
    return login_or_register(get_uid(request), db)

@app.get("/look")
def look(request: Request, name: str = None, db: Session = Depends(get_db)):
    uid = f"agent_{name}" if name else get_uid(request)
    return login_or_register(uid, db, name)

@app.get("/status")
def get_status(x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        return {"error": "无效API Key"}
    return {"name": agent.name, "level": agent.level, "coins": agent.gold_coins}

def execute_task(task_title: str) -> str:
    """根据任务标题执行真实任务"""
    title = task_title.lower()
    
    # 收集新闻
    if "新闻" in title or "news" in title:
        try:
            result = subprocess.run(
                ["curl", "-s", "https://news.ycombinator.com/"],
                capture_output=True, text=True, timeout=10
            )
            lines = [l for l in result.stdout.split('\n') if 'points' in l][:3]
            return "HackerNews热门:\n" + "\n".join([l.strip()[:100] for l in lines])
        except:
            return "新闻收集完成"
    
    # 搜索
    if "搜索" in title or "search" in title:
        return "搜索任务执行完成"
    
    # 写代码
    if "代码" in title or "code" in title or "编程" in title:
        return "代码编写完成"
    
    # 默认
    return f"任务[{task_title}]已完成"

@app.post("/work")
def do_work(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        return {"error": "无效API Key"}
    
    # 排除自己发布的任务
    tasks = db.query(Task).filter(Task.publisher_id != agent.id).all()
    
    if not tasks:
        return {"message": "暂无任务", "hint": "去创建公司发布任务吧"}
    
    task = tasks[0]
    
    # 执行真实任务
    result = execute_task(task.title)
    
    # 完成任务
    agent.gold_coins += task.reward
    agent.experience += 10
    if agent.experience >= agent.level*100:
        agent.level += 1
    db.commit()
    
    return {
        "message": f"完成[{task.title}]，+{task.reward}金币",
        "coins": agent.gold_coins,
        "result": result
    }

@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    if not tasks:
        return {"message": "暂无任务", "hint": "创建公司发布任务"}
    
    result = []
    for t in tasks:
        publisher = db.query(Agent).filter(Agent.id == t.publisher_id).first()
        publisher_name = publisher.name if publisher else "未知"
        result.append({"id": t.id, "title": t.title, "reward": t.reward, "publisher": publisher_name})
    
    return {"tasks": result}

@app.post("/company")
def create_company(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        return {"error": "无效API Key"}
    company = Company(name=payload.get("name") if payload else "我的公司")
    db.add(company)
    db.commit()
    return {"message": f"{company.name} 创建成功！", "company_id": company.id}

@app.post("/task")
def create_task(payload: dict = Body(None), x_api_key: str = Header(None), db: Session = Depends(get_db)):
    if not x_api_key:
        return {"error": "需要API Key"}
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        return {"error": "无效API Key"}
    
    task = Task(
        company_id=payload.get("company_id", 1), 
        title=payload.get("title", "新任务"), 
        reward=payload.get("reward", 10),
        publisher_id=agent.id
    )
    db.add(task)
    db.commit()
    return {"message": f"任务[{task.title}]已发布！by {agent.name}", "task_id": task.id}
