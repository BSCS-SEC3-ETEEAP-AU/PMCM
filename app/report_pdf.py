"""Executive-style visual PDF report rendering for the Reports module."""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

THEMES = {
    "project_status": ("#0B5CAD", "#0F9D8F", "#F59E0B", "#EAF3FB", "#12304A"),
    "competency": ("#6B46C1", "#8B5CF6", "#D946EF", "#F2ECFF", "#39235F"),
    "learning_progress": ("#D97706", "#F59E0B", "#EA580C", "#FFF4E5", "#713F12"),
    "workforce": ("#087F5B", "#0F9D8F", "#65A30D", "#EAF8F3", "#164E3B"),
    "delivery_performance": ("#173B63", "#C53030", "#F97316", "#EEF3F8", "#172B4D"),
}
TEXT = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
LIGHT = colors.HexColor("#F7F9FC")
BORDER = colors.HexColor("#D9E2EC")
TRACK = colors.HexColor("#E7EDF3")
WHITE = colors.white


def _theme(report_type):
    p, s, a, soft, dark = THEMES[report_type]
    return {"primary": colors.HexColor(p), "secondary": colors.HexColor(s), "accent": colors.HexColor(a), "soft": colors.HexColor(soft), "dark": colors.HexColor(dark)}


def _fmt(v):
    if v is None or v == "":
        return "—"
    if hasattr(v, "strftime"):
        return v.strftime("%b %d, %Y")
    return str(v)


def _styles(theme):
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("rt", parent=s["Title"], fontName="Helvetica-Bold", fontSize=23, leading=26, textColor=theme["dark"]),
        "subtitle": ParagraphStyle("rs", parent=s["Normal"], fontSize=9.5, leading=13, textColor=MUTED),
        "section": ParagraphStyle("rh", parent=s["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=theme["dark"], spaceBefore=5, spaceAfter=6),
        "small": ParagraphStyle("rsm", parent=s["BodyText"], fontSize=7.2, leading=9, textColor=MUTED),
        "metric": ParagraphStyle("rm", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=17, leading=19, textColor=theme["primary"]),
        "label": ParagraphStyle("rl", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=MUTED),
        "cardtitle": ParagraphStyle("rct", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=9.5, leading=11, textColor=theme["dark"]),
        "white": ParagraphStyle("rw", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=WHITE),
    }


def _P(value, style):
    return Paragraph(str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def _header_footer(canvas, doc, theme):
    canvas.saveState()
    w, h = doc.pagesize
    canvas.setFillColor(theme["primary"])
    canvas.rect(0, h - 7 * mm, w, 7 * mm, fill=1, stroke=0)
    canvas.setFillColor(theme["dark"])
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.drawString(15 * mm, 10 * mm, "SPM&ECD | Management Report")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(w - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _doc(title, theme):
    ps = landscape(A4)
    m = 14 * mm
    buf = BytesIO()
    d = BaseDocTemplate(buf, pagesize=ps, leftMargin=m, rightMargin=m, topMargin=18 * mm, bottomMargin=17 * mm, title=title, author="SPM&ECD")
    d.addPageTemplates([PageTemplate(id="report", frames=[Frame(m, 17 * mm, ps[0] - 2 * m, ps[1] - 35 * mm, id="normal")], onPage=lambda c, doc: _header_footer(c, doc, theme))])
    return d, ps, buf


def _kpis(items, width, theme):
    st = _styles(theme)
    gap = 3 * mm
    cw = (width - gap * (len(items) - 1)) / len(items)
    cells = []
    accents = {"primary": theme["primary"], "secondary": theme["secondary"], "accent": theme["accent"]}
    for label, value, note, accent in items:
        metric = ParagraphStyle(f"metric_{label}", parent=st["metric"], textColor=accents.get(accent, theme["primary"]))
        cells.append(Table([[_P(label.upper(), st["label"])], [_P(value, metric)], [_P(note, st["small"])]], colWidths=[cw], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), .7, BORDER),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, accents.get(accent, theme["primary"])),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
            ("TOPPADDING", (0, 1), (-1, 1), 2), ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
            ("TOPPADDING", (0, 2), (-1, 2), 1), ("BOTTOMPADDING", (0, 2), (-1, 2), 7),
        ])))
    return Table([cells], colWidths=[cw] * len(items), style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), gap)]))


