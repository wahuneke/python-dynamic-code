"""
Verify function of conversion writer, providing handling of code having line directives, section directives and code
with varying level of nested blocks.
"""
import ast
import itertools
from dataclasses import dataclass
from textwrap import dedent
from typing import List
from typing import Type
from typing import Union

import pytest
from pytest_mock import MockerFixture

from python_dynamic_code.conversion_code.writer import ConversionCodeWriter
from python_dynamic_code.parse import parse
from python_dynamic_code.parse import PdcSection
from python_dynamic_code.parse.ast_util import unparse
from python_dynamic_code.parse.directives import PdcDirective
from python_dynamic_code.parse.pdc_nodes import PdcDirectiveProtocol


def run_test(mocker: MockerFixture, mock_directives: Type[PdcDirectiveProtocol], source: str) -> str:
    """
    Run conversion on an AST which has ast_comments.Comment nodes and actual code nodes
    all ready to go in it.  The comment nodes should invoke directives that are subclasses of
    `mock_directives`.  `mock_directives` will be used instead of the real directives.

    Output the `unparse`d result of the conversion.
    """

    tree = parse(source, directive_parent_class=mock_directives)
    writer = ConversionCodeWriter("controller_name", source, rule_group_class=PdcSection)
    conversion_code = writer.visit(tree)
    assert isinstance(conversion_code, ast.AST)
    return unparse(conversion_code)


class NoDirectives(PdcDirective):
    """A parent class of directives having no directives in it"""


class SimpleDirectiveFamily(PdcDirective):
    """A basic collection of annotations and directives"""

    PREFIX = "# Test-"


class StartDirective(SimpleDirectiveFamily):
    """A directive which starts a section"""

    TAG = "Mystart"
    group_requires_end_tag = True
    is_end_tag = False
    section_name = "section_name"

    def run_rule(
        self, original_source: str, current_node: Union[ast.AST, List[ast.AST]]
    ) -> Union[ast.AST, List[ast.AST]]:
        return []


class EndDirective(SimpleDirectiveFamily):
    """A directive which starts a section"""

    TAG = "Myend"
    group_requires_end_tag = True
    is_end_tag = True
    section_name = "section_name"


class CopyLineDirective(SimpleDirectiveFamily):
    """Indicates that the node following should be echoed into conversion code"""

    TAG = "CopyLine"

    def run_rule(
        self, original_source: str, current_node: Union[ast.AST, List[ast.AST]]
    ) -> Union[ast.AST, List[ast.AST]]:
        if not isinstance(current_node, list):
            current_node = [current_node]

        return list(
            itertools.chain(
                current_node,
                (
                    ast.Expr(
                        value=ast.Yield(
                            value=ast.Constant(value=ast.get_source_segment(original_source, node=node)), kind=None
                        )
                    )
                    for node in current_node
                ),
            )
        )


class CopySectionDirective(SimpleDirectiveFamily):
    """Indicates that the entire section should be echoed into conversion code"""

    TAG = "Copy"


@dataclass
class _Scenario:
    id_str: str
    test_source: str
    expected_output: str
    mock_directives: Type[PdcDirective]


@pytest.mark.parametrize(
    "scenario",
    [
        _Scenario(
            "with no annotations, conversion code will be equal to the original code",
            """\
            im_python()
            """,
            """\
            im_python()""",
            NoDirectives,
        ),
        _Scenario(
            "Quick demo of a section",
            """\
            im_python()
            # Test-MyStart
            in_section()
            # Test-MyEnd
            """,
            """\
            im_python()
            '# Test-MyStart'
            in_section()
            '# Test-MyEnd'""",
            SimpleDirectiveFamily,
        ),
        _Scenario(
            "Simple Copy directive",
            """\
            im_python()
            # Test-CopyLine
            in_section()
            """,
            """\
            im_python()
            in_section()
            yield 'in_section()'""",
            SimpleDirectiveFamily,
        ),
    ],
    ids=lambda scenario: scenario.id_str,
)
def test_simple(mocker, scenario) -> None:
    assert run_test(mocker, scenario.mock_directives, dedent(scenario.test_source)) == dedent(scenario.expected_output)


@pytest.mark.parametrize(
    "scenario",
    [
        _Scenario(
            "copy directive in front of an IF block",
            """\
            im_python()
            # Test-CopyLine
            if True:
                in_section()
            """,
            """\
            im_python()
            if True:
                in_section()
            yield 'if True:\\n    in_section()'""",
            SimpleDirectiveFamily,
        ),
        _Scenario(
            "copy directive within IF block",
            """\
            im_python()
            if True:
                # Test-CopyLine
                in_section()
            """,
            """\
            im_python()
            if True:
                in_section()
                yield 'in_section()'""",
            SimpleDirectiveFamily,
        ),
    ],
    ids=lambda scenario: scenario.id_str,
)
def test_verbatim_scenarios(mocker, scenario) -> None:
    assert run_test(mocker, scenario.mock_directives, dedent(scenario.test_source)) == dedent(scenario.expected_output)
