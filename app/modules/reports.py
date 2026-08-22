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
    assessments = CompetencyAssessment.query.all()
    recommendations = LearningRecommendation.query.all()

    total_projects = len(projects)
    active = sum(1 for project in projects if project.status == "Active")
    completed = sum(1 for project in projects if project.status == "Completed")
    on_hold = sum(1 for project in projects if project.status == "On Hold")
    completed_learning = sum(1 for rec in recommendations if rec.status == "Completed")

    report_summary = {
        "total_projects": total_projects,
        "team_members": len(employees),
        "gap_count": sum(1 for assessment in assessments if assessment.gap > 0),
        "learning_completion": round(100 * completed_learning / len(recommendations)) if recommendations else 0,
    }
    project_status = {
        "active": active,
        "completed": completed,
        "on_hold": on_hold,
        "active_pct": round(100 * active / total_projects) if total_projects else 0,
        "completed_pct": round(100 * completed / total_projects) if total_projects else 0,
    }

    team_coverage = []
    for team in sorted({employee.team for employee in employees if employee.team}):
        team_employees = [employee for employee in employees if employee.team == team]
        team_employee_ids = {employee.id for employee in team_employees}
        team_assessments = [assessment for assessment in assessments if assessment.employee_id in team_employee_ids]
        gaps = sum(1 for assessment in team_assessments if assessment.gap > 0)
        assessed = len(team_assessments)
        coverage = round(100 * (assessed - gaps) / assessed) if assessed else 0
        team_coverage.append({
            "team": team,
            "assessed": assessed,
            "gaps": gaps,
            "coverage": coverage,
        })

    recent_reports = ReportLog.query.order_by(ReportLog.generated_at.desc()).limit(6).all()
    return render_template(
        "reports/index.html",
        projects=projects, employees=employees,
        report_summary=report_summary, project_status=project_status,
        team_coverage=team_coverage, recent_reports=recent_reports,
    )


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
