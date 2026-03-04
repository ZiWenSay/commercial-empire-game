from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import SETTINGS


DATABASE_URL = SETTINGS.get("database_url", "sqlite:///./empire.db")

# For SQLite we need check_same_thread False when used with FastAPI
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    from sqlalchemy.orm import Session

    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
