"""
In this module, the standard AST tech is extended to add:

    * the ability to identify "directives" that are embedded in comments
    * the ability to group statements together into blocks
    * ast_utils is used to bring in the AstCommentV2 node type for parsing comments from source code

"""
import ast
import sys
from typing import Any
from typing import Generic
from typing import List
from typing import Literal
from typing import Optional
from typing import overload
from typing import Protocol
from typing import runtime_checkable
from typing import Type
from typing import TypeVar
from typing import Union

from typing_extensions import Self

from python_dynamic_code.parse import ast_util


@runtime_checkable
class PdcDirectiveProtocol(Protocol):
    @classmethod
    def as_directive(cls, lineno: int, body: str) -> "Self":
        ...


# noinspection PyPropertyDefinition
@runtime_checkable
class PdcGroupControlDirective(Protocol):
    @property
    def section_name(self) -> str:
        ...

    @property
    def group_requires_end_tag(self) -> bool:
        ...

    @property
    def is_end_tag(self) -> bool:
        ...


@overload
def parse(
    source: Union[str, bytes, ast.AST],
    filename: str = "<unknown>",
    mode: Literal["exec"] = "exec",
    directive_parent_class: Optional[Type[PdcDirectiveProtocol]] = None,
) -> ast.Module:
    ...


def parse(
    source: Union[str, bytes, ast.AST],
    filename: str = "<unknown>",
    mode: str = "exec",
    directive_parent_class: Optional[Type[PdcDirectiveProtocol]] = None,
) -> ast.AST:
    """
    Wrap the ast_comments parser (which wraps standard ast.parse()) in order to produce a tree with all the stock ast
    node types **plus** the Pdc node types of AstCommentV2, PdcNode, and PdcGroup
    """
    return PdcNodeBase.convert_tree(
        ast_util.parse(source, filename, mode), directive_parent_class=directive_parent_class
    )


if sys.version_info >= (3, 9):

    def unparse(ast_obj: ast.Module) -> str:
        return PdcNodeBase.Unparser().visit(ast_obj)


_PdcDirectiveClassT = TypeVar("_PdcDirectiveClassT", bound=PdcDirectiveProtocol)


class PdcNodeBase(ast.AST, Generic[_PdcDirectiveClassT]):
    """
    All of our special PDC directives will start life out as AstCommentsV2 nodes (the node type used generically for
    any Python single line or inline comment, ie # ...)

    Subclasses of this class must:
      1) override the as_pdc_node() and as_merged() methods
    and
      2) implement a visitor method in this class's PdcNodeBase.Unparser _or_ define a brand new `unparse()` method
         which uses a new Unparser
    """

    @classmethod
    def try_parse_as(cls) -> List[Type["PdcNodeBase[_PdcDirectiveClassT]"]]:
        """When converting nodes into this type, try parsing as these subclasses in the given order"""
        return [PdcGroup, PdcNode[_PdcDirectiveClassT]]

    if sys.version_info >= (3, 9):

        class Unparser(ast_util.AstCommentV2.Unparser):
            def visit_PdcNode(self, node: ast.AST) -> None:
                self.visit_AstCommentV2(node)

            def visit_PdcGroup(self, node: ast.AST) -> None:
                assert isinstance(node, ast.If)
                self.visit_If(node)

    @classmethod
    def as_pdc_node(
        cls, node: ast.AST, directive_parent_class: Optional[Type[_PdcDirectiveClassT]] = None
    ) -> Optional[Self]:
        """
        If the given node appears to be a PDC directive comment, emit a PdcNode for it. Otherwise, emit None

        Subclasses must override this function
        """
        parsed = None
        for try_class in cls.try_parse_as():
            parsed = try_class.as_pdc_node(node, directive_parent_class)
            if parsed:
                break

        return parsed

    @classmethod
    def convert_tree(cls, tree: ast.AST, directive_parent_class: Optional[Type[_PdcDirectiveClassT]] = None) -> ast.AST:
        """
        Given an output from ast.parse() or from ast_comments.parse(), create a new tree where instances of
        AstCommentsV2 are replaced with instances of PdcNode. In some cases, multiple consecutive instances of Comment
        may be combined into one, if the item is found to be a multi-line directive
        """

        class FindDirectives(ast.NodeTransformer):
            def visit_AstCommentV2(self, node: ast.AST) -> ast.AST:
                assert isinstance(node, ast_util.AstCommentV2)
                pdc_node = cls.as_pdc_node(node, directive_parent_class)
                if pdc_node:
                    return pdc_node
                else:
                    return node

        # Do it in two separate passes, for simplicity
        tree_with_directives = FindDirectives().visit(tree)

        class MergePdcNodes(ast_util.NodeMerger):
            def merge_nodes(self, node_a: ast.AST, node_b: ast.AST) -> Optional[ast.AST]:
                if isinstance(node_a, cls):
                    merged = node_a.as_merged(node_b)
                    if merged:
                        return merged

        tree_with_merged_directives = MergePdcNodes().visit(tree_with_directives)

        return tree_with_merged_directives

    def as_merged(self, node_b: ast.AST) -> Optional["Self"]:
        """
        Given another node (presumably, located consecutively with this one) determine whether it should be merged with
        this node in the AST.  This facilitates handling of multi-line directives

        Return the 'new', merged node IF the two should be considered merged (ie node_b can be discarded in this case).
        """
        raise NotImplementedError("implement in sub classes")


