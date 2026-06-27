"""
MediSafe Clinic - 데이터베이스 연결 관리
SQLAlchemy ORM 기반 멀티테넌트 PostgreSQL 연결을 관리합니다.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

from app.core.config import settings

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # 연결 상태 확인
    pool_size=10,
    max_overflow=20,
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 베이스 클래스
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 의존성 주입용 데이터베이스 세션 생성기
    요청마다 새로운 세션을 생성하고 완료 후 자동으로 닫습니다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
