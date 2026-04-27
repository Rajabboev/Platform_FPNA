"""
Authentication API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone
import logging
from typing import List

from app.database import get_db

logger = logging.getLogger(__name__)
from app.models.user import User, Role
from app.schemas.auth import (
    Token,
    UserCreate,
    UserResponse,
    LoginRequest,
    UserAdminCreate,
    UserAdminUpdate,
    RoleResponse,
)
from app.utils.security import verify_password, create_access_token, get_password_hash
from app.utils.permissions import get_user_permissions
from app.utils.dependencies import get_current_active_user
from app.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])

def _ensure_admin_or_cfo(current_user: User) -> None:
    role_names = {role.name.upper() for role in current_user.roles}
    if "ADMIN" not in role_names and "CFO" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or CFO role required"
        )


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        employee_id=user.employee_id,
        department=user.department,
        branch=user.branch,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        roles=[role.name for role in user.roles]
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""

    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        employee_id=user_data.employee_id,
        department=user_data.department,
        branch=user_data.branch,
        is_active=True,
        is_verified=False
    )

    # Assign default role (VIEWER)
    default_role = db.query(Role).filter(Role.name == "VIEWER").first()
    if default_role:
        new_user.roles.append(default_role)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Format response
    user_response = UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        full_name=new_user.full_name,
        employee_id=new_user.employee_id,
        department=new_user.department,
        branch=new_user.branch,
        is_active=new_user.is_active,
        is_verified=new_user.is_verified,
        created_at=new_user.created_at,
        roles=[role.name for role in new_user.roles]
    )

    return user_response


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login endpoint - OAuth2 compatible"""

    # Find user
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Get user roles and permissions
    role_names = [role.name for role in user.roles]
    permissions = get_user_permissions(role_names)

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "roles": role_names},
        expires_delta=access_token_expires
    )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "roles": role_names,
            "permissions": permissions
        }
    }


@router.post("/login-simple", response_model=Token)
async def login_simple(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Simple login with JSON body - easier for testing"""
    try:
        # Find user
        user = db.query(User).filter(User.username == login_data.username).first()

        if not user or not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Get user roles and permissions (safe if roles missing)
        try:
            role_names = [role.name for role in user.roles]
        except Exception as e:
            logger.warning("Could not load user roles: %s", e)
            role_names = []
        permissions = get_user_permissions(role_names)

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "roles": role_names},
            expires_delta=access_token_expires
        )

        # Update last login (skip if DB has issues with datetime)
        try:
            user.last_login = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "roles": role_names,
                "permissions": permissions
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) if settings.DEBUG else "An error occurred during login",
        ) from e


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    return _to_user_response(current_user)


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List active roles for user management forms (CFO/Admin only)."""
    _ensure_admin_or_cfo(current_user)
    roles = db.query(Role).filter(Role.is_active == True).order_by(Role.name.asc()).all()
    return roles


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List users with roles (CFO/Admin only)."""
    _ensure_admin_or_cfo(current_user)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_to_user_response(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    payload: UserAdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create user and assign roles (CFO/Admin only)."""
    _ensure_admin_or_cfo(current_user)

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if payload.employee_id and db.query(User).filter(User.employee_id == payload.employee_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee ID already registered")

    role_names = [r.strip().upper() for r in (payload.roles or []) if r and r.strip()]
    roles = []
    if role_names:
        roles = db.query(Role).filter(Role.name.in_(role_names)).all()
        found = {r.name for r in roles}
        missing = [r for r in role_names if r not in found]
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown roles: {', '.join(missing)}")
    else:
        default_role = db.query(Role).filter(Role.name == "VIEWER").first()
        if default_role:
            roles = [default_role]

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        employee_id=payload.employee_id,
        department=payload.department,
        branch=payload.branch,
        is_active=payload.is_active,
        is_verified=False,
    )
    user.roles = roles
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_admin(
    user_id: int,
    payload: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update user profile, activation and role assignments (CFO/Admin only)."""
    _ensure_admin_or_cfo(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.email is not None and payload.email != user.email:
        exists = db.query(User).filter(User.email == payload.email, User.id != user_id).first()
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user.email = payload.email

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.employee_id is not None:
        exists = db.query(User).filter(User.employee_id == payload.employee_id, User.id != user_id).first() if payload.employee_id else None
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee ID already registered")
        user.employee_id = payload.employee_id or None
    if payload.department is not None:
        user.department = payload.department or None
    if payload.branch is not None:
        user.branch = payload.branch or None
    if payload.password:
        user.hashed_password = get_password_hash(payload.password)
    if payload.is_active is not None:
        user.is_active = payload.is_active

    if payload.roles is not None:
        role_names = [r.strip().upper() for r in payload.roles if r and r.strip()]
        if not role_names:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one role is required")
        roles = db.query(Role).filter(Role.name.in_(role_names)).all()
        found = {r.name for r in roles}
        missing = [r for r in role_names if r not in found]
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown roles: {', '.join(missing)}")
        user.roles = roles

    db.commit()
    db.refresh(user)
    return _to_user_response(user)