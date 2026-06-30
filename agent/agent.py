"""
MediSafe Clinic - PC 보안 에이전트 v2.0
병원 등록코드 기반 자동 등록 (비밀번호 불필요)
"""
import sys, time, json, schedule
from datetime import datetime
from pathlib import Path

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    G = Fore.GREEN; R = Fore.RED; Y = Fore.YELLOW; C = Fore.CYAN; RST = Style.RESET_ALL
except:
    G = R = Y = C = RST = ""

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    col = {"ok":G,"warn":Y,"error":R,"send":C}.get(level,"")
    icon = {"ok":"OK","warn":"!!","error":"XX","send":">>","info":"  "}.get(level,"  ")
    print(f"{col}[{ts}][{icon}] {msg}{RST}")

def setup(client):
    import sys
    config = sys.modules.get("config") or load_config()
    import collector

    log("서버 연결 확인 중...")
    if not client.health_check():
        log(f"서버 연결 실패: {config.SERVER_URL}", "error")
        return None, None
    log("서버 연결 OK", "ok")

    # 구버전 상태파일 확인 — agent_token 없으면 재등록
    endpoint_id, agent_token = client.load_state()
    if endpoint_id and agent_token:
        log(f"기존 등록 PC 사용: ID={endpoint_id}", "ok")
        return endpoint_id, agent_token

    # 구버전 .agent_state.json (endpoint_id만 있고 token 없는 경우) 삭제
    STATE_FILE = Path(__file__).parent / ".agent_state.json"
    if STATE_FILE.exists():
        try:
            d = json.loads(STATE_FILE.read_text())
            if d.get("endpoint_id") and not d.get("agent_token"):
                STATE_FILE.unlink()
                log("구버전 상태파일 삭제 → 재등록", "warn")
        except:
            STATE_FILE.unlink()

    # 등록코드로 자동 등록
    log(f"이 PC를 MediSafe에 자동 등록 중... (코드: {config.ENROLL_CODE})")
    data = collector.collect_all()
    # PC_NAME이 있으면 사용, 없으면 시스템 hostname 사용
    pc_name = getattr(config, 'PC_NAME', '').strip() or data["hostname"]
    endpoint_id, agent_token = client.enroll(
        enroll_code = config.ENROLL_CODE,
        hostname    = pc_name,
        ip          = data["ip_address"],
        os_type     = data["os_info"].get("system", "windows"),
        os_version  = data["os_info"].get("release", ""),
        location    = config.PC_LOCATION or "",
    )
    if endpoint_id:
        log(f"자동 등록 완료! ID={endpoint_id}", "ok")
        return endpoint_id, agent_token

    log("등록 실패 — 등록 코드를 확인하세요.", "error")
    return None, None

_prev_usb = set()

def do_heartbeat(client, endpoint_id, agent_token):
    import sys
    config = sys.modules.get("config") or load_config()
    import collector
    log("보안 상태 수집 중...", "send")
    data = collector.collect_all()

    pc_name  = getattr(config, 'PC_NAME', '').strip() or None
    location = getattr(config, 'PC_LOCATION', '').strip() or None
    client.send_heartbeat(endpoint_id, agent_token, data, pc_name=pc_name, location=location)

    # USB 변화 감지
    global _prev_usb
    cur = {d["name"] for d in data.get("usb_devices", [])}
    for dev in cur - _prev_usb:
        log(f"USB 연결: {dev}", "warn")
        client.send_usb_event(agent_token, dev, "connected")
    for dev in _prev_usb - cur:
        client.send_usb_event(agent_token, dev, "disconnected")
    _prev_usb = cur

    # 보안 이슈 출력
    issues = []
    if data.get("disk_encrypted") is False:      issues.append("디스크 암호화 미설정")
    if data.get("antivirus_installed") is False:  issues.append("백신 미설치")
    if data.get("os_patched") is False:           issues.append("OS 업데이트 필요")
    if data.get("firewall_enabled") is False:     issues.append("방화벽 비활성")
    if data.get("screen_lock_enabled") is False:  issues.append("화면잠금 미설정")

    if issues:
        for i in issues: log(f"보안 이슈: {i}", "warn")
    else:
        log("모든 보안 항목 정상", "ok")

def load_config():
    """config.py를 인코딩 자동 감지로 로드 (UTF-8 BOM, CP949, UTF-8 모두 처리)"""
    import importlib, sys
    config_path = Path(__file__).parent / "config.py"
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            src = config_path.read_text(encoding=enc)
            spec = importlib.util.spec_from_loader("config", loader=None)
            mod  = type(sys)("config")
            exec(compile(src, str(config_path), "exec"), mod.__dict__)
            sys.modules["config"] = mod
            return mod
        except Exception:
            continue
    raise RuntimeError("config.py 읽기 실패 — 파일 인코딩을 확인하세요")

def main():
    import importlib.util
    config = load_config()
    from api_client import MediSafeClient

    print()
    pc_label = getattr(config, 'PC_NAME', '').strip() or "(자동감지)"
    print(f"{C}  MediSafe Clinic - PC 보안 에이전트 v2.0{RST}")
    print(f"{C}  PC명: {pc_label}  |  등록코드: {config.ENROLL_CODE}{RST}")
    print(f"{C}  서버: {config.SERVER_URL}{RST}")
    print()

    client = MediSafeClient(config.SERVER_URL)
    endpoint_id, agent_token = setup(client)
    if not endpoint_id:
        log("초기화 실패. 등록 코드를 확인하고 다시 시도하세요.", "error")
        input("\n종료하려면 Enter...")
        sys.exit(1)

    do_heartbeat(client, endpoint_id, agent_token)

    if "--test" in sys.argv:
        log(f"테스트 완료! 대시보드: {config.SERVER_URL}", "ok")
        return

    schedule.every(config.HEARTBEAT_INTERVAL_MIN).minutes.do(
        do_heartbeat, client, endpoint_id, agent_token
    )
    log(f"{config.HEARTBEAT_INTERVAL_MIN}분마다 자동 전송 시작", "ok")
    print()

    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        log("에이전트 종료")
