"""
Department Management API

Endpoints for managing departments and user assignments.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.department import Department, DepartmentAssignment, DepartmentRole
from app.models.coa_dimension import BudgetingGroup
from app.models.user import User
from app.utils.dependencies import get_current_active_user

router = APIRouter(prefix="/departments", tags=["Departments"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class DepartmentCreate(BaseModel):
    code: str
    name_en: str
    name_uz: Optional[str] = None
    name_ru: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    head_user_id: Optional[int] = None
    is_baseline_only: bool = False
    display_order: int = 0


class DepartmentUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    name_ru: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    head_user_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_baseline_only: Optional[bool] = None
    display_order: Optional[int] = None


class DepartmentResponse(BaseModel):
    id: int
    code: str
    name_en: str
    name_uz: Optional[str]
    name_ru: Optional[str]
    description: Optional[str]
    parent_id: Optional[int]
    head_user_id: Optional[int]
    is_active: bool
    is_baseline_only: bool
    display_order: int
    budgeting_group_ids: List[int]
    
    class Config:
        from_attributes = True


class AssignmentCreate(BaseModel):
    user_id: int
    role: DepartmentRole = DepartmentRole.ANALYST


class AssignmentResponse(BaseModel):
    id: int
    department_id: int
    user_id: int
    role: str
    is_active: bool
    
    class Config:
        from_attributes = True


class AssignGroupsRequest(BaseModel):
    budgeting_group_ids: List[int]


# ============================================================================
# Department CRUD Endpoints
# ============================================================================

@router.get("/", response_model=List[DepartmentResponse])
def list_departments(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all departments"""
    query = db.query(Department)
    if not include_inactive:
        query = query.filter(Department.is_active == True)
    
    departments = query.order_by(Department.display_order, Department.name_en).all()
    
    result = []
    for dept in departments:
        result.append({
            **dept.__dict__,
            'budgeting_group_ids': [bg.group_id for bg in dept.budgeting_groups]
        })
    
    return result


@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new department"""
    # Check for duplicate code
    existing = db.query(Department).filter(Department.code == data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with code '{data.code}' already exists"
        )
    
    dept = Department(
        code=data.code,
        name_en=data.name_en,
        name_uz=data.name_uz,
        name_ru=data.name_ru,
        description=data.description,
        parent_id=data.parent_id,
        head_user_id=data.head_user_id,
        is_baseline_only=data.is_baseline_only,
        display_order=data.display_order,
        created_by_user_id=current_user.id,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    
    return {
        **dept.__dict__,
        'budgeting_group_ids': []
    }


@router.get("/{dept_id}", response_model=DepartmentResponse)
def get_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get department by ID"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    return {
        **dept.__dict__,
        'budgeting_group_ids': [bg.group_id for bg in dept.budgeting_groups]
    }


@router.patch("/{dept_id}", response_model=DepartmentResponse)
def update_department(
    dept_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a department"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(dept, key, value)
    
    db.commit()
    db.refresh(dept)
    
    return {
        **dept.__dict__,
        'budgeting_group_ids': [bg.group_id for bg in dept.budgeting_groups]
    }


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a department (soft delete)"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    dept.is_active = False
    db.commit()


# ============================================================================
# User Assignment Endpoints
# ============================================================================

@router.get("/{dept_id}/users", response_model=List[AssignmentResponse])
def list_department_users(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List users assigned to a department"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    return [
        {
            'id': a.id,
            'department_id': a.department_id,
            'user_id': a.user_id,
            'role': a.role.value,
            'is_active': a.is_active,
        }
        for a in dept.assignments if a.is_active
    ]


@router.post("/{dept_id}/assign", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_user_to_department(
    dept_id: int,
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Assign a user to a department"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already assigned
    existing = db.query(DepartmentAssignment).filter(
        DepartmentAssignment.department_id == dept_id,
        DepartmentAssignment.user_id == data.user_id,
        DepartmentAssignment.is_active == True
    ).first()
    
    if existing:
        # Update role
        existing.role = data.role
        db.commit()
        return {
            'id': existing.id,
            'department_id': existing.department_id,
            'user_id': existing.user_id,
            'role': existing.role.value,
            'is_active': existing.is_active,
        }
    
    assignment = DepartmentAssignment(
        department_id=dept_id,
        user_id=data.user_id,
        role=data.role,
        assigned_by_user_id=current_user.id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    return {
        'id': assignment.id,
        'department_id': assignment.department_id,
        'user_id': assignment.user_id,
        'role': assignment.role.value,
        'is_active': assignment.is_active,
    }


@router.delete("/{dept_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_from_department(
    dept_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a user from a department"""
    assignment = db.query(DepartmentAssignment).filter(
        DepartmentAssignment.department_id == dept_id,
        DepartmentAssignment.user_id == user_id,
        DepartmentAssignment.is_active == True
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    assignment.is_active = False
    db.commit()


# ============================================================================
# Budgeting Group Assignment Endpoints
# ============================================================================

@router.post("/{dept_id}/assign-groups")
def assign_budgeting_groups(
    dept_id: int,
    data: AssignGroupsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Assign budgeting groups to a department"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Get budgeting groups
    groups = db.query(BudgetingGroup).filter(
        BudgetingGroup.group_id.in_(data.budgeting_group_ids)
    ).all()
    
    # Clear existing and set new
    dept.budgeting_groups = groups
    db.commit()
    
    return {
        "status": "success",
        "department_id": dept_id,
        "assigned_groups": [g.group_id for g in groups]
    }


@router.get("/{dept_id}/groups")
def get_department_groups(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get budgeting groups assigned to a department"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    
    return {
        "department_id": dept_id,
        "groups": [
            {
                "group_id": g.group_id,
                "name_ru": g.name_ru,
                "name_en": g.name_en,
                "category": g.category,
            }
            for g in dept.budgeting_groups
        ]
    }
