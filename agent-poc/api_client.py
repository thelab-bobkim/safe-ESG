"""
MediSafe Clinic - 서버 통신 클라이언트
수집한 데이터를 MediSafe 서버로 전송합니다.
"""

import json
import socket
import requests
from pathlib import Path

TOKEN_FILE = Path(__file__).parent / ".agent_token"

class MediSafeClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "MediSafe-Agent/0.1",
        })
        self._token: str | None = None
        self._endpoint_id: int | None = None

    # ──────────────────────────────────────────
    # 인증 토큰 관리
    # ──────────────────────────────────────────

    def login(self, email: str, password: str) -> bool:
        """원장 계정으로 로그인하여 JWT 토큰 획득"""
        try:
            res = self.session.post(
                f"{self.server_url}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            if res.status_code == 200:
                self._token = res.json()["access_token"]
                self.session.headers["Authorization"] = f"Bearer {self._token}"
                # 토큰 저장
                TOKEN_FILE.write_text(self._token)
                return True
            print(f"  ❌ 로그인 실패: {res.status_code} {res.text[:100]}")
        except Exception as e:
            print(f"  ❌ 서버 연결 실패: {e}")
        return False

    def load_token(self) -> bool:
        """저장된 토큰 로드"""
        if TOKEN_FILE.exists():
            self._token = TOKEN_FILE.read_text().strip()
            self.session.headers["Authorization"] = f"Bearer {self._token}"
            return bool(self._token)
        return False

    def verify_token(self) -> bool:
        """토큰 유효성 확인"""
        try:
            res = self.session.get(
                f"{self.server_url}/api/v1/auth/me",
                timeout=5,
            )
            return res.status_code == 200
        except Exception:
            return False

    # ──────────────────────────────────────────
    # 엔드포인트 등록
    # ──────────────────────────────────────────

    def register_endpoint(self, hostname: str, ip: str, location: str, os_info: dict) -> int | None:
        """이 PC를 서버에 등록하고 endpoint_id 반환"""
        try:
            res = self.session.post(
                f"{self.server_url}/api/v1/endpoints/",
                json={
                    "hostname": hostname,
                    "ip_address": ip,
                    "location": location,
                    "os_type": os_info.get("system", "Unknown").lower(),
                    "os_version": f"{os_info.get('release', '')} {os_info.get('version', '')}".strip(),
                    "device_type": "desktop",
                },
                timeout=10,
            )
            if res.status_code in (200, 201):
                ep = res.json()
                print(f"  ✅ PC 등록 완료: ID={ep['id']} ({hostname})")
                return ep["id"]
            elif res.status_code == 422:
                # 이미 등록된 경우 - 기존 ID 조회
                return self._find_existing_endpoint(hostname)
            print(f"  ❌ 등록 실패: {res.status_code} {res.text[:200]}")
        except Exception as e:
            print(f"  ❌ 등록 오류: {e}")
        return None

    def _find_existing_endpoint(self, hostname: str) -> int | None:
        """기존 등록된 엔드포인트 ID 찾기"""
        try:
            res = self.session.get(f"{self.server_url}/api/v1/endpoints/", timeout=10)
            if res.status_code == 200:
                for ep in res.json():
                    if ep["hostname"] == hostname:
                        print(f"  ℹ️  기존 PC 확인: ID={ep['id']} ({hostname})")
                        return ep["id"]
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────
    # 데이터 전송
    # ──────────────────────────────────────────

    def send_heartbeat(self, endpoint_id: int, security_data: dict) -> bool:
        """보안 상태 heartbeat 전송"""
        try:
            payload = {
                "disk_encrypted": security_data.get("disk_encrypted"),
                "antivirus_installed": security_data.get("antivirus_installed"),
                "os_patched": security_data.get("os_patched"),
                "firewall_enabled": security_data.get("firewall_enabled"),
                "screen_lock_enabled": security_data.get("screen_lock_enabled"),
                "ip_address": security_data.get("ip_address"),
                "os_version": (
                    f"{security_data['os_info']['release']} {security_data['os_info']['version']}"
                    if security_data.get("os_info") else None
                ),
                "extra_data": {
                    "metrics": security_data.get("system_metrics", {}),
                    "usb_count": len(security_data.get("usb_devices", [])),
                },
            }
            res = self.session.patch(
                f"{self.server_url}/api/v1/endpoints/{endpoint_id}/heartbeat",
                json=payload,
                timeout=10,
            )
            if res.status_code == 200:
                score = res.json().get("security_score", "?")
                print(f"  ✅ Heartbeat 전송 완료 (보안점수: {score}점)")
                return True
            print(f"  ❌ Heartbeat 실패: {res.status_code} {res.text[:100]}")
        except Exception as e:
            print(f"  ❌ Heartbeat 오류: {e}")
        return False

    def send_usb_event(self, endpoint_id: int, device_name: str, action: str = "connected") -> bool:
        """USB 연결/해제 이벤트 전송"""
        try:
            res = self.session.post(
                f"{self.server_url}/api/v1/endpoints/{endpoint_id}/usb-events",
                json={
                    "endpoint_id": endpoint_id,
                    "device_name": device_name,
                    "action": action,
                    "blocked": False,
                },
                timeout=10,
            )
            ok = res.status_code in (200, 201)
            if ok:
                print(f"  ⚡ USB 이벤트 전송: {device_name} ({action})")
            return ok
        except Exception as e:
            print(f"  ❌ USB 이벤트 오류: {e}")
        return False

    def send_log(self, event_type: str, description: str,
                 severity: str = "info", result: str = "success",
                 resource: str | None = None) -> bool:
        """접속 로그 전송"""
        try:
            res = self.session.post(
                f"{self.server_url}/api/v1/logs/",
                json={
                    "event_type": event_type,
                    "severity": severity,
                    "result": result,
                    "description": description,
                    "resource": resource,
                    "ip_address": socket.gethostbyname(socket.gethostname()),
                },
                timeout=10,
            )
            return res.status_code in (200, 201)
        except Exception:
            return False

    def health_check(self) -> bool:
        """서버 헬스체크"""
        try:
            res = self.session.get(f"{self.server_url}/health", timeout=5)
            return res.status_code == 200
        except Exception:
            return False
