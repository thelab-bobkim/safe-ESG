"""
MediSafe Clinic - SafeEndpoint API
병원 내 PC 엔드포인트의 보안 상태를 관리합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import secrets

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.endpoint import Endpoint, EndpointStatus, OSType, USBEvent
from app.models.user import User
from app.services.security_score import calculate_endpoint_score
from app.services import log_service

router = APIRouter(prefix="/endpoints", tags=["SafeEndpoint"])


class EndpointCreate(BaseModel):
    hostname: str
    ip_address: Optional[str] = None
    os_type: OSType
    os_version: Optional[str] = None
    location: Optional[str] = None


class EndpointStatusUpdate(BaseModel):
    """에이전트가 주기적으로 보안 상태를 보고하는 스키마"""
    agent_token: str
    status: EndpointStatus
    disk_encrypted: Optional[bool] = None
    antivirus_installed: Optional[bool] = None
    antivirus_updated: Optional[bool] = None
    os_patched: Optional[bool] = None
    usb_blocked: Optional[bool] = None
    firewall_enabled: Optional[bool] = None
    screen_lock_enabled: Optional[bool] = None
    agent_version: Optional[str] = None
    ip_address: Optional[str] = None


class USBEventReport(BaseModel):
    """USB 이벤트 보고"""
    agent_token: str
    event_type: str  # connect / disconnect
    device_name: Optional[str] = None
    device_id: Optional[str] = None
    blocked: bool = False


@router.get("/")
async def list_endpoints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """병원의 엔드포인트 목록을 반환합니다."""
    endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == current_user.tenant_id,
        Endpoint.is_active == True
    ).order_by(Endpoint.hostname).all()

    return [_endpoint_to_dict(ep) for ep in endpoints]


@router.get("/{endpoint_id}")
async def get_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """특정 엔드포인트 상세 정보를 반환합니다."""
    ep = _get_endpoint_or_404(db, endpoint_id, current_user.tenant_id)
    result = _endpoint_to_dict(ep)
    result["usb_events"] = [
        {
            "id": u.id,
            "event_type": u.event_type,
            "device_name": u.device_name,
            "blocked": u.blocked,
            "occurred_at": u.occurred_at.isoformat(),
        }
        for u in ep.usb_events[-20:]  # 최근 20개
    ]
    return result


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_endpoint(
    data: EndpointCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    새 엔드포인트(PC)를 등록합니다.
    등록 시 에이전트 인증 토큰이 발급됩니다.
    """
    # 최대 엔드포인트 수 확인
    count = db.query(Endpoint).filter(
        Endpoint.tenant_id == current_user.tenant_id,
        Endpoint.is_active == True
    ).count()
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant or count >= tenant.max_endpoints:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 구독 플랜의 최대 엔드포인트 수({tenant.max_endpoints}대)를 초과했습니다.",
        )

    # 에이전트 토큰 생성 (안전한 랜덤 토큰)
    agent_token = secrets.token_urlsafe(32)

    ep = Endpoint(
        tenant_id=current_user.tenant_id,
        hostname=data.hostname,
        ip_address=data.ip_address,
        os_type=data.os_type,
        os_version=data.os_version,
        location=data.location,
        agent_token=agent_token,
        status=EndpointStatus.OFFLINE,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)

    # SafeLog 기록
    log_service.log_endpoint_registered(
        db, current_user.tenant_id, current_user.id, current_user.name,
        data.hostname, data.ip_address or "", data.os_type, commit=True
    )

    result = _endpoint_to_dict(ep)
    result["agent_token"] = agent_token  # 최초 등록 시에만 토큰 반환
    return result


