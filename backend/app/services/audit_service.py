"""
MediSafe Clinic Ver-1 - 감사 로그 서비스
모든 API에서 호출하는 중앙집중식 감사 로그 기록
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models.audit import AuditLog, AuditAction, AuditSeverity


def write_audit(
    db: Session,
    action: AuditAction,
    *,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    result: str = "success",
    severity: AuditSeverity = AuditSeverity.INFO,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_desc: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AuditLog:
    """
    감사 로그 기록 (해시 체인 포함)
    
    모든 중요 행위에서 호출:
      - 로그인/로그아웃
      - 개인정보 접근
      - 데이터 수정/삭제
      - 보안 이벤트
    """
    # 이전 레코드 해시 조회 (체인 연결)
    prev_log = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    prev_hash = prev_log.record_hash if prev_log else "genesis"

    # 보관 기한: 2년 (개인정보보호법 시행령 제30조)
    retain_until = datetime.utcnow() + timedelta(days=365 * 2)

    log = AuditLog(
        tenant_id     = tenant_id,
        user_id       = user_id,
        endpoint_id   = endpoint_id,
        action        = action,
        severity      = severity,
        result        = result,
        ip_address    = ip_address,
        user_agent    = user_agent,
        resource_type = resource_type,
        resource_id   = str(resource_id) if resource_id else None,
        resource_desc = resource_desc,
        session_id    = session_id,
        prev_hash     = prev_hash,
        retain_until  = retain_until,
        is_worm       = True,
        created_at    = datetime.utcnow(),
    )
    db.add(log)
    db.flush()  # id 먼저 확보

    # 해시 체인 계산 및 저장
    log.record_hash = log.compute_hash()
    db.commit()
    return log


def verify_audit_chain(db: Session, tenant_id: int) -> dict:
    """
    감사 로그 무결성 검증
    개인정보보호법 제29조 - 접속기록 위변조 방지 점검
    """
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.id.asc())
        .all()
    )

    total        = len(logs)
    tampered     = []
    chain_broken = []

    for i, log in enumerate(logs):
        # 해시 재계산
        expected = log.compute_hash()
        if log.record_hash != expected:
            tampered.append(log.id)

        # 체인 연속성 확인
        if i > 0:
            if log.prev_hash != logs[i-1].record_hash:
                chain_broken.append(log.id)

    return {
        "total":         total,
        "tampered":      tampered,
        "chain_broken":  chain_broken,
        "integrity_ok":  len(tampered) == 0 and len(chain_broken) == 0,
        "checked_at":    datetime.utcnow().isoformat(),
    }
