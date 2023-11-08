import ast
from textwrap import dedent

import pytest

from python_dynamic_code.parse.ast_util import AstCommentV2
from python_dynamic_code.parse.ast_util import unparse
from python_dynamic_code.parse.directives import FunctionStartDirective
from python_dynamic_code.parse.directives import StartDirective
from python_dynamic_code.parse.directives import VerbatimDirective
from python_dynamic_code.parse.pdc_nodes import parse
from python_dynamic_code.parse.pdc_nodes import PdcGroup
from python_dynamic_code.parse.pdc_nodes import PdcNode


def test_find_pdc_nodes() -> None:
    """Simple parse and walk showing that we can distinguish PDC nodes (comments that hold a PDC directive)"""
    source = dedent(
        """
        im_python()
        x = 1 + 2
        # I'm a comment
        # PDC-Verbatim comment
        #               a continuation of the directive above
        assert x > 1
        """
    )
    tree = parse(source)

    body_3 = tree.body[3]
    assert isinstance(body_3, PdcNode)
    assert isinstance(body_3.directive, VerbatimDirective)
    assert body_3.directive.instruction_input == "comment a continuation of the directive above", "continuation merged"
    assert not isinstance(tree.body[4], AstCommentV2)
    # Ensure that the resulting tree can compile
    _ = compile(tree, "", "exec")

    assert unparse(tree) == dedent(
        """\
        im_python()
        x = 1 + 2
        "# I\'m a comment"
        '# PDC-Verbatim comment\\n#               a continuation of the directive above'
        assert x > 1"""
    )


def test_find_pdc_groups() -> None:
    """Check a simple scenario of pdc grouping"""
    source = dedent(
        """
        im_python()
        x = 1 + 2
        # I'm a comment
        # PDC-Function
        assert x > 1
        """
    )
    tree = parse(source)
    body_3 = tree.body[3]
    assert isinstance(body_3, PdcGroup)
    assert isinstance(body_3.body[0], PdcNode)
    assert isinstance(body_3.body[0].directive, FunctionStartDirective)
    assert isinstance(body_3.body[1], ast.Assert)

    assert unparse(tree) == dedent(
        """\
    im_python()
    x = 1 + 2
    "# I\'m a comment"
    if True:
        '# PDC-Function'
        assert x > 1"""
    )


def test_find_pdc_section() -> None:
    """
    Test another type of group which is a section. Unlike the Function directive group (which has no end), the section
    has a start and an end.  It can have statements that come after the section (and which would be unindent in the
    unparse)
    """
    source = dedent(
        """
        im_python()
        x = 1 + 2
        # I'm a comment
        # PDC-Start section 1
        assert x > 1
        # PDC-End section 1
        y = 123
        """
    )
    tree = parse(source)
    body_3 = tree.body[3]
    assert isinstance(body_3, PdcGroup)
    assert isinstance(body_3.body[0], PdcNode)
    assert isinstance(body_3.body[0].directive, StartDirective)

    assert unparse(tree) == dedent(
        """\
    im_python()
    x = 1 + 2
    "# I\'m a comment"
    if True:
        '# PDC-Start section 1'
        assert x > 1
        '# PDC-End section 1'
    y = 123"""
    )


@pytest.mark.parametrize(
    "source,expect_result",
    [
        (
            dedent(
                """
        im_python()
        # PDC-Start section 1
        assert x > 1
        # PDC-End section 1
        """
            ),
            dedent(
                """\
    im_python()
    if True:
        '# PDC-Start section 1'
        assert x > 1
        '# PDC-End section 1'"""
            ),
        ),
        (
            dedent(
                """
        im_python()
        # PDC-Function
        # PDC-Start section 1
        assert x > 1
        # PDC-End section 1
        """
            ),
            dedent(
                """\
    im_python()
    if True:
        '# PDC-Function'
        if True:
            '# PDC-Start section 1'
            assert x > 1
            '# PDC-End section 1'"""
            ),
        ),
        (
            dedent(
                """
        im_python()
        # PDC-Function
        # PDC-Start section 1
        assert x > 1
        # PDC-End section 1
        one_more_thing()
        """
            ),
            dedent(
                """\
    im_python()
    if True:
        '# PDC-Function'
        if True:
            '# PDC-Start section 1'
            assert x > 1
            '# PDC-End section 1'
        one_more_thing()"""
            ),
        ),
        (
            dedent(
                """
        im_python()
        # PDC-Start section 1
        # PDC-Start section 2
        stuff()
        # PDC-End section 2
        assert x > 1
        # PDC-End section 1
        """
            ),
            dedent(
                """\
    im_python()
    if True:
        '# PDC-Start section 1'
        if True:
            '# PDC-Start section 2'
            stuff()
            '# PDC-End section 2'
        assert x > 1
        '# PDC-End section 1'"""
            ),
        ),
        (
            dedent(
                """
        im_python()
        # PDC-Start section 1
        # PDC-Start section 2
        stuff()
        # PDC-End section 2
        # PDC-Start section 2.1
        other_stuff()
        # PDC-End section 2.1
        assert x > 1
        # PDC-End section 1
        """
            ),
            dedent(
                """\
    im_python()
    if True:
        '# PDC-Start section 1'
        if True:
            '# PDC-Start section 2'
            stuff()
            '# PDC-End section 2'
        if True:
            '# PDC-Start section 2.1'
            other_stuff()
            '# PDC-End section 2.1'
        assert x > 1
        '# PDC-End section 1'"""
            ),
        ),
    ],
)
def test_find_pdc_section_scenarios(source: str, expect_result: str) -> None:
    """
    Try some more complicated scenarios (nested sections, etc)
    """
    tree = parse(source)
    assert unparse(tree) == expect_result
