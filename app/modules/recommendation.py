"""Sprint 3 - Competency-Based Learning Recommendation Module.

Rule-based engine (thesis explicitly: NO AI/ML). Compares each employee's
competency gap (current vs required) against the Learning Resource Repository,
recommends resources that build the missing proficiency, and tracks completion
which then updates competency records.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..models import (
    db, Employee, Skill, CompetencyAssessment, LearningResource,
    LearningRecommendation,
)
from ..decorators import manager_required

recommendation_bp = Blueprint("recommendation", __name__, url_prefix="/recommend")


@recommendation_bp.route("/")
@login_required
def my_recommendations():
    """Employee view: their own recommendations."""
    if current_user.role == "employee":
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        if not emp:
            flash("No competency profile linked to your account.", "warning")
            return redirect(url_for("main.dashboard"))
        recs = LearningRecommendation.query.filter_by(employee_id=emp.id).all()
        return render_template("recommendation/list.html", recs=recs, own=True)
    # Manager/Admin: see all
    recs = LearningRecommendation.query.order_by(LearningRecommendation.gap.desc()).all()
    return render_template("recommendation/list.html", recs=recs, own=False)


@recommendation_bp.route("/generate", methods=["POST"])
@manager_required
def generate():
    """Run the rule-based recommendation process for all employees."""
    employees = Employee.query.all()
    resources = LearningResource.query.all()
    created = 0
    for emp in employees:
        # gather latest assessment per skill
        assessments = CompetencyAssessment.query.filter_by(employee_id=emp.id).all()
        for a in assessments:
            if a.gap > 0:
                # find resources that build toward the required level for this skill
                matched = [
                    r for r in resources
                    if r.skill_id == a.skill_id and r.target_level >= a.current_level + 1
                ]
                for r in matched:
                    exists = LearningRecommendation.query.filter_by(
                        employee_id=emp.id, resource_id=r.id
                    ).first()
                    if not exists:
                        db.session.add(LearningRecommendation(
                            employee_id=emp.id,
                            resource_id=r.id,
                            skill_id=a.skill_id,
                            gap=a.gap,
                            reason=(f"Gap of {a.gap} in {a.skill.name} "
                                    f"({a.current_level}→{a.required_level}). "
                                    f"Resource builds toward level {r.target_level}."),
                            status="Recommended",
                        ))
                        created += 1
    db.session.commit()
    flash(f"Recommendation engine ran. {created} new recommendation(s) generated.", "success")
    return redirect(url_for("recommendation.my_recommendations"))


@recommendation_bp.route("/<int:rec_id>/complete", methods=["POST"])
@login_required
def complete(rec_id):
    rec = LearningRecommendation.query.get_or_404(rec_id)
    # Employees complete their own; managers/admin may also mark
    if current_user.role == "employee":
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        if not emp or emp.id != rec.employee_id:
            flash("You can only update your own recommendations.", "warning")
            return redirect(url_for("recommendation.my_recommendations"))
    if rec.status != "Completed":
        rec.status = "Completed"
        from datetime import datetime
        rec.completed_at = datetime.utcnow()
        # Update competency: raise current_level one step toward required
        a = CompetencyAssessment.query.filter_by(
            employee_id=rec.employee_id, skill_id=rec.skill_id
        ).first()
        if a and a.current_level < a.required_level:
            a.current_level = min(a.required_level, a.current_level + 1)
        db.session.commit()
        flash("Recommendation marked complete; competency updated.", "success")
    return redirect(url_for("recommendation.my_recommendations"))


@recommendation_bp.route("/resources")
@manager_required
def list_resources():
    resources = LearningResource.query.order_by(LearningResource.skill_id).all()
    skills = Skill.query.order_by(Skill.name).all()
    return render_template("recommendation/resources.html", resources=resources, skills=skills)


@recommendation_bp.route("/resources/add", methods=["POST"])
@manager_required
def add_resource():
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(LearningResource(
            title=title,
            description=request.form.get("description", ""),
            skill_id=int(request.form.get("skill_id")),
            target_level=int(request.form.get("target_level", 3)),
            resource_type=request.form.get("resource_type", "Course"),
            url=request.form.get("url", ""),
        ))
        db.session.commit()
        flash("Learning resource added to repository.", "success")
    return redirect(url_for("recommendation.list_resources"))
