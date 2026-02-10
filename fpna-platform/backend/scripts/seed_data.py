"""Seed initial roles and users"""
import sys
import os

# Add backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User, Role, RoleEnum
from app.utils.security import get_password_hash
from app.utils.permissions import ROLE_PERMISSIONS

def seed_roles(db: Session):
    """Create all roles (skip if already exist)"""
    print("Creating roles...")
    created = 0
    for role_enum, permissions in ROLE_PERMISSIONS.items():
        if db.query(Role).filter(Role.name == role_enum.value).first():
            continue
        role = Role(
            name=role_enum.value,
            display_name=role_enum.value.replace('_', ' ').title(),
            description=f"Role for {role_enum.value}",
            permissions=','.join([p.value for p in permissions]),
            is_active=True
        )
        db.add(role)
        created += 1
    db.commit()
    print(f"✅ Roles done ({created} created, {len(ROLE_PERMISSIONS) - created} already existed)")


def seed_users(db: Session):
    """Create test users (skip if already exist)"""
    print("Creating test users...")
    roles = {role.name: role for role in db.query(Role).all()}

    users_data = [
        {"username": "admin", "email": "admin@fpna.com", "full_name": "System Admin", "role": "ADMIN",
         "employee_id": "EMP001"},
        {"username": "ceo", "email": "ceo@fpna.com", "full_name": "John CEO", "role": "CEO", "employee_id": "EMP002"},
        {"username": "cfo", "email": "cfo@fpna.com", "full_name": "Jane CFO", "role": "CFO", "employee_id": "EMP003"},
        {"username": "manager", "email": "manager@fpna.com", "full_name": "Bob Manager", "role": "FINANCE_MANAGER",
         "employee_id": "EMP004"},
        {"username": "branch_manager", "email": "branch@fpna.com", "full_name": "Branch Manager", "role": "BRANCH_MANAGER", "employee_id": "EMP006"},
        {"username": "analyst", "email": "analyst@fpna.com", "full_name": "Alice Analyst", "role": "ANALYST",
         "employee_id": "EMP005"},
    ]

    created = 0
    for user_data in users_data:
        if db.query(User).filter(User.username == user_data["username"]).first():
            continue
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            full_name=user_data["full_name"],
            employee_id=user_data["employee_id"],
            hashed_password=get_password_hash("password123"),
            is_active=True,
            is_verified=True
        )
        user.roles.append(roles[user_data["role"]])
        db.add(user)
        created += 1

    db.commit()
    print(f"✅ Users done ({created} created, {len(users_data) - created} already existed)")
    print("\n📝 Test credentials (all use password: password123):")
    for user_data in users_data:
        print(f"   - {user_data['username']} ({user_data['role']})")

def main():
    db = SessionLocal()
    try:
        seed_roles(db)
        seed_users(db)
        print("\n✅ Seed complete!")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()