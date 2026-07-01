"""
MediSafe Clinic - SafeGuard API
규제 컴플라이언스 체크리스트 및 점검 결과를 관리합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
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


@router.get("/checks/{check_id}/pdf")
async def download_compliance_pdf(
    check_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """점검 결과를 PDF 파일로 다운로드합니다."""
    # 권한 확인 (tenant 격리)
    check = _get_check_or_404(db, check_id, current_user.tenant_id)

    from app.services.report_service import generate_compliance_pdf
    try:
        pdf_bytes = generate_compliance_pdf(check_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 생성 오류: {str(e)}")

    checked_at_str = (
        check.checked_at.strftime("%Y%m%d") if check.checked_at else "unknown"
    )
    filename = f"medisafe_compliance_{check_id}_{checked_at_str}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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


# ─────────────────────────────────────────────────────────────
# F10: 심평원 보안 지표 내보내기
# ─────────────────────────────────────────────────────────────

@router.get("/export/hira")
async def export_hira(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """건강보험심사평가원 의료기관 정보보호 지표 CSV 내보내기."""
    import io
    import csv
    from fastapi.responses import StreamingResponse as SR

    from app.models.endpoint import Endpoint
    from app.models.tenant import Tenant

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == current_user.tenant_id,
        Endpoint.is_active == True,
    ).all()

    total = len(endpoints)
    def pct(count): return f"{round(count/max(total,1)*100)}%" if total > 0 else "N/A"
    def yn(val): return "예" if val else "아니오"

    enc_count = sum(1 for e in endpoints if e.disk_encrypted)
    av_count  = sum(1 for e in endpoints if e.antivirus_installed)
    fw_count  = sum(1 for e in endpoints if e.firewall_enabled)
    sl_count  = sum(1 for e in endpoints if e.screen_lock_enabled)
    pt_count  = sum(1 for e in endpoints if e.os_patched)

    # 최신 컴플라이언스 점수
    latest_check = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == current_user.tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).first()

    rows = [
        ["항목코드", "보호지표", "현황", "세부내용", "비고"],
        ["AC-01", "접근통제", "적용", f"MediSafe 역할기반 접근제어 적용 / 등록PC {total}대", "의료법 제23조"],
        ["AC-02", "사용자인증", "적용", "JWT+비밀번호 정책(8자+3종조합+90일만료)", ""],
        ["ENC-01", "암호화(저장)", pct(enc_count), f"BitLocker 암호화 {enc_count}/{total}대 적용", "개인정보보호법 제29조"],
        ["AV-01", "악성코드 대응", pct(av_count), f"Defender/백신 설치 {av_count}/{total}대", ""],
        ["FW-01", "네트워크 방화벽", pct(fw_count), f"방화벽 활성 {fw_count}/{total}대", ""],
        ["BK-01", "백업", "적용", "MediSafe 서버 일 1회 자동 백업", ""],
        ["SL-01", "화면잠금/세션관리", pct(sl_count), f"화면잠금 {sl_count}/{total}대 적용", ""],
        ["PT-01", "패치관리", pct(pt_count), f"OS 최신 패치 {pt_count}/{total}대", ""],
        ["LOG-01", "감사로그", "적용", "MediSafe SafeLog 자동 수집/WORM 보관", ""],
        ["EDU-01", "보안교육", "미확인", "연 1회 이상 보안교육 실시 여부 직접 확인 필요", "권고"],
        ["COMP-01", "컴플라이언스 종합점수", f"{round(latest_check.total_score,1) if latest_check else 'N/A'}점", "MediSafe SafeGuard 자동 점검 결과", ""],
        ["INFO-01", "평가기관", tenant.name if tenant else "", f"생성일: {datetime.utcnow().strftime('%Y-%m-%d')}", "심평원 제출용"],
    ]

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM (Excel 호환)
    writer = csv.writer(output)
    writer.writerows(rows)
    output.seek(0)

    date_str = datetime.utcnow().strftime('%Y%m%d')
    from urllib.parse import quote
    filename_ascii = f"HIRA_Security_{date_str}.csv"
    filename_encoded = quote(f"HIRA_보안지표_{date_str}.csv")
    return SR(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename_ascii}; filename*=UTF-8''{filename_encoded}"},
    )


# ─────────────────────────────────────────────────────────────
# F11: 개인정보 영향평가(PIA) 보조
# ─────────────────────────────────────────────────────────────

@router.get("/pia-checklist")
async def get_pia_checklist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """개인정보 영향평가 체크리스트 및 현재 데이터 교차 분석."""
    from app.models.endpoint import Endpoint

    endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == current_user.tenant_id,
        Endpoint.is_active == True,
    ).all()
    total = len(endpoints)
    enc_pct = round(sum(1 for e in endpoints if e.disk_encrypted) / max(total, 1) * 100)
    av_pct  = round(sum(1 for e in endpoints if e.antivirus_installed) / max(total, 1) * 100)
    fw_pct  = round(sum(1 for e in endpoints if e.firewall_enabled) / max(total, 1) * 100)

    checklist = [
        {
            "id": 1,
            "category": "개인정보 처리 목적",
            "item": "개인정보 처리 목적이 명확히 정의되어 있는가?",
            "weight": 10,
            "auto_status": None,
            "guidance": "개인정보처리방침 및 내부 규정에 처리 목적을 명시하세요.",
        },
        {
            "id": 2,
            "category": "최소수집 원칙",
            "item": "업무에 필요한 최소한의 개인정보만 수집하고 있는가?",
            "weight": 10,
            "auto_status": None,
            "guidance": "불필요한 개인정보 항목 수집을 즉시 중단하세요.",
        },
        {
            "id": 3,
            "category": "접근통제",
            "item": "개인정보에 대한 접근이 역할별로 통제되고 있는가?",
            "weight": 15,
            "auto_status": "적용" if total > 0 else "미확인",
            "guidance": "MediSafe 역할기반 접근제어(원장/직원 분리) 적용 중.",
        },
        {
            "id": 4,
            "category": "암호화",
            "item": "저장된 개인정보(환자 기록 포함)가 암호화되어 있는가?",
            "weight": 15,
            "auto_status": f"{enc_pct}% 적용" if total > 0 else "미확인",
            "guidance": f"BitLocker 암호화 {enc_pct}% 적용 중. 미적용 PC 조치 필요.",
        },
        {
            "id": 5,
            "category": "악성코드 대응",
            "item": "모든 PC에 백신이 설치되고 최신 상태로 유지되는가?",
            "weight": 10,
            "auto_status": f"{av_pct}% 적용" if total > 0 else "미확인",
            "guidance": f"백신 설치율 {av_pct}%. 미설치 PC 즉시 조치 필요.",
        },
        {
            "id": 6,
            "category": "네트워크 보안",
            "item": "방화벽이 모든 PC에 활성화되어 있는가?",
            "weight": 10,
            "auto_status": f"{fw_pct}% 적용" if total > 0 else "미확인",
            "guidance": f"방화벽 활성화율 {fw_pct}%.",
        },
        {
            "id": 7,
            "category": "감사로그",
            "item": "개인정보 접근 및 처리 기록이 보관되고 있는가?",
            "weight": 10,
            "auto_status": "적용",
            "guidance": "MediSafe SafeLog WORM 기록 적용 중.",
        },
        {
            "id": 8,
            "category": "제3자 제공",
            "item": "개인정보 제3자 제공 시 동의를 받고 있는가?",
            "weight": 10,
            "auto_status": None,
            "guidance": "EMR 시스템 내 동의 관리 현황을 확인하세요.",
        },
        {
            "id": 9,
            "category": "보존 및 파기",
            "item": "개인정보 보존기간이 정해지고 파기 절차가 있는가?",
            "weight": 10,
            "auto_status": None,
            "guidance": "외래 5년, 입원 10년 보존 후 안전 파기 절차를 마련하세요.",
        },
        {
            "id": 10,
            "category": "보안교육",
            "item": "개인정보 취급자에 대한 정기 보안교육이 실시되는가?",
            "weight": 10,
            "auto_status": None,
            "guidance": "연 1회 이상 개인정보 보호 교육 실시 및 이수 기록 보관.",
        },
    ]

    return {"checklist": checklist, "endpoint_count": total}


class PIAReportRequest(BaseModel):
    responses: Optional[dict] = None  # {item_id: "적용" | "미적용" | "부분적용"}


@router.post("/pia-report")
async def generate_pia_report(
    data: PIAReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PIA 보고서 초안 텍스트 생성."""
    from app.models.tenant import Tenant
    from app.models.endpoint import Endpoint

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == current_user.tenant_id,
        Endpoint.is_active == True,
    ).all()
    total = len(endpoints)
    avg_score = sum(e.security_score or 0 for e in endpoints) / max(total, 1)

    latest_check = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == current_user.tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).first()

    now = datetime.utcnow()
    report_text = f"""
개인정보 영향평가(PIA) 보고서 초안
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ 기관명: {tenant.name if tenant else ""}
■ 평가일: {now.strftime('%Y년 %m월 %d일')}
■ 담당자: MediSafe Clinic 자동 생성 (최종 검토 필요)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 개요
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
본 기관은 「개인정보 보호법」 제33조에 따라 개인정보 영향평가를 실시하며,
의료기관으로서 환자 개인정보(성명, 생년월일, 의무기록 등) 처리에 관한
보안 현황을 점검합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. 현황 요약
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
· 등록 PC 수: {total}대
· 평균 보안점수: {avg_score:.1f}점
· 컴플라이언스 점수: {f'{latest_check.total_score:.1f}점' if latest_check else '미점검'}
· 암호화 적용: {sum(1 for e in endpoints if e.disk_encrypted)}/{total}대
· 백신 설치: {sum(1 for e in endpoints if e.antivirus_installed)}/{total}대
· 방화벽 활성: {sum(1 for e in endpoints if e.firewall_enabled)}/{total}대

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. 위험 요소 분석
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{'· 일부 PC 암호화 미적용 - 분실 시 환자 정보 유출 위험' if sum(1 for e in endpoints if not e.disk_encrypted) > 0 else '· 전 PC 암호화 적용 완료'}
{'· 백신 미설치 PC 존재 - 악성코드 감염 위험' if sum(1 for e in endpoints if not e.antivirus_installed) > 0 else '· 전 PC 백신 설치 완료'}
{'· 방화벽 미활성 PC 존재 - 네트워크 침입 위험' if sum(1 for e in endpoints if not e.firewall_enabled) > 0 else '· 전 PC 방화벽 활성화'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. 조치 계획
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
· 미암호화 PC: BitLocker 즉시 활성화 (30일 이내)
· 백신 미설치: Windows Defender 활성화 (1주일 이내)
· 방화벽 미활성: 방화벽 정책 적용 (1주일 이내)
· 정기 보안교육: 연 1회 이상 실시

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. 서명
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
기관장: __________________ (인)
개인정보 보호책임자: __________________ (인)
평가일: {now.strftime('%Y년 %m월 %d일')}

※ 이 보고서는 MediSafe Clinic에서 자동 생성된 초안입니다.
   제출 전 개인정보 보호책임자(CPO)의 검토 및 서명이 필요합니다.
"""

    return {
        "report_text": report_text,
        "tenant_name": tenant.name if tenant else "",
        "generated_at": now.isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# F12: 의료기관 정보보호 등급 자동 계산
# ─────────────────────────────────────────────────────────────

@router.get("/security-grade")
async def get_security_grade(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """1~5등급 자동 계산 및 향상 로드맵 반환."""
    from app.models.endpoint import Endpoint

    endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == current_user.tenant_id,
        Endpoint.is_active == True,
    ).all()
    total = len(endpoints)

    # 최신 컴플라이언스 점수
    latest_check = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == current_user.tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).first()

    # 종합점수: 컴플라이언스 50% + 엔드포인트 보안 50%
    compliance_score = latest_check.total_score if latest_check else 50.0
    ep_avg = sum(e.security_score or 0 for e in endpoints) / max(total, 1) if total else 50.0
    total_score = compliance_score * 0.5 + ep_avg * 0.5

    # 등급 계산
    if total_score >= 90:
        grade = 5
        grade_name = "5등급 (최우수)"
        grade_color = "#16a34a"
    elif total_score >= 80:
        grade = 4
        grade_name = "4등급 (우수)"
        grade_color = "#2563eb"
    elif total_score >= 70:
        grade = 3
        grade_name = "3등급 (보통)"
        grade_color = "#d97706"
    elif total_score >= 60:
        grade = 2
        grade_name = "2등급 (미흡)"
        grade_color = "#ea580c"
    else:
        grade = 1
        grade_name = "1등급 (취약)"
        grade_color = "#dc2626"

    # 조치 목록
    actions = []
    unencrypted = [e.hostname for e in endpoints if not e.disk_encrypted]
    no_av = [e.hostname for e in endpoints if not e.antivirus_installed]
    no_fw = [e.hostname for e in endpoints if not e.firewall_enabled]
    no_sl = [e.hostname for e in endpoints if not e.screen_lock_enabled]
    not_patched = [e.hostname for e in endpoints if not e.os_patched]

    if unencrypted:
        actions.append({"priority": "높음", "action": f"BitLocker 암호화 활성화", "targets": unencrypted, "score_impact": "+15점"})
    if no_av:
        actions.append({"priority": "높음", "action": "백신(Defender) 설치/활성화", "targets": no_av, "score_impact": "+10점"})
    if no_fw:
        actions.append({"priority": "중간", "action": "방화벽 활성화", "targets": no_fw, "score_impact": "+10점"})
    if no_sl:
        actions.append({"priority": "중간", "action": "화면잠금 설정", "targets": no_sl, "score_impact": "+8점"})
    if not_patched:
        actions.append({"priority": "중간", "action": "OS 패치 적용", "targets": not_patched, "score_impact": "+7점"})
    if not latest_check:
        actions.append({"priority": "높음", "action": "컴플라이언스 점검 실시", "targets": [], "score_impact": "+20점"})

    return {
        "grade": grade,
        "grade_name": grade_name,
        "grade_color": grade_color,
        "current_score": round(total_score, 1),   # 프론트 호환 필드
        "total_score": round(total_score, 1),
        "compliance_score": round(compliance_score, 1),
        "endpoint_score": round(ep_avg, 1),
        "next_grade": grade + 1 if grade < 5 else 5,
        "next_grade_threshold": [0, 60, 70, 80, 90][min(grade, 4)],
        "score_to_next": max(0, round([0, 60, 70, 80, 90][min(grade, 4)] - total_score, 1)),
        "total_endpoints": total,
        "actions": actions,
    }


