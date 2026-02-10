"""
FastAPI dependencies for authentication and authorization
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List

from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, PermissionEnum
from app.utils.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = db.query(User).options(selectinload(User.roles)).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
        current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user is active"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return current_user


def require_permissions(required_permissions: List[PermissionEnum]):
    """
    Dependency to check if user has required permissions
    Usage: current_user: User = Depends(require_permissions([PermissionEnum.CREATE_BUDGET]))
    """

    async def permission_checker(
            current_user: User = Depends(get_current_active_user)
    ) -> User:
        # Get user permissions from roles
        user_permissions = []
        for role in current_user.roles:
            if role.permissions:
                perms = role.permissions.split(',')
                user_permissions.extend(perms)

        # Check if user has all required permissions
        missing_permissions = []
        for perm in required_permissions:
            if perm.value not in user_permissions:
                missing_permissions.append(perm.value)

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing_permissions)}"
            )

        return current_user

    return permission_checker