"""In these tests, we see what conversion code results from various source code inputs"""
from textwrap import dedent

import pytest

from python_dynamic_code.parse import unparse
from python_dynamic_code.conversion_code.conversion import get_conversion_code_tree
from python_dynamic_code.runner import PdcStream


def input_to_conversion_code(input_code: str) -> str:
    stream = PdcStream("test", input_code.splitlines())
    return unparse(get_conversion_code_tree(stream))


@pytest.mark.parametrize(
    ("try_input", "expect_output"),
    [
        # (
        #     dedent(
        #         """\
        #         print("I'm a Python script")
        #         """
        #     ),
        #     dedent(
        #         """\
        #         print("I'm a Python script")
        #
        #         yield "\\n"
        #         """
        #     ),
        # ),
        # (
        #     dedent(
        #         """\
        #         # PDC-Start section 1
        #         # PDC-Verbatim
        #         print("I'm a Python script")
        #         # PDC-End section 1
        #         """
        #     ),
        #     dedent(
        #         """\
        #         print("I'm a Python script")
        #         yield "print(\"I'm a Python script\")\\n"
        #
        #         yield "\\n"
        #         """
        #     ),
        # ),(
        #     dedent(
        #         """\
        #         # PDC-Start section 1
        #         # PDC-TemplateCode
        #         # PDC-Replace some_dict\[some_key\]
        #         print("I'm a Python script")
        #         x = some_dict[some_key]
        #         # PDC-End section 1
        #         """
        #     ),
        #     dedent(
        #         """\
        #         print("I'm a Python script")
        #         yield "print(\"I'm a Python script\")\\n"
        #         x = some_dict[some_key]
        #         var1 = test.run_template('section 1', 'some_dict\\\\[some_key\\\\]', locals())
        #         yield "x = var1\\n"
        #
        #         yield "\\n"
        #         """
        #     ),
        # ),
        # ("def func():\n\t# PDC-Function\n\tprint('hi')",
        #  "print('hi')\n\nyield \"\\n\"\n"),
        (
            "def func():\n    # PDC-Function\n    # PDC-VerbatimLine\n    print('hi')",
            "print('hi')\n\nyield \"    print('hi')\\n\"\n\tyield \"\\n\"\n",
        ),
    ],
)
def test_simple(try_input, expect_output) -> None:
    """Try a few simple cases"""
    assert input_to_conversion_code(try_input) == expect_output


@pytest.mark.parametrize(
    "try_input,expect_first_line",
    [
        (
            dedent(
                """\
        # PDC-Function
        some_code
        """
            ),
            "some_code",
        ),
        (
            dedent(
                """\
        def my_func():
            # PDC-Function
            some_code
        """
            ),
            # require that indentation is reset
            "some_code",
        ),
        (
            dedent(
                """\
        @some_decorator
        @other deco
        def funcy(self, a, b, c):
            \"\"\"
            Some function comment
            \"\"\"
            # PDC-Function
            start_here
        """
            ),
            "start_here",
        ),
    ],
)
def test_strip_function_header(try_input: str, expect_first_line: str) -> None:
    """
    The method used to read and parse source code (inspect.getsourcelines) will include decorators and the initial
    function declaration.  We need all of that removed.

    For now, our implementation makes this simple.  We require the presence of a PDC-Function annotation to mark the
    starting point of the function. Everything before that is completely ignored.
    """
    assert input_to_conversion_code(try_input).startswith(expect_first_line)
