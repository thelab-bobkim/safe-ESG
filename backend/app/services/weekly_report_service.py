"""
MediSafe Clinic - 주간 보안 리포트 서비스 (F6)
매주 월요일 09:00 KST 자동 발송
"""
import logging
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("medisafe")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def generate_weekly_report(tenant_id: int, db) -> dict:
    """지난 7일 통계 수집 및 리포트 데이터 생성."""
    from app.models.tenant import Tenant
    from app.models.endpoint import Endpoint, EndpointStatus
    from app.models.log import AccessLog, LogSeverity
    from app.models.compliance import ComplianceCheck, CheckStatus

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return {}

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    # 엔드포인트 현황
    endpoints = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id,
        Endpoint.is_active == True,
    ).all()

    total_eps = len(endpoints)
    online_eps = sum(1 for e in endpoints if e.status == EndpointStatus.ONLINE)
    avg_score = sum(e.security_score or 0 for e in endpoints) / max(total_eps, 1)

    # 이번 주 보안 이벤트
    logs = db.query(AccessLog).filter(
        AccessLog.tenant_id == tenant_id,
        AccessLog.occurred_at >= week_ago,
    ).all()

    critical_count = sum(1 for l in logs if l.severity and str(l.severity) in ['critical', 'LogSeverity.CRITICAL'])
    warning_count = sum(1 for l in logs if l.severity and str(l.severity) in ['warning', 'LogSeverity.WARNING'])
    failed_login = sum(1 for l in logs if l.event_type and 'login_fail' in str(l.event_type))

    # 미조치 항목
    latest_check = db.query(ComplianceCheck).filter(
        ComplianceCheck.tenant_id == tenant_id
    ).order_by(ComplianceCheck.checked_at.desc()).first()

    pending_items = []
    if latest_check:
        from app.models.compliance import ComplianceCheckResult
        results = db.query(ComplianceCheckResult).filter(
            ComplianceCheckResult.check_id == latest_check.id,
        ).all()
        pending_items = [
            {
                "title": r.item.title if r.item else "알 수 없음",
                "status": str(r.status),
            }
            for r in results
            if r.status and str(r.status) in ['CheckStatus.FAIL', 'CheckStatus.PENDING', 'fail', 'pending']
        ]

    # PC별 보안점수
    endpoint_scores = [
        {
            "hostname": e.hostname,
            "location": e.location or "-",
            "score": e.security_score or 0,
            "status": str(e.status),
        }
        for e in sorted(endpoints, key=lambda x: x.security_score or 0)
    ]

    return {
        "tenant_name": tenant.name,
        "tenant_email": tenant.email,
        "report_period": f"{week_ago.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}",
        "total_endpoints": total_eps,
        "online_endpoints": online_eps,
        "avg_security_score": round(avg_score, 1),
        "critical_events": critical_count,
        "warning_events": warning_count,
        "failed_logins": failed_login,
        "total_events": len(logs),
        "pending_items": pending_items,
        "endpoint_scores": endpoint_scores,
        "compliance_score": round(latest_check.total_score, 1) if latest_check else None,
        "generated_at": now.isoformat(),
    }


