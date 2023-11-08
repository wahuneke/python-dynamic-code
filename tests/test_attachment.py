"""
Test variations of ways to use DynamicCodeBuilder to attach to different types of functions
"""
from typing import Any, TypeVar, Dict
from typing import Callable
from typing import Mapping
from typing import Tuple
from typing import Type

import pytest
from typing_extensions import ParamSpec

from python_dynamic_code import DynamicCodeBuilder
from python_dynamic_code import DynamicCodeRunner
from python_dynamic_code.main import UnboundDynamicCodeRunner

_P = ParamSpec("_P")
_R = TypeVar("_R", covariant=True)

DType = Dict[int, int]


@pytest.fixture
def builder_class() -> Type[DynamicCodeBuilder]:
    class MyBuilder(DynamicCodeBuilder):
        """A barebones implementation of DynamicCodeBuilder that does nothing"""

        def template_handler(self, section_name: str, template_matched: str, local_namespace: Mapping[str, Any]) -> str:
            raise NotImplementedError("not a real builder")

        def refresh(self, runner: DynamicCodeRunner[_P, _R], *args: "_P.args", **kwargs: "_P.kwargs") -> None:
            # Just set the exec block back to the original function. No conversion running in this test
            runner.exec_block = runner.code

        def setup_conversion_func(self, runner: DynamicCodeRunner[_P, _R]) -> None:
            # Just use the original func as conversion func in this test
            runner.exec_block = runner.code

    return MyBuilder


def test_attach_to_function(builder_class: Type[DynamicCodeBuilder]) -> None:
    @builder_class()
    def im_a_function(a: str, b: int, c: DType) -> Tuple[str, int, DType]:
        # PDC-Function
        # PDC-Verbatim
        return a, b, c

    assert isinstance(im_a_function, UnboundDynamicCodeRunner)
    assert im_a_function("a", 2, {3: 3}) == ("a", 2, {3: 3})
    # When pytest runs with mypy, this winds up amounting to a type assertion
    _1: "UnboundDynamicCodeRunner[str, [int, DType], Tuple[str, int, DType]]" = im_a_function  # noqa: F841
    _2: "Callable[[str, int, DType], Tuple[str, int, DType]]" = im_a_function.__call__  # noqa: F841


def test_attach_to_method(builder_class: Type[DynamicCodeBuilder]) -> None:
    class MyClass:
        def __init__(self) -> None:
            self.x = 1

        @builder_class()
        def im_a_method(self, a: str, b: int, c: DType) -> Tuple[str, int, DType]:
            assert self.x == 1
            return a, b, c

    c = MyClass()
    assert c.im_a_method("a", 2, {3: 3}) == ("a", 2, {3: 3})
    assert isinstance(c.im_a_method, DynamicCodeRunner)
    _: "DynamicCodeRunner[[str, int, DType], Tuple[str, int, DType]]" = c.im_a_method  # noqa: F841
    _2: "Callable[[str, int, DType], Tuple[str, int, DType]]" = c.im_a_method.__call__  # noqa: F841


def test_attach_to_staticmethod(builder_class: Type[DynamicCodeBuilder]) -> None:
    class MyClass:
        @staticmethod
        @builder_class()
        def im_a_staticmethod(a: str, b: int, c: dict) -> Tuple[str, int, dict]:
            return a, b, c

    assert isinstance(MyClass.im_a_staticmethod, DynamicCodeRunner)
    assert isinstance(MyClass().im_a_staticmethod, DynamicCodeRunner)
    assert MyClass.im_a_staticmethod("a", 2, {3: 3}) == ("a", 2, {3: 3})
    assert MyClass().im_a_staticmethod("a", 2, {3: 3}) == ("a", 2, {3: 3})
    # When pytest runs with mypy, this winds up amounting to a type assertion
    _1: "UnboundDynamicCodeRunner[str, [ int, dict], Tuple[str, int, dict]]" = MyClass.im_a_staticmethod  # noqa: F841
    _2: "Callable[[str, int, dict], Tuple[str, int, dict]]" = MyClass.im_a_staticmethod.__call__  # noqa: F841


def test_attach_to_classmethod(builder_class: Type[DynamicCodeBuilder]) -> None:
    called_with_class = []

    class MyClass:
        @classmethod
        @builder_class()
        def im_a_classmethod(cls, a: str, b: int, c: DType) -> Tuple[str, int, DType]:
            called_with_class.append(cls)
            return a, b, c

    class MyClass2(MyClass):
        @classmethod
        @builder_class()
        def im_a_classmethod(cls: Type[MyClass], a: str, b: int, c: DType) -> Tuple[str, int, DType]:
            called_with_class.append(cls)
            return a, b, c

    assert isinstance(MyClass.im_a_classmethod, DynamicCodeRunner)
    assert isinstance(MyClass().im_a_classmethod, DynamicCodeRunner)
    assert called_with_class == []
    assert MyClass.im_a_classmethod("a", 2, {3: 3}) == ("a", 2, {3: 3})
    assert called_with_class == [MyClass]
    assert MyClass().im_a_classmethod("a", 2, {3: 3}) == ("a", 2, {3: 3})
    assert called_with_class == [MyClass, MyClass]
    assert MyClass2.im_a_classmethod("a", 2, {3: 3}) == ("a", 2, {3: 3})
    assert called_with_class == [MyClass, MyClass, MyClass2]
    assert MyClass2().im_a_classmethod("a", 2, {3: 3}) == ("a", 2, {3: 3})
    assert called_with_class == [MyClass, MyClass, MyClass2, MyClass2]

    # When pytest runs with mypy, this winds up amounting to a type assertion
    _1: "DynamicCodeRunner[[str, int, DType], Tuple[str, int, DType]]" = MyClass.im_a_classmethod  # noqa: F841
    _2: "Callable[[str, int, dict], Tuple[str, int, dict]]" = MyClass.im_a_classmethod.__call__  # noqa: F841
    _3: "DynamicCodeRunner[[str, int, DType], Tuple[str, int, DType]]" = MyClass().im_a_classmethod  # noqa: F841
