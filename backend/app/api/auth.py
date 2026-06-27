"""
MediSafe Clinic - 인증 API
로그인, 토큰 갱신, 비밀번호 변경을 처리합니다.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.core.database import get_db
from app.core.security import (
    verify_password, create_access_token, get_current_user, hash_password
)
from app.models.user import User
from app.models.log import AccessLog, LogEventType, LogSeverity

router = APIRouter(prefix="/auth", tags=["인증"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    user_name: str
    role: str
    tenant_id: int | None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    로그인 API
    이메일/비밀번호로 인증하고 JWT 토큰을 발급합니다.
    모든 로그인 시도(성공/실패)는 감사 로그에 기록됩니다.
    """
    user = db.query(User).filter(
        User.email == request.email,
        User.is_active == True
    ).first()

    if not user or not verify_password(request.password, user.hashed_password):
        # 로그인 실패 기록 (감사 추적)
        if user:
            _log_event(db, user.tenant_id, None, request.email, LogEventType.LOGIN_FAIL,
                      LogSeverity.WARNING, result="fail")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    # 마지막 로그인 시간 업데이트
    user.last_login_at = datetime.utcnow()
    db.commit()

    # 로그인 성공 기록
    _log_event(db, user.tenant_id, user.id, user.email, LogEventType.LOGIN_SUCCESS,
               LogSeverity.INFO, result="success")

    # JWT 토큰 발급
    token = create_access_token({
        "sub": str(user.id),
        "tenant_id": user.tenant_id,
        "role": user.role,
        "name": user.name,
    })

    return LoginResponse(
        access_token=token,
        user_id=user.id,
        user_name=user.name,
        role=user.role,
        tenant_id=user.tenant_id,
    )


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보를 반환합니다."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "last_login_at": current_user.last_login_at,
    }


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """비밀번호를 변경합니다."""
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다.",
        )

    current_user.hashed_password = hash_password(request.new_password)
    db.commit()

    # 비밀번호 변경 감사 로그
    _log_event(db, current_user.tenant_id, current_user.id, current_user.email,
               LogEventType.ADMIN_ACTION, LogSeverity.WARNING,
               description="비밀번호 변경")

    return {"message": "비밀번호가 성공적으로 변경되었습니다."}


def _log_event(db, tenant_id, user_id, email, event_type, severity,
               result="success", description=None):
    """감사 로그를 기록하는 내부 함수"""
    log = AccessLog(
        tenant_id=tenant_id,
        user_id=user_id,
        user_email=email,
        event_type=event_type,
        severity=severity,
        result=result,
        description=description,
    )
    db.add(log)
    db.commit()
