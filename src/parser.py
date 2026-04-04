import ast
import importlib
from typing import Any, Dict

from src.exceptions import ParsingError
from src.logger import get_logger

logger = get_logger("parser")


def _get_full_path(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_get_full_path(node.value)}.{node.attr}"
    raise ParsingError(f"Unsupported node type for full path: {type(node).__name__}")


def _evaluate_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_evaluate_node(e) for e in node.elts]
    if isinstance(node, ast.Dict):
        keys = [_evaluate_node(k) for k in node.keys]
        values = [_evaluate_node(v) for v in node.values]
        return dict(zip(keys, values))
    if isinstance(node, ast.Name):
        try:
            return importlib.import_module(node.id)
        except ImportError:
            raise ParsingError(f"Could not resolve name: {node.id}")
    if isinstance(node, ast.Attribute):
        parent_obj = _evaluate_node(node.value)
        try:
            return getattr(parent_obj, node.attr)
        except AttributeError:
            raise ParsingError(f"Could not find attribute '{node.attr}' on '{parent_obj}'")
    if isinstance(node, ast.Call):
        callable_obj = _evaluate_node(node.func)
        args = [_evaluate_node(arg) for arg in node.args]
        kwargs = {kw.arg: _evaluate_node(kw.value) for kw in node.keywords if kw.arg}
        return callable_obj(*args, **kwargs)

    raise ParsingError(f"Unsupported syntax node for argument: {type(node).__name__}")


def parse_command(line: str) -> Dict[str, Any]:
    line = line.strip()
    if not line:
        raise ParsingError("Command line is empty.")

    try:
        tree = ast.parse(line, mode='eval').body
    except SyntaxError as e:
        raise ParsingError(f"Syntax error in command: {e}") from e

    if not isinstance(tree, ast.Call):
        raise ParsingError("Command must be a function call.")

    func_node = tree.func

    try:
        args = [_evaluate_node(arg) for arg in tree.args]
        kwargs = {kw.arg: _evaluate_node(kw.value) for kw in tree.keywords if kw.arg}

        if isinstance(func_node, ast.Attribute) and isinstance(func_node.value,
                                                               ast.Name) and func_node.value.id == 'client':
            method_name = func_node.attr
            return {"type": "high_level", "method_name": method_name, "args": args, "kwargs": kwargs, }

        full_path = _get_full_path(func_node)
        return {"type": "low_level", "full_path": full_path, "args": args, "kwargs": kwargs, }

    except ParsingError as e:
        raise e
    except Exception as e:
        raise ParsingError(f"Failed to parse arguments or command structure: {e}") from e
