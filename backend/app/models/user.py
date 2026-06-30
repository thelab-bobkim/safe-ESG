"""
MediSafe Clinic Ver-1 - 사용자 모델
개인정보보호법 제29조: 접근통제, 계정잠금, 비밀번호 정책 지원

Ver-1 변경:
  - failed_login_count: 로그인 실패 횟수 추적
  - locked_until: 계정 잠금 해제 시각
  - password_changed_at: 비밀번호 변경일 (90일 만료 정책)
  - must_change_password: 최초 로그인 시 강제 변경
  - last_login_ip: 마지막 접속 IP (이상 접속 탐지)
  - mfa_enabled: 2차 인증 (향후 확장)
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"  # 플랫폼 전체 관리자
    ADMIN      = "admin"       # 병원 관리자 (원장)
    STAFF      = "staff"       # 직원


class User(Base):
    """사용자 테이블 - tenant_id로 병원별 완전 격리"""
    __tablename__ = "users"

    id        = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True,
                       comment="소속 병원 (슈퍼관리자는 NULL)")

    # 인증 정보
    email           = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(512), nullable=False,
                             comment="Argon2id 해시 (Ver-1 이전: bcrypt)")

    # 프로필
    name  = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=True)
    role  = Column(Enum(UserRole), default=UserRole.STAFF)

    # 상태
    is_active            = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False,
                                  comment="최초 로그인 시 비밀번호 변경 강제")

    # 계정 잠금 (개인정보보호법 제29조 - 접근통제)
    failed_login_count = Column(Integer, default=0,
                                comment="연속 로그인 실패 횟수 (5회 초과 시 잠금)")
    locked_until       = Column(DateTime, nullable=True,
                                comment="계정 잠금 해제 시각 (NULL이면 잠금 없음)")

    # 비밀번호 정책 (90일 만료)
    password_changed_at = Column(DateTime, nullable=True,
                                 comment="마지막 비밀번호 변경일")

    # 접속 이력
    last_login_at  = Column(DateTime, nullable=True)
    last_login_ip  = Column(String(45), nullable=True,
                            comment="마지막 접속 IP (이상 접속 탐지)")

    # 2차 인증 (향후 TOTP 연동)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret  = Column(String(64), nullable=True)

    # 타임스탬프
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 관계
    tenant = relationship("Tenant", back_populates="users")

    @property
    def is_locked(self) -> bool:
        """계정 잠금 여부"""
        from datetime import datetime
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    @property
    def password_expired(self) -> bool:
        """비밀번호 90일 만료 여부"""
        from datetime import datetime, timedelta
        if not self.password_changed_at:
            return False
        return (datetime.utcnow() - self.password_changed_at).days > 90

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
