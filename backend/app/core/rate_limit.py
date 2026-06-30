"""
MediSafe Clinic Ver-1 - API Rate Limiting
무차별 대입 공격, DoS 방어

정책:
  - 로그인 API:   10회/분 (IP 기준)
  - 일반 API:    100회/분 (사용자 기준)
  - 에이전트 API: 30회/분 (토큰 기준)
  - 관리자 API:  200회/분
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def _get_key(request: Request) -> str:
    """
    Rate Limit 키 결정 (Cloudflare 헤더 우선)
    """
    # Cloudflare 실제 IP
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    # 일반 프록시
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_key)

# 각 API에서 import해서 사용하는 데코레이터
LOGIN_LIMIT   = "10/minute"     # 로그인 시도 제한
API_LIMIT     = "100/minute"    # 일반 API
AGENT_LIMIT   = "30/minute"     # 에이전트 heartbeat
EXPORT_LIMIT  = "5/minute"      # CSV/데이터 내보내기
ADMIN_LIMIT   = "200/minute"    # 관리자 작업
