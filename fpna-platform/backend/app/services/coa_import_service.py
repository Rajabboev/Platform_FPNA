"""
COA Dimension Import Service

Imports the CBU Chart of Accounts hierarchy from Excel files.
Supports the MDS export format with header row at index 1.
"""

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from app.models.coa_dimension import COADimension, BudgetingGroup, BSClass
from app.services.coa_product_taxonomy import classify_coa_row, resolve_coa_taxonomy

logger = logging.getLogger(__name__)


# Column mapping from Excel to model fields
COLUMN_MAPPING = {
    'COA_CODE': 'coa_code',
    'Code': 'code',
    'Name': 'name',
    'BS_FLAG': 'bs_flag',
    'BS_FLAG_1': 'bs_flag_1',
    'BS_NAME': 'bs_name',
    'BS_FLAG_1_Name': 'bs_flag_1_name',
    'BS_GROUP': 'bs_group',
    'GROUP_NAME': 'group_name',
    'COA_NAME': 'coa_name',
    'MKB_BS_GROUP_FLAG': 'mkb_bs_group_flag',
    'MKB_BS_GROUP': 'mkb_bs_group',
    'BS_CBU_sub_Item_group': 'bs_cbu_sub_item_group',
    'BS_CBU_Item_name': 'bs_cbu_item_name',
    'BS_CBU_sub_Item': 'bs_cbu_sub_item',
    'BS_CBU_sub_Item_name': 'bs_cbu_sub_item_name',
    'Asset_Liability_FLAG_1': 'asset_liability_flag_1',
    'Asset_Liability_FLAG_1_Name': 'asset_liability_flag_1_name',
    'Asset_Liability_FLAG_2': 'asset_liability_flag_2',
    'Asset_Liability_FLAG_2_Name': 'asset_liability_flag_2_name',
    'P_L_flag': 'p_l_flag',
    'P_L_flag_name': 'p_l_flag_name',
    'P_L_group': 'p_l_group',
    'P_L_sub_group': 'p_l_sub_group',
    'P_L_sub_group_name': 'p_l_sub_group_name',
    'P_L_sub_group_name_ru': 'p_l_sub_group_name_ru',
    'P_L_sub_group_name_rus': 'p_l_sub_group_name_rus',
    'P_L_FLAG_NAME_RUS': 'p_l_flag_name_rus',
    '$ValidationStatus$': 'validation_status',
}


def import_coa_from_excel(
    file_path: str,
    db: Session,
    sheet_name: str = 'CBU_2',
    header_row: int = 1,
    replace_existing: bool = True
) -> Dict[str, Any]:
    """
    Import COA dimension from Excel file
    
    Args:
        file_path: Path to the Excel file
        db: Database session
        sheet_name: Name of the sheet to read (default: CBU_2)
        header_row: Row index containing headers (default: 1)
        replace_existing: If True, delete existing records before import
    
    Returns:
        Dict with import statistics
    """
    try:
        # Read Excel file
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        
        # Filter only validated records
        if '$ValidationStatus$' in df.columns:
            df = df[df['$ValidationStatus$'] == 'Validation succeeded']
        
        # Filter out rows without COA_CODE
        df = df[df['COA_CODE'].notna()]
        
        total_rows = len(df)
        imported = 0
        updated = 0
        errors = []
        
        if replace_existing:
            # Delete existing records
            deleted = db.query(COADimension).delete()
            logger.info(f"Deleted {deleted} existing COA dimension records")
        
        # Import each row
        for idx, row in df.iterrows():
            try:
                coa_code = str(row['COA_CODE']).strip()
                
                # Check if record exists
                existing = None
                if not replace_existing:
                    existing = db.query(COADimension).filter(
                        COADimension.coa_code == coa_code
                    ).first()
                
                # Build record data
                record_data = {'coa_code': coa_code}
                for excel_col, model_field in COLUMN_MAPPING.items():
                    if excel_col in df.columns and excel_col != 'COA_CODE':
                        value = row.get(excel_col)
                        if pd.notna(value):
                            # Convert numeric fields
                            if model_field in ('bs_flag', 'bs_flag_1', 'bs_group',
                                              'p_l_flag', 'p_l_group', 'p_l_sub_group',
                                              'mkb_bs_group_flag', 'bs_cbu_sub_item_group',
                                              'bs_cbu_sub_item', 'asset_liability_flag_1',
                                              'asset_liability_flag_2'):
                                try:
                                    value = int(float(value))
                                except (ValueError, TypeError):
                                    value = None
                            record_data[model_field] = value
                
                if existing:
                    # Update existing record
                    for key, value in record_data.items():
                        setattr(existing, key, value)
                    updated += 1
                else:
                    # Create new record
                    coa_record = COADimension(**record_data)
                    db.add(coa_record)
                    imported += 1
                    
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
                logger.warning(f"Error importing row {idx}: {e}")
        
        db.commit()
        
        _populate_budgeting_groups(df, db)
        _populate_bs_classes(df, db)
        fpna_updated = sync_fpna_product_columns(db)
        
        return {
            'status': 'success',
            'total_rows': total_rows,
            'imported': imported,
            'updated': updated,
            'fpna_product_rows_updated': fpna_updated,
            'errors': errors[:20],  # First 20 errors
            'error_count': len(errors),
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"COA import failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
        }


