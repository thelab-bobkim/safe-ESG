@echo off
chcp 65001 > nul
title MediSafe Clinic - PC 보안 에이전트 (DSTI POC)
color 0B

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║      MediSafe Clinic - PC 보안 에이전트              ║
echo  ║      DSTI 사무실 POC 전용 v1.0                       ║
echo  ║      서버: https://jntubkwn.gensparkclaw.com         ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

REM ── Python 확인 및 자동 설치 안내 ──────────────────────────
python --version > nul 2>&1
if %errorLevel% neq 0 (
    echo  [!] Python이 설치되어 있지 않습니다.
    echo.
    echo  Python 설치 방법:
    echo  1. https://www.python.org/downloads/ 접속
    echo  2. "Download Python 3.12.x" 클릭
    echo  3. 설치 시 [Add Python to PATH] 반드시 체크!
    echo  4. 설치 완료 후 이 파일을 다시 실행하세요.
    echo.
    echo  또는 아래 명령어로 winget 자동 설치:
    echo  winget install Python.Python.3.12
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  [OK] Python %PYVER% 확인

REM ── 필요 라이브러리 설치 ─────────────────────────────────────
echo  [1/3] 필요 라이브러리 설치 중...
python -m pip install -q --upgrade pip > nul 2>&1
python -m pip install -q requests psutil schedule colorama > nul 2>&1
echo  [OK] 라이브러리 설치 완료

REM ── 에이전트 스크립트 생성 ───────────────────────────────────
echo  [2/3] 에이전트 설정 생성 중...

REM 현재 디렉토리에 agent 파일 생성
set AGENT_DIR=%~dp0

python -c "
import os, sys
agent_dir = r'%AGENT_DIR%'

# config.py 생성
config_content = '''
SERVER_URL = 'https://jntubkwn.gensparkclaw.com'
REGISTER_EMAIL = 'htkim@dsti.co.kr'
REGISTER_PASSWORD = 'Dsti@Admin1!'
HEARTBEAT_INTERVAL_MIN = 5
PC_LOCATION = 'DSTI 사무실'
'''.strip()

with open(os.path.join(agent_dir, 'config.py'), 'w', encoding='utf-8') as f:
    f.write(config_content)
print('[OK] config.py 생성')
"

REM ── agent.py 다운로드 ────────────────────────────────────────
echo  [3/3] 에이전트 파일 다운로드 중...
python -c "
import urllib.request, os, sys
base = 'https://jntubkwn.gensparkclaw.com/agent/'
files = ['agent.py', 'api_client.py', 'collector.py']
agent_dir = r'%AGENT_DIR%'
for f in files:
    try:
        url = base + f
        urllib.request.urlretrieve(url, os.path.join(agent_dir, f))
        print(f'  [OK] {f} 다운로드')
    except Exception as e:
        print(f'  [!!] {f} 다운로드 실패: {e}')
        sys.exit(1)
"
if %errorLevel% neq 0 (
    echo.
    echo  [오류] 파일 다운로드 실패. 인터넷 연결을 확인하세요.
    echo  서버: https://jntubkwn.gensparkclaw.com
    pause
    exit /b 1
)

echo.
echo  ══════════════════════════════════════════════════════
echo   설치 완료! 에이전트를 시작합니다...
echo   대시보드: https://jntubkwn.gensparkclaw.com
echo   종료: 이 창을 닫으세요 (Ctrl+C)
echo  ══════════════════════════════════════════════════════
echo.

REM ── 에이전트 실행 (첫 번째 테스트) ──────────────────────────
python "%AGENT_DIR%agent.py" --test

if %errorLevel% neq 0 (
    echo.
    echo  [오류] 서버 연결 실패. 아래를 확인하세요:
    echo   - 인터넷 연결 상태
    echo   - 방화벽에서 443 포트 허용 여부
    echo   - config.py 의 이메일/비밀번호
    pause
    exit /b 1
)

echo.
echo  ══════════════════════════════════════════════════════
echo   테스트 성공! 에이전트를 상시 실행하시겠습니까?
echo   (5분마다 보안 상태를 자동으로 전송합니다)
echo  ══════════════════════════════════════════════════════
echo.
set /p RUN_ALWAYS="계속 실행하려면 Y를 입력하세요 [Y/N]: "
if /i "%RUN_ALWAYS%"=="Y" (
    echo.
    echo  에이전트 상시 실행 중... (종료: Ctrl+C 또는 창 닫기)
    python "%AGENT_DIR%agent.py"
) else (
    echo  나중에 실행하려면 이 파일을 다시 클릭하세요.
)

pause
