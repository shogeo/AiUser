import ast
import importlib
import operator
from typing import Any, Optional

from src.logger import get_logger

logger = get_logger("parser")


def _evaluate_node(node: ast.AST) -> Any:
    """Recursively evaluate an AST node."""
    try:
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
    except (ValueError, AttributeError, ImportError, TypeError) as e:
        logger.error(f"Error evaluating node: {e}\nNode: {ast.dump(node)}")
        return None


def parse_full_api_command(line: str) -> Optional[Any]:
    """Parse a full API command line into a request object."""
    line = line.strip()
    if not line:
        return None

    try:
        tree = ast.parse(line, mode='eval')
        return _evaluate_node(tree.body)
    except (SyntaxError, ValueError) as e:
        logger.error(f"Failed to parse command line: '{line}'. Error: {e}")
        return None
