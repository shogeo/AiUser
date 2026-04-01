import ast
import importlib
import operator
from typing import Any

# --- Whitelist for safe operations ---
ALLOWED_MODULES = ("telethon.tl.functions", "telethon.tl.types")
ALLOWED_OPERATORS = {
    ast.BitOr: operator.or_,
}

def _evaluate_node(node: ast.AST) -> Any:
    """
    Safely evaluates an AST node, supporting Telethon objects, lists, and bitwise OR.
    This is a secure alternative to eval().
    """
    # --- Base Cases: Literals ---
    if isinstance(node, ast.Constant):
        return node.value
    # For older Python versions that don't use ast.Constant for everything
    if isinstance(node, (ast.Str, ast.Num)):
        return node.s if isinstance(node, ast.Str) else node.n
    if isinstance(node, ast.NameConstant):
        return node.value

    # --- Recursive Cases: Containers and Operations ---
    elif isinstance(node, ast.List):
        return [_evaluate_node(e) for e in node.elts]

    elif isinstance(node, ast.Dict):
        keys = [_evaluate_node(k) for k in node.keys]
        values = [_evaluate_node(v) for v in node.values]
        return dict(zip(keys, values))

    elif isinstance(node, ast.BinOp):
        if type(node.op) in ALLOWED_OPERATORS:
            left = _evaluate_node(node.left)
            right = _evaluate_node(node.right)
            op_func = ALLOWED_OPERATORS[type(node.op)]
            return op_func(left, right)
        else:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

    # --- Object Instantiation and Path Resolution ---
    elif isinstance(node, ast.Name):
        # This is the root of an object path, e.g., 'telethon'
        if node.id == 'telethon':
            return importlib.import_module('telethon')
        raise ValueError(f"Invalid starting identifier: '{node.id}'. Must be 'telethon'.")

    elif isinstance(node, ast.Attribute):
        # Recursively resolve the parent object, e.g., 'telethon.tl.functions.messages'
        parent_obj = _evaluate_node(node.value)
        # Get the attribute, e.g., 'SendMessageRequest'
        try:
            return getattr(parent_obj, node.attr)
        except AttributeError:
            # Provide a clear error if an attribute is not found
            raise ValueError(f"Attribute '{node.attr}' not found on object '{parent_obj}'.")

    elif isinstance(node, ast.Call):
        # This is the final instantiation call
        callable_obj = _evaluate_node(node.func)

        # --- SECURITY CHECK ---
        # Ensure the object being called is from a whitelisted Telethon module
        module_name = getattr(callable_obj, '__module__', '')
        if not module_name.startswith(ALLOWED_MODULES):
            raise ValueError(f"Disallowed module: Calling objects from '{module_name}' is forbidden.")

        # Evaluate arguments
        args = [_evaluate_node(arg) for arg in node.args]
        kwargs = {kw.arg: _evaluate_node(kw.value) for kw in node.keywords if kw.arg}
        
        try:
            return callable_obj(*args, **kwargs)
        except TypeError as e:
            raise ValueError(f"Failed to instantiate '{callable_obj.__name__}': {e}") from e

    else:
        raise ValueError(f"Unsupported syntax node: {type(node).__name__}")

def parse_full_api_command(line: str) -> Any:
    """
    Parses a full API command string into an executable Telethon request object.
    This function is the entry point and wraps the recursive _evaluate_node.
    """
    line = line.strip()
    if not line:
        raise ValueError("Command line is empty.")

    try:
        # Parse the line into an AST expression
        tree = ast.parse(line, mode='eval')
        # Evaluate the entire AST tree starting from the body
        return _evaluate_node(tree.body)
    except Exception as e:
        # In the simplified model, any parsing error is a generic exception.
        # The assistant will catch it and report it to the model.
        raise