def sync_fpna_product_columns(db: Session) -> int:
    """Persist FP&A product taxonomy on every coa_dimension row from classify rules."""
    rows = db.query(COADimension).all()
    for acc in rows:
        tax = classify_coa_row(acc)
        acc.fpna_product_key = tax['product_key'][:50]
        acc.fpna_product_label_en = (tax['product_label_en'] or '')[:500]
        acc.fpna_product_pillar = (tax['product_pillar'] or '')[:50]
        dg = tax.get('display_group') or '—'
        acc.fpna_display_group = str(dg)[:1000]
    db.commit()
    return len(rows)


def _populate_budgeting_groups(df: pd.DataFrame, db: Session):
    """Populate BudgetingGroup lookup from Excel when BUDGETING_GROUPS column exists (legacy)."""
    try:
        if 'BUDGETING_GROUPS' not in df.columns or df['BUDGETING_GROUPS'].isna().all():
            return
        bg_df = df[['BUDGETING_GROUPS', 'BUDGETING_GROUPS_NAME', 'BS_FLAG']].dropna(
            subset=['BUDGETING_GROUPS']
        ).drop_duplicates(subset=['BUDGETING_GROUPS'])
        
        # Delete existing
        db.query(BudgetingGroup).delete()
        
        for _, row in bg_df.iterrows():
            group_id = int(float(row['BUDGETING_GROUPS']))
            name_ru = row['BUDGETING_GROUPS_NAME'] if pd.notna(row['BUDGETING_GROUPS_NAME']) else f"Group {group_id}"
            bs_flag = int(float(row['BS_FLAG'])) if pd.notna(row['BS_FLAG']) else None
            
            # Determine category based on BS_FLAG
            category = None
            if bs_flag == 1:
                category = 'ASSET'
            elif bs_flag == 2:
                category = 'LIABILITY'
            elif bs_flag == 3:
                category = 'CAPITAL'
            elif bs_flag == 9:
                category = 'OFF_BALANCE'
            
            bg = BudgetingGroup(
                group_id=group_id,
                name_ru=name_ru,
                category=category,
                display_order=group_id,
            )
            db.add(bg)
        
        db.commit()
        logger.info(f"Populated {len(bg_df)} budgeting groups")
        
    except Exception as e:
        logger.warning(f"Error populating budgeting groups: {e}")


def _populate_bs_classes(df: pd.DataFrame, db: Session):
    """Populate BSClass lookup table from COA data"""
    try:
        # Get unique BS classes
        bs_df = df[['BS_FLAG', 'BS_NAME']].dropna().drop_duplicates()
        
        # Delete existing
        db.query(BSClass).delete()
        
        # English translations
        bs_names_en = {
            1: 'Assets',
            2: 'Liabilities',
            3: 'Capital',
            9: 'Off-Balance Sheet',
        }
        
        for _, row in bs_df.iterrows():
            bs_flag = int(float(row['BS_FLAG']))
            name_uz = row['BS_NAME']
            
            bs_class = BSClass(
                bs_flag=bs_flag,
                name_uz=name_uz,
                name_en=bs_names_en.get(bs_flag),
                display_order=bs_flag,
            )
            db.add(bs_class)
        
        db.commit()
        logger.info(f"Populated {len(bs_df)} BS classes")
        
    except Exception as e:
        logger.warning(f"Error populating BS classes: {e}")


