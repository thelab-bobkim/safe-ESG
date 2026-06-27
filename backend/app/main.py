"""
MediSafe Clinic - FastAPI 메인 애플리케이션
의료보안 SaaS 베타 버전 - 소형 병·의원 대상
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import engine, Base
# 모든 모델을 먼저 임포트하여 관계 설정 완료
import app.models  # noqa: F401
from app.api import auth, endpoints, logs, compliance, dashboard

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 이벤트 처리"""
    # 시작: DB 테이블 생성 및 초기 데이터 삽입
    logger.info("🏥 MediSafe Clinic 시작 중...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 데이터베이스 테이블 생성 완료")

    # 초기 데이터 삽입
    await seed_initial_data()

    yield

    logger.info("👋 MediSafe Clinic 종료")


async def seed_initial_data():
    """초기 데이터(시드) 삽입"""
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    from app.models.tenant import Tenant, SubscriptionPlan, TenantStatus
    from app.models.user import User, UserRole
    from app.models.endpoint import Endpoint, OSType, EndpointStatus
    from app.models.log import AccessLog, LogEventType, LogSeverity
    from app.models.compliance import ComplianceItem, RegulationType, ComplianceCheck, ComplianceCheckResult, CheckStatus
    from app.core.security import hash_password
    from datetime import datetime, timedelta

    db: Session = SessionLocal()
    try:
        # 이미 데이터가 있으면 스킵
        if db.query(Tenant).first():
            logger.info("ℹ️ 초기 데이터 이미 존재 - 스킵")
            return

        logger.info("🌱 초기 데이터 삽입 중...")

        # ── 슈퍼관리자 계정 ──────────────────────────────
        superadmin = User(
            tenant_id=None,
            email="admin@medisafe.clinic",
            hashed_password=hash_password("Admin1234!"),
            name="시스템 관리자",
            role=UserRole.SUPERADMIN,
            is_active=True,
        )
        db.add(superadmin)
        db.flush()

        # ── 테넌트 1: 연세가정의원 ──────────────────────
        tenant1 = Tenant(
            name="연세가정의원",
            business_number="123-45-67890",
            address="서울특별시 강남구 테헤란로 123",
            phone="02-1234-5678",
            email="admin@yonsei-clinic.kr",
            plan=SubscriptionPlan.STANDARD,
            status=TenantStatus.ACTIVE,
            max_endpoints=10,
            subscription_starts_at=datetime.utcnow() - timedelta(days=60),
            subscription_ends_at=datetime.utcnow() + timedelta(days=305),
        )
        db.add(tenant1)
        db.flush()

        # 연세가정의원 관리자 (원장)
        admin1 = User(
            tenant_id=tenant1.id,
            email="doctor@yonsei-clinic.kr",
            hashed_password=hash_password("Doctor1234!"),
            name="김원장",
            role=UserRole.ADMIN,
            is_active=True,
        )
        # 연세가정의원 직원 (원무)
        staff1 = User(
            tenant_id=tenant1.id,
            email="staff@yonsei-clinic.kr",
            hashed_password=hash_password("Staff1234!"),
            name="이간호사",
            role=UserRole.STAFF,
            is_active=True,
        )
        db.add_all([admin1, staff1])
        db.flush()

        # 연세가정의원 엔드포인트 5대
        ep_data = [
            ("YONSEI-PC001", "192.168.1.11", OSType.WINDOWS, "Windows 11 Pro", "원장실", True, True, True, True, False, True, True),
            ("YONSEI-PC002", "192.168.1.12", OSType.WINDOWS, "Windows 10 Pro", "진료실 1", True, True, False, True, True, True, True),
            ("YONSEI-PC003", "192.168.1.13", OSType.WINDOWS, "Windows 10 Pro", "진료실 2", False, True, True, False, True, False, True),
            ("YONSEI-PC004", "192.168.1.14", OSType.WINDOWS, "Windows 11 Home", "원무 데스크", True, True, True, True, True, True, True),
            ("YONSEI-LAPTOP", "192.168.1.20", OSType.MACOS, "macOS 14 Sonoma", "이동용", True, True, True, True, None, True, True),
        ]
        for h, ip, os_t, os_v, loc, enc, av, av_up, patch, usb, fw, sl in ep_data:
            from app.services.security_score import calculate_endpoint_score
            ep = Endpoint(
                tenant_id=tenant1.id,
                hostname=h, ip_address=ip, os_type=os_t, os_version=os_v,
                location=loc, agent_version="1.0.0-beta",
                status=EndpointStatus.ONLINE,
                disk_encrypted=enc, antivirus_installed=av, antivirus_updated=av_up,
                os_patched=patch, usb_blocked=usb, firewall_enabled=fw,
                screen_lock_enabled=sl,
                last_seen_at=datetime.utcnow() - timedelta(minutes=5),
            )
            db.add(ep)
            db.flush()
            score = calculate_endpoint_score(ep)
            ep.security_score = score["total"]
            ep.score_details = score["details"]

        # 연세가정의원 접속 로그 샘플
        log_samples = [
            (admin1.id, "김원장", admin1.email, LogEventType.LOGIN_SUCCESS, LogSeverity.INFO, "192.168.1.11", "YONSEI-PC001", None, "로그인", "success", "원장 정상 로그인"),
            (staff1.id, "이간호사", staff1.email, LogEventType.EMR_ACCESS, LogSeverity.INFO, "192.168.1.14", "YONSEI-PC004", "환자ID:10042", "EMR 접속", "success", "환자 차트 조회"),
            (staff1.id, "이간호사", staff1.email, LogEventType.EMR_QUERY, LogSeverity.INFO, "192.168.1.14", "YONSEI-PC004", "환자ID:10042", "진료기록 조회", "success", None),
            (admin1.id, "김원장", admin1.email, LogEventType.POLICY_CHANGE, LogSeverity.WARNING, "192.168.1.11", "YONSEI-PC001", "USB 정책", "정책 변경", "success", "USB 차단 정책 적용"),
            (None, "알수없음", "unknown@external.com", LogEventType.LOGIN_FAIL, LogSeverity.WARNING, "203.45.67.89", None, None, "로그인 시도", "fail", "외부 IP 로그인 실패"),
            (None, "알수없음", "brute@hack.com", LogEventType.LOGIN_FAIL, LogSeverity.CRITICAL, "91.234.56.78", None, None, "로그인 시도", "fail", "비정상적 로그인 시도 감지"),
            (staff1.id, "이간호사", staff1.email, LogEventType.EMR_MODIFY, LogSeverity.WARNING, "192.168.1.14", "YONSEI-PC004", "환자ID:10085", "진료기록 수정", "success", "처방 내역 수정"),
            (admin1.id, "김원장", admin1.email, LogEventType.ADMIN_ACTION, LogSeverity.INFO, "192.168.1.11", "YONSEI-PC001", None, "사용자 관리", "success", "직원 계정 비밀번호 초기화"),
        ]
        for uid, uname, uemail, etype, esev, ip, host, res, action, result, desc in log_samples:
            offset_hours = log_samples.index((uid, uname, uemail, etype, esev, ip, host, res, action, result, desc))
            log = AccessLog(
                tenant_id=tenant1.id,
                user_id=uid,
                user_name=uname,
                user_email=uemail,
                event_type=etype,
                severity=esev,
                ip_address=ip,
                endpoint_hostname=host,
                resource=res,
                action=action,
                result=result,
                description=desc,
                occurred_at=datetime.utcnow() - timedelta(hours=offset_hours * 2),
            )
            db.add(log)

        # ── 테넌트 2: 서울연합치과 ──────────────────────
        tenant2 = Tenant(
            name="서울연합치과",
            business_number="234-56-78901",
            address="서울특별시 서초구 강남대로 456",
            phone="02-9876-5432",
            email="admin@seoul-dental.kr",
            plan=SubscriptionPlan.BASIC,
            status=TenantStatus.TRIAL,
            max_endpoints=3,
            trial_ends_at=datetime.utcnow() + timedelta(days=22),
        )
        db.add(tenant2)
        db.flush()

        admin2 = User(
            tenant_id=tenant2.id,
            email="doctor@seoul-dental.kr",
            hashed_password=hash_password("Doctor5678!"),
            name="박원장",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin2)
        db.flush()

        # 치과 엔드포인트 2대
        ep2_1 = Endpoint(
            tenant_id=tenant2.id,
            hostname="DENTAL-PC001", ip_address="10.0.0.11",
            os_type=OSType.WINDOWS, os_version="Windows 10 Pro",
            location="진료실", agent_version="1.0.0-beta",
            status=EndpointStatus.WARNING,
            disk_encrypted=False, antivirus_installed=True, antivirus_updated=True,
            os_patched=False, firewall_enabled=True, screen_lock_enabled=False,
            last_seen_at=datetime.utcnow() - timedelta(minutes=15),
        )
        db.add(ep2_1)
        db.flush()
        score2 = calculate_endpoint_score(ep2_1)
        ep2_1.security_score = score2["total"]
        ep2_1.score_details = score2["details"]

        # ── 규제 체크리스트 마스터 데이터 ──────────────
        compliance_items = [
            # 개인정보보호법 제29조
            ("PA29-01", RegulationType.PRIVACY_ACT_29, "접근 권한 관리", "개인정보처리시스템에 대한 접근 권한을 업무 필요에 따라 최소한으로 부여하고 있음", "역할별 접근 권한 목록 작성 및 정기 검토", True, 1.5, 1),
            ("PA29-02", RegulationType.PRIVACY_ACT_29, "접근 통제", "개인정보처리시스템에 대한 불법적 접근 및 침해 예방을 위한 접근 통제 조치", "방화벽 설정, VPN 사용 여부 확인", True, 1.5, 2),
            ("PA29-03", RegulationType.PRIVACY_ACT_29, "접속 기록 보관", "개인정보처리시스템에 접속한 기록을 6개월 이상 보관·관리", "접속 로그 시스템 보유 여부 확인", True, 2.0, 3),
            ("PA29-04", RegulationType.PRIVACY_ACT_29, "암호화", "개인정보를 안전하게 저장·전송하기 위한 암호화 조치", "디스크 암호화, 전송 암호화(TLS) 적용 여부", True, 2.0, 4),
            ("PA29-05", RegulationType.PRIVACY_ACT_29, "악성프로그램 방지", "악성프로그램 등을 방지·치료할 수 있는 백신 소프트웨어 설치·운영", "백신 설치 및 최신 업데이트 여부 확인", True, 1.5, 5),
            ("PA29-06", RegulationType.PRIVACY_ACT_29, "물리적 보안", "전산실, 자료보관실 등 물리적 보안조치 적용", "출입통제, CCTV, 잠금장치 등 확인", False, 1.0, 6),
            # 의료법 제23조
            ("MA23-01", RegulationType.MEDICAL_ACT_23, "전자의무기록 작성기준", "전자의무기록 작성·관리·보존에 관한 기준 준수", "EMR 시스템 인증 여부 확인", True, 2.0, 7),
            ("MA23-02", RegulationType.MEDICAL_ACT_23, "EMR 접근 통제", "전자의무기록에 대한 접근권한 설정 및 관리", "EMR 사용자별 권한 설정 현황 확인", True, 2.0, 8),
            ("MA23-03", RegulationType.MEDICAL_ACT_23, "EMR 열람 기록", "전자의무기록 열람·수정·삭제 기록의 보관", "EMR 접속 및 수정 기록 로그 보유 여부", True, 2.0, 9),
            ("MA23-04", RegulationType.MEDICAL_ACT_23, "의무기록 보존", "의무기록 법정 보존 기간(외래 5년, 입원 10년) 준수", "데이터 백업 및 보존 기간 정책 확인", True, 1.5, 10),
            # EMR 인증 기준
            ("EMR-01", RegulationType.EMR_CERT, "EMR 시스템 인증", "보건복지부 고시 전자의무기록 시스템 인증 획득 여부", "EMR 인증서 보유 여부 확인", False, 1.5, 11),
            ("EMR-02", RegulationType.EMR_CERT, "데이터 백업 정책", "EMR 데이터 정기 백업 및 복구 계획 수립", "백업 주기, 복구 테스트 실시 여부 확인", True, 2.0, 12),
            ("EMR-03", RegulationType.EMR_CERT, "세션 관리", "장시간 미사용 시 자동 로그아웃 기능", "화면 잠금 및 세션 타임아웃 설정 확인", True, 1.0, 13),
            ("EMR-04", RegulationType.EMR_CERT, "비밀번호 정책", "강력한 비밀번호 정책 적용 및 주기적 변경", "비밀번호 복잡도, 변경주기 정책 확인", True, 1.0, 14),
        ]

        for code, reg, title, desc, guidance, mandatory, weight, order in compliance_items:
            item = ComplianceItem(
                regulation=reg, item_code=code, title=title,
                description=desc, guidance=guidance,
                is_mandatory=mandatory, weight=weight, order_num=order,
            )
            db.add(item)
        db.flush()

        # 테넌트1 컴플라이언스 점검 샘플
        check_items = db.query(ComplianceItem).all()
        check = ComplianceCheck(
            tenant_id=tenant1.id,
            checked_by=admin1.id,
            checked_by_name="김원장",
            next_check_at=datetime.utcnow() + timedelta(days=25),
        )
        db.add(check)
        db.flush()

        statuses_map = {
            "PA29-01": CheckStatus.PASS, "PA29-02": CheckStatus.PASS,
            "PA29-03": CheckStatus.PASS, "PA29-04": CheckStatus.PASS,
            "PA29-05": CheckStatus.PASS, "PA29-06": CheckStatus.PARTIAL,
            "MA23-01": CheckStatus.PASS, "MA23-02": CheckStatus.PASS,
            "MA23-03": CheckStatus.PASS, "MA23-04": CheckStatus.PARTIAL,
            "EMR-01": CheckStatus.NA, "EMR-02": CheckStatus.PASS,
            "EMR-03": CheckStatus.PASS, "EMR-04": CheckStatus.FAIL,
        }
        for item in check_items:
            result = ComplianceCheckResult(
                check_id=check.id,
                item_id=item.id,
                tenant_id=tenant1.id,
                status=statuses_map.get(item.item_code, CheckStatus.PENDING),
                evidence="MediSafe 시스템 자동 확인" if statuses_map.get(item.item_code) == CheckStatus.PASS else None,
                note="비밀번호 정책 미적용 - 조치 필요" if item.item_code == "EMR-04" else None,
            )
            db.add(result)
        db.flush()

        # 점수 계산
        from app.api.compliance import _recalculate_scores
        _recalculate_scores(db, check)

        db.commit()
        logger.info("✅ 초기 데이터 삽입 완료")
        logger.info("=" * 50)
        logger.info("🔑 기본 계정 정보:")
        logger.info("  슈퍼관리자: admin@medisafe.clinic / Admin1234!")
        logger.info("  연세가정의원 원장: doctor@yonsei-clinic.kr / Doctor1234!")
        logger.info("  연세가정의원 직원: staff@yonsei-clinic.kr / Staff1234!")
        logger.info("  서울연합치과 원장: doctor@seoul-dental.kr / Doctor5678!")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"❌ 초기 데이터 삽입 실패: {e}")
        db.rollback()
    finally:
        db.close()


# FastAPI 앱 생성
app = FastAPI(
    title="MediSafe Clinic API",
    description="소형 병·의원 의료정보보호 SaaS 플랫폼 베타",
    version="0.1.0-beta",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 미들웨어 (프론트엔드 연결)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(auth.router, prefix="/api/v1")
app.include_router(endpoints.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "MediSafe Clinic API",
        "version": "0.1.0-beta",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {"status": "healthy", "service": "MediSafe Clinic"}