@router.post("/agent/heartbeat")
async def agent_heartbeat(
    data: EndpointStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    에이전트가 주기적으로 보안 상태를 보고하는 엔드포인트입니다.
    JWT 인증 없이 에이전트 토큰으로 인증합니다.
    """
    ep = db.query(Endpoint).filter(
        Endpoint.agent_token == data.agent_token,
        Endpoint.is_active == True
    ).first()

    if not ep:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 에이전트 토큰")

    # 보안 상태 업데이트
    ep.status = data.status
    ep.last_seen_at = datetime.utcnow()
    if data.disk_encrypted is not None: ep.disk_encrypted = data.disk_encrypted
    if data.antivirus_installed is not None: ep.antivirus_installed = data.antivirus_installed
    if data.antivirus_updated is not None: ep.antivirus_updated = data.antivirus_updated
    if data.os_patched is not None: ep.os_patched = data.os_patched
    if data.usb_blocked is not None: ep.usb_blocked = data.usb_blocked
    if data.firewall_enabled is not None: ep.firewall_enabled = data.firewall_enabled
    if data.screen_lock_enabled is not None: ep.screen_lock_enabled = data.screen_lock_enabled
    if data.agent_version: ep.agent_version = data.agent_version
    if data.ip_address: ep.ip_address = data.ip_address

    # 보안 점수 재계산
    score_data = calculate_endpoint_score(ep)
    ep.security_score = score_data["total"]
    ep.score_details = score_data["details"]

    db.commit()
    return {"status": "ok", "score": score_data["total"]}


@router.post("/agent/usb-event")
async def report_usb_event(data: USBEventReport, db: Session = Depends(get_db)):
    """에이전트가 USB 이벤트를 보고합니다. (WORM 저장)"""
    ep = db.query(Endpoint).filter(
        Endpoint.agent_token == data.agent_token,
        Endpoint.is_active == True
    ).first()

    if not ep:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 에이전트 토큰")

    event = USBEvent(
        tenant_id=ep.tenant_id,
        endpoint_id=ep.id,
        event_type=data.event_type,
        device_name=data.device_name,
        device_id=data.device_id,
        blocked=data.blocked,
    )
    db.add(event)
    db.commit()
    return {"status": "recorded"}


@router.patch("/{endpoint_id}/heartbeat")
async def jwt_heartbeat(
    endpoint_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    JWT 인증 기반 heartbeat (에이전트 v0.1용)
    원장 JWT 토큰으로 본인 테넌트 엔드포인트의 상태를 업데이트합니다.
    """
    ep = _get_endpoint_or_404(db, endpoint_id, current_user.tenant_id)

    # 보안 상태 업데이트
    ep.last_seen_at = datetime.utcnow()
    ep.status = EndpointStatus.ONLINE
    for field in ["disk_encrypted", "antivirus_installed", "os_patched",
                  "firewall_enabled", "screen_lock_enabled", "ip_address", "os_version"]:
        if data.get(field) is not None:
            setattr(ep, field, data[field])
    if data.get("extra_data"):
        ep.score_details = data["extra_data"]

    # 보안 점수 재계산
    score_data = calculate_endpoint_score(ep)
    ep.security_score = score_data["total"]

    # 보안 이슈 목록
    issues = []
    if ep.disk_encrypted is False:      issues.append("디스크 암호화 미설정")
    if ep.antivirus_installed is False:  issues.append("백신 미설치")
    if ep.os_patched is False:           issues.append("OS 업데이트 필요")
    if ep.firewall_enabled is False:     issues.append("방화벽 비활성")
    if ep.screen_lock_enabled is False:  issues.append("화면잠금 미설정")

    # SafeLog 기록 (이슈 있을 때만 WARNING, 없으면 INFO)
    log_service.log_agent_heartbeat(
        db, ep.tenant_id, ep.id, ep.hostname,
        ep.ip_address or "", score_data["total"], issues
    )

    db.commit()
    return {
        "status": "ok",
        "endpoint_id": ep.id,
        "hostname": ep.hostname,
        "security_score": score_data["total"],
        "grade": score_data.get("grade", "?"),
    }


@router.post("/{endpoint_id}/usb-events")
async def report_usb_event_jwt(
    endpoint_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """JWT 인증 기반 USB 이벤트 기록 (에이전트 v0.1용)"""
    ep = _get_endpoint_or_404(db, endpoint_id, current_user.tenant_id)

    device_name = data.get("device_name", "Unknown")
    action      = data.get("action", "connected")
    blocked     = data.get("blocked", False)

    event = USBEvent(
        tenant_id=ep.tenant_id,
        endpoint_id=ep.id,
        event_type=action,
        device_name=device_name,
        device_id=data.get("device_id", ""),
        blocked=blocked,
    )
    db.add(event)

    # SafeLog 기록
    log_service.log_usb_event(
        db, ep.tenant_id, ep.id, ep.hostname,
        device_name, action, blocked
    )

    db.commit()
    return {"status": "recorded", "endpoint_id": ep.id}


@router.delete("/{endpoint_id}")
async def deactivate_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """엔드포인트를 비활성화합니다. (물리적 삭제 없음)"""
    ep = _get_endpoint_or_404(db, endpoint_id, current_user.tenant_id)
    ep.is_active = False
    log_service.log_endpoint_deactivated(
        db, current_user.tenant_id, current_user.id, current_user.name, ep.hostname
    )
    db.commit()
    return {"message": f"{ep.hostname} 엔드포인트가 비활성화되었습니다."}


def _get_endpoint_or_404(db, endpoint_id, tenant_id):
    """엔드포인트를 조회하고 없으면 404를 반환합니다. (테넌트 격리 보장)"""
    ep = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id,
        Endpoint.tenant_id == tenant_id,  # 반드시 테넌트 필터 적용
    ).first()
    if not ep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="엔드포인트를 찾을 수 없습니다.")
    return ep


def _endpoint_to_dict(ep: Endpoint) -> dict:
    return {
        "id": ep.id,
        "hostname": ep.hostname,
        "ip_address": ep.ip_address,
        "os_type": ep.os_type,
        "os_version": ep.os_version,
        "location": ep.location,
        "status": ep.status,
        "agent_version": ep.agent_version,
        "security_score": ep.security_score,
        "score_details": ep.score_details,
        "disk_encrypted": ep.disk_encrypted,
        "antivirus_installed": ep.antivirus_installed,
        "antivirus_updated": ep.antivirus_updated,
        "os_patched": ep.os_patched,
        "usb_blocked": ep.usb_blocked,
        "firewall_enabled": ep.firewall_enabled,
        "screen_lock_enabled": ep.screen_lock_enabled,
        "last_seen_at": ep.last_seen_at.isoformat() if ep.last_seen_at else None,
        "registered_at": ep.registered_at.isoformat() if ep.registered_at else None,
    }