def get_coa_hierarchy(db: Session) -> Dict[str, Any]:
    """
    Get COA hierarchy for frontend tree view
    Organized by: BS Class -> BS group -> FP&A product -> accounts
    """
    # Get all COA records
    coa_records = db.query(COADimension).filter(
        COADimension.is_active == True
    ).order_by(
        COADimension.bs_flag,
        COADimension.bs_group,
        COADimension.fpna_product_key,
        COADimension.coa_code,
    ).all()
    
    # Get BS classes
    bs_classes = db.query(BSClass).order_by(BSClass.display_order).all()
    bs_class_map = {bc.bs_flag: bc for bc in bs_classes}
    
    # Build hierarchy: BS Class -> BS Group -> FP&A product -> COA Account
    hierarchy = []
    
    for bs_class in bs_classes:
        # Get accounts for this class
        class_accounts = [c for c in coa_records if c.bs_flag == bs_class.bs_flag]
        if not class_accounts:
            continue
            
        # Group by bs_group (3-digit code from COA dimension).
        # When bs_group is NULL, treat as a special \"Unassigned\" bucket
        # instead of showing confusing code \"000\".
        bs_group_map = {}
        for acc in class_accounts:
            if acc.bs_group is None:
                bs_grp = "UNASSIGNED"
                grp_name = "Unassigned BS group"
            else:
                bs_grp = str(acc.bs_group)
                grp_name = acc.group_name or f"Group {bs_grp}"
            if bs_grp not in bs_group_map:
                bs_group_map[bs_grp] = {
                    'bs_group': bs_grp,
                    'group_name': grp_name,
                    'accounts': []
                }
            bs_group_map[bs_grp]['accounts'].append(acc)
        
        bs_groups_list = []
        for bs_grp, grp_data in sorted(bs_group_map.items(), key=lambda x: str(x[0])):
            product_map = {}
            for acc in grp_data['accounts']:
                tax = resolve_coa_taxonomy(acc)
                pk = tax['product_key']
                if pk not in product_map:
                    product_map[pk] = {
                        'product_key': pk,
                        'product_label_en': tax['product_label_en'],
                        'product_pillar': tax['product_pillar'],
                        'display_group': tax['display_group'],
                        'accounts': [],
                    }
                product_map[pk]['accounts'].append({
                    'coa_code': acc.coa_code,
                    'coa_name': acc.coa_name,
                    'has_pl_impact': acc.has_pl_impact,
                    **tax,
                })

            prod_list = sorted(product_map.values(), key=lambda x: x['product_label_en'] or '')
            bs_groups_list.append({
                'bs_group': bs_grp,
                'group_name': grp_data['group_name'],
                'products': prod_list,
                'account_count': len(grp_data['accounts']),
            })
        
        class_node = {
            'bs_flag': bs_class.bs_flag,
            'bs_name': bs_class.name_en or bs_class.name_uz,
            'bs_groups': bs_groups_list,
            'account_count': len(class_accounts),
        }
        hierarchy.append(class_node)
    
    return hierarchy


def get_accounts_by_budgeting_group(db: Session, group_id: int) -> List[Dict]:
    """Get all accounts in a budgeting group"""
    accounts = db.query(COADimension).filter(
        COADimension.budgeting_groups == group_id,
        COADimension.is_active == True
    ).order_by(COADimension.coa_code).all()
    
    return [
        {
            'coa_code': acc.coa_code,
            'coa_name': acc.coa_name,
            'bs_flag': acc.bs_flag,
            'bs_group': acc.bs_group,
            'group_name': acc.group_name,
            'has_pl_impact': acc.has_pl_impact,
            **resolve_coa_taxonomy(acc),
        }
        for acc in accounts
    ]


def search_accounts(
    db: Session,
    query: str = None,
    bs_flag: int = None,
    product_key: str = None,
    limit: int = 100
) -> List[Dict]:
    """Search COA accounts with filters (FP&A product_key, not CBU budgeting group)."""
    q = db.query(COADimension).filter(COADimension.is_active == True)
    
    if query:
        search_term = f"%{query}%"
        q = q.filter(
            (COADimension.coa_code.ilike(search_term)) |
            (COADimension.coa_name.ilike(search_term)) |
            (COADimension.group_name.ilike(search_term))
        )
    
    if bs_flag is not None:
        q = q.filter(COADimension.bs_flag == bs_flag)
    
    if product_key:
        pk = product_key.strip().upper()
        has_null_pk = (
            db.query(COADimension.id)
            .filter(COADimension.is_active == True, COADimension.fpna_product_key.is_(None))
            .limit(1)
            .first()
        )
        if has_null_pk:
            pool = q.order_by(COADimension.coa_code).limit(min(max(limit * 20, 200), 8000)).all()
            accounts = [a for a in pool if resolve_coa_taxonomy(a)["product_key"] == pk][:limit]
            return [
                {
                    'coa_code': acc.coa_code,
                    'coa_name': acc.coa_name,
                    'bs_flag': acc.bs_flag,
                    'bs_name': acc.bs_name,
                    'bs_group': acc.bs_group,
                    'group_name': acc.group_name,
                    'has_pl_impact': acc.has_pl_impact,
                    'fpna_product_key': acc.fpna_product_key,
                    'fpna_product_label_en': acc.fpna_product_label_en,
                    'fpna_product_pillar': acc.fpna_product_pillar,
                    'fpna_display_group': acc.fpna_display_group,
                    **resolve_coa_taxonomy(acc),
                }
                for acc in accounts
            ]
        q = q.filter(COADimension.fpna_product_key == pk)

    accounts = q.order_by(COADimension.coa_code).limit(limit).all()
    
    return [
        {
            'coa_code': acc.coa_code,
            'coa_name': acc.coa_name,
            'bs_flag': acc.bs_flag,
            'bs_name': acc.bs_name,
            'bs_group': acc.bs_group,
            'group_name': acc.group_name,
            'has_pl_impact': acc.has_pl_impact,
            'fpna_product_key': acc.fpna_product_key,
            'fpna_product_label_en': acc.fpna_product_label_en,
            'fpna_product_pillar': acc.fpna_product_pillar,
            'fpna_display_group': acc.fpna_display_group,
            **resolve_coa_taxonomy(acc),
        }
        for acc in accounts
    ]
