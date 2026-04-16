"""
Seed department users for workflow testing.
Creates one manager + one analyst per department and assigns them.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import ALL models first so SQLAlchemy resolves relationships
import app.models.user
import app.models.department
import app.models.budget_plan
import app.models.baseline
import app.models.coa_dimension
import app.models.notification

from app.database import SessionLocal
from app.models.user import User, Role, RoleEnum
from app.models.department import Department, DepartmentAssignment, DepartmentRole
from app.utils.security import get_password_hash

PASSWORD = "password123"

# dept_code → (manager_username, analyst_username)
DEPT_USERS = {
    "TREASURY":     ("treasury_mgr",   "treasury_analyst"),
    "RETAIL":       ("retail_mgr",     "retail_analyst"),
    "CORPORATE":    ("corporate_mgr",  "corporate_analyst"),
    "RISK":         ("risk_mgr",       "risk_analyst"),
    "OPERATIONS":   ("ops_mgr",        "ops_analyst"),
    "BASELINE_REF": ("baseline_mgr",   "baseline_analyst"),
}

def get_role(db, role_name):
    return db.query(Role).filter(Role.name == role_name).first()

def get_or_create_user(db, username, full_name, role):
    u = db.query(User).filter(User.username == username).first()
    if u:
        return u, False
    u = User(
        username=username,
        email=f"{username}@fpna.com",
        full_name=full_name,
        employee_id=(username.upper()[:8] + str(abs(hash(username)) % 100)),
        hashed_password=get_password_hash(PASSWORD),
        is_active=True,
        is_verified=True,
    )
    if role:
        u.roles.append(role)
    db.add(u)
    db.flush()
    return u, True

def ensure_assignment(db, dept_id, user_id, role: DepartmentRole):
    exists = db.query(DepartmentAssignment).filter(
        DepartmentAssignment.department_id == dept_id,
        DepartmentAssignment.user_id == user_id,
    ).first()
    if not exists:
        db.add(DepartmentAssignment(
            department_id=dept_id,
            user_id=user_id,
            role=role,
            is_active=True,
        ))

def main():
    db = SessionLocal()
    try:
        mgr_role    = get_role(db, RoleEnum.FINANCE_MANAGER.value)
        analyst_role = get_role(db, RoleEnum.ANALYST.value)

        depts = {d.code: d for d in db.query(Department).all()}

        print(f"\n{'-'*60}")
        print(f"{'USERNAME':<22} {'ROLE':<18} {'DEPT':<20} STATUS")
        print(f"{'-'*60}")

        results = []
        for code, (mgr_un, analyst_un) in DEPT_USERS.items():
            dept = depts.get(code)
            if not dept:
                print(f"  ⚠  Department {code} not found — skipping")
                continue

            dept_label = dept.name_en[:18]

            # Manager
            mgr, created = get_or_create_user(
                db, mgr_un, f"{dept.name_en} Manager", mgr_role
            )
            ensure_assignment(db, dept.id, mgr.id, DepartmentRole.MANAGER)
            # Set as dept manager
            dept.manager_user_id = mgr.id
            status = "CREATED" if created else "exists"
            print(f"  {mgr_un:<22} {'FINANCE_MANAGER':<18} {dept_label:<20} {status}")
            results.append((mgr_un, PASSWORD, "Manager", dept.name_en))

            # Analyst
            ana, created = get_or_create_user(
                db, analyst_un, f"{dept.name_en} Analyst", analyst_role
            )
            ensure_assignment(db, dept.id, ana.id, DepartmentRole.ANALYST)
            status = "CREATED" if created else "exists"
            print(f"  {analyst_un:<22} {'ANALYST':<18} {dept_label:<20} {status}")
            results.append((analyst_un, PASSWORD, "Analyst", dept.name_en))

        db.commit()

        print(f"\n{'='*60}")
        print("  LOGIN CREDENTIALS (all password: password123)")
        print(f"{'='*60}")
        print(f"  {'USERNAME':<22} {'DEPT'}")
        print(f"  {'-'*50}")
        for un, pw, role, dept_name in results:
            print(f"  {un:<22} {dept_name}  [{role}]")
        print(f"{'='*60}\n")

    finally:
        db.close()

if __name__ == "__main__":
    main()
