"""Branded PDF report generation for ReqQuality AI exports."""

from datetime import datetime, timezone
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

FOREST = colors.HexColor("#173F35")
SECONDARY_GREEN = colors.HexColor("#285B4A")
ACCENT_GREEN = colors.HexColor("#3F765F")
CHARCOAL = colors.HexColor("#161A18")
BEIGE = colors.HexColor("#F4EFE6")
SURFACE = colors.HexColor("#FBF7F0")
BORDER = colors.HexColor("#D8CEC0")
MUTED = colors.HexColor("#6B706C")

SOURCE_LABELS = {
    "original": "Original",
    "rule_based": "Rule-based",
    "ai_suggestion": "AI Suggestion",
    "ai_assumption": "AI Assumption",
    "confirmed": "Confirmed",
}


def _generated_at():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=21, leading=26, textColor=CHARCOAL, alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", parent=base["Normal"], fontSize=9,
            leading=13, textColor=MUTED, spaceAfter=13,
        ),
        "section": ParagraphStyle(
            "ReportSection", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=12, leading=16, textColor=FOREST, spaceBefore=11,
            spaceAfter=6, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "ReportBody", parent=base["BodyText"], fontSize=8.5,
            leading=12, textColor=CHARCOAL, spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "ReportSmall", parent=base["BodyText"], fontSize=7.5,
            leading=10, textColor=MUTED,
        ),
        "label": ParagraphStyle(
            "ReportLabel", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8, leading=11, textColor=FOREST,
        ),
        "table_header": ParagraphStyle(
            "ReportTableHeader", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8, leading=10, textColor=colors.white,
        ),
    }


def _paragraph(text, style):
    safe_text = escape(str(text)).replace("\r\n", "\n").replace("\r", "\n")
    return Paragraph(safe_text.replace("\n", "<br/>"), style)


def _content_paragraph(item, review_status, style, default_source=None):
    if isinstance(item, dict):
        text = item.get("text", item.get("description", ""))
        source = item.get("source", default_source)
        needs_confirmation = bool(item.get("needs_confirmation"))
    else:
        text = item
        source = default_source
        needs_confirmation = False

    labels = []
    if source:
        labels.append(SOURCE_LABELS.get(source, "Rule-based"))
    if needs_confirmation:
        labels.append("Needs Confirmation")
    elif source == "confirmed" or review_status == "Approved":
        labels.append("Confirmed")
    prefix = " ".join(f"[{label}]" for label in dict.fromkeys(labels))
    content = f"{prefix} {text}" if prefix else str(text)
    return _paragraph(content, style)


def _item_list(items, review_status, styles, default_source=None):
    if not isinstance(items, list):
        items = [items] if items else []
    if not items:
        return [_paragraph("None recorded.", styles["small"])]
    return [
        _content_paragraph(item, review_status, styles["body"], default_source)
        for item in items
    ]


def _section(story, title, styles):
    story.append(Paragraph(escape(title), styles["section"]))


