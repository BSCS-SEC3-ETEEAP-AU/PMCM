# Smart Project Management & Employee Competency Development Platform
### For Hybrid Software Development Teams — BS Computer Science Thesis (ETEEAP), Arellano University

This is the implemented web platform described in **Chapters 1–3** of the thesis:
*A Smart Project Management and Employee Competency Development Platform for Hybrid Software Development Teams*
(IT Architecture & Data Engineering Department, The Medical City).

---

## Tech Stack (per thesis Chapter 1 & 3)
| Layer | Technology |
|---|---|
| Backend | **Python 3.10+ / Flask** |
| Database | **PostgreSQL** (hosted on **Supabase Cloud** in production) |
| Frontend | **HTML5, CSS3, JavaScript** (responsive) |
| Auth | Flask-Login + Role-Based Access Control (RBAC) |
| Methodology | Agile Scrum (4 sprints, one per module) |

> **Note on running locally:** This build runs against a local PostgreSQL instance so it is
> demonstrable immediately. To deploy on Supabase, set `DATABASE_URL` in `.env` to your
> Supabase PostgreSQL connection string — no code changes required (see below).

---

## Modules (thesis Chapter 3)
1. **Project Management** — project creation, task assignment, Kanban-style workflow,
   milestones/deadlines, progress monitoring.
2. **Employee Competency Development** — competency profiles, skills catalog, certifications,
   competency assessments, gap analysis.
3. **Competency-Based Learning Recommendation** — **rule-based** engine (NO AI/ML, per thesis
   Scope & Limitations) that compares employee competency gaps with the Learning Resource
   Repository and recommends relevant resources; tracks completion and updates competencies.
4. **Reports & Dashboard** — project status reports, competency reports, executive dashboard
   with KPIs, charts, filters, and an audit trail (`ReportLog`).

## Roles (RBAC)
- **Administrator** — full access, account management.
- **Manager / Project Manager** — projects, tasks, assessments, recommendations, reports.
- **Employee** — update own tasks, complete own competency assessment, view own recommendations.

---

## How to Run (local)
```bash
# 1. Install dependencies
pip3 install flask flask-sqlalchemy flask-login psycopg2-binary python-dotenv

# 2. Ensure PostgreSQL is running and create the database
#    (connection string is in config.py / .env)
createdb thesis_platform   # or use the supplied local instance

# 3. Seed the demo dataset (TMC department sample data)
python3.11 seed.py

# 4. Start the app
python3.11 run.py
# Open http://localhost:5000
```

### Demo accounts (password: `password123`)
| Username | Role |
|---|---|
| `admin` | Administrator |
| `mgr_gueco` | Manager |
| `mgr_buban` | Manager |
| `emp_liza` | Employee (Data Analyst) |

---

## Switching to Supabase Cloud (thesis deployment)
1. In Supabase: create a project; the PostgreSQL database is provisioned automatically.
2. Copy `.env.example` → `.env` and set:
   ```
   DATABASE_URL=postgresql+psycopg2://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
3. Run `python3.11 seed.py` once to create tables and load data (or use Supabase SQL editor
   with the schema in `app/models.py`).
4. No application code changes are needed — SQLAlchemy abstracts the database.

---

## ISO/IEC 25010 Evaluation Instrument
The platform is evaluated by intended users and IT professionals using the standard's
characteristics (thesis Chapter 3, Table 4 rating scale).

**Rating scale:** 5 = Strongly Agree … 1 = Strongly Disagree
| Weighted Mean | Descriptive Rating |
|---|---|
| 4.51–5.00 | Excellent |
| 3.51–4.50 | Very Good |
| 2.51–3.50 | Good |
| 1.51–2.50 | Fair |
| 1.00–1.50 | Poor |

**Characteristic → sample items**
- **Functional Suitability** — The system performs project management, competency tracking, and recommendation as intended.
- **Performance Efficiency** — Pages load promptly; recommendation processing is fast.
- **Compatibility** — Works across browsers; Supabase/PostgreSQL compatible.
- **Usability** — Interface is clear and easy to navigate for hybrid teams.
- **Reliability** — The system operates without failure during normal use.
- **Security** — RBAC ensures users access only their authorized functions/data.
- **Maintainability** — Modular code (per-sprint blueprints) is easy to modify.
- **Portability** — Easily deployed to local PostgreSQL or Supabase Cloud.

*(Full questionnaire in thesis Appendix H; this instrument maps the live system to the
evaluation criteria.)*

---

## Project Structure
```
thesis_webapp/
├── run.py                 # app entry point
├── config.py              # config (DB URL, roles, statuses)
├── seed.py                # demo data (TMC department)
├── app/
│   ├── __init__.py        # app factory, blueprints, login manager
│   ├── models.py          # SQLAlchemy models (all entities)
│   ├── decorators.py      # RBAC decorators
│   ├── modules/           # Sprint 1–4 blueprints
│   │   ├── auth.py        # login / RBAC
│   │   ├── projects.py    # Sprint 1
│   │   ├── competency.py  # Sprint 2
│   │   ├── recommendation.py # Sprint 3 (rule-based)
│   │   ├── reports.py     # Sprint 4
│   │   └── main.py        # dashboard
│   ├── templates/         # HTML5 (responsive)
│   └── static/            # CSS3 + JS (charts)
└── tests/                 # (extend with UAT scripts)
```

---
*Developed for the ETEEAP BS Computer Science thesis, Arellano University.*
