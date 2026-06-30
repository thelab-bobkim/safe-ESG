"""
MediSafe Clinic - PDF 보고서 자동 생성 서비스
규제 컴플라이언스 점검 결과를 PDF 파일로 출력합니다.
"""
import io
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.compliance import ComplianceCheck, ComplianceCheckResult, CheckStatus


STATUS_LABELS = {
    CheckStatus.PASS: "통과 ✓",
    CheckStatus.FAIL: "미충족 ✗",
    CheckStatus.PARTIAL: "부분 충족 △",
    CheckStatus.NA: "해당없음",
    CheckStatus.PENDING: "미확인",
}

STATUS_COLORS = {
    CheckStatus.PASS: (0.0, 0.6, 0.2),       # 초록
    CheckStatus.FAIL: (0.8, 0.1, 0.1),        # 빨강
    CheckStatus.PARTIAL: (0.9, 0.6, 0.0),     # 주황
    CheckStatus.NA: (0.5, 0.5, 0.5),          # 회색
    CheckStatus.PENDING: (0.4, 0.4, 0.7),     # 파랑
}

REGULATION_LABELS = {
    "privacy_act_29": "개인정보보호법 제29조",
    "medical_act_23": "의료법 제23조",
    "emr_cert": "EMR 인증 기준",
    "isms_p": "ISMS-P",
}

GUIDANCE_MAP = {
    "fail": [
        "즉각적인 조치가 필요합니다.",
        "IT 담당자 또는 보안 전문가에게 문의하세요.",
        "조치 완료 후 재점검을 실시하세요.",
    ],
    "partial": [
        "부분적으로 이행되고 있습니다. 미이행 부분을 보완하세요.",
        "단계적 개선 계획을 수립하고 이행하세요.",
    ],
    "pending": [
        "점검이 필요한 항목입니다. 담당자를 지정하여 확인하세요.",
    ],
}


