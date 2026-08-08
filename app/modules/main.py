"""Main / landing / dashboard routes."""
from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from ..models import Project, Task, Employee, CompetencyAssessment, Milestone, ProjectMember

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


def pct(part, whole):
    """Return a conventional rounded percentage."""
    if not whole:
        return 0
    return int(((part / whole) * 100) + 0.5)


def project_progress_pct(project_id):
    """Return progress percent for a project based on completed tasks."""
    total_tasks = Task.query.filter_by(project_id=project_id).count()
    if total_tasks == 0:
        return 0

    done_tasks = Task.query.filter_by(project_id=project_id, status="Done").count()
    return pct(done_tasks, total_tasks)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    employee_view = current_user.role == "employee"
    employee = None
    member_project_ids = []

    if employee_view:
        employee = Employee.query.filter_by(user_id=current_user.id).first()
        if employee:
            member_project_ids = [
                pm.project_id
                for pm in ProjectMember.query.filter_by(employee_id=employee.id).all()
            ]

    # ----- Shared datasets, scoped by role -----
    active_projects_query = Project.query.filter_by(status="Active")
    if employee_view:
        if member_project_ids:
            active_projects_query = active_projects_query.filter(Project.id.in_(member_project_ids))
        else:
            active_projects_query = active_projects_query.filter(Project.id == -1)

    active_projects = (
        active_projects_query
        .order_by(Project.target_date.asc(), Project.id.desc())
        .all()
    )
    active_project_ids = [project.id for project in active_projects]

    # ----- Top cards -----
    kpi_active_projects = len(active_projects)

    if employee_view:
        kpi_open_tasks = (
            Task.query.filter(Task.assignee_id == employee.id, Task.status != "Done").count()
            if employee else 0
        )
        kpi_team_members = (
            ProjectMember.query.with_entities(ProjectMember.employee_id)
            .filter(ProjectMember.project_id.in_(active_project_ids))
            .distinct()
            .count()
            if active_project_ids else 0
        )
        assessments = (
            CompetencyAssessment.query.filter_by(employee_id=employee.id).all()
            if employee else []
        )
    else:
        kpi_open_tasks = Task.query.filter(Task.status != "Done").count()
        kpi_team_members = Employee.query.count()
        assessments = CompetencyAssessment.query.all()

    kpi_gap_count = sum(1 for assessment in assessments if assessment.gap > 0)

    # ----- Task Per Project Progress (accessible active projects only) -----
    if active_project_ids:
        total_active_tasks = Task.query.filter(Task.project_id.in_(active_project_ids)).count()
        completed_tasks = Task.query.filter(
            Task.project_id.in_(active_project_ids),
            Task.status == "Done"
        ).count()
        in_progress_tasks = Task.query.filter(
            Task.project_id.in_(active_project_ids),
            Task.status.in_(["In Progress", "In Review"])
        ).count()
        not_started_tasks = Task.query.filter(
            Task.project_id.in_(active_project_ids),
            Task.status.in_(["Backlog", "To Do"])
        ).count()
    else:
        total_active_tasks = 0
        completed_tasks = 0
        in_progress_tasks = 0
        not_started_tasks = 0

    if total_active_tasks > 0:
        progress_overview = {
            "completed": pct(completed_tasks, total_active_tasks),
            "in_progress": pct(in_progress_tasks, total_active_tasks),
            "not_started": pct(not_started_tasks, total_active_tasks),
        }
        overall_pct = pct(completed_tasks, total_active_tasks)
    else:
        progress_overview = {
            "completed": 0,
            "in_progress": 0,
            "not_started": 0,
        }
        overall_pct = 0

    # ----- Tasks by Status -----
    task_query = Task.query
    if employee_view:
        if employee:
            task_query = task_query.filter(Task.assignee_id == employee.id)
        else:
            task_query = task_query.filter(Task.id == -1)

    todo_count = task_query.filter(Task.status.in_(["Backlog", "To Do"])).count()
    in_progress_count = task_query.filter(Task.status == "In Progress").count()
    in_review_count = task_query.filter(Task.status == "In Review").count()
    completed_count = task_query.filter(Task.status == "Done").count()

    task_bars = [
        {"label": "To Do", "count": todo_count},
        {"label": "In Progress", "count": in_progress_count},
        {"label": "In Review", "count": in_review_count},
        {"label": "Completed", "count": completed_count},
    ]

    max_bar_value = max((item["count"] for item in task_bars), default=0)
    task_bar_max = max(10, ((max_bar_value + 9) // 10) * 10) if max_bar_value else 10

    # ----- Active Projects table -----
    active_project_rows = []
    for project in active_projects[:5]:
        active_project_rows.append(
            {
                "id": project.id,
                "name": project.name,
                "manager": project.manager.full_name if project.manager else "—",
                "status": project.status,
                "progress": project_progress_pct(project.id),
                "target_date": project.target_date,
            }
        )

    # ----- Upcoming Deadlines (accessible active-project milestones only) -----
    upcoming_deadlines = []
    if active_project_ids:
        deadline_rows = (
            Milestone.query.filter_by(achieved=False)
            .filter(Milestone.project_id.in_(active_project_ids))
            .filter(Milestone.due_date >= date.today())
            .order_by(Milestone.due_date)
            .limit(3)
            .all()
        )

        project_lookup = {project.id: project for project in active_projects}
        for milestone in deadline_rows:
            project = project_lookup.get(milestone.project_id)
            upcoming_deadlines.append(
                {
                    "title": milestone.title,
                    "date": milestone.due_date,
                    "project": project.name if project else "",
                }
            )

    return render_template(
        "dashboard.html",
        employee_view=employee_view,
        kpi_active_projects=kpi_active_projects,
        kpi_open_tasks=kpi_open_tasks,
        kpi_team_members=kpi_team_members,
        kpi_gap_count=kpi_gap_count,
        progress_overview=progress_overview,
        overall_pct=overall_pct,
        task_bars=task_bars,
        task_bar_max=task_bar_max,
        active_project_rows=active_project_rows,
        upcoming_deadlines=upcoming_deadlines,
    )
