"""
FP&A product taxonomy for coa_dimension.

Classification uses BS class, P&L flags, CBU/MKB text fields, and keyword hints (EN/RU/UZ).
Persisted columns on COADimension (fpna_product_*) are filled on import / rebuild; runtime
uses resolve_coa_taxonomy() so stored values override re-classification when present.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Import only for type hints / runtime isinstance
try:
    from app.models.coa_dimension import COADimension
except ImportError:
    COADimension = Any  # type: ignore


def _norm(text: Optional[str]) -> str:
    if not text or not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text).lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _blob(acc: Any) -> str:
    """Concatenate descriptive COA fields for keyword search (no CBU budgeting group — unreliable for FP&A)."""
    parts = [
        getattr(acc, "coa_name", None),
        getattr(acc, "group_name", None),
        getattr(acc, "bs_name", None),
        getattr(acc, "bs_cbu_item_name", None),
        getattr(acc, "bs_cbu_sub_item_name", None),
        getattr(acc, "mkb_bs_group", None),
        getattr(acc, "asset_liability_flag_1_name", None),
        getattr(acc, "asset_liability_flag_2_name", None),
        getattr(acc, "p_l_flag_name", None),
        getattr(acc, "p_l_sub_group_name", None),
        getattr(acc, "p_l_sub_group_name_ru", None),
        getattr(acc, "p_l_flag_name_rus", None),
        getattr(acc, "name", None),
    ]
    return _norm(" ".join(p for p in parts if p))


def _any_kw(blob: str, kws: Tuple[str, ...]) -> bool:
    return any(k in blob for k in kws)


@dataclass(frozen=True)
class ProductTaxonomyItem:
    key: str
    label_en: str
    pillar: str  # BALANCE_SHEET | INCOME | CAPITAL | OFF_BALANCE


# Canonical list (order = API / docs order)
TAXONOMY: Tuple[ProductTaxonomyItem, ...] = (
    ProductTaxonomyItem("LOANS", "Loans", "BALANCE_SHEET"),
    ProductTaxonomyItem("DEPOSITS", "Deposits", "BALANCE_SHEET"),
    ProductTaxonomyItem("RESERVES", "Reserves & provisions", "BALANCE_SHEET"),
    ProductTaxonomyItem("CASH_LIQUID", "Cash & liquid assets", "BALANCE_SHEET"),
    ProductTaxonomyItem("SECURITIES_INVEST", "Securities & investments", "BALANCE_SHEET"),
    ProductTaxonomyItem("FIXED_ASSETS", "Fixed assets (PP&E)", "BALANCE_SHEET"),
    ProductTaxonomyItem("ASSETS_OTHER", "Other assets", "BALANCE_SHEET"),
    ProductTaxonomyItem("LIABS_CARDS", "Card & payment liabilities", "BALANCE_SHEET"),
    ProductTaxonomyItem("LIABS_CBU", "CBU & regulatory liabilities", "BALANCE_SHEET"),
    ProductTaxonomyItem("LIABS_OTHER", "Other liabilities", "BALANCE_SHEET"),
    ProductTaxonomyItem("REV_INTEREST", "Revenue — interest income", "INCOME"),
    ProductTaxonomyItem("REV_NONINTEREST", "Revenue — non-interest income", "INCOME"),
    ProductTaxonomyItem("EXP_INTEREST", "Expenses — interest expense", "INCOME"),
    ProductTaxonomyItem("EXP_NONINTEREST", "Expenses — non-interest (banking)", "INCOME"),
    ProductTaxonomyItem("OPEX", "Operating expenses (OPEX)", "INCOME"),
    ProductTaxonomyItem("CAPEX_PNL", "Capital-related P&L (depreciation / amortization)", "INCOME"),
    ProductTaxonomyItem("TAX", "Taxes", "INCOME"),
    ProductTaxonomyItem("CAPITAL", "Capital & equity", "CAPITAL"),
    ProductTaxonomyItem("OFF_BALANCE", "Off-balance sheet", "OFF_BALANCE"),
    ProductTaxonomyItem("UNCLASSIFIED", "Unclassified", "BALANCE_SHEET"),
)

TAXONOMY_BY_KEY = {t.key: t for t in TAXONOMY}
# Order used when listing departments / product owners (Loans before Deposits, …).
TAXONOMY_ORDER_INDEX: Dict[str, int] = {t.key: i for i, t in enumerate(TAXONOMY)}


def department_list_sort_key(
    primary_product_key: Optional[str],
    display_order: int,
    name_en: Optional[str],
) -> Tuple[int, int, int, str]:
    """
    Sort key for UI lists: product owners follow canonical taxonomy order;
    departments without primary_product_key sort after.
    """
    pk = (primary_product_key or "").strip().upper() or None
    if pk and pk in TAXONOMY_ORDER_INDEX:
        return (0, TAXONOMY_ORDER_INDEX[pk], display_order or 0, (name_en or "").lower())
    return (1, 0, display_order or 0, (name_en or "").lower())

# Keyword packs (lowercase / normalized)
_KW_LOAN = (
    "loan", "loans", "kredit", "credit", "lending", "кредит", "кредиты",
    "qarz", "ипотека", "mortgage", "microloan",
)
_KW_DEPOSIT = (
    "deposit", "депозит", "muddatli", "жамғарма", "savings", "current account",
    "текущий счет", "oqim", "депозитлар", "омадий",
)
_KW_RESERVE = (
    "provision", "reserve", "zaxira", "резерв", "резервы", "allowance",
    "impairment", "npl", "узгариш", "ожидаемый кредитный убыток",
)
_KW_CASH = (
    "cash", "нақд", "накт", "nostro", "loro", "correspondent", "лоро", "ностро",
    "касса", "cassa", "money market", "cbu account", "цб ру",
)
_KW_SEC = (
    "security", "securities", "bond", "облигац", "ценная бумага", "investment",
    "инвестиц", "portfolio", "валютный резерв",
)
_KW_FIXED = (
    "fixed asset", "ppe", "property", "equipment", "building", "амортизация актив",
    "основное средство", "инвентарь", "vehicle",
)
_KW_CARD = (
    "card", "plastic", "visa", "mastercard", "humo", "uzcard", "пластик",
    "карта", "карталар", "payment system",
)
_KW_CBU_LIAB = (
    "cbu", "цбу", "mkk", "regulator", "обязательн", "mandatory", "резерв треб",
    "обязательства перед", "nostro liability",
)
_KW_INT_INC = (
    "interest income", "interest rev", "foiz daromad", "процентный доход",
    "доход от процент", "келиши фоиз",
)
_KW_NONINT_INC = (
    "non-interest", "noninterest", "commission", "fee income", "комиссион",
    "service charge", "валютная разница", "fx gain", "dividend income",
)
_KW_INT_EXP = (
    "interest expense", "interest exp", "процентный расход", "расход по процент",
    "foiz xarajat", "deposit interest expense",
)
_KW_NONINT_EXP = (
    "non-interest exp", "administrativ", "general exp", "banking exp",
    "операционные расходы", "банковские расходы",
)
_KW_OPEX = (
    "salary", "wage", "payroll", "staff", "personnel", "rent", "lease",
    "utilities", "marketing", "advertising", "it service", "software",
    "заработная плата", "фонд оплаты", "аренда", "коммунал",
    "иш хақи", "ходимлар",
)
_KW_CAPEX_PNL = (
    "depreciation", "amortization", "амортизация", "эслатма актив",
    "wear", "fixed asset disposal",
)
_KW_TAX = (
    "tax", "налог", "солиқ", "income tax", "profit tax",
)


def resolve_coa_taxonomy(acc: Any) -> Dict[str, Any]:
    """
    Prefer persisted dim columns; otherwise classify from BS/P&L/COA text.
    Use this anywhere FP&A product bucket is needed (API, baseline, hierarchy).
    """
    pk_stored = getattr(acc, "fpna_product_key", None)
    if pk_stored and str(pk_stored).strip():
        pk = str(pk_stored).strip().upper()
        t = TAXONOMY_BY_KEY.get(pk, TAXONOMY_BY_KEY["UNCLASSIFIED"])
        label = getattr(acc, "fpna_product_label_en", None) or t.label_en
        pillar = getattr(acc, "fpna_product_pillar", None) or t.pillar
        dg = getattr(acc, "fpna_display_group", None)
        if not dg or not str(dg).strip():
            dg = _display_group_name(acc)
        return {
            "product_key": t.key,
            "product_label_en": label,
            "product_pillar": pillar,
            "display_group": dg if dg else "—",
        }
    return classify_coa_row(acc)


def classify_coa_row(acc: Any) -> Dict[str, Any]:
    """
    Return product taxonomy + display group for one COADimension row (or duck-typed dict).
    """
    bs_flag = getattr(acc, "bs_flag", None)
    pl_flag = getattr(acc, "p_l_flag", None)
    b = _blob(acc)

    display_group = _display_group_name(acc)

    # Off-balance & capital first
    if bs_flag == 9:
        return _out("OFF_BALANCE", display_group)
    if bs_flag == 3:
        return _out("CAPITAL", display_group)

    # P&L accounts (CBU export usually sets p_l_flag for income statement lines)
    if pl_flag is not None:
        if _any_kw(b, _KW_INT_INC):
            return _out("REV_INTEREST", display_group)
        if _any_kw(b, _KW_INT_EXP):
            return _out("EXP_INTEREST", display_group)
        if _any_kw(b, _KW_TAX):
            return _out("TAX", display_group)
        if _any_kw(b, _KW_CAPEX_PNL):
            return _out("CAPEX_PNL", display_group)
        if _any_kw(b, _KW_OPEX):
            return _out("OPEX", display_group)
        if _any_kw(b, _KW_NONINT_EXP):
            return _out("EXP_NONINTEREST", display_group)
        if _any_kw(b, _KW_NONINT_INC):
            return _out("REV_NONINTEREST", display_group)
        # Broad P&L heuristics from flag names
        if _any_kw(b, ("доход", "income", "revenue", "daromad", "прибыл")) and _any_kw(
            b, ("процент", "interest", "foiz")
        ):
            return _out("REV_INTEREST", display_group)
        if _any_kw(b, ("расход", "expense", "xarajat")) and _any_kw(
            b, ("процент", "interest", "foiz")
        ):
            return _out("EXP_INTEREST", display_group)
        if _any_kw(b, ("доход", "income", "revenue", "daromad")):
            return _out("REV_NONINTEREST", display_group)
        if _any_kw(b, ("расход", "expense", "xarajat")):
            return _out("OPEX", display_group)
        return _out("EXP_NONINTEREST", display_group)

    # Balance sheet — assets
    if bs_flag == 1:
        if _any_kw(b, _KW_LOAN):
            return _out("LOANS", display_group)
        if _any_kw(b, _KW_RESERVE) and not _any_kw(b, _KW_LOAN):
            return _out("RESERVES", display_group)
        if _any_kw(b, _KW_CASH):
            return _out("CASH_LIQUID", display_group)
        if _any_kw(b, _KW_SEC):
            return _out("SECURITIES_INVEST", display_group)
        if _any_kw(b, _KW_FIXED):
            return _out("FIXED_ASSETS", display_group)
        return _out("ASSETS_OTHER", display_group)

    # Balance sheet — liabilities
    if bs_flag == 2:
        if _any_kw(b, _KW_DEPOSIT):
            return _out("DEPOSITS", display_group)
        if _any_kw(b, _KW_RESERVE):
            return _out("RESERVES", display_group)
        if _any_kw(b, _KW_CARD):
            return _out("LIABS_CARDS", display_group)
        if _any_kw(b, _KW_CBU_LIAB):
            return _out("LIABS_CBU", display_group)
        return _out("LIABS_OTHER", display_group)

    return _out("UNCLASSIFIED", display_group)


def _display_group_name(acc: Any) -> str:
    gn = getattr(acc, "group_name", None) or ""
    cbu = getattr(acc, "bs_cbu_sub_item_name", None) or ""
    cbu_item = getattr(acc, "bs_cbu_item_name", None) or ""
    parts = [p.strip() for p in (gn, cbu, cbu_item) if p and str(p).strip()]
    if not parts:
        return "—"
    # De-dupe while keeping order
    seen = set()
    out: List[str] = []
    for p in parts:
        k = _norm(p)
        if k and k not in seen:
            seen.add(k)
            out.append(p.strip())
    return " · ".join(out)


def _out(product_key: str, display_group: str) -> Dict[str, Any]:
    t = TAXONOMY_BY_KEY.get(product_key, TAXONOMY_BY_KEY["UNCLASSIFIED"])
    return {
        "product_key": t.key,
        "product_label_en": t.label_en,
        "product_pillar": t.pillar,
        "display_group": display_group,
    }


# Standard CBU / bank P&L bucket codes used across BaselineData, planning APIs, and drivers
KNOWN_PL_FLAGS = frozenset({1, 2, 3, 4, 5, 7, 8})

_PRODUCT_KEY_TO_PL_FLAG: Dict[str, int] = {
    "REV_INTEREST": 1,
    "EXP_INTEREST": 2,
    "REV_NONINTEREST": 4,
    "EXP_NONINTEREST": 5,
    "OPEX": 7,
    "TAX": 8,
    "CAPEX_PNL": 7,
}


def _exp_noninterest_pl_flag(coa: Any) -> int:
    """Map EXP_NONINTEREST to provisions (3) vs other non-int expense (5) using COA text."""
    b = _blob(coa)
    if _any_kw(b, _KW_RESERVE):
        return 3
    return 5


def effective_pl_flag_for_planning(coa: Any, tax: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """
    Single P&L bucket flag for budget / P&L APIs when dimension rows omit ``p_l_flag``.

    Priority: ``p_l_flag`` (if a known IS code) → ``p_l_group`` when it matches the same
    code set (some CBU extracts only populate group) → FP&A taxonomy when
    ``product_pillar == INCOME`` (persisted ``fpna_product_key`` or classify).
    """
    if tax is None:
        tax = resolve_coa_taxonomy(coa)

    pf = getattr(coa, "p_l_flag", None)
    if pf is not None:
        try:
            fi = int(pf)
            if fi in KNOWN_PL_FLAGS:
                return fi
        except (TypeError, ValueError):
            pass

    pg = getattr(coa, "p_l_group", None)
    if pg is not None:
        try:
            gi = int(pg)
            if gi in KNOWN_PL_FLAGS:
                return gi
        except (TypeError, ValueError):
            pass

    if tax.get("product_pillar") != "INCOME":
        return None

    pk = (tax.get("product_key") or "UNCLASSIFIED").strip().upper()
    if pk == "UNCLASSIFIED":
        return None
    if pk == "EXP_NONINTEREST":
        return _exp_noninterest_pl_flag(coa)
    return _PRODUCT_KEY_TO_PL_FLAG.get(pk)


def product_keys_for_legacy_budgeting_groups(db: Any, group_ids: List[int]) -> List[str]:
    """
    Map legacy CBU budgeting group IDs (coa_dimension.budgeting_groups) to FP&A product keys.
    Used when department_product_access is empty but department_budgeting_groups is set.
    """
    if not group_ids:
        return []
    from app.models.coa_dimension import COADimension

    rows = (
        db.query(COADimension)
        .filter(
            COADimension.is_active == True,
            COADimension.budgeting_groups.in_(group_ids),
        )
        .all()
    )
    keys: List[str] = []
    seen = set()
    for row in rows:
        k = resolve_coa_taxonomy(row)["product_key"]
        if k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def taxonomy_definitions() -> List[Dict[str, str]]:
    return [
        {
            "key": t.key,
            "label_en": t.label_en,
            "pillar": t.pillar,
        }
        for t in TAXONOMY
    ]


def enrich_account_dict(acc: Any, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    d = dict(base) if base else {}
    d.update(resolve_coa_taxonomy(acc))
    return d
