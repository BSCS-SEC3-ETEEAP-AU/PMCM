"""Sprint 4 - Reports and Dashboard Module.

Project status reports, competency reports, and summarized dashboards with
filters (project / employee / team / date) and an audit trail (ReportLog).
Manager/Admin access (thesis Fig. 8).
"""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from ..models import (
    db, Project, Task, Employee, CompetencyAssessment, LearningRecommendation,
    ReportLog, User,
)
from ..decorators import manager_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
@manager_required
def index():
    projects = Project.query.order_by(Project.name).all()
    employees = Employee.query.order_by(Employee.full_name).all()
    return render_template("reports/index.html", projects=projects, employees=employees)


@reports_bp.route("/project-status")
@manager_required
def project_status():
    project_id = request.args.get("project_id", type=int)
    projects = Project.query.order_by(Project.name).all()
    selected = None
    rows = []
    if project_id:
        selected = Project.query.get_or_404(project_id)
        tasks = Task.query.filter_by(project_id=project_id).all()
        total = len(tasks)
        done = sum(1 for t in tasks if t.status == "Done")
        by_status = {}
        for t in tasks:
            by_status[t.status] = by_status.get(t.status, 0) + 1
        rows = [{
            "project": selected.name,
            "total_tasks": total,
            "done": done,
            "progress": round(100 * done / total) if total else 0,
            "by_status": by_status,
            "status": selected.status,
        }]
        _log("Project Status Report", f"project_id={project_id}")
    else:
        for p in projects:
            tasks = Task.query.filter_by(project_id=p.id).all()
            total = len(tasks)
            done = sum(1 for t in tasks if t.status == "Done")
            rows.append({
                "project": p.name, "total_tasks": total, "done": done,
                "progress": round(100 * done / total) if total else 0,
                "status": p.status, "by_status": {},
            })
        _log("Project Status Report", "all projects")
    return render_template(
        "reports/project_status.html", projects=projects,
        selected=selected, rows=rows,
    )


@reports_bp.route("/competency")
@manager_required
def competency_report():
    team = request.args.get("team", "")
    employees = Employee.query.all()
    if team:
        employees = [e for e in employees if e.team == team]
    rows = []
    for e in employees:
        a = CompetencyAssessment.query.filter_by(employee_id=e.id).all()
        gaps = sum(1 for x in a if x.gap > 0)
        cov = round(100 * (1 - gaps / len(a)), 1) if a else 0
        rows.append({
            "employee": e.full_name, "team": e.team, "position": e.position,
            "assessed": len(a), "gaps": gaps, "coverage": cov,
        })
    teams = sorted({e.team for e in Employee.query.all() if e.team})
    _log("Competency Report", f"team={team or 'all'}")
    return render_template(
        "reports/competency.html", rows=rows, teams=teams, selected_team=team,
    )


def _log(report_type, filters):
    db.session.add(ReportLog(
        user_id=current_user.id, report_type=report_type, filters=filters,
    ))
    db.session.commit()
