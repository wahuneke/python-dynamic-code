import ast
import itertools
from dataclasses import dataclass
from typing import ClassVar, Union
from typing import Collection
from typing import Iterable
from typing import List
from typing import NoReturn
from typing import Optional
from typing import Self
from typing import Tuple

from more_itertools import peekable


@dataclass
class PdcDirective:
    """A string directive parsed directly from source.  May apply to multiple lines"""

    PREFIX: ClassVar[str] = "# PDC-"
    TAG: ClassVar[Optional[str]] = None

    start: int
    # The first line of this directive
    end: int
    # The last line (usually equal to start except for multi-line directives)
    directive: str
    # The directive (e.g. 'start', 'end', 'killif', etc)
    instruction_input: str
    # Everything read _after_ the directive name (possibly empty string)
    tab_offset: int
    # Number of spaces to the left of the directive prefix (e.g. 4 for '    # PDC-Start')

    def incorporate_continuation_line(self, line_no: int, line: str) -> bool:
        """
        Incorporate the given line into this directive.  This is only used for multi-line directives
        Return True if the line was incorporated, False if it was not
        """
        if line_no != self.end + 1:
            return False

        pre_space, _, content = line.partition("#")
        if pre_space == " " * self.tab_offset:
            # Extra -1 because self.PREFIX includes the hash
            expect_inner_shift = len(f"{self.PREFIX}{self.TAG} ") - 1
            if content.startswith(" " * expect_inner_shift):
                self.instruction_input += content[expect_inner_shift:]
                self.end = line_no
                return True

        return False

    def update_rules(self, current_section_rules: List["SectionAttachment"]) -> None:
        """
        Update rules given the current one.  For instance, if this is a KillSection rule, go through and eliminate
        any current rules which contradict this (e.g. verbatim rules)
        """
        pass

    def run_rule(self, original_source: str, current_node: Union[ast.AST, List[ast.AST]]) -> Union[ast.AST, List[ast.AST]]:
        """
        Apply this rule's operations on the current node (generally, don't apply to this node's children). Those will
        be visited later and run_rule will go again for those child nodes
        """
        return None

    @staticmethod
    def raise_unexpected_end() -> NoReturn:
        raise ValueError(
            "One or more PDC line directives appear to precede the end of input code. Line "
            "directives must be attached to a line of code and cannot be the last non-empty "
            "line of code input."
        )

    @classmethod
    def parse_from(cls, it: "peekable[Tuple[int, str]]") -> Optional["Self"]:
        """
        Parse directive from the given line(s) and advance the iterator as needed.  If the given line(s) are not a
        directive, return None and do not advance the iterator
        """
        try:
            line_no, line = it.peek()
        except StopIteration:
            return None
        if (result := cls.as_directive(line_no, line)) is None:
            return None
        else:
            # Catch up with the peek we just did
            _ = next(it)
            # Keep peeking and incorportating lines until we find a non-continuation line
            try:
                line_no, line = it.peek()
            except StopIteration:
                return result
            while result.incorporate_continuation_line(line_no, line):
                _ = next(it)
                line_no, line = it.peek()

            return result

    @classmethod
    def as_directive(cls, line_no: int, line: str) -> Optional["Self"]:
        """
        If the given line is a directive, find the subclass that matches it and instantiate it.  Otherwise, return None
        """
        result = cls._as_directive(line_no, line)
        if result is None and line.lstrip(" ").startswith(cls.PREFIX):
            raise ValueError(
                f"Source line {line_no} contains a directive that looks like a PDC directive but is "
                f"unrecognized. Possible spelling error for: '{line}'?"
            )
        return result

    @classmethod
    def _as_directive(cls, line_no: int, line: str) -> Optional["Self"]:
        """
        Recursive worker
        """
        if cls.TAG is None:
            for sub_cls in cls.__subclasses__():
                result = sub_cls._as_directive(line_no, line)
                if result is not None:
                    return result
        else:
            stripped_line = line.lstrip(" ")
            if stripped_line == (cls.PREFIX + cls.TAG) or stripped_line.startswith(cls.PREFIX + cls.TAG + " "):
                return cls(
                    line_no,
                    line_no,
                    cls.TAG,
                    stripped_line[len(cls.PREFIX + cls.TAG) :].lstrip(" "),
                    cls.get_tab_offset(line),
                )
        return None

    @staticmethod
    def get_tab_offset(line: str) -> int:
        """
        Get the tab offset of the given line
        """
        stripped_line = line.lstrip(" ")
        return len(line) - len(stripped_line)

    @classmethod
    def find_directives(cls, block: str) -> Collection["Self"]:
        """
        Find all directives in the given block of text
        """
        line_it: "peekable[Tuple[int, str]]" = peekable(enumerate(iter(block.split("\n"))))
        result: List["Self"] = []
        while True:
            try:
                d = cls.parse_from(line_it)
                if d is not None:
                    result.append(d)
                else:
                    _ = next(line_it)
            except StopIteration:
                break

        return result

    def raise_unexpected(self) -> NoReturn:
        """A generic error message for directives appearing in unexpected places during parsing"""
        raise ValueError(f"Unexpected directive: {self}")

    @classmethod
    def apply_conversion_updates(cls, directives: Iterable["Self"], source: str, line_no: int) -> str:
        """Apply conversion updates, in sequence and return the cumulative effect"""
        for directive in directives:
            source = directive.update_conversion_output(source, line_no)

        return source

    @classmethod
    def apply_exec_updates(cls, directives: Iterable["Self"], source: str, line_no: int) -> str:
        """Apply exec code updates, in sequence and return the cumulative effect"""
        for directive in directives:
            source = directive.update_exec_output(source, line_no)

        return source

    # noinspection PyMethodMayBeStatic
    def update_conversion_output(self, source: str, line_no: int) -> str:
        """Apply any changes to conversion output (including possibly dropping it altogether)"""
        _ = line_no
        return source

    # noinspection PyMethodMayBeStatic
    def update_exec_output(self, source: str, line_no: int) -> str:
        """Apply any changes to output destined to _exec_ code (including possibly dropping it altogether)"""
        _ = line_no
        return source


