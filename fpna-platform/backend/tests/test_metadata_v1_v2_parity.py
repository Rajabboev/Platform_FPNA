from decimal import Decimal

from app.services.metadata_formula_engine import MetadataFormulaEngine


def _v1_result(driver_type: str, baseline: Decimal, rate: Decimal) -> Decimal:
    if driver_type == "growth_rate":
        return (baseline * (Decimal(1) + rate / Decimal(100))).quantize(Decimal("0.01"))
    if driver_type in {"yield_rate", "cost_rate"}:
        return (baseline * rate / Decimal(100) / Decimal(12)).quantize(Decimal("0.01"))
    if driver_type == "provision_rate":
        return (baseline * rate / Decimal(100)).quantize(Decimal("0.01"))
    if driver_type == "inflation_rate":
        return (baseline * (Decimal(1) + rate / Decimal(100))).quantize(Decimal("0.01"))
    return (baseline * (Decimal(1) + rate / Decimal(100))).quantize(Decimal("0.01"))


def _v2_result(formula: str, baseline: Decimal, rate: Decimal) -> Decimal:
    return MetadataFormulaEngine().evaluate(formula, {"baseline": baseline, "rate": rate})


def test_v1_v2_formula_parity_core_driver_types():
    cases = [
        ("growth_rate", "baseline * (1 + rate / 100)"),
        ("yield_rate", "baseline * rate / 100 / 12"),
        ("cost_rate", "baseline * rate / 100 / 12"),
        ("provision_rate", "baseline * rate / 100"),
        ("inflation_rate", "baseline * (1 + rate / 100)"),
    ]
    baseline = Decimal("1500")
    rate = Decimal("8")
    for dtype, formula in cases:
        assert _v2_result(formula, baseline, rate) == _v1_result(dtype, baseline, rate)
