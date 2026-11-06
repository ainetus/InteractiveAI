"""Load, validate, evaluate, and describe failure-forecast rules.

The rules are distilled offline in the RL failure-forecast project.  This
module is intentionally self-contained so the PowerGrid runtime only needs the
deployed ``best_rule.py`` artifacts and never needs an LLM connection.
"""
from __future__ import annotations

import ast
import logging
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


LOGGER = logging.getLogger(__name__)

FEATURE_TEXT = {
    "sum_load_p": "total active power load at the current time",
    "sum_load_q": "total reactive power load at the current time",
    "sum_gen_p": "total active power generation at the current time",
    "var_line_rho": "variance of line loading at the current time",
    "avg_line_rho": "average line loading at the current time",
    "max_line_rho": "maximum line loading at the current time",
    "nb_rho_ge_0.95": "number of highly loaded lines at the current time",
    "load_gen_ratio": "load-to-generation ratio at the current time",
    "aleatoric_load_p_mean": "forecast uncertainty for active load",
    "aleatoric_load_q_mean": "forecast uncertainty for reactive load",
    "aleatoric_gen_p_mean": "forecast uncertainty for generation",
    "epistemic_before": "epistemic uncertainty at the current time",
    "epistemic_after": "epistemic uncertainty in the forecast state",
    "fcast_sum_load_p": "forecast total active power load one hour ahead",
    "fcast_sum_load_q": "forecast total reactive power load one hour ahead",
    "fcast_sum_gen_p": "forecast total generation one hour ahead",
    "fcast_var_line_rho": "forecast variance of line loading one hour ahead",
    "fcast_avg_line_rho": "forecast average line loading one hour ahead",
    "fcast_max_line_rho": "forecast maximum line loading one hour ahead",
    "fcast_nb_rho_ge_0.95": (
        "forecast number of highly loaded lines one hour ahead"
    ),
}

FEATURE_UNITS = {
    "sum_load_p": "MW",
    "sum_load_q": "MVAR",
    "sum_gen_p": "MW",
    "fcast_sum_load_p": "MW",
    "fcast_sum_load_q": "MVAR",
    "fcast_sum_gen_p": "MW",
}

_OP_TEXT = {
    ast.GtE: ">=",
    ast.Gt: ">",
    ast.LtE: "<=",
    ast.Lt: "<",
    ast.Eq: "=",
    ast.NotEq: "!=",
}

_INVERTED_OP_TEXT = {
    ast.GtE: "<",
    ast.Gt: "<=",
    ast.LtE: ">",
    ast.Lt: ">=",
    ast.Eq: "!=",
    ast.NotEq: "=",
}

_ALLOWED_NODES = (
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.If,
    ast.Return,
    ast.Compare,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Subscript,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.UnaryOp,
    ast.USub,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.Eq,
    ast.NotEq,
)


def _feature_name(node: ast.expr) -> str:
    if not isinstance(node, ast.Subscript):
        raise ValueError("A rule condition must read a feature from x[...].")
    if not isinstance(node.value, ast.Name) or node.value.id != "x":
        raise ValueError("A rule condition must read a feature from x[...].")
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return node.slice.value
    raise ValueError("A rule feature name must be a string literal.")


def _number(node: ast.expr) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_number(node.operand)
    raise ValueError("A rule threshold must be numeric.")


def _format_threshold(value: float, unit: str | None) -> str:
    rendered = f"{value:.0f}" if abs(value) >= 10 else f"{value:.4g}"
    return f"{rendered} {unit}" if unit else rendered


def _condition_text(node: ast.expr, *, negated: bool = False) -> str:
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == len(node.comparators) == 1
    ):
        feature = _feature_name(node.left)
        value = _number(node.comparators[0])
        operators = _INVERTED_OP_TEXT if negated else _OP_TEXT
        operator = operators.get(type(node.ops[0]))
        if operator is None:
            raise ValueError("Unsupported comparison operator in rule.")
        description = FEATURE_TEXT.get(feature, feature.replace("_", " "))
        threshold = _format_threshold(value, FEATURE_UNITS.get(feature))
        return f"the {description} is {operator} {threshold}"
    if isinstance(node, ast.BoolOp):
        joiner = " or " if isinstance(node.op, ast.Or) else " and "
        if negated:
            joiner = " and " if joiner == " or " else " or "
        return "(" + joiner.join(
            _condition_text(value, negated=negated) for value in node.values
        ) + ")"
    raise ValueError("Unsupported rule condition.")


