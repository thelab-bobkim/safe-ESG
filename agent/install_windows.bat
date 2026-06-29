@echo off
chcp 65001 > nul
echo.
echo ╔═══════════════════════════════════════════════╗
echo ║    MediSafe Clinic - PC 에이전트 설치         ║
echo ║    병·의원 의료정보보호 솔루션                  ║
echo ╚═══════════════════════════════════════════════╝
echo.

REM 관리자 권한 확인
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [오류] 관리자 권한으로 실행해주세요.
    echo 이 파일을 우클릭 후 "관리자 권한으로 실행"을 선택하세요.
    pause
    exit /b 1
)

REM Python 설치 확인
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [안내] Python이 설치되지 않았습니다.
    echo Python 3.11 이상을 설치해주세요: https://www.python.org/downloads/
    echo 설치 시 "Add Python to PATH" 옵션을 반드시 체크하세요!
    pause
    exit /b 1
)

echo [1/3] 필요 라이브러리 설치 중...
pip install -q requests psutil schedule colorama pywin32 wmi
if %errorLevel% neq 0 (
    echo [오류] 라이브러리 설치 실패. 인터넷 연결을 확인하세요.
    pause
    exit /b 1
)
echo   완료!

echo [2/3] 에이전트 설정 확인...
if not exist "config.py" (
    echo [오류] config.py 파일이 없습니다. 에이전트 폴더에서 실행하세요.
    pause
    exit /b 1
)
echo   완료!

echo [3/3] 첫 번째 연결 테스트...
python agent.py --test
if %errorLevel% neq 0 (
    echo.
    echo [오류] 서버 연결에 실패했습니다.
    echo config.py에서 SERVER_URL, REGISTER_EMAIL, REGISTER_PASSWORD를 확인하세요.
    pause
    exit /b 1
)

echo.
echo ════════════════════════════════════════════════
echo  설치 완료! 에이전트를 시작합니다.
echo ════════════════════════════════════════════════
echo.
echo 에이전트가 백그라운드에서 5분마다 보안 상태를 전송합니다.
echo 종료하려면 이 창을 닫으세요.
echo.
echo 대시보드: https://jntubkwn.gensparkclaw.com
echo.

REM 윈도우 시작프로그램에 등록 (선택)
set STARTUP_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
echo @echo off > "%STARTUP_PATH%\medisafe-agent.bat"
echo cd /d "%~dp0" >> "%STARTUP_PATH%\medisafe-agent.bat"
echo python agent.py >> "%STARTUP_PATH%\medisafe-agent.bat"
echo 시작프로그램에 등록됨: %STARTUP_PATH%\medisafe-agent.bat

REM 에이전트 실행
python agent.py
pause
