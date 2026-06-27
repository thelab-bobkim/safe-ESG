"""
MediSafe Clinic - 설정 관리 모듈
애플리케이션 전반의 환경 변수 및 설정값을 관리합니다.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 앱 기본 설정
    APP_NAME: str = "MediSafe Clinic"
    APP_VERSION: str = "0.1.0-beta"
    DEBUG: bool = True

    # 데이터베이스
    DATABASE_URL: str = "postgresql://medisafe:medisafe_secret_2024@localhost:5432/medisafe"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT 인증
    SECRET_KEY: str = "medisafe-super-secret-jwt-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8시간

    # CORS 허용 도메인 (프로덕션에서는 실제 도메인으로 변경)
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://medisafe.clinic",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
