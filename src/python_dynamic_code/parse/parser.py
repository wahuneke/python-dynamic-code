import ast
from _ast import AST
from ast import NodeVisitor
from dataclasses import dataclass
from typing import Any
from typing import Iterable
from typing import List
from typing import Mapping
from typing import MutableMapping
from typing import Sequence
from typing import TYPE_CHECKING

from python_dynamic_code.parse.directives import LineDirective
from python_dynamic_code.parse.directives import SectionAttachment
from python_dynamic_code.parse.pdc_nodes import PdcDirectiveProtocol
from python_dynamic_code.parse.pdc_nodes import PdcGroup
from python_dynamic_code.parse.pdc_nodes import PdcNode

if TYPE_CHECKING:
    from python_dynamic_code.conversion_code.writer import SectionRuleMakerProtocol


__all__ = [
    "PdcSection",
]


@dataclass
class PdcSection:
    """
    A set of source lines which may have subsections and also has section attachments, such as instructions about
    how to process the given section, what code to rewrite, what lines to drop, etc
    """

    pdc_group: PdcGroup[PdcDirectiveProtocol]
    sub_sections: Sequence["PdcSection"]
    attachments: Sequence["SectionRuleMakerProtocol"]
    statement_attachments: Mapping[ast.AST, Sequence["LineDirective"]]

    def get_attachments(self) -> Iterable["SectionRuleMakerProtocol"]:
        return self.attachments

    @property
    def name(self) -> str:
        return self.pdc_group.group_name

    @classmethod
    def parse_from(
        cls, parse_from_node: "PdcGroup[PdcDirectiveProtocol]", parse_sub_sections: bool = True
    ) -> "PdcSection":
        class Visitor(NodeVisitor):
            """Walk the whole subtree and collect: line directives, section attachments, and sub sections"""

            child_sections: List[PdcSection]
            attachments: List[SectionAttachment]
            statement_attachments: MutableMapping[ast.AST, Sequence["LineDirective"]]
            building_line_attachment: List[LineDirective]

            def __init__(self) -> None:
                self.child_sections = []
                self.attachments = []
                self.statement_attachments = dict()
                self.building_line_attachment = []

            def generic_visit(self, node: AST) -> None:
                if isinstance(node, PdcGroup):
                    if parse_sub_sections:
                        self.child_sections.append(cls.parse_from(node))
                else:
                    super().generic_visit(node)

            def visit(self, node: AST) -> Any:
                if not isinstance(node, PdcNode):
                    if self.building_line_attachment:
                        self.statement_attachments[node] = self.building_line_attachment
                        self.building_line_attachment = []

                return super().visit(node)

            def visit_PdcNode(self, node: PdcNode[PdcDirectiveProtocol]) -> None:
                child_directive = node.directive
                if isinstance(child_directive, SectionAttachment):
                    self.attachments.append(child_directive)
                elif isinstance(child_directive, LineDirective):
                    self.building_line_attachment.append(child_directive)

        visitor = Visitor()
        visitor.visit(parse_from_node)

        return cls(
            parse_from_node,
            visitor.child_sections,
            visitor.attachments,
            visitor.statement_attachments,
        )
