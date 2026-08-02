"""
User Acceptance Testing (UAT) script — thesis Chapter 3, Objective 3.
Verifies the core functional requirements of each module against the running app.
Run:  python3.11 tests/test_uat.py
"""
import requests

BASE = "http://127.0.0.1:5000"
PASS = "password123"


def login(username):
    s = requests.Session()
    s.post(BASE + "/login", data={"username": username, "password": PASS})
    return s


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")


def main():
    # --- Auth & RBAC ---
    admin = login("admin")
    check("Admin can reach dashboard", admin.get(BASE + "/dashboard").status_code == 200)
    emp = login("emp_liza")
    check("Employee is blocked from Reports (RBAC)", emp.get(BASE + "/reports/").status_code == 403)
    check("Employee reaches own recommendations", emp.get(BASE + "/recommend/").status_code == 200)

    # --- Sprint 1: Project Management ---
    r = admin.get(BASE + "/projects/")
    check("Projects list renders seeded project", "Enterprise Data Platform" in r.text)
    r = admin.get(BASE + "/projects/1")
    check("Project detail shows task board", "Tasks" in r.text)

    # --- Sprint 2: Competency Development ---
    r = admin.get(BASE + "/competency/employees")
    check("Employee competency list renders", "Liza Torres" in r.text)
    r = admin.get(BASE + "/competency/gap-report")
    check("Gap analysis report renders", "Gap Analysis" in r.text)

    # --- Sprint 3: Recommendation (rule-based) ---
    admin.post(BASE + "/recommend/generate")
    r = admin.get(BASE + "/recommend/")
    check("Recommendation engine produced recommendations", "Mark Done" in r.text or "Completed" in r.text)

    # --- Sprint 4: Reports & Dashboard ---
    r = admin.get(BASE + "/reports/project-status")
    check("Project status report renders progress", "%" in r.text)
    r = admin.get(BASE + "/reports/competency")
    check("Competency report renders coverage", "%" in r.text)

    print("\nUAT complete.")


if __name__ == "__main__":
    main()
