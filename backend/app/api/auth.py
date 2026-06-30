"""
MediSafe Clinic Ver-1 - 인증 API
개인정보보호법 제29조 준수: 접근통제, 감사로그, 계정잠금

Ver-1 변경:
  - 모든 로그인 시도 감사 로그 기록
  - 계정잠금 (5회 실패 → 30분 잠금)
  - 비밀번호 강도 검증 (대소문자+숫자+특수문자 3종 이상)
  - 90일 비밀번호 만료 경고
  - Rate Limiting: 로그인 10회/분
  - 응답에서 내부 정보 최소화 (에러 메시지 표준화)
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
import secrets

from app.core.database import get_db
from app.core.security import (
    verify_password, hash_password, create_access_token, create_refresh_token,
    get_current_user, validate_password_strength,
    record_login_failure, record_login_success, get_client_ip, needs_rehash
)
from app.core.rate_limit import limiter, LOGIN_LIMIT, API_LIMIT
from app.models.user import User
from app.models.audit import AuditAction, AuditSeverity
from app.services.audit_service import write_audit
from app.services import log_service

router = APIRouter(prefix="/auth", tags=["인증"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 14400  # 4시간 (초)
    must_change_password: bool = False
    password_expires_in_days: int | None = None


@router.post("/login", response_model=TokenResponse)
@limiter.limit(LOGIN_LIMIT)
async def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    로그인 API
    - Rate Limit: 10회/분 (IP 기준)
    - 실패 5회 시 계정 30분 잠금
    - 모든 시도 감사 로그 기록
    """
    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent", "")[:256]

    # 사용자 조회 (이메일 존재 여부를 공개하지 않음 → 동일 오류 메시지)
    user = db.query(User).filter(
        User.email == data.email.lower(),
        User.is_active == True,
    ).first()

    _GENERIC_ERROR = "이메일 또는 비밀번호가 올바르지 않습니다."

    if not user:
        # 타이밍 공격 방어: 사용자 없어도 동일 처리 시간 유지
        hash_password("dummy_timing_attack_prevention")
        write_audit(db, AuditAction.LOGIN_FAIL,
                    result="fail", severity=AuditSeverity.WARNING,
                    ip_address=ip, user_agent=ua,
                    resource_desc=f"존재하지 않는 이메일: {data.email}")
        raise HTTPException(status_code=401, detail=_GENERIC_ERROR)

    # 계정 잠금 확인
    if user.is_locked:
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
        write_audit(db, AuditAction.LOGIN_FAIL,
                    tenant_id=user.tenant_id, user_id=user.id,
                    result="blocked", severity=AuditSeverity.WARNING,
                    ip_address=ip, user_agent=ua,
                    resource_desc=f"잠긴 계정 접근 시도")
        raise HTTPException(
            status_code=423,
            detail=f"계정이 잠겨 있습니다. 약 {remaining}분 후에 다시 시도하세요."
        )

    # 비밀번호 검증
    if not verify_password(data.password, user.hashed_password):
        record_login_failure(user, db)
        attempts = user.failed_login_count
        remaining_attempts = max(0, 5 - attempts)

        write_audit(db, AuditAction.LOGIN_FAIL,
                    tenant_id=user.tenant_id, user_id=user.id,
                    result="fail", severity=AuditSeverity.WARNING,
                    ip_address=ip, user_agent=ua,
                    resource_desc=f"비밀번호 불일치 ({attempts}번째 실패)")

        if remaining_attempts > 0:
            log_service.log_login_fail(db, user.tenant_id, data.email, ip,
                f"비밀번호 불일치 ({attempts}번째 실패, 잔여 {remaining_attempts}회)")
            raise HTTPException(
                status_code=401,
                detail=f"{_GENERIC_ERROR} ({remaining_attempts}회 더 실패 시 계정이 잠깁니다.)"
            )
        else:
            log_service.log_account_locked(db, user.tenant_id, data.email, ip)
            raise HTTPException(
                status_code=423,
                detail="로그인 시도 초과로 계정이 잠겼습니다. 30분 후 다시 시도하세요."
            )

    # 로그인 성공
    record_login_success(user, db)
    # SafeLog 기록
    log_service.log_login_success(db, user.tenant_id, user.id, user.name, user.email, ip)

    # Argon2 rehash 필요 시 자동 업그레이드
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(data.password)
        db.commit()

    # IP 이상 감지 (이전 IP와 다를 경우 경고)
    sev = AuditSeverity.INFO
    if user.last_login_ip and user.last_login_ip != ip:
        sev = AuditSeverity.WARNING

    write_audit(db, AuditAction.LOGIN_SUCCESS,
                tenant_id=user.tenant_id, user_id=user.id,
                result="success", severity=sev,
                ip_address=ip, user_agent=ua,
                resource_desc=f"정상 로그인: {user.email}")

    # 마지막 접속 IP 업데이트
    user.last_login_ip = ip
    db.commit()

    # 토큰 발급
    access_token  = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token(user.id)

    # 비밀번호 만료 일수 계산
    pw_expires_days = None
    if user.password_changed_at:
        days_since = (datetime.utcnow() - user.password_changed_at).days
        pw_expires_days = max(0, 90 - days_since)

    return TokenResponse(
        access_token             = access_token,
        refresh_token            = refresh_token,
        must_change_password     = user.must_change_password,
        password_expires_in_days = pw_expires_days,
    )


@router.get("/me")
@limiter.limit(API_LIMIT)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """현재 로그인한 사용자 정보"""
    return {
        "id":                  current_user.id,
        "email":               current_user.email,
        "name":                current_user.name,
        "role":                current_user.role,
        "tenant_id":           current_user.tenant_id,
        "must_change_password": current_user.must_change_password,
        "password_expired":    current_user.password_expired,
        "mfa_enabled":         current_user.mfa_enabled,
        "last_login_at":       current_user.last_login_at.isoformat() if current_user.last_login_at else None,
    }


