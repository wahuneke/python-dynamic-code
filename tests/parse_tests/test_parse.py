import re
from textwrap import dedent
from typing import Sequence

import pytest
from _pytest.mark import ParameterSet

from python_dynamic_code.parse.directives import KillLineDirective
from python_dynamic_code.parse.directives import PdcDirective
from python_dynamic_code.parse.directives import StartDirective
from python_dynamic_code.parse.directives import VerbatimLineDirective
from python_dynamic_code.parse.parser import PdcSection
from python_dynamic_code.runner import PdcStream


def do_parse(input_code: str) -> Sequence[PdcSection]:
    # Reference the sections property to trigger parsing
    return PdcStream("test", input_code.splitlines()).sections


@pytest.mark.parametrize(
    ("code_string", "expected_annotations"),
    [
        ("", []),
        ("Hello", []),
        ("\n# PDC-Start section 1\n\n", [StartDirective(1, 1, "Start", "section 1", 0)]),
        # Annotations should not be found within strings, even if they are on their
        # own line
        ParameterSet(
            ['"""\n # PDC-Start section 1\n"""\n', []],
            marks=[pytest.mark.xfail(reason="Filtering out this directive would be tough in current implementation")],
            id="valid directive but in a string",
        ),
    ],
)
def test_find_tags(code_string, expected_annotations) -> None:
    assert list(PdcDirective.find_directives(code_string)) == expected_annotations


@pytest.mark.parametrize(
    "bad_input, expected_exception_string",
    [
        # End directive has wrong name
        (
            "# PDC-Start section 1\n# PDC-End section 2\n",
            "End directive ('section 2', line 1) does not match start directive ('section 1', line 0)",
        ),
        (
            "# PDC-Start section 1\n# PDC-Start section 1.1\n# PDC-End section 1",
            "End directive ('section 1', line 2) does not match start directive ('section 1.1', line 1)",
        ),
        # End directive is missing
        ("# PDC-Start section 1\n", "Section section 1 started on line 0 but never ended (expected an end directive)"),
        (
            "# PDC-Start section 1\n# PDC-Start section 1.1\n# PDC-End section 1.1\n",
            "Section section 1 started on line 0 but never ended (expected an end directive)",
        ),
        # Line directive has no line to attach to
        (
            "# PDC-Start section 1\n# PDC-VerbatimLine\n# PDC-End section 1\n",
            "One or more PDC line directives appear to precede the end of section 'section 1' on line 2. Line "
            "directives must be attached to a line of code within the section where they are declared",
        ),
    ],
)
def test_catch_directive_errors(bad_input, expected_exception_string) -> None:
    with pytest.raises(Exception, match=re.escape(expected_exception_string)):
        _ = do_parse(bad_input)


class TestSectionParse:
    def test_simple_section_parse(self):
        pdc = PdcStream(
            "test",
            dedent(
                """\
        # PDC-Start section 1
        # PDC-End section 1
        """
            ).splitlines(),
        )

        section = pdc.sections
        assert len(section) == 1
        assert section[0].start_directive.section_name == "section 1"

    def test_simple_subsections_parse(self):
        sections = do_parse(
            dedent(
                """\
        # PDC-Start section 1
           Some section 1 code
           # PDC-Start section 1.1
                Some section 1.1 code
           # PDC-End section 1.1
        # PDC-End section 1
        """
            )
        )

        assert len(sections) == 1
        assert sections[0].start_directive.section_name == "section 1"
        assert sections[0].source_lines == [
            "",
            "   Some section 1 code",
            "",
            "        Some section 1.1 code",
            "",
            "",
        ]
        assert len(sections[0].sub_sections) == 1
        assert sections[0].sub_sections[0].start_directive.section_name == "section 1.1"
        assert sections[0].sub_sections[0].source_lines == ["", "        Some section 1.1 code", ""]


@pytest.mark.parametrize(
    ("input_code", "expect_line_attachments"),
    [
        # We can correctly pickup a line directive and connect it to a line of source code
        (
            dedent(
                """\
    # PDC-Start section 1
    # PDC-VerbatimLine
    Some Code
    # PDC-End section 1
    """
            ),
            {2: [VerbatimLineDirective(1, 1, "VerbatimLine", "", 0)]},
        ),
        # We can also correctly handle multiple line directives, 'stacked' for the same line of source code
        (
            dedent(
                """\
    # PDC-Start section 1
    # PDC-VerbatimLine
    # PDC-KillLine
    Some Code
    # PDC-End section 1
    """
            ),
            {3: [VerbatimLineDirective(1, 1, "VerbatimLine", "", 0), KillLineDirective(2, 2, "KillLine", "", 0)]},
        ),
    ],
)
def test_line_directive_parse(input_code, expect_line_attachments):
    """A few simple tests for parsing line directives"""
    sections = do_parse(input_code)

    assert len(sections) == 1
    assert sections[0].line_attachments == expect_line_attachments


def test_simple_directive_parse():
    class PdcDirectiveTest(PdcDirective):
        pass

    class D1(PdcDirectiveTest):
        TAG = "Tag1"

    class D2(PdcDirectiveTest):
        TAG = "Tag2"

    results = PdcDirectiveTest.find_directives(
        dedent(
            """\
    # PDC-Tag1
    # PDC-Tag2
    """
        )
    )
    assert results == [D1(0, 0, "Tag1", "", 0), D2(1, 1, "Tag2", "", 0)]

    results = PdcDirectiveTest.find_directives(
        dedent(
            """\
    # PDC-Tag1
    Other text
       # PDC-Tag2
    """
        )
    )
    assert results == [D1(0, 0, "Tag1", "", 0), D2(2, 2, "Tag2", "", 3)]

    results = PdcDirectiveTest.find_directives(
        dedent(
            """\

    # PDC-Tag1
    #          Continuation text
       # PDC-Tag2
    """
        )
    )
    assert results == [D1(1, 2, "Tag1", "Continuation text", 0), D2(3, 3, "Tag2", "", 3)]
