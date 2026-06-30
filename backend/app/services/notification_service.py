"""
MediSafe Clinic - 보안 알림 서비스
심각한 보안 이벤트를 이메일로 관리자에게 통보합니다.
SMTP 설정이 없어도 에러 없이 동작합니다 (로그만 출력).
"""
import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("medisafe.notification")


async def send_security_alert(
    tenant_id: int,
    event_type: str,
    description: str,
    severity: str,
    endpoint_hostname: str,
    db: Session,
) -> bool:
    """
    보안 이벤트 알림을 발송합니다.
    severity=='critical'인 경우 해당 테넌트 관리자 이메일로 발송.
    SMTP 환경변수 미설정 시 로그만 출력하고 False 반환 (예외 발생 안 함).

    Returns:
        True = 이메일 발송 성공, False = SMTP 미설정 또는 발송 실패
    """
    try:
        # 심각도 확인
        if severity.lower() != "critical":
            logger.info(
                f"[알림 스킵] 심각도={severity} (critical만 이메일 발송) | "
                f"tenant={tenant_id} | event={event_type}"
            )
            return False

        # 관리자 이메일 조회
        admin_email = await _get_tenant_admin_email(tenant_id, db)
        if not admin_email:
            logger.warning(f"[알림] tenant_id={tenant_id} 관리자 이메일 없음")
            return False

        # SMTP 설정 확인
        smtp_user = os.environ.get("SMTP_USER", "").strip()
        smtp_pass = os.environ.get("SMTP_PASS", "").strip()

        if not smtp_user or not smtp_pass:
            logger.warning(
                f"[알림] SMTP 미설정 — 이메일 발송 생략\n"
                f"  수신자: {admin_email}\n"
                f"  이벤트: {event_type}\n"
                f"  설명: {description}\n"
                f"  PC: {endpoint_hostname}"
            )
            return False

        # 이메일 발송
        sent = await _send_email(
            to_email=admin_email,
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            event_type=event_type,
            description=description,
            endpoint_hostname=endpoint_hostname,
            tenant_id=tenant_id,
        )
        return sent

    except Exception as e:
        logger.error(f"[알림 오류] send_security_alert 예외: {e}", exc_info=True)
        return False


async def _get_tenant_admin_email(tenant_id: int, db: Session) -> Optional[str]:
    """테넌트의 admin 역할 사용자 이메일을 조회합니다."""
    try:
        from app.models.user import User, UserRole
        admin = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.role == UserRole.ADMIN,
            User.is_active == True,
        ).first()
        return admin.email if admin else None
    except Exception as e:
        logger.error(f"[알림] 관리자 이메일 조회 실패: {e}")
        return None


async def _send_email(
    to_email: str,
    smtp_user: str,
    smtp_pass: str,
    event_type: str,
    description: str,
    endpoint_hostname: str,
    tenant_id: int,
) -> bool:
    """aiosmtplib을 사용하여 실제 이메일을 발송합니다."""
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime

        event_labels = {
            "disk_antivirus_critical": "디스크 미암호화 + 백신 미설치",
            "critical_log": "위험 보안 로그",
            "usb_blocked": "USB 차단 이벤트",
            "login_fail": "로그인 실패",
            "agent_offline": "에이전트 오프라인",
        }
        event_label = event_labels.get(event_type, event_type)
        now_str = datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S")

        subject = f"[MediSafe 🔴 위험] {event_label} — {endpoint_hostname}"

        html_body = f"""
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="font-family: 'Malgun Gothic', sans-serif; background: #f4f6f8; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <div style="background: #c0392b; color: white; padding: 20px 24px;">
      <h2 style="margin: 0; font-size: 18px;">🔴 MediSafe 보안 위험 알림</h2>
      <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">{now_str}</p>
    </div>
    <div style="padding: 24px;">
      <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
        <tr style="background: #fef2f2;">
          <td style="padding: 10px 12px; font-weight: bold; width: 120px; border: 1px solid #e5e7eb;">심각도</td>
          <td style="padding: 10px 12px; border: 1px solid #e5e7eb; color: #c0392b; font-weight: bold;">🔴 위험 (CRITICAL)</td>
        </tr>
        <tr>
          <td style="padding: 10px 12px; font-weight: bold; border: 1px solid #e5e7eb;">이벤트 유형</td>
          <td style="padding: 10px 12px; border: 1px solid #e5e7eb;">{event_label}</td>
        </tr>
        <tr style="background: #f9fafb;">
          <td style="padding: 10px 12px; font-weight: bold; border: 1px solid #e5e7eb;">PC / 엔드포인트</td>
          <td style="padding: 10px 12px; border: 1px solid #e5e7eb;">{endpoint_hostname}</td>
        </tr>
        <tr>
          <td style="padding: 10px 12px; font-weight: bold; border: 1px solid #e5e7eb;">상세 내용</td>
          <td style="padding: 10px 12px; border: 1px solid #e5e7eb;">{description}</td>
        </tr>
      </table>
      <div style="margin-top: 20px; padding: 16px; background: #fff8e1; border-left: 4px solid #f0a500; border-radius: 4px;">
        <strong>⚠️ 권고 조치사항</strong>
        <ul style="margin: 8px 0; padding-left: 20px; font-size: 13px;">
          <li>즉시 해당 PC의 보안 상태를 확인하세요.</li>
          <li>MediSafe 대시보드에서 엔드포인트 상태를 점검하세요.</li>
          <li>필요 시 IT 담당자 또는 보안 전문가에게 연락하세요.</li>
        </ul>
      </div>
      <div style="margin-top: 20px; text-align: center;">
        <a href="https://jntubkwn.gensparkclaw.com" 
           style="background: #1a3a5c; color: white; padding: 10px 24px; text-decoration: none; border-radius: 6px; font-size: 14px;">
          MediSafe 대시보드 바로가기
        </a>
      </div>
    </div>
    <div style="padding: 16px 24px; background: #f4f6f8; font-size: 12px; color: #666; text-align: center;">
      MediSafe Clinic v2.0 | 이 메일은 자동 발송되었습니다.
    </div>
  </div>
</body>
</html>
"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"MediSafe 보안알림 <{smtp_user}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=smtp_user,
            password=smtp_pass,
            timeout=15,
        )

        logger.info(f"[알림] 이메일 발송 성공 → {to_email} (이벤트: {event_type})")
        return True

    except Exception as e:
        logger.error(f"[알림] 이메일 발송 실패: {e}")
        return False
