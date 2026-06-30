"""
MediSafe Clinic Ver-1 - FastAPI 애플리케이션 진입점
개인정보보호법 제29조, 의료법 제23조 준수

Ver-1 보안 강화 항목:
  1. Rate Limiting (SlowAPI) - 로그인 10회/분, API 100회/분
  2. 보안 HTTP 헤더 (HSTS, CSP, X-Frame-Options 등)
  3. CORS 정책 강화 (허용 Origin 명시)
  4. 요청 크기 제한 (10MB)
  5. 응답에서 서버 정보 숨김 (X-Powered-By 제거)
  6. 감사 로그 시스템 초기화
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.core.rate_limit import limiter
from app.core.security import hash_password, generate_agent_token

# 라우터 등록
from app.api import auth, endpoints, logs, compliance, dashboard, billing, groups

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medisafe")


# ──────────────────────────────────────────────
# 시드 데이터 (초기 병원 2개 + 직원)
# ──────────────────────────────────────────────

async def seed_initial_data():
    """
    개발/데모용 초기 데이터 삽입
    운영 환경에서는 별도 관리자 도구 사용
    """
    import app.models  # noqa - 모든 모델 등록
    from app.models.tenant import Tenant, SubscriptionPlan
    from app.models.user import User, UserRole
    from app.models.endpoint import Endpoint, EndpointStatus, OSType
    from app.models.log import AccessLog, LogEventType as EventType, LogSeverity as Severity
    from app.models.compliance import ComplianceCheck, ComplianceItem, CheckStatus

    db = SessionLocal()
    try:
        # 이미 데이터 있으면 스킵
        if db.query(Tenant).count() > 0:
            logger.info("시드 데이터 이미 존재 - 스킵")
            return

        logger.info("초기 시드 데이터 삽입 중...")

        # ── 테넌트 1: 연세가정의원 (Standard) ──
        t1 = Tenant(
            name="연세가정의원", business_number="123-45-67890",
            address="서울시 강남구 테헤란로 123", phone="02-1234-5678",
            plan=SubscriptionPlan.STANDARD, max_endpoints=10, is_active=True,
        )
        db.add(t1)
        db.flush()

        # 원장
        u1 = User(
            tenant_id=t1.id, email="doctor@yonsei-clinic.kr",
            hashed_password=hash_password("Doctor1234!"),
            name="김연세", role=UserRole.ADMIN,
            password_changed_at=datetime.utcnow(),
        )
        # 직원
        u2 = User(
            tenant_id=t1.id, email="staff@yonsei-clinic.kr",
            hashed_password=hash_password("Staff1234!"),
            name="이직원", role=UserRole.STAFF,
            password_changed_at=datetime.utcnow(),
        )
        db.add_all([u1, u2])

        # 엔드포인트 5대
        endpoints_data = [
            ("YONSEI-PC001", "192.168.1.10", "원장실", True, True, True, True, True, 95.0),
            ("YONSEI-PC002", "192.168.1.11", "진료실 1", True, True, True, True, False, 85.0),
            ("YONSEI-PC003", "192.168.1.12", "진료실 2", False, True, True, True, False, 45.0),
            ("YONSEI-PC004", "192.168.1.13", "원무 데스크", True, True, True, True, True, 100.0),
            ("YONSEI-LAPTOP", "192.168.1.20", "이동용", True, True, True, True, True, 96.5),
        ]
        ep_list = []
        for hostname, ip, loc, enc, av, patch, fw, sl, score in endpoints_data:
            ep = Endpoint(
                tenant_id=t1.id, hostname=hostname, ip_address=ip,
                location=loc, os_type=OSType.WINDOWS, os_version="Windows 11 Pro",
                status=EndpointStatus.ONLINE,
                disk_encrypted=enc, antivirus_installed=av, os_patched=patch,
                firewall_enabled=fw, screen_lock_enabled=sl,
                security_score=score,
                agent_token=generate_agent_token(),
                agent_token_revoked=False,
                agent_token_issued_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
            db.add(ep)
            ep_list.append(ep)
        db.flush()

        # 샘플 로그
        sample_logs = [
            (EventType.LOGIN_SUCCESS, Severity.INFO, "success", "원장 로그인"),
            (EventType.EMR_ACCESS,    Severity.INFO, "success", "환자 기록 조회"),
            (EventType.EMR_MODIFY,    Severity.WARNING, "success", "처방전 수정"),
            (EventType.FILE_ACCESS,   Severity.INFO, "success", "X-ray 파일 조회"),
            (EventType.LOGIN_FAIL,    Severity.WARNING, "fail", "비밀번호 오류"),
            (EventType.EMR_ACCESS,    Severity.CRITICAL, "success", "심야 비정상 접근 탐지"),
            (EventType.EMR_ACCESS,    Severity.INFO, "success", "외래환자 기록 조회"),
            (EventType.LOGIN_SUCCESS, Severity.INFO, "success", "직원 로그인"),
            (EventType.SYSTEM_EVENT,  Severity.INFO, "success", "백신 정의 파일 업데이트"),
        ]
        for evt, sev, res, desc in sample_logs:
            log = AccessLog(
                tenant_id=t1.id, user_id=u1.id, endpoint_id=ep_list[0].id,
                event_type=evt, severity=sev, result=res, description=desc,
                user_email=u1.email, ip_address="192.168.1.10",
                is_worm=True,
            )
            db.add(log)

        # ── 테넌트 2: 서울연합치과 (Basic, 체험) ──
        t2 = Tenant(
            name="서울연합치과", business_number="234-56-78901",
            address="서울시 서초구 서초대로 456", phone="02-9876-5432",
            plan=SubscriptionPlan.BASIC, max_endpoints=3, is_active=True,
        )
        db.add(t2)
        db.flush()
        u3 = User(
            tenant_id=t2.id, email="doctor@seoul-dental.kr",
            hashed_password=hash_password("Doctor5678!"),
            name="박치과", role=UserRole.ADMIN,
            password_changed_at=datetime.utcnow(),
        )
        db.add(u3)
        db.flush()

        ep2 = Endpoint(
            tenant_id=t2.id, hostname="DENTAL-PC001", ip_address="192.168.2.10",
            location="진료실", os_type=OSType.WINDOWS, os_version="Windows 10 Pro",
            status=EndpointStatus.ONLINE,
            disk_encrypted=False, antivirus_installed=True, os_patched=False,
            firewall_enabled=True, screen_lock_enabled=False,
            security_score=52.0,
            agent_token=generate_agent_token(),
            agent_token_revoked=False,
            agent_token_issued_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
        )
        db.add(ep2)

        # 컴플라이언스 체크리스트
        from app.api.compliance import _seed_compliance
        db.flush()
        _seed_compliance(db, t1.id)
        _seed_compliance(db, t2.id)

        # 슈퍼관리자
        superadmin = User(
            tenant_id=None, email="admin@medisafe.clinic",
            hashed_password=hash_password("Admin@MediSafe2024!"),
            name="시스템관리자", role=UserRole.SUPERADMIN,
            password_changed_at=datetime.utcnow(),
        )
        db.add(superadmin)

        db.commit()
        logger.info("✅ 시드 데이터 삽입 완료 (Ver-1)")

    except Exception as e:
        db.rollback()
        logger.error(f"시드 데이터 오류: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


# ──────────────────────────────────────────────
# 앱 수명주기
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 수명주기"""
    import app.models  # noqa
    import app.models.hospital_group  # noqa - F9 모델 등록
    Base.metadata.create_all(bind=engine)
    await seed_initial_data()

    # ── APScheduler: 주간 보안 리포트 자동 발송 (F6) ──
    scheduler = None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.services.weekly_report_service import send_all_weekly_reports

        scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
        scheduler.add_job(
            lambda: send_all_weekly_reports(SessionLocal),
            CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="Asia/Seoul"),
            id="weekly_security_report",
            name="주간 보안 리포트 발송",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("✅ APScheduler 시작: 매주 월요일 09:00 KST 주간 리포트 발송")
    except ImportError:
        logger.warning("⚠️ apscheduler 미설치 - 주간 리포트 스케줄러 비활성. pip install apscheduler")
    except Exception as e:
        logger.warning(f"⚠️ APScheduler 시작 실패 (서버는 정상 운영): {e}")

    logger.info(f"🏥 MediSafe Clinic Ver-2 시작 ({settings.APP_VERSION})")
    yield

    # 종료 시 스케줄러 정리
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
    logger.info("MediSafe Clinic 서버 종료")


