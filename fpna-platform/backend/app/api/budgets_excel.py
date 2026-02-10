"""
Budget Excel upload and management API
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import os
from datetime import datetime
import shutil

from app.database import get_db
from app.models.budget import Budget, BudgetLineItem, BudgetStatus
from app.models.user import User
from app.utils.dependencies import get_current_active_user
from app.services.approval_service import submit_budget
from app.schemas.budget import (
    BudgetResponse,
    BudgetSummary,
    BudgetUpdate,
    BudgetLineItemCreate,
    BudgetLineItemUpdate,
    BudgetLineItemResponse,
    ScaleSectionRequest,
    BatchUpdateRequest,
)
from app.services.excel_service import ExcelProcessor
from app.config import settings

router = APIRouter(prefix="/budgets", tags=["budgets"])

# DRAFT and REJECTED budgets can be edited; edits to REJECTED set status back to DRAFT for resubmit
def _is_editable(status) -> bool:
    """Check if budget can be edited (handles enum or string from DB)."""
    s = (status.value if hasattr(status, 'value') else str(status)) if status else ""
    return s in ("DRAFT", "REJECTED")

# Ensure upload folder exists
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)


@router.post("/upload", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def upload_budget_excel(
        file: UploadFile = File(...),
        uploaded_by: str = Query("system", description="User who uploaded the file"),
        db: Session = Depends(get_db)
):
    """
    Upload budget from Excel file

    Expected Excel format:
    - Sheet 1: Header (Fiscal Year, Department, Branch, Description, Currency)
    - Sheet 2: LineItems (Account Code, Account Name, Category, Month, Amount, etc.)
    """

    # Validate file extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )

    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(settings.allowed_extensions_list)}"
        )

    # Read file content
    contents = await file.read()
    file_size = len(contents)

    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )

    # Save file temporarily
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_filename = f"{timestamp}_{file.filename}"
    temp_filepath = os.path.join(settings.UPLOAD_FOLDER, temp_filename)

    with open(temp_filepath, 'wb') as f:
        f.write(contents)

    try:
        # Parse Excel file
        excel_data = ExcelProcessor.parse_budget_excel(temp_filepath)

        # Generate budget code
        budget_code = f"BDG-{excel_data['header']['fiscal_year']}-{timestamp}"

        # Create budget record
        new_budget = Budget(
            budget_code=budget_code,
            fiscal_year=excel_data['header']['fiscal_year'],
            department=excel_data['header']['department'],
            branch=excel_data['header']['branch'],
            total_amount=excel_data['total_amount'],
            currency=excel_data['header']['currency'],
            description=excel_data['header']['description'],
            status=BudgetStatus.DRAFT,
            source_file=temp_filename,
            uploaded_by=uploaded_by
        )

        db.add(new_budget)
        db.flush()  # Get the budget ID

        # Create line items
        for item_data in excel_data['line_items']:
            line_item = BudgetLineItem(
                budget_id=new_budget.id,
                **item_data
            )
            db.add(line_item)

        db.commit()
        db.refresh(new_budget)

        try:
            from app.services.notification_service import notify_managers_uploaded
            notify_managers_uploaded(new_budget, uploaded_by, db)
        except Exception:
            pass

        return new_budget

    except ValueError as ve:
        # Clean up file on error
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        # Clean up file on error
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing upload: {str(e)}"
        )


@router.get("/template/download")
def download_template():
    """Download Excel template for budget upload"""
    template_path = os.path.join(settings.UPLOAD_FOLDER, "budget_template.xlsx")
    if not os.path.exists(template_path):
        ExcelProcessor.create_template(template_path)
    return FileResponse(
        path=template_path,
        filename="budget_template.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/", response_model=List[BudgetSummary])
def list_budgets(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        fiscal_year: int = Query(None),
        status: BudgetStatus = Query(None),
        department: str = Query(None),
        db: Session = Depends(get_db)
):
    """List all budgets with optional filtering"""

    query = db.query(Budget)

    # Apply filters
    if fiscal_year:
        query = query.filter(Budget.fiscal_year == fiscal_year)
    if status:
        query = query.filter(Budget.status == status)
    if department:
        query = query.filter(Budget.department.ilike(f"%{department}%"))

    budgets = query.order_by(Budget.id).offset(skip).limit(limit).all()

    # Add line items count
    result = []
    for budget in budgets:
        try:
            count = len(budget.line_items) if budget.line_items else 0
        except Exception:
            count = 0
        budget_dict = {
            "id": budget.id,
            "budget_code": budget.budget_code,
            "fiscal_year": budget.fiscal_year,
            "department": budget.department,
            "branch": budget.branch,
            "total_amount": float(budget.total_amount) if budget.total_amount is not None else 0,
            "status": budget.status.value if hasattr(budget.status, 'value') else str(budget.status),
            "created_at": budget.created_at,
            "line_items_count": count
        }
        result.append(BudgetSummary(**budget_dict))

    return result


@router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(budget_id: int, db: Session = Depends(get_db)):
    """Get budget details including all line items"""

    budget = db.query(Budget).filter(Budget.id == budget_id).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget with ID {budget_id} not found"
        )

    return budget


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(budget_id: int, payload: BudgetUpdate, db: Session = Depends(get_db)):
    """Update budget header (DRAFT or REJECTED). REJECTED becomes DRAFT so it can be resubmitted."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget with ID {budget_id} not found"
        )
    if not _is_editable(budget.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only DRAFT or REJECTED budgets can be updated"
        )
    was_rejected = _status_str(budget.status) == "REJECTED"
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(budget, key, value)
    if was_rejected:
        budget.status = BudgetStatus.DRAFT
    db.commit()
    db.refresh(budget)
    return budget


