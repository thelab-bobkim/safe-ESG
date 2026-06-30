"""
MediSafe Clinic Ver-1 - 보안 코어
개인정보보호법 제29조, 의료법 제23조 준수를 위한 인증/인가 시스템

변경 이력:
  Beta → Ver-1:
    - 에이전트 인증: 원장 PW 제거 → PC별 고유 토큰 (HMAC-SHA256)
    - 비밀번호 해시: bcrypt → Argon2id (NIST SP 800-63B 권고)
    - JWT: 만료시간 단축 (8h→4h), 토큰 갱신 메커니즘 추가
    - 계정 잠금: 5회 실패 시 30분 잠금
    - 세션 추적: 모든 로그인/로그아웃 감사 로그 기록
"""

import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

# ──────────────────────────────────────────────
# Argon2id 해시 (NIST SP 800-63B 준수)
# bcrypt 대비 사이드채널 공격에 강함
# ──────────────────────────────────────────────
_ph = PasswordHasher(
    time_cost=3,       # 반복 횟수
    memory_cost=65536, # 64MB 메모리
    parallelism=2,     # 병렬 처리 수
    hash_len=32,
    salt_len=16,
)

def hash_password(password: str) -> str:
    """Argon2id로 비밀번호 해시"""
    return _ph.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """비밀번호 검증 (타이밍 공격 방어 포함)"""
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError):
        return False

def needs_rehash(hashed: str) -> bool:
    """해시 알고리즘 업그레이드 필요 여부"""
    return _ph.check_needs_rehash(hashed)

# ──────────────────────────────────────────────
# 비밀번호 강도 검증 (개인정보보호법 제29조)
# ──────────────────────────────────────────────
def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    개인정보보호법 제29조 기준 비밀번호 정책:
    - 최소 8자 이상
    - 영문 대/소문자, 숫자, 특수문자 중 3종류 이상 조합
    - 연속 문자/숫자 4개 이상 금지
    - 이전 비밀번호 재사용 금지 (호출부에서 처리)
    """
    if len(password) < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    if len(password) > 128:
        return False, "비밀번호는 128자 이하여야 합니다."

    has_upper   = any(c.isupper() for c in password)
    has_lower   = any(c.islower() for c in password)
    has_digit   = any(c.isdigit() for c in password)
    has_special = any(c in string.punctuation for c in password)
    complexity  = sum([has_upper, has_lower, has_digit, has_special])

    if complexity < 3:
        return False, "영문 대/소문자, 숫자, 특수문자 중 3종류 이상을 포함해야 합니다."

    # 연속 문자 패턴 검사 (숫자에만 적용)
    for i in range(len(password) - 3):
        chars = [password[i+j] for j in range(4)]
        if all(c.isdigit() for c in chars):
            nums = [int(c) for c in chars]
            diffs = [nums[j+1] - nums[j] for j in range(3)]
            if all(d == 1 for d in diffs) or all(d == -1 for d in diffs):
                return False, "4자 이상 연속된 숫자(예: 1234, 9876)는 사용할 수 없습니다."

    return True, "OK"

# ──────────────────────────────────────────────
# JWT 토큰 (사용자용)
# ──────────────────────────────────────────────
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT Access Token 생성"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),  # JWT ID (토큰 재사용 추적용)
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(user_id: int) -> str:
    """JWT Refresh Token 생성 (24시간)"""
    return create_access_token(
        {"sub": str(user_id), "type": "refresh"},
        expires_delta=timedelta(hours=24)
    )

def decode_token(token: str) -> dict:
    """JWT 토큰 디코드 및 검증"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """현재 인증된 사용자 반환"""
    from app.models.user import User
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="토큰에 사용자 정보가 없습니다.")

    user = db.query(User).filter(
        User.id == int(user_id),
        User.is_active == True,
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없거나 비활성화된 계정입니다.")

    # 계정 잠금 확인
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
        raise HTTPException(
            status_code=423,
            detail=f"계정이 잠겨 있습니다. {remaining}분 후 다시 시도하세요."
        )

    return user

async def get_current_admin(
    current_user=Depends(get_current_user),
):
    """원장(admin) 이상 권한 확인"""
    from app.models.user import UserRole
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="원장 권한이 필요합니다.",
        )
    return current_user

async def get_superadmin(current_user=Depends(get_current_user)):
    """슈퍼관리자 권한 확인"""
    from app.models.user import UserRole
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="슈퍼관리자 권한이 필요합니다.")
    return current_user

# ──────────────────────────────────────────────
# 에이전트 전용 토큰 (PC별 고유, 원장 PW 불필요)
# ──────────────────────────────────────────────

AGENT_TOKEN_PREFIX = "msa_"  # MediSafe Agent

def generate_agent_token() -> str:
    """
    PC별 고유 에이전트 토큰 생성
    형식: msa_{32바이트 URL-safe random}
    특징:
      - 원장 계정과 완전 분리
      - PC 분실/도난 시 서버에서 즉시 무효화 가능
      - 토큰 탈취돼도 원장 계정 안전
    """
    return AGENT_TOKEN_PREFIX + secrets.token_urlsafe(32)

def verify_agent_token(token: str, db: Session):
    """에이전트 토큰 검증 → Endpoint 객체 반환"""
    from app.models.endpoint import Endpoint
    if not token or not token.startswith(AGENT_TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="유효하지 않은 에이전트 토큰 형식입니다.")

    ep = db.query(Endpoint).filter(
        Endpoint.agent_token == token,
        Endpoint.is_active == True,
        Endpoint.agent_token_revoked == False,  # 폐기된 토큰 차단
    ).first()

    if not ep:
        raise HTTPException(status_code=401, detail="등록되지 않았거나 폐기된 에이전트 토큰입니다.")

    return ep

# ──────────────────────────────────────────────
# 계정 잠금 관리 (개인정보보호법 제29조 - 접근통제)
# ──────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES    = 30

def record_login_failure(user, db: Session):
    """로그인 실패 기록 및 계정 잠금 처리"""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= MAX_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        user.failed_login_count = 0
    db.commit()

def record_login_success(user, db: Session):
    """로그인 성공 시 실패 카운터 초기화"""
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    db.commit()

# ──────────────────────────────────────────────
# IP 기반 접근 통제 유틸
# ──────────────────────────────────────────────
def get_client_ip(request: Request) -> str:
    """실제 클라이언트 IP 추출 (Cloudflare/Proxy 고려)"""
    # Cloudflare → CF-Connecting-IP 우선
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    # 일반 리버스 프록시
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