def _key_value_table(rows, styles, label_width=43 * mm):
    table_data = [
        [_paragraph(label, styles["label"]), value]
        for label, value in rows
    ]
    table = Table(table_data, colWidths=[label_width, 165 * mm - label_width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BEIGE),
        ("BACKGROUND", (1, 0), (1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _draw_chrome(canvas, document):
    canvas.saveState()
    page_width, page_height = A4
    canvas.setFillColor(FOREST)
    canvas.rect(0, page_height - 13 * mm, page_width, 13 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(18 * mm, page_height - 8.5 * mm, "ReqQuality AI")
    canvas.setFillColor(colors.HexColor("#D7E4D8"))
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(page_width - 18 * mm, page_height - 8.5 * mm, "REQUIREMENTS & SOFTWARE QUALITY")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 14 * mm, page_width - 18 * mm, 14 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 9 * mm, "Final Year Project | ReqQuality AI")
    canvas.drawRightString(page_width - 18 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def _build_pdf(story, title):
    output = BytesIO()
    document = BaseDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=21 * mm,
        bottomMargin=19 * mm,
        title=title,
        author="ReqQuality AI",
        subject="Requirements and Software Quality Engineering Report",
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="report-content",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_draw_chrome)])
    document.build(story)
    output.seek(0)
    return output


def build_requirement_pdf(requirement):
    styles = _styles()
    story = [
        Paragraph(f"Requirement Report | #{int(requirement['id'])}", styles["title"]),
        _paragraph(f"Generated {_generated_at()}", styles["subtitle"]),
    ]
    review_status = requirement.get("review_status", "Pending")
    analysis = requirement.get("analysis_summary") or {}
    labeled = analysis.get("labeled_analysis") or {}
    story.append(_key_value_table([
        ("Requirement ID", _paragraph(requirement.get("id", ""), styles["body"])),
        ("Title", _paragraph(requirement.get("title", ""), styles["body"])),
        ("Requirement Type", _paragraph(requirement.get("requirement_type", ""), styles["body"])),
        ("User Priority", _paragraph(requirement.get("user_priority", requirement.get("priority", "")), styles["body"])),
        ("Suggested Priority", _paragraph(requirement.get("suggested_priority") or "Not assessed", styles["body"])),
        ("Quality Risk Score", _paragraph(f"{requirement.get('risk_score')}/100" if requirement.get("risk_score") is not None else "Not assessed", styles["body"])),
        ("Risk Level", _paragraph(requirement.get("risk_level") or "Not assessed", styles["body"])),
    ], styles))

    _section(story, "Original Requirement", styles)
    story.append(_paragraph(requirement.get("description", ""), styles["body"]))

    for title, key, default_source in (
        ("Ambiguity Findings", "ambiguity_issues", "rule_based"),
        ("Missing Information", "missing_information", "rule_based"),
        ("Testability Findings", "testability_issues", "rule_based"),
        ("Assumptions", "assumptions", "ai_assumption"),
    ):
        _section(story, title, styles)
        items = labeled.get(key) or analysis.get(key) or []
        story.extend(_item_list(items, review_status, styles, default_source))

    _section(story, "Improved Requirement", styles)
    improved = labeled.get("improved_requirement") or analysis.get("improved_requirement")
    if improved:
        story.append(_content_paragraph(improved, review_status, styles["body"], "ai_suggestion"))
    else:
        story.append(_paragraph("No improved requirement recorded.", styles["small"]))

    _section(story, "Acceptance Criteria", styles)
    criteria = requirement.get("acceptance_criteria", [])
    if criteria:
        for criterion in criteria:
            code = criterion.get("criterion_code", "")
            description = criterion.get("description", "")
            paragraph = _content_paragraph(
                {**criterion, "text": f"{code}: {description}"},
                review_status,
                styles["body"],
                "rule_based",
            )
            story.append(paragraph)
    else:
        story.append(_paragraph("No acceptance criteria recorded.", styles["small"]))

    _section(story, "Generated Test Scenarios", styles)
    scenarios = requirement.get("test_scenarios", [])
    if not scenarios:
        story.append(_paragraph("No linked test scenarios recorded.", styles["small"]))
    for scenario in scenarios:
        scenario_title = f"{scenario.get('scenario_code', '')} | {scenario.get('category', '')}: {scenario.get('title', '')}"
        story.append(_content_paragraph(
            {**scenario, "text": scenario_title},
            review_status,
            styles["label"],
            "rule_based",
        ))
        if scenario.get("assumption_reasons"):
            story.append(_content_paragraph(
                {"text": "Assumptions: " + "; ".join(scenario["assumption_reasons"]), "source": "ai_assumption", "needs_confirmation": scenario.get("needs_confirmation", False)},
                review_status,
                styles["small"],
            ))
        story.append(_paragraph("Preconditions", styles["label"]))
        story.extend(_item_list(scenario.get("preconditions", []), review_status, styles))
        story.append(_paragraph("Test Steps", styles["label"]))
        story.extend(_item_list(scenario.get("test_steps", []), review_status, styles))
        story.append(_paragraph("Expected Result", styles["label"]))
        story.append(_paragraph(scenario.get("expected_result", ""), styles["body"]))
        story.append(Spacer(1, 4))

    _section(story, "Traceability", styles)
    story.append(_key_value_table([
        ("Requirement", _paragraph(f"REQ-{requirement.get('id')}", styles["body"])),
        ("Acceptance Criteria", _paragraph(
            ", ".join(item.get("criterion_code", "") for item in criteria) or "None linked",
            styles["body"],
        )),
        ("Test Scenarios", _paragraph(
            ", ".join(item.get("scenario_code", "") for item in scenarios) or "None linked",
            styles["body"],
        )),
        ("Traceability", _paragraph(
            "Criteria and scenarios are linked to this requirement record." if criteria and scenarios
            else "Traceability is incomplete: one or more linked verification artifacts are missing.",
            styles["body"],
        )),
    ], styles))

    _section(story, "SQA Review", styles)
    story.append(_key_value_table([
        ("Review Status", _paragraph(review_status, styles["body"])),
        ("Reviewer Notes", _paragraph(requirement.get("reviewer_notes") or "No reviewer notes.", styles["body"])),
        ("Reviewer Name", _paragraph(requirement.get("reviewed_by_name") or "Not assigned", styles["body"])),
        ("Review Timestamp", _paragraph(requirement.get("reviewed_at") or "Not reviewed", styles["body"])),
    ], styles))
    return _build_pdf(story, f"ReqQuality AI Requirement {requirement.get('id')}")


def build_project_summary_pdf(summary):
    styles = _styles()
    story = [
        Paragraph("Project Quality Summary", styles["title"]),
        _paragraph(f"ReqQuality AI | Generated {_generated_at()}", styles["subtitle"]),
    ]
    _section(story, "Project Overview", styles)
    story.append(_key_value_table([
        ("Total Requirements", _paragraph(summary["total_requirements"], styles["body"])),
        ("Average Quality Risk Score", _paragraph(f"{summary['average_risk_score']}/100", styles["body"])),
        ("Total Test Scenarios", _paragraph(summary["total_test_scenarios"], styles["body"])),
        ("Traceability Coverage", _paragraph(f"{summary['traceability_coverage_percent']}% ({summary['traceable_requirement_count']} requirements)", styles["body"])),
    ], styles))

    _section(story, "Review Status Distribution", styles)
    story.append(_key_value_table([
        (status, _paragraph(summary["review_counts"].get(status, 0), styles["body"]))
        for status in ("Approved", "Pending", "In Review", "Needs Revision")
    ], styles))

    _section(story, "Risk Distribution", styles)
    story.append(_key_value_table([
        (level, _paragraph(summary["risk_counts"].get(level, 0), styles["body"]))
        for level in ("Low", "Medium", "High", "Critical", "Unscored")
    ], styles))

    _section(story, "Requirement Type Distribution", styles)
    story.append(_key_value_table([
        (kind, _paragraph(summary["type_counts"].get(kind, 0), styles["body"]))
        for kind in ("Functional", "Non-Functional", "Business")
    ], styles))

    _section(story, "High Attention Requirements", styles)
    high_attention = summary.get("high_attention_requirements", [])
    if high_attention:
        table_data = [[
            _paragraph("ID", styles["table_header"]),
            _paragraph("Title", styles["table_header"]),
            _paragraph("Risk", styles["table_header"]),
            _paragraph("Review Status", styles["table_header"]),
        ]]
        for requirement in high_attention:
            risk = requirement.get("risk_score")
            table_data.append([
                _paragraph(requirement.get("id", ""), styles["body"]),
                _paragraph(requirement.get("title", ""), styles["body"]),
                _paragraph(f"{risk}/100 · {requirement.get('risk_level') or 'Unscored'}" if risk is not None else "Unscored", styles["body"]),
                _paragraph(requirement.get("review_status", "Pending"), styles["body"]),
            ])
        table = Table(table_data, colWidths=[15 * mm, 88 * mm, 30 * mm, 32 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_GREEN),
            ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
    else:
        story.append(_paragraph("No high-attention requirements.", styles["small"]))

    return _build_pdf(story, "ReqQuality AI Project Quality Summary")
