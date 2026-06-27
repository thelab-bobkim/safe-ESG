"""
MediSafe Clinic - 사용자 모델
원장(admin), 직원(staff), 슈퍼관리자(superadmin) 역할을 지원합니다.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"  # 플랫폼 전체 관리자
    ADMIN = "admin"            # 병원 관리자 (원장)
    STAFF = "staff"            # 직원 (원무 등)


class User(Base):
    """사용자 테이블 - tenant_id로 병원별 격리"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True,
                       comment="소속 병원 (슈퍼관리자는 NULL)")

    # 인증 정보
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200), nullable=False)

    # 프로필
    name = Column(String(50), nullable=False, comment="이름")
    phone = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.STAFF, comment="역할")

    # 상태
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 관계
    tenant = relationship("Tenant", back_populates="users")

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
