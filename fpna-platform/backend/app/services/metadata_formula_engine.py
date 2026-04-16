"""
Safe metadata formula parsing and evaluation.
"""

from __future__ import annotations

import ast
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, Optional


class FormulaValidationError(ValueError):
    pass


class MetadataFormulaEngine:
    ALLOWED_FUNCTIONS = {"min", "max", "abs", "round", "coalesce"}
    ALLOWED_NODES = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.BoolOp,
        ast.Compare,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Gt,
        ast.GtE,
        ast.Lt,
        ast.LtE,
    )

    def validate_formula(self, formula: str) -> None:
        if not formula or not formula.strip():
            raise FormulaValidationError("Formula cannot be empty")
        try:
            tree = ast.parse(formula, mode="eval")
        except SyntaxError as exc:
            raise FormulaValidationError(f"Invalid syntax: {exc}") from exc
        for node in ast.walk(tree):
            if not isinstance(node, self.ALLOWED_NODES):
                raise FormulaValidationError(f"Disallowed expression node: {type(node).__name__}")
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in self.ALLOWED_FUNCTIONS:
                    raise FormulaValidationError("Disallowed function call")

    def evaluate(
        self,
        formula: str,
        context: Dict[str, Any],
        *,
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None,
        rounding_places: int = 2,
    ) -> Decimal:
        self.validate_formula(formula)
        tree = ast.parse(formula, mode="eval")
        result = self._eval_node(tree.body, context)
        dec_result = self._to_decimal(result)
        if min_value is not None:
            dec_result = max(dec_result, Decimal(str(min_value)))
        if max_value is not None:
            dec_result = min(dec_result, Decimal(str(max_value)))
        quant = Decimal("1").scaleb(-rounding_places)
        return dec_result.quantize(quant, rounding=ROUND_HALF_UP)

    def _eval_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in context:
                return 0
            return context[node.id]
        if isinstance(node, ast.BinOp):
            left = self._to_decimal(self._eval_node(node.left, context))
            right = self._to_decimal(self._eval_node(node.right, context))
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    return Decimal("0")
                return left / right
            if isinstance(node.op, ast.Mod):
                if right == 0:
                    return Decimal("0")
                return left % right
            if isinstance(node.op, ast.Pow):
                return left ** int(right)
            raise FormulaValidationError("Unsupported binary operator")
        if isinstance(node, ast.UnaryOp):
            val = self._to_decimal(self._eval_node(node.operand, context))
            if isinstance(node.op, ast.USub):
                return -val
            if isinstance(node.op, ast.UAdd):
                return val
            raise FormulaValidationError("Unsupported unary operator")
        if isinstance(node, ast.BoolOp):
            values = [bool(self._eval_node(v, context)) for v in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            for op, comp in zip(node.ops, node.comparators):
                right = self._eval_node(comp, context)
                if not self._compare(op, left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call):
            func_name = node.func.id
            args = [self._eval_node(a, context) for a in node.args]
            return self._call_function(func_name, args)
        raise FormulaValidationError("Unsupported node")

    def _compare(self, op: ast.cmpop, left: Any, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        lval = self._to_decimal(left)
        rval = self._to_decimal(right)
        if isinstance(op, ast.Gt):
            return lval > rval
        if isinstance(op, ast.GtE):
            return lval >= rval
        if isinstance(op, ast.Lt):
            return lval < rval
        if isinstance(op, ast.LtE):
            return lval <= rval
        raise FormulaValidationError("Unsupported comparator")

    def _call_function(self, name: str, args: list[Any]) -> Any:
        if name == "coalesce":
            for arg in args:
                if arg is not None:
                    return arg
            return 0
        if name == "round":
            if not args:
                return 0
            value = self._to_decimal(args[0])
            places = int(args[1]) if len(args) > 1 else 2
            return value.quantize(Decimal("1").scaleb(-places), rounding=ROUND_HALF_UP)
        dec_args = [self._to_decimal(a) for a in args]
        if name == "min":
            return min(dec_args) if dec_args else Decimal("0")
        if name == "max":
            return max(dec_args) if dec_args else Decimal("0")
        if name == "abs":
            return abs(dec_args[0]) if dec_args else Decimal("0")
        raise FormulaValidationError("Unsupported function")

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None or value is False:
            return Decimal("0")
        if value is True:
            return Decimal("1")
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0")