def _recompute_budget_total(db: Session, budget_id: int) -> None:
    total = db.query(func.coalesce(func.sum(BudgetLineItem.amount), 0)).filter(
        BudgetLineItem.budget_id == budget_id
    ).scalar()
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget:
        budget.total_amount = total
        db.commit()


def _status_str(s) -> str:
    """Normalize status for comparison (handles enum or string from DB)."""
    return (s.value if hasattr(s, 'value') else str(s)) if s else ""


def _allow_edit_and_reopen_if_rejected(db: Session, budget: Budget) -> None:
    """If budget was REJECTED, set to DRAFT so it can be resubmitted."""
    if _status_str(budget.status) == "REJECTED":
        budget.status = BudgetStatus.DRAFT


@router.post("/{budget_id}/line-items", response_model=BudgetLineItemResponse, status_code=status.HTTP_201_CREATED)
def create_line_item(budget_id: int, payload: BudgetLineItemCreate, db: Session = Depends(get_db)):
    """Add a line item (DRAFT or REJECTED). REJECTED becomes DRAFT for resubmit."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    if not _is_editable(budget.status):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be edited")
    _allow_edit_and_reopen_if_rejected(db, budget)
    item = BudgetLineItem(budget_id=budget_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    _recompute_budget_total(db, budget_id)
    return item


@router.patch("/{budget_id}/line-items/{item_id}", response_model=BudgetLineItemResponse)
def update_line_item(budget_id: int, item_id: int, payload: BudgetLineItemUpdate, db: Session = Depends(get_db)):
    """Update a line item (DRAFT or REJECTED). REJECTED becomes DRAFT for resubmit."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    if not _is_editable(budget.status):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be edited")
    _allow_edit_and_reopen_if_rejected(db, budget)
    item = db.query(BudgetLineItem).filter(
        BudgetLineItem.id == item_id,
        BudgetLineItem.budget_id == budget_id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    _recompute_budget_total(db, budget_id)
    return item


@router.post("/{budget_id}/line-items/scale-section")
def scale_section(budget_id: int, payload: ScaleSectionRequest, db: Session = Depends(get_db)):
    """Scale a section (DRAFT or REJECTED). REJECTED becomes DRAFT for resubmit."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    if not _is_editable(budget.status):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be edited")
    _allow_edit_and_reopen_if_rejected(db, budget)

    if payload.group_by == "category":
        if payload.group_value in ("", "Uncategorized", "None"):
            items = [i for i in db.query(BudgetLineItem).filter(BudgetLineItem.budget_id == budget_id).all()
                     if (i.category or "").strip() == ""]
        else:
            items = db.query(BudgetLineItem).filter(
                BudgetLineItem.budget_id == budget_id,
                BudgetLineItem.category == payload.group_value
            ).all()
    else:
        month_val = int(payload.group_value) if payload.group_value.isdigit() else None
        items = db.query(BudgetLineItem).filter(
            BudgetLineItem.budget_id == budget_id,
            BudgetLineItem.month == month_val
        ).all()

    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No line items in this section")

    if payload.new_amount is not None:
        total_amt = sum(float(i.amount) for i in items)
        if total_amt == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot scale: section total is zero")
        factor = float(payload.new_amount) / total_amt
        for i in items:
            i.amount = round(float(i.amount) * factor, 2)

    if payload.new_quantity is not None:
        total_qty = sum(float(i.quantity or 0) for i in items)
        if total_qty == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot scale quantity: section total is zero")
        factor = float(payload.new_quantity) / total_qty
        for i in items:
            if i.quantity is not None:
                i.quantity = round(float(i.quantity) * factor, 4)

    db.commit()
    _recompute_budget_total(db, budget_id)
    return {"message": "Section scaled", "items_updated": len(items)}


@router.post("/{budget_id}/line-items/batch")
def batch_update_line_items(budget_id: int, payload: BatchUpdateRequest, db: Session = Depends(get_db)):
    """Batch update multiple line items (DRAFT or REJECTED). REJECTED becomes DRAFT for resubmit."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    if not _is_editable(budget.status):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be edited")
    _allow_edit_and_reopen_if_rejected(db, budget)

    for u in payload.updates:
        item = db.query(BudgetLineItem).filter(
            BudgetLineItem.id == u.id,
            BudgetLineItem.budget_id == budget_id
        ).first()
        if not item:
            continue
        update_data = u.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
    db.commit()
    _recompute_budget_total(db, budget_id)
    return {"message": "Batch updated", "count": len(payload.updates)}


