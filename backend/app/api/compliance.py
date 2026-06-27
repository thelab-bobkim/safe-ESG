"""
MediSafe Clinic - SafeGuard API
규제 컴플라이언스 체크리스트 및 점검 결과를 관리합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.compliance import (
    ComplianceItem, ComplianceCheck, ComplianceCheckResult,
    RegulationType, CheckStatus
)
from app.models.user import User

router = APIRouter(prefix="/compliance", tags=["SafeGuard"])


class CheckResultUpdate(BaseModel):
    item_id: int
    status: CheckStatus
    evidence: Optional[str] = None
    note: Optional[str] = None
    due_date: Optional[datetime] = None


@router.get("/items")
async def list_compliance_items(
    regulation: Optional[RegulationType] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """규제 체크리스트 항목 목록을 반환합니다."""
    query = db.query(ComplianceItem)
    if regulation:
        query = query.filter(ComplianceItem.regulation == regulation)
    items = query.order_by(ComplianceItem.order_num).all()
    return [_item_to_dict(item) for item in items]


@router.get("/checks")
async def list_checks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """병원의 컴플라이언스 점검 이력을 반환합니다."""
    checks = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == current_user.tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).limit(20).all()
    return [_check_to_dict(c) for c in checks]


@router.post("/checks", status_code=201)
async def create_check(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    새 컴플라이언스 점검을 시작합니다.
    모든 체크리스트 항목이 'pending' 상태로 생성됩니다.
    """
    # 모든 체크리스트 항목 가져오기
    items = db.query(ComplianceItem).order_by(ComplianceItem.order_num).all()
    if not items:
        raise HTTPException(status_code=400, detail="체크리스트 항목이 없습니다. 초기 데이터를 먼저 등록하세요.")

    check = ComplianceCheck(
        tenant_id=current_user.tenant_id,
        checked_by=current_user.id,
        checked_by_name=current_user.name,
        next_check_at=datetime.utcnow() + timedelta(days=30),  # 30일 후 재점검
    )
    db.add(check)
    db.flush()

    # 각 항목에 대해 결과 레코드 생성
    for item in items:
        result = ComplianceCheckResult(
            check_id=check.id,
            item_id=item.id,
            tenant_id=current_user.tenant_id,
            status=CheckStatus.PENDING,
        )
        db.add(result)

    db.commit()
    db.refresh(check)
    return _check_to_dict(check)


@router.get("/checks/{check_id}")
async def get_check_detail(
    check_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """점검 세션의 상세 결과를 반환합니다."""
    check = _get_check_or_404(db, check_id, current_user.tenant_id)
    result = _check_to_dict(check)
    result["results"] = [
        {
            "id": r.id,
            "item_id": r.item_id,
            "item_code": r.item.item_code,
            "item_title": r.item.title,
            "regulation": r.item.regulation,
            "is_mandatory": r.item.is_mandatory,
            "status": r.status,
            "evidence": r.evidence,
            "note": r.note,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "guidance": r.item.guidance,
        }
        for r in check.results
    ]
    return result


@router.put("/checks/{check_id}/results")
async def update_check_results(
    check_id: int,
    updates: List[CheckResultUpdate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    체크리스트 항목 결과를 업데이트하고 점수를 재계산합니다.
    """
    check = _get_check_or_404(db, check_id, current_user.tenant_id)

    for update in updates:
        result = db.query(ComplianceCheckResult).filter(
            ComplianceCheckResult.check_id == check_id,
            ComplianceCheckResult.item_id == update.item_id,
        ).first()
        if result:
            result.status = update.status
            if update.evidence: result.evidence = update.evidence
            if update.note: result.note = update.note
            if update.due_date: result.due_date = update.due_date

    db.flush()

    # 점수 재계산
    _recalculate_scores(db, check)
    db.commit()

    return {"message": "업데이트 완료", "total_score": check.total_score}


@router.get("/checks/{check_id}/pending")
async def get_pending_items(
    check_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """미조치 항목 목록을 반환합니다."""
    check = _get_check_or_404(db, check_id, current_user.tenant_id)
    pending = [
        r for r in check.results
        if r.status in [CheckStatus.FAIL, CheckStatus.PENDING]
    ]
    return {
        "pending_count": len(pending),
        "items": [
            {
                "item_code": r.item.item_code,
                "title": r.item.title,
                "regulation": r.item.regulation,
                "status": r.status,
                "is_mandatory": r.item.is_mandatory,
                "due_date": r.due_date.isoformat() if r.due_date else None,
            }
            for r in pending
        ]
    }


def _recalculate_scores(db, check: ComplianceCheck):
    """점검 점수를 재계산합니다."""
    results = check.results
    if not results:
        return

    # 각 규제별 점수 계산
    def calc_score(regs):
        items = [r for r in results if r.item.regulation in regs]
        if not items:
            return 0.0
        pass_count = sum(1 for r in items if r.status == CheckStatus.PASS)
        partial_count = sum(1 for r in items if r.status == CheckStatus.PARTIAL)
        return ((pass_count + partial_count * 0.5) / len(items)) * 100

    check.privacy_score = calc_score([RegulationType.PRIVACY_ACT_29])
    check.medical_score = calc_score([RegulationType.MEDICAL_ACT_23])
    check.emr_score = calc_score([RegulationType.EMR_CERT])
    check.total_score = (check.privacy_score + check.medical_score + check.emr_score) / 3

    check.pass_count = sum(1 for r in results if r.status == CheckStatus.PASS)
    check.fail_count = sum(1 for r in results if r.status == CheckStatus.FAIL)
    check.partial_count = sum(1 for r in results if r.status == CheckStatus.PARTIAL)
    check.na_count = sum(1 for r in results if r.status == CheckStatus.NA)


def _get_check_or_404(db, check_id, tenant_id):
    check = db.query(ComplianceCheck).filter(
        ComplianceCheck.id == check_id,
        ComplianceCheck.tenant_id == tenant_id,  # 테넌트 격리
    ).first()
    if not check:
        raise HTTPException(status_code=404, detail="점검 기록을 찾을 수 없습니다.")
    return check


def _item_to_dict(item: ComplianceItem) -> dict:
    return {
        "id": item.id,
        "regulation": item.regulation,
        "item_code": item.item_code,
        "title": item.title,
        "description": item.description,
        "guidance": item.guidance,
        "is_mandatory": item.is_mandatory,
        "weight": item.weight,
    }


def _check_to_dict(check: ComplianceCheck) -> dict:
    return {
        "id": check.id,
        "title": check.title,
        "total_score": round(check.total_score, 1),
        "privacy_score": round(check.privacy_score, 1),
        "medical_score": round(check.medical_score, 1),
        "emr_score": round(check.emr_score, 1),
        "pass_count": check.pass_count,
        "fail_count": check.fail_count,
        "partial_count": check.partial_count,
        "na_count": check.na_count,
        "checked_by_name": check.checked_by_name,
        "checked_at": check.checked_at.isoformat() if check.checked_at else None,
        "next_check_at": check.next_check_at.isoformat() if check.next_check_at else None,
    }
