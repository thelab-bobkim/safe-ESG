# 🏥 MediSafe Clinic — 의료정보보호 SaaS 베타 v0.1

> 소형 병·의원을 위한 의료정보보호 구독형 SaaS 플랫폼

---

## 📋 개요

MediSafe Clinic은 IT 전담 인력이 없는 소형 병·의원이 개인정보보호법 제29조, 의료법 제23조를 준수하고 랜섬웨어, 개인정보 유출, 규제 감사에 대응할 수 있도록 돕는 Managed Security SaaS입니다.

### 베타 버전 포함 모듈
| 모듈 | 설명 |
|------|------|
| **SafeEndpoint** | PC 보안 상태 모니터링 (암호화, 백신, 패치, USB, 방화벽) |
| **SafeLog** | 접속 로그 수집·보존·검색·CSV 내보내기 (WORM 방식) |
| **SafeGuard** | 규제 컴플라이언스 체크리스트 (개인정보보호법·의료법·EMR인증) |

---

## 🚀 빠른 시작

### 1. 환경 변수 설정
```bash
cp .env .env.local
# .env.local에서 SECRET_KEY 등 수정 (프로덕션용)
```

### 2. Docker로 전체 실행
```bash
cd medisafe
docker-compose up -d
```

### 3. 접속
| 서비스 | URL |
|--------|-----|
| **프론트엔드 대시보드** | http://localhost:3000 |
| **백엔드 API 문서** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |

---

## 🔑 기본 계정

| 역할 | 이메일 | 비밀번호 | 설명 |
|------|--------|---------|------|
| 슈퍼관리자 | admin@medisafe.clinic | Admin1234! | 플랫폼 전체 관리 |
| 원장 (연세가정의원) | doctor@yonsei-clinic.kr | Doctor1234! | 병원 관리자 |
| 직원 (연세가정의원) | staff@yonsei-clinic.kr | Staff1234! | 일반 직원 |
| 원장 (서울연합치과) | doctor@seoul-dental.kr | Doctor5678! | 체험판 고객 |

---

## 💰 구독 플랜

| 플랜 | 월 요금 | 대상 | 엔드포인트 |
|------|---------|------|----------|
| **Clinic Basic** | 4.9만원/월 | 1~3대 소형 의원 | 최대 3대 |
| **Clinic Standard** | 14.9만원/월 | 3~10대 일반 의원 | 최대 10대 |
| **Clinic Pro** | 34.9만원/월 | 10대 이상·다지점 | 무제한 |

---

## 🏗️ 기술 아키텍처

```
medisafe/
├── backend/                # FastAPI (Python 3.11+)
│   └── app/
│       ├── core/           # 설정, 인증, DB 연결
│       ├── models/         # SQLAlchemy ORM 모델
│       ├── api/            # API 라우터
│       └── services/       # 보안 점수 계산 등
├── frontend/               # React 18 + TypeScript + Tailwind CSS
│   └── src/
│       ├── pages/          # 대시보드, 엔드포인트, 로그, 컴플라이언스
│       └── api/            # Axios 클라이언트
└── docker-compose.yml      # PostgreSQL + Redis + Backend + Frontend
```

---

## 🔐 보안 설계 원칙

1. **멀티테넌트 격리**: 모든 DB 쿼리에 `tenant_id` 필터 강제 적용
2. **JWT 인증**: 모든 API 엔드포인트 JWT Bearer 토큰 필수
3. **WORM 로그**: 접속 로그는 삭제·수정 불가 (규제 증빙용)
4. **bcrypt**: 비밀번호 bcrypt 해시 저장
5. **최소 권한**: 역할별(원장/직원/슈퍼관리자) 접근 권한 분리
6. **감사 추적**: 모든 로그인·정책변경·관리자 행위 자동 기록

---

## 📊 보안 점수 계산 방식

**종합 점수 = SafeEndpoint(50%) + SafeGuard(35%) + SafeLog(15%)**

| 항목 | 가중치 |
|------|--------|
| 디스크 암호화 | 25점 |
| 백신 설치 | 20점 |
| OS 최신 패치 | 20점 |
| 백신 업데이트 | 15점 |
| 방화벽 활성화 | 10점 |
| 화면 잠금 | 5점 |
| USB 차단 | 5점 |

---

## 📡 주요 API

```
POST  /api/v1/auth/login          # 로그인
GET   /api/v1/dashboard/summary   # 대시보드 요약
GET   /api/v1/endpoints/          # 엔드포인트 목록
POST  /api/v1/endpoints/agent/heartbeat  # 에이전트 상태 보고
GET   /api/v1/logs/               # 접속 로그 조회
GET   /api/v1/logs/export/csv     # CSV 내보내기
GET   /api/v1/compliance/checks   # 점검 이력
POST  /api/v1/compliance/checks   # 새 점검 시작
```

---

## 🗺️ 개발 로드맵

| Phase | 기간 | 내용 |
|-------|------|------|
| **베타 (현재)** | M0~M3 | SafeEndpoint + SafeLog + SafeGuard MVP |
| **Phase 2** | M4~M6 | SafeBackup, 사고 알림, 월간 리포트 PDF |
| **Phase 3** | M7~M9 | 파트너 API, OEM 브랜딩, 과금 연동 |
| **Phase 4** | M10~M12 | 자동 격리, 이상 탐지, 다지점 관리 |

---

## 📞 문의
- 이메일: contact@medisafe.clinic
- 무료 진단 신청: https://medisafe.clinic/trial

*© 2024 MediSafe Clinic. 의료정보보호 전문 플랫폼 베타 버전*