@router.post("/logout")
@limiter.limit(API_LIMIT)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """로그아웃 (감사 로그 기록)"""
    ip = get_client_ip(request)
    write_audit(db, AuditAction.LOGOUT,
                tenant_id=current_user.tenant_id, user_id=current_user.id,
                result="success", severity=AuditSeverity.INFO,
                ip_address=ip)
    return {"message": "로그아웃 되었습니다."}


@router.post("/change-password")
@limiter.limit(API_LIMIT)
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    비밀번호 변경
    - 현재 비밀번호 재확인
    - 새 비밀번호 강도 검증
    - 변경 일시 기록 (90일 만료 정책)
    """
    ip = get_client_ip(request)

    if not verify_password(data.current_password, current_user.hashed_password):
        write_audit(db, AuditAction.PASSWORD_CHANGE,
                    tenant_id=current_user.tenant_id, user_id=current_user.id,
                    result="fail", severity=AuditSeverity.WARNING,
                    ip_address=ip, resource_desc="현재 비밀번호 불일치")
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")

    ok, msg = validate_password_strength(data.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # 현재 비밀번호와 동일 여부 확인
    if verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="이전 비밀번호와 동일한 비밀번호는 사용할 수 없습니다.")

    current_user.hashed_password    = hash_password(data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    current_user.must_change_password = False
    db.commit()

    write_audit(db, AuditAction.PASSWORD_CHANGE,
                tenant_id=current_user.tenant_id, user_id=current_user.id,
                result="success", severity=AuditSeverity.INFO,
                ip_address=ip)
    log_service.log_password_change(db, current_user.tenant_id,
                current_user.id, current_user.name, current_user.email, ip)
    db.commit()

    return {"message": "비밀번호가 변경되었습니다."}


# ──────────────────────────────────────────────
# 셀프 온보딩 - 병원 신규 등록
# ──────────────────────────────────────────────

PLAN_MAX_ENDPOINTS = {
    "basic": 5,
    "standard": 20,
    "pro": 100,
}


class RegisterHospitalRequest(BaseModel):
    hospital_name: str
    business_number: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str
    phone: Optional[str] = None
    plan: str = "standard"  # basic | standard | pro


@router.post("/register-hospital", status_code=201)
async def register_hospital(
    data: RegisterHospitalRequest,
    db: Session = Depends(get_db),
):
    """
    병원 셀프 온보딩 — 신규 병원 등록 (인증 불필요)
    - 이메일/사업자번호 중복 체크
    - Tenant + 관리자 User 생성
    - 에이전트 등록 코드(enroll_code) 자동 발급
    """
    from app.models.tenant import Tenant, SubscriptionPlan, TenantStatus
    from app.models.user import UserRole
    from datetime import timedelta

    # 플랜 검증
    plan_lower = data.plan.lower()
    if plan_lower not in PLAN_MAX_ENDPOINTS:
        raise HTTPException(
            status_code=400,
            detail=f"올바르지 않은 플랜입니다. (basic / standard / pro 중 선택)"
        )

    # 이메일 중복 확인
    existing_email = db.query(User).filter(
        User.email == data.admin_email.lower()
    ).first()
    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="이미 등록된 이메일 주소입니다."
        )

    # 사업자번호 중복 확인
    bn = data.business_number.strip()
    existing_bn = db.query(Tenant).filter(
        Tenant.business_number == bn
    ).first()
    if existing_bn:
        raise HTTPException(
            status_code=400,
            detail="이미 등록된 사업자등록번호입니다."
        )

    # 비밀번호 강도 검증
    ok, msg = validate_password_strength(data.admin_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # enroll_code 자동 생성 (형식: MSF-XXXXXX, 대문자+숫자 6자리)
    def _generate_enroll_code() -> str:
        while True:
            code = "MSF-" + secrets.token_hex(3).upper()
            exists = db.query(Tenant).filter(Tenant.enroll_code == code).first()
            if not exists:
                return code

    enroll_code = _generate_enroll_code()

    try:
        # Tenant 생성
        plan_enum_map = {
            "basic": SubscriptionPlan.BASIC,
            "standard": SubscriptionPlan.STANDARD,
            "pro": SubscriptionPlan.PRO,
        }
        tenant = Tenant(
            name=data.hospital_name.strip(),
            business_number=bn,
            phone=data.phone,
            plan=plan_enum_map[plan_lower],
            status=TenantStatus.TRIAL,
            max_endpoints=PLAN_MAX_ENDPOINTS[plan_lower],
            is_active=True,
            enroll_code=enroll_code,
            trial_ends_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(tenant)
        db.flush()

        # 관리자 User 생성
        admin_user = User(
            tenant_id=tenant.id,
            email=data.admin_email.lower(),
            hashed_password=hash_password(data.admin_password),
            name=data.admin_name.strip(),
            phone=data.phone,
            role=UserRole.ADMIN,
            is_active=True,
            password_changed_at=datetime.utcnow(),
            must_change_password=False,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(tenant)

        return {
            "tenant_id": tenant.id,
            "enroll_code": enroll_code,
            "plan": plan_lower,
            "max_endpoints": tenant.max_endpoints,
            "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            "message": (
                f"'{data.hospital_name}' 병원이 성공적으로 등록되었습니다. "
                f"에이전트 설치 시 등록 코드 '{enroll_code}'를 사용하세요."
            ),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"병원 등록 중 오류가 발생했습니다: {str(e)}"
        )
