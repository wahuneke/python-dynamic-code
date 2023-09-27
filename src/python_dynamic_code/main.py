import inspect
from typing import Any


class DynamicCodeBuilder:
    source_function: Any

    def compile(self, **kwargs) -> "DynamicCodeRunner":
        lines, lineno = inspect.getsourcelines(self.source_function)
        code = "".join(lines)
        return DynamicCodeRunner(code)


class DynamicCodeRunner:
    code: str

    def __init__(self, code: str) -> None:
        self.code = code

    def run_it(*args, **kwargs):
        pass