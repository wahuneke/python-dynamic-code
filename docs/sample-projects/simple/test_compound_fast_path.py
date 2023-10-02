"""In this test, we confirm that the intermediate steps produced from the fast path are as expected"""
from dataclasses import dataclass
from textwrap import dedent
from typing import Mapping

import pytest
from simple_lib import compound_fast_path
from simple_lib import PluginType


def func_factory(name):
    def func(*args):
        arg_strs = ", ".join(repr(o) for o in args)
        print(f"Func call {name}({arg_strs})")

    return func


@dataclass
class CodeTestScenario:
    fast_path_input: Mapping
    expect_conversion_code: str
    expect_exec_code: str


@pytest.fixture(
    params=[
        (
            {"a": PluginType(func_factory("a_1"), ("arg1", "arg3", "arg4"))},
            dedent(
                """\
        results = []
        results.append(__pdc_unroll_2.call_func(changes_every_call))

        """
            ),
            "",
        ),
    ]
)
def scenario(request) -> CodeTestScenario:
    fast_path_input, expect_conversion_code, expect_exec_code = request.param
    return CodeTestScenario(fast_path_input, expect_conversion_code, expect_exec_code)


def test_confirm_conversion_code(scenario):
    """Run the fast path pre-compilation step which generates the intermediate conversion code"""
    assert (
        compound_fast_path.get_conversion_code(changes_less_often=scenario.fast_path_input)
        == scenario.expect_conversion_code
    )
