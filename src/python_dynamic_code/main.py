import abc
import ast
import inspect
import sys
from functools import partial
from typing import Any
from typing import Callable
from typing import ClassVar
from typing import Generic
from typing import Iterable
from typing import Mapping
from typing import Optional
from typing import overload
from typing import Tuple
from typing import Type
from typing import TypeVar
from typing import Union

from typing_extensions import Concatenate
from typing_extensions import ParamSpec

from python_dynamic_code.conversion_code import get_conversion_code_tree
from python_dynamic_code.parse import unparse
from python_dynamic_code.runner import PdcStream

__all__ = [
    "simple_automatic_recalculation_cmp",
    "simple_automatic_recalculation_hash",
    "DynamicCodeBuilder",
    "DynamicCodeRunner",
    "UnboundDynamicCodeRunner",
]

_P = ParamSpec("_P")
_R = TypeVar("_R", covariant=True)
_T = TypeVar("_T")
_T2 = TypeVar("_T2")

_ExecParamsType = Tuple[Tuple[Any, ...], Mapping[str, Any]]
"""When the full set of call arguments is to be passed to a call, it will be passed in this form"""

_runner_counter = 0
"""
A global that is used to keep track of the number of instances of dynamic code runner so that unique function names
can be generated to live in the global namespace.
"""

_ConversionFunction = Callable[_P, Iterable[str]]
"""
A conversion function is a callable taking a parameter set and returning an iterable of strings which (when joined with
`CR`) form a complete Python definition for the exec function
"""