@router.delete("/{budget_id}/line-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_line_item(budget_id: int, item_id: int, db: Session = Depends(get_db)):
    """Delete a line item (DRAFT or REJECTED). REJECTED becomes DRAFT for resubmit."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    if not _is_editable(budget.status):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be edited")
    _allow_edit_and_reopen_if_rejected(db, budget)
    item = db.query(BudgetLineItem).filter(
        BudgetLineItem.id == item_id,
        BudgetLineItem.budget_id == budget_id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")
    db.delete(item)
    db.commit()
    _recompute_budget_total(db, budget_id)
    return None


@router.post("/{budget_id}/submit", response_model=BudgetResponse)
def submit_budget_for_approval(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Submit DRAFT budget to start approval workflow (DRAFT → PENDING_L1)."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    try:
        return submit_budget(budget, current_user, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) if settings.DEBUG else "Submit failed",
        ) from e


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    """Delete a budget (DRAFT or REJECTED only)."""

    budget = db.query(Budget).filter(Budget.id == budget_id).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget with ID {budget_id} not found"
        )

    if not _is_editable(budget.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only DRAFT or REJECTED budgets can be deleted"
        )

    # Delete associated file
    if budget.source_file:
        file_path = os.path.join(settings.UPLOAD_FOLDER, budget.source_file)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(budget)
    db.commit()
    return None


@router.get("/{budget_id}/stats")
def get_budget_stats(budget_id: int, db: Session = Depends(get_db)):
    """Get statistics for a budget"""

    budget = db.query(Budget).filter(Budget.id == budget_id).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget with ID {budget_id} not found"
        )

    # Calculate statistics
    stats = db.query(
        func.count(BudgetLineItem.id).label('total_items'),
        func.sum(BudgetLineItem.amount).label('total_amount'),
        func.avg(BudgetLineItem.amount).label('avg_amount'),
        func.min(BudgetLineItem.amount).label('min_amount'),
        func.max(BudgetLineItem.amount).label('max_amount')
    ).filter(BudgetLineItem.budget_id == budget_id).first()

    # Group by category
    category_stats = db.query(
        BudgetLineItem.category,
        func.count(BudgetLineItem.id).label('count'),
        func.sum(BudgetLineItem.amount).label('total')
    ).filter(
        BudgetLineItem.budget_id == budget_id
    ).group_by(BudgetLineItem.category).all()

    return {
        "budget_code": budget.budget_code,
        "fiscal_year": budget.fiscal_year,
        "overall": {
            "total_items": stats.total_items,
            "total_amount": float(stats.total_amount) if stats.total_amount else 0,
            "average_amount": float(stats.avg_amount) if stats.avg_amount else 0,
            "min_amount": float(stats.min_amount) if stats.min_amount else 0,
            "max_amount": float(stats.max_amount) if stats.max_amount else 0
        },
        "by_category": [
            {
                "category": cat.category or "Uncategorized",
                "count": cat.count,
                "total": float(cat.total)
            }
            for cat in category_stats
        ]
    }