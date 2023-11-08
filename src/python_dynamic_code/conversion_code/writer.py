import ast
import itertools
import re
from ast import NodeTransformer
from dataclasses import field
from typing import Any
from typing import Iterable
from typing import List
from typing import MutableMapping
from typing import Optional
from typing import Protocol
from typing import runtime_checkable
from typing import Sequence
from typing import Type
from typing import Union

from typing_extensions import Self


__all__ = ["ConversionCodeWriter"]

from python_dynamic_code.parse.pdc_nodes import PdcGroup, PdcNode, PdcDirectiveProtocol
from python_dynamic_code.util import iter_of_type

_TemplateMapType = MutableMapping[re.Pattern[str], Optional[str]]


@runtime_checkable
class RuleMakerProtocol(Protocol):
    lineno: int
    """The original source line where this rule was declared"""

    def update_rules(self, current_rules: Sequence[Union["RuleMakerProtocol", "SectionRuleMakerProtocol"]]) -> None:
        """
        Update rules given the current one.  For instance, if this is a KillSection rule, go through and eliminate
        any current rules which contradict this (e.g. verbatim rules).

        The provided rule list should be modified in place.
        """
        ...

    # noinspection PyMethodMayBeStatic
    def run_rule(
        self, original_source: str, current_node: Union[ast.AST, List[ast.AST]]
    ) -> Union[ast.AST, List[ast.AST]]:
        """
        Apply this rule's operations on the current node (generally, don't apply to this node's children). Those will
        be visited later and run_rule will go again for those child nodes
        """
        ...


class SectionRuleMakerProtocol(RuleMakerProtocol):
    pass


# noinspection PyPropertyDefinition
class RuleMakerGroupProtocol(Protocol):
    def get_attachments(self) -> Iterable[SectionRuleMakerProtocol]:
        ...

    @classmethod
    def parse_from(cls, parse_from_node: "PdcGroup[PdcDirectiveProtocol]", parse_sub_sections: bool = True) -> "Self":
        ...


class ConversionCodeWriter(NodeTransformer):
    """
    This object maintains information about the current transformations and echo rules currently being applied to
    the output stream and applies the rules appropriately. It outputs conversion code as a brand new AST,
    including:

      * original logic
      * output statements (instructions to add to the output of the conversion code, ie exec code)
    """

    conversion_controller_name: str
    """
    The symbol name for the conversion controller.  This is needed so that conversion code can call methods on the
    controller.  This will usually be the name of the function that has had the DynamicCodeBuilder attached to it.
    """

    full_source: str
    """
    The full source code for the tree being converted. Line numbers and columns should line up with the code
    coordinates found in the nodes of the tree
    """

    rule_group_class: Type[RuleMakerGroupProtocol]
    """This class will be used to process rule groupings (PDC Sections)"""

    section_stack: List["RuleMakerGroupProtocol"] = field(default_factory=list, init=False)
    """This stack allows inner sections to override the settings of outer sections"""

    current_section_rules: List["SectionRuleMakerProtocol"] = field(default_factory=list, init=False)
    """
    whenever there's a change in the section stack, this set of rules is updated
    The rules here represent all the section attachment rules from all section in the stack, **with** priority
    override being applied for newer sections.  SectionAttachments from more recent sections have the option to
    override or rewrite section rules from lower sections.
    """

    current_line_directives: List[RuleMakerProtocol] = field(default_factory=list, init=False)
    """
    as we progress, keep track of any line directives that came up recently
    These get applied and then reset to empty list as soon as a node comes along that can have a line directive applied
    to it
    """

    def __init__(
        self,
        conversion_controller_name: str,
        full_source: str,
        rule_group_class: Type[RuleMakerGroupProtocol],
    ) -> None:
        self.conversion_controller_name = conversion_controller_name
        self.full_source = full_source
        self.rule_group_class = rule_group_class
        self.section_stack = list()
        self.current_section_rules = list()
        self.current_line_directives = list()

    def push_section_rules(self, section: RuleMakerGroupProtocol) -> None:
        self.section_stack.append(section)
        self.build_current_section_attachments()

    def pop_section_rules(self) -> None:
        if self.current_line_directives:
            raise ValueError(
                "PDC Section ended with one or more line directives still in effect. Line directives "
                "be followed by a line (or block) of code. Error occured at line no: "
                + str(self.current_line_directives[0].lineno)
            )
        self.section_stack.pop()
        self.build_current_section_attachments()

    def build_current_section_attachments(self) -> None:
        """Update current section attachments by looking at the current section stack"""
        self.current_section_rules.clear()
        for section in self.section_stack:
            if self.current_section_rules:
                # Update existing rules using the rules in the newer (higher priority) section
                for rule in section.get_attachments():
                    rule.update_rules(self.current_section_rules)

            self.current_section_rules.extend(section.get_attachments())

    def visit(self, node: ast.AST) -> Optional[Union[ast.AST, List[Any]]]:
        result: Union[ast.AST, List[ast.AST]]

        if isinstance(node, PdcGroup):
            if self.current_line_directives:
                raise ValueError(
                    f"PDC Section at line no {node.lineno} is preceded by line directives. Line "
                    f"directives must be followed by either more line directives or by Python code"
                )

            self.push_section_rules(self.rule_group_class.parse_from(node, parse_sub_sections=False))
            # Run visitor for all child nodes on node (but, key, not the group node itself)
            result = list(
                filter(
                    None,
                    itertools.chain.from_iterable(
                        lc if isinstance(lc, list) else [lc] for lc in (self.visit(c) for c in node.body)
                    ),
                )
            )
            self.pop_section_rules()
            return result
        elif isinstance(node, PdcNode):
            if isinstance(node.directive, RuleMakerProtocol):
                self.current_line_directives.append(node.directive)
            else:
                # Nothing to be done here.  Presumably this directive has already been processed and incorporated
                # into the PdcSection
                pass

            return None
        else:
            node_directives: List[Union[RuleMakerProtocol, SectionRuleMakerProtocol]]

            if self.current_line_directives:
                node_directives = list(self.current_section_rules)
                # Update our current section directives based on the line directives (which have the highest priority,
                # but only for the current node)
                for rule in self.current_line_directives:
                    rule.update_rules(node_directives)
                node_directives.extend(self.current_line_directives)
            else:
                node_directives = list(self.current_section_rules)

            result = [node]
            # Run each rule until result is None or until we have run all the rules
            for rule in node_directives:
                result = rule.run_rule(self.full_source, result)
                if not result:
                    break

            if isinstance(result, list):
                return list(filter(None, (super().visit(n) for n in iter_of_type(result, ast.AST))))
            elif result is not None:
                return super().visit(result)
