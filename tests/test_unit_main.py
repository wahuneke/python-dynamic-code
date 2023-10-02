"""Use mocks to do unit testing on the main classes (the Builder and the Runner)"""
from typing import Any
from typing import ClassVar
from typing import Mapping
from typing import Tuple

import pytest

from python_dynamic_code import DynamicCodeBuilder
from python_dynamic_code import UnboundDynamicCodeRunner
from python_dynamic_code import simple_automatic_recalculation_cmp
from python_dynamic_code import simple_automatic_recalculation_hash
from python_dynamic_code.parse import parse


class MySimpleBuilder(DynamicCodeBuilder):
    def template_handler(self, section_name: str, template_matched: str, local_namespace: Mapping[str, Any]) -> str:
        """
        These tests will never attempt to parse PDC annotations or execute them, so the template handler is not
        needed.
        """
        raise NotImplementedError("This should not be called in theses tests")


@pytest.fixture
def simple_func_demo(mocker) -> UnboundDynamicCodeRunner[int, [int], Tuple]:
    """
    Create a code runner based on a simple conversion script that changes code between returning (x,y) and returning
    (y,y) depending on the value of x.  In this case, 'x' is an example of a "slow param" meaning it changes
    infrequently but has a big impact on the code that runs.
    """
    mocker.patch(
        "python_dynamic_code.main.get_conversion_code_tree",
        return_value=parse("def my_func(x,y):\n\tyield 'def my_func(x,y):'\n\tyield '\treturn x,y' if x < 5 else '\treturn -1*x, -1*y'\n"),
    )

    @MySimpleBuilder()
    def my_func(x: int, y: int) -> tuple:
        # This body gets completely overwritten by the output of the mock conversion code
        # Just need placeholder here so that mypy passes
        return x, y

    return my_func


@pytest.fixture(params=["comparison", "hash"])
def auto_builder_func_demo(mocker, request) -> UnboundDynamicCodeRunner[int, [int], Tuple]:
    """
    Create a simple builder but setup with different automatic comparison modes
    """
    mocker.patch(
        "python_dynamic_code.main.get_conversion_code_tree",
        return_value=parse("def my_func(x,y):\n\tyield 'def my_func(x,y):'\n\tyield '\treturn x,y' if x < 5 else '\treturn -1*x, -1*y'\n"),
    )

    class MySimpleBuilderAuto(DynamicCodeBuilder):
        if request.param == "comparison":
            automatic_recalculation_cmp_func: ClassVar = staticmethod(simple_automatic_recalculation_cmp)
        elif request.param == "hash":
            automatic_recalculation_hash_func: ClassVar = staticmethod(simple_automatic_recalculation_hash)
        else:
            raise ValueError("Unexpected auto type")

        def template_handler(self, section_name: str, template_matched: str, local_namespace: Mapping[str, Any]) -> str:
            """
            These tests will never attempt to parse PDC annotations or execute them, so the template handler is not
            needed.
            """
            raise NotImplementedError("This should not be called in theses tests")

    @MySimpleBuilderAuto()
    def my_func(x: int, y: int) -> tuple:
        # This body gets completely overwritten by the output of the mock conversion code
        # Just need placeholder here so that mypy passes
        return x, y

    return my_func


DemoType = UnboundDynamicCodeRunner[int, [int], Tuple]


def test_simple(simple_func_demo: DemoType) -> None:
    """Simple scenario demonstrating basic usage"""

    assert simple_func_demo.exec_block is None, "This will be null at first"
    assert simple_func_demo(1, 2) == (1, 2)
    assert simple_func_demo.exec_block is not None
    assert simple_func_demo(1, 2) == (1, 2)

    simple_func_demo.reset()
    assert simple_func_demo.exec_block is None, "This will be null again"
    simple_func_demo.refresh(1, 2)
    assert simple_func_demo.exec_block is not None, "We have an exec again because we got some args"


def test_simple_branching(simple_func_demo: DemoType) -> None:
    """Simple scenario demonstrating code which adapts depending on the value of param x"""

    assert simple_func_demo.exec_block is None, "This will be null at first"
    assert simple_func_demo(1, 2) == (1, 2)
    assert simple_func_demo.exec_block is not None
    assert simple_func_demo(1, 2) == (1, 2)
    assert simple_func_demo(5, 2) == (5, 2)

    simple_func_demo.reset()
    assert simple_func_demo.exec_block is None, "This will be null again"
    assert simple_func_demo(5, 2) == (-5, -2)
    assert simple_func_demo.exec_block is not None, "We have an exec again because we got some args"
    simple_func_demo.refresh(1, 2)
    assert simple_func_demo(1, 2) == (1, 2), "Back to the old algorithm"
    assert simple_func_demo(5, 2) == (5, 2), "Back to the old algorithm"


def test_manual_refresh(simple_func_demo: DemoType) -> None:
    """
    A test with same basic structure, but different emphasis.  Make sure manual refresh works as expected (goes with
    other test: test_auto_refresh)
    """
    assert simple_func_demo.exec_block is None, "This will be null at first"
    assert simple_func_demo(1, 2) == (1, 2)
    assert simple_func_demo.exec_block is not None, "Running the func should have triggered building of exec block"
    assert simple_func_demo(5, 2) == (5, 2), "Also, fast path code will not change based on change in x"

    simple_func_demo.reset()
    assert simple_func_demo.exec_block is None, "This will be null again"
    assert simple_func_demo(5, 2) == (-5, -2), "Now it has changed because of the reset."
    assert simple_func_demo(1, 2) == (-1, -2), "But now the old function call returns new answer (new code)."


def test_auto_refresh(auto_builder_func_demo: DemoType) -> None:
    """
    A test with same basic structure, but different emphasis.  Make sure automatic refresh works as expected (goes with
    other tests: test_manual_refresh)
    """
    assert auto_builder_func_demo.exec_block is None, "This will be null at first"
    assert auto_builder_func_demo(1, 2) == (1, 2)
    assert auto_builder_func_demo.exec_block is not None, "Running the func should have triggered building of exec"
    assert auto_builder_func_demo(5, 2) == (-5, -2), "Fast path updated automatically!!"

    auto_builder_func_demo.reset()
    assert auto_builder_func_demo.exec_block is None, "This will be null again"
    auto_builder_func_demo.refresh(1, 2)
    assert auto_builder_func_demo(1, 2) == (1, 2), "Fast path will always update appropriately"
    assert auto_builder_func_demo(5, 2) == (-5, -2), "Calling reset and/or refresh had no impact"
