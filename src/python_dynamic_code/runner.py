import ast
import inspect
from _ast import Module
from dataclasses import field
from functools import partial
from textwrap import dedent
from types import ModuleType
from typing import Union, Iterable, Optional

from python_dynamic_code.parse import parse, ast_util


class PdcStream:
    """
    Take a stream of Python code which may have 'PDC' annotations in it.  Parse the annotations and find and identify
    the sections, nested sections, and annotations that go with each.

    Keep track of the file and module the code came from and facilitate declaring new copies of the function in the
    same namespace.
    """

    name: str

    filename: Optional[str] = field(init=False, default=None)
    """The filename, if applicable.  As with `module` property, this will be None if source was a raw string"""

    module: Optional[ModuleType] = field(init=False, default=None)
    """The module that the original source code came from. Or, None if source was a raw string (e.g. in a test case)"""

    source_ast: ast.Module = field(init=False, default_factory=ast.AST)
    """This is the annotated source after being parsed by the parsing sub package. ie, it will contain PdcNodes, etc"""

    source_code: str = field(init=False, default_factory=str)
    """
    The original source code, as a string. This will include all code lines starting at line 1 (ie a full module) and
    usually will include more than just the code from the individual function
    """

    def __init__(self, name: str, code: Union[callable, str, Iterable[str]]):
        self.name = name

        if isinstance(code, str):
            self.source_ast = parse(code)
            self.source_code = code
        elif isinstance(code, Iterable):
            self.source_code = "\n".join(code)
            self.source_ast = parse(self.source_code)
        else:
            if isinstance(code, partial):
                func = code.func
            elif isinstance(code, staticmethod):
                func = code.__func__
            else:
                func = code

            self.filename = inspect.getsourcefile(func)
            self.module = inspect.getmodule(func)
            self.source_code = inspect.getsource(self.module)

            lines, line_no = inspect.getsourcelines(func)

            try:
                self.source_ast = parse(dedent("\n".join(lines)), self.filename)
            except SyntaxError as e:
                e.lineno += line_no - 1
                # TODO: this line number fix gets the line number right but the code excerpt displayed will be wrong
                #  (it will use the line number from the original file, not the line number from the function)
                raise

            ast.increment_lineno(self.source_ast, line_no - 1)

    def add_new_function(self, func: Union[str, "Module"]) -> callable:
        """
        Take the given function and 'add' it into the module by executing the definition code within the namespace
        of the module.  This ensures that, if the function makes reference to names or globals imported or defined
        in the module, then the new function will be able to run.

        If the PdcStream is not attached to a module (e.g. in unit testing), the global namespace is used.

        A random (and guaranteed-unused) function name is chosen.
        """
        if self.module:
            namespace = self.module.__dict__
        else:
            namespace = globals()

        # Find a function name that is not yet used
        function_name_suffix = 1
        while (function_name := f"__pdc_dynamic_func_{function_name_suffix}") in namespace:
            function_name_suffix += 1

        if isinstance(func, str):
            func = parse(func)

        assert isinstance(func, Module)

        # Build a new def with the new name
        new_func = ast_util.ast_rename_function(func, function_name)

        # Execute the new function definition, in the proper namespace. Return the new callable created there
        compiled_new_func = compile(new_func, self.filename, mode="exec")
        assert compiled_new_func is not None
        exec(compiled_new_func, namespace)

        return namespace[function_name]

    def remove_function(self, func: callable) -> None:
        """
        Given a temporary function that was created using the `add_new_function()` method, declare that the function
        is no longer needed. Recover important resources (in case of very-long running app with a large number of
        dynamically-added functions
        """
        if self.module:
            assert inspect.getmodule(func) is self.module

        if self.module:
            namespace = self.module.__dict__
        else:
            namespace = globals()

        del namespace[func.__name__]
