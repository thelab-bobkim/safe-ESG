"""
MediSafe Clinic - SafeGuard 모듈 모델
규제 컴플라이언스 체크리스트 및 점검 결과를 관리합니다.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class RegulationType(str, enum.Enum):
    PRIVACY_ACT_29 = "privacy_act_29"   # 개인정보보호법 제29조
    MEDICAL_ACT_23 = "medical_act_23"   # 의료법 제23조
    EMR_CERT = "emr_cert"               # EMR 인증 기준
    ISMS_P = "isms_p"                   # ISMS-P


class CheckStatus(str, enum.Enum):
    PASS = "pass"          # 통과
    FAIL = "fail"          # 미충족
    PARTIAL = "partial"    # 부분 충족
    NA = "na"              # 해당 없음
    PENDING = "pending"    # 미확인


class ComplianceItem(Base):
    """
    규제 체크리스트 항목 마스터 테이블
    개인정보보호법 제29조, 의료법 제23조, EMR 인증 기준 항목들을 정의합니다.
    """
    __tablename__ = "compliance_items"

    id = Column(Integer, primary_key=True, index=True)
    regulation = Column(Enum(RegulationType), nullable=False, index=True)
    item_code = Column(String(20), nullable=False, unique=True, comment="항목 코드 (예: PA29-01)")
    title = Column(String(200), nullable=False, comment="항목 제목")
    description = Column(Text, nullable=True, comment="상세 설명")
    guidance = Column(Text, nullable=True, comment="이행 방법 가이드")
    is_mandatory = Column(Boolean, default=True, comment="필수 여부")
    weight = Column(Float, default=1.0, comment="점수 가중치")
    order_num = Column(Integer, default=0, comment="표시 순서")

    # 관계
    check_results = relationship("ComplianceCheckResult", back_populates="item")


class ComplianceCheck(Base):
    """병원별 컴플라이언스 점검 세션"""
    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # 점검 정보
    title = Column(String(100), default="정기 보안 점검", comment="점검 제목")
    checked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    checked_by_name = Column(String(50), nullable=True)

    # 점수 (0-100)
    total_score = Column(Float, default=0.0, comment="종합 컴플라이언스 점수")
    privacy_score = Column(Float, default=0.0, comment="개인정보보호법 점수")
    medical_score = Column(Float, default=0.0, comment="의료법 점수")
    emr_score = Column(Float, default=0.0, comment="EMR 인증 점수")

    pass_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    partial_count = Column(Integer, default=0)
    na_count = Column(Integer, default=0)

    notes = Column(Text, nullable=True, comment="총평 및 권고사항")

    # 타임스탬프
    checked_at = Column(DateTime, server_default=func.now())
    next_check_at = Column(DateTime, nullable=True, comment="다음 점검 예정일")

    # 관계
    tenant = relationship("Tenant", back_populates="compliance_checks")
    results = relationship("ComplianceCheckResult", back_populates="check", cascade="all, delete-orphan")


class ComplianceCheckResult(Base):
    """개별 체크리스트 항목 점검 결과"""
    __tablename__ = "compliance_check_results"

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(Integer, ForeignKey("compliance_checks.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("compliance_items.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    status = Column(Enum(CheckStatus), default=CheckStatus.PENDING)
    evidence = Column(Text, nullable=True, comment="이행 증빙 내용")
    note = Column(Text, nullable=True, comment="담당자 메모")
    due_date = Column(DateTime, nullable=True, comment="조치 기한")

    # 관계
    check = relationship("ComplianceCheck", back_populates="results")
    item = relationship("ComplianceItem", back_populates="check_results")
