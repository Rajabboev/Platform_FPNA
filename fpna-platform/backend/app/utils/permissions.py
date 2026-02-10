"""
Permission management and role-based access control
"""

from typing import List
from app.models.user import PermissionEnum, RoleEnum

# Role-Permission mapping
ROLE_PERMISSIONS = {
    RoleEnum.ADMIN: [
        PermissionEnum.MANAGE_USERS,
        PermissionEnum.MANAGE_ROLES,
        PermissionEnum.VIEW_ALL,
    ],
    RoleEnum.CEO: [
        PermissionEnum.VIEW_BUDGET,
        PermissionEnum.APPROVE_L4,
        PermissionEnum.VIEW_ALL,
        PermissionEnum.EXPORT_DATA,
    ],
    RoleEnum.CFO: [
        PermissionEnum.CREATE_BUDGET,
        PermissionEnum.VIEW_BUDGET,
        PermissionEnum.EDIT_BUDGET,
        PermissionEnum.SUBMIT_BUDGET,
        PermissionEnum.APPROVE_L3,
        PermissionEnum.VIEW_ALL,
        PermissionEnum.UPLOAD_DATA,
        PermissionEnum.EXPORT_DATA,
    ],
    RoleEnum.FINANCE_MANAGER: [
        PermissionEnum.CREATE_BUDGET,
        PermissionEnum.VIEW_BUDGET,
        PermissionEnum.EDIT_BUDGET,
        PermissionEnum.SUBMIT_BUDGET,
        PermissionEnum.APPROVE_L2,
        PermissionEnum.VIEW_DEPARTMENT,
        PermissionEnum.UPLOAD_DATA,
        PermissionEnum.EXPORT_DATA,
    ],
    RoleEnum.DEPARTMENT_MANAGER: [
        PermissionEnum.VIEW_BUDGET,
        PermissionEnum.APPROVE_L2,
        PermissionEnum.VIEW_DEPARTMENT,
    ],
    RoleEnum.BRANCH_MANAGER: [
        PermissionEnum.CREATE_BUDGET,
        PermissionEnum.VIEW_BUDGET,
        PermissionEnum.EDIT_BUDGET,
        PermissionEnum.SUBMIT_BUDGET,
        PermissionEnum.APPROVE_L1,
        PermissionEnum.VIEW_OWN,
        PermissionEnum.UPLOAD_DATA,
    ],
    RoleEnum.ANALYST: [
        PermissionEnum.CREATE_BUDGET,
        PermissionEnum.VIEW_BUDGET,
        PermissionEnum.EDIT_BUDGET,
        PermissionEnum.SUBMIT_BUDGET,
        PermissionEnum.VIEW_DEPARTMENT,
        PermissionEnum.UPLOAD_DATA,
        PermissionEnum.EXPORT_DATA,
    ],
    RoleEnum.DATA_ENTRY: [
        PermissionEnum.UPLOAD_DATA,
        PermissionEnum.VIEW_OWN,
    ],
    RoleEnum.VIEWER: [
        PermissionEnum.VIEW_BUDGET,
        PermissionEnum.VIEW_OWN,
    ],
}


def get_permissions_for_role(role_name: str) -> List[str]:
    """Get all permissions for a given role (case-insensitive)"""
    if not role_name:
        return []
    try:
        role_enum = RoleEnum(role_name.upper())
        return [perm.value for perm in ROLE_PERMISSIONS.get(role_enum, [])]
    except ValueError:
        return []


def get_user_permissions(roles: List[str]) -> List[str]:
    """Get all permissions for a user based on their roles"""
    all_permissions = set()
    for role in roles:
        permissions = get_permissions_for_role(role)
        all_permissions.update(permissions)
    return list(all_permissions)


def user_has_permission(user_permissions: List[str], required_permission: str) -> bool:
    """Check if user has a specific permission"""
    return required_permission in user_permissions
