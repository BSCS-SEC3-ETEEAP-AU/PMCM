"""
Application configuration.

The database connection is environment-driven so the platform can run against
a local PostgreSQL instance during development/defense, or against a hosted
Supabase PostgreSQL database in production — exactly as described in the thesis
(Chapter 1, Scope and Limitations; Chapter 3, System Planning and Design).
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Local PostgreSQL is the default; override DATABASE_URL in .env for Supabase.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://thesis_user:thesis_pass@localhost:5432/thesis_platform",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

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
