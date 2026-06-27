"""
MediSafe Clinic - SafeEndpoint 모듈 모델
병원 내 PC/노트북 엔드포인트의 보안 상태를 관리합니다.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class OSType(str, enum.Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class EndpointStatus(str, enum.Enum):
    ONLINE = "online"      # 온라인
    OFFLINE = "offline"    # 오프라인
    WARNING = "warning"    # 경고 (보안 이슈 있음)
    CRITICAL = "critical"  # 위험 (즉각 조치 필요)


class Endpoint(Base):
    """엔드포인트(PC) 테이블"""
    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # 기기 기본 정보
    hostname = Column(String(100), nullable=False, comment="컴퓨터 이름")
    ip_address = Column(String(45), nullable=True, comment="IP 주소")
    mac_address = Column(String(17), nullable=True, comment="MAC 주소")
    os_type = Column(Enum(OSType), nullable=False, comment="운영체제 종류")
    os_version = Column(String(100), nullable=True, comment="운영체제 버전")
    location = Column(String(100), nullable=True, comment="위치 (예: 진료실 1)")

    # 에이전트 정보
    agent_version = Column(String(20), nullable=True, comment="설치된 에이전트 버전")
    agent_token = Column(String(100), unique=True, nullable=True, comment="에이전트 인증 토큰")
    status = Column(Enum(EndpointStatus), default=EndpointStatus.OFFLINE)
    last_seen_at = Column(DateTime, nullable=True, comment="마지막 온라인 시간")

    # 보안 상태 (에이전트가 주기적으로 업데이트)
    disk_encrypted = Column(Boolean, nullable=True, comment="디스크 암호화 여부")
    antivirus_installed = Column(Boolean, nullable=True, comment="백신 설치 여부")
    antivirus_updated = Column(Boolean, nullable=True, comment="백신 최신 업데이트 여부")
    os_patched = Column(Boolean, nullable=True, comment="OS 최신 패치 적용 여부")
    usb_blocked = Column(Boolean, nullable=True, comment="USB 차단 정책 적용 여부")
    firewall_enabled = Column(Boolean, nullable=True, comment="방화벽 활성화 여부")
    screen_lock_enabled = Column(Boolean, nullable=True, comment="화면 잠금 설정 여부")

    # 보안 점수 (0-100)
    security_score = Column(Float, default=0.0, comment="현재 보안 점수")
    score_details = Column(JSON, nullable=True, comment="점수 세부 내역")

    # 상태
    is_active = Column(Boolean, default=True)
    registered_at = Column(DateTime, server_default=func.now(), comment="등록일")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 관계
    tenant = relationship("Tenant", back_populates="endpoints")
    usb_events = relationship("USBEvent", back_populates="endpoint", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Endpoint {self.hostname} ({self.status})>"


class USBEvent(Base):
    """USB 연결/해제 이벤트 테이블 (WORM - 삭제 불가)"""
    __tablename__ = "usb_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False, index=True)

    event_type = Column(String(20), nullable=False, comment="connect / disconnect")
    device_name = Column(String(200), nullable=True, comment="USB 장치명")
    device_id = Column(String(100), nullable=True, comment="USB 장치 ID")
    blocked = Column(Boolean, default=False, comment="차단 여부")

    # WORM: 이 레코드는 절대 삭제하지 않습니다
    is_worm = Column(Boolean, default=True, comment="WORM 보존 플래그 - 절대 삭제 금지")
    occurred_at = Column(DateTime, server_default=func.now(), comment="발생 시각")

    # 관계
    endpoint = relationship("Endpoint", back_populates="usb_events")