# ─────────────────────────────────────────────────────────────
# F8 헬퍼용 엔드포인트 데이터 접근 (endpoints.py에 추가하기 위한 함수)
# ─────────────────────────────────────────────────────────────

def _seed_compliance(db, tenant_id: int):
    """초기 컴플라이언스 항목 시드 데이터 삽입."""
    from app.models.compliance import ComplianceItem, RegulationType

    # 이미 있으면 스킵
    if db.query(ComplianceItem).count() > 0:
        return

    items = [
        # 개인정보보호법 제29조
        ComplianceItem(regulation=RegulationType.PRIVACY_ACT_29, item_code="PA29-01",
            title="접근 권한 관리", description="개인정보 접근 권한을 역할별로 차등 부여", is_mandatory=True, weight=15, order_num=1,
            guidance="MediSafe 관리자/직원 역할 분리 적용"),
        ComplianceItem(regulation=RegulationType.PRIVACY_ACT_29, item_code="PA29-02",
            title="접근 통제", description="방화벽 및 네트워크 접근 통제", is_mandatory=True, weight=15, order_num=2,
            guidance="에이전트 방화벽 상태 자동 점검"),
        ComplianceItem(regulation=RegulationType.PRIVACY_ACT_29, item_code="PA29-03",
            title="접속 기록 보관", description="개인정보 시스템 접속 기록 보관 (최소 6개월)", is_mandatory=True, weight=15, order_num=3,
            guidance="MediSafe SafeLog WORM 기록"),
        ComplianceItem(regulation=RegulationType.PRIVACY_ACT_29, item_code="PA29-04",
            title="개인정보 암호화", description="저장 개인정보 암호화 (BitLocker 등)", is_mandatory=True, weight=15, order_num=4,
            guidance="에이전트 BitLocker 상태 자동 점검"),
        ComplianceItem(regulation=RegulationType.PRIVACY_ACT_29, item_code="PA29-05",
            title="악성프로그램 방지", description="백신 프로그램 설치 및 주기적 갱신", is_mandatory=True, weight=10, order_num=5,
            guidance="에이전트 Defender 상태 자동 점검"),
        ComplianceItem(regulation=RegulationType.PRIVACY_ACT_29, item_code="PA29-06",
            title="물리적 보안", description="화면잠금, USB 보안", is_mandatory=False, weight=10, order_num=6,
            guidance="에이전트 화면잠금 상태 자동 점검"),
        # 의료법 제23조
        ComplianceItem(regulation=RegulationType.MEDICAL_ACT_23, item_code="MA23-01",
            title="EMR 인증", description="보건복지부 인증 EMR 사용", is_mandatory=True, weight=20, order_num=7,
            guidance="EMR 벤더 인증서 확인 필요"),
        ComplianceItem(regulation=RegulationType.MEDICAL_ACT_23, item_code="MA23-02",
            title="전자서명", description="전자의무기록 전자서명 적용", is_mandatory=True, weight=15, order_num=8,
            guidance="EMR 시스템 설정 확인"),
        ComplianceItem(regulation=RegulationType.MEDICAL_ACT_23, item_code="MA23-03",
            title="접속 기록", description="EMR 접속 기록 보관", is_mandatory=True, weight=15, order_num=9,
            guidance="MediSafe SafeLog 자동 기록"),
        ComplianceItem(regulation=RegulationType.MEDICAL_ACT_23, item_code="MA23-04",
            title="의무기록 보존", description="외래 5년·입원 10년 보존", is_mandatory=True, weight=15, order_num=10,
            guidance="EMR 시스템 보존 기간 설정 확인"),
        # EMR 인증 기준
        ComplianceItem(regulation=RegulationType.EMR_CERT, item_code="EMR-01",
            title="EMR 인증 번호", description="공인 EMR 인증 번호 보유", is_mandatory=True, weight=25, order_num=11,
            guidance="EMR 벤더에 인증서 요청"),
        ComplianceItem(regulation=RegulationType.EMR_CERT, item_code="EMR-02",
            title="자동 백업", description="EMR 데이터 자동 백업 설정", is_mandatory=True, weight=25, order_num=12,
            guidance="EMR 관리자 화면에서 백업 설정 확인"),
        ComplianceItem(regulation=RegulationType.EMR_CERT, item_code="EMR-03",
            title="세션 타임아웃", description="비활동 세션 자동 종료", is_mandatory=False, weight=25, order_num=13,
            guidance="EMR 세션 타임아웃 10분 이하 설정 권장"),
        ComplianceItem(regulation=RegulationType.EMR_CERT, item_code="EMR-04",
            title="비밀번호 정책", description="복잡성·만료 정책 적용", is_mandatory=True, weight=25, order_num=14,
            guidance="MediSafe 비밀번호 정책 자동 적용"),
    ]
    for item in items:
        db.add(item)
