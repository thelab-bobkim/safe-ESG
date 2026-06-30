"""
MediSafe Clinic - PC 보안 에이전트 메인
사내 PC에서 실행하면 MediSafe 서버로 보안 정보를 자동 전송합니다.

실행방법:
  python agent.py           # 일반 실행 (5분마다 heartbeat)
  python agent.py --test    # 즉시 1회 테스트 후 종료
  python agent.py --setup   # 최초 등록만 수행
"""

import sys
import time
import argparse
import schedule
from datetime import datetime
from pathlib import Path

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    COLOR = True
except ImportError:
    COLOR = False

import config
import collector
from api_client import MediSafeClient

# 에이전트 상태 저장 파일
STATE_FILE = Path(__file__).parent / ".agent_state.json"

# ──────────────────────────────────────────────
# 출력 헬퍼
# ──────────────────────────────────────────────

def c(text: str, color: str = "") -> str:
    if not COLOR:
        return text
    colors = {
        "green": Fore.GREEN, "red": Fore.RED,
        "yellow": Fore.YELLOW, "cyan": Fore.CYAN,
        "blue": Fore.BLUE, "bold": Style.BRIGHT,
    }
    return f"{colors.get(color, '')}{text}{Style.RESET_ALL}"

def banner():
    print(c("""
╔═══════════════════════════════════════════════╗
║       MediSafe Clinic - PC 보안 에이전트       ║
║            병·의원 의료정보보호 솔루션           ║
╚═══════════════════════════════════════════════╝
""", "cyan"))

def log(msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"info": "ℹ", "ok": "✅", "warn": "⚠️ ", "error": "❌", "send": "📡"}
    colors = {"info": "blue", "ok": "green", "warn": "yellow", "error": "red", "send": "cyan"}
    icon = icons.get(level, "·")
    col = colors.get(level, "")
    print(c(f"[{ts}] {icon}  {msg}", col))

# ──────────────────────────────────────────────
# 상태 파일 관리
# ──────────────────────────────────────────────

def save_state(endpoint_id: int):
    import json
    STATE_FILE.write_text(json.dumps({"endpoint_id": endpoint_id}))

def load_state() -> int | None:
    import json
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text()).get("endpoint_id")
        except Exception:
            pass
    return None

# ──────────────────────────────────────────────
# 에이전트 초기화 (등록)
# ──────────────────────────────────────────────

def setup(client: MediSafeClient) -> int | None:
    """서버 연결 확인 → 로그인 → PC 등록"""
    log("서버 연결 확인 중...")
    if not client.health_check():
        log(f"서버에 연결할 수 없습니다: {config.SERVER_URL}", "error")
        log("인터넷 연결 또는 서버 주소를 확인하세요", "warn")
        return None
    log(f"서버 연결 OK: {config.SERVER_URL}", "ok")

    # 저장된 토큰 확인
    if client.load_token() and client.verify_token():
        log("저장된 인증 토큰 사용", "ok")
    else:
        log("원장 계정으로 로그인 중...")
        if not client.login(config.REGISTER_EMAIL, config.REGISTER_PASSWORD):
            log("로그인 실패. config.py의 이메일/비밀번호를 확인하세요.", "error")
            return None
        log(f"로그인 성공: {config.REGISTER_EMAIL}", "ok")

    # 기존 등록 확인
    endpoint_id = load_state()
    if endpoint_id:
        log(f"기존 등록된 PC: ID={endpoint_id}", "ok")
        return endpoint_id

    # 신규 등록
    log("이 PC를 MediSafe에 등록 중...")
    data = collector.collect_all()
    endpoint_id = client.register_endpoint(
        hostname=data["hostname"],
        ip=data["ip_address"],
        location=config.PC_LOCATION,
        os_info=data["os_info"],
    )
    if endpoint_id:
        save_state(endpoint_id)
        log(f"PC 등록 완료! endpoint_id={endpoint_id}", "ok")
        return endpoint_id

    log("PC 등록 실패", "error")
    return None

# ──────────────────────────────────────────────
# Heartbeat (주기적 보안 상태 전송)
# ──────────────────────────────────────────────

_prev_usb = set()

def do_heartbeat(client: MediSafeClient, endpoint_id: int):
    """보안 상태 수집 후 서버 전송"""
    log("보안 상태 수집 중...", "send")
    data = collector.collect_all()

    # Heartbeat 전송
    ok = client.send_heartbeat(endpoint_id, data)
    if not ok:
        # 토큰 만료 시 재로그인
        log("토큰 재발급 시도...", "warn")
        if client.login(config.REGISTER_EMAIL, config.REGISTER_PASSWORD):
            client.send_heartbeat(endpoint_id, data)

    # USB 변경 감지
    global _prev_usb
    current_usb = {d["name"] for d in data.get("usb_devices", [])}
    new_devices  = current_usb - _prev_usb
    removed      = _prev_usb  - current_usb

    for dev in new_devices:
        log(f"USB 연결 감지: {dev}", "warn")
        client.send_usb_event(endpoint_id, dev, "connected")

    for dev in removed:
        log(f"USB 제거 감지: {dev}", "info")
        client.send_usb_event(endpoint_id, dev, "disconnected")

    _prev_usb = current_usb

    # 보안 이슈 요약 출력
    issues = []
    if data["disk_encrypted"] is False:   issues.append("⚠️  디스크 암호화 미설정")
    if data["antivirus_installed"] is False: issues.append("⚠️  백신 미설치")
    if data["os_patched"] is False:       issues.append("⚠️  OS 업데이트 필요")
    if data["firewall_enabled"] is False: issues.append("⚠️  방화벽 비활성")
    if data["screen_lock_enabled"] is False: issues.append("⚠️  화면잠금 미설정")

    if issues:
        for issue in issues:
            log(issue, "warn")
    else:
        log("모든 보안 항목 정상", "ok")

# ──────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────

def main():
    banner()

    parser = argparse.ArgumentParser(description="MediSafe 에이전트")
    parser.add_argument("--test",  action="store_true", help="1회 테스트 후 종료")
    parser.add_argument("--setup", action="store_true", help="최초 등록만 수행")
    args = parser.parse_args()

    client = MediSafeClient(config.SERVER_URL)

    # ── 초기화 ──
    log("에이전트 초기화 중...")
    endpoint_id = setup(client)
    if not endpoint_id:
        log("초기화 실패. 프로그램을 종료합니다.", "error")
        sys.exit(1)

    if args.setup:
        log("등록 완료. --setup 모드 종료.", "ok")
        return

    # ── 1회 즉시 실행 ──
    log(f"첫 번째 Heartbeat 전송...")
    do_heartbeat(client, endpoint_id)

    if args.test:
        log("테스트 완료!", "ok")
        log(f"👉 결과 확인: {config.SERVER_URL}", "info")
        return

    # ── 스케줄 설정 ──
    interval = config.HEARTBEAT_INTERVAL_MIN
    schedule.every(interval).minutes.do(do_heartbeat, client, endpoint_id)
    log(f"스케줄 설정 완료: {interval}분마다 보안 상태 전송", "ok")
    log(f"종료하려면 Ctrl+C를 누르세요", "info")
    print()

    # ── 실행 루프 ──
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n")
        log("에이전트 종료됨", "info")
