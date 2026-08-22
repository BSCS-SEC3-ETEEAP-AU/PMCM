"""
Database models for the Smart Project Management and Employee Competency
Development Platform.

Entities reflect the thesis design (Chapter 3):
  - User (RBAC: admin / manager / employee)
  - Project, Task (Project Management Module)
  - Employee, Skill, Certification, CompetencyAssessment (Competency Module)
  - LearningResource, LearningRecommendation (Recommendation Module)
  - ReportLog (Reports & Dashboard Module audit trail)
"""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """System accounts with role-based access control."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    role = db.Column(db.String(20), nullable=False)  # admin | manager | employee
    work_mode = db.Column(db.String(20), default="onsite")  # onsite | remote | hybrid
    position = db.Column(db.String(80))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_manager(self):
        return self.role in ("admin", "manager")


class Employee(db.Model):
    """Competency profile of a staff member (links to User when applicable)."""
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    full_name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(80))
    team = db.Column(db.String(80))  # e.g. Software Engineering, Data Engineering, Data Analytics
    work_mode = db.Column(db.String(20), default="hybrid")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="employee_profile", uselist=False)


class Skill(db.Model):
    """Catalog of competencies tracked by the organization."""
    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(80))  # Technical | Soft | Domain
    description = db.Column(db.Text)


class Certification(db.Model):
    """Employee certifications / professional credentials."""
    __tablename__ = "certifications"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    issuer = db.Column(db.String(120))
    issued_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CompetencyAssessment(db.Model):
    """Recorded proficiency of an employee for a given skill (gap-analysis input)."""
    __tablename__ = "competency_assessments"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    current_level = db.Column(db.Integer, nullable=False)  # 1-5
    required_level = db.Column(db.Integer, nullable=False)  # 1-5 (role/project need)
    assessed_on = db.Column(db.Date, default=date.today)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("Employee", backref="assessments")
    skill = db.relationship("Skill", backref="assessments")

    @property
    def gap(self):
        return max(0, self.required_level - self.current_level)


class Project(db.Model):
    """Project record (Project Management Module)."""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="Active")  # Active | Completed | On Hold
    start_date = db.Column(db.Date)
    target_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    manager = db.relationship("User", backref="managed_projects")


class ProjectMember(db.Model):
    """Many-to-many link between projects and employees."""
    __tablename__ = "project_members"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)


class Task(db.Model):
    """Task / work item within a project."""
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assignee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    status = db.Column(db.String(20), default="Backlog")
    priority = db.Column(db.String(20), default="Medium")  # Low | Medium | High
    # Required competency for this task (used by recommendation engine)
    required_skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=True)
    required_level = db.Column(db.Integer, default=3)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = db.relationship("Project", backref="tasks")
    assignee = db.relationship("Employee", backref="assigned_tasks")
    required_skill = db.relationship("Skill", backref="required_by_tasks")


class Milestone(db.Model):
    """Project milestone / deadline."""
    __tablename__ = "milestones"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    due_date = db.Column(db.Date)
    achieved = db.Column(db.Boolean, default=False)


class LearningResource(db.Model):
    """Learning material in the repository (Recommendation Module)."""
    __tablename__ = "learning_resources"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    target_level = db.Column(db.Integer, default=3)  # builds toward this proficiency
    resource_type = db.Column(db.String(40), default="Course")  # Course | Article | Certification
    url = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    skill = db.relationship("Skill", backref="learning_resources")


class LearningRecommendation(db.Model):
    """Rule-based recommendation: employee + resource + reason (gap)."""
    __tablename__ = "learning_recommendations"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("learning_resources.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    gap = db.Column(db.Integer, default=0)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default="Recommended")  # Recommended | In Progress | Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    employee = db.relationship("Employee", backref="recommendations")
    resource = db.relationship("LearningResource", backref="recommendations")
    skill = db.relationship("Skill", backref="recommendations")


class ReportLog(db.Model):
    """Audit trail for report/dashboard generation (Reports & Dashboard Module)."""
    __tablename__ = "report_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    report_type = db.Column(db.String(80), nullable=False)
    filters = db.Column(db.Text)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="report_logs")


class AccountAssistanceRequest(db.Model):
    """Login-page request routed to Administrators for account assistance."""
    __tablename__ = "account_assistance_requests"

    id = db.Column(db.Integer, primary_key=True)
    request_type = db.Column(db.String(40), nullable=False)
    requester_name = db.Column(db.String(120), nullable=False)
    requester_contact = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="Open")  # Open | Resolved
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id])


def init_db():
    db.create_all()
