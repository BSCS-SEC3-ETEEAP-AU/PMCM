"""Sprint 3 - Competency-Based Learning Recommendation Module.

Rule-based engine (thesis explicitly: NO AI/ML). Active project/task competency
requirements are compared with recorded employee proficiency, matched against the
Learning Resource Repository, and tracked through Recommended -> In Progress ->
Completed. Learning completion is recorded as development history; competency
improvement is validated through a later competency assessment.
"""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..competency_rules import active_project_requirements
from ..decorators import manager_required
from ..models import (
    CompetencyAssessment,
    Employee,
    LearningRecommendation,
    LearningResource,
    Project,
    ProjectMember,
    Skill,
    db,
)

recommendation_bp = Blueprint("recommendation", __name__, url_prefix="/recommend")


def _linked_employee():
    """Return the employee profile linked to the signed-in account, when present."""
    return Employee.query.filter_by(user_id=current_user.id).first()


def _sorted_recommendations(recs):
    """Put active learning first while keeping completed items available as history."""
    status_rank = {"In Progress": 0, "Recommended": 1, "Completed": 2}
    return sorted(
        recs,
        key=lambda rec: (
            status_rank.get(rec.status, 9),
            -(rec.gap or 0),
            (rec.employee.full_name or "").lower(),
            (rec.resource.title or "").lower(),
            rec.id,
        ),
    )


def _enforce_own_learning(rec):
    """Learning progress can only be changed by the person who owns the record."""
    emp = _linked_employee()
    if not emp or emp.id != rec.employee_id:
        abort(403)
    return emp


