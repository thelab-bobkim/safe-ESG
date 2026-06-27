"""
MediSafe Clinic - SafeLog API
EMR 접속 로그 수집, 검색, 내보내기를 담당합니다.
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import csv
import io

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.log import AccessLog, LogEventType, LogSeverity
from app.models.user import User

router = APIRouter(prefix="/logs", tags=["SafeLog"])


class LogCreateRequest(BaseModel):
    """로그 수집 요청 스키마"""
    event_type: LogEventType
    severity: LogSeverity = LogSeverity.INFO
    resource: Optional[str] = None
    action: Optional[str] = None
    result: str = "success"
    description: Optional[str] = None
    ip_address: Optional[str] = None
    endpoint_hostname: Optional[str] = None


@router.get("/")
async def list_logs(
    # 필터 파라미터
    event_type: Optional[LogEventType] = Query(None, description="이벤트 유형 필터"),
    severity: Optional[LogSeverity] = Query(None, description="심각도 필터"),
    start_date: Optional[date] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    user_email: Optional[str] = Query(None, description="사용자 이메일 검색"),
    keyword: Optional[str] = Query(None, description="키워드 검색 (설명, 리소스)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    접속 로그를 조회합니다.
    날짜, 이벤트 유형, 사용자, 키워드로 필터링 가능합니다.
    """
    query = db.query(AccessLog).filter(
        AccessLog.tenant_id == current_user.tenant_id  # 테넌트 격리 필수
    )

    # 필터 적용
    if event_type:
        query = query.filter(AccessLog.event_type == event_type)
    if severity:
        query = query.filter(AccessLog.severity == severity)
    if start_date:
        query = query.filter(AccessLog.occurred_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(AccessLog.occurred_at <= datetime.combine(end_date, datetime.max.time()))
    if user_email:
        query = query.filter(AccessLog.user_email.ilike(f"%{user_email}%"))
    if keyword:
        query = query.filter(
            (AccessLog.description.ilike(f"%{keyword}%")) |
            (AccessLog.resource.ilike(f"%{keyword}%")) |
            (AccessLog.action.ilike(f"%{keyword}%"))
        )

    # 전체 개수
    total = query.count()

    # 페이지네이션 (최신순)
    logs = query.order_by(AccessLog.occurred_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": [_log_to_dict(log) for log in logs],
    }


@router.post("/", status_code=201)
async def create_log(
    data: LogCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """수동으로 로그를 기록합니다. (WORM 저장)"""
    log = AccessLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user_name=current_user.name,
        user_email=current_user.email,
        event_type=data.event_type,
        severity=data.severity,
        resource=data.resource,
        action=data.action,
        result=data.result,
        description=data.description,
        ip_address=data.ip_address,
        endpoint_hostname=data.endpoint_hostname,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _log_to_dict(log)


@router.get("/export/csv")
async def export_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    접속 로그를 CSV 파일로 내보냅니다.
    규제 감사 대응용 증빙 자료로 활용할 수 있습니다.
    """
    query = db.query(AccessLog).filter(
        AccessLog.tenant_id == current_user.tenant_id
    )
    if start_date:
        query = query.filter(AccessLog.occurred_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(AccessLog.occurred_at <= datetime.combine(end_date, datetime.max.time()))

    logs = query.order_by(AccessLog.occurred_at.desc()).all()

    # CSV 생성
    output = io.StringIO()
    writer = csv.writer(output)

    # 헤더 (한국어)
    writer.writerow([
        "번호", "발생시각", "이벤트유형", "심각도",
        "사용자명", "사용자이메일", "IP주소", "접속PC",
        "리소스", "행위", "결과", "설명",
    ])

    for log in logs:
        writer.writerow([
            log.id,
            log.occurred_at.strftime("%Y-%m-%d %H:%M:%S") if log.occurred_at else "",
            log.event_type.value,
            log.severity.value,
            log.user_name or "",
            log.user_email or "",
            log.ip_address or "",
            log.endpoint_hostname or "",
            log.resource or "",
            log.action or "",
            log.result or "",
            log.description or "",
        ])

    output.seek(0)
    filename = f"medisafe_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),  # BOM 포함 (엑셀 호환)
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/summary")
async def get_log_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """최근 7일 로그 요약 통계를 반환합니다."""
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)

    base_query = db.query(AccessLog).filter(
        AccessLog.tenant_id == current_user.tenant_id,
        AccessLog.occurred_at >= week_ago,
    )

    total = base_query.count()
    critical = base_query.filter(AccessLog.severity == LogSeverity.CRITICAL).count()
    warning = base_query.filter(AccessLog.severity == LogSeverity.WARNING).count()
    failed = base_query.filter(AccessLog.result == "fail").count()

    return {
        "period": "최근 7일",
        "total_events": total,
        "critical_events": critical,
        "warning_events": warning,
        "failed_attempts": failed,
        "normal_events": total - critical - warning,
    }


def _log_to_dict(log: AccessLog) -> dict:
    return {
        "id": log.id,
        "event_type": log.event_type,
        "severity": log.severity,
        "user_name": log.user_name,
        "user_email": log.user_email,
        "ip_address": log.ip_address,
        "endpoint_hostname": log.endpoint_hostname,
        "resource": log.resource,
        "action": log.action,
        "result": log.result,
        "description": log.description,
        "occurred_at": log.occurred_at.isoformat() if log.occurred_at else None,
        "is_worm": log.is_worm,
    }
