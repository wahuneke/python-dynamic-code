"""The "Stream" class is supposed to represent the wrapper that contains the fast path code to which we are attaching"""
import sys
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from typing import Callable
from typing import Generator
from typing import Tuple

import pytest

from python_dynamic_code.parse import unparse
from python_dynamic_code.runner import PdcStream
from python_dynamic_code.util import import_module_from_file

_module_counter = 1


@pytest.fixture
def temporary_module(tmp_path: Path) -> Generator[ModuleType, None, None]:
    """Create a new Python file and import it as a module"""
    global _module_counter
    module_file = tmp_path.joinpath("tmp_module.py")
    module_file.write_text(
        dedent(
            """\
    '''A fake module header doc'''

    a_global_variable = 100

    def func_a(a: int, b: str) -> tuple:
        a += 1
        return a, b

    def func_b(a: int, b: str) -> tuple:
        global a_global_variable
        a += 1
        a_global_variable += a
        return a, b
    """
        )
    )
    module_name = f"temporary_module_{_module_counter}"
    _module_counter += 1
    module = import_module_from_file(module_name, module_file)
    yield module
    del sys.modules[module_name]


def test_basic_parse() -> None:
    source = dedent(
        """\
    def my_func(a: int, b: str) -> tuple:
        a += 1
        return a, b
    """
    )
    stream = PdcStream("test", source)
    assert unparse(stream.source_ast) == dedent(
        """\
        def my_func(a: int, b: str) -> tuple:
            a += 1
            return (a, b)"""
    )


def test_basic_func_parse(temporary_module: ModuleType) -> None:
    stream = PdcStream("test", temporary_module.func_a)
    assert unparse(stream.source_ast) == dedent(
        """\
        def func_a(a: int, b: str) -> tuple:
            a += 1
            return (a, b)"""
    )
    assert stream.source_ast.body[0].lineno == 5

    new_func: Callable[[int, str], Tuple[int, str]] = stream.add_new_function(stream.source_ast)

    # This behaves as expected
    assert new_func.__name__.startswith("__pdc")
    assert new_func(1, "hi") == (2, "hi")


def test_module_global_access(temporary_module: ModuleType) -> None:
    stream = PdcStream("test", temporary_module.func_a)
    stream_b = PdcStream("test", temporary_module.func_b)

    assert temporary_module.a_global_variable == 100

    new_func: Callable[[int, str], Tuple[int, str]] = stream.add_new_function(stream.source_ast)
    new_func_b: Callable[[int, str], Tuple[int, str]] = stream_b.add_new_function(stream_b.source_ast)

    assert temporary_module.a_global_variable == 100

    r = new_func_b(1, "hi")
    assert r == (2, "hi")

    # The code in "new func_b", which was pushed into our temporary module, has modified the global variable
    assert temporary_module.a_global_variable == 102

    assert new_func.__name__ == "__pdc_dynamic_func_1"
    assert new_func_b.__name__ == "__pdc_dynamic_func_2"