class PdcConversionError(Exception):
    def __init__(
        self,
        filename: str,
        func_object: Any,
        conv_args: Optional[Tuple[Any, ...]] = None,
        conv_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.filename = filename
        self.func_object = func_object
        self.conv_args = conv_args
        self.conv_kwargs = conv_kwargs

    def __str__(self) -> str:
        return f"{self.filename}{inspect.getsource(self.func_object)}\n{self.conv_args}\n{self.conv_kwargs}"


class DynamicCodeRunner(Generic[_P, _R]):
    """This class manages the automatic generation and re-generation of the code replacement."""

    builder: "DynamicCodeBuilder"
    code: Callable[_P, _R]
    conversion_code_ast: Optional[ast.Module]
    exec_code_str: Optional[str]
    automatic_cache: Optional[Union[int, _ExecParamsType]]
    runner_number: int
    exec_block: Optional[Callable[_P, _R]]
    conversion_function: _ConversionFunction[_P]

    def __init__(self, builder: "DynamicCodeBuilder", attached_func: Callable[_P, _R], **kwargs: Any) -> None:
        global _runner_counter
        _runner_counter += 1
        self.runner_number = _runner_counter
        self.exec_block = None
        self.automatic_cache = None
        self.builder = builder
        self.code = attached_func
        attached_func_name = getattr(attached_func, "__name__", "__pdc_unnammed_func")
        self.pdc_stream = PdcStream(attached_func_name, attached_func)
        self.builder.setup_conversion_func(self)

    def __call__(self, *args: "_P.args", **kwargs: "_P.kwargs") -> _R:
        if self.builder.automatic_recalculation_hash_func is not None:
            return self._call_hash_mode(*args, **kwargs)
        elif self.builder.automatic_recalculation_cmp_func is not None:
            return self._call_comp_mode(*args, **kwargs)
        else:
            return self._call_manual_mode(*args, **kwargs)

    def _call_manual_mode(self, *args: "_P.args", **kwargs: "_P.kwargs") -> _R:
        """
        See docs. In manual mode, a refresh is only done if the `reset` or `refresh` methods are called explicitly
        """
        if not self.exec_block:
            self.refresh(*args, **kwargs)

        assert self.exec_block is not None
        return self.exec_block(*args, **kwargs)

    def _call_hash_mode(self, *args: "_P.args", **kwargs: "_P.kwargs") -> _R:
        """In automatic (hash) mode, we calculate a hash of inputs and re-calculate exec block if changed"""
        assert self.builder.automatic_recalculation_hash_func is not None
        call_hash = self.builder.automatic_recalculation_hash_func((args, kwargs))
        if self.automatic_cache != call_hash or self.exec_block is None:
            self.refresh(*args, **kwargs)
            self.automatic_cache = call_hash

        assert self.exec_block is not None
        return self.exec_block(*args, **kwargs)

    def _call_comp_mode(self, *args: "_P.args", **kwargs: "_P.kwargs") -> _R:
        """
        In automatic (comparison) mode, we run a full comparison of passed arguments to decide whether to
        re-calculate the exec block.
        """
        assert self.builder.automatic_recalculation_cmp_func is not None
        assert not isinstance(self.automatic_cache, int)
        if (
            self.automatic_cache is None
            or self.exec_block is None
            or self.builder.automatic_recalculation_cmp_func((args, kwargs), self.automatic_cache)
        ):
            self.refresh(*args, **kwargs)
            self.automatic_cache = (args, kwargs)

        assert self.exec_block is not None
        return self.exec_block(*args, **kwargs)

    def reset(self) -> None:
        """
        Calling this causes any cached exec block (from previous runs of the fast path) to be removed.  As a result, a
        new exec block will be created the next time the fast path function is called.

        See also `refresh()`, which can be used to update exec code before the fast path runs.
        """
        if self.exec_block:
            # recover resources so that this module does not grow infinitely with all the exec blocks
            self.pdc_stream.remove_function(self.exec_block)
        self.exec_block = None

    @property
    def conversion_func_ast(self) -> ast.Module:
        """
        After original source is parsed and directives are applied, this will be the result. This will be compiled and
        attached to the source module as the new conversion function to be run whenever new exec code is needed.

        This function definition is ready to be grafted into the target namespace (into the module or int global,
        if no module).

        This function definition does not yet have its final function name. Still needs to be renamed to a new,
        available name. This is done at last step by the `add_new_function()` method.
        """
        return get_conversion_code_tree(self.pdc_stream)

    def conversion_func_definition(self) -> str:
        """
        This is the string representation of the conversion function definition.  It is generated by unparsing the
        AST in `conversion_func_ast`. It requires python 3.9 or later (it is intended only for debugging and testing).
        """
        if sys.version_info < (3, 9):
            raise NotImplementedError("This method requires Python 3.9 or later")

        return (
            "# The following is the code that will be executed whenever there is a refresh (in order to generate \n"
            "# new 'exec code').\n"
            "# NOTE: the function name here is not the one that will be used to represent this code internally\n"
            "#   ie, it is for example purposes.  All other code is a true copy." + unparse(self.conversion_func_ast)
        )

    def refresh(self, *args: "_P.args", **kwargs: "_P.kwargs") -> None:
        """
        Similar to running the `reset()` method, but this function also *executes* the conversion function, using
        the provided conversion args and kwargs, and produces an `exec_block` that is ready to run in the fast path.

        As an alternative, the `reset()` method can be called instead - in which case an exec_block will be
        automatically generated the next time the fast path function is run.
        """
        self.builder.refresh(self, *args, **kwargs)


class UnboundDynamicCodeRunner(DynamicCodeRunner[Concatenate[_T, _P], _R], Generic[_T, _P, _R]):
    """
    When used as a method, but not yet bound to an instance or type, the function will appear to be an instance
    of this subclass.  Functionally identical to the `DynamicCodeRunner`, present only for accurate typing.
    """

    owner_class: Optional[object]

    use_bound_class: Type[DynamicCodeRunner[_P, _R]]

    def __init__(
        self,
        builder: "DynamicCodeBuilder",
        attached_func: "Callable[Concatenate[_T, _P], _R]",
        use_bound_class: Optional[Type[DynamicCodeRunner[_P, _R]]] = None,
    ) -> None:
        super().__init__(builder, attached_func)
        self.owner_class = None
        self.use_bound_class = use_bound_class or DynamicCodeRunner[_P, _R]

    def __set_name__(self, owner: object, name: str) -> None:
        assert self.owner_class is None, "This decorator should only be used once"
        self.owner_class = owner

    @overload
    def __get__(self, instance: None, owner: Type[_T]) -> "UnboundDynamicCodeRunner[_T, _P, _R]":
        ...

    @overload
    def __get__(self, instance: _T, owner: Optional[Type[_T]]) -> "DynamicCodeRunner[_P, _R]":
        ...

    def __get__(
        self, instance: Optional[Any], owner: Optional[Type[Any]]
    ) -> Union["UnboundDynamicCodeRunner[_T, _P, _R]", "DynamicCodeRunner[_P, _R]",]:
        if instance is None:
            assert owner is not None
            return self
        else:
            return self.use_bound_class(self.builder, partial(self.code, instance))


class DynamicCodeBuilder(abc.ABC):
    """
     This class should be subclassed, and then can be attached to fast-path code as a function/method decorator. For
     example:

     >>> class MyCodeBuilder(DynamicCodeBuilder):
     >>>    def template_handler(self, section_name: str, template_matched: str, local_namespace: dict) -> str:
     >>>        ...
     >>>
     >>> @MyCodeBuilder()
     >>> def my_fast_path_function(arg1, arg2):
     >>>     ...
     >>>     # PDC-Start section 1
     >>>     ...

     In the above example, the `my_fast_path_function` will be replaced with a new function that will be an instance of
     `DynamicCodeRunner`. The `DynamicCodeRunner` will in turn take care of deciding when to run 'conversion code' and
     when to execute 'exec code'.

     In implementin the builder subclass, a decision should be made about whether to use *manual* or *automatic*
     regeneration of exec code.

     **Manual Conversion**

    `Conversion code` will be turned into exec code the first time the fastpath is called. After which, the same `exec
     code` will always run.  Regeneration of exec code can be manually triggered at any time, by invoking `refresh()` on
     the runner and providing the appropriate, new slow parameter values.

     **Automatic Conversion**

     The decision to recreate the exec code can also be made 'automatically' every time the fast path is executed. To do
     this, the builder must have defined either a _hash_ function or a _comparison_ function which can be called, with
     fast path exec params to determine whether the 'slow' portion of the exec params has been changed since the last
     run (causing it to be necessary to re-run conversion code).

     Using 'automatic conversion' may result in a significantly slower fast path function in comparison with 'manual'
     mode, because every fast path run will be preceeded by a check of the hash or the comparison function.
    """

    automatic_recalculation_hash_func: ClassVar[Optional[Callable[[_ExecParamsType], int]]] = None
    """
    A hash function can be defined which which will be given the full set of exec params (on every
    call to the fast path) and which will return a hash of the `slow params`.  When this hash changes, the runner will
    interpret this as meaning that a new `exec block` must be computed.
    """

    automatic_recalculation_cmp_func: ClassVar[Optional[Callable[[_ExecParamsType, _ExecParamsType], bool]]] = None
    """
    A comparison function can be defined which will be given the full set of exec params (on every
    call to the fast path) along with a copy of the most recent set of exec params when the params changed.
    The function should return True if slow param values have changed (meaning the exec code should be regenerated).
    """

    unbound_runner_class: ClassVar[Type[DynamicCodeRunner]] = UnboundDynamicCodeRunner  # type: ignore
    """This can be set to a subclass of `UnboundDynamicCodeRunner` to change the behavior of the decorator."""

    runner_class: ClassVar[Type[DynamicCodeRunner]] = DynamicCodeRunner  # type: ignore
    """This can be set to a subclass of `DynamicCodeRunner` to change the behavior of the decorator."""

    def __call__(
        self, fn: "Callable[Concatenate[_T, _P], _R]"
    ) -> Union[UnboundDynamicCodeRunner[_T, _P, _R], DynamicCodeRunner[_P, _R]]:
        if isinstance(fn, staticmethod):
            return self.runner_class(self, fn)
        else:
            return self.unbound_runner_class(self, fn, use_bound_class=self.runner_class)

    @abc.abstractmethod
    def template_handler(self, section_name: str, template_matched: str, local_namespace: Mapping[str, Any]) -> str:
        ...

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if cls.automatic_recalculation_hash_func is not None and cls.automatic_recalculation_cmp_func is not None:
            raise TypeError(
                f"Class '{cls}' defined with values for both types of automatic recalculation. Set only "
                f"one of these values."
            )

    def refresh(self, runner: DynamicCodeRunner[_P, _R], *args: "_P.args", **kwargs: "_P.kwargs") -> None:
        """
        Similar to running the `reset()` method, but this function also *executes* the conversion function, using
        the provided conversion args and kwargs, and produces an `exec_block` that is ready to run in the fast path.

        As an alternative, the `reset()` method can be called instead - in which case an exec_block will be
        automatically generated the next time the fast path function is run.
        """
        if runner.exec_block:
            # There was already an exec block.  Delete it (to recover resources)
            runner.reset()
        runner.exec_code_str = "\n".join(runner.conversion_function(*args, **kwargs))
        runner.exec_block = runner.pdc_stream.add_new_function(runner.exec_code_str)

    def setup_conversion_func(self, runner: DynamicCodeRunner[_P, _R]) -> None:
        runner.conversion_code_ast = get_conversion_code_tree(runner.pdc_stream)
        runner.conversion_function = runner.pdc_stream.add_new_function(runner.conversion_code_ast)


def simple_automatic_recalculation_hash(run_params: Tuple[Tuple[Any, ...], Mapping[str, Any]]) -> int:
    """
    A simple implementation of a recalculation hash.  Normally, the hash would be performed only on *some* of the
    parameter values (the "slow args").  This, sample function, computes a hash over *all* the parameters.
    """
    args, kwargs = run_params
    return hash((args, tuple(kwargs.items())))


def simple_automatic_recalculation_cmp(
    args_1: Tuple[Tuple[Any, ...], Mapping[str, Any]], args_2: Tuple[Tuple[Any, ...], Mapping[str, Any]]
) -> bool:
    """
    A simple implementation to check whether function arguments have changed enough to justify a recalculation of
    fast path exec block.  Normally, the comparison would be performed over only *some* of the parameters (only the
    "slow args").

    Returns True if *any* args have changed (ie for non-equality)
    """
    return args_1 != args_2