# ──────────────────────────────────────────────
# FastAPI 앱 생성
# ──────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
MediSafe Clinic Ver-1 - 소형 병·의원용 의료정보보호 SaaS

## 보안 기준
- 개인정보보호법 제29조 (기술적/관리적 보호조치)
- 의료법 제23조 (전자의무기록 보안)
- NIST SP 800-63B (인증 표준)

## 인증
Bearer JWT 토큰 (4시간 유효)
    """,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,  # 운영환경 Swagger 비공개
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Rate Limiter 등록
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ──────────────────────────────────────────────
# CORS (운영: 실제 도메인만 허용)
# ──────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "https://jntubkwn.gensparkclaw.com",  # 운영 도메인
    "http://localhost:3000",               # 개발
    "http://localhost:5173",               # Vite dev
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# ──────────────────────────────────────────────
# 보안 HTTP 헤더 미들웨어 (개인정보보호법 제29조)
# ──────────────────────────────────────────────

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    OWASP 권고 보안 헤더 추가
    - HSTS: HTTPS 강제 (1년)
    - CSP: XSS 방어
    - X-Frame-Options: 클릭재킹 방어
    - X-Content-Type-Options: MIME 스니핑 방어
    """
    response = await call_next(request)

    # 서버 정보 숨김
    if "server" in response.headers:
        del response.headers["server"]
    if "x-powered-by" in response.headers:
        del response.headers["x-powered-by"]

    # HSTS (HTTPS 강제, 1년)
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains; preload"
    )
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self';"
    )
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["X-Content-Type-Options"]   = "nosniff"
    response.headers["Referrer-Policy"]          = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]       = (
        "geolocation=(), microphone=(), camera=()"
    )
    return response