def _generate_html(report: dict) -> str:
    """HTML 이메일 생성."""
    pending_html = ""
    for item in report.get("pending_items", []):
        pending_html += f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{item['title']}</td><td style='padding:8px;border-bottom:1px solid #eee;color:#dc3545'>{item['status']}</td></tr>"

    ep_html = ""
    for ep in report.get("endpoint_scores", []):
        color = "#dc3545" if ep["score"] < 60 else "#fd7e14" if ep["score"] < 80 else "#28a745"
        ep_html += f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{ep['hostname']}</td><td>{ep['location']}</td><td style='color:{color};font-weight:bold'>{ep['score']:.0f}점</td><td>{ep['status']}</td></tr>"

    score = report.get('avg_security_score', 0)
    score_color = "#dc3545" if score < 60 else "#fd7e14" if score < 80 else "#28a745"

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Apple SD Gothic Neo,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f7fa">
<div style="background:white;border-radius:12px;padding:30px;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
  <div style="text-align:center;margin-bottom:24px">
    <div style="background:#1e40af;display:inline-block;padding:12px 24px;border-radius:8px">
      <span style="color:white;font-size:20px;font-weight:bold">🏥 MediSafe Clinic</span>
    </div>
    <h2 style="color:#1e293b;margin-top:16px">주간 보안 리포트</h2>
    <p style="color:#64748b">{report.get('tenant_name', '')} | {report.get('report_period', '')}</p>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:24px">
    <div style="background:#eff6ff;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:{score_color}">{score:.0f}</div>
      <div style="font-size:12px;color:#64748b">평균 보안점수</div>
    </div>
    <div style="background:#fef3c7;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#d97706">{report.get('critical_events', 0)}</div>
      <div style="font-size:12px;color:#64748b">위험 이벤트</div>
    </div>
    <div style="background:#f0fdf4;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:bold;color:#16a34a">{report.get('online_endpoints', 0)}/{report.get('total_endpoints', 0)}</div>
      <div style="font-size:12px;color:#64748b">온라인 PC</div>
    </div>
  </div>

  {'<div style="margin-bottom:24px"><h3 style="color:#dc3545">⚠️ 미조치 항목</h3><table style="width:100%;border-collapse:collapse"><tr style="background:#fee2e2"><th style="padding:8px;text-align:left">항목</th><th style="padding:8px;text-align:left">상태</th></tr>' + pending_html + '</table></div>' if report.get('pending_items') else ''}

  <div style="margin-bottom:24px">
    <h3 style="color:#1e293b">PC별 보안 점수</h3>
    <table style="width:100%;border-collapse:collapse">
      <tr style="background:#f1f5f9"><th style="padding:8px;text-align:left">PC명</th><th>위치</th><th>점수</th><th>상태</th></tr>
      {ep_html}
    </table>
  </div>

  <div style="background:#f8fafc;border-radius:8px;padding:16px;font-size:12px;color:#64748b;text-align:center">
    이 리포트는 MediSafe Clinic에서 자동으로 발송됩니다.<br>
    문의: support@medisafe.clinic
  </div>
</div>
</body>
</html>
"""


def send_weekly_report(tenant_id: int, db) -> bool:
    """주간 보안 리포트 이메일 발송."""
    try:
        report = generate_weekly_report(tenant_id, db)
        if not report or not report.get("tenant_email"):
            logger.info(f"[주간리포트] tenant_id={tenant_id} 이메일 주소 없음, 스킵")
            return False

        html_content = _generate_html(report)

        if not SMTP_USER or not SMTP_PASSWORD:
            logger.info(f"[주간리포트] SMTP 미설정 (tenant_id={tenant_id}), 리포트 생성만 완료")
            logger.info(f"리포트 미리보기: {report}")
            return True

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[MediSafe] {report['tenant_name']} 주간 보안 리포트 ({report['report_period']})"
        msg["From"] = SMTP_USER
        msg["To"] = report["tenant_email"]
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [report["tenant_email"]], msg.as_string())

        logger.info(f"[주간리포트] 발송 완료: {report['tenant_name']} → {report['tenant_email']}")
        return True

    except Exception as e:
        logger.error(f"[주간리포트] 발송 오류 (tenant_id={tenant_id}): {e}")
        return False


def send_all_weekly_reports(db_factory):
    """전체 tenant 주간 리포트 발송."""
    from app.models.tenant import Tenant
    try:
        db = db_factory()
        try:
            tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
            logger.info(f"[주간리포트] 전체 발송 시작: {len(tenants)}개 병원")
            for tenant in tenants:
                send_weekly_report(tenant.id, db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[주간리포트] 전체 발송 오류: {e}")
