from typing import Optional, Dict, Any, List
import ast
import json
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models


ALLOWED_AST_NODES = {
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Constant,
}


def _validate_ast(node: ast.AST) -> None:
    """Recursively ensure AST uses only allowed node types."""
    if type(node) not in ALLOWED_AST_NODES:
        # allow operator nodes via their classes (BinOp has op child)
        raise ValueError(f"Disallowed expression element: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _validate_ast(child)


def validate_expression(expression: str) -> Optional[str]:
    """Return None when valid, else a deterministic error string."""
    expr = (expression or "").strip()
    if not expr:
        return "empty_expression"
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return "invalid_syntax"

    try:
        _validate_ast(tree)
    except ValueError as exc:
        return str(exc)

    return None


def evaluate_expression_detailed(expression: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate expression and include deterministic error metadata."""
    validation_error = validate_expression(expression)
    if validation_error:
        return {"result": False, "error": validation_error}

    try:
        tree = ast.parse(expression, mode="eval")
        value = eval(compile(tree, filename="<ast>", mode="eval"), {"__builtins__": {}}, context)
        return {"result": bool(value), "error": None}
    except NameError as exc:
        return {"result": False, "error": f"missing_variable:{exc}"}
    except Exception as exc:
        return {"result": False, "error": f"evaluation_error:{exc.__class__.__name__}"}


def evaluate_expression(expression: str, context: Dict[str, Any]) -> bool:
    """Safely evaluate a boolean expression using a restricted AST check and empty builtins.

    Expression can reference keys from `context` as variable names. Example: `revenue < 1000 and margin > 0.1`
    """
    return bool(evaluate_expression_detailed(expression, context)["result"])


def evaluate_numeric_expression_detailed(expression: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate numeric DSL expression with safe AST and deterministic errors."""
    validation_error = validate_expression(expression)
    if validation_error:
        return {"result": None, "error": validation_error}

    try:
        tree = ast.parse(expression, mode="eval")
        value = eval(compile(tree, filename="<ast>", mode="eval"), {"__builtins__": {}}, context)
        return {"result": float(value), "error": None}
    except NameError as exc:
        return {"result": None, "error": f"missing_variable:{exc}"}
    except Exception as exc:
        return {"result": None, "error": f"evaluation_error:{exc.__class__.__name__}"}


async def run_deterministic_engine(db: AsyncSession, model_version_id: Optional[str] = None, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Deterministic engine that evaluates rule conditions against `input_data`.

    Behavior:
    - Loads the specified or active `ModelVersion`.
    - Loads active `Rule`s and their `RuleCondition`s.
    - Evaluates each condition against `input_data` (defaults to empty dict).
    - Computes a simple contribution breakdown and derives a `state` using `StateThreshold` numeric thresholds.
    """
    input_data = input_data or {}

    # Load model version
    if model_version_id:
        try:
            mv_id = uuid.UUID(str(model_version_id))
        except Exception:
            return {"error": "invalid_model_version_id", "message": "model_version_id must be a UUID"}
        q = select(models.ModelVersion).where(models.ModelVersion.id == mv_id)
    else:
        q = select(models.ModelVersion).where(models.ModelVersion.is_active == True).limit(1)

    res = await db.execute(q)
    mv = res.scalars().first()

    if mv is None:
        return {"error": "no_model_version", "message": "No active ModelVersion found"}

    # Load rules for model version
    rules_q = select(models.Rule).where(models.Rule.model_version_id == mv.id, models.Rule.is_active == True)
    rules_res = await db.execute(rules_q)
    rules = rules_res.scalars().all()

    # Load conditions grouped by rule
    rule_ids = [r.id for r in rules]
    conditions: List[models.RuleCondition] = []
    if rule_ids:
        condition_q = select(models.RuleCondition).where(models.RuleCondition.rule_id.in_(rule_ids), models.RuleCondition.is_active == True)
        cond_res = await db.execute(condition_q)
        conditions = cond_res.scalars().all()

    # Build coefficient config from DB (supports scalar values or DSL formulas)
    coefficient_configs: List[Dict[str, Any]] = []
    coeff_q = select(models.Coefficient).where(
        models.Coefficient.model_version_id == mv.id,
        models.Coefficient.is_active == True,
    )
    coeff_res = await db.execute(coeff_q)
    coefficients = coeff_res.scalars().all()
    for coeff in coefficients:
        raw_value = (coeff.value or "").strip()
        try:
            numeric_value = float(raw_value)
            coefficient_configs.append(
                {
                    "name": coeff.name,
                    "type": "scalar",
                    "raw": raw_value,
                    "scalar": numeric_value,
                }
            )
        except Exception:
            coefficient_configs.append(
                {
                    "name": coeff.name,
                    "type": "formula",
                    "raw": raw_value,
                }
            )

    # Evaluate conditions
    triggered_rules = set()
    contributions = []
    for cond in conditions:
        expr = (cond.expression or "").strip()
        if not expr:
            continue
        eval_result = evaluate_expression_detailed(expr, input_data)
        ok = bool(eval_result["result"])
        contributions.append(
            {
                "rule_id": str(cond.rule_id),
                "condition_id": str(cond.id),
                "expression": expr,
                "result": ok,
                "error": eval_result.get("error"),
            }
        )
        if ok:
            triggered_rules.add(str(cond.rule_id))

    rule_count = len(rules)
    triggered_count = len(triggered_rules)

    # Compute contribution scores using RuleImpact numeric values when present
    rule_scores: Dict[str, float] = {}
    try:
        if rule_ids:
            impact_q = select(models.RuleImpact).where(
                models.RuleImpact.rule_id.in_(rule_ids),
                models.RuleImpact.is_active == True,
            )
            impact_res = await db.execute(impact_q)
            impacts = impact_res.scalars().all()
            impacts_by_rule = {}
            for imp in impacts:
                impacts_by_rule.setdefault(str(imp.rule_id), []).append(imp)

            for rid in triggered_rules:
                total = 0.0
                entries = impacts_by_rule.get(rid, [])
                for e in entries:
                    try:
                        total += float(e.impact)
                    except Exception:
                        continue
                rule_scores[rid] = total if total > 0 else 1.0
    except Exception:
        rule_scores = {}

    rule_impact_score = float(sum(rule_scores.values())) if rule_scores else 0.0

    # Deterministic weighted score from coefficient config
    # - scalar coefficient: contribution = input[coefficient.name] * scalar
    # - formula coefficient: contribution = eval(formula, runtime_context)
    coefficient_contributions = []
    weighted_input_score = 0.0
    runtime_context: Dict[str, Any] = {}
    runtime_context.update(input_data)

    # expose rule impact score in formulas
    runtime_context["rule_impact_score"] = rule_impact_score

    # expose metric values from active metrics for model version
    metric_values: Dict[str, float] = {}
    metric_q = select(models.Metric).where(
        models.Metric.model_version_id == mv.id,
        models.Metric.is_active == True,
    )
    metric_res = await db.execute(metric_q)
    metric_items = metric_res.scalars().all()
    for metric in metric_items:
        raw = input_data.get(metric.name)
        try:
            metric_values[metric.name] = float(raw)
        except Exception:
            continue
    runtime_context.update(metric_values)

    for conf in coefficient_configs:
        name = conf["name"]
        if conf["type"] == "scalar":
            scalar = float(conf["scalar"])
            raw_input = runtime_context.get(name)
            try:
                numeric_val = float(raw_input)
                contribution = numeric_val * scalar
                weighted_input_score += contribution
                coefficient_contributions.append(
                    {
                        "name": name,
                        "mode": "scalar",
                        "input": numeric_val,
                        "coefficient": scalar,
                        "formula": None,
                        "contribution": contribution,
                        "error": None,
                    }
                )
            except Exception:
                coefficient_contributions.append(
                    {
                        "name": name,
                        "mode": "scalar",
                        "input": raw_input,
                        "coefficient": scalar,
                        "formula": None,
                        "contribution": 0.0,
                        "error": "missing_or_non_numeric_input",
                    }
                )
            continue

        formula = conf["raw"]
        eval_out = evaluate_numeric_expression_detailed(formula, runtime_context)
        result = eval_out.get("result")
        err = eval_out.get("error")
        if result is None:
            coefficient_contributions.append(
                {
                    "name": name,
                    "mode": "formula",
                    "input": None,
                    "coefficient": None,
                    "formula": formula,
                    "contribution": 0.0,
                    "error": err,
                }
            )
            continue

        contribution = float(result)
        weighted_input_score += contribution
        coefficient_contributions.append(
            {
                "name": name,
                "mode": "formula",
                "input": None,
                "coefficient": None,
                "formula": formula,
                "contribution": contribution,
                "error": None,
            }
        )

    total_score = weighted_input_score + rule_impact_score

    # Calibrated state score to avoid over-classifying every scenario as CRITICAL.
    # State should be driven primarily by rule triggers + impacts, with weighted input
    # score acting as a softer secondary signal.
    state_score = max(0.0, weighted_input_score) * 0.1 + rule_impact_score + (triggered_count * 20.0)

    # Determine state via tenant-scoped StateThreshold using calibrated state_score
    state = "NORMAL"
    try:
        thresholds_q = (
            select(models.StateThreshold)
            .where(models.StateThreshold.tenant_id == mv.tenant_id)
        )
        th_res = await db.execute(thresholds_q)
        thresholds = th_res.scalars().all()

        matches = []
        for t in thresholds:
            try:
                threshold_value = float(t.threshold)
            except Exception:
                continue

            if state_score >= threshold_value:
                sd = await db.get(models.StateDefinition, t.state_definition_id)
                if sd and sd.tenant_id == mv.tenant_id:
                    matches.append((sd.name, threshold_value))

        if matches:
            # choose highest threshold match first, with severity override for CRITICAL/ELEVATED
            matches.sort(key=lambda x: x[1], reverse=True)
            names = [m[0] for m in matches]
            if "CRITICAL_ZONE" in names:
                state = "CRITICAL_ZONE"
            elif "ELEVATED_RISK" in names:
                state = "ELEVATED_RISK"
            else:
                state = names[0]
    except Exception:
        state = "NORMAL"

    # CRITICAL_ZONE restructuring lookup from DB templates/rules
    restructuring_actions = []
    if state == "CRITICAL_ZONE":
        try:
            rr_q = select(models.RestructuringRule).where(models.RestructuringRule.tenant_id == mv.tenant_id)
            rr_res = await db.execute(rr_q)
            rr_items = rr_res.scalars().all()
            for rr in rr_items:
                template = await db.get(models.RestructuringTemplate, rr.template_id)
                if template is None:
                    continue
                parsed_payload: Any = template.payload
                if template.payload:
                    try:
                        parsed_payload = json.loads(template.payload)
                    except Exception:
                        parsed_payload = template.payload
                restructuring_actions.append(
                    {
                        "restructuring_rule_id": str(rr.id),
                        "template_id": str(template.id),
                        "template_name": template.name,
                        "payload": parsed_payload,
                    }
                )
        except Exception:
            restructuring_actions = []

    snapshot = {
        "model_version": {"id": str(mv.id), "name": mv.name, "tenant_id": str(mv.tenant_id)},
        "rule_count": rule_count,
        "triggered_rule_count": triggered_count,
        "conditions_evaluated": len(conditions),
        "state": state,
        "contributions": contributions,
        "scores": rule_scores,
        "score_breakdown": {
            "weighted_input_score": weighted_input_score,
            "rule_impact_score": rule_impact_score,
            "total_score": total_score,
            "state_score": state_score,
            "coefficient_contributions": coefficient_contributions,
        },
        "restructuring_actions": restructuring_actions,
    }

    return snapshot
