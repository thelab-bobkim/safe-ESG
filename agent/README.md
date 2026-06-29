# MediSafe Clinic - PC 보안 에이전트

병원 사내 PC에 설치하여 MediSafe 서버로 보안 상태를 자동 전송하는 에이전트입니다.

---

## 📋 사전 요구사항

- **Python 3.11 이상** (https://www.python.org/downloads/)
  - 설치 시 **"Add Python to PATH"** 반드시 체크!
- 인터넷 연결 (HTTPS 443 포트)

---

## 🚀 설치 방법 (Windows)

### 1단계: 에이전트 폴더 다운로드
이 폴더를 `C:\MediSafe\` 에 복사합니다.

### 2단계: config.py 수정
메모장으로 `config.py`를 열고 아래 항목을 수정하세요:

```python
SERVER_URL = "https://jntubkwn.gensparkclaw.com"  # 그대로 유지

REGISTER_EMAIL    = "doctor@yonsei-clinic.kr"   # ← 원장 이메일
REGISTER_PASSWORD = "Doctor1234!"               # ← 원장 비밀번호

PC_LOCATION = "원무실"   # ← 이 PC 위치 (예: 원무실, 진료실1, 원장실)
```

### 3단계: 설치 실행
`install_windows.bat`를 **우클릭 → 관리자 권한으로 실행**

---

## ▶️ 수동 실행

```bash
# 1회 테스트 (결과 확인 후 종료)
python agent.py --test

# 일반 실행 (5분마다 자동 전송)
python agent.py

# 처음 등록만 수행
python agent.py --setup
```

---

## 📊 수집 정보

| 항목 | 설명 | 주기 |
|------|------|------|
| 디스크 암호화 | BitLocker 활성화 여부 | 5분 |
| 백신 설치 | Windows Defender 상태 | 5분 |
| OS 패치 | 최근 업데이트 여부 | 5분 |
| 방화벽 | Windows 방화벽 상태 | 5분 |
| 화면 잠금 | 화면보호기 설정 여부 | 5분 |
| USB 이벤트 | USB 연결/해제 감지 | 실시간 |
| 시스템 리소스 | CPU/메모리/디스크 사용률 | 5분 |

---

## 🔒 보안 고지

- 에이전트는 **보안 설정 상태만** 수집합니다 (파일 내용, 개인정보 수집 없음)
- 모든 통신은 **HTTPS(TLS 1.3)** 으로 암호화됩니다
- 수집 데이터는 **병원 원장만** 확인 가능합니다

---

## ❓ 문제 해결

| 문제 | 해결 방법 |
|------|-----------|
| 서버 연결 실패 | 인터넷 연결 확인, 방화벽에서 443 포트 허용 |
| 로그인 실패 | config.py의 이메일/비밀번호 확인 |
| Python 없음 | python.org에서 설치 후 PATH 추가 |

---

**대시보드**: https://jntubkwn.gensparkclaw.com
