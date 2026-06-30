"""
MediSafe Clinic - 다중 지점(병원 그룹) 관리 API (F9)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.tenant import Tenant
from app.models.user import User
from app.models.hospital_group import HospitalGroup

router = APIRouter(prefix="/groups", tags=["다중 지점"])


class GroupCreate(BaseModel):
    name: str


@router.post("/", status_code=201)
async def create_group(
    data: GroupCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """병원 그룹 생성."""
    group = HospitalGroup(
        name=data.name,
        owner_tenant_id=current_user.tenant_id,
    )
    db.add(group)
    # 생성한 테넌트를 그룹에 자동 추가
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    db.flush()
    if tenant:
        tenant.group_id = group.id
    db.commit()
    db.refresh(group)

    return {
        "id": group.id,
        "name": group.name,
        "owner_tenant_id": group.owner_tenant_id,
        "created_at": group.created_at.isoformat(),
    }


@router.get("/{group_id}/tenants")
async def list_group_tenants(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """그룹 소속 병원 목록."""
    group = db.query(HospitalGroup).filter(HospitalGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")

    # 보안: 그룹 소속 테넌트만 접근 가능
    caller_tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not caller_tenant or caller_tenant.group_id != group_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    tenants = db.query(Tenant).filter(Tenant.group_id == group_id).all()

    from app.models.endpoint import Endpoint
    result = []
    for t in tenants:
        eps = db.query(Endpoint).filter(
            Endpoint.tenant_id == t.id, Endpoint.is_active == True
        ).all()
        avg_score = sum(e.security_score or 0 for e in eps) / max(len(eps), 1)
        result.append({
            "id": t.id,
            "name": t.name,
            "plan": t.plan,
            "is_active": t.is_active,
            "endpoint_count": len(eps),
            "avg_security_score": round(avg_score, 1),
            "is_owner": (t.id == group.owner_tenant_id),
        })

    return {
        "group_id": group_id,
        "group_name": group.name,
        "tenants": result,
    }


@router.get("/{group_id}/summary")
async def get_group_summary(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """그룹 전체 보안 현황 요약."""
    group = db.query(HospitalGroup).filter(HospitalGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")

    caller_tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not caller_tenant or caller_tenant.group_id != group_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    tenants = db.query(Tenant).filter(Tenant.group_id == group_id).all()

    from app.models.endpoint import Endpoint, EndpointStatus as EpStatus
    from app.models.compliance import ComplianceCheck

    total_endpoints = 0
    online_endpoints = 0
    all_scores = []
    tenant_summaries = []

    for t in tenants:
        eps = db.query(Endpoint).filter(
            Endpoint.tenant_id == t.id, Endpoint.is_active == True
        ).all()
        total_endpoints += len(eps)
        online_endpoints += sum(1 for e in eps if e.status == EpStatus.ONLINE)
        scores = [e.security_score for e in eps if e.security_score is not None]
        all_scores.extend(scores)
        avg_score = sum(scores) / max(len(scores), 1) if scores else 0

        # 최신 컴플라이언스 점수
        latest_check = db.query(ComplianceCheck).filter(
            ComplianceCheck.tenant_id == t.id
        ).order_by(ComplianceCheck.checked_at.desc()).first()

        tenant_summaries.append({
            "tenant_id": t.id,
            "tenant_name": t.name,
            "endpoint_count": len(eps),
            "online_count": sum(1 for e in eps if e.status == EpStatus.ONLINE),
            "avg_security_score": round(avg_score, 1),
            "compliance_score": round(latest_check.total_score, 1) if latest_check else None,
        })

    group_avg = sum(all_scores) / max(len(all_scores), 1) if all_scores else 0

    return {
        "group_id": group_id,
        "group_name": group.name,
        "total_tenants": len(tenants),
        "total_endpoints": total_endpoints,
        "online_endpoints": online_endpoints,
        "group_avg_score": round(group_avg, 1),
        "tenant_summaries": tenant_summaries,
    }
