import ast
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
        # This is a simple case, might need to be more robust
        # depending on what the model is expected to pass.
        # For now, we assume it's a string-like name.
        return node.id
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

    # High-level commands: client.method_name(...)
    if isinstance(func_node, ast.Attribute) and isinstance(func_node.value,
                                                           ast.Name) and func_node.value.id == 'client':
        method_name = func_node.attr
        try:
            args = [_evaluate_node(arg) for arg in tree.args]
            kwargs = {kw.arg: _evaluate_node(kw.value) for kw in tree.keywords if kw.arg}
            return {"type": "high_level", "method_name": method_name, "args": args, "kwargs": kwargs, }
        except ParsingError as e:
            # Re-raise parsing errors from argument evaluation
            raise e
        except Exception as e:
            # Catch any other unexpected errors during arg evaluation
            raise ParsingError(f"Failed to evaluate arguments for high-level command: {e}") from e

    # Low-level commands: telethon.tl.functions.messages.SendMessageRequest(...)
    try:
        full_path = _get_full_path(func_node)
        args = [_evaluate_node(arg) for arg in tree.args]
        kwargs = {kw.arg: _evaluate_node(kw.value) for kw in tree.keywords if kw.arg}
        return {"type": "low_level", "full_path": full_path, "args": args, "kwargs": kwargs, }
    except ParsingError as e:
        # Re-raise parsing errors from path or argument evaluation
        raise e
    except Exception as e:
        # Catch any other unexpected errors
        raise ParsingError(f"Failed to parse low-level command: {e}") from e