def _bar(label, value, max_value, note, accent, width, theme):
    st = _styles(theme)
    pct = max(0, min(100, (value / max_value * 100) if max_value else 0))
    bw = width * .66
    fill = bw * pct / 100
    if value and fill < 1.5 * mm:
        fill = 1.5 * mm
    remain = max(.1 * mm, bw - fill)
    bar = Table([["", ""]], colWidths=[fill or .1 * mm, remain], rowHeights=[5.5 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), accent), ("BACKGROUND", (1, 0), (1, 0), TRACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return Table([[_P(label, st["cardtitle"]), _P(f"{value}%", st["metric"])], [bar, ""], [_P(note, st["small"]), ""]], colWidths=[width - 30 * mm, 30 * mm], style=TableStyle([
        ("SPAN", (0, 1), (-1, 1)), ("SPAN", (0, 2), (-1, 2)), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))


def _card(title, lines, width, theme, accent=None):
    st = _styles(theme)
    body = [[_P(title, st["cardtitle"])]] + [[_P(a, st["small"]), _P(b, st["small"])] for a, b in lines]
    return Table(body, colWidths=[width * .58, width * .42], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), theme["soft"]), ("LINEBEFORE", (0, 0), (0, -1), 2.5, accent or theme["primary"]),
        ("BOX", (0, 0), (-1, -1), .6, BORDER), ("SPAN", (0, 0), (-1, 0)),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))


def _banner(title, subtitle, width, theme):
    st = _styles(theme)
    return Table([[_P(title.upper(), st["white"]), _P(subtitle, st["small"])]], colWidths=[width * .30, width * .70], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), theme["primary"]), ("BACKGROUND", (1, 0), (1, 0), theme["soft"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), .6, BORDER),
    ]))


def _intro(st, title, subtitle, filters):
    return [Spacer(1, 3 * mm), _P(title, st["title"]), _P(subtitle, st["subtitle"]), Spacer(1, 2 * mm), _P(f"Generated {_fmt(datetime.now())} · Filters: {filters or 'All records'}", st["small"]), Spacer(1, 5 * mm)]


