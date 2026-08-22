"""Application factory for the thesis platform."""
from datetime import date, timedelta

from flask import Flask
from flask_login import LoginManager, current_user
from .models import db, User
from config import Config

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from .modules.auth import auth_bp
    from .modules.projects import projects_bp
    from .modules.competency import competency_bp
    from .modules.recommendation import recommendation_bp
    from .modules.reports import reports_bp
    from .modules.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(competency_bp)
    app.register_blueprint(recommendation_bp)
    app.register_blueprint(reports_bp)

    @app.context_processor
    def inject_shell_notifications():
        """Provide role-scoped deadline and account-assistance notifications."""
        empty = {
            "shell_notifications": [],
            "shell_notification_count": 0,
            "shell_notification_signature": "",
            "shell_account_request_count": 0,
        }
        if not current_user.is_authenticated:
            return empty

        from .models import (
            AccountAssistanceRequest, Employee, Milestone, Project, ProjectMember
        )

        notifications = []
        signature_parts = []
        account_request_count = 0

        # Login/account assistance is an Administrator responsibility.
        if current_user.role == "admin":
            assistance_query = (
                AccountAssistanceRequest.query
                .filter_by(status="Open")
                .order_by(AccountAssistanceRequest.created_at.desc(), AccountAssistanceRequest.id.desc())
            )
            assistance_signature_rows = assistance_query.with_entities(
                AccountAssistanceRequest.id, AccountAssistanceRequest.created_at
            ).all()
            account_request_count = len(assistance_signature_rows)
            signature_parts.extend(
                f"a:{row.id}:{row.created_at.isoformat()}"
                for row in assistance_signature_rows
            )

            for help_request in assistance_query.limit(5).all():
                notifications.append({
                    "kind": "account_request",
                    "title": "Account assistance request",
                    "request_id": help_request.id,
                    "request_type": help_request.request_type,
                    "requester_name": help_request.requester_name,
                    "created_at": help_request.created_at,
                })

        project_ids = []
        active_projects = Project.query.filter(Project.status != "Completed")

        if current_user.role == "admin":
            project_ids = [row.id for row in active_projects.with_entities(Project.id).all()]
        elif current_user.role == "manager":
            project_ids = [
                row.id
                for row in active_projects.filter(Project.manager_id == current_user.id)
                .with_entities(Project.id)
                .all()
            ]
        elif current_user.role == "employee":
            employee = Employee.query.filter_by(user_id=current_user.id).first()
            if employee:
                project_ids = [
                    row.project_id
                    for row in ProjectMember.query.filter_by(employee_id=employee.id).all()
                ]

        milestone_count = 0
        if project_ids:
            today = date.today()
            horizon = today + timedelta(days=45)
            milestone_query = (
                Milestone.query
                .filter(Milestone.project_id.in_(project_ids))
                .filter(Milestone.achieved.is_(False))
                .filter(Milestone.due_date >= today)
                .filter(Milestone.due_date <= horizon)
                .order_by(Milestone.due_date.asc(), Milestone.id.asc())
            )

            signature_rows = milestone_query.with_entities(Milestone.id, Milestone.due_date).all()
            milestone_count = len(signature_rows)
            signature_parts.extend(
                f"m:{row.id}:{row.due_date.isoformat()}"
                for row in signature_rows
            )

            remaining_slots = max(0, 5 - len(notifications))
            rows = milestone_query.limit(remaining_slots).all() if remaining_slots else []
            project_ids_in_rows = {row.project_id for row in rows}
            projects = Project.query.filter(Project.id.in_(project_ids_in_rows)).all() if rows else []
            project_lookup = {project.id: project for project in projects}

            for milestone in rows:
                project = project_lookup.get(milestone.project_id)
                notifications.append({
                    "kind": "milestone",
                    "title": milestone.title,
                    "date": milestone.due_date,
                    "project_id": milestone.project_id,
                    "project_name": project.name if project else "Project",
                })

        return {
            "shell_notifications": notifications,
            "shell_notification_count": account_request_count + milestone_count,
            "shell_notification_signature": "|".join(signature_parts),
            "shell_account_request_count": account_request_count,
        }

    return app
