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
    # Every workforce profile has a login account so assigned staff can access
    # their projects, tasks, competencies, and learning recommendations.
    emp_data = [
        ("emp_maria", "Maria Santos", "m.santos@tmc.edu.ph", "Software Engineer", "Software Engineering", "hybrid"),
        ("emp_john", "John Cruz", "j.cruz@tmc.edu.ph", "Software Engineer", "Software Engineering", "onsite"),
        ("emp_anna", "Anna Reyes", "a.reyes@tmc.edu.ph", "Data Engineer", "Data Engineering", "remote"),
        ("emp_paolo", "Paolo Diaz", "p.diaz@tmc.edu.ph", "Data Engineer", "Data Engineering", "hybrid"),
        ("emp_liza", "Liza Torres", "l.torres@tmc.edu.ph", "Data Analyst", "Data Analytics", "remote"),
        ("emp_mark", "Mark Lim", "m.lim@tmc.edu.ph", "Data Analyst", "Data Analytics", "onsite"),
    ]
    employees = []
    for username, name, email, pos, team, mode in emp_data:
        user = User(
            username=username, full_name=name, email=email, role="employee",
            position=pos, work_mode=mode, is_active=True,
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()
        employee = Employee(
            user_id=user.id, full_name=name, position=pos, team=team, work_mode=mode
        )
        employees.append(employee)
        db.session.add(employee)
    db.session.commit()

    # Privileged accounts are still employees: role controls permissions,
    # while Employee holds the person's own competency identity.
    role_profiles = {}
    role_profile_teams = {
        "admin": "IT Architecture & Data Engineering",
        "mgr1": "Data Engineering",
        "mgr2": "IT Architecture & Data Engineering",
    }
    for key, team in role_profile_teams.items():
        user = users[key]
        profile = Employee(
            user_id=user.id, full_name=user.full_name, position=user.position,
            team=team, work_mode=user.work_mode,
        )
        role_profiles[key] = profile
        db.session.add(profile)
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

    # Personal competency records for Administrator / Project Managers.
    role_assess_map = [
        ("admin", "Communication", 4, 4), ("admin", "Agile/Scrum", 3, 4), ("admin", "SQL", 3, 3),
        ("mgr1", "Communication", 4, 5), ("mgr1", "Agile/Scrum", 4, 4), ("mgr1", "SQL", 3, 4),
        ("mgr2", "Communication", 4, 5), ("mgr2", "Agile/Scrum", 4, 4), ("mgr2", "SQL", 3, 4),
    ]
    for key, sk, cur, req in role_assess_map:
        db.session.add(CompetencyAssessment(
            employee_id=role_profiles[key].id, skill_id=skills[sk].id,
            current_level=cur, required_level=req,
            assessed_on=date.today() - timedelta(days=7),
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
        ("Advanced Python for Data", "Deep dive into Python data tooling.", "Python", 5, "Course", "LinkedIn Learning", "Company Subscription", "https://www.linkedin.com/learning/search?keywords=advanced%20python%20data"),
        ("React Patterns & Hooks", "Modern React development.", "React", 4, "Course", "React Documentation", "External", "https://react.dev/learn"),
        ("AWS Data Engineering Path", "Build pipelines on AWS.", "Cloud (AWS)", 4, "Course", "AWS Skill Builder", "External", "https://skillbuilder.aws/"),
        ("Data Pipeline Orchestration", "Airflow & orchestration basics.", "Data Pipelines", 4, "Article", "Apache Airflow Documentation", "External", "https://airflow.apache.org/docs/apache-airflow/stable/"),
        ("Tableau Dashboards", "Build executive dashboards.", "Data Visualization", 4, "Course", "Tableau Learning", "External", "https://www.tableau.com/learn/training"),
        ("Effective Stakeholder Communication", "Communication skills for IT.", "Communication", 4, "Article", "LinkedIn Learning", "Company Subscription", "https://www.linkedin.com/learning/search?keywords=stakeholder%20communication"),
        ("Professional Scrum Master Advanced Preparation", "Advanced Scrum leadership and certification preparation.", "Agile/Scrum", 5, "Certification", "Scrum.org", "External", "https://www.scrum.org/professional-scrum-master-certification"),
    ]
    for title, desc, sk, lvl, rtype, provider, access_type, url in resources:
        db.session.add(LearningResource(
            title=title, description=desc, skill_id=skills[sk].id,
            target_level=lvl, resource_type=rtype, provider=provider,
            access_type=access_type, url=url,
        ))
    db.session.commit()

    print("Seed complete.")
    print("Seed complete.")
    print("Login accounts (password: password123):")
    print("  admin      (Administrator)")
    print("  mgr_gueco  (Manager)")
    print("  mgr_buban  (Manager)")
    print("  emp_maria / emp_john / emp_anna / emp_paolo / emp_liza / emp_mark")
    print("             (Employee accounts)")
