def _test_evaluate_expression_import():
    from app.services.engine import evaluate_expression

    ctx = {"revenue": 500, "margin": 0.2}
    assert evaluate_expression("revenue < 1000 and margin > 0.1", ctx) is True
    assert evaluate_expression("revenue > 1000", ctx) is False


if __name__ == "__main__":
    _test_evaluate_expression_import()
    print("engine evaluator quick-check: OK")
