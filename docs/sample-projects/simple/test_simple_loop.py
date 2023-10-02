from textwrap import dedent

from simple_lib import simple_unroll_fast_path


def test_conversion_code() -> None:
    """
    Check that the conversion code will compile input as expected.

    Checking the content of conversion code is messy business. In real projects, it will be easier
    to confirm only some instances of exec code.
    """
    expected_conversion_code = dedent(
        """\
    output_code = ""
    output_code += "results: List[int] = []\\n"
    for f in call_funcs:
        template_value = simple_unroll_fast_path._compute_Section_1("f()", locals())
        output_code += "results.append(" + template_value + ")\\n"
    """
    )
    assert simple_unroll_fast_path.get_conversion_code(call_funcs=[]) == expected_conversion_code
