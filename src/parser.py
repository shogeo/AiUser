import ast
from typing import Any, Dict, List, Tuple
from src.exceptions import ParsingError

def parse_command(line: str) -> Tuple[str, List[Any], Dict[str, Any]]:
    """
    Parses a command string into a method name, positional arguments, and keyword arguments.
    """
    line = line.strip()
    if not line:
        raise ParsingError("Command line is empty.")

    open_paren = line.find('(')
    if open_paren == -1:
        raise ParsingError(f"Missing opening parenthesis in command: '{line}'")

    method_name = line[:open_paren].strip()
    if not method_name:
        raise ParsingError(f"Missing method name in command: '{line}'")

    closing_paren = line.rfind(')')
    if closing_paren == -1:
        raise ParsingError(f"Missing closing parenthesis in command: '{line}'")

    args_str = line[open_paren + 1:closing_paren].strip()

    if not args_str:
        return method_name, [], {}

    try:
        # We wrap the arguments in a function call `f(...)` to create a valid AST node.
        tree = ast.parse(f"f({args_str})", mode='eval')
        if not isinstance(tree.body, ast.Call):
            raise ParsingError("Failed to parse arguments as a function call.")

        call = tree.body
        args = []
        for a in call.args:
            try:
                val = ast.literal_eval(a)
            except (ValueError, SyntaxError):
                # If it's not a literal, treat it as a string representation.
                val = ast.unparse(a)
            args.append(val)

        kwargs = {}
        for kw in call.keywords:
            try:
                val = ast.literal_eval(kw.value)
            except (ValueError, SyntaxError):
                val = ast.unparse(kw.value)
            if kw.arg is None:
                raise ParsingError("Keyword arguments must have a name.")
            kwargs[kw.arg] = val

        return method_name, args, kwargs
    except (SyntaxError, ValueError) as e:
        raise ParsingError(f"Failed to parse arguments '{args_str}': {e}") from e
