"""
Application configuration.

Environment-driven settings for the Smart Project Management and Employee
Competency Development Platform.

This version is updated for Neon PostgreSQL in production while still allowing
local PostgreSQL during development.
"""
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv()


def build_database_url():
    """Return a SQLAlchemy-ready database URL.

    Supports:
    - local PostgreSQL for development
    - Neon PostgreSQL for cloud deployment

    It also normalizes postgres:// to postgresql+psycopg2:// and ensures
    sslmode=require for remote PostgreSQL hosts such as Neon.
    """
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://thesis_user:thesis_pass@localhost:5432/thesis_platform",
    ).strip()

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    parsed = urlparse(db_url)
    is_postgres = parsed.scheme.startswith("postgresql")
    is_remote_host = parsed.hostname not in (None, "", "localhost", "127.0.0.1")

    if is_postgres and is_remote_host:
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.setdefault("sslmode", os.environ.get("DB_SSLMODE", "require"))
        db_url = urlunparse(parsed._replace(query=urlencode(query)))

    return db_url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = build_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Role constants (RBAC per thesis: Administrator, Manager, Employee)
    ROLE_ADMIN = "admin"
    ROLE_MANAGER = "manager"
    ROLE_EMPLOYEE = "employee"

    # Task workflow statuses (hybrid team task lifecycle)
    TASK_STATUSES = ["Backlog", "To Do", "In Progress", "In Review", "Done"]

    # Competency proficiency scale (1-5) used in assessments / gap analysis
    PROFICIENCY_LEVELS = {
        1: "Beginner",
        2: "Basic",
        3: "Intermediate",
        4: "Advanced",
        5: "Expert",
    }
