"""Sprint 4 - Reports and Dashboard Module.

Project status, competency, learning progress and workforce summary reports with
managerial filters, CSV export and an audit trail (ReportLog). Reports reuse the
same project-driven competency rules used by competency profiles and the
recommendation engine so values stay synchronized across modules.
"""
import csv
from datetime import date, datetime
from io import StringIO

from flask import Blueprint, Response, render_template, request
from flask_login import current_user

from ..competency_rules import active_project_requirements
from ..decorators import manager_required
from ..models import (
    db, Project, ProjectMember, Task, Milestone, Employee, Skill,
    CompetencyAssessment, LearningRecommendation, ReportLog, User,
)

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _assessment_lookup():
    """Return the latest stored assessment per employee/skill pair."""
    lookup = {}
    assessments = CompetencyAssessment.query.order_by(
        CompetencyAssessment.assessed_on.desc(), CompetencyAssessment.id.desc()
    ).all()
    for assessment in assessments:
        lookup.setdefault((assessment.employee_id, assessment.skill_id), assessment)
    return lookup


def _date_arg(name):
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _report_query_params(exclude=("export",)):
    parts = []
    for key in sorted(request.args.keys()):
        if key in exclude:
            continue
        value = (request.args.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts) or "all"


def _csv_response(filename_prefix, headers, rows):
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    filename = f"{filename_prefix}_{date.today().isoformat()}.csv"
    # UTF-8 BOM helps Excel display names/text correctly without extra import steps.
    body = "\ufeff" + stream.getvalue()
    return Response(
        body,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _log(report_type, filters):
    db.session.add(ReportLog(
        user_id=current_user.id, report_type=report_type, filters=filters,
    ))
    db.session.commit()


@reports_bp.route("/")
@manager_required
def index():
    projects = Project.query.order_by(Project.name).all()
    employees = Employee.query.order_by(Employee.full_name).all()
    recommendations = LearningRecommendation.query.all()
    assessment_lookup = _assessment_lookup()

    total_projects = len(projects)
    active = sum(1 for project in projects if project.status == "Active")
    completed = sum(1 for project in projects if project.status == "Completed")
    on_hold = sum(1 for project in projects if project.status == "On Hold")
    completed_learning = sum(1 for rec in recommendations if rec.status == "Completed")

    requirement_cache = {employee.id: active_project_requirements(employee.id) for employee in employees}
    gap_count = 0
    team_requirement_stats = {}
    for employee in employees:
        stats = team_requirement_stats.setdefault(employee.team or "Unassigned", {"required": 0, "met": 0, "gaps": 0})
        for skill_id, requirement in requirement_cache[employee.id].items():
            stats["required"] += 1
            assessment = assessment_lookup.get((employee.id, skill_id))
            if assessment and assessment.current_level >= requirement["required_level"]:
                stats["met"] += 1
            else:
                stats["gaps"] += 1
                gap_count += 1

    report_summary = {
        "total_projects": total_projects,
        "team_members": len(employees),
        "gap_count": gap_count,
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
    for team in sorted(team_requirement_stats):
        stats = team_requirement_stats[team]
        required = stats["required"]
        coverage = round(100 * stats["met"] / required) if required else 0
        team_coverage.append({
            "team": team,
            "assessed": required,
            "gaps": stats["gaps"],
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
    status = (request.args.get("status") or "").strip()
    manager_id = request.args.get("manager_id", type=int)
    search = (request.args.get("q") or "").strip().lower()
    date_from = _date_arg("date_from")
    date_to = _date_arg("date_to")

    projects = Project.query.order_by(Project.name).all()
    managers = User.query.filter(User.role.in_(("admin", "manager"))).order_by(User.full_name).all()
    filtered = projects
    if project_id:
        filtered = [project for project in filtered if project.id == project_id]
    if status:
        filtered = [project for project in filtered if project.status == status]
    if manager_id:
        filtered = [project for project in filtered if project.manager_id == manager_id]
    if search:
        filtered = [
            project for project in filtered
            if search in (project.name or "").lower()
            or search in ((project.manager.full_name if project.manager else "") or "").lower()
        ]
    # The date filter represents the project target/deadline range.
    if date_from:
        filtered = [project for project in filtered if project.target_date and project.target_date >= date_from]
    if date_to:
        filtered = [project for project in filtered if project.target_date and project.target_date <= date_to]

    rows = []
    for project in filtered:
        tasks = Task.query.filter_by(project_id=project.id).all()
        milestones = Milestone.query.filter_by(project_id=project.id).all()
        total = len(tasks)
        done = sum(1 for task in tasks if (task.status or "").lower() == "done")
        open_milestones = [milestone for milestone in milestones if not milestone.achieved]
        milestone_dates = [milestone.due_date for milestone in open_milestones if milestone.due_date]
        next_deadline = min(milestone_dates) if milestone_dates else project.target_date
        rows.append({
            "project": project.name,
            "manager": project.manager.full_name if project.manager else "—",
            "status": project.status,
            "start_date": project.start_date,
            "target_date": project.target_date,
            "total_tasks": total,
            "done": done,
            "progress": round(100 * done / total) if total else 0,
            "open_milestones": len(open_milestones),
            "next_deadline": next_deadline,
        })

    summary = {
        "projects": len(rows),
        "active": sum(1 for row in rows if row["status"] == "Active"),
        "completed": sum(1 for row in rows if row["status"] == "Completed"),
        "on_hold": sum(1 for row in rows if row["status"] == "On Hold"),
        "avg_progress": round(sum(row["progress"] for row in rows) / len(rows)) if rows else 0,
    }
    filters = _report_query_params()

    if request.args.get("export") == "csv":
        _log("Project Status Report CSV", filters)
        return _csv_response(
            "project_status_report",
            ["Project", "Manager", "Status", "Start Date", "Target Date", "Tasks", "Done", "Progress %", "Open Milestones", "Next Deadline"],
            [[
                row["project"], row["manager"], row["status"], row["start_date"] or "", row["target_date"] or "",
                row["total_tasks"], row["done"], row["progress"], row["open_milestones"], row["next_deadline"] or "",
            ] for row in rows],
        )

    _log("Project Status Report", filters)
    return render_template(
        "reports/project_status.html",
        projects=projects, managers=managers, rows=rows, summary=summary,
        selected_project_id=project_id, selected_status=status, selected_manager_id=manager_id,
        search=request.args.get("q", ""), date_from=date_from, date_to=date_to,
    )


@reports_bp.route("/competency")
@manager_required
def competency_report():
    team = (request.args.get("team") or "").strip()
    employee_id = request.args.get("employee_id", type=int)
    skill_id = request.args.get("skill_id", type=int)
    gap_status = (request.args.get("gap_status") or "").strip()
    search = (request.args.get("q") or "").strip().lower()
    date_from = _date_arg("date_from")
    date_to = _date_arg("date_to")

    all_employees = Employee.query.order_by(Employee.full_name).all()
    all_skills = Skill.query.order_by(Skill.name).all()
    skill_lookup = {skill.id: skill for skill in all_skills}
    assessment_lookup = _assessment_lookup()

    employees = all_employees
    if team:
        employees = [employee for employee in employees if employee.team == team]
    if employee_id:
        employees = [employee for employee in employees if employee.id == employee_id]

    rows = []
    for employee in employees:
        requirements = active_project_requirements(employee.id)
        assessed_skill_ids = {
            assessed_skill_id for (assessed_employee_id, assessed_skill_id) in assessment_lookup
            if assessed_employee_id == employee.id
        }
        for row_skill_id in sorted(set(requirements) | assessed_skill_ids, key=lambda sid: skill_lookup.get(sid).name if skill_lookup.get(sid) else ""):
            if skill_id and row_skill_id != skill_id:
                continue
            skill = skill_lookup.get(row_skill_id)
            if not skill:
                continue
            assessment = assessment_lookup.get((employee.id, row_skill_id))
            if date_from and (not assessment or not assessment.assessed_on or assessment.assessed_on < date_from):
                continue
            if date_to and (not assessment or not assessment.assessed_on or assessment.assessed_on > date_to):
                continue
            requirement = requirements.get(row_skill_id)
            target = requirement["required_level"] if requirement else None
            current = assessment.current_level if assessment else None
            if target is None:
                status_label = "No Active Target"
                gap = None
            elif current is None:
                status_label = "Not Assessed"
                gap = None
            elif current >= target:
                status_label = "Meets Target"
                gap = 0
            else:
                status_label = "Has Gap"
                gap = target - current

            normalized = {
                "Has Gap": "gap", "Meets Target": "met",
                "Not Assessed": "unassessed", "No Active Target": "no_target",
            }[status_label]
            if gap_status and normalized != gap_status:
                continue

            row = {
                "employee": employee.full_name,
                "team": employee.team or "—",
                "position": employee.position or "—",
                "skill": skill.name,
                "current": current,
                "target": target,
                "gap": gap,
                "status": status_label,
                "required_by": ", ".join(requirement["projects"]) if requirement else "—",
                "assessed_on": assessment.assessed_on if assessment else None,
            }
            if search and not any(search in str(row[field]).lower() for field in ("employee", "team", "position", "skill", "required_by")):
                continue
            rows.append(row)

    active_requirement_rows = [row for row in rows if row["target"] is not None]
    met_rows = [row for row in active_requirement_rows if row["status"] == "Meets Target"]
    open_rows = [row for row in active_requirement_rows if row["status"] in ("Has Gap", "Not Assessed")]
    summary = {
        "employees": len({row["employee"] for row in rows}),
        "requirements": len(active_requirement_rows),
        "open_gaps": len(open_rows),
        "coverage": round(100 * len(met_rows) / len(active_requirement_rows)) if active_requirement_rows else 0,
    }
    teams = sorted({employee.team for employee in all_employees if employee.team})
    filters = _report_query_params()

    if request.args.get("export") == "csv":
        _log("Competency Report CSV", filters)
        return _csv_response(
            "competency_report",
            ["Employee", "Team", "Position", "Skill", "Current Level", "Project Target", "Gap", "Status", "Required By", "Last Assessed"],
            [[
                row["employee"], row["team"], row["position"], row["skill"],
                row["current"] if row["current"] is not None else "Not Assessed",
                row["target"] if row["target"] is not None else "",
                row["gap"] if row["gap"] is not None else "",
                row["status"], row["required_by"], row["assessed_on"] or "",
            ] for row in rows],
        )

    _log("Competency Report", filters)
    return render_template(
        "reports/competency.html", rows=rows, teams=teams, employees=all_employees,
        skills=all_skills, summary=summary, selected_team=team,
        selected_employee_id=employee_id, selected_skill_id=skill_id,
        selected_gap_status=gap_status, search=request.args.get("q", ""), date_from=date_from, date_to=date_to,
    )


@reports_bp.route("/learning-progress")
@manager_required
def learning_progress():
    team = (request.args.get("team") or "").strip()
    employee_id = request.args.get("employee_id", type=int)
    skill_id = request.args.get("skill_id", type=int)
    status = (request.args.get("status") or "").strip()
    search = (request.args.get("q") or "").strip().lower()
    date_from = _date_arg("date_from")
    date_to = _date_arg("date_to")

    employees = Employee.query.order_by(Employee.full_name).all()
    skills = Skill.query.order_by(Skill.name).all()
    recs = LearningRecommendation.query.order_by(LearningRecommendation.created_at.desc()).all()
    rows = []
    for rec in recs:
        employee = rec.employee
        if not employee:
            continue
        if team and employee.team != team:
            continue
        if employee_id and employee.id != employee_id:
            continue
        if skill_id and rec.skill_id != skill_id:
            continue
        if status and rec.status != status:
            continue
        rec_date = rec.created_at.date() if rec.created_at else None
        if date_from and (not rec_date or rec_date < date_from):
            continue
        if date_to and (not rec_date or rec_date > date_to):
            continue
        row = {
            "employee": employee.full_name,
            "team": employee.team or "—",
            "resource": rec.resource.title if rec.resource else "—",
            "skill": rec.skill.name if rec.skill else "—",
            "provider": rec.resource.provider if rec.resource and rec.resource.provider else "—",
            "access": rec.resource.access_type if rec.resource and rec.resource.access_type else "—",
            "status": rec.status,
            "gap": rec.gap,
            "created_at": rec.created_at,
            "completed_at": rec.completed_at,
        }
        if search and not any(search in str(row[field]).lower() for field in ("employee", "team", "resource", "skill", "provider", "access")):
            continue
        rows.append(row)

    total = len(rows)
    recommended = sum(1 for row in rows if row["status"] == "Recommended")
    in_progress = sum(1 for row in rows if row["status"] == "In Progress")
    completed = sum(1 for row in rows if row["status"] == "Completed")
    summary = {
        "total": total,
        "recommended": recommended,
        "in_progress": in_progress,
        "completed": completed,
        "completion": round(100 * completed / total) if total else 0,
    }
    teams = sorted({employee.team for employee in employees if employee.team})
    filters = _report_query_params()

    if request.args.get("export") == "csv":
        _log("Learning Progress Report CSV", filters)
        return _csv_response(
            "learning_progress_report",
            ["Employee", "Team", "Learning Resource", "Skill", "Provider", "Access", "Status", "Competency Gap", "Recommended On", "Completed On"],
            [[
                row["employee"], row["team"], row["resource"], row["skill"], row["provider"], row["access"], row["status"],
                row["gap"], row["created_at"].date() if row["created_at"] else "",
                row["completed_at"].date() if row["completed_at"] else "",
            ] for row in rows],
        )

    _log("Learning Progress Report", filters)
    return render_template(
        "reports/learning_progress.html", rows=rows, employees=employees, teams=teams,
        skills=skills, summary=summary, selected_team=team,
        selected_employee_id=employee_id, selected_skill_id=skill_id,
        selected_status=status, search=request.args.get("q", ""), date_from=date_from, date_to=date_to,
    )


@reports_bp.route("/workforce-summary")
@manager_required
def workforce_summary():
    team = (request.args.get("team") or "").strip()
    search = (request.args.get("q") or "").strip().lower()
    employees = Employee.query.order_by(Employee.full_name).all()
    assessment_lookup = _assessment_lookup()
    teams = sorted({employee.team for employee in employees if employee.team})
    selected_teams = [team] if team else teams
    if search:
        selected_teams = [team_name for team_name in selected_teams if search in team_name.lower()]

    rows = []
    for team_name in selected_teams:
        team_employees = [employee for employee in employees if employee.team == team_name]
        employee_ids = {employee.id for employee in team_employees}
        required = 0
        met = 0
        gaps = 0
        for employee in team_employees:
            for skill_id, requirement in active_project_requirements(employee.id).items():
                required += 1
                assessment = assessment_lookup.get((employee.id, skill_id))
                if assessment and assessment.current_level >= requirement["required_level"]:
                    met += 1
                else:
                    gaps += 1

        project_ids = {
            member.project_id for member in ProjectMember.query.filter(ProjectMember.employee_id.in_(employee_ids)).all()
        } if employee_ids else set()
        recs = LearningRecommendation.query.filter(LearningRecommendation.employee_id.in_(employee_ids)).all() if employee_ids else []
        in_progress = sum(1 for rec in recs if rec.status == "In Progress")
        completed = sum(1 for rec in recs if rec.status == "Completed")
        rows.append({
            "team": team_name,
            "members": len(team_employees),
            "projects": len(project_ids),
            "requirements": required,
            "coverage": round(100 * met / required) if required else 0,
            "gaps": gaps,
            "in_progress": in_progress,
            "completed": completed,
        })

    summary = {
        "teams": len(rows),
        "members": sum(row["members"] for row in rows),
        "requirements": sum(row["requirements"] for row in rows),
        "gaps": sum(row["gaps"] for row in rows),
    }
    filters = _report_query_params()

    if request.args.get("export") == "csv":
        _log("Workforce Summary CSV", filters)
        return _csv_response(
            "workforce_summary",
            ["Team", "Members", "Projects Represented", "Active Skill Requirements", "Coverage %", "Open Gaps", "Learning In Progress", "Learning Completed"],
            [[
                row["team"], row["members"], row["projects"], row["requirements"], row["coverage"],
                row["gaps"], row["in_progress"], row["completed"],
            ] for row in rows],
        )

    _log("Workforce Summary", filters)
    return render_template(
        "reports/workforce.html", rows=rows, teams=teams, selected_team=team,
        search=request.args.get("q", ""), summary=summary,
    )
