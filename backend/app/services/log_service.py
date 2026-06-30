"""
MediSafe Clinic - SafeLog 자동 기록 서비스
모든 보안 이벤트를 AccessLog(SafeLog)에 자동으로 기록합니다.

개인정보보호법 제29조 제5호: 접속 기록 보관 (6개월 이상)
의료법 제23조: 전자의무기록 접근 기록 보관
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.models.log import AccessLog, LogEventType, LogSeverity


def record(
    db: Session,
    *,
    tenant_id: int,
    event_type: LogEventType,
    severity: LogSeverity = LogSeverity.INFO,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    endpoint_hostname: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    result: str = "success",
    description: Optional[str] = None,
    extra_data: Optional[dict] = None,
    commit: bool = False,
):
    """SafeLog에 보안 이벤트를 기록합니다."""
    log = AccessLog(
        tenant_id=tenant_id,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        ip_address=ip_address,
        endpoint_hostname=endpoint_hostname,
        event_type=event_type,
        severity=severity,
        resource=resource,
        action=action,
        result=result,
        description=description,
        extra_data=extra_data or {},
        is_worm=True,
    )
    db.add(log)
    if commit:
        db.commit()
    return log


# ── 편의 함수들 ──────────────────────────────────────────────

def log_login_success(db, tenant_id, user_id, user_name, user_email, ip, commit=False):
    return record(db,
        tenant_id=tenant_id, user_id=user_id,
        user_name=user_name, user_email=user_email,
        ip_address=ip,
        event_type=LogEventType.LOGIN_SUCCESS,
        severity=LogSeverity.INFO,
        resource="MediSafe 대시보드",
        action="로그인",
        result="success",
        description=f"{user_name}({user_email}) 로그인 성공 — IP: {ip}",
        commit=commit,
    )


def log_login_fail(db, tenant_id, email, ip, reason="비밀번호 불일치", commit=False):
    return record(db,
        tenant_id=tenant_id,
        user_email=email,
        ip_address=ip,
        event_type=LogEventType.LOGIN_FAIL,
        severity=LogSeverity.WARNING,
        resource="MediSafe 대시보드",
        action="로그인 시도",
        result="fail",
        description=f"로그인 실패 — {email} | 사유: {reason} | IP: {ip}",
        commit=commit,
    )


def log_account_locked(db, tenant_id, email, ip, commit=False):
    return record(db,
        tenant_id=tenant_id,
        user_email=email,
        ip_address=ip,
        event_type=LogEventType.SECURITY_ALERT,
        severity=LogSeverity.CRITICAL,
        resource="계정 보안",
        action="계정 잠금",
        result="blocked",
        description=f"계정 잠금 — {email} (5회 연속 실패) | IP: {ip}",
        commit=commit,
    )


def log_agent_heartbeat(db, tenant_id, endpoint_id, hostname, ip, score, issues: list, commit=False):
    severity = LogSeverity.INFO
    desc_parts = [f"PC 보안 상태 전송 — {hostname} ({ip}) | 보안점수: {score}점"]
    if issues:
        severity = LogSeverity.WARNING
        desc_parts.append(f"보안 이슈: {', '.join(issues)}")
    return record(db,
        tenant_id=tenant_id,
        endpoint_hostname=hostname,
        ip_address=ip,
        event_type=LogEventType.SYSTEM_EVENT,
        severity=severity,
        resource=f"PC: {hostname}",
        action="에이전트 보안 상태 보고",
        result="success",
        description=" | ".join(desc_parts),
        extra_data={"endpoint_id": endpoint_id, "score": score, "issues": issues},
        commit=commit,
    )


def log_usb_event(db, tenant_id, endpoint_id, hostname, device_name, action, blocked, commit=False):
    return record(db,
        tenant_id=tenant_id,
        endpoint_hostname=hostname,
        event_type=LogEventType.SECURITY_ALERT,
        severity=LogSeverity.WARNING if not blocked else LogSeverity.CRITICAL,
        resource=f"USB: {device_name}",
        action=f"USB {action}",
        result="blocked" if blocked else "detected",
        description=f"USB {'차단' if blocked else '감지'} — {hostname} | 장치: {device_name} | 동작: {action}",
        extra_data={"endpoint_id": endpoint_id, "blocked": blocked},
        commit=commit,
    )


def log_password_change(db, tenant_id, user_id, user_name, user_email, ip, commit=False):
    return record(db,
        tenant_id=tenant_id,
        user_id=user_id, user_name=user_name, user_email=user_email,
        ip_address=ip,
        event_type=LogEventType.POLICY_CHANGE,
        severity=LogSeverity.INFO,
        resource="계정 보안",
        action="비밀번호 변경",
        result="success",
        description=f"비밀번호 변경 완료 — {user_email} | IP: {ip}",
        commit=commit,
    )


def log_endpoint_registered(db, tenant_id, user_id, user_name, hostname, ip, os_type, commit=False):
    return record(db,
        tenant_id=tenant_id,
        user_id=user_id, user_name=user_name,
        ip_address=ip,
        endpoint_hostname=hostname,
        event_type=LogEventType.ADMIN_ACTION,
        severity=LogSeverity.INFO,
        resource=f"PC: {hostname}",
        action="PC 등록",
        result="success",
        description=f"새 PC 등록 — {hostname} ({os_type}) | IP: {ip}",
        commit=commit,
    )


def log_endpoint_deactivated(db, tenant_id, user_id, user_name, hostname, commit=False):
    return record(db,
        tenant_id=tenant_id,
        user_id=user_id, user_name=user_name,
        endpoint_hostname=hostname,
        event_type=LogEventType.ADMIN_ACTION,
        severity=LogSeverity.WARNING,
        resource=f"PC: {hostname}",
        action="PC 비활성화",
        result="success",
        description=f"PC 비활성화 — {hostname}",
        commit=commit,
    )
