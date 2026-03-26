import ast
from typing import Any, Dict, List, Tuple

from src.logger import setup_logger

logger = setup_logger(__name__)


def parse_command(line: str) -> Tuple[str, List[Any], Dict[str, Any]]:
    line = line.strip()
    if not line:
        raise ValueError("Пустая строка")

    open_paren = line.find('(')
    if open_paren == -1:
        raise ValueError(f"Нет открывающей скобки: {line}")

    method_name = line[:open_paren].strip()
    args_str = line[open_paren + 1:line.rfind(')')].strip()

    if not args_str:
        return method_name, [], {}

    try:
        tree = ast.parse(f"f({args_str})", mode='eval')
        if not isinstance(tree.body, ast.Call):
            raise ValueError("Не удалось разобрать аргументы")

        call = tree.body
        args = []
        for a in call.args:
            try:
                val = ast.literal_eval(a)
            except Exception:
                val = ast.unparse(a)
            args.append(val)

        kwargs = {}
        for kw in call.keywords:
            try:
                val = ast.literal_eval(kw.value)
            except Exception:
                val = ast.unparse(kw.value)
            kwargs[kw.arg] = val

        return method_name, args, kwargs
    except Exception as e:
        raise ValueError(f"Не удалось разобрать аргументы: {args_str}") from e
