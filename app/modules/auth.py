"""Authentication & account management (RBAC)."""
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_

from ..models import db, User, Employee, AccountAssistanceRequest
from ..decorators import admin_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        identity = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(or_(User.username == identity, User.email == identity)).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=bool(request.form.get("remember")))
            flash(f"Welcome, {user.full_name} ({user.role.title()}).", "success")
            return redirect(url_for("main.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/account-assistance/request", methods=["POST"])
def request_account_assistance():
    """Accept a lightweight login/account-help request without requiring authentication."""
    allowed_types = {
        "Need an account",
        "Password reset",
        "Account locked / cannot sign in",
        "Other",
    }
    request_type = request.form.get("request_type", "").strip()
    requester_name = request.form.get("requester_name", "").strip()
    requester_contact = request.form.get("requester_contact", "").strip()
    message = request.form.get("message", "").strip()

    # Honeypot field: silently accept bot submissions without storing them.
    if request.form.get("website", "").strip():
        flash("Your request has been sent to the system administrators.", "success")
        return redirect(url_for("auth.login"))

    if request_type not in allowed_types:
        flash("Please select a valid account assistance reason.", "danger")
        return redirect(url_for("auth.login"))
    if not requester_name or not requester_contact:
        flash("Name and username/email are required for account assistance.", "danger")
        return redirect(url_for("auth.login"))
    if len(requester_name) > 120 or len(requester_contact) > 120 or len(message) > 500:
        flash("The account assistance request is too long. Please shorten the entered details.", "danger")
        return redirect(url_for("auth.login"))

    existing = AccountAssistanceRequest.query.filter_by(
        request_type=request_type,
        requester_contact=requester_contact,
        status="Open",
    ).first()
    if existing:
        flash("An open request for this account is already pending with the system administrators.", "info")
        return redirect(url_for("auth.login"))

    assistance_request = AccountAssistanceRequest(
        request_type=request_type,
        requester_name=requester_name,
        requester_contact=requester_contact,
        message=message or None,
    )
    db.session.add(assistance_request)
    db.session.commit()
    flash("Your request has been sent to the system administrators.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/account-requests")
@admin_required
def account_requests():
    open_requests = (
        AccountAssistanceRequest.query
        .filter_by(status="Open")
        .order_by(AccountAssistanceRequest.created_at.desc(), AccountAssistanceRequest.id.desc())
        .all()
    )
    resolved_requests = (
        AccountAssistanceRequest.query
        .filter_by(status="Resolved")
        .order_by(AccountAssistanceRequest.resolved_at.desc(), AccountAssistanceRequest.id.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "auth/account_requests.html",
        open_requests=open_requests,
        resolved_requests=resolved_requests,
    )


@auth_bp.route("/account-requests/<int:request_id>/resolve", methods=["POST"])
@admin_required
def resolve_account_request(request_id):
    assistance_request = db.session.get(AccountAssistanceRequest, request_id)
    if not assistance_request:
        flash("Account assistance request not found.", "danger")
        return redirect(url_for("auth.account_requests"))

    if assistance_request.status != "Resolved":
        assistance_request.status = "Resolved"
        assistance_request.resolved_at = datetime.utcnow()
        assistance_request.resolved_by_user_id = current_user.id
        db.session.commit()
        flash("Account assistance request marked as resolved.", "success")

    return redirect(url_for("auth.account_requests"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Allow a signed-in user to maintain their own basic account profile."""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        work_mode = request.form.get("work_mode", "onsite").strip().lower()

        if not full_name:
            flash("Full name is required.", "danger")
            return redirect(url_for("auth.profile"))
        if work_mode not in ("onsite", "remote", "hybrid"):
            work_mode = "onsite"

        current_user.full_name = full_name
        current_user.email = email or None
        current_user.work_mode = work_mode
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    employee = Employee.query.filter_by(user_id=current_user.id).first()
    return render_template("auth/profile.html", employee=employee)


@auth_bp.route("/accounts")
@admin_required
def accounts():
    users = User.query.order_by(User.role, User.full_name).all()
    open_request_count = AccountAssistanceRequest.query.filter_by(status="Open").count()
    return render_template("auth/accounts.html", users=users, open_request_count=open_request_count)
