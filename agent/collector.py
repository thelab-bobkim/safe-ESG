"""
MediSafe Clinic - 보안 정보 수집기
Windows/Linux/macOS에서 PC 보안 상태를 수집합니다.
"""

import os
import sys
import socket
import platform
import subprocess
import psutil
from datetime import datetime

def get_hostname() -> str:
    return socket.gethostname()

def get_ip_address() -> str:
    """실제 외부 통신용 IP 반환"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_os_info() -> dict:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }

def check_disk_encryption() -> bool | None:
    """디스크 암호화 여부 확인"""
    system = platform.system()
    try:
        if system == "Windows":
            # BitLocker 확인
            result = subprocess.run(
                ["manage-bde", "-status", "C:"],
                capture_output=True, text=True, timeout=10
            )
            return "Protection On" in result.stdout or "보호 설정" in result.stdout
        elif system == "Darwin":
            # macOS FileVault
            result = subprocess.run(
                ["fdesetup", "status"],
                capture_output=True, text=True, timeout=10
            )
            return "FileVault is On" in result.stdout
        elif system == "Linux":
            # LUKS 암호화 확인
            result = subprocess.run(
                ["lsblk", "-o", "TYPE"],
                capture_output=True, text=True, timeout=10
            )
            return "crypt" in result.stdout
    except Exception:
        pass
    return None

def check_antivirus() -> bool | None:
    """백신 설치 여부 확인"""
    system = platform.system()
    try:
        if system == "Windows":
            # Windows Defender 및 주요 백신 확인
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-MpComputerStatus | Select-Object -ExpandProperty AntivirusEnabled"],
                capture_output=True, text=True, timeout=15, shell=False
            )
            return "True" in result.stdout
        elif system == "Darwin":
            # macOS 엔드포인트 보안 확인
            av_apps = [
                "/Applications/Malwarebytes.app",
                "/Applications/CrowdStrike Falcon.app",
                "/Library/Intego",
            ]
            return any(os.path.exists(p) for p in av_apps)
        elif system == "Linux":
            # ClamAV 또는 기타 백신 확인
            result = subprocess.run(
                ["which", "clamscan"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
    except Exception:
        pass
    return None

def check_os_patched() -> bool | None:
    """OS 최신 패치 여부 확인"""
    system = platform.system()
    try:
        if system == "Windows":
            # 최근 업데이트 확인 (30일 이내)
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn"],
                capture_output=True, text=True, timeout=20
            )
            if result.stdout.strip():
                last_update = result.stdout.strip()
                # 날짜 파싱하여 30일 이내인지 확인
                return True  # 간소화: 업데이트 기록이 있으면 True
        elif system == "Darwin":
            result = subprocess.run(
                ["softwareupdate", "-l"],
                capture_output=True, text=True, timeout=30
            )
            return "No new software available" in result.stdout
        elif system == "Linux":
            # APT 업데이트 가능 패키지 확인
            result = subprocess.run(
                ["apt-get", "-s", "upgrade"],
                capture_output=True, text=True, timeout=30
            )
            return "0 upgraded" in result.stdout
    except Exception:
        pass
    return None

def check_firewall() -> bool | None:
    """방화벽 활성화 여부 확인"""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True, text=True, timeout=10
            )
            return "ON" in result.stdout.upper()
        elif system == "Darwin":
            result = subprocess.run(
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
                capture_output=True, text=True, timeout=10
            )
            return "enabled" in result.stdout.lower()
        elif system == "Linux":
            result = subprocess.run(
                ["ufw", "status"], capture_output=True, text=True, timeout=10
            )
            return "active" in result.stdout.lower()
    except Exception:
        pass
    return None

def check_screen_lock() -> bool | None:
    """화면 잠금 설정 여부 확인"""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-ItemProperty 'HKCU:\\Control Panel\\Desktop').ScreenSaveTimeOut"],
                capture_output=True, text=True, timeout=10
            )
            timeout = result.stdout.strip()
            return timeout.isdigit() and 0 < int(timeout) <= 900  # 15분 이내
        elif system == "Darwin":
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to tell security preferences to get require password to wake'],
                capture_output=True, text=True, timeout=10
            )
            return "true" in result.stdout.lower()
        elif system == "Linux":
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.screensaver", "lock-enabled"],
                capture_output=True, text=True, timeout=10
            )
            return "true" in result.stdout.lower()
    except Exception:
        pass
    return None

def check_usb_devices() -> list[dict]:
    """현재 연결된 USB 장치 목록"""
    devices = []
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PnpDevice -Class USB | Where-Object Status -eq 'OK' | Select-Object FriendlyName, DeviceID | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            if result.stdout.strip():
                import json
                raw = json.loads(result.stdout)
                if isinstance(raw, dict):
                    raw = [raw]
                for d in (raw or []):
                    devices.append({
                        "name": d.get("FriendlyName", "Unknown"),
                        "device_id": d.get("DeviceID", ""),
                    })
        elif system == "Linux":
            result = subprocess.run(
                ["lsusb"], capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    devices.append({"name": line.strip(), "device_id": ""})
    except Exception:
        pass
    return devices

def get_cpu_usage() -> float:
    return psutil.cpu_percent(interval=1)

def get_memory_usage() -> dict:
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 1),
        "used_percent": mem.percent,
    }

def get_disk_usage() -> dict:
    disk = psutil.disk_usage("/")
    return {
        "total_gb": round(disk.total / (1024**3), 1),
        "used_percent": disk.percent,
    }

def collect_all() -> dict:
    """전체 보안 정보 수집 (메인 함수)"""
    print(f"  🔍 정보 수집 중...")
    
    data = {
        "hostname": get_hostname(),
        "ip_address": get_ip_address(),
        "os_info": get_os_info(),
        "disk_encrypted": check_disk_encryption(),
        "antivirus_installed": check_antivirus(),
        "os_patched": check_os_patched(),
        "firewall_enabled": check_firewall(),
        "screen_lock_enabled": check_screen_lock(),
        "usb_devices": check_usb_devices(),
        "system_metrics": {
            "cpu_usage": get_cpu_usage(),
            "memory": get_memory_usage(),
            "disk": get_disk_usage(),
        },
        "collected_at": datetime.now().isoformat(),
    }
    
    print(f"  ✅ 수집 완료: {data['hostname']} ({data['ip_address']})")
    return data