def _refresh_recommendations(employee_ids):
    """Refresh recommendations only for the supplied employee profiles.

    Scoping the engine here keeps employee self-service safe: an employee can
    refresh their own recommendations without gaining permission to recalculate
    or clean up another employee's learning records.
    """
    employee_ids = sorted({int(employee_id) for employee_id in employee_ids if employee_id})
    if not employee_ids:
        return {"created": 0, "updated": 0, "removed": 0}

    employees = Employee.query.filter(Employee.id.in_(employee_ids)).all()
    resources = LearningResource.query.filter_by(is_active=True).all()
    skills = {skill.id: skill for skill in Skill.query.all()}
    valid_pairs = set()
    created = 0
    updated = 0
    removed = 0

    for emp in employees:
        assessment_map = {
            assessment.skill_id: assessment
            for assessment in CompetencyAssessment.query.filter_by(employee_id=emp.id).all()
        }
        requirements = active_project_requirements(emp.id)

        # When an employee has no active project requirements, use a broader
        # development-oriented recommendation pool. Assessed skills below Level 5
        # receive targeted resources, while skills without an assessment can still
        # surface learning resources without inventing a competency gap.
        if not requirements:
            active_project_count = (
                db.session.query(ProjectMember.project_id)
                .join(Project, Project.id == ProjectMember.project_id)
                .filter(
                    ProjectMember.employee_id == emp.id,
                    Project.status == "Active",
                )
                .count()
            )
            if active_project_count == 0:
                assessed_skill_ids = set(assessment_map)

                # First, recommend resources that can raise an assessed skill.
                for skill_id, assessment in assessment_map.items():
                    current_level = int(assessment.current_level or 0)
                    if current_level >= 5:
                        continue

                    matched = [
                        resource for resource in resources
                        if resource.skill_id == skill_id
                        and resource.target_level > current_level
                    ]
                    skill = assessment.skill or skills.get(skill_id)
                    if not skill:
                        continue

                    for resource in matched:
                        pair = (emp.id, resource.id, skill_id)
                        valid_pairs.add(pair)
                        gap = max(0, resource.target_level - current_level)
                        reason = (
                            f"No active project assignment. Strengthen {skill.name} "
                            f"from Level {current_level} toward Level {resource.target_level} "
                            "through this learning resource."
                        )
                        existing = (
                            LearningRecommendation.query
                            .filter_by(employee_id=emp.id, resource_id=resource.id, skill_id=skill_id)
                            .filter(LearningRecommendation.status != "Completed")
                            .order_by(LearningRecommendation.id)
                            .first()
                        )
                        if existing:
                            existing.gap = gap
                            existing.reason = reason
                            updated += 1
                        else:
                            db.session.add(LearningRecommendation(
                                employee_id=emp.id,
                                resource_id=resource.id,
                                skill_id=skill_id,
                                gap=gap,
                                reason=reason,
                                status="Recommended",
                            ))
                            created += 1

                # Then broaden the pool with resources for skills that have no
                # recorded assessment. These are intentionally shown as
                # "Assessment Needed" rather than using an invented gap.
                for resource in resources:
                    skill_id = resource.skill_id
                    if skill_id in assessed_skill_ids:
                        continue

                    skill = resource.skill or skills.get(skill_id)
                    if not skill:
                        continue

                    pair = (emp.id, resource.id, skill_id)
                    valid_pairs.add(pair)
                    reason = (
                        f"No active project assignment. Explore {skill.name} "
                        "to build this competency while you are available for development. "
                        f"This resource targets Level {resource.target_level}; assess your "
                        "proficiency to track your development gap."
                    )
                    existing = (
                        LearningRecommendation.query
                        .filter_by(employee_id=emp.id, resource_id=resource.id, skill_id=skill_id)
                        .filter(LearningRecommendation.status != "Completed")
                        .order_by(LearningRecommendation.id)
                        .first()
                    )
                    if existing:
                        existing.gap = None
                        existing.reason = reason
                        updated += 1
                    else:
                        db.session.add(LearningRecommendation(
                            employee_id=emp.id,
                            resource_id=resource.id,
                            skill_id=skill_id,
                            gap=None,
                            reason=reason,
                            status="Recommended",
                        ))
                        created += 1

        for skill_id, requirement in requirements.items():
            assessment = assessment_map.get(skill_id)
            target = requirement["required_level"]

            if assessment:
                # Keep the legacy stored target synchronized for compatibility/reporting,
                # while active project/task requirements remain the source of truth.
                assessment.required_level = target
                gap = max(0, target - assessment.current_level)
                if gap <= 0:
                    continue
                resource_matches = lambda resource: (
                    resource.skill_id == skill_id
                    and resource.target_level >= assessment.current_level + 1
                )
            else:
                # An unassessed required skill is a development need, but its
                # numerical gap is unknown until the employee records a level.
                gap = None
                # For an unassessed required skill, any active learning resource
                # for the skill can serve as a development step toward the required target.
                resource_matches = lambda resource: (
                    resource.skill_id == skill_id
                )

            matched = [resource for resource in resources if resource_matches(resource)]
            skill = assessment.skill if assessment else skills.get(skill_id)
            if not skill:
                continue
            skill_name = skill.name
            project_text = ", ".join(requirement["projects"]) or "active project work"

            for resource in matched:
                pair = (emp.id, resource.id, skill_id)
                valid_pairs.add(pair)
                if assessment:
                    reason = (
                        f"Gap of {gap} in {skill_name} "
                        f"({assessment.current_level}→{target}) required by {project_text}. "
                        f"Resource builds toward level {resource.target_level}."
                    )
                else:
                    reason = (
                        f"{skill_name} is required at Level {target} by {project_text}, "
                        "but current proficiency has not been assessed. "
                        f"Resource builds toward level {resource.target_level}."
                    )
                existing = (
                    LearningRecommendation.query
                    .filter_by(employee_id=emp.id, resource_id=resource.id, skill_id=skill_id)
                    .filter(LearningRecommendation.status != "Completed")
                    .order_by(LearningRecommendation.id)
                    .first()
                )
                if existing:
                    existing.gap = gap
                    existing.reason = reason
                    updated += 1
                else:
                    db.session.add(LearningRecommendation(
                        employee_id=emp.id,
                        resource_id=resource.id,
                        skill_id=skill_id,
                        gap=gap,
                        reason=reason,
                        status="Recommended",
                    ))
                    created += 1

    # Make newly generated records visible to the cleanup query before committing.
    db.session.flush()

    # Cleanup is deliberately restricted to the same employee scope. This prevents
    # an employee's self-refresh from changing another person's recommendations.
    seen_active = {}
    active_recs = (
        LearningRecommendation.query
        .filter(
            LearningRecommendation.employee_id.in_(employee_ids),
            LearningRecommendation.status.in_(["Recommended", "In Progress"]),
        )
        .order_by(LearningRecommendation.id)
        .all()
    )
    for rec in active_recs:
        pair = (rec.employee_id, rec.resource_id, rec.skill_id)
        if rec.status in ("Recommended", "In Progress") and pair not in valid_pairs:
            # Active recommendations are tied to current project-driven requirements.
            # Completed records remain as learning history.
            db.session.delete(rec)
            removed += 1
            continue

        previous = seen_active.get(pair)
        if previous:
            if previous.status == "Recommended" and rec.status == "In Progress":
                db.session.delete(previous)
                seen_active[pair] = rec
            else:
                db.session.delete(rec)
            removed += 1
        else:
            seen_active[pair] = rec

    db.session.commit()
    return {"created": created, "updated": updated, "removed": removed}


