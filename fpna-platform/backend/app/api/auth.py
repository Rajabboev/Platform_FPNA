"""
Authentication API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone
import logging

from app.database import get_db

logger = logging.getLogger(__name__)
from app.models.user import User, Role
from app.schemas.auth import Token, UserCreate, UserResponse, LoginRequest
from app.utils.security import verify_password, create_access_token, get_password_hash
from app.utils.permissions import get_user_permissions
from app.utils.dependencies import get_current_active_user
from app.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


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
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        employee_id=current_user.employee_id,
        department=current_user.department,
        branch=current_user.branch,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        roles=[role.name for role in current_user.roles]
    )