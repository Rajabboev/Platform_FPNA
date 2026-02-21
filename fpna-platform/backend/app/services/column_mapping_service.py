"""Column mapping service for universal data source upload.

Handles validation and transformation of source data to target budget schema.
"""
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
from decimal import Decimal


BUDGET_TARGET_SCHEMA = {
    "header": {
        "fiscal_year": {"type": "integer", "required": True, "description": "Budget fiscal year"},
        "department": {"type": "string", "required": False, "description": "Department name"},
        "branch": {"type": "string", "required": False, "description": "Branch/location"},
        "currency": {"type": "string", "required": False, "default": "USD", "description": "Currency code"},
        "description": {"type": "string", "required": False, "description": "Budget description"},
    },
    "line_items": {
        "account_code": {"type": "string", "required": True, "description": "Account code identifier"},
        "account_name": {"type": "string", "required": True, "description": "Account name/description"},
        "category": {"type": "string", "required": False, "description": "Category (Revenue, Expense, etc.)"},
        "month": {"type": "integer", "required": False, "description": "Month (1-12)"},
        "quarter": {"type": "integer", "required": False, "description": "Quarter (1-4)"},
        "year": {"type": "integer", "required": False, "description": "Year"},
        "amount": {"type": "decimal", "required": True, "description": "Amount value"},
        "quantity": {"type": "decimal", "required": False, "description": "Quantity"},
        "unit_price": {"type": "decimal", "required": False, "description": "Unit price"},
        "notes": {"type": "string", "required": False, "description": "Additional notes"},
    }
}

COMMON_ALIASES = {
    "account_code": ["acct_code", "acc_code", "account_id", "acct_id", "gl_code", "gl_account", "account_no", "account_number"],
    "account_name": ["acct_name", "acc_name", "account_desc", "account_description", "gl_name", "gl_description"],
    "category": ["type", "account_type", "category_name", "expense_type", "budget_category"],
    "month": ["period_month", "budget_month", "fiscal_month", "mo"],
    "quarter": ["qtr", "fiscal_quarter", "budget_quarter", "q"],
    "year": ["fiscal_year", "budget_year", "yr", "period_year"],
    "amount": ["value", "budget_amount", "amt", "total", "budget_value", "sum", "budget"],
    "quantity": ["qty", "units", "count", "volume"],
    "unit_price": ["price", "unit_cost", "rate", "cost_per_unit"],
    "notes": ["note", "comment", "comments", "description", "remarks", "memo"],
    "fiscal_year": ["year", "budget_year", "fy", "fiscal_yr"],
    "department": ["dept", "department_name", "dept_name", "division", "cost_center"],
    "branch": ["location", "branch_name", "office", "site", "region"],
    "currency": ["curr", "currency_code", "ccy"],
}


def get_target_schema() -> Dict[str, Any]:
    """Get the target budget schema definition."""
    return BUDGET_TARGET_SCHEMA


def get_required_fields(schema_type: str = "line_items") -> List[str]:
    """Get list of required fields for a schema type."""
    schema = BUDGET_TARGET_SCHEMA.get(schema_type, {})
    return [field for field, config in schema.items() if config.get("required", False)]


def get_optional_fields(schema_type: str = "line_items") -> List[str]:
    """Get list of optional fields for a schema type."""
    schema = BUDGET_TARGET_SCHEMA.get(schema_type, {})
    return [field for field, config in schema.items() if not config.get("required", False)]


def _similarity_score(s1: str, s2: str) -> float:
    """Calculate similarity between two strings."""
    s1_clean = s1.lower().replace("_", "").replace("-", "").replace(" ", "")
    s2_clean = s2.lower().replace("_", "").replace("-", "").replace(" ", "")
    return SequenceMatcher(None, s1_clean, s2_clean).ratio()


def suggest_mapping(
    source_columns: List[str],
    schema_type: str = "line_items",
    threshold: float = 0.6
) -> List[Dict[str, Any]]:
    """Suggest column mappings based on name similarity.
    
    Args:
        source_columns: List of source column names
        schema_type: Target schema type ("header" or "line_items")
        threshold: Minimum similarity score to suggest a mapping
        
    Returns:
        List of suggested mappings with confidence scores
    """
    schema = BUDGET_TARGET_SCHEMA.get(schema_type, {})
    suggestions = []
    used_targets = set()
    
    for source_col in source_columns:
        source_lower = source_col.lower().strip()
        best_match = None
        best_score = 0
        
        for target_field, config in schema.items():
            if target_field in used_targets:
                continue
            
            if source_lower == target_field.lower():
                best_match = target_field
                best_score = 1.0
                break
            
            aliases = COMMON_ALIASES.get(target_field, [])
            for alias in aliases:
                if source_lower == alias.lower():
                    best_match = target_field
                    best_score = 0.95
                    break
            
            if best_score >= 0.95:
                break
            
            score = _similarity_score(source_col, target_field)
            if score > best_score:
                best_score = score
                best_match = target_field
            
            for alias in aliases:
                score = _similarity_score(source_col, alias)
                if score > best_score:
                    best_score = score
                    best_match = target_field
        
        suggestion = {
            "source_column": source_col,
            "suggested_target": best_match if best_score >= threshold else None,
            "confidence": round(best_score, 2) if best_score >= threshold else 0,
            "required": schema.get(best_match, {}).get("required", False) if best_match else False
        }
        
        if best_match and best_score >= threshold:
            used_targets.add(best_match)
        
        suggestions.append(suggestion)
    
    return suggestions


