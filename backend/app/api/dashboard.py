"""
MediSafe Clinic - 대시보드 API
보안 점수, 모듈 요약, 최근 이벤트 등 대시보드 데이터를 제공합니다.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.endpoint import Endpoint, EndpointStatus
from app.models.log import AccessLog, LogSeverity, LogEventType
from app.models.compliance import ComplianceCheck
from app.services.security_score import calculate_tenant_security_score

router = APIRouter(prefix="/dashboard", tags=["대시보드"])


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    대시보드 메인 요약 데이터를 반환합니다.
    종합 보안 점수, 모듈별 상태, 최근 이벤트를 포함합니다.
    """
    tenant_id = current_user.tenant_id

    # 종합 보안 점수 계산
    score_data = calculate_tenant_security_score(db, tenant_id)

    # SafeEndpoint 요약
    all_endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id,
        Endpoint.is_active == True
    ).all()
    endpoint_summary = {
        "total": len(all_endpoints),
        "online": sum(1 for ep in all_endpoints if ep.status == EndpointStatus.ONLINE),
        "warning": sum(1 for ep in all_endpoints if ep.status == EndpointStatus.WARNING),
        "critical": sum(1 for ep in all_endpoints if ep.status == EndpointStatus.CRITICAL),
        "offline": sum(1 for ep in all_endpoints if ep.status == EndpointStatus.OFFLINE),
        "avg_score": round(
            sum(ep.security_score for ep in all_endpoints) / len(all_endpoints), 1
        ) if all_endpoints else 0,
        "issues": [
            {
                "hostname": ep.hostname,
                "issue": _get_endpoint_issue(ep),
                "score": ep.security_score,
            }
            for ep in all_endpoints
            if ep.status in [EndpointStatus.WARNING, EndpointStatus.CRITICAL]
        ]
    }

    # SafeLog 요약 (최근 24시간)
    day_ago = datetime.utcnow() - timedelta(hours=24)
    recent_logs = db.query(AccessLog).filter(
        AccessLog.tenant_id == tenant_id,
        AccessLog.occurred_at >= day_ago,
    ).order_by(AccessLog.occurred_at.desc()).all()

    log_summary = {
        "total_24h": len(recent_logs),
        "critical_24h": sum(1 for l in recent_logs if l.severity == LogSeverity.CRITICAL),
        "warning_24h": sum(1 for l in recent_logs if l.severity == LogSeverity.WARNING),
        "failed_attempts_24h": sum(1 for l in recent_logs if l.result == "fail"),
        "recent_events": [
            {
                "id": l.id,
                "event_type": l.event_type,
                "severity": l.severity,
                "user_name": l.user_name,
                "description": l.description,
                "result": l.result,
                "occurred_at": l.occurred_at.isoformat() if l.occurred_at else None,
            }
            for l in recent_logs[:10]  # 최근 10건
        ]
    }

    # SafeGuard 요약
    latest_check = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).first()

    compliance_summary = {
        "total_score": round(latest_check.total_score, 1) if latest_check else 0,
        "privacy_score": round(latest_check.privacy_score, 1) if latest_check else 0,
        "medical_score": round(latest_check.medical_score, 1) if latest_check else 0,
        "emr_score": round(latest_check.emr_score, 1) if latest_check else 0,
        "fail_count": latest_check.fail_count if latest_check else 0,
        "pending_count": 0,  # 추후 계산
        "last_checked_at": latest_check.checked_at.isoformat() if latest_check and latest_check.checked_at else None,
        "next_check_at": latest_check.next_check_at.isoformat() if latest_check and latest_check.next_check_at else None,
    }

    # 이번 달 대비 지난 달 이벤트 수 비교
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)
    this_month_events = db.query(AccessLog).filter(
        AccessLog.tenant_id == tenant_id,
        AccessLog.occurred_at >= month_ago,
    ).count()

    # 테넌트 정보 조회
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    return {
        "tenant_name": tenant.name if tenant else "",
        "plan": tenant.plan if tenant else "basic",
        "score": score_data,
        "endpoints": endpoint_summary,
        "logs": log_summary,
        "compliance": compliance_summary,
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.get("/alerts")
async def get_active_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """현재 활성 알림 목록을 반환합니다."""
    alerts = []
    tenant_id = current_user.tenant_id

    # 보안 점수 낮은 엔드포인트 체크
    low_score_endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id,
        Endpoint.is_active == True,
        Endpoint.security_score < 60,
    ).all()

    for ep in low_score_endpoints:
        alerts.append({
            "type": "endpoint_low_score",
            "severity": "critical" if ep.security_score < 40 else "warning",
            "title": f"{ep.hostname} 보안 점수 낮음",
            "description": f"보안 점수 {ep.security_score}점 - 즉각적인 조치가 필요합니다.",
            "action_url": f"/endpoints/{ep.id}",
        })

    # 최근 24시간 로그인 실패 체크
    day_ago = datetime.utcnow() - timedelta(hours=24)
    login_fails = db.query(AccessLog).filter(
        AccessLog.tenant_id == tenant_id,
        AccessLog.event_type == LogEventType.LOGIN_FAIL,
        AccessLog.occurred_at >= day_ago,
    ).count()

    if login_fails >= 5:
        alerts.append({
            "type": "login_fail_spike",
            "severity": "warning",
            "title": f"로그인 실패 다수 감지",
            "description": f"최근 24시간 내 {login_fails}회 로그인 실패. 무단 접근 시도일 수 있습니다.",
            "action_url": "/logs?event_type=login_fail",
        })

    # 컴플라이언스 점검 미완료 체크
    latest_check = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).first()

    if not latest_check:
        alerts.append({
            "type": "no_compliance_check",
            "severity": "warning",
            "title": "컴플라이언스 점검 미실시",
            "description": "아직 보안 규제 점검을 실시하지 않았습니다. 지금 바로 점검을 시작하세요.",
            "action_url": "/compliance",
        })
    elif latest_check.next_check_at and latest_check.next_check_at < datetime.utcnow():
        alerts.append({
            "type": "compliance_overdue",
            "severity": "info",
            "title": "컴플라이언스 재점검 필요",
            "description": f"마지막 점검 후 30일이 지났습니다. 재점검을 권고합니다.",
            "action_url": "/compliance",
        })

    return {"count": len(alerts), "alerts": alerts}


def _get_endpoint_issue(ep: Endpoint) -> str:
    """엔드포인트의 주요 보안 이슈를 문자열로 반환합니다."""
    issues = []
    if ep.disk_encrypted is False: issues.append("디스크 암호화 미설정")
    if ep.antivirus_installed is False: issues.append("백신 미설치")
    if ep.antivirus_updated is False: issues.append("백신 업데이트 필요")
    if ep.os_patched is False: issues.append("OS 패치 필요")
    if ep.firewall_enabled is False: issues.append("방화벽 비활성화")
    return ", ".join(issues) if issues else "상태 미확인"
