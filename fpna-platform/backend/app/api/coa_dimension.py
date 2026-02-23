"""
COA Dimension API - Chart of Accounts Hierarchy Management

Provides endpoints for:
- Importing COA dimension from Excel
- Browsing COA hierarchy (for tree views)
- Searching accounts
- Getting accounts by budgeting group
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
from datetime import datetime

from app.database import get_db
from app.models.coa_dimension import COADimension, BudgetingGroup, BSClass
from app.models.user import User
from app.utils.dependencies import get_current_active_user
from app.services.coa_import_service import (
    import_coa_from_excel,
    get_coa_hierarchy,
    get_accounts_by_budgeting_group,
    search_accounts,
)
from app.config import settings

router = APIRouter(prefix="/coa-dimension", tags=["coa-dimension"])

os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)


@router.post("/import")
async def import_coa_dimension(
    file: UploadFile = File(...),
    sheet_name: str = Query("CBU_2", description="Sheet name in Excel file"),
    replace_existing: bool = Query(True, description="Replace existing records"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Import COA dimension from Excel file (MDS export format)
    
    Expected format:
    - Sheet with header row at index 1
    - Columns: COA_CODE, COA_NAME, BS_FLAG, BS_NAME, BS_GROUP, GROUP_NAME,
               BUDGETING_GROUPS, BUDGETING_GROUPS_NAME, P_L_flag_name, etc.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")
    
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in ['xlsx', 'xls']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Excel files are supported")
    
    # Save file temporarily
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_filename = f"coa_import_{timestamp}_{file.filename}"
    temp_filepath = os.path.join(settings.UPLOAD_FOLDER, temp_filename)
    
    contents = await file.read()
    with open(temp_filepath, 'wb') as f:
        f.write(contents)
    
    try:
        result = import_coa_from_excel(
            file_path=temp_filepath,
            db=db,
            sheet_name=sheet_name,
            replace_existing=replace_existing,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/import-from-uploads")
def import_from_uploads_folder(
    filename: str = Query("COA_Dimension.xlsx", description="Filename in uploads folder"),
    sheet_name: str = Query("CBU_2", description="Sheet name in Excel file"),
    replace_existing: bool = Query(True, description="Replace existing records"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Import COA dimension from a file already in the uploads folder"""
    file_path = os.path.join(settings.UPLOAD_FOLDER, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {filename}")
    
    result = import_coa_from_excel(
        file_path=file_path,
        db=db,
        sheet_name=sheet_name,
        replace_existing=replace_existing,
    )
    return result


@router.get("/hierarchy")
def get_hierarchy(db: Session = Depends(get_db)):
    """
    Get COA hierarchy for tree view
    
    Returns hierarchy organized by:
    BS Class -> Budgeting Group -> Accounts
    """
    return get_coa_hierarchy(db)


@router.get("/accounts")
def list_accounts(
    query: str = Query(None, description="Search term (code or name)"),
    bs_flag: int = Query(None, description="Filter by BS class (1=Assets, 2=Liabilities, 3=Capital, 9=Off-balance)"),
    budgeting_group: int = Query(None, description="Filter by budgeting group ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=2000),
    db: Session = Depends(get_db)
):
    """Search and list COA accounts with filters"""
    if query or bs_flag is not None or budgeting_group is not None:
        return search_accounts(db, query, bs_flag, budgeting_group, limit)
    
    # Default: return paginated list
    accounts = db.query(COADimension).filter(
        COADimension.is_active == True
    ).order_by(COADimension.coa_code).offset(skip).limit(limit).all()
    
    total = db.query(func.count(COADimension.id)).filter(
        COADimension.is_active == True
    ).scalar()
    
    return {
        'total': total,
        'accounts': [
            {
                'id': acc.id,
                'coa_code': acc.coa_code,
                'coa_name': acc.coa_name,
                'bs_flag': acc.bs_flag,
                'bs_name': acc.bs_name,
                'bs_group': acc.bs_group,
                'group_name': acc.group_name,
                'budgeting_groups': acc.budgeting_groups,
                'budgeting_groups_name': acc.budgeting_groups_name,
                'p_l_flag_name': acc.p_l_flag_name,
                'has_pl_impact': acc.has_pl_impact,
            }
            for acc in accounts
        ]
    }


@router.get("/accounts/{coa_code}")
def get_account(coa_code: str, db: Session = Depends(get_db)):
    """Get detailed information for a specific account"""
    account = db.query(COADimension).filter(
        COADimension.coa_code == coa_code
    ).first()
    
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    
    return {
        'id': account.id,
        'coa_code': account.coa_code,
        'coa_name': account.coa_name,
        'code': account.code,
        'name': account.name,
        'bs_flag': account.bs_flag,
        'bs_name': account.bs_name,
        'bs_group': account.bs_group,
        'group_name': account.group_name,
        'budgeting_groups': account.budgeting_groups,
        'budgeting_groups_name': account.budgeting_groups_name,
        'mkb_bs_group': account.mkb_bs_group,
        'bs_cbu_item_name': account.bs_cbu_item_name,
        'asset_liability_flag_1_name': account.asset_liability_flag_1_name,
        'p_l_flag': account.p_l_flag,
        'p_l_flag_name': account.p_l_flag_name,
        'p_l_sub_group_name': account.p_l_sub_group_name,
        'p_l_flag_name_rus': account.p_l_flag_name_rus,
        'is_balance_sheet': account.is_balance_sheet,
        'is_asset': account.is_asset,
        'is_liability': account.is_liability,
        'is_capital': account.is_capital,
        'is_off_balance': account.is_off_balance,
        'has_pl_impact': account.has_pl_impact,
        'validation_status': account.validation_status,
        'created_at': account.created_at.isoformat() if account.created_at else None,
    }


@router.get("/budgeting-groups")
def list_budgeting_groups(
    category: str = Query(None, description="Filter by category (ASSET, LIABILITY, CAPITAL, OFF_BALANCE)"),
    db: Session = Depends(get_db)
):
    """List all budgeting groups with account counts and BS class info"""
    from sqlalchemy import func as sql_func
    
    query = db.query(BudgetingGroup).filter(BudgetingGroup.is_active == True)
    
    if category:
        query = query.filter(BudgetingGroup.category == category.upper())
    
    groups = query.order_by(BudgetingGroup.display_order).all()
    
    # Get account counts per budgeting group
    account_counts = db.query(
        COADimension.budgeting_groups,
        sql_func.count(COADimension.id).label('count'),
        sql_func.min(COADimension.bs_flag).label('bs_flag')
    ).filter(
        COADimension.is_active == True,
        COADimension.budgeting_groups.isnot(None)
    ).group_by(COADimension.budgeting_groups).all()
    
    count_map = {row.budgeting_groups: {'count': row.count, 'bs_flag': row.bs_flag} for row in account_counts}
    
    # Get BS class names
    bs_classes = db.query(BSClass).all()
    bs_class_map = {bc.bs_flag: bc.name_en or bc.name_uz for bc in bs_classes}
    
    # Map category to bs_flag
    category_to_bs_flag = {
        'ASSET': 1,
        'LIABILITY': 2,
        'CAPITAL': 3,
        'OFF_BALANCE': 9,
    }
    
    result = []
    for g in groups:
        info = count_map.get(g.group_id, {'count': 0, 'bs_flag': None})
        bs_flag = info['bs_flag'] or category_to_bs_flag.get(g.category, 1)
        result.append({
            'id': g.id,
            'group_id': g.group_id,
            'group_name': g.name_en or g.name_ru or g.name_uz,
            'name_ru': g.name_ru,
            'name_en': g.name_en,
            'name_uz': g.name_uz,
            'category': g.category,
            'display_order': g.display_order,
            'bs_flag': bs_flag,
            'bs_name': bs_class_map.get(bs_flag, 'Unknown'),
            'account_count': info['count'],
        })
    
    return result


@router.get("/budgeting-groups/{group_id}/accounts")
def get_budgeting_group_accounts(group_id: int, db: Session = Depends(get_db)):
    """Get all accounts in a budgeting group"""
    return get_accounts_by_budgeting_group(db, group_id)


@router.get("/bs-classes")
def list_bs_classes(db: Session = Depends(get_db)):
    """List all balance sheet classes"""
    classes = db.query(BSClass).filter(BSClass.is_active == True).order_by(BSClass.display_order).all()
    
    return [
        {
            'id': c.id,
            'bs_flag': c.bs_flag,
            'name_uz': c.name_uz,
            'name_ru': c.name_ru,
            'name_en': c.name_en,
            'display_order': c.display_order,
        }
        for c in classes
    ]


@router.get("/stats")
def get_coa_stats(db: Session = Depends(get_db)):
    """Get COA dimension statistics"""
    total_accounts = db.query(func.count(COADimension.id)).filter(
        COADimension.is_active == True
    ).scalar()
    
    by_bs_flag = db.query(
        COADimension.bs_flag,
        COADimension.bs_name,
        func.count(COADimension.id)
    ).filter(
        COADimension.is_active == True
    ).group_by(COADimension.bs_flag, COADimension.bs_name).all()
    
    by_budgeting_group = db.query(
        COADimension.budgeting_groups,
        COADimension.budgeting_groups_name,
        func.count(COADimension.id)
    ).filter(
        COADimension.is_active == True,
        COADimension.budgeting_groups.isnot(None)
    ).group_by(COADimension.budgeting_groups, COADimension.budgeting_groups_name).all()
    
    pl_accounts = db.query(func.count(COADimension.id)).filter(
        COADimension.is_active == True,
        COADimension.p_l_flag.isnot(None)
    ).scalar()
    
    return {
        'total_accounts': total_accounts,
        'pl_accounts': pl_accounts,
        'by_bs_class': [
            {'bs_flag': bs_flag, 'bs_name': bs_name, 'count': count}
            for bs_flag, bs_name, count in by_bs_flag
        ],
        'by_budgeting_group': [
            {'group_id': group_id, 'group_name': group_name, 'count': count}
            for group_id, group_name, count in sorted(by_budgeting_group, key=lambda x: x[0] or 0)
        ],
    }
