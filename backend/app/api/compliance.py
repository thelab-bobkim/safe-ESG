"""
MediSafe Clinic - SafeGuard API
규제 컴플라이언스 체크리스트 및 점검 결과를 관리합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
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
    endpoint_id: Optional[int] = Query(None, description="특정 PC ID (미지정 시 전체 평균)"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    새 컴플라이언스 점검을 시작합니다.
    endpoint_id 지정 시 해당 PC 단독 판정, 미지정 시 전체 PC 평균 판정
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

    # ── 에이전트 데이터 수집 ──────────────────────────────
    from app.models.endpoint import Endpoint
    ep_query = db.query(Endpoint).filter(
        Endpoint.tenant_id == current_user.tenant_id,
        Endpoint.is_active == True,
    )
    # 특정 PC 선택 시 해당 PC만, 미선택 시 전체
    if endpoint_id:
        ep_query = ep_query.filter(Endpoint.id == endpoint_id)
    endpoints = ep_query.all()
    total_eps = len(endpoints)
    # 점검 대상 PC명 저장
    target_name = endpoints[0].hostname if len(endpoints) == 1 else f"전체 {total_eps}대"
    check.checked_by_name = f"{current_user.name} ({target_name})"

    def ratio(field):
        if not endpoints: return None
        vals = [getattr(e, field) for e in endpoints if getattr(e, field) is not None]
        if not vals: return None
        return sum(1 for v in vals if v) / len(vals)

    enc_ratio = ratio('disk_encrypted')
    av_ratio  = ratio('antivirus_installed')
    fw_ratio  = ratio('firewall_enabled')
    sl_ratio  = ratio('screen_lock_enabled')
    op_ratio  = ratio('os_patched')

    # 감사로그 수 확인
    from app.models.audit import AuditLog
    audit_count = db.query(AuditLog).filter(
        AuditLog.tenant_id == current_user.tenant_id
    ).count()

    def auto_status(ratio_val):
        if ratio_val is None:  return CheckStatus.PENDING
        if ratio_val >= 1.0:   return CheckStatus.PASS
        if ratio_val >= 0.5:   return CheckStatus.PARTIAL
        return CheckStatus.FAIL

    def pct(r): return int((r or 0) * 100)
    def cnt(r): return int((r or 0) * total_eps)

    # ── 14개 항목 전부 자동 판정 ─────────────────────────
    auto_map = {
        # 개인정보보호법 제29조
        'PA29-01': (
            CheckStatus.PASS if total_eps > 0 else CheckStatus.PARTIAL,
            f"MediSafe 계정 기반 접근제어 적용 중. 등록 PC {total_eps}대 개별 토큰 인증."
        ),
        'PA29-02': (
            auto_status(fw_ratio),
            f"에이전트 자동 수집: 방화벽 활성 {pct(fw_ratio)}% ({cnt(fw_ratio)}/{total_eps}대). HTTPS 전용 통신 적용."
        ),
        'PA29-03': (
            CheckStatus.PASS if audit_count >= 10 else CheckStatus.PARTIAL if audit_count > 0 else CheckStatus.PENDING,
            f"MediSafe 감사로그 {audit_count}건 자동 기록 중. SHA-256 해시 체인 무결성 보호."
        ),
        'PA29-04': (
            auto_status(enc_ratio),
            f"에이전트 자동 수집: BitLocker 암호화 {pct(enc_ratio)}% ({cnt(enc_ratio)}/{total_eps}대)."
        ),
        'PA29-05': (
            auto_status(av_ratio),
            f"에이전트 자동 수집: 백신(Defender) 활성 {pct(av_ratio)}% ({cnt(av_ratio)}/{total_eps}대)."
        ),
        'PA29-06': (
            auto_status(sl_ratio),
            f"에이전트 자동 수집: 화면잠금 설정 {pct(sl_ratio)}% ({cnt(sl_ratio)}/{total_eps}대). USB 이벤트 모니터링 중."
        ),
        # 의료법 제23조
        'MA23-01': (
            CheckStatus.PARTIAL,
            "EMR 소프트웨어 인증 여부는 사용 중인 EMR 벤더에서 직접 확인 필요. 인증서 사본 보관 권장."
        ),
        'MA23-02': (
            CheckStatus.PASS if total_eps > 0 else CheckStatus.PARTIAL,
            f"MediSafe 역할 기반 접근제어(원장/직원 분리) 적용 중. 등록 PC {total_eps}대."
        ),
        'MA23-03': (
            CheckStatus.PASS if audit_count >= 10 else CheckStatus.PARTIAL,
            f"MediSafe SafeLog 자동 기록 중 ({audit_count}건). EMR 자체 열람 기록은 EMR 시스템에서 별도 확인."
        ),
        'MA23-04': (
            CheckStatus.PARTIAL,
            "의무기록 보존 기간(외래 5년·입원 10년)은 EMR 시스템 설정에서 직접 확인 필요."
        ),
        # EMR 인증 기준
        'EMR-01': (
            CheckStatus.PARTIAL,
            "사용 중인 EMR의 보건복지부 인증 번호를 EMR 벤더에 요청하여 확인하세요."
        ),
        'EMR-02': (
            CheckStatus.PARTIAL,
            "EMR 자동 백업 설정 여부는 EMR 관리자 화면에서 직접 확인 필요. MediSafe 서버는 일 1회 백업 중."
        ),
        'EMR-03': (
            auto_status(sl_ratio),
            f"에이전트 자동 수집: 화면잠금(세션 타임아웃 대용) {pct(sl_ratio)}% 적용. EMR 자체 타임아웃은 EMR 설정 확인."
        ),
        'EMR-04': (
            CheckStatus.PASS,
            "MediSafe 비밀번호 정책 적용 중: 8자 이상·3종 조합·90일 만료·계정잠금(5회 실패)."
        ),
    }

    # 각 항목에 대해 결과 레코드 생성
    for item in items:
        st, ev = auto_map.get(item.item_code, (CheckStatus.PENDING, None))
        result = ComplianceCheckResult(
            check_id=check.id,
            item_id=item.id,
            tenant_id=current_user.tenant_id,
            status=st,
            evidence=ev,
        )
        db.add(result)

    db.commit()
    db.refresh(check)
    _recalculate_scores(db, check)
    db.commit()
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
