"""
Budget Template API endpoints
Handles template management, assignments, and pre-filling
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date
from decimal import Decimal

from app.database import get_db
from app.models.template import (
    BudgetTemplate, TemplateSection, TemplateAssignment, 
    TemplateLineItem, TemplateType, TemplateStatus
)
from app.models.business_unit import BusinessUnit
from app.services.template_service import TemplateService
from app.schemas.template import (
    BudgetTemplateCreate, BudgetTemplateUpdate, BudgetTemplateResponse, BudgetTemplateDetail,
    TemplateSectionCreate, TemplateSectionUpdate, TemplateSectionResponse,
    TemplateAssignmentCreate, TemplateAssignmentUpdate, TemplateAssignmentResponse, 
    TemplateAssignmentDetail, BulkAssignmentCreate,
    TemplateLineItemCreate, TemplateLineItemUpdate, TemplateLineItemResponse, TemplateLineItemDetail,
    PrefilledTemplateRequest, PrefilledTemplateResponse,
    TemplateSubmissionRequest, TemplateSubmissionResponse,
    TemplateType as SchemaTemplateType, TemplateStatus as SchemaTemplateStatus
)

router = APIRouter(prefix="/templates", tags=["Budget Templates"])


@router.get("", response_model=List[BudgetTemplateResponse])
def list_templates(
    template_type: Optional[SchemaTemplateType] = None,
    status: Optional[SchemaTemplateStatus] = None,
    fiscal_year: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all budget templates"""
    query = db.query(BudgetTemplate)

    if template_type:
        query = query.filter(BudgetTemplate.template_type == template_type.value)
    if status:
        query = query.filter(BudgetTemplate.status == status.value)
    if fiscal_year:
        query = query.filter(BudgetTemplate.fiscal_year == fiscal_year)
    if is_active is not None:
        query = query.filter(BudgetTemplate.is_active == is_active)

    return query.order_by(BudgetTemplate.display_order, BudgetTemplate.code).all()


