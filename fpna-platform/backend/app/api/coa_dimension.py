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
from app.services.coa_product_taxonomy import (
    TAXONOMY_BY_KEY,
    resolve_coa_taxonomy,
    taxonomy_definitions,
)
from app.services.coa_import_service import sync_fpna_product_columns
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
               P_L fields, etc. FP&A product buckets are derived and stored (fpna_product_*).
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
    BS Class -> BS group -> FP&A product -> accounts
    """
    return get_coa_hierarchy(db)


@router.post("/rebuild-fpna-products")
def rebuild_fpna_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Recompute and persist fpna_product_* on all coa_dimension rows (after upgrade or rule changes)."""
    n = sync_fpna_product_columns(db)
    return {"status": "success", "rows_updated": n}


@router.get("/accounts")
def list_accounts(
    query: str = Query(None, description="Search term (code or name)"),
    bs_flag: int = Query(None, description="Filter by BS class (1=Assets, 2=Liabilities, 3=Capital, 9=Off-balance)"),
    product_key: str = Query(None, description="Filter by FP&A product key (e.g. DEPOSITS)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=2000),
    db: Session = Depends(get_db)
):
    """Search and list COA accounts with filters"""
    if query or bs_flag is not None or product_key is not None:
        return search_accounts(db, query, bs_flag, product_key, limit)
    
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
                'p_l_flag_name': acc.p_l_flag_name,
                'has_pl_impact': acc.has_pl_impact,
                'fpna_product_key': acc.fpna_product_key,
                'fpna_product_label_en': acc.fpna_product_label_en,
                'fpna_product_pillar': acc.fpna_product_pillar,
                'fpna_display_group': acc.fpna_display_group,
                **resolve_coa_taxonomy(acc),
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
        'fpna_product_key': account.fpna_product_key,
        'fpna_product_label_en': account.fpna_product_label_en,
        'fpna_product_pillar': account.fpna_product_pillar,
        'fpna_display_group': account.fpna_display_group,
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
        **resolve_coa_taxonomy(account),
    }


@router.get("/budgeting-groups")
def list_budgeting_groups(
    category: str = Query(None, description="Filter by category (ASSET, LIABILITY, CAPITAL, OFF_BALANCE)"),
    db: Session = Depends(get_db)
):
    """Legacy CBU budgeting groups (lookup table). Prefer /product-taxonomy for FP&A planning."""
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


@router.get("/product-taxonomy")
def get_product_taxonomy():
    """
    FP&A product buckets derived from coa_dimension (Loans, Deposits, P&L slices, etc.).
    Stable keys for filters and reporting.
    """
    return {"items": taxonomy_definitions()}


@router.get("/product-summary")
def get_product_summary(db: Session = Depends(get_db)):
    """Account counts per product_key (uses stored fpna_product_key when set)."""
    rows = db.query(COADimension).filter(COADimension.is_active == True).all()
    counts: dict = {}
    for acc in rows:
        key = resolve_coa_taxonomy(acc)["product_key"]
        counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    unclassified = TAXONOMY_BY_KEY["UNCLASSIFIED"]
    return {
        "total_accounts": len(rows),
        "by_product": [
            {
                "product_key": k,
                "count": c,
                "label_en": TAXONOMY_BY_KEY.get(k, unclassified).label_en,
                "pillar": TAXONOMY_BY_KEY.get(k, unclassified).pillar,
            }
            for k, c in ordered
        ],
    }


@router.get("/accounts/by-product/{product_key}")
def list_accounts_by_product(
    product_key: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """All COA codes classified into the given product_key (scans active dimension)."""
    pk = product_key.strip().upper()
    valid = {t["key"] for t in taxonomy_definitions()}
    if pk not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown product_key. Use GET /coa-dimension/product-taxonomy for keys.",
        )
    has_null = (
        db.query(COADimension.id)
        .filter(COADimension.is_active == True, COADimension.fpna_product_key.is_(None))
        .limit(1)
        .first()
    )
    if not has_null:
        q = (
            db.query(COADimension)
            .filter(COADimension.is_active == True, COADimension.fpna_product_key == pk)
            .order_by(COADimension.coa_code)
        )
        rows = q.offset(skip).limit(limit).all()
        matched = [
            {
                "id": acc.id,
                "coa_code": acc.coa_code,
                "coa_name": acc.coa_name,
                "bs_flag": acc.bs_flag,
                "p_l_flag_name": acc.p_l_flag_name,
                "fpna_product_key": acc.fpna_product_key,
                "fpna_product_label_en": acc.fpna_product_label_en,
                **resolve_coa_taxonomy(acc),
            }
            for acc in rows
        ]
        return {"product_key": pk, "count_returned": len(matched), "accounts": matched}

    q = db.query(COADimension).filter(COADimension.is_active == True).order_by(COADimension.coa_code)
    matched = []
    for acc in q:
        tax = resolve_coa_taxonomy(acc)
        if tax["product_key"] != pk:
            continue
        if skip > 0:
            skip -= 1
            continue
        if len(matched) >= limit:
            break
        matched.append(
            {
                "id": acc.id,
                "coa_code": acc.coa_code,
                "coa_name": acc.coa_name,
                "bs_flag": acc.bs_flag,
                "p_l_flag_name": acc.p_l_flag_name,
                "fpna_product_key": acc.fpna_product_key,
                "fpna_product_label_en": acc.fpna_product_label_en,
                **tax,
            }
        )
    return {"product_key": pk, "count_returned": len(matched), "accounts": matched}


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
    
    by_product = db.query(
        COADimension.fpna_product_key,
        func.count(COADimension.id),
    ).filter(
        COADimension.is_active == True,
        COADimension.fpna_product_key.isnot(None),
    ).group_by(COADimension.fpna_product_key).all()

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
        'by_product': [
            {
                'product_key': pk,
                'label_en': TAXONOMY_BY_KEY.get(pk, TAXONOMY_BY_KEY['UNCLASSIFIED']).label_en,
                'count': cnt,
            }
            for pk, cnt in sorted(by_product, key=lambda x: (-x[1], x[0] or ''))
        ],
    }
