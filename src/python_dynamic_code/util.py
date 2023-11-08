import importlib.util
import itertools
import sys
from dataclasses import dataclass
from dataclasses import field
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import Any
from typing import Collection
from typing import Generic
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Set
from typing import Type
from typing import TypeVar

import more_itertools

__all__ = ["has_instance", "DictStack", "count_indent_columns", "not_optional", "import_module_from_file"]

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")


def not_optional(val: Optional[_T]) -> _T:
    """Raise TypeError if the given value is None"""
    if val is None:
        raise TypeError("Value cannot be None")
    return val


def iter_of_type(it: Iterable[Any], t: Type[_T]) -> Iterator[_T]:
    """Typecast with type assertion.  TypeError will be raised if any item is not of the given type"""
    for i in it:
        if not isinstance(i, t):
            raise TypeError(f"Expected {t.__name__}, got {type(i).__name__}")
        yield i


def import_module_from_file(module_name: str, module_file: Path) -> ModuleType:
    spec = not_optional(importlib.util.spec_from_file_location(module_name, str(module_file.absolute())))
    module = not_optional(importlib.util.module_from_spec(spec))
    sys.modules[module_name] = module
    not_optional(spec.loader).exec_module(module)
    return module


def count_indent_columns(line: str) -> int:
    """Count the number of leading whitespace columns in the given line"""
    return len(line) - len(line.lstrip())


def has_instance(it: Collection[Any], t: type) -> bool:
    """Return true if the given collection contains at least one item that is an instance of the given type"""
    return any(isinstance(i, t) for i in it)


@dataclass
class DictStack(Mapping[_KT, _VT], Generic[_KT, _VT]):
    """
    A type of mapping where lookups are performed against a stack of dictionaries, so that values pushed at top
    can override those below. Further, popping topmost dictionary may restore previous values
    """

    mapping_stack: List[MutableMapping[_KT, _VT]] = field(default_factory=list)
    """
    Stack of dictionaries where topmost will be the _first_ dictionary consulted for lookups (ie, overrides others)
    """

    @cached_property
    def _key_set(self) -> Set[_KT]:
        return set(itertools.chain.from_iterable(self.mapping_stack))

    def _clear_key_set(self) -> None:
        """Clears the cached property so it will be recalculated on next access"""
        if "_key_set" in self.__dict__:
            del self.__dict__["_key_set"]

    def __len__(self) -> int:
        return more_itertools.ilen(self.__iter__())

    def __iter__(self) -> Iterator[_KT]:
        return iter(self._key_set)

    def set(self, k: _KT, v: _VT) -> None:
        """
        Update the value in the _first_ dictionary in the stack that contains the given key. Raises KeyError if not
        found
        """
        if k not in self._key_set:
            raise KeyError(k)

        for d in reversed(self.mapping_stack):
            if k in d:
                d[k] = v
                return

        # THIS SHOULD NOT BE REACHABLE - but it might happen if key set is out of sync, e.g. if inner dicts are modified
        # after they are pushed into this stack
        assert False, "Should not be reachable"

    def push(self, d: MutableMapping[_KT, _VT]) -> None:
        self._clear_key_set()
        self.mapping_stack.append(d)

    def pop(self) -> MutableMapping[_KT, _VT]:
        self._clear_key_set()
        return self.mapping_stack.pop()

    def __getitem__(self, item: _KT) -> _VT:
        for d in reversed(self.mapping_stack):
            try:
                return d[item]
            except KeyError:
                pass
        raise KeyError(item)

    def __contains__(self, item: object) -> bool:
        return item in self._key_set
