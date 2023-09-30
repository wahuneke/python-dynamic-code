import inspect
from types import FunctionType


class DynamicCodeBuilder:
    """
    This class must be customized and missing values defined in order to define a section of code which PDC will
    optimize
    """

    source_function: FunctionType

    def compile(self, **kwargs) -> "DynamicCodeRunner":
        lines, lineno = inspect.getsourcelines(self.source_function)
        code = "".join(lines)
        return DynamicCodeRunner(code)


class DynamicCodeRunner:
    """This class manages the automatic generation and re-generation of the code replacement."""

    code: str

    def __init__(self, code: str) -> None:
        self.code = code

    def run_it(*args, **kwargs):
        pass
