import pytest

from python_dynamic_code.util import DictStack


def test_dict_stack() -> None:
    d1: DictStack = DictStack()
    d1.push({"a": 1, "b": 2})
    d1.push({"a": 3, "c": 4})
    assert set(d1) == {"a", "b", "c"}
    assert len(d1) == 3
    assert d1["a"] == 3
    assert d1["b"] == 2
    assert d1["c"] == 4
    d1.pop()
    assert d1["a"] == 1
    assert d1["b"] == 2
    with pytest.raises(KeyError):
        _ = d1["c"]
    assert len(d1) == 2
    assert set(d1) == {"a", "b"}
    d1.pop()
    with pytest.raises(KeyError):
        _ = d1["a"]
    assert len(d1) == 0
