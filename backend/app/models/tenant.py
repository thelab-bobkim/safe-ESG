"""
MediSafe Clinic - 테넌트(병원) 모델
각 병원이 하나의 테넌트를 구성합니다. 모든 데이터는 tenant_id로 완전 격리됩니다.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class SubscriptionPlan(str, enum.Enum):
    BASIC = "basic"        # 기본 (4.9만원/월) - 1~3대
    STANDARD = "standard"  # 표준 (14.9만원/월) - 3~10대
    PRO = "pro"            # 전문 (34.9만원/월) - 10대 이상


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"      # 활성
    TRIAL = "trial"        # 무료 체험 중 (30일)
    SUSPENDED = "suspended"  # 정지
    EXPIRED = "expired"    # 만료


class Tenant(Base):
    """병원(테넌트) 정보 테이블"""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)

    # 병원 기본 정보
    name = Column(String(100), nullable=False, comment="병원명")
    business_number = Column(String(20), unique=True, nullable=True, comment="사업자등록번호")
    address = Column(Text, nullable=True, comment="병원 주소")
    phone = Column(String(20), nullable=True, comment="병원 대표 전화")
    email = Column(String(100), nullable=True, comment="병원 대표 이메일")

    # 구독 정보
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.STANDARD, comment="구독 플랜")
    status = Column(Enum(TenantStatus), default=TenantStatus.TRIAL, comment="서비스 상태")
    trial_ends_at = Column(DateTime, nullable=True, comment="무료 체험 종료일")
    subscription_starts_at = Column(DateTime, nullable=True, comment="구독 시작일")
    subscription_ends_at = Column(DateTime, nullable=True, comment="구독 종료일")

    # 설정
    max_endpoints = Column(Integer, default=10, comment="최대 등록 가능 엔드포인트 수")
    is_active = Column(Boolean, default=True)

    # 타임스탬프
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 관계
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    endpoints = relationship("Endpoint", back_populates="tenant", cascade="all, delete-orphan")
    access_logs = relationship("AccessLog", back_populates="tenant", cascade="all, delete-orphan")
    compliance_checks = relationship("ComplianceCheck", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant {self.name}>"
