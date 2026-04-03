import ast
import importlib
import operator
from typing import Any, Optional, Dict

from src.logger import get_logger

logger = get_logger("parser")


def _evaluate_node(node: ast.AST) -> Any:
    """Recursively evaluates an AST node to a Python object."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.List):
        return [_evaluate_node(e) for e in node.elts]
    elif isinstance(node, ast.Dict):
        keys = [_evaluate_node(k) for k in node.keys]
        values = [_evaluate_node(v) for v in node.values]
        return dict(zip(keys, values))
    elif isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.BitOr):
            return operator.or_(left, right)
        raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
    elif isinstance(node, ast.Name):
        return importlib.import_module(node.id)
    elif isinstance(node, ast.Attribute):
        parent_obj = _evaluate_node(node.value)
        return getattr(parent_obj, node.attr)
    elif isinstance(node, ast.Call):
        callable_obj = _evaluate_node(node.func)
        args = [_evaluate_node(arg) for arg in node.args]
        kwargs = {kw.arg: _evaluate_node(kw.value) for kw in node.keywords if kw.arg}
        return callable_obj(*args, **kwargs)
    else:
        raise ValueError(f"Unsupported syntax node: {type(node).__name__}")


def parse_command(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses a command line into a structured dictionary for the executor.
    Differentiates between high-level ('client.') and low-level ('telethon.') commands.
    """
    line = line.strip()
    if not line:
        return None

    try:
        tree = ast.parse(line, mode='eval').body
    except SyntaxError as e:
        logger.error(f"Failed to parse command line due to syntax error: '{line}'. Error: {e}")
        return None

    if not isinstance(tree, ast.Call):
        logger.warning(f"Command is not a function call, trying to evaluate directly: '{line}'")
        try:
            return {
                "type": "low_level",
                "request_object": _evaluate_node(tree)
            }
        except Exception as e:
            logger.error(f"Failed to evaluate non-call command '{line}': {e}")
            return None

    # Check for high-level 'client.' calls
    func_node = tree.func
    if isinstance(func_node, ast.Attribute) and isinstance(func_node.value, ast.Name) and func_node.value.id == 'client':
        method_name = func_node.attr
        try:
            args = [_evaluate_node(arg) for arg in tree.args]
            kwargs = {kw.arg: _evaluate_node(kw.value) for kw in tree.keywords if kw.arg}
            return {
                "type": "high_level",
                "method_name": method_name,
                "args": args,
                "kwargs": kwargs,
            }
        except Exception as e:
            logger.error(f"Failed to evaluate arguments for high-level command '{line}': {e}")
            return None

    # Otherwise, treat as a low-level command
    try:
        request_object = _evaluate_node(tree)
        return {
            "type": "low_level",
            "request_object": request_object
        }
    except Exception as e:
        logger.error(f"Failed to parse low-level command '{line}': {e}")
        return None
