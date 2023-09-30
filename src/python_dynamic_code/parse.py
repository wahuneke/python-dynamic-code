from functools import cached_property
from typing import Iterator, Tuple, Optional, Collection, Sequence


class PdcDirective:
    """A string directive parsed directly from source.  May apply to multiple lines"""

    start: int
    # The first line of this directive
    end: int
    # The last line (usually equal to start except for multi-line directives)
    directive: str
    # The directive (e.g. 'start', 'end', 'killif', etc)
    instruction_input: str
    # Everything read _after_ the directive name (possibly empty string)

    @classmethod
    def parse_from(cls, iter: Iterator[Tuple[int, str]]) -> Tuple[Optional["PdcDirective"], Tuple[int, str]]:
        """
        Parse directive from the given line(s) and advance the iterator as needed.  Return the first
        line that was _not_ parsed as a directive
        """
        next(iter)
        return None, (1, "")


class PdcAttachment:
    """
    Instructions that get attached to a PDC Section and control its behavior within PDC
      e.g:
        * hide this section
        * do a find and replace
        * evaluate something and then hide based on a condition
    """


class PdcSection:
    """
    A set of source lines which may have subsections and also has section attachments, such as instructions about
    how to process the given section, what code to rewrite, what lines to drop, etc
    """

    offset: int  # e.g. 0 if this section starts at first line of its parent section
    tab_offset: int  # e.g. 4, the number of positions to the right these lines are shifted from the parent block
    parent: Optional["PdcSection"]
    sub_sections: Collection["PdcSection"]
    attachments: Collection[PdcAttachment]
    source_lines: Sequence[str]
    source_start: int
    source_end: int


class PdcStream:
    """
    Take a stream of Python code which may have 'PDC' annotations in it.  Parse the annotations and find and identify
    the sections, nested sections, and annotations that go with each
    """

    source_lines: Sequence[str]

    @cached_property
    def sections(self) -> Sequence[PdcSection]:
        for line_no, line in enumerate(self.source_lines):
            if line.lstrip("").startswith("# PDC"):
                print("hi")
        return []
