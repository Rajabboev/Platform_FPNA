"""Update role permissions in DB to match ROLE_PERMISSIONS (e.g. after adding SUBMIT_BUDGET to ANALYST)"""
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models.user import Role
from app.utils.permissions import ROLE_PERMISSIONS

def run():
    db = SessionLocal()
    try:
        for role_enum, perms in ROLE_PERMISSIONS.items():
            role = db.query(Role).filter(Role.name == role_enum.value).first()
            if role:
                new_perms = ",".join(p.value for p in perms)
                if role.permissions != new_perms:
                    role.permissions = new_perms
                    print(f"Updated {role_enum.value}")
        db.commit()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run()
