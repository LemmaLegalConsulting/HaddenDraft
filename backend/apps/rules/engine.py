from datetime import date, datetime
from typing import Any


class RuleEvaluationError(Exception):
    pass


MISSING = object()


def get_path(data: dict, path: str, default=None):
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def coerce_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise RuleEvaluationError(f"Cannot coerce date: {value!r}")


def eval_condition(condition: dict, facts: dict) -> bool:
    field = condition["field"]
    op = condition["op"]
    expected = condition.get("value")
    actual = get_path(facts, field)

    if op == "equals":
        return actual == expected
    if op == "not_equals":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "exists":
        return get_path(facts, field, MISSING) is not MISSING
    if op == "missing":
        return get_path(facts, field, MISSING) is MISSING
    if op == "greater_than":
        return actual is not None and actual > expected
    if op == "greater_than_or_equal":
        return actual is not None and actual >= expected
    if op == "less_than":
        return actual is not None and actual < expected
    if op == "less_than_or_equal":
        return actual is not None and actual <= expected
    if op == "between":
        if actual is None:
            return False
        low, high = expected
        return low <= actual <= high
    if op == "contains":
        if actual is None:
            return False
        return expected in actual
    if op == "date_before":
        actual_date = coerce_date(actual)
        expected_date = coerce_date(expected)
        return actual_date is not None and actual_date < expected_date
    if op == "date_after":
        actual_date = coerce_date(actual)
        expected_date = coerce_date(expected)
        return actual_date is not None and actual_date > expected_date

    raise RuleEvaluationError(f"Unsupported operator: {op}")


def eval_node(node: dict, facts: dict) -> bool:
    if "field" in node:
        return eval_condition(node, facts)
    if "all" in node:
        return all(eval_node(child, facts) for child in node["all"])
    if "any" in node:
        return any(eval_node(child, facts) for child in node["any"])
    if "not" in node:
        return not eval_node(node["not"], facts)
    raise RuleEvaluationError(f"Invalid condition node: {node}")


def condition_fields(node: dict) -> set[str]:
    if "field" in node:
        return {node["field"]}
    fields = set()
    for key in ("all", "any"):
        if key in node:
            for child in node[key]:
                fields.update(condition_fields(child))
    if "not" in node:
        fields.update(condition_fields(node["not"]))
    return fields


def evaluate_table(table: Any, facts: dict) -> list[dict]:
    matches = []
    rows = table.rows.filter(enabled=True).order_by("priority", "id")

    for row in rows:
        if eval_node(row.conditions, facts):
            match = {
                "row_id": row.row_id,
                "label": row.label,
                "outputs": row.outputs,
                "explanation": row.explanation_template,
                "priority": row.priority,
                "condition_fields": sorted(condition_fields(row.conditions)),
            }
            matches.append(match)
            if table.hit_policy == "first":
                break

    if table.hit_policy == "unique" and len(matches) > 1:
        raise RuleEvaluationError(f"Unique hit policy violated for table {table.key} v{table.version}")

    if table.hit_policy == "priority" and matches:
        return [sorted(matches, key=lambda match: match["priority"])[0]]

    return matches
