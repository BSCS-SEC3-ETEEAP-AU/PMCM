"""
Seed script: populates the platform with a realistic dataset for the
IT Architecture and Data Engineering Department of The Medical City (TMC),
as described in the thesis (Chapter 1, Background of the Study).

Run:  python3.11 seed.py
"""
from datetime import date, timedelta
from app import create_app
from app.models import (
    db, User, Employee, Skill, Certification, CompetencyAssessment,
    Project, ProjectMember, Task, Milestone, LearningResource,
)
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()

    # ---- Users (RBAC: admin / manager / employee) ----
    users = {
        "admin": User(username="admin", full_name="Christine K. Cabrera",
                      email="admin@tmc.edu.ph", role="admin", position="System Administrator"),
        "mgr1": User(username="mgr_gueco", full_name="Gene Henry J. Gueco",
                     email="g.gueco@tmc.edu.ph", role="manager", position="Department Manager"),
        "mgr2": User(username="mgr_buban", full_name="Fhamela T. Buban",
                     email="f.buban@tmc.edu.ph", role="manager", position="Project Manager"),
    }
    for u in users.values():
        u.set_password("password123")
        db.session.add(u)
    db.session.commit()

    # ---- Employees (multidisciplinary TMC team) ----
    emp_data = [
        ("Maria Santos", "Software Engineer", "Software Engineering", "hybrid"),
        ("John Cruz", "Software Engineer", "Software Engineering", "onsite"),
        ("Anna Reyes", "Data Engineer", "Data Engineering", "remote"),
        ("Paolo Diaz", "Data Engineer", "Data Engineering", "hybrid"),
        ("Liza Torres", "Data Analyst", "Data Analytics", "remote"),
        ("Mark Lim", "Data Analyst", "Data Analytics", "onsite"),
    ]
    employees = []
    for name, pos, team, mode in emp_data:
        e = Employee(full_name=name, position=pos, team=team, work_mode=mode)
        employees.append(e)
        db.session.add(e)
    db.session.commit()

    # Link managers to employee profiles so they can also view/assess as staff
    employees[2].user_id = users["mgr1"].id   # Anna Reyes (Data Engineer)
    employees[0].user_id = users["mgr2"].id   # Maria Santos (Software Engineer)
    db.session.commit()

    # Dedicated employee account (role-restricted views)
    emp_user = User(username="emp_liza", full_name="Liza Torres",
                    email="l.torres@tmc.edu.ph", role="employee", position="Data Analyst")
    emp_user.set_password("password123")
    db.session.add(emp_user)
    db.session.commit()
    employees[4].user_id = emp_user.id  # Liza Torres
    db.session.commit()

    # ---- Skills catalog ----
    skills = {
        "Python": Skill(name="Python", category="Technical", description="Backend & data programming"),
        "SQL": Skill(name="SQL", category="Technical", description="Relational data querying"),
        "React": Skill(name="React", category="Technical", description="Frontend web development"),
        "Data Pipelines": Skill(name="Data Pipelines", category="Technical", description="ETL / orchestration"),
        "Cloud (AWS)": Skill(name="Cloud (AWS)", category="Technical", description="Cloud infrastructure"),
        "Data Visualization": Skill(name="Data Visualization", category="Technical", description="BI & dashboards"),
        "Communication": Skill(name="Communication", category="Soft", description="Stakeholder communication"),
        "Agile/Scrum": Skill(name="Agile/Scrum", category="Soft", description="Iterative delivery"),
    }
    for s in skills.values():
        db.session.add(s)
    db.session.commit()

    # ---- Competency assessments (current vs required => gaps) ----
    # (employee_idx, skill, current, required)
    assess_map = [
        (0, "Python", 4, 5), (0, "React", 3, 4), (0, "Communication", 4, 4),
        (1, "Python", 3, 4), (1, "SQL", 4, 4), (1, "Agile/Scrum", 3, 4),
        (2, "Python", 4, 5), (2, "Data Pipelines", 3, 4), (2, "SQL", 5, 5),
        (3, "Data Pipelines", 2, 4), (3, "Cloud (AWS)", 2, 4), (3, "SQL", 4, 5),
        (4, "Data Visualization", 3, 4), (4, "SQL", 4, 5), (4, "Python", 2, 3),
        (5, "Data Visualization", 4, 4), (5, "Communication", 3, 4), (5, "SQL", 3, 4),
    ]
    for ei, sk, cur, req in assess_map:
        db.session.add(CompetencyAssessment(
            employee_id=employees[ei].id, skill_id=skills[sk].id,
            current_level=cur, required_level=req,
            assessed_on=date.today() - timedelta(days=10),
        ))
    db.session.commit()

    # ---- Certifications ----
    certs = [
        (0, "AWS Certified Developer", "Amazon", date(2024, 5, 1), date(2027, 5, 1)),
        (2, "Google Data Engineer", "Google", date(2023, 8, 15), date(2026, 8, 15)),
        (4, "Tableau Desktop Specialist", "Tableau", date(2024, 2, 10), None),
    ]
    for ei, name, issuer, iss, exp in certs:
        db.session.add(Certification(
            employee_id=employees[ei].id, name=name, issuer=issuer,
            issued_date=iss, expiry_date=exp,
        ))
    db.session.commit()

    # ---- Projects ----
    p1 = Project(name="Enterprise Data Platform Upgrade",
                 description="Modernize the centralized data platform for clinical & operational reporting.",
                 manager_id=users["mgr1"].id, status="Active",
                 start_date=date.today() - timedelta(days=30),
                 target_date=date.today() + timedelta(days=60))
    p2 = Project(name="Patient Portal Enhancement",
                 description="Add self-service features to the patient web portal.",
                 manager_id=users["mgr2"].id, status="Active",
                 start_date=date.today() - timedelta(days=15),
                 target_date=date.today() + timedelta(days=45))
    db.session.add_all([p1, p2])
    db.session.commit()

    # Project members
    for ei in range(6):
        db.session.add(ProjectMember(project_id=p1.id, employee_id=employees[ei].id))
    for ei in [0, 1, 4, 5]:
        db.session.add(ProjectMember(project_id=p2.id, employee_id=employees[ei].id))
    db.session.commit()

    # ---- Tasks ----
    task_defs = [
        (p1, "Design data lake architecture", 2, "Done", "High", "Data Pipelines", 4),
        (p1, "Build ingestion pipelines", 3, "In Progress", "High", "Data Pipelines", 4),
        (p1, "Provision cloud environment", 3, "To Do", "Medium", "Cloud (AWS)", 4),
        (p1, "Data quality validation", 2, "Backlog", "Medium", "SQL", 5),
        (p2, "Implement appointment UI", 0, "In Progress", "High", "React", 4),
        (p2, "Build notification service", 1, "To Do", "Medium", "Python", 4),
        (p2, "Dashboard analytics view", 4, "Backlog", "Low", "Data Visualization", 4),
    ]
    for proj, title, eidx, status, prio, sk, req in task_defs:
        db.session.add(Task(
            project_id=proj.id, title=title, assignee_id=employees[eidx].id,
            status=status, priority=prio, required_skill_id=skills[sk].id,
            required_level=req, due_date=date.today() + timedelta(days=20),
        ))
    db.session.commit()

    # ---- Milestones ----
    db.session.add_all([
        Milestone(project_id=p1.id, title="Architecture sign-off", due_date=date.today() + timedelta(days=10)),
        Milestone(project_id=p1.id, title="Pipeline MVP", due_date=date.today() + timedelta(days=35)),
        Milestone(project_id=p2.id, title="UI beta release", due_date=date.today() + timedelta(days=20)),
    ])
    db.session.commit()

    # ---- Learning resources (repository) ----
    resources = [
        ("Advanced Python for Data", "Deep dive into Python data tooling.", "Python", 5, "Course", ""),
        ("React Patterns & Hooks", "Modern React development.", "React", 4, "Course", ""),
        ("AWS Data Engineering Path", "Build pipelines on AWS.", "Cloud (AWS)", 4, "Course", ""),
        ("Data Pipeline Orchestration", "Airflow & orchestration basics.", "Data Pipelines", 4, "Article", ""),
        ("Tableau Dashboards", "Build executive dashboards.", "Data Visualization", 4, "Course", ""),
        ("Effective Stakeholder Communication", "Communication skills for IT.", "Communication", 4, "Article", ""),
        ("Professional Scrum Master", "Agile/Scrum certification prep.", "Agile/Scrum", 4, "Certification", ""),
    ]
    for title, desc, sk, lvl, rtype, url in resources:
        db.session.add(LearningResource(
            title=title, description=desc, skill_id=skills[sk].id,
            target_level=lvl, resource_type=rtype, url=url,
        ))
    db.session.commit()

    print("Seed complete.")
    print("Seed complete.")
    print("Login accounts (password: password123):")
    print("  admin      (Administrator)")
    print("  mgr_gueco  (Manager)")
    print("  mgr_buban  (Manager)")
    print("  emp_liza   (Employee - Data Analyst)")