def validate_mapping(
    mapping: List[Dict[str, str]],
    source_columns: List[str],
    schema_type: str = "line_items"
) -> Dict[str, Any]:
    """Validate a column mapping configuration.
    
    Args:
        mapping: List of {"source_column": str, "target_field": str}
        source_columns: Available source columns
        schema_type: Target schema type
        
    Returns:
        Validation result with errors and warnings
    """
    schema = BUDGET_TARGET_SCHEMA.get(schema_type, {})
    required_fields = get_required_fields(schema_type)
    
    errors = []
    warnings = []
    
    mapped_targets = {}
    for m in mapping:
        source = m.get("source_column")
        target = m.get("target_field")
        
        if not source or not target:
            continue
        
        if source not in source_columns:
            errors.append(f"Source column '{source}' not found in data")
        
        if target not in schema:
            errors.append(f"Target field '{target}' is not a valid budget field")
        
        if target in mapped_targets:
            warnings.append(f"Target field '{target}' is mapped multiple times")
        
        mapped_targets[target] = source
    
    for required in required_fields:
        if required not in mapped_targets:
            errors.append(f"Required field '{required}' is not mapped")
    
    unmapped_sources = [col for col in source_columns if col not in [m.get("source_column") for m in mapping]]
    if unmapped_sources:
        warnings.append(f"Unmapped source columns: {', '.join(unmapped_sources[:5])}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "mapped_fields": list(mapped_targets.keys()),
        "missing_required": [f for f in required_fields if f not in mapped_targets],
        "coverage": {
            "required": len([f for f in required_fields if f in mapped_targets]),
            "required_total": len(required_fields),
            "optional": len([f for f in mapped_targets if f not in required_fields]),
            "optional_total": len(schema) - len(required_fields)
        }
    }


def apply_mapping(
    df: pd.DataFrame,
    mapping: List[Dict[str, str]],
    schema_type: str = "line_items"
) -> pd.DataFrame:
    """Apply column mapping to transform source data to target schema.
    
    Args:
        df: Source DataFrame
        mapping: List of {"source_column": str, "target_field": str}
        schema_type: Target schema type
        
    Returns:
        Transformed DataFrame with target column names
    """
    schema = BUDGET_TARGET_SCHEMA.get(schema_type, {})
    
    mapping_dict = {m["source_column"]: m["target_field"] for m in mapping if m.get("source_column") and m.get("target_field")}
    
    result_df = pd.DataFrame()
    
    for source_col, target_field in mapping_dict.items():
        if source_col in df.columns and target_field in schema:
            result_df[target_field] = df[source_col]
    
    for target_field, config in schema.items():
        if target_field not in result_df.columns:
            if "default" in config:
                result_df[target_field] = config["default"]
    
    result_df = _convert_types(result_df, schema)
    
    return result_df


def _convert_types(df: pd.DataFrame, schema: Dict[str, Any]) -> pd.DataFrame:
    """Convert DataFrame columns to expected types."""
    for col in df.columns:
        if col not in schema:
            continue
        
        expected_type = schema[col].get("type")
        
        try:
            if expected_type == "integer":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            elif expected_type == "decimal":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            elif expected_type == "string":
                df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        except Exception:
            pass
    
    return df


def transform_to_budget_format(
    df: pd.DataFrame,
    mapping: List[Dict[str, str]],
    header_values: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Transform mapped data to budget import format.
    
    Args:
        df: Source DataFrame
        mapping: Column mapping configuration
        header_values: Optional header field values (fiscal_year, department, etc.)
        
    Returns:
        Dict with "header" and "line_items" ready for budget creation
    """
    line_items_df = apply_mapping(df, mapping, "line_items")
    
    header = {
        "fiscal_year": header_values.get("fiscal_year") if header_values else None,
        "department": header_values.get("department", "") if header_values else "",
        "branch": header_values.get("branch", "") if header_values else "",
        "currency": header_values.get("currency", "USD") if header_values else "USD",
        "description": header_values.get("description", "") if header_values else "",
    }
    
    if header["fiscal_year"] is None:
        if "year" in line_items_df.columns:
            years = line_items_df["year"].dropna().unique()
            if len(years) > 0:
                header["fiscal_year"] = int(years[0])
        if header["fiscal_year"] is None:
            from datetime import datetime
            header["fiscal_year"] = datetime.now().year
    
    line_items = []
    for _, row in line_items_df.iterrows():
        item = {}
        for col in line_items_df.columns:
            val = row[col]
            if pd.isna(val):
                item[col] = None
            elif isinstance(val, (int, float)):
                item[col] = float(val) if col in ["amount", "quantity", "unit_price"] else int(val) if col in ["month", "quarter", "year"] else val
            else:
                item[col] = str(val) if val else None
        
        if item.get("account_code") and item.get("account_name"):
            line_items.append(item)
    
    total_amount = sum(item.get("amount", 0) or 0 for item in line_items)
    
    return {
        "header": header,
        "line_items": line_items,
        "total_amount": total_amount,
        "summary": {
            "total_items": len(line_items),
            "total_amount": total_amount,
            "categories": list(set(item.get("category") for item in line_items if item.get("category")))
        }
    }
