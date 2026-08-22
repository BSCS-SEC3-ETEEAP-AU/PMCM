"""Sprint 2 - Employee Competency Development Module.

Manages competency profiles, skills, certifications, competency assessments,
and gap analysis (thesis Fig. 6). Employees complete assessments; the system
computes current vs required gaps that feed the recommendation engine.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import date
from ..models import (
    db, Employee, Skill, Certification, CompetencyAssessment, User,
)
from ..decorators import manager_required, admin_required
from ..competency_rules import active_project_requirements

competency_bp = Blueprint("competency", __name__, url_prefix="/competency")


def _current_employee():
    """Return the Employee profile linked to the signed-in user, if any."""
    return Employee.query.filter_by(user_id=current_user.id).first()


def _enforce_employee_scope(employee_id):
    """Allow Admin/Manager to access any profile; Employee only their own."""
    if current_user.role in ("admin", "manager"):
        return
    if current_user.role == "employee":
        emp = _current_employee()
        if emp and emp.id == employee_id:
            return
    abort(403)


@competency_bp.route("/me")
@login_required
def my_profile():
    """Open the competency profile linked to the signed-in user, regardless of role."""
    emp = _current_employee()
    if not emp:
        flash("No competency profile is linked to your account.", "warning")
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("competency.employee_profile", employee_id=emp.id))


@competency_bp.route("/overview")
@manager_required
def overview():
    """Manager-facing competency overview using active project targets."""
    employees = Employee.query.order_by(Employee.full_name).all()
    assessments = CompetencyAssessment.query.all()
    certifications = Certification.query.all()

    assessments_by_employee = {}
    for assessment in assessments:
        assessments_by_employee.setdefault(assessment.employee_id, []).append(assessment)

    certifications_by_employee = {}
    for certification in certifications:
        certifications_by_employee[certification.employee_id] = (
            certifications_by_employee.get(certification.employee_id, 0) + 1
        )

    rows = []
    assessed_employees = 0
    employees_with_gaps = 0
    total_gaps = 0

    for employee in employees:
        employee_assessments = assessments_by_employee.get(employee.id, [])
        assessment_map = {assessment.skill_id: assessment for assessment in employee_assessments}
        requirements = active_project_requirements(employee.id)
        assessed_count = len(employee_assessments)
        gap_count = 0
        meets_target = 0
        unassessed_required = 0

        for skill_id, requirement in requirements.items():
            assessment = assessment_map.get(skill_id)
            target = requirement["required_level"]
            if not assessment:
                unassessed_required += 1
            elif assessment.current_level >= target:
                meets_target += 1
            else:
                gap_count += 1

        required_count = len(requirements)
        coverage = round((meets_target / required_count) * 100) if required_count else None

        if assessed_count:
            assessed_employees += 1
        if gap_count:
            employees_with_gaps += 1
        total_gaps += gap_count

        if unassessed_required:
            status = "Assessment Needed"
        elif gap_count:
            status = "Has Gaps"
        elif required_count:
            status = "Meets Target"
        else:
            status = "No Active Targets"

        rows.append({
            "employee": employee,
            "competencies": assessed_count,
            "gaps": gap_count,
            "coverage": coverage,
            "certifications": certifications_by_employee.get(employee.id, 0),
            "required": required_count,
            "unassessed_required": unassessed_required,
            "status": status,
        })

    summary = {
        "team_members": len(employees),
        "assessed_employees": assessed_employees,
        "employees_with_gaps": employees_with_gaps,
        "total_gaps": total_gaps,
        "certifications": len(certifications),
    }

    return render_template(
        "competency/overview.html",
        rows=rows,
        summary=summary,
    )


@competency_bp.route("/employees")
@login_required
def list_employees():
    # Employees should not receive an organization-wide employee directory here.
    if current_user.role == "employee":
        return redirect(url_for("competency.my_profile"))
    if current_user.role not in ("admin", "manager"):
        abort(403)

    employees = Employee.query.order_by(Employee.full_name).all()
    return render_template("competency/employees.html", employees=employees)


@competency_bp.route("/employees/<int:employee_id>")
@login_required
def employee_profile(employee_id):
    _enforce_employee_scope(employee_id)
    emp = Employee.query.get_or_404(employee_id)
    certs = Certification.query.filter_by(employee_id=employee_id).order_by(Certification.issued_date.desc()).all()
    assessments = CompetencyAssessment.query.filter_by(employee_id=employee_id).all()
    assessment_map = {assessment.skill_id: assessment for assessment in assessments}
    requirements = active_project_requirements(employee_id)
    skills = Skill.query.order_by(Skill.name).all()

    competency_rows = []
    for skill in skills:
        assessment = assessment_map.get(skill.id)
        requirement = requirements.get(skill.id)
        if not assessment and not requirement:
            continue
        target = requirement["required_level"] if requirement else None
        gap = None if not assessment or target is None else max(0, target - assessment.current_level)
        competency_rows.append({
            "skill": skill,
            "assessment": assessment,
            "target": target,
            "gap": gap,
            "projects": requirement["projects"] if requirement else [],
            "tasks": requirement["tasks"] if requirement else [],
        })

    required_count = len(requirements)
    meets_target = sum(
        1 for row in competency_rows
        if row["target"] is not None and row["assessment"] and row["assessment"].current_level >= row["target"]
    )
    gaps = sum(1 for row in competency_rows if row["gap"] is not None and row["gap"] > 0)
    unassessed_required = sum(
        1 for row in competency_rows if row["target"] is not None and not row["assessment"]
    )
    assessment_summary = {
        "total": len(assessments),
        "required": required_count,
        "gaps": gaps,
        "unassessed_required": unassessed_required,
        "meets_target": meets_target,
        "high": sum(1 for assessment in assessments if assessment.current_level >= 4),
        "coverage": round(100 * meets_target / required_count) if required_count else None,
    }
    return render_template(
        "competency/profile.html",
        emp=emp, certs=certs, assessments=assessments, skills=skills,
        competency_rows=competency_rows, assessment_summary=assessment_summary,
    )


@competency_bp.route("/employees/<int:employee_id>/assess", methods=["GET", "POST"])
@login_required
def assess(employee_id):
    """Record current proficiency while project work supplies target levels."""
    _enforce_employee_scope(employee_id)
    emp = Employee.query.get_or_404(employee_id)
    skills = Skill.query.order_by(Skill.name).all()
    assessments = CompetencyAssessment.query.filter_by(employee_id=employee_id).all()
    assessment_map = {assessment.skill_id: assessment for assessment in assessments}
    requirements = active_project_requirements(employee_id)

    if request.method == "POST":
        saved = 0
        for skill in skills:
            raw_current = (request.form.get(f"current_{skill.id}") or "").strip()
            existing = assessment_map.get(skill.id)
            requirement = requirements.get(skill.id)

            if not raw_current:
                if existing:
                    existing.required_level = (
                        requirement["required_level"] if requirement else existing.current_level
                    )
                continue

            try:
                current_level = int(raw_current)
            except ValueError:
                flash(f"Select a valid proficiency level for {skill.name}.", "warning")
                return redirect(url_for("competency.assess", employee_id=employee_id))
            if current_level not in range(1, 6):
                flash(f"Proficiency for {skill.name} must be between Level 1 and Level 5.", "warning")
                return redirect(url_for("competency.assess", employee_id=employee_id))

            target_level = requirement["required_level"] if requirement else current_level
            notes = request.form.get(f"notes_{skill.id}", "").strip()
            if existing:
                existing.current_level = current_level
                existing.required_level = target_level
                existing.notes = notes
                existing.assessed_on = date.today()
            else:
                db.session.add(CompetencyAssessment(
                    employee_id=employee_id, skill_id=skill.id,
                    current_level=current_level, required_level=target_level,
                    assessed_on=date.today(), notes=notes,
                ))
            saved += 1

        db.session.commit()
        if saved:
            flash("Competency assessment saved. Project targets were applied automatically.", "success")
        else:
            flash("No proficiency changes were submitted.", "info")
        return redirect(url_for("competency.employee_profile", employee_id=employee_id))

    required_items = []
    optional_items = []
    for skill in skills:
        assessment = assessment_map.get(skill.id)
        requirement = requirements.get(skill.id)
        target = requirement["required_level"] if requirement else None
        item = {
            "skill": skill,
            "assessment": assessment,
            "target": target,
            "gap": None if not assessment or target is None else max(0, target - assessment.current_level),
            "projects": requirement["projects"] if requirement else [],
            "tasks": requirement["tasks"] if requirement else [],
        }
        if requirement:
            required_items.append(item)
        else:
            optional_items.append(item)

    return render_template(
        "competency/assess.html", emp=emp,
        required_items=required_items, optional_items=optional_items,
    )


@competency_bp.route("/employees/<int:employee_id>/cert/add", methods=["POST"])
@login_required
def add_cert(employee_id):
    _enforce_employee_scope(employee_id)
    emp = Employee.query.get_or_404(employee_id)
    name = request.form.get("name", "").strip()
    if name:
        db.session.add(Certification(
            employee_id=employee_id,
            name=name,
            issuer=request.form.get("issuer", ""),
            issued_date=_date(request.form.get("issued_date")),
            expiry_date=_date(request.form.get("expiry_date")),
        ))
        db.session.commit()
        flash("Certification recorded.", "success")
    return redirect(url_for("competency.employee_profile", employee_id=employee_id))


@competency_bp.route("/skills")
@manager_required
def list_skills():
    skills = Skill.query.order_by(Skill.category, Skill.name).all()
    return render_template("competency/skills.html", skills=skills)


@competency_bp.route("/skills/add", methods=["POST"])
@admin_required
def add_skill():
    name = request.form.get("name", "").strip()
    if name:
        db.session.add(Skill(
            name=name,
            category=request.form.get("category", "Technical"),
            description=request.form.get("description", ""),
        ))
        db.session.commit()
        flash("Skill added to catalog.", "success")
    return redirect(url_for("competency.list_skills"))


@competency_bp.route("/gap-report")
@manager_required
def gap_report():
    """Organization-wide gap analysis against active project/task requirements."""
    rows = []
    employees = Employee.query.order_by(Employee.full_name).all()
    for employee in employees:
        assessment_map = {
            assessment.skill_id: assessment
            for assessment in CompetencyAssessment.query.filter_by(employee_id=employee.id).all()
        }
        requirements = active_project_requirements(employee.id)
        if not requirements:
            continue
        skills = {skill.id: skill for skill in Skill.query.filter(Skill.id.in_(list(requirements))).all()}
        for skill_id, requirement in requirements.items():
            assessment = assessment_map.get(skill_id)
            target = requirement["required_level"]
            rows.append({
                "employee": employee.full_name,
                "team": employee.team,
                "skill": skills[skill_id].name if skill_id in skills else "Unknown skill",
                "current": assessment.current_level if assessment else None,
                "required": target,
                "gap": max(0, target - assessment.current_level) if assessment else None,
                "projects": requirement["projects"],
            })
    rows.sort(key=lambda row: (row["gap"] is None, -(row["gap"] or 0), row["employee"], row["skill"]))
    return render_template("competency/gap_report.html", rows=rows)


def _date(v):
    from datetime import datetime
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return None