@recommendation_bp.route("/")
@login_required
def my_recommendations():
    """Personal learning for everyone; managers/admins can also monitor team learning."""
    privileged = current_user.role in ("admin", "manager")
    requested_view = request.args.get("view", "").strip().lower()
    # Learning defaults to the signed-in person's own development record.
    view_mode = "team" if privileged and requested_view == "team" else "my"

    if view_mode == "my":
        emp = _linked_employee()
        if not emp:
            flash("No competency profile linked to your account.", "warning")
            if privileged:
                return redirect(url_for("recommendation.my_recommendations", view="team"))
            return redirect(url_for("main.dashboard"))

        # Personal recommendations refresh automatically when My Learning opens.
        # The same scoped operation is also available through the manual button.
        has_active_project = (
            db.session.query(ProjectMember.project_id)
            .join(Project, Project.id == ProjectMember.project_id)
            .filter(
                ProjectMember.employee_id == emp.id,
                Project.status == "Active",
            )
            .first()
            is not None
        )
        _refresh_recommendations([emp.id])
        recs = LearningRecommendation.query.filter_by(employee_id=emp.id).all()
        return render_template(
            "recommendation/list.html",
            recs=_sorted_recommendations(recs),
            own=True,
            view_mode="my",
            linked_employee=emp,
            no_active_project=not has_active_project,
        )

    recs = LearningRecommendation.query.all()
    return render_template(
        "recommendation/list.html",
        recs=_sorted_recommendations(recs),
        own=False,
        view_mode="team",
        linked_employee=_linked_employee(),
        no_active_project=False,
    )


@recommendation_bp.route("/generate", methods=["POST"])
@login_required
def generate():
    """Refresh recommendations within the caller's authorized learning scope."""
    privileged = current_user.role in ("admin", "manager")
    scope = request.form.get("scope", "my").strip().lower()

    if scope == "team":
        if not privileged:
            abort(403)
        employee_ids = [employee.id for employee in Employee.query.all()]
        return_view = "team"
        scope_label = "Team recommendations"
    else:
        emp = _linked_employee()
        if not emp:
            flash("No competency profile linked to your account.", "warning")
            return redirect(url_for("main.dashboard"))
        employee_ids = [emp.id]
        return_view = "my"
        scope_label = "Your recommendations"

    stats = _refresh_recommendations(employee_ids)
    flash(
        f"{scope_label} refreshed. {stats['created']} new, {stats['updated']} refreshed, "
        f"and {stats['removed']} obsolete/duplicate recommendation(s) cleared.",
        "success",
    )
    return redirect(url_for("recommendation.my_recommendations", view=return_view))


@recommendation_bp.route("/<int:rec_id>/start", methods=["POST"])
@login_required
def start(rec_id):
    rec = LearningRecommendation.query.get_or_404(rec_id)
    _enforce_own_learning(rec)

    if rec.status == "Recommended":
        rec.status = "In Progress"
        db.session.commit()
        flash("Learning activity started. Progress is now In Progress.", "success")
    elif rec.status == "Completed":
        flash("This learning activity is already completed.", "info")
    return redirect(url_for("recommendation.my_recommendations", view="my"))


@recommendation_bp.route("/<int:rec_id>/complete", methods=["POST"])
@login_required
def complete(rec_id):
    rec = LearningRecommendation.query.get_or_404(rec_id)
    _enforce_own_learning(rec)

    if rec.status == "Recommended":
        flash("Start the learning activity before marking it complete.", "warning")
    elif rec.status == "In Progress":
        rec.status = "Completed"
        rec.completed_at = datetime.utcnow()
        db.session.commit()
        flash(
            "Learning activity completed. Your competency level will change only after a new assessment validates improvement.",
            "success",
        )
    return redirect(url_for("recommendation.my_recommendations", view="my"))