class PdcNode(PdcNodeBase[_PdcDirectiveClassT], ast_util.AstCommentV2, Generic[_PdcDirectiveClassT]):
    """Generic pdc node"""

    directive: _PdcDirectiveClassT
    """The attached directive instance"""

    @classmethod
    def as_pdc_node(
        cls, node: ast.AST, directive_parent_class: Optional[Type[_PdcDirectiveClassT]] = None
    ) -> Optional[Self]:
        # Make an assertion on a not very important assumption. Review this if/when it fails
        assert node.lineno == node.end_lineno or node.end_lineno is None
        if directive_parent_class is None:
            from python_dynamic_code.parse.directives import PdcDirective

            directive_parent_class = PdcDirective

        # We can only convert from AstCommentsV2 nodes
        if isinstance(node, ast_util.AstCommentV2):
            as_directive = directive_parent_class.as_directive(node.lineno, node.comment)
            if as_directive:
                if node.inline:
                    # This is not supported right now.  No reason it can't be added.
                    raise ValueError(f"PDC annotations are not allowed in inline comments (line {node.lineno})")
                return cls(directive=as_directive, value=node.value, **ast_util.copy_ast_line_info(node))

    def as_merged(self, node_b: ast.AST) -> Optional["Self"]:
        """
        Given another node (presumably, located consecutively with this one) determine whether it should be merged with
        this node in the AST.  This facilitates handling of multi-line directives

        Return the 'new', merged node IF the two should be considered merged (ie node_b can be discarded in this case).
        """
        if isinstance(node_b, ast_util.AstCommentV2) and self.directive.incorporate_continuation_line(
            node_b.lineno, node_b.comment
        ):
            # The incorporation line above will have already copied in the content from node_b. So, node_b is (almost)
            # ready to be discarded
            self.value.value += "\n" + node_b.value.value
            setattr(self, "end_lineno", node_b.end_lineno)
            setattr(self, "end_col_offset", node_b.end_col_offset)
            return self


