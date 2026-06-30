"""
MediSafe Clinic Ver-1 - 감사 로그 모델
개인정보보호법 제29조 제2항: '접속기록의 보관 및 위변조 방지 조치'
의료법 제23조의2: '전자의무기록의 생성·저장·관리 및 보안에 관한 사항'

요구사항:
  - 모든 개인정보 접근/수정/삭제/출력/다운로드 기록
  - 최소 2년 보관 (개인정보보호법 시행령 제30조)
  - WORM(Write Once Read Many): 수정/삭제 불가
  - 위변조 방지: 해시 체인 (각 레코드에 이전 레코드 해시 포함)
  - 정기 무결성 검증 지원
"""

import hashlib
import json
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    Enum, Index, ForeignKey
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditAction(str, PyEnum):
    # 인증
    LOGIN_SUCCESS    = "login_success"
    LOGIN_FAIL       = "login_fail"
    LOGOUT           = "logout"
    PASSWORD_CHANGE  = "password_change"
    ACCOUNT_LOCK     = "account_lock"
    ACCOUNT_UNLOCK   = "account_unlock"
    TOKEN_REVOKE     = "token_revoke"

    # 개인정보 접근 (의료법 제23조)
    PATIENT_DATA_VIEW   = "patient_data_view"
    PATIENT_DATA_EXPORT = "patient_data_export"
    EMR_ACCESS          = "emr_access"
    EMR_MODIFY          = "emr_modify"
    EMR_DELETE          = "emr_delete"
    EMR_PRINT           = "emr_print"

    # 시스템 관리
    ENDPOINT_REGISTER   = "endpoint_register"
    ENDPOINT_DELETE     = "endpoint_delete"
    AGENT_TOKEN_REVOKE  = "agent_token_revoke"
    USER_CREATE         = "user_create"
    USER_DEACTIVATE     = "user_deactivate"
    COMPLIANCE_UPDATE   = "compliance_update"
    TENANT_CONFIG       = "tenant_config"

    # 보안 이벤트
    USB_CONNECT       = "usb_connect"
    USB_BLOCK         = "usb_block"
    RANSOMWARE_DETECT = "ransomware_detect"
    ANOMALY_DETECT    = "anomaly_detect"


class AuditSeverity(str, PyEnum):
    INFO     = "info"      # 일반 접근
    WARNING  = "warning"   # 주의 필요
    CRITICAL = "critical"  # 즉시 조치 필요
    SECURITY = "security"  # 보안 위반


class AuditLog(Base):
    """
    감사 로그 - WORM 방식 (수정/삭제 금지)
    
    개인정보보호법 제29조 준수:
    - created_at: 서버 UTC 타임스탬프 (클라이언트 조작 불가)
    - record_hash: SHA-256(이전해시 + 현재데이터) 해시 체인
    - is_worm = True: ORM/API 레벨에서 UPDATE/DELETE 차단
    """
    __tablename__ = "audit_logs"

    id              = Column(Integer, primary_key=True, index=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    endpoint_id     = Column(Integer, ForeignKey("endpoints.id"), nullable=True)

    # 행위 정보
    action          = Column(Enum(AuditAction), nullable=False, index=True)
    severity        = Column(Enum(AuditSeverity), default=AuditSeverity.INFO)
    result          = Column(String(20), default="success")  # success / fail / blocked

    # 대상 리소스
    resource_type   = Column(String(50), nullable=True)   # endpoint / user / patient_record
    resource_id     = Column(String(100), nullable=True)  # 리소스 식별자
    resource_desc   = Column(Text, nullable=True)         # 사람이 읽을 수 있는 설명

    # 접속 정보
    ip_address      = Column(String(45), nullable=True)   # IPv6 대응
    user_agent      = Column(String(512), nullable=True)
    session_id      = Column(String(64), nullable=True)

    # 변경 데이터 (최소화 - 개인정보 미포함)
    old_value_hash  = Column(String(64), nullable=True)   # 변경 전 데이터 SHA-256
    new_value_hash  = Column(String(64), nullable=True)   # 변경 후 데이터 SHA-256

    # WORM 무결성
    record_hash     = Column(String(64), nullable=True)   # 해시 체인
    prev_hash       = Column(String(64), nullable=True)   # 이전 레코드 해시

    # 타임스탬프 (서버 생성, 수정 불가)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # 보관 정책
    retain_until    = Column(DateTime, nullable=True)     # 2년 후 자동 삭제 가능 날짜
    is_worm         = Column(Boolean, default=True)       # WORM 플래그 (항상 True)

    # 관계
    tenant   = relationship("Tenant", foreign_keys=[tenant_id])
    user     = relationship("User",   foreign_keys=[user_id])
    endpoint = relationship("Endpoint", foreign_keys=[endpoint_id])

    def compute_hash(self) -> str:
        """이 레코드의 무결성 해시 계산"""
        data = {
            "id":         self.id,
            "tenant_id":  self.tenant_id,
            "user_id":    self.user_id,
            "action":     str(self.action),
            "result":     self.result,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "prev_hash":  self.prev_hash,
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    __table_args__ = (
        Index("ix_audit_tenant_action", "tenant_id", "action"),
        Index("ix_audit_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_user_created", "user_id", "created_at"),
    )
