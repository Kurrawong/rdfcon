import ast
import importlib.util
import os
from functools import lru_cache


def _list_functions_in_file(filename: str):
    with open(filename, "r") as f:
        tree = ast.parse(f.read(), filename=filename)
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _load_module_from_file(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=128)
def load_custom_functions(filename: str | None) -> dict[str:object]:
    if filename:
        module_name = os.path.splitext(os.path.basename(filename))[0]
        function_names = _list_functions_in_file(filename)
        module = _load_module_from_file(module_name, filename)
        return {
            name: getattr(module, name)
            for name in function_names
            if hasattr(module, name)
        }
    return {}
