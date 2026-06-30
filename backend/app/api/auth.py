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
            raise HTTPException(
                status_code=401,
                detail=f"{_GENERIC_ERROR} ({remaining_attempts}회 더 실패 시 계정이 잠깁니다.)"
            )
        else:
            raise HTTPException(
                status_code=423,
                detail="로그인 시도 초과로 계정이 잠겼습니다. 30분 후 다시 시도하세요."
            )

    # 로그인 성공
    record_login_success(user, db)

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

    return {"message": "비밀번호가 변경되었습니다."}