@recommendation_bp.route("/resources")
@manager_required
def list_resources():
    search = request.args.get("search", "").strip()
    skill_id = request.args.get("skill_id", "").strip()
    resource_type = request.args.get("resource_type", "").strip()
    provider = request.args.get("provider", "").strip()
    status = request.args.get("status", "all").strip().lower()

    query = LearningResource.query
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            LearningResource.title.ilike(pattern),
            LearningResource.provider.ilike(pattern),
            LearningResource.description.ilike(pattern),
        ))
    if skill_id.isdigit():
        query = query.filter(LearningResource.skill_id == int(skill_id))
    if resource_type:
        query = query.filter(LearningResource.resource_type == resource_type)
    if provider:
        query = query.filter(LearningResource.provider == provider)
    if status == "active":
        query = query.filter(LearningResource.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(LearningResource.is_active.is_(False))

    resources = query.order_by(
        LearningResource.is_active.desc(),
        LearningResource.title.asc(),
    ).all()
    skills = Skill.query.order_by(Skill.name).all()
    providers = [
        row[0] for row in
        db.session.query(LearningResource.provider)
        .filter(LearningResource.provider.isnot(None), LearningResource.provider != "")
        .distinct()
        .order_by(LearningResource.provider)
        .all()
    ]
    resource_types = ["Course", "Article", "Certification", "Documentation", "Video"]
    all_resources = LearningResource.query.all()
    repository_stats = {
        "total": len(all_resources),
        "active": sum(1 for resource in all_resources if resource.is_active),
        "skills": len({resource.skill_id for resource in all_resources if resource.is_active}),
        "providers": len({resource.provider for resource in all_resources if resource.is_active and resource.provider}),
    }
    return render_template(
        "recommendation/resources.html",
        resources=resources,
        skills=skills,
        providers=providers,
        resource_types=resource_types,
        repository_stats=repository_stats,
        filters={
            "search": search,
            "skill_id": skill_id,
            "resource_type": resource_type,
            "provider": provider,
            "status": status,
        },
    )


def _resource_form_values():
    allowed_access_types = {"Internal", "Company Subscription", "External"}
    allowed_resource_types = {"Course", "Article", "Certification", "Documentation", "Video"}

    title = request.form.get("title", "").strip()
    provider = request.form.get("provider", "").strip()
    access_type = request.form.get("access_type", "").strip()
    resource_type = request.form.get("resource_type", "Course").strip()
    description = request.form.get("description", "").strip()
    url = request.form.get("url", "").strip()

    try:
        skill_id = int(request.form.get("skill_id", ""))
        target_level = int(request.form.get("target_level", "3"))
    except (TypeError, ValueError):
        return None, "Skill and target proficiency are required."

    if not title or not provider:
        return None, "Title and provider/source are required."
    if access_type not in allowed_access_types:
        return None, "Please select a valid access type."
    if resource_type not in allowed_resource_types:
        return None, "Please select a valid resource type."
    if target_level not in range(1, 6):
        return None, "Target proficiency must be between Level 1 and Level 5."
    if not db.session.get(Skill, skill_id):
        return None, "Selected skill was not found."

    return {
        "title": title,
        "provider": provider,
        "access_type": access_type,
        "resource_type": resource_type,
        "skill_id": skill_id,
        "target_level": target_level,
        "description": description or None,
        "url": url or None,
    }, None


@recommendation_bp.route("/resources/add", methods=["POST"])
@manager_required
def add_resource():
    values, error = _resource_form_values()
    if error:
        flash(error, "warning")
        return redirect(url_for("recommendation.list_resources"))

    db.session.add(LearningResource(**values, is_active=True))
    db.session.commit()
    flash("Learning resource added to the repository.", "success")
    return redirect(url_for("recommendation.list_resources"))


@recommendation_bp.route("/resources/<int:resource_id>/edit", methods=["POST"])
@manager_required
def edit_resource(resource_id):
    resource = LearningResource.query.get_or_404(resource_id)
    values, error = _resource_form_values()
    if error:
        flash(error, "warning")
        return redirect(url_for("recommendation.list_resources"))

    for field, value in values.items():
        setattr(resource, field, value)
    db.session.commit()
    flash(f"{resource.title} updated.", "success")
    return redirect(url_for("recommendation.list_resources"))


@recommendation_bp.route("/resources/<int:resource_id>/toggle", methods=["POST"])
@manager_required
def toggle_resource(resource_id):
    resource = LearningResource.query.get_or_404(resource_id)
    resource.is_active = not resource.is_active
    db.session.commit()
    state = "reactivated" if resource.is_active else "deactivated"
    flash(
        f"{resource.title} {state}. "
        + ("It can be used for new recommendations again." if resource.is_active
           else "Existing learning history is preserved, but it will not be used for new recommendations."),
        "success" if resource.is_active else "info",
    )
    return redirect(url_for("recommendation.list_resources"))
