@echo off
chcp 65001 > nul
title MediSafe Clinic - DSTI 자동 설치
color 0B

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║      MediSafe Clinic - PC 보안 에이전트              ║
echo  ║      DSTI 사무실 POC 전용 v1.0                       ║
echo  ║      이 파일 하나로 자동 설치됩니다                   ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

REM ═══════════════════════════════════════════════
REM  설치 폴더 고정: C:\MediSafe
REM ═══════════════════════════════════════════════
set INSTALL_DIR=C:\MediSafe
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"

REM ═══════════════════════════════════════════════
REM  1단계: Python 확인 및 자동 설치
REM ═══════════════════════════════════════════════
echo  [1/4] Python 확인 중...
python --version > nul 2>&1
if %errorLevel% neq 0 (
    echo  [!] Python이 없습니다. winget으로 자동 설치합니다...
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if %errorLevel% neq 0 (
        echo.
        echo  ┌─────────────────────────────────────────────┐
        echo  │ winget 설치 실패. 수동 설치가 필요합니다.   │
        echo  │                                             │
        echo  │ 1. 아래 주소에서 Python 설치:               │
        echo  │    https://www.python.org/downloads/        │
        echo  │                                             │
        echo  │ 2. 설치 시 반드시 체크:                     │
        echo  │    [√] Add Python to PATH                   │
        echo  │                                             │
        echo  │ 3. 설치 완료 후 이 파일 다시 실행           │
        echo  └─────────────────────────────────────────────┘
        pause
        exit /b 1
    )
    REM PATH 갱신을 위해 새 cmd 세션에서 재실행
    echo  [OK] Python 설치 완료. 재시작합니다...
    start "" "%~f0"
    exit /b 0
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo  [OK] Python %%v 확인

REM ═══════════════════════════════════════════════
REM  2단계: 필요 라이브러리 설치
REM ═══════════════════════════════════════════════
echo  [2/4] 라이브러리 설치 중...
python -m pip install -q --upgrade pip
python -m pip install -q requests psutil schedule colorama
echo  [OK] 라이브러리 준비 완료

REM ═══════════════════════════════════════════════
REM  3단계: 에이전트 파일 전체 자동 생성
REM         (config.py + agent.py + api_client.py + collector.py)
REM         모든 내용이 이 배치 파일 안에 내장되어 있음
REM ═══════════════════════════════════════════════
echo  [3/4] 에이전트 파일 생성 중...

REM ── PC 이름 자동 감지 ──────────────────────────
for /f "tokens=*" %%c in ('hostname') do set THIS_PC=%%c
echo  [OK] 이 PC 이름: %THIS_PC%

REM ── config.py 자동 생성 (수정 불필요) ──────────
python -c "
content = '''# MediSafe Clinic - DSTI 자동 설정 (수정하지 마세요)
SERVER_URL = \"https://jntubkwn.gensparkclaw.com\"
REGISTER_EMAIL    = \"htkim@dsti.co.kr\"
REGISTER_PASSWORD = \"Dsti@Admin1!\"
PC_LOCATION       = \"DSTI 사무실\"
HEARTBEAT_INTERVAL_MIN = 5
'''
with open('config.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('  [OK] config.py 생성')
"

REM ── collector.py 생성 (보안 정보 수집) ──────────
python -c "
import os, sys, textwrap
code = r'''
import os, sys, socket, platform, subprocess, psutil
from datetime import datetime

def get_hostname():
    return socket.gethostname()

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((\"8.8.8.8\", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return \"127.0.0.1\"

def get_os_info():
    return {\"system\": platform.system(), \"release\": platform.release(), \"version\": platform.version(), \"machine\": platform.machine()}

def check_disk_encryption():
    try:
        if platform.system() == \"Windows\":
            r = subprocess.run([\"manage-bde\",\"-status\",\"C:\"], capture_output=True, text=True, timeout=10)
            return \"Protection On\" in r.stdout or \"보호 설정\" in r.stdout
    except:
        pass
    return None

def check_antivirus():
    try:
        if platform.system() == \"Windows\":
            r = subprocess.run([\"powershell\",\"-Command\",\"Get-MpComputerStatus | Select-Object -ExpandProperty AntivirusEnabled\"], capture_output=True, text=True, timeout=15)
            return \"True\" in r.stdout
    except:
        pass
    return None

def check_os_patched():
    try:
        if platform.system() == \"Windows\":
            r = subprocess.run([\"powershell\",\"-Command\",\"(Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn\"], capture_output=True, text=True, timeout=20)
            return bool(r.stdout.strip())
    except:
        pass
    return None

def check_firewall():
    try:
        if platform.system() == \"Windows\":
            r = subprocess.run([\"netsh\",\"advfirewall\",\"show\",\"allprofiles\",\"state\"], capture_output=True, text=True, timeout=10)
            return \"ON\" in r.stdout.upper()
    except:
        pass
    return None

def check_screen_lock():
    try:
        if platform.system() == \"Windows\":
            r = subprocess.run([\"powershell\",\"-Command\",\"(Get-ItemProperty 'HKCU:\\\\Control Panel\\\\Desktop').ScreenSaveTimeOut\"], capture_output=True, text=True, timeout=10)
            t = r.stdout.strip()
            return t.isdigit() and 0 < int(t) <= 900
    except:
        pass
    return None

def check_usb_devices():
    devices = []
    try:
        if platform.system() == \"Windows\":
            r = subprocess.run([\"powershell\",\"-Command\",\"Get-PnpDevice -Class USB | Where-Object Status -eq 'OK' | Select-Object FriendlyName,DeviceID | ConvertTo-Json\"], capture_output=True, text=True, timeout=15)
            if r.stdout.strip():
                import json
                raw = json.loads(r.stdout)
                if isinstance(raw, dict): raw = [raw]
                for d in (raw or []):
                    devices.append({\"name\": d.get(\"FriendlyName\",\"Unknown\"), \"device_id\": d.get(\"DeviceID\",\"\")})
    except:
        pass
    return devices

def collect_all():
    print(\"  수집 중...\")
    data = {
        \"hostname\": get_hostname(),
        \"ip_address\": get_ip_address(),
        \"os_info\": get_os_info(),
        \"disk_encrypted\": check_disk_encryption(),
        \"antivirus_installed\": check_antivirus(),
        \"os_patched\": check_os_patched(),
        \"firewall_enabled\": check_firewall(),
        \"screen_lock_enabled\": check_screen_lock(),
        \"usb_devices\": check_usb_devices(),
        \"system_metrics\": {\"cpu_usage\": psutil.cpu_percent(interval=1), \"memory\": {\"used_percent\": psutil.virtual_memory().percent}, \"disk\": {\"used_percent\": psutil.disk_usage(\"/\").percent}},
        \"collected_at\": datetime.now().isoformat(),
    }
    print(f\"  완료: {data['hostname']} ({data['ip_address']})\")
    return data
'''.strip()
with open('collector.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('  [OK] collector.py 생성')
"

REM ── api_client.py 생성 (서버 통신) ──────────────
python -c "
code = r'''
import json, socket, requests
from pathlib import Path

TOKEN_FILE = Path(__file__).parent / \".agent_token\"

class MediSafeClient:
    def __init__(self, server_url):
        self.server_url = server_url.rstrip(\"/\")
        self.session = requests.Session()
        self.session.headers.update({\"Content-Type\": \"application/json\", \"User-Agent\": \"MediSafe-Agent/1.0\"})
        self._token = None

    def login(self, email, password):
        try:
            res = self.session.post(f\"{self.server_url}/api/v1/auth/login\", json={\"email\": email, \"password\": password}, timeout=10)
            if res.status_code == 200:
                self._token = res.json()[\"access_token\"]
                self.session.headers[\"Authorization\"] = f\"Bearer {self._token}\"
                TOKEN_FILE.write_text(self._token)
                return True
            print(f\"  로그인 실패: {res.status_code} {res.text[:100]}\")
        except Exception as e:
            print(f\"  서버 연결 실패: {e}\")
        return False

    def load_token(self):
        if TOKEN_FILE.exists():
            self._token = TOKEN_FILE.read_text().strip()
            self.session.headers[\"Authorization\"] = f\"Bearer {self._token}\"
            return bool(self._token)
        return False

    def verify_token(self):
        try:
            return self.session.get(f\"{self.server_url}/api/v1/auth/me\", timeout=5).status_code == 200
        except:
            return False

    def register_endpoint(self, hostname, ip, location, os_info):
        try:
            res = self.session.post(f\"{self.server_url}/api/v1/endpoints/\", json={\"hostname\": hostname, \"ip_address\": ip, \"location\": location, \"os_type\": os_info.get(\"system\",\"Unknown\").lower(), \"os_version\": os_info.get(\"release\",\"\"), \"device_type\": \"desktop\"}, timeout=10)
            if res.status_code in (200, 201):
                ep = res.json()
                print(f\"  PC 등록 완료: ID={ep['id']}\")
                return ep[\"id\"]
            return self._find_existing(hostname)
        except Exception as e:
            print(f\"  등록 오류: {e}\")
        return None

    def _find_existing(self, hostname):
        try:
            res = self.session.get(f\"{self.server_url}/api/v1/endpoints/\", timeout=10)
            if res.status_code == 200:
                for ep in res.json():
                    if ep[\"hostname\"] == hostname:
                        print(f\"  기존 PC 확인: ID={ep['id']}\")
                        return ep[\"id\"]
        except:
            pass
        return None

    def send_heartbeat(self, endpoint_id, data):
        try:
            payload = {\"disk_encrypted\": data.get(\"disk_encrypted\"), \"antivirus_installed\": data.get(\"antivirus_installed\"), \"os_patched\": data.get(\"os_patched\"), \"firewall_enabled\": data.get(\"firewall_enabled\"), \"screen_lock_enabled\": data.get(\"screen_lock_enabled\"), \"ip_address\": data.get(\"ip_address\"), \"os_version\": data[\"os_info\"].get(\"release\",\"\") if data.get(\"os_info\") else None, \"extra_data\": {\"metrics\": data.get(\"system_metrics\",{})}}
            res = self.session.patch(f\"{self.server_url}/api/v1/endpoints/{endpoint_id}/heartbeat\", json=payload, timeout=10)
            if res.status_code == 200:
                r = res.json()
                print(f\"  전송 완료 - 보안점수: {r.get('security_score','?')}점 ({r.get('grade','?')}등급)\")
                return True
            print(f\"  Heartbeat 실패: {res.status_code}\")
        except Exception as e:
            print(f\"  Heartbeat 오류: {e}\")
        return False

    def send_usb_event(self, endpoint_id, device_name, action=\"connected\"):
        try:
            self.session.post(f\"{self.server_url}/api/v1/endpoints/{endpoint_id}/usb-events\", json={\"endpoint_id\": endpoint_id, \"device_name\": device_name, \"action\": action, \"blocked\": False}, timeout=10)
        except:
            pass

    def health_check(self):
        try:
            return self.session.get(f\"{self.server_url}/health\", timeout=5).status_code == 200
        except:
            return False
'''.strip()
with open('api_client.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('  [OK] api_client.py 생성')
"

REM ── agent.py 생성 (메인 실행) ────────────────────
python -c "
code = r'''
import sys, time, json, schedule
from datetime import datetime
from pathlib import Path

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    def c(t, col=\"\"): cols={\"green\":Fore.GREEN,\"red\":Fore.RED,\"yellow\":Fore.YELLOW,\"cyan\":Fore.CYAN}; return f\"{cols.get(col,'')}{t}{Style.RESET_ALL}\"
except:
    def c(t, col=\"\"): return t

STATE_FILE = Path(__file__).parent / \".agent_state.json\"

def log(msg, level=\"info\"):
    ts = datetime.now().strftime(\"%H:%M:%S\")
    icons = {\"info\":\"i\",\"ok\":\"OK\",\"warn\":\"!!\",\"error\":\"XX\",\"send\":\">>\"};  cols = {\"info\":\"cyan\",\"ok\":\"green\",\"warn\":\"yellow\",\"error\":\"red\",\"send\":\"cyan\"}
    print(c(f\"[{ts}] [{icons.get(level,'i')}] {msg}\", cols.get(level,\"\")))

def save_state(eid): STATE_FILE.write_text(json.dumps({\"endpoint_id\": eid}))
def load_state():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text()).get(\"endpoint_id\")
        except: pass
    return None

def setup(client):
    import config
    log(\"서버 연결 확인 중...\")
    if not client.health_check():
        log(f\"서버 연결 실패: {config.SERVER_URL}\", \"error\"); return None
    log(f\"서버 연결 OK\", \"ok\")
    if client.load_token() and client.verify_token():
        log(\"저장된 인증 토큰 사용\", \"ok\")
    else:
        log(\"로그인 중...\")
        if not client.login(config.REGISTER_EMAIL, config.REGISTER_PASSWORD):
            log(\"로그인 실패\", \"error\"); return None
        log(f\"로그인 성공: {config.REGISTER_EMAIL}\", \"ok\")
    eid = load_state()
    if eid:
        log(f\"기존 등록 PC: ID={eid}\", \"ok\"); return eid
    log(\"이 PC를 MediSafe에 등록 중...\")
    import collector
    data = collector.collect_all()
    eid = client.register_endpoint(data[\"hostname\"], data[\"ip_address\"], config.PC_LOCATION, data[\"os_info\"])
    if eid:
        save_state(eid); log(f\"등록 완료! ID={eid}\", \"ok\"); return eid
    log(\"등록 실패\", \"error\"); return None

_prev_usb = set()

def do_heartbeat(client, eid):
    import config, collector
    log(\"보안 상태 수집 중...\", \"send\")
    data = collector.collect_all()
    if not client.send_heartbeat(eid, data):
        if client.login(config.REGISTER_EMAIL, config.REGISTER_PASSWORD):
            client.send_heartbeat(eid, data)
    global _prev_usb
    cur = {d[\"name\"] for d in data.get(\"usb_devices\",[])}
    for dev in cur - _prev_usb: log(f\"USB 연결: {dev}\", \"warn\"); client.send_usb_event(eid, dev, \"connected\")
    for dev in _prev_usb - cur: client.send_usb_event(eid, dev, \"disconnected\")
    _prev_usb = cur
    issues = []
    if data[\"disk_encrypted\"] is False: issues.append(\"디스크 암호화 미설정\")
    if data[\"antivirus_installed\"] is False: issues.append(\"백신 미설치\")
    if data[\"os_patched\"] is False: issues.append(\"OS 업데이트 필요\")
    if data[\"firewall_enabled\"] is False: issues.append(\"방화벽 비활성\")
    if data[\"screen_lock_enabled\"] is False: issues.append(\"화면잠금 미설정\")
    if issues:
        for i in issues: log(f\"보안 이슈: {i}\", \"warn\")
    else:
        log(\"모든 보안 항목 정상\", \"ok\")

def main():
    import config
    from api_client import MediSafeClient
    print()
    print(c(\" MediSafe Clinic - PC 보안 에이전트 v1.0\", \"cyan\"))
    print(c(\" DSTI 사무실 POC\", \"cyan\"))
    print()
    client = MediSafeClient(config.SERVER_URL)
    eid = setup(client)
    if not eid:
        log(\"초기화 실패. 창을 닫고 다시 시도하세요.\", \"error\"); input(\"종료하려면 Enter...\"); sys.exit(1)
    log(\"첫 번째 보안 상태 전송...\")
    do_heartbeat(client, eid)
    if \"--test\" in sys.argv:
        print(); log(f\"테스트 완료! 대시보드 확인: {config.SERVER_URL}\", \"ok\"); return
    schedule.every(config.HEARTBEAT_INTERVAL_MIN).minutes.do(do_heartbeat, client, eid)
    log(f\"{config.HEARTBEAT_INTERVAL_MIN}분마다 자동 전송 시작 (종료: Ctrl+C 또는 창 닫기)\", \"ok\")
    print()
    while True:
        schedule.run_pending(); time.sleep(10)

if __name__ == \"__main__\":
    try:
        main()
    except KeyboardInterrupt:
        print(); log(\"에이전트 종료\", \"info\")
'''.strip()
with open('agent.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('  [OK] agent.py 생성')
"

echo  [OK] 모든 파일 생성 완료

REM ═══════════════════════════════════════════════
REM  4단계: 서버 연결 테스트 및 실행
REM ═══════════════════════════════════════════════
echo  [4/4] 서버 연결 테스트 중...
echo.

python "%INSTALL_DIR%\agent.py" --test

if %errorLevel% neq 0 (
    echo.
    echo  ┌─────────────────────────────────────────────────┐
    echo  │ 오류: 서버 연결에 실패했습니다.                  │
    echo  │                                                  │
    echo  │ 확인사항:                                        │
    echo  │  - 인터넷 연결 상태                              │
    echo  │  - 방화벽에서 443 포트 허용 여부                 │
    echo  └─────────────────────────────────────────────────┘
    pause
    exit /b 1
)

echo.
echo  ══════════════════════════════════════════════════════
echo   [완료] 설치 및 테스트 성공!
echo.
echo   대시보드 주소:
echo   https://jntubkwn.gensparkclaw.com
echo.
echo   로그인:  htkim@dsti.co.kr / Dsti@Admin1!
echo  ══════════════════════════════════════════════════════
echo.
echo  5분마다 이 PC의 보안 상태를 자동으로 전송합니다.
echo  이 창을 닫으면 중지됩니다.
echo  PC 시작 시 자동 실행하려면 아래 파일을 시작 프로그램에 추가하세요:
echo  %INSTALL_DIR%\agent.py
echo.

REM ── 시작 프로그램 등록 (선택) ─────────────────
choice /c YN /m "PC 시작 시 자동 실행으로 등록하시겠습니까? [Y/N]"
if %errorLevel%==1 (
    set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
    echo @echo off > "%STARTUP%\MediSafe_Agent.bat"
    echo cd /d "%INSTALL_DIR%" >> "%STARTUP%\MediSafe_Agent.bat"
    echo python agent.py >> "%STARTUP%\MediSafe_Agent.bat"
    echo  [OK] 시작 프로그램에 등록되었습니다.
)

echo.
echo  에이전트를 계속 실행합니다...
python "%INSTALL_DIR%\agent.py"
pause
