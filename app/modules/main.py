"""Main / landing / dashboard routes."""
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ..models import (
    db, User, Project, Task, Employee, CompetencyAssessment,
    LearningRecommendation,
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    # KPI counts shown to all authenticated users (scoped by role where relevant)
    total_projects = Project.query.count()
    active_projects = Project.query.filter_by(status="Active").count()
    total_employees = Employee.query.count()
    open_tasks = Task.query.filter(Task.status != "Done").count()
    pending_recs = LearningRecommendation.query.filter_by(status="Recommended").count()

    # Task status distribution for chart
    statuses = ["Backlog", "To Do", "In Progress", "In Review", "Done"]
    task_dist = {s: Task.query.filter_by(status=s).count() for s in statuses}

    # Competency coverage: avg proficiency vs required across assessments
    assessments = CompetencyAssessment.query.all()
    gap_count = sum(1 for a in assessments if a.gap > 0)
    coverage = round(100 * (1 - gap_count / len(assessments)), 1) if assessments else 0

    # Per-team competency coverage (for manager/admin)
    from sqlalchemy import func
    teams = db.session.query(Employee.team).distinct().all()
    team_coverage = []
    for (team,) in teams:
        if not team:
            continue
        emps = Employee.query.filter_by(team=team).all()
        emp_ids = [e.id for e in emps]
        a = CompetencyAssessment.query.filter(CompetencyAssessment.employee_id.in_(emp_ids)).all()
        gaps = sum(1 for x in a if x.gap > 0)
        cov = round(100 * (1 - gaps / len(a)), 1) if a else 0
        team_coverage.append({"team": team, "coverage": cov, "employees": len(emps)})

    return render_template(
        "dashboard.html",
        total_projects=total_projects,
        active_projects=active_projects,
        total_employees=total_employees,
        open_tasks=open_tasks,
        pending_recs=pending_recs,
        task_dist=task_dist,
        coverage=coverage,
        team_coverage=team_coverage,
        role=current_user.role,
    )
