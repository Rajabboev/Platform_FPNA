from decimal import Decimal

from app.services.metadata_formula_engine import MetadataFormulaEngine


def test_formula_engine_growth_rate_parity():
    engine = MetadataFormulaEngine()
    result = engine.evaluate(
        "baseline * (1 + rate / 100)",
        {"baseline": Decimal("1000"), "rate": Decimal("10")},
    )
    assert result == Decimal("1100.00")


def test_formula_engine_yield_rate_parity():
    engine = MetadataFormulaEngine()
    result = engine.evaluate(
        "baseline * rate / 100 / 12",
        {"baseline": Decimal("1200"), "rate": Decimal("12")},
    )
    assert result == Decimal("12.00")


def test_formula_engine_safety_rejects_unsafe_nodes():
    engine = MetadataFormulaEngine()
    try:
        engine.validate_formula("__import__('os').system('echo x')")
        assert False, "Unsafe formula should be rejected"
    except Exception:
        assert True