def generate_compliance_pdf(check_id: int, db: Session) -> bytes:
    """
    컴플라이언스 점검 결과 PDF 바이트를 생성하여 반환합니다.

    Args:
        check_id: 점검 세션 ID
        db: DB 세션

    Returns:
        PDF 바이트 스트림
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # ── 한글 폰트 설정 (시스템 폰트 → Helvetica fallback) ──
    korean_font = "Helvetica"
    korean_font_bold = "Helvetica-Bold"

    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    font_bold_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/unfonts-core/UnDotumBold.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    ]

    for p in font_paths:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont("Korean", p))
                korean_font = "Korean"
                break
            except Exception:
                pass

    for p in font_bold_paths:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont("KoreanBold", p))
                korean_font_bold = "KoreanBold"
                break
            except Exception:
                pass

    # ── 데이터 로드 ──
    check: Optional[ComplianceCheck] = db.query(ComplianceCheck).filter(
        ComplianceCheck.id == check_id
    ).first()

    if not check:
        raise ValueError(f"점검 ID {check_id}를 찾을 수 없습니다.")

    results = check.results  # ComplianceCheckResult list

    # 테넌트 정보
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == check.tenant_id).first()
    hospital_name = tenant.name if tenant else "병원명 미상"

    # ── PDF 생성 ──
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # 스타일 정의
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontName=korean_font_bold,
        fontSize=20,
        spaceAfter=6,
        textColor=colors.HexColor("#1a3a5c"),
    )
    h2_style = ParagraphStyle(
        "CustomH2",
        parent=styles["Heading2"],
        fontName=korean_font_bold,
        fontSize=13,
        spaceAfter=4,
        spaceBefore=12,
        textColor=colors.HexColor("#1a3a5c"),
    )
    h3_style = ParagraphStyle(
        "CustomH3",
        parent=styles["Heading3"],
        fontName=korean_font_bold,
        fontSize=11,
        spaceAfter=3,
        spaceBefore=8,
        textColor=colors.HexColor("#2c5282"),
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontName=korean_font,
        fontSize=9,
        spaceAfter=3,
        leading=14,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName=korean_font,
        fontSize=8,
        spaceAfter=2,
        leading=12,
        textColor=colors.HexColor("#444444"),
    )

    # ── 헤더 ──
    story.append(Paragraph("🏥 MediSafe Clinic", title_style))
    story.append(Paragraph("보안 컴플라이언스 점검 보고서", h2_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a3a5c")))
    story.append(Spacer(1, 0.3 * cm))

    # 기본 정보 테이블
    checked_at_str = (
        check.checked_at.strftime("%Y년 %m월 %d일 %H:%M")
        if check.checked_at else "미상"
    )
    next_check_str = (
        check.next_check_at.strftime("%Y년 %m월 %d일")
        if check.next_check_at else "미정"
    )

    info_data = [
        ["병원명", hospital_name, "점검일시", checked_at_str],
        ["점검자", check.checked_by_name or "자동", "다음 점검 예정일", next_check_str],
        ["보고서 생성일", datetime.now().strftime("%Y년 %m월 %d일"), "점검 ID", f"#{check.id}"],
    ]

    info_table = Table(info_data, colWidths=[3 * cm, 7 * cm, 3.5 * cm, 4 * cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), korean_font),
        ("FONTNAME", (0, 0), (0, -1), korean_font_bold),
        ("FONTNAME", (2, 0), (2, -1), korean_font_bold),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f0fe")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e8f0fe")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── 종합 점수 카드 ──
    story.append(Paragraph("■ 종합 점수 카드", h2_style))

    def score_color(score):
        if score >= 80:
            return colors.HexColor("#1a7a3c")
        elif score >= 60:
            return colors.HexColor("#c07000")
        else:
            return colors.HexColor("#c0392b")

    def grade_label(score):
        if score >= 90: return "A (우수)"
        if score >= 80: return "B (양호)"
        if score >= 60: return "C (보통)"
        if score >= 40: return "D (미흡)"
        return "F (불량)"

    score_data = [
        ["구분", "점수", "등급"],
        ["종합 컴플라이언스", f"{check.total_score:.1f}점", grade_label(check.total_score)],
        ["개인정보보호법 제29조", f"{check.privacy_score:.1f}점", grade_label(check.privacy_score)],
        ["의료법 제23조", f"{check.medical_score:.1f}점", grade_label(check.medical_score)],
        ["EMR 인증 기준", f"{check.emr_score:.1f}점", grade_label(check.emr_score)],
    ]

    score_table = Table(score_data, colWidths=[7 * cm, 4 * cm, 6.5 * cm])
    score_style = TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), korean_font),
        ("FONTNAME", (0, 0), (-1, 0), korean_font_bold),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#dbeafe")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTSIZE", (0, 1), (0, 1), 10),
        ("FONTNAME", (0, 1), (0, 1), korean_font_bold),
    ])
    # 점수별 색상
    for i, score in enumerate([check.total_score, check.privacy_score,
                                check.medical_score, check.emr_score], 1):
        score_style.add("TEXTCOLOR", (1, i), (2, i), score_color(score))
        if i == 1:
            score_style.add("FONTNAME", (1, i), (2, i), korean_font_bold)
    score_table.setStyle(score_style)
    story.append(score_table)
    story.append(Spacer(1, 0.3 * cm))

    # 항목 수 요약
    summary_data = [["통과", "미충족", "부분충족", "해당없음", "미확인", "합계"]]
    summary_data.append([
        str(check.pass_count),
        str(check.fail_count),
        str(check.partial_count),
        str(check.na_count),
        str(len(results) - check.pass_count - check.fail_count - check.partial_count - check.na_count),
        str(len(results)),
    ])
    summary_table = Table(summary_data, colWidths=[2.5 * cm] * 6)
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), korean_font),
        ("FONTNAME", (0, 0), (-1, 0), korean_font_bold),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#1a7a3c")),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#c0392b")),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#c07000")),
        ("BACKGROUND", (3, 0), (3, 0), colors.HexColor("#7f8c8d")),
        ("BACKGROUND", (4, 0), (4, 0), colors.HexColor("#2980b9")),
        ("BACKGROUND", (5, 0), (5, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── 14개 항목 결과표 ──
    story.append(Paragraph("■ 점검 항목별 결과", h2_style))

    # 규제별로 그룹화
    groups: dict = {}
    for r in results:
        reg = r.item.regulation if r.item else "unknown"
        groups.setdefault(reg, []).append(r)

    for reg_key, reg_results in groups.items():
        reg_label = REGULATION_LABELS.get(str(reg_key), str(reg_key))
        story.append(Paragraph(f"▶ {reg_label}", h3_style))

        table_data = [["항목코드", "항목명", "결과", "증빙/이행 내용"]]
        for r in reg_results:
            item = r.item
            status_label = STATUS_LABELS.get(r.status, str(r.status))
            evidence = (r.evidence or "")[:80]  # 최대 80자
            if len(r.evidence or "") > 80:
                evidence += "..."
            table_data.append([
                Paragraph(item.item_code if item else "-", small_style),
                Paragraph(item.title[:40] if item else "-", small_style),
                Paragraph(status_label, small_style),
                Paragraph(evidence, small_style),
            ])

        col_widths = [2.2 * cm, 4.5 * cm, 2.5 * cm, 8.3 * cm]
        result_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        result_style = TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), korean_font),
            ("FONTNAME", (0, 0), (-1, 0), korean_font_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f7fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
        # 결과 컬럼 색상
        for i, r in enumerate(reg_results, 1):
            col_color = STATUS_COLORS.get(r.status, (0.3, 0.3, 0.3))
            result_style.add(
                "TEXTCOLOR", (2, i), (2, i),
                colors.Color(*col_color)
            )
        result_table.setStyle(result_style)
        story.append(result_table)
        story.append(Spacer(1, 0.3 * cm))

    # ── 조치 가이드 ──
    story.append(Paragraph("■ 조치 가이드", h2_style))

    fail_items = [r for r in results if r.status == CheckStatus.FAIL]
    partial_items = [r for r in results if r.status == CheckStatus.PARTIAL]
    pending_items = [r for r in results if r.status == CheckStatus.PENDING]

    if not fail_items and not partial_items and not pending_items:
        story.append(Paragraph(
            "✅ 모든 항목이 기준을 충족합니다. 지속적인 모니터링을 유지하세요.",
            body_style
        ))
    else:
        if fail_items:
            story.append(Paragraph("🔴 즉각 조치 필요 항목 (FAIL)", h3_style))
            guide_data = [["항목코드", "항목명", "권고 조치사항"]]
            for r in fail_items:
                item = r.item
                guidance = item.guidance[:100] if item and item.guidance else "담당자 확인 후 즉시 조치 필요"
                if item and item.guidance and len(item.guidance) > 100:
                    guidance += "..."
                guide_data.append([
                    Paragraph(item.item_code if item else "-", small_style),
                    Paragraph(item.title[:35] if item else "-", small_style),
                    Paragraph(guidance, small_style),
                ])
            guide_table = Table(guide_data, colWidths=[2.2 * cm, 4.5 * cm, 10.8 * cm])
            guide_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), korean_font),
                ("FONTNAME", (0, 0), (-1, 0), korean_font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c0392b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(guide_table)
            story.append(Spacer(1, 0.3 * cm))

        if partial_items:
            story.append(Paragraph("🟡 보완 필요 항목 (PARTIAL)", h3_style))
            guide_data = [["항목코드", "항목명", "권고 조치사항"]]
            for r in partial_items:
                item = r.item
                guidance = item.guidance[:100] if item and item.guidance else "부분 이행 중 — 미이행 부분 보완 필요"
                if item and item.guidance and len(item.guidance) > 100:
                    guidance += "..."
                guide_data.append([
                    Paragraph(item.item_code if item else "-", small_style),
                    Paragraph(item.title[:35] if item else "-", small_style),
                    Paragraph(guidance, small_style),
                ])
            guide_table = Table(guide_data, colWidths=[2.2 * cm, 4.5 * cm, 10.8 * cm])
            guide_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), korean_font),
                ("FONTNAME", (0, 0), (-1, 0), korean_font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c07000")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(guide_table)
            story.append(Spacer(1, 0.3 * cm))

    # ── 법적 안내문 ──
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#999999")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "※ 본 보고서는 MediSafe Clinic 자동화 시스템으로 생성된 참고 자료입니다. "
        "공식 규제 감사 제출 전 법무/보안 전문가의 검토를 받으시기 바랍니다.",
        small_style
    ))
    story.append(Paragraph(
        f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | MediSafe Clinic v2.0",
        small_style
    ))

    # PDF 빌드
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