class SectionAttachment(PdcDirective):
    """A type of directive that is attached to a section and applies to the entire section."""


class LineDirective(PdcDirective):
    """A type of directive that is attached to a line and applies to that line only."""


class FunctionStartDirective(LineDirective):
    """
    Indicates the beginning of the fast path function. Lines preceding this will never be included in conversion
    code (or in exec code)
    """

    TAG = "Function"

    @property
    def section_name(self) -> str:
        return "__pdc_function"

    group_requires_end_tag = False
    is_end_tag = False


class StartDirective(PdcDirective):
    TAG = "Start"

    @property
    def section_name(self) -> str:
        return self.instruction_input

    group_requires_end_tag = True
    is_end_tag = False


class EndDirective(PdcDirective):
    TAG = "End"

    @property
    def section_name(self) -> str:
        return self.instruction_input

    is_end_tag = True

    def raise_end_does_not_match_start(self, start_directive: StartDirective) -> NoReturn:
        raise Exception(
            f"End directive ('{self.section_name}', line {self.start}) "
            f"does not match start directive "
            f"('{start_directive.section_name}', line {start_directive.start})"
        )


class VerbatimDirective(SectionAttachment):
    """
    This directive, attached to a section, indicates that the entire section should be echoed verbatim into conversion
    output
    """

    TAG = "Verbatim"

    def run_rule(self, original_source: str, current_node: Union[ast.AST, List[ast.AST]]) -> Union[ast.AST, List[ast.AST]]:
        if not isinstance(current_node, list):
            current_node = [current_node]

        return list(
            itertools.chain(
        current_node,
                (
                    ast.Expr(value=ast.Yield(
                        value=ast.Constant(value=ast.get_source_segment(original_source, node=node)), kind=None))
                    for node in current_node
                )
            )
        )


class TemplateDirective(SectionAttachment):
    """
    This directive, attached to a section, indicates that string replacements should be run for substrings found in this
    section.  With the exception of template replacements, the section should be echoed verbatim into conversion output.
    """

    TAG = "TemplateCode"


class ReplaceDirective(SectionAttachment):
    """This directive identifies a substring that should be replaced, whenever it occurs in the following section"""

    TAG = "Replace"

    @property
    def replace(self) -> str:
        return self.instruction_input


class KillSectionDirective(SectionAttachment):
    """
    This directive indicates that this section should be removed from conversion output. This is useful when used
    in a subsection to remove a block from the parent section
    """

    TAG = "Kill"


class KillIfSectionDirective(SectionAttachment):
    """
    This directive indicates that this section should be removed from conversion output. A condition should be provided
    which will be evaluated in the context of the conversion function. If the condition evaluates to True, the section
    will be removed. If the condition evaluates to False, the section will be kept.
    """

    TAG = "KillIf"

    @property
    def condition(self) -> str:
        return self.instruction_input


class VerbatimLineDirective(LineDirective):
    """Indicates that the following line should be echoed verbatim into conversion output"""

    TAG = "VerbatimLine"
    def run_rule(self, original_source: str, current_node: Union[ast.AST, List[ast.AST]]) -> Union[ast.AST, List[ast.AST]]:
        if not isinstance(current_node, list):
            current_node = [current_node]

        return list(itertools.chain(
            current_node,
            (
            ast.Expr(value=ast.Yield(value=ast.Constant(value=ast.get_source_segment(original_source, node=node)), kind=None))
            for node in current_node
            )
        ))


class KillLineDirective(LineDirective):
    """Indicates that the following line should be removed from conversion output"""

    TAG = "KillLine"
