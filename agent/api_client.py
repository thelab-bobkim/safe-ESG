"""
MediSafe Agent - API Client v2
병원 등록코드 기반 자동 인증 (비밀번호 불필요)
"""
import json, requests
from pathlib import Path

TOKEN_FILE = Path(__file__).parent / ".agent_token"
STATE_FILE = Path(__file__).parent / ".agent_state.json"

class MediSafeClient:
    def __init__(self, server_url):
        self.server_url = server_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "MediSafe-Agent/2.0 (Windows)"
        })
        self._agent_token = None

    def health_check(self):
        try:
            return self.session.get(f"{self.server_url}/health", timeout=5).status_code == 200
        except:
            return False

    def load_state(self):
        """저장된 등록 상태 로드 (endpoint_id + agent_token)"""
        if STATE_FILE.exists():
            try:
                d = json.loads(STATE_FILE.read_text())
                self._agent_token = d.get("agent_token")
                return d.get("endpoint_id"), d.get("agent_token")
            except:
                pass
        return None, None

    def save_state(self, endpoint_id, agent_token):
        STATE_FILE.write_text(json.dumps({
            "endpoint_id": endpoint_id,
            "agent_token": agent_token,
        }))
        self._agent_token = agent_token

    def enroll(self, enroll_code, hostname, ip, os_type, os_version, location):
        """병원 등록코드로 PC 자동 등록 + 에이전트 토큰 발급"""
        try:
            res = self.session.post(
                f"{self.server_url}/api/v1/endpoints/agent/enroll",
                json={
                    "enroll_code": enroll_code,
                    "hostname":    hostname,
                    "ip_address":  ip,
                    "os_type":     os_type.lower(),
                    "os_version":  os_version,
                    "location":    location,
                },
                timeout=15
            )
            if res.status_code in (200, 201):
                data = res.json()
                endpoint_id = data["endpoint_id"]
                agent_token = data["agent_token"]
                self.save_state(endpoint_id, agent_token)
                print(f"  등록 완료: ID={endpoint_id} | 병원={data.get('tenant_name','')} | {data.get('message','')}")
                return endpoint_id, agent_token
            print(f"  등록 실패: {res.status_code} - {res.json().get('detail','')}")
        except Exception as e:
            print(f"  등록 오류: {e}")
        return None, None

    def send_heartbeat(self, endpoint_id, agent_token, data, pc_name=None, location=None):
        """에이전트 토큰 기반 heartbeat 전송"""
        try:
            payload = {
                "agent_token":         agent_token,
                "status":              "online",
                "disk_encrypted":      data.get("disk_encrypted"),
                "antivirus_installed": data.get("antivirus_installed"),
                "antivirus_updated":   data.get("antivirus_updated"),
                "os_patched":          data.get("os_patched"),
                "firewall_enabled":    data.get("firewall_enabled"),
                "screen_lock_enabled": data.get("screen_lock_enabled"),
                "ip_address":          data.get("ip_address"),
                "os_version":          data.get("os_info", {}).get("release", ""),
                "agent_version":       "2.0",
                "pc_name":             pc_name or None,
                "location":            location or None,
            }
            res = self.session.post(
                f"{self.server_url}/api/v1/endpoints/agent/heartbeat",
                json=payload, timeout=10
            )
            if res.status_code == 200:
                r = res.json()
                print(f"  전송 완료 - 보안점수: {r.get('score','?')}점")
                return True
            print(f"  Heartbeat 실패: {res.status_code}")
        except Exception as e:
            print(f"  Heartbeat 오류: {e}")
        return False

    def send_usb_event(self, agent_token, device_name, action="connected"):
        try:
            self.session.post(
                f"{self.server_url}/api/v1/endpoints/agent/usb-event",
                json={
                    "agent_token": agent_token,
                    "event_type":  action,
                    "device_name": device_name,
                    "blocked":     False,
                },
                timeout=10
            )
        except:
            pass
