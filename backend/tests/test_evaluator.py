from app.services.engine import (
    evaluate_expression,
    evaluate_expression_detailed,
    evaluate_numeric_expression_detailed,
)


def test_evaluate_basic():
    ctx = {"revenue": 500, "margin": 0.2}
    assert evaluate_expression("revenue < 1000 and margin > 0.1", ctx) is True
    assert evaluate_expression("revenue > 1000", ctx) is False


def test_evaluate_invalid_syntax_reports_error():
    ctx = {"revenue": 500}
    out = evaluate_expression_detailed("revenue <", ctx)
    assert out["result"] is False
    assert out["error"] == "invalid_syntax"


def test_evaluate_disallowed_ast_reports_error():
    ctx = {"revenue": 500}
    out = evaluate_expression_detailed("__import__('os').system('echo bad')", ctx)
    assert out["result"] is False
    assert "Disallowed expression element" in (out["error"] or "")


def test_numeric_formula_evaluation():
    ctx = {"revenue": 900, "margin": 0.2}
    out = evaluate_numeric_expression_detailed("revenue * margin", ctx)
    assert out["error"] is None
    assert float(out["result"]) == 180.0


def test_numeric_formula_reports_missing_variable():
    out = evaluate_numeric_expression_detailed("revenue * unknown_var", {"revenue": 100})
    assert out["result"] is None
    assert (out["error"] or "").startswith("missing_variable:")
