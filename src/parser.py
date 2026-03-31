import ast
import importlib
from typing import Any

from src.exceptions import ParsingError, CommandNotFoundError

def _get_full_class_path(node: ast.AST) -> str:
    """Recursively reconstructs the full class path from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_get_full_class_path(node.value)}.{node.attr}"
    else:
        raise ParsingError(f"Unsupported node type for class path: {type(node)}")

def parse_full_api_command(line: str) -> Any:
    """
    Parses a full API command string (e.g., 'functions.messages.SendMessageRequest(...)')
    into an executable Telethon request object.
    """
    line = line.strip()
    if not line:
        raise ParsingError("Command line is empty.")

    try:
        tree = ast.parse(line, mode='eval')
    except SyntaxError as e:
        raise ParsingError(f"Invalid Python syntax in command: '{line}'") from e

    if not isinstance(tree.body, ast.Call):
        raise ParsingError("Command must be a function or class instantiation call.")

    call_node = tree.body
    
    # Reconstruct the full class path (e.g., 'functions.messages.SendMessageRequest')
    full_class_str = _get_full_class_path(call_node.func)
    
    # Prepend the required 'telethon.tl.' prefix
    full_module_path = f"telethon.tl.{full_class_str}"

    module_name, class_name = full_module_path.rsplit('.', 1)

    try:
        # Dynamically and safely import the module
        module = importlib.import_module(module_name)
        # Get the class from the module
        target_class = getattr(module, class_name)
    except ImportError:
        raise CommandNotFoundError(f"Module '{module_name}' not found.")
    except AttributeError:
        raise CommandNotFoundError(f"Class '{class_name}' not found in module '{module_name}'.")

    # Recursively parse arguments to handle nested API objects
    args = [parse_full_api_command(ast.unparse(arg)) if isinstance(arg, ast.Call) else ast.literal_eval(arg) for arg in call_node.args]
    kwargs = {kw.arg: (parse_full_api_command(ast.unparse(kw.value)) if isinstance(kw.value, ast.Call) else ast.literal_eval(kw.value)) for kw in call_node.keywords}

    try:
        # Create an instance of the target class
        return target_class(*args, **kwargs)
    except TypeError as e:
        raise ParsingError(f"Failed to instantiate '{class_name}' with provided arguments: {e}") from e
