"""
모든 모델을 한번에 임포트하여 SQLAlchemy 관계 매핑이 올바르게 설정되도록 합니다.
"""
from app.models.tenant import Tenant, SubscriptionPlan, TenantStatus
from app.models.user import User, UserRole
from app.models.endpoint import Endpoint, USBEvent, OSType, EndpointStatus
from app.models.log import AccessLog, LogEventType, LogSeverity
from app.models.compliance import ComplianceItem, ComplianceCheck, ComplianceCheckResult, RegulationType, CheckStatus

__all__ = [
    "Tenant", "SubscriptionPlan", "TenantStatus",
    "User", "UserRole",
    "Endpoint", "USBEvent", "OSType", "EndpointStatus",
    "AccessLog", "LogEventType", "LogSeverity",
    "ComplianceItem", "ComplianceCheck", "ComplianceCheckResult", "RegulationType", "CheckStatus",
]
