# MediSafe Clinic v2.0 개발 로드맵

## 프로젝트 정보
- Live URL: https://jntubkwn.gensparkclaw.com
- Backend: FastAPI + PostgreSQL, PM2 (port 8010)
- Frontend: React 18 + TypeScript + Vite
- Root: /home/work/.openclaw/workspace/medisafe/

## Phase 1 — 필수 (상용화 전 필수)
### F1. PDF 보고서 자동 생성
- 점검 결과 → 감사기관 제출용 PDF
- 라이브러리: reportlab 또는 weasyprint
- 엔드포인트: GET /api/v1/compliance/checks/{id}/pdf
- 파일: backend/app/services/report_service.py

### F2. 이메일/SMS 보안 알림
- 위험 이벤트 즉시 담당자 통보
- 이메일: SMTP (Gmail) / SMS: 알리고 API
- 파일: backend/app/services/notification_service.py
- 트리거: CRITICAL 로그 발생 시 자동 발송

### F3. EMR 프로세스 감지
- 에이전트가 의사랑/비트컴퓨터/유비케어 실행 감지
- collector.py에 emr_detection() 함수 추가
- 감지 대상: CharmEMR.exe, BitEMR.exe, UbiEMR.exe 등

### F4. 셀프 온보딩
- 병원 자체 회원가입 → 등록코드 자동 발급
- 신규 페이지: /register (병원명, 사업자번호, 담당자)
- 엔드포인트: POST /api/v1/auth/register-hospital

### F5. 결제/구독 관리
- 토스페이먼츠 연동
- 플랜별 자동 결제 (Basic 29,000 / Standard 59,000 / Pro 99,000)
- 파일: backend/app/api/billing.py

## Phase 2 — 경쟁력 강화
### F6. 주간 보안 리포트 자동 발송
- 매주 월요일 오전 9시 이메일 발송
- 전주 이벤트 요약 + 보안점수 추이

### F7. 모바일 앱 (PWA)
- React PWA로 변환 (manifest.json + service worker)
- 푸시 알림 지원

### F8. 취약점 원클릭 조치 스크립트
- 미충족 항목 클릭 → PowerShell 스크립트 자동 생성/실행
- BitLocker 활성화, Defender 켜기, 방화벽 설정

### F9. 다중 지점 관리
- 분원 여러 개를 상위 그룹으로 관리
- 모델: HospitalGroup → Tenant (1:N)

## Phase 3 — 사회보장정보원 특화
### F10. 심평원 제출용 보안 점수 포맷
- 건강보험심사평가원 의료기관 정보보호 지표 매핑
- 엑셀/CSV 내보내기

### F11. 개인정보 영향평가(PIA) 보조
- PIA 체크리스트 자동 작성
- 개인정보처리방침 초안 자동 생성

### F12. 의료기관 정보보호 등급 자동 계산
- 1~5등급 자동 산정
- 등급 향상 로드맵 제시

## 개발 순서
Phase 1 → Phase 2 → Phase 3
각 Phase 완료 후 배포 및 테스트
