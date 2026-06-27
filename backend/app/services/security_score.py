"""
MediSafe Clinic - 보안 점수 계산 서비스
엔드포인트 상태와 컴플라이언스 결과를 종합하여 보안 점수를 산출합니다.
"""
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.endpoint import Endpoint, EndpointStatus
from app.models.compliance import ComplianceCheck, CheckStatus
from app.models.log import AccessLog, LogSeverity


def calculate_endpoint_score(endpoint: Endpoint) -> Dict[str, Any]:
    """
    단일 엔드포인트의 보안 점수를 계산합니다.
    각 보안 항목별 가중치를 적용하여 0-100점으로 산출합니다.
    """
    score = 0.0
    details = {}

    # 항목별 가중치 정의
    checks = [
        ("disk_encrypted", "디스크 암호화", 25),
        ("antivirus_installed", "백신 설치", 20),
        ("antivirus_updated", "백신 최신 업데이트", 15),
        ("os_patched", "OS 최신 패치", 20),
        ("firewall_enabled", "방화벽 활성화", 10),
        ("screen_lock_enabled", "화면 잠금 설정", 5),
        ("usb_blocked", "USB 차단", 5),
    ]

    for field, label, weight in checks:
        value = getattr(endpoint, field, None)
        if value is True:
            score += weight
            details[field] = {"label": label, "status": "pass", "score": weight}
        elif value is False:
            details[field] = {"label": label, "status": "fail", "score": 0}
        else:
            # None = 미확인 (절반 점수)
            score += weight * 0.3
            details[field] = {"label": label, "status": "unknown", "score": weight * 0.3}

    return {
        "total": round(score, 1),
        "max": 100,
        "grade": get_grade(score),
        "details": details,
    }


def get_grade(score: float) -> str:
    """점수를 등급으로 변환합니다."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def calculate_tenant_security_score(db: Session, tenant_id: int) -> Dict[str, Any]:
    """
    병원 전체의 종합 보안 점수를 계산합니다.
    SafeEndpoint + SafeGuard + SafeLog 모듈 점수를 종합합니다.
    """
    # 1. SafeEndpoint 점수 (전체 엔드포인트 평균)
    endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id,
        Endpoint.is_active == True
    ).all()

    endpoint_score = 0.0
    if endpoints:
        scores = []
        for ep in endpoints:
            ep_score = calculate_endpoint_score(ep)
            scores.append(ep_score["total"])
            # 엔드포인트 점수 업데이트
            ep.security_score = ep_score["total"]
            ep.score_details = ep_score["details"]
        db.commit()
        endpoint_score = sum(scores) / len(scores)
    else:
        endpoint_score = 0.0

    # 2. SafeGuard 점수 (최근 컴플라이언스 점검)
    latest_check = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).first()
    compliance_score = latest_check.total_score if latest_check else 0.0

    # 3. SafeLog 점수 (최근 7일 로그 기반)
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    critical_count = db.query(AccessLog).filter(
        AccessLog.tenant_id == tenant_id,
        AccessLog.severity == LogSeverity.CRITICAL,
        AccessLog.occurred_at >= week_ago
    ).count()

    # 경고 이벤트가 많을수록 점수 감소
    log_score = max(0, 100 - (critical_count * 10))

    # 4. 종합 점수 (가중 평균)
    total_score = (
        endpoint_score * 0.50 +   # 엔드포인트 50%
        compliance_score * 0.35 + # 컴플라이언스 35%
        log_score * 0.15          # 로그 15%
    )

    return {
        "total": round(total_score, 1),
        "grade": get_grade(total_score),
        "breakdown": {
            "endpoint": {
                "score": round(endpoint_score, 1),
                "weight": "50%",
                "count": len(endpoints),
                "online": sum(1 for ep in endpoints if ep.status == EndpointStatus.ONLINE),
            },
            "compliance": {
                "score": round(compliance_score, 1),
                "weight": "35%",
                "last_checked": latest_check.checked_at.isoformat() if latest_check else None,
            },
            "log": {
                "score": round(log_score, 1),
                "weight": "15%",
                "critical_events_7d": critical_count,
            },
        },
    }
