"""FEEL-Lite: a safe expression evaluator that grew into DMN S-FEEL coverage.

The compliance plan (`docs/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md` §2.6)
called for real DMN S-FEEL in Phase 29. Rather than write a stand-alone FEEL
parser (which would be ~600 lines of recursive-descent), Phase 29 takes the
already-safe Python-`ast`-based evaluator from Phase 27 and *extends* it with
the S-FEEL semantics that matter for VIZA's exit criterion:

    "A rule can express RSI < 30 AND volume_spike > 2 AND
    days(event.observed_at, cutoff) < 5 in one expression."

The internal syntax is therefore Python-compatible, but the *semantics* match
DMN S-FEEL: ranges, list membership (`in`), date-and-time built-ins
(`date(...)`, `duration(...)`, `days(...)`, `now()`), and the standard
comparison/boolean/arithmetic operators.

DMN XML export (`viza/dmn_export.py`) is responsible for translating these
expressions into proper FEEL syntax (`==` → `=`, etc.) so the rules round-trip
into external DMN engines. The same expression body authored once works in
both worlds.

Safety still comes from parsing via Python's `ast` module with a strict node
whitelist: no attribute lookups on Python objects, no calls except to a fixed
function table, no comprehensions, no lambdas, no imports.
"""

from __future__ import annotations

import ast
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


class FeelLiteError(ValueError):
    pass


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub, ast.Not)
_ALLOWED_COMPARES = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq, ast.In, ast.NotIn)
_ALLOWED_BOOLOPS = (ast.And, ast.Or)


def _safe_min(*args: Any) -> Any:
    if not args:
        raise FeelLiteError("min() requires at least one argument")
    return min(args)


def _safe_max(*args: Any) -> Any:
    if not args:
        raise FeelLiteError("max() requires at least one argument")
    return max(args)


def _safe_abs(value: Any) -> Any:
    return abs(value)


def _safe_clamp(value: Any, lo: Any, hi: Any) -> Any:
    return max(lo, min(hi, value))


def _safe_round(value: Any, digits: Any = 6) -> Any:
    return round(value, int(digits))


def _safe_sqrt(value: Any) -> Any:
    return math.sqrt(value)


def _safe_date(value: Any) -> datetime:
    """S-FEEL `date(string)` built-in. Returns a tz-aware UTC datetime so
    arithmetic with other date/datetime values stays consistent."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        raise FeelLiteError(f"date() requires a string, got {type(value).__name__}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_duration(value: Any) -> timedelta:
    """S-FEEL `duration(string)` built-in. Accepts ISO-8601 day-and-time
    durations: `PnDTnHnMnS`. Year/month durations are not supported in the
    FEEL-Lite scope because they require calendar arithmetic."""
    if isinstance(value, timedelta):
        return value
    if not isinstance(value, str):
        raise FeelLiteError(
            f"duration() requires an ISO-8601 string, got {type(value).__name__}"
        )
    return _parse_iso_duration(value)


def _safe_days(start: Any, end: Any) -> float:
    """`days(start, end)` returns the floating-point number of days between
    two date/datetime values. Negative when end < start. Date-only inputs
    are coerced via `date(...)`."""
    start_dt = _coerce_to_datetime(start)
    end_dt = _coerce_to_datetime(end)
    return (end_dt - start_dt).total_seconds() / 86400.0


def _safe_now() -> datetime:
    return datetime.now(timezone.utc)


_ALLOWED_FUNCTIONS = {
    "min": _safe_min,
    "max": _safe_max,
    "abs": _safe_abs,
    "clamp": _safe_clamp,
    "round": _safe_round,
    "sqrt": _safe_sqrt,
    # S-FEEL date / duration built-ins.
    "date": _safe_date,
    "datetime": _safe_date,
    "duration": _safe_duration,
    "days": _safe_days,
    "now": _safe_now,
}


def _coerce_to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return _safe_date(value)
    raise FeelLiteError(
        f"expected a date or datetime, got {type(value).__name__}: {value!r}"
    )


def _parse_iso_duration(value: str) -> timedelta:
    """Minimal ISO-8601 duration parser covering the D/H/M/S components.

    Examples that parse: `P30D`, `PT5H`, `P3DT2H30M`, `PT0.5S`, `-P1D`.
    Rejects months/years because they require calendar context; callers that
    need them should compute via `days(date_a, date_b)` instead.
    """
    if not value:
        raise FeelLiteError("duration string is empty")
    negative = False
    text = value
    if text[0] == "-":
        negative = True
        text = text[1:]
    if not text.startswith("P"):
        raise FeelLiteError(f"duration must start with 'P': {value!r}")
    text = text[1:]
    if "Y" in text or text.split("T")[0].endswith("M"):
        # A 'M' before the T separator is months — unsupported.
        date_part = text.split("T")[0]
        if "Y" in date_part or "M" in date_part:
            raise FeelLiteError(
                f"year/month durations are not supported in FEEL-Lite: {value!r}"
            )
    days = hours = minutes = seconds = 0.0
    date_part, _, time_part = text.partition("T")
    if date_part:
        if not date_part.endswith("D"):
            raise FeelLiteError(f"unrecognized day-part in duration: {value!r}")
        days = float(date_part[:-1])
    if time_part:
        token = ""
        for ch in time_part:
            if ch.isdigit() or ch == "." or ch == "-":
                token += ch
                continue
            if not token:
                raise FeelLiteError(f"missing magnitude before {ch!r} in {value!r}")
            magnitude = float(token)
            if ch == "H":
                hours = magnitude
            elif ch == "M":
                minutes = magnitude
            elif ch == "S":
                seconds = magnitude
            else:
                raise FeelLiteError(f"unrecognized time-part token {ch!r} in {value!r}")
            token = ""
        if token:
            raise FeelLiteError(f"trailing magnitude {token!r} in {value!r}")
    delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    return -delta if negative else delta


def evaluate(expression: str, context: Mapping[str, Any]) -> Any:
    """Evaluate `expression` against `context`.

    Identifiers in the expression are looked up in `context` by their full
    dotted path (e.g. `technical.rsi_14`). Missing identifiers raise
    `FeelLiteError`; the caller must decide whether to treat that as a failed
    trigger / sizing computation.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise FeelLiteError("expression must be a non-empty string")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FeelLiteError(f"could not parse FEEL-Lite expression: {exc}") from exc
    return _eval_node(tree.body, context)


