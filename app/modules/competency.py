"""Sprint 2 - Employee Competency Development Module.

Manages competency profiles, skills, certifications, competency assessments,
and gap analysis (thesis Fig. 6). Employees complete assessments; the system
computes current vs required gaps that feed the recommendation engine.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ..models import (
    db, Employee, Skill, Certification, CompetencyAssessment, User,
)
from ..decorators import manager_required, admin_required

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
    """Safe shortcut for employees to open their own competency profile."""
    emp = _current_employee()
    if not emp:
        flash("No competency profile is linked to your account.", "warning")
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("competency.employee_profile", employee_id=emp.id))


@competency_bp.route("/overview")
@manager_required
def overview():
    """Manager-facing competency overview for workforce development monitoring."""
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
        assessed_count = len(employee_assessments)
        gap_count = sum(1 for assessment in employee_assessments if assessment.gap > 0)
        meets_target = assessed_count - gap_count
        coverage = round((meets_target / assessed_count) * 100) if assessed_count else None

        if assessed_count:
            assessed_employees += 1
        if gap_count:
            employees_with_gaps += 1
        total_gaps += gap_count

        rows.append({
            "employee": employee,
            "competencies": assessed_count,
            "gaps": gap_count,
            "coverage": coverage,
            "certifications": certifications_by_employee.get(employee.id, 0),
            "status": (
                "Not Assessed" if assessed_count == 0
                else "Meets Target" if gap_count == 0
                else "Has Gaps"
            ),
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
    skills = Skill.query.order_by(Skill.name).all()
    total = len(assessments)
    gaps = sum(1 for assessment in assessments if assessment.gap > 0)
    meets_target = total - gaps
    assessment_summary = {
        "total": total,
        "gaps": gaps,
        "meets_target": meets_target,
        "high": sum(1 for assessment in assessments if assessment.current_level >= 4),
        "coverage": round(100 * meets_target / total) if total else 0,
    }
    return render_template(
        "competency/profile.html",
        emp=emp, certs=certs, assessments=assessments, skills=skills,
        assessment_summary=assessment_summary,
    )


@competency_bp.route("/employees/<int:employee_id>/assess", methods=["GET", "POST"])
@login_required
def assess(employee_id):
    """Employees complete their own assessment; Manager/Admin may record any."""
    _enforce_employee_scope(employee_id)
    emp = Employee.query.get_or_404(employee_id)
    skills = Skill.query.order_by(Skill.name).all()

    if request.method == "POST":
        for skill in skills:
            current_level = int(request.form.get(f"current_{skill.id}", 1))
            required_level = int(request.form.get(f"required_{skill.id}", 3))
            notes = request.form.get(f"notes_{skill.id}", "")
            existing = CompetencyAssessment.query.filter_by(
                employee_id=employee_id, skill_id=skill.id
            ).first()
            if existing:
                existing.current_level = current_level
                existing.required_level = required_level
                existing.notes = notes
            else:
                db.session.add(CompetencyAssessment(
                    employee_id=employee_id, skill_id=skill.id,
                    current_level=current_level, required_level=required_level,
                    notes=notes,
                ))
        db.session.commit()
        flash("Competency assessment saved.", "success")
        return redirect(url_for("competency.employee_profile", employee_id=employee_id))
    return render_template("competency/assess.html", emp=emp, skills=skills)


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
    """Organization-wide competency gap analysis for Manager/Admin."""
    assessments = CompetencyAssessment.query.all()
    rows = []
    for a in assessments:
        rows.append({
            "employee": a.employee.full_name,
            "team": a.employee.team,
            "skill": a.skill.name,
            "current": a.current_level,
            "required": a.required_level,
            "gap": a.gap,
        })
    rows.sort(key=lambda r: r["gap"], reverse=True)
    return render_template("competency/gap_report.html", rows=rows)


def _date(v):
    from datetime import datetime
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return None