# ──────────────────────────────────────────────
# 요청 로깅 미들웨어 (API 감사 추적)
# ──────────────────────────────────────────────

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """API 요청 로깅 (민감 정보 제외)"""
    import time, uuid

    request_id = str(uuid.uuid4())[:8]
    start = time.time()

    # 요청 크기 제한 (10MB)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content={"detail": "요청 크기가 너무 큽니다 (최대 10MB)."}
        )

    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000)

    # 비밀번호 포함 경로는 body 로깅 안 함
    log_msg = f"[{request_id}] {request.method} {request.url.path} → {response.status_code} ({elapsed}ms)"
    if response.status_code >= 400:
        logger.warning(log_msg)
    else:
        logger.info(log_msg)

    response.headers["X-Request-ID"] = request_id
    return response


# ──────────────────────────────────────────────
# 라우터 등록
# ──────────────────────────────────────────────
app.include_router(auth.router,       prefix="/api/v1")
app.include_router(endpoints.router,  prefix="/api/v1")
app.include_router(logs.router,       prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(dashboard.router,  prefix="/api/v1")
app.include_router(billing.router,    prefix="/api/v1")   # F5 결제/구독
app.include_router(groups.router,     prefix="/api/v1")   # F9 다중지점


# ──────────────────────────────────────────────
# 헬스체크 + 버전 정보
# ──────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "compliance": ["개인정보보호법 제29조", "의료법 제23조"],
    }