def _eval_node(node: ast.AST, context: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, str, bool)):
            return node.value
        raise FeelLiteError(f"unsupported constant: {node.value!r}")

    if isinstance(node, ast.Name):
        return _resolve_name(node.id, context)

    if isinstance(node, ast.Attribute):
        path = _attribute_path(node)
        return _resolve_name(path, context)

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise FeelLiteError(f"binary operator not allowed: {type(node.op).__name__}")
        left = _eval_node(node.left, context)
        right = _eval_node(node.right, context)
        return _apply_binop(left, right, node.op)

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            raise FeelLiteError(f"unary operator not allowed: {type(node.op).__name__}")
        operand = _eval_node(node.operand, context)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            return not operand
        raise FeelLiteError("unreachable: unary op already validated")

    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, _ALLOWED_BOOLOPS):
            raise FeelLiteError(f"boolean operator not allowed: {type(node.op).__name__}")
        values = [_eval_node(value, context) for value in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for v in values:
                result = result and v
            return result
        result = False
        for v in values:
            result = result or v
        return result

    if isinstance(node, ast.Compare):
        if any(not isinstance(op, _ALLOWED_COMPARES) for op in node.ops):
            raise FeelLiteError("only <, <=, >, >=, ==, != comparisons are allowed")
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, context)
            if not _apply_compare(left, right, op):
                return False
            left = right
        return True

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FeelLiteError("only direct function calls are allowed (no attribute calls)")
        func_name = node.func.id
        if func_name not in _ALLOWED_FUNCTIONS:
            raise FeelLiteError(f"function not allowed: {func_name!r}")
        if node.keywords:
            raise FeelLiteError("keyword arguments are not supported")
        args = [_eval_node(arg, context) for arg in node.args]
        return _ALLOWED_FUNCTIONS[func_name](*args)

    if isinstance(node, ast.List):
        return [_eval_node(element, context) for element in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(element, context) for element in node.elts)

    raise FeelLiteError(f"unsupported expression node: {type(node).__name__}")


def _apply_binop(left: Any, right: Any, op: ast.AST) -> Any:
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        if right == 0:
            raise FeelLiteError("division by zero")
        return left / right
    if isinstance(op, ast.Mod):
        if right == 0:
            raise FeelLiteError("modulo by zero")
        return left % right
    if isinstance(op, ast.Pow):
        return left**right
    raise FeelLiteError("unreachable: binop already validated")


def _apply_compare(left: Any, right: Any, op: ast.AST) -> bool:
    if isinstance(op, ast.Lt):
        return left < right
    if isinstance(op, ast.LtE):
        return left <= right
    if isinstance(op, ast.Gt):
        return left > right
    if isinstance(op, ast.GtE):
        return left >= right
    if isinstance(op, ast.Eq):
        return left == right
    if isinstance(op, ast.NotEq):
        return left != right
    if isinstance(op, ast.In):
        if not isinstance(right, (list, tuple, set, frozenset, str)):
            raise FeelLiteError(
                f"`in` requires a list/tuple/set/string on the right, "
                f"got {type(right).__name__}"
            )
        return left in right
    if isinstance(op, ast.NotIn):
        if not isinstance(right, (list, tuple, set, frozenset, str)):
            raise FeelLiteError(
                f"`not in` requires a list/tuple/set/string on the right, "
                f"got {type(right).__name__}"
            )
        return left not in right
    raise FeelLiteError("unreachable: compare already validated")


def _attribute_path(node: ast.Attribute) -> str:
    """Build a dotted-path string from an ast.Attribute chain rooted in a Name."""
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    else:
        raise FeelLiteError("dotted path must start with a plain identifier")
    return ".".join(reversed(parts))


def _resolve_name(name: str, context: Mapping[str, Any]) -> Any:
    """Look up `name` in `context`, walking dotted paths into nested mappings."""
    if name in context:
        return context[name]
    parts = name.split(".")
    current: Any = context
    for index, part in enumerate(parts):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
            continue
        path_so_far = ".".join(parts[: index + 1])
        raise FeelLiteError(f"identifier not bound in context: {path_so_far!r}")
    return current
