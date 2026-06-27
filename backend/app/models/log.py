"""
MediSafe Clinic - SafeLog 모듈 모델
EMR 접속 기록 및 시스템 이벤트 로그를 WORM 방식으로 보존합니다.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class LogEventType(str, enum.Enum):
    EMR_ACCESS = "emr_access"          # EMR 접속
    EMR_QUERY = "emr_query"            # 환자 기록 조회
    EMR_MODIFY = "emr_modify"          # 환자 기록 수정
    EMR_DELETE = "emr_delete"          # 환자 기록 삭제 (고위험)
    LOGIN_SUCCESS = "login_success"    # 로그인 성공
    LOGIN_FAIL = "login_fail"          # 로그인 실패
    FILE_ACCESS = "file_access"        # 파일 접근
    POLICY_CHANGE = "policy_change"    # 보안 정책 변경 (감사 필수)
    ADMIN_ACTION = "admin_action"      # 관리자 행위
    SYSTEM_EVENT = "system_event"      # 시스템 이벤트
    SECURITY_ALERT = "security_alert"  # 보안 경고


class LogSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AccessLog(Base):
    """
    접속 로그 테이블 (WORM - 삭제/수정 불가)
    개인정보보호법 제29조 및 의료법 제23조 준수를 위한 핵심 데이터입니다.
    이 테이블의 레코드는 절대 삭제하거나 수정하지 않습니다.
    """
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # 행위자 정보
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="사용자 ID")
    user_name = Column(String(100), nullable=True, comment="사용자명 (삭제 후에도 보존)")
    user_email = Column(String(100), nullable=True, comment="이메일")
    ip_address = Column(String(45), nullable=True, comment="접속 IP")
    endpoint_hostname = Column(String(100), nullable=True, comment="접속 PC 이름")

    # 이벤트 정보
    event_type = Column(Enum(LogEventType), nullable=False, index=True)
    severity = Column(Enum(LogSeverity), default=LogSeverity.INFO)
    resource = Column(String(200), nullable=True, comment="접근한 리소스 (환자ID, 파일명 등)")
    action = Column(String(100), nullable=True, comment="수행한 행위")
    result = Column(String(20), default="success", comment="결과 (success/fail/blocked)")
    description = Column(Text, nullable=True, comment="상세 설명")
    extra_data = Column(JSON, nullable=True, comment="추가 메타데이터")

    # WORM 보존 플래그 - 이 레코드는 절대 삭제/수정하지 않습니다
    is_worm = Column(Boolean, default=True, comment="WORM 보존 플래그")
    occurred_at = Column(DateTime, server_default=func.now(), index=True, comment="발생 시각")

    # 관계
    tenant = relationship("Tenant", back_populates="access_logs")

    def __repr__(self):
        return f"<AccessLog {self.event_type} by {self.user_name} at {self.occurred_at}>"