class PdcGroup(ast.If, PdcNodeBase[_PdcDirectiveClassT], Generic[_PdcDirectiveClassT]):
    """
    As a way to conceptualize a grouping of statements into a block we'll pretend that it's an if block with a
    test expression that is always true.

    ie, if we wanted to conceptually group a series of statements together from a block of Python, we could just
    wrap them under an `if True:` statement like this, eg:

    ```python
    statement_1()
    # start block
    b_1()
    b_2()
    # end block
    statement_4()
    ```

    Becomes ->

    ```python
    statement_1()
    if True:
        b_1()
        b_2()
    statement_4()
    ```

    which will be equivalent, but also indicates that some of those statements belong together in some way.
    """

    body: List[ast.AST]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # make some quick assumptions about how the init works here. Fix this later if problems arise

        if kwargs:
            assert not args
            test = kwargs.get("test", None)
            body = kwargs.get("body", [])
            or_else = kwargs.get("orelse", [])
        else:
            if len(args) == 1:
                body = args[0]
                test = or_else = None
            else:
                test, body, or_else = args

        if or_else or test:
            raise TypeError(f"{self.__class__} should be instantied with only a list of body statements")

        if not isinstance(body, list):
            body = list(body)

        test = ast.Constant(value=True)
        or_else = []

        super().__init__(test, body, or_else)

    @classmethod
    def as_pdc_node(
        cls, node: ast.AST, directive_parent_class: Optional[Type[_PdcDirectiveClassT]] = None
    ) -> Optional[Self]:
        # A PdcGroup node starts as a PdcNode and then looks at its directive and, if it is a group starter directive
        # then it promotes to a PdcGroup instance
        pdc_node = PdcNode.as_pdc_node(node, directive_parent_class)
        if pdc_node:
            if isinstance(pdc_node.directive, PdcGroupControlDirective):
                body = [pdc_node]
                return cls(body=body, **ast_util.copy_ast_line_info(node))

    @property
    def group_name(self) -> str:
        s = self.start_directive
        return s.section_name

    @property
    def start_directive(self) -> "PdcGroupControlDirective":
        group_start = self.body[0]
        assert isinstance(group_start, PdcNode)
        assert isinstance(group_start.directive, PdcGroupControlDirective)
        return group_start.directive

    def as_merged(self, node_b: ast.AST) -> Optional["Self"]:
        """
        For the PdcGroup node, we want to keep merging in siblings until we reach the natural end of our group.
        Depending on how the group was started this will be either: encountering the end of siblings list or
        encountering an EndDirective
        """
        group_start = self.body[0]
        most_recent_body = self.body[-1] if len(self.body) > 1 else None
        node_b_directive = node_b.directive if isinstance(node_b, PdcNode) else None

        # First, give most recent child a chance to absorb node_b
        if isinstance(most_recent_body, PdcNodeBase):
            # In this case, give our latest child a chance to absorb this node first. we only get a chance to add it
            # to our body attribute *if* the child does not absorb it.
            child_absorbed = most_recent_body.as_merged(node_b)
            if child_absorbed:
                # Just in case most_recent_body has changed by doing the merge, update that entry in our body array
                self.body[-1] = child_absorbed
                # In this case, we don't get to absorb it, our child did. So we don't add node_b to our body.
                # But we do want to continue receiving things to merge in. So return self.
                return self

        if self.start_directive.group_requires_end_tag:
            if isinstance(node_b_directive, PdcGroupControlDirective) and node_b_directive.is_end_tag:
                if node_b_directive.section_name != self.start_directive.section_name:
                    raise ValueError(
                        f"Section start (line {group_start.lineno}) must end with an EndSection directive with"
                        f"a matching section name ({self.start_directive.section_name})"
                    )
            elif (
                isinstance(most_recent_body, PdcNode)
                and isinstance(most_recent_body.directive, PdcGroupControlDirective)
                and most_recent_body.directive.is_end_tag
            ):
                # This indicates that we are on a line immediately *after* we've already found the enddirective for
                # our section.  This is the spot where we should **stop** absorbing siblings.  Return None
                return None

        # In all other cases, 'absorb' this node into the body of our section by adding it to body and returning self
        self.body.append(node_b)
        return self


class PdcOutputNode(ast.AST):
    """
    An output node in the tree is used to make the conversion code output something (as in a print '<code>' or a
    yield '<code>').  It is an intermediate step and should be run through the `PdcOutputNode.convert_tree()` method

    """

    def convert_tree(self, tree: ast.AST) -> ast.AST:
        """
        Strip output nodes from the tree replace them with code which will output the node's content
        """

        class RewriteOutputNodes(ast.NodeTransformer):
            def visit_PdcOutputNode(self, node: ast.AST) -> ast.AST:
                assert isinstance(node, PdcOutputNode)
                return node.to_output()