def validate_rule(rule_code: str) -> ast.FunctionDef:
    """Validate the deliberately small, side-effect-free rule language."""
    try:
        tree = ast.parse(textwrap.dedent(rule_code).strip())
    except (SyntaxError, TypeError) as exc:
        raise ValueError(f"Invalid rule syntax: {exc}") from exc

    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(tree.body) != 1 or len(functions) != 1 or functions[0].name != "rule":
        raise ValueError("Rule source must contain exactly one function named 'rule'.")

    function = functions[0]
    arguments = function.args
    if (
        len(arguments.args) != 1
        or arguments.args[0].arg != "x"
        or arguments.vararg is not None
        or arguments.kwarg is not None
        or arguments.defaults
        or arguments.kw_defaults
    ):
        raise ValueError("Rule signature must be exactly def rule(x):")

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"Unsupported syntax in rule: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in {"x", "rule"}:
            raise ValueError(f"Unsupported name in rule: {node.id}")
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("Rule comparisons must use one numeric threshold.")
            feature = _feature_name(node.left)
            if feature not in FEATURE_TEXT:
                raise ValueError(f"Unsupported feature in rule: {feature}")
            _number(node.comparators[0])
        if isinstance(node, ast.Return):
            try:
                value = _number(node.value) if node.value is not None else None
            except ValueError as exc:
                raise ValueError(
                    "Rule return values must be exactly 0 or 1."
                ) from exc
            if value not in {0.0, 1.0}:
                raise ValueError("Rule return values must be exactly 0 or 1.")
    return function


def compile_rule(rule_code: str) -> Callable[[Mapping[str, float]], int]:
    """Compile validated rule source without exposing Python built-ins."""
    validate_rule(rule_code)
    namespace: dict[str, Any] = {}
    exec(
        compile(textwrap.dedent(rule_code), "<explainability-rule>", "exec"),
        {"__builtins__": {}},
        namespace,
    )
    return namespace["rule"]


def _failure_paths(
    statements: list[ast.stmt], conditions: list[str]
) -> list[list[str]]:
    if not statements:
        return []
    first, rest = statements[0], statements[1:]
    if isinstance(first, ast.Return):
        return [conditions] if _number(first.value) == 1 else []
    if not isinstance(first, ast.If):
        return _failure_paths(rest, conditions)
    return (
        _failure_paths(
            list(first.body) + rest,
            conditions + [_condition_text(first.test)],
        )
        + _failure_paths(
            list(first.orelse) + rest,
            conditions + [_condition_text(first.test, negated=True)],
        )
    )


def translate_rule_to_sentence(rule_code: str, line_name: str) -> str:
    """Describe every branch that produces a rule-based predicted probability of failure."""
    function = validate_rule(rule_code)
    paths = _failure_paths(list(function.body), [])
    line_name = str(line_name).removeprefix("line_")
    if not paths:
        return f"The explanatory rule for contingency {line_name} never predicts failure."
    clauses = [" and ".join(path) if path else "all conditions" for path in paths]
    return (
        f"For a contingency on line {line_name}, the simplified explanatory rule "
        f"predicts that the RL agent may fail when "
        + "; or when ".join(clauses)
        + "."
    )


@dataclass(frozen=True)
class RuleExplanation:
    line: str
    prediction: int
    text: str


class RuleExplainer:
    """Load valid ``line_*/best_rule.py`` files from deployed artifacts."""

    def __init__(self, rules_dir: str | Path):
        self.rules_dir = Path(rules_dir)
        self._codes: dict[str, str] = {}
        self._rules: dict[str, Callable[[Mapping[str, float]], int]] = {}
        if not self.rules_dir.exists():
            LOGGER.warning(
                "Explanatory rules directory does not exist: %s", self.rules_dir
            )
            return
        for path in sorted(self.rules_dir.glob("line_*/best_rule.py")):
            line = path.parent.name.removeprefix("line_")
            try:
                code = path.read_text(encoding="utf-8")
                rule = compile_rule(code)
            except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
                LOGGER.warning("Skipping invalid explanatory rule %s: %s", path, exc)
                continue
            self._rules[line] = rule
            self._codes[line] = code

    @property
    def available_lines(self) -> list[str]:
        return sorted(self._rules)

    def describe(self, line: str) -> str:
        name = str(line).removeprefix("line_")
        if name not in self._codes:
            raise KeyError(f"No explanatory rule is available for line {name!r}.")
        return translate_rule_to_sentence(self._codes[name], name)

    def explain(
        self, line: str, features: Mapping[str, float]
    ) -> RuleExplanation:
        name = str(line).removeprefix("line_")
        if name not in self._rules:
            raise KeyError(f"No explanatory rule is available for line {name!r}.")
        prediction = int(self._rules[name](features))
        if prediction not in {0, 1}:
            raise ValueError(
                f"Rule for line {name!r} returned {prediction}, expected 0 or 1"
            )
        return RuleExplanation(name, prediction, self.describe(name))
