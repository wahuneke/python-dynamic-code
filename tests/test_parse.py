import pytest


@pytest.mark.parametrize(("code_string", "expected_annotations"), [
    ("", []),
    ("Hello", []),
    # Annotations should not be found within strings, even if they are on their
    # own line
    ("\"\"\"\n # PDC-Start section 1\n\"\"\"\n", [])
])
def test_find_tags(code_string, expected_annotations) -> None:
    assert list(find_annotations(code_string)) == expected_annotations