"""
Department Management API

Endpoints for managing departments and user assignments.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.department import Department, DepartmentAssignment, DepartmentRole, DepartmentProductAccess
from app.models.coa_dimension import BudgetingGroup
from app.services.coa_product_taxonomy import (
    TAXONOMY,
    TAXONOMY_BY_KEY,
    department_list_sort_key,
)
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
    manager_user_id: Optional[int] = None
    is_baseline_only: bool = False
    display_order: int = 0
    dwh_segment_value: Optional[str] = None
    primary_product_key: Optional[str] = None  # FP&A taxonomy key; one active dept per key


class DepartmentUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    name_ru: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    head_user_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_baseline_only: Optional[bool] = None
    display_order: Optional[int] = None
    dwh_segment_value: Optional[str] = None
    primary_product_key: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: int
    code: str
    name_en: str
    name_uz: Optional[str]
    name_ru: Optional[str]
    description: Optional[str]
    parent_id: Optional[int]
    head_user_id: Optional[int]
    manager_user_id: Optional[int]
    is_active: bool
    is_baseline_only: bool
    display_order: int
    dwh_segment_value: Optional[str] = None
    primary_product_key: Optional[str] = None
    product_label_en: Optional[str] = None
    product_pillar: Optional[str] = None
    budgeting_group_ids: List[int]
    product_keys: List[str] = []
    head_user_name: Optional[str] = None
    manager_user_name: Optional[str] = None

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


class AssignProductsRequest(BaseModel):
    product_keys: List[str]


def _normalize_product_key(raw: Optional[str]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip().upper()


def _assert_primary_product_available(
    db: Session, primary_key: Optional[str], exclude_dept_id: Optional[int]
) -> None:
    if not primary_key:
        return
    q = db.query(Department).filter(
        Department.primary_product_key == primary_key,
        Department.is_active == True,  # noqa: E712
    )
    if exclude_dept_id is not None:
        q = q.filter(Department.id != exclude_dept_id)
    if q.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Another active department already owns product '{primary_key}'.",
        )


def _ensure_product_access_row(
    db: Session, dept_id: int, product_key: str, current_user_id: int
) -> None:
    existing = (
        db.query(DepartmentProductAccess)
        .filter(
            DepartmentProductAccess.department_id == dept_id,
            DepartmentProductAccess.product_key == product_key,
        )
        .first()
    )
    if existing:
        return
    now = datetime.now(timezone.utc)
    db.add(
        DepartmentProductAccess(
            department_id=dept_id,
            product_key=product_key,
            can_edit=True,
            can_submit=True,
            assigned_by_user_id=current_user_id,
            assigned_at=now,
        )
    )


def _dept_to_response(dept: Department) -> dict:
    """Build DepartmentResponse dict from a Department ORM object."""
    head_name = None
    if dept.head_user and hasattr(dept.head_user, 'full_name'):
        head_name = dept.head_user.full_name or dept.head_user.username
    manager_name = None
    if dept.manager_user and hasattr(dept.manager_user, 'full_name'):
        manager_name = dept.manager_user.full_name or dept.manager_user.username
    pk = getattr(dept, "primary_product_key", None)
    tax = TAXONOMY_BY_KEY.get(pk) if pk else None
    return {
        **{k: v for k, v in dept.__dict__.items() if not k.startswith('_')},
        'budgeting_group_ids': [bg.group_id for bg in dept.budgeting_groups],
        'product_keys': [p.product_key for p in (dept.product_access_rows or [])],
        'head_user_name': head_name,
        'manager_user_name': manager_name,
        'product_label_en': tax.label_en if tax else None,
        'product_pillar': tax.pillar if tax else None,
    }


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
    
    departments = query.all()
    departments.sort(
        key=lambda d: department_list_sort_key(
            d.primary_product_key, d.display_order or 0, d.name_en
        )
    )
    return [_dept_to_response(d) for d in departments]


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
    
    ppk = _normalize_product_key(data.primary_product_key)
    if ppk and ppk not in TAXONOMY_BY_KEY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown primary_product_key '{ppk}'. Use GET /api/v1/coa-dimension/product-taxonomy.",
        )
    _assert_primary_product_available(db, ppk, None)

    dept = Department(
        code=data.code,
        name_en=data.name_en,
        name_uz=data.name_uz,
        name_ru=data.name_ru,
        description=data.description,
        parent_id=data.parent_id,
        head_user_id=data.head_user_id,
        manager_user_id=data.manager_user_id,
        is_baseline_only=data.is_baseline_only,
        display_order=data.display_order,
        dwh_segment_value=data.dwh_segment_value,
        primary_product_key=ppk,
        created_by_user_id=current_user.id,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    if ppk:
        _ensure_product_access_row(db, dept.id, ppk, current_user.id)
        db.commit()
        db.refresh(dept)

    return _dept_to_response(dept)


@router.post("/seed-product-owners")
def seed_product_owner_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create or align departments with FP&A taxonomy: one product owner per product
    (skips UNCLASSIFIED). Sets code, name_en, display_order, primary_product_key,
    and replaces department_product_access with that single product.
    Idempotent: matches existing rows by primary_product_key or code.
    """
    skip = frozenset({"UNCLASSIFIED"})
    created = 0
    updated = 0
    now = datetime.now(timezone.utc)
    for ord_idx, item in enumerate(TAXONOMY):
        if item.key in skip:
            continue
        dept = (
            db.query(Department)
            .filter(Department.primary_product_key == item.key)
            .first()
        )
        if not dept:
            dept = db.query(Department).filter(Department.code == item.key).first()
        if dept:
            dept.primary_product_key = item.key
            dept.name_en = item.label_en
            dept.display_order = ord_idx
            dept.is_active = True
            updated += 1
        else:
            dept = Department(
                code=item.key,
                name_en=item.label_en,
                primary_product_key=item.key,
                display_order=ord_idx,
                created_by_user_id=current_user.id,
            )
            db.add(dept)
            db.flush()
            created += 1

        _assert_primary_product_available(db, item.key, dept.id)
        db.query(DepartmentProductAccess).filter(
            DepartmentProductAccess.department_id == dept.id
        ).delete(synchronize_session=False)
        db.add(
            DepartmentProductAccess(
                department_id=dept.id,
                product_key=item.key,
                can_edit=True,
                can_submit=True,
                assigned_by_user_id=current_user.id,
                assigned_at=now,
            )
        )

    db.commit()
    return {
        "status": "success",
        "created_departments": created,
        "updated_departments": updated,
        "message": "Departments aligned with FP&A product taxonomy (excluding UNCLASSIFIED).",
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
    
    return _dept_to_response(dept)


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
    
    update_data = data.model_dump(exclude_unset=True)
    if "primary_product_key" in update_data:
        raw_pk = update_data.pop("primary_product_key")
        ppk = _normalize_product_key(raw_pk) if raw_pk is not None else None
        if ppk is not None and ppk not in TAXONOMY_BY_KEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown primary_product_key '{ppk}'. Use GET /api/v1/coa-dimension/product-taxonomy.",
            )
        if ppk is None:
            dept.primary_product_key = None
        else:
            _assert_primary_product_available(db, ppk, dept.id)
            dept.primary_product_key = ppk

    for key, value in update_data.items():
        setattr(dept, key, value)

    db.commit()
    db.refresh(dept)
    if dept.primary_product_key:
        _ensure_product_access_row(db, dept.id, dept.primary_product_key, current_user.id)
        db.commit()
        db.refresh(dept)
    return _dept_to_response(dept)


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


@router.post("/{dept_id}/assign-products")
def assign_fpna_products(
    dept_id: int,
    data: AssignProductsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Assign FP&A product buckets (Loans, Deposits, …) to a department for budget planning."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    normalized = []
    for raw in data.product_keys:
        pk = (raw or "").strip().upper()
        if not pk:
            continue
        if pk not in TAXONOMY_BY_KEY:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown product_key '{raw}'. Use GET /api/v1/coa-dimension/product-taxonomy.",
            )
        normalized.append(pk)

    db.query(DepartmentProductAccess).filter(DepartmentProductAccess.department_id == dept_id).delete()
    now = datetime.now(timezone.utc)
    for pk in normalized:
        db.add(
            DepartmentProductAccess(
                department_id=dept_id,
                product_key=pk,
                can_edit=True,
                can_submit=True,
                assigned_by_user_id=current_user.id,
                assigned_at=now,
            )
        )
    db.commit()

    return {"status": "success", "department_id": dept_id, "product_keys": normalized}


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
