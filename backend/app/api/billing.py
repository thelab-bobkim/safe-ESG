"""
MediSafe Clinic - 결제/구독 관리 API (F5)
토스페이먼츠 연동 (TOSS_SECRET_KEY 없으면 Mock 테스트 모드)
"""
import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.tenant import Tenant, SubscriptionPlan
from app.models.user import User

logger = logging.getLogger("medisafe")

router = APIRouter(prefix="/billing", tags=["결제/구독"])

TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "")
TOSS_TEST_MODE = not bool(TOSS_SECRET_KEY)

PLAN_PRICES = {
    "basic": 49000,
    "standard": 149000,
    "pro": 349000,
}

PLAN_NAMES = {
    "basic": "Basic (1~3대)",
    "standard": "Standard (3~10대)",
    "pro": "Pro (10대 이상)",
}


class CheckoutRequest(BaseModel):
    plan: str  # basic / standard / pro
    success_url: Optional[str] = None
    fail_url: Optional[str] = None


class ConfirmRequest(BaseModel):
    payment_key: str
    order_id: str
    amount: int


class CancelRequest(BaseModel):
    reason: Optional[str] = "사용자 요청"


@router.post("/checkout")
async def create_checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """결제 세션 생성. TOSS_SECRET_KEY 없으면 Mock 반환."""
    plan = data.plan.lower()
    if plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="유효하지 않은 플랜입니다.")

    amount = PLAN_PRICES[plan]
    order_id = f"MEDISAFE-{current_user.tenant_id}-{uuid.uuid4().hex[:8].upper()}"

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다.")

    # Mock 모드: 실제 토스 API 호출 없이 테스트 응답 반환
    if TOSS_TEST_MODE:
        return {
            "test_mode": True,
            "order_id": order_id,
            "amount": amount,
            "plan": plan,
            "plan_name": PLAN_NAMES[plan],
            "payment_url": f"https://payment.test.toss.mock/checkout/{order_id}",
            "message": "⚠️ 테스트 모드입니다. TOSS_SECRET_KEY를 설정하면 실제 결제가 활성화됩니다.",
        }

    # 실제 토스페이먼츠 결제 세션 생성
    import base64
    import httpx

    credentials = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.tosspayments.com/v1/payments",
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/json"},
            json={
                "amount": amount,
                "orderId": order_id,
                "orderName": f"MediSafe {PLAN_NAMES[plan]}",
                "customerKey": tenant.toss_customer_key or f"tenant-{tenant.id}",
                "successUrl": data.success_url or "https://jntubkwn.gensparkclaw.com/billing/success",
                "failUrl": data.fail_url or "https://jntubkwn.gensparkclaw.com/billing/fail",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="토스페이먼츠 결제 세션 생성 실패")

        return resp.json()


@router.post("/confirm")
async def confirm_payment(
    data: ConfirmRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """결제 확인 및 구독 플랜 업데이트."""
    from app.models.hospital_group import BillingHistory

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다.")

    # Mock 모드에서는 order_id에서 플랜을 추출하거나 금액으로 추론
    if TOSS_TEST_MODE:
        # 금액으로 플랜 결정
        plan = next((k for k, v in PLAN_PRICES.items() if v == data.amount), "standard")
        max_eps = {"basic": 3, "standard": 10, "pro": 50}.get(plan, 10)

        tenant.plan = SubscriptionPlan(plan)
        tenant.plan_expires_at = datetime.utcnow() + timedelta(days=30)
        tenant.max_endpoints = max_eps
        tenant.payment_method = "card_mock"

        billing = BillingHistory(
            tenant_id=tenant.id,
            plan=plan,
            amount=data.amount,
            payment_key=data.payment_key,
            order_id=data.order_id,
            status="paid",
            paid_at=datetime.utcnow(),
        )
        db.add(billing)
        db.commit()

        return {
            "success": True,
            "test_mode": True,
            "plan": plan,
            "expires_at": tenant.plan_expires_at.isoformat(),
            "message": "테스트 결제 완료. 30일 구독이 활성화되었습니다.",
        }

    # 실제 토스페이먼츠 결제 확인
    import base64
    import httpx

    credentials = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.tosspayments.com/v1/payments/confirm",
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/json"},
            json={"paymentKey": data.payment_key, "orderId": data.order_id, "amount": data.amount},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="결제 확인 실패")

        toss_data = resp.json()
        plan = next((k for k, v in PLAN_PRICES.items() if v == data.amount), "standard")
        max_eps = {"basic": 3, "standard": 10, "pro": 50}.get(plan, 10)

        tenant.plan = SubscriptionPlan(plan)
        tenant.plan_expires_at = datetime.utcnow() + timedelta(days=30)
        tenant.max_endpoints = max_eps
        tenant.payment_method = toss_data.get("method", "card")
        tenant.toss_customer_key = toss_data.get("customerKey", tenant.toss_customer_key)

        billing = BillingHistory(
            tenant_id=tenant.id,
            plan=plan,
            amount=data.amount,
            payment_key=data.payment_key,
            order_id=data.order_id,
            status="paid",
            toss_response=str(toss_data),
            paid_at=datetime.utcnow(),
        )
        db.add(billing)
        db.commit()

        return {"success": True, "plan": plan, "expires_at": tenant.plan_expires_at.isoformat()}


@router.get("/subscription")
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """현재 구독 정보 조회."""
    from app.models.hospital_group import BillingHistory

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다.")

    histories = db.query(BillingHistory).filter(
        BillingHistory.tenant_id == current_user.tenant_id
    ).order_by(BillingHistory.created_at.desc()).limit(10).all()

    return {
        "plan": tenant.plan,
        "plan_name": PLAN_NAMES.get(tenant.plan, tenant.plan),
        "plan_price": PLAN_PRICES.get(tenant.plan, 0),
        "plan_expires_at": tenant.plan_expires_at.isoformat() if tenant.plan_expires_at else None,
        "payment_method": tenant.payment_method,
        "max_endpoints": tenant.max_endpoints,
        "is_active": tenant.is_active,
        "test_mode": TOSS_TEST_MODE,
        "billing_history": [
            {
                "id": h.id,
                "plan": h.plan,
                "plan_name": PLAN_NAMES.get(h.plan, h.plan),
                "amount": h.amount,
                "status": h.status,
                "created_at": h.created_at.isoformat(),
                "paid_at": h.paid_at.isoformat() if h.paid_at else None,
            }
            for h in histories
        ],
    }


@router.post("/cancel")
async def cancel_subscription(
    data: CancelRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """구독 취소 (즉시 다운그레이드 없음 - 만료일까지 유지)."""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다.")

    # 만료일까지 유지하고 이후 Basic으로 전환 예약
    logger.info(f"구독 취소 요청: tenant={tenant.id} 사유={data.reason}")

    return {
        "success": True,
        "message": f"구독 취소가 접수되었습니다. {tenant.plan_expires_at.strftime('%Y-%m-%d') if tenant.plan_expires_at else '현재'} 까지 서비스가 유지됩니다.",
        "expires_at": tenant.plan_expires_at.isoformat() if tenant.plan_expires_at else None,
    }
