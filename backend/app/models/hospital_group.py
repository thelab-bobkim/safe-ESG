"""
MediSafe Clinic - 다중 지점(병원 그룹) 모델 (F9)
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class HospitalGroup(Base):
    """병원 그룹 테이블 - 다중 지점 관리"""
    __tablename__ = "hospital_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="그룹명")
    owner_tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, comment="대표 병원 tenant_id")
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<HospitalGroup {self.name}>"


class BillingHistory(Base):
    """결제 이력 테이블 (F5)"""
    __tablename__ = "billing_histories"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    plan = Column(String(50), nullable=False)
    amount = Column(Integer, nullable=False)
    payment_key = Column(String(200), nullable=True)
    order_id = Column(String(200), nullable=True)
    status = Column(String(50), default="pending")
    toss_response = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", foreign_keys=[tenant_id])