@router.post("", response_model=BudgetTemplateResponse, status_code=201)
def create_template(
    data: BudgetTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new budget template"""
    existing = db.query(BudgetTemplate).filter(BudgetTemplate.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Template with code {data.code} already exists")

    template_data = data.model_dump(exclude={"sections"})
    template = BudgetTemplate(**template_data)
    db.add(template)
    db.flush()

    if data.sections:
        for i, section_data in enumerate(data.sections):
            section = TemplateSection(
                template_id=template.id,
                **section_data.model_dump(),
                display_order=section_data.display_order or i
            )
            db.add(section)

    db.commit()
    db.refresh(template)
    return template


@router.post("/seed", response_model=dict)
def seed_templates(db: Session = Depends(get_db)):
    """Seed default templates"""
    service = TemplateService(db)
    created = service.seed_default_templates()
    return {"created": created}


sections_router = APIRouter(prefix="/sections", tags=["Template Sections"])


@sections_router.get("", response_model=List[TemplateSectionResponse])
def list_sections(
    template_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List template sections"""
    query = db.query(TemplateSection)

    if template_code:
        template = db.query(BudgetTemplate).filter(BudgetTemplate.code == template_code).first()
        if template:
            query = query.filter(TemplateSection.template_id == template.id)

    return query.order_by(TemplateSection.display_order).all()


@sections_router.post("", response_model=TemplateSectionResponse, status_code=201)
def create_section(
    data: TemplateSectionCreate,
    db: Session = Depends(get_db)
):
    """Create a template section"""
    template = db.query(BudgetTemplate).filter(BudgetTemplate.id == data.template_id).first()
    if not template:
        raise HTTPException(status_code=400, detail="Template not found")

    section = TemplateSection(**data.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@sections_router.get("/{section_id}", response_model=TemplateSectionResponse)
def get_section(section_id: int, db: Session = Depends(get_db)):
    """Get section by ID"""
    section = db.query(TemplateSection).filter(TemplateSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section


@sections_router.patch("/{section_id}", response_model=TemplateSectionResponse)
def update_section(
    section_id: int,
    data: TemplateSectionUpdate,
    db: Session = Depends(get_db)
):
    """Update section"""
    section = db.query(TemplateSection).filter(TemplateSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(section, field, value)

    db.commit()
    db.refresh(section)
    return section


@sections_router.delete("/{section_id}")
def delete_section(section_id: int, db: Session = Depends(get_db)):
    """Delete section"""
    section = db.query(TemplateSection).filter(TemplateSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    db.delete(section)
    db.commit()
    return {"message": "Section deleted"}


router.include_router(sections_router)


assignments_router = APIRouter(prefix="/assignments", tags=["Template Assignments"])


@assignments_router.get("", response_model=List[TemplateAssignmentDetail])
def list_assignments(
    template_code: Optional[str] = None,
    business_unit_code: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List template assignments"""
    query = db.query(TemplateAssignment)

    if template_code:
        template = db.query(BudgetTemplate).filter(BudgetTemplate.code == template_code).first()
        if template:
            query = query.filter(TemplateAssignment.template_id == template.id)

    if business_unit_code:
        bu = db.query(BusinessUnit).filter(BusinessUnit.code == business_unit_code).first()
        if bu:
            query = query.filter(TemplateAssignment.business_unit_id == bu.id)

    if fiscal_year:
        query = query.filter(TemplateAssignment.fiscal_year == fiscal_year)
    if status:
        query = query.filter(TemplateAssignment.status == status)

    assignments = query.order_by(TemplateAssignment.fiscal_year.desc()).all()

    results = []
    for assignment in assignments:
        template = db.query(BudgetTemplate).filter(BudgetTemplate.id == assignment.template_id).first()
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == assignment.business_unit_id).first()

        results.append(TemplateAssignmentDetail(
            **{c.name: getattr(assignment, c.name) for c in assignment.__table__.columns},
            template_code=template.code if template else "",
            template_name=template.name_en if template else "",
            business_unit_code=bu.code if bu else "",
            business_unit_name=bu.name_en if bu else ""
        ))

    return results


@assignments_router.post("", response_model=TemplateAssignmentResponse, status_code=201)
def create_assignment(
    data: TemplateAssignmentCreate,
    db: Session = Depends(get_db)
):
    """Create template assignment"""
    service = TemplateService(db)
    
    try:
        assignment = service.assign_to_business_unit(
            template_id=data.template_id,
            business_unit_id=data.business_unit_id,
            fiscal_year=data.fiscal_year,
            deadline=data.deadline
        )
        return assignment
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@assignments_router.post("/bulk", response_model=dict, status_code=201)
def bulk_create_assignments(
    data: BulkAssignmentCreate,
    db: Session = Depends(get_db)
):
    """Bulk create assignments"""
    service = TemplateService(db)
    
    assignments = service.bulk_assign(
        template_id=data.template_id,
        business_unit_ids=data.business_unit_ids,
        fiscal_year=data.fiscal_year,
        deadline=data.deadline
    )
    
    return {"created": len(assignments)}


@assignments_router.get("/{assignment_id}", response_model=TemplateAssignmentDetail)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    """Get assignment by ID"""
    assignment = db.query(TemplateAssignment).filter(
        TemplateAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    template = db.query(BudgetTemplate).filter(BudgetTemplate.id == assignment.template_id).first()
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == assignment.business_unit_id).first()

    return TemplateAssignmentDetail(
        **{c.name: getattr(assignment, c.name) for c in assignment.__table__.columns},
        template_code=template.code if template else "",
        template_name=template.name_en if template else "",
        business_unit_code=bu.code if bu else "",
        business_unit_name=bu.name_en if bu else ""
    )


@assignments_router.patch("/{assignment_id}", response_model=TemplateAssignmentResponse)
def update_assignment(
    assignment_id: int,
    data: TemplateAssignmentUpdate,
    db: Session = Depends(get_db)
):
    """Update assignment"""
    assignment = db.query(TemplateAssignment).filter(
        TemplateAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assignment, field, value)

    db.commit()
    db.refresh(assignment)
    return assignment


@assignments_router.delete("/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db)):
    """Delete assignment"""
    assignment = db.query(TemplateAssignment).filter(
        TemplateAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.status == "submitted":
        raise HTTPException(status_code=400, detail="Cannot delete submitted assignment")

    db.delete(assignment)
    db.commit()
    return {"message": "Assignment deleted"}


@assignments_router.post("/{assignment_id}/prefill", response_model=PrefilledTemplateResponse)
def prefill_template(
    assignment_id: int,
    baseline_version: Optional[int] = None,
    apply_drivers: bool = True,
    db: Session = Depends(get_db)
):
    """Generate pre-filled template with baseline data"""
    service = TemplateService(db)
    
    try:
        result = service.generate_prefilled_template(
            assignment_id=assignment_id,
            baseline_version=baseline_version,
            apply_drivers=apply_drivers
        )
        return PrefilledTemplateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@assignments_router.post("/{assignment_id}/submit", response_model=TemplateSubmissionResponse)
def submit_template(
    assignment_id: int,
    submitted_by_user_id: int = Query(...),
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Submit filled template for approval"""
    service = TemplateService(db)
    
    try:
        assignment, passed, errors = service.submit_template(
            assignment_id=assignment_id,
            submitted_by_user_id=submitted_by_user_id,
            notes=notes
        )
        return TemplateSubmissionResponse(
            assignment_id=assignment.id,
            status=assignment.status,
            submitted_at=assignment.submitted_at,
            submitted_by_user_id=submitted_by_user_id,
            validation_passed=passed,
            validation_errors=errors
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


router.include_router(assignments_router)


line_items_router = APIRouter(prefix="/line-items", tags=["Template Line Items"])


@line_items_router.get("", response_model=List[TemplateLineItemResponse])
def list_line_items(
    assignment_id: int,
    section_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List line items for an assignment"""
    query = db.query(TemplateLineItem).filter(
        TemplateLineItem.assignment_id == assignment_id
    )

    if section_id:
        query = query.filter(TemplateLineItem.section_id == section_id)

    return query.order_by(TemplateLineItem.account_code).all()


@line_items_router.get("/{line_item_id}", response_model=TemplateLineItemDetail)
def get_line_item(line_item_id: int, db: Session = Depends(get_db)):
    """Get line item by ID"""
    item = db.query(TemplateLineItem).filter(
        TemplateLineItem.id == line_item_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    from app.models.coa import Account
    account = db.query(Account).filter(Account.code == item.account_code).first()

    variance = item.adjusted_total - item.baseline_total
    variance_pct = (variance / item.baseline_total * 100) if item.baseline_total != 0 else None

    return TemplateLineItemDetail(
        **{c.name: getattr(item, c.name) for c in item.__table__.columns},
        account_name=account.name_en if account else None,
        baseline_total=item.baseline_total,
        adjusted_total=item.adjusted_total,
        variance=variance,
        variance_percent=variance_pct
    )


@line_items_router.patch("/{line_item_id}", response_model=TemplateLineItemResponse)
def update_line_item(
    line_item_id: int,
    data: TemplateLineItemUpdate,
    db: Session = Depends(get_db)
):
    """Update line item adjusted values"""
    service = TemplateService(db)
    
    try:
        adjusted_values = {}
        if data.adjusted:
            adjusted_values = data.adjusted.model_dump()
        
        item = service.update_line_item(
            line_item_id=line_item_id,
            adjusted_values=adjusted_values,
            notes=data.adjustment_notes
        )
        return item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


router.include_router(line_items_router)


@router.get("/{code}", response_model=BudgetTemplateDetail)
def get_template(code: str, db: Session = Depends(get_db)):
    """Get template by code with sections"""
    template = db.query(BudgetTemplate).filter(BudgetTemplate.code == code).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    sections = db.query(TemplateSection).filter(
        TemplateSection.template_id == template.id
    ).order_by(TemplateSection.display_order).all()

    assignment_count = db.query(func.count(TemplateAssignment.id)).filter(
        TemplateAssignment.template_id == template.id
    ).scalar()

    return BudgetTemplateDetail(
        **{c.name: getattr(template, c.name) for c in template.__table__.columns},
        sections=sections,
        assignment_count=assignment_count
    )


@router.patch("/{code}", response_model=BudgetTemplateResponse)
def update_template(
    code: str,
    data: BudgetTemplateUpdate,
    db: Session = Depends(get_db)
):
    """Update template"""
    template = db.query(BudgetTemplate).filter(BudgetTemplate.code == code).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/{code}")
def delete_template(code: str, db: Session = Depends(get_db)):
    """Delete template"""
    template = db.query(BudgetTemplate).filter(BudgetTemplate.code == code).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    assignments = db.query(TemplateAssignment).filter(
        TemplateAssignment.template_id == template.id
    ).count()

    if assignments > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete template with {assignments} active assignments"
        )

    db.delete(template)
    db.commit()
    return {"message": "Template deleted"}


@router.post("/{code}/activate", response_model=BudgetTemplateResponse)
def activate_template(code: str, db: Session = Depends(get_db)):
    """Activate a template"""
    service = TemplateService(db)
    template = db.query(BudgetTemplate).filter(BudgetTemplate.code == code).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        template = service.activate_template(template.id)
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{code}/clone", response_model=BudgetTemplateResponse)
def clone_template(
    code: str,
    new_code: str = Query(...),
    new_fiscal_year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Clone an existing template"""
    service = TemplateService(db)
    template = db.query(BudgetTemplate).filter(BudgetTemplate.code == code).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        new_template = service.clone_template(template.id, new_code, new_fiscal_year)
        return new_template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