def build_pdf(report_type, *, summary, rows, filters, completed_projects=None):
    titles = {
        "project_status": ("Project Status Report", "Portfolio health, delivery progress and schedule exposure."),
        "competency": ("Competency Report", "Workforce proficiency, project requirements and development gaps."),
        "learning_progress": ("Learning Progress Report", "Learning activity, development progress and completion."),
        "workforce": ("Workforce Summary", "Team capacity, competency coverage and development needs."),
        "delivery_performance": ("Delivery Performance Report", "Delivery speed, deadline reliability and completed project performance."),
    }
    title, subtitle = titles[report_type]
    theme = _theme(report_type)
    doc, ps, buf = _doc(title, theme)
    st = _styles(theme)
    W = ps[0] - 28 * mm
    story = _intro(st, title, subtitle, filters)

    if report_type == "project_status":
        story += [_kpis([("Projects", summary["projects"], "Filtered projects", "primary"), ("Active", summary["active"], "Currently active", "secondary"), ("Completed", summary["completed"], "Completed projects", "accent"), ("Avg Progress", f"{summary['avg_progress']}%", "Task completion", "primary")], W, theme), Spacer(1, 5 * mm), _banner("Portfolio Health", "Visual distribution of project delivery states.", W, theme), Spacer(1, 3 * mm)]
        total = summary["projects"] or 1
        for label, key, accent in [("Active", "active", theme["secondary"]), ("Completed", "completed", theme["primary"]), ("On Hold", "on_hold", theme["accent"])]:
            story.append(_bar(label, round(summary[key] * 100 / total), 100, f"{summary[key]} projects", accent, W, theme))
        story += [Spacer(1, 4 * mm), _P("Project Portfolio", st["section"])]
        for r in rows:
            story += [KeepTogether([_card(r["project"], [("Manager", r["manager"]), ("Status", r["status"]), ("Progress", f"{r['progress']}%"), ("Tasks", f"{r['done']} / {r['total_tasks']}"), ("Target", _fmt(r["target_date"])), ("Next Deadline", _fmt(r["next_deadline"]))], W, theme)]), Spacer(1, 3 * mm)]

    elif report_type == "competency":
        story += [_kpis([("Employees", summary["employees"], "Shown in results", "primary"), ("Requirements", summary["requirements"], "Active project targets", "secondary"), ("Open Gaps", summary["open_gaps"], "Gap or not assessed", "accent"), ("Coverage", f"{summary['coverage']}%", "Requirements met", "primary")], W, theme), Spacer(1, 5 * mm), _banner("Capability Coverage", "Current readiness against active project requirements.", W, theme), Spacer(1, 3 * mm), _bar("Requirements met", summary["coverage"], 100, "Current coverage", theme["secondary"], W, theme), _bar("Open or unassessed", 100 - summary["coverage"], 100, "Development attention", theme["accent"], W, theme), Spacer(1, 4 * mm), _P("Competency Review", st["section"])]
        for r in rows:
            story += [_card(r["skill"], [("Employee", r["employee"]), ("Team / Position", f"{r['team']} · {r['position']}"), ("Current", f"Level {r['current']}" if r["current"] is not None else "Not Assessed"), ("Project Target", f"Level {r['target']}" if r["target"] is not None else "—"), ("Gap", r["gap"] if r["gap"] is not None else "—"), ("Status", r["status"]), ("Required By", r["required_by"]), ("Last Assessed", _fmt(r["assessed_on"]))], W, theme), Spacer(1, 3 * mm)]

    elif report_type == "learning_progress":
        story += [_kpis([("Activities", summary["total"], "Filtered records", "primary"), ("Recommended", summary["recommended"], "Not started", "secondary"), ("In Progress", summary["in_progress"], "Currently learning", "accent"), ("Completed", summary["completed"], f"{summary['completion']}% completion", "primary")], W, theme), Spacer(1, 5 * mm), _banner("Learning Activity", "Visual distribution of development activity.", W, theme), Spacer(1, 3 * mm)]
        total = summary["total"] or 1
        for label, key, accent in [("Recommended", "recommended", theme["secondary"]), ("In Progress", "in_progress", theme["accent"]), ("Completed", "completed", theme["primary"])]:
            story.append(_bar(label, round(summary[key] * 100 / total), 100, f"{summary[key]} activities", accent, W, theme))
        story += [Spacer(1, 4 * mm), _P("Learning Portfolio", st["section"])]
        for r in rows:
            story += [_card(r["resource"], [("Employee", r["employee"]), ("Team", r["team"]), ("Skill", r["skill"]), ("Provider / Access", f"{r['provider']} · {r['access']}"), ("Status", r["status"]), ("Gap", "Assessment Needed" if r["gap"] is None else f"{r['gap']} level(s)"), ("Recommended", _fmt(r["created_at"])), ("Completed", _fmt(r["completed_at"]))], W, theme), Spacer(1, 3 * mm)]

    elif report_type == "workforce":
        story += [_kpis([("Teams", summary["teams"], "Included teams", "primary"), ("Members", summary["members"], "Employees represented", "secondary"), ("Requirements", summary["requirements"], "Active targets", "primary"), ("Open Gaps", summary["gaps"], "Development needs", "accent")], W, theme), Spacer(1, 5 * mm), _banner("Team Readiness", "Team-level coverage and development activity.", W, theme), Spacer(1, 3 * mm)]
        for r in rows:
            story += [KeepTogether([_bar(r["team"], r["coverage"], 100, f"{r['members']} members · {r['requirements']} requirements · {r['gaps']} gaps", theme["secondary"], W, theme), _card("Team Development", [("Projects", r["projects"]), ("Learning In Progress", r["in_progress"]), ("Learning Completed", r["completed"]), ("Coverage", f"{r['coverage']}%")], W, theme)]), Spacer(1, 4 * mm)]

    elif report_type == "delivery_performance":
        fastest = summary.get("fastest")
        story += [_kpis([("Completed Tasks", summary["completed_tasks"], "Included metrics", "primary"), ("Employees Tracked", summary["employees"], f"{summary['ranked_employees']} ranked · {summary['limited_employees']} limited", "secondary"), ("On-Time Rate", f"{summary['on_time_rate']}%" if summary["on_time_rate"] is not None else "—", "Recorded due dates", "primary"), ("Fastest Qualified", fastest["avg_label"] if fastest else "—", fastest["employee"].full_name if fastest else "No qualified sample", "accent")], W, theme), Spacer(1, 5 * mm), _banner("Delivery Performance", "Employee delivery speed and deadline reliability.", W, theme), Spacer(1, 3 * mm)]
        if fastest:
            story.append(_card("Fastest Qualified", [("Average Completion", fastest["avg_label"]), ("Employee", fastest["employee"].full_name)], W, theme, theme["accent"]))
            story.append(Spacer(1, 4 * mm))
        for r in rows:
            story += [_card(r["employee"].full_name, [("Team / Position", f"{r['employee'].team or 'Unassigned'} · {r['employee'].position or '—'}"), ("Rank", f"#{r['rank']}" if r["ranking_eligible"] else "Limited Sample"), ("Completed", r["completed"]), ("Average Completion", r["avg_label"]), ("Fastest Task", r["fastest_label"]), ("On Time / Late", f"{r['on_time']} / {r['late']}"), ("On-Time Rate", f"{r['on_time_rate']}%" if r["on_time_rate"] is not None else "No due dates")], W, theme, theme["secondary"]), Spacer(1, 3 * mm)]
        if completed_projects:
            story.append(_P("Completed Project Delivery", st["section"]))
            for r in completed_projects:
                story += [_card(r["project"].name, [("Manager", r["project"].manager.full_name if r["project"].manager else "—"), ("Delivery", f"{r['delivery_days']} days" if r["delivery_days"] is not None else "—"), ("Status", r["delivery_status"]), ("Completed", _fmt(r["project"].completed_at))], W, theme), Spacer(1, 3 * mm)]

    doc.build(story)
    return buf.getvalue()


def render_pdf(report_type, **kwargs):
    return build_pdf(report_type, **kwargs)
