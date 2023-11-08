import ast
import sys
from _ast import FunctionDef
from _ast import Module
from copy import copy
from typing import Any
from typing import List
from typing import Mapping
from typing import Optional
from typing import Union

import ast_comments  # type: ignore
from typing_extensions import cast
from typing_extensions import Self


def parse(source: Union[str, bytes, ast.AST], filename: str = "<unknown>", mode: str = "exec") -> ast.AST:
    """
    Replace the ast.parse method with one which picks up comments.
    """
    return AstCommentV2.convert_tree(ast_comments.parse(source, filename, mode))


if sys.version_info >= (3, 9):

    def unparse(ast_obj: ast.AST) -> str:
        return cast(str, AstCommentV2.Unparser().visit(ast_obj))

else:

    def unparse(ast_obj: ast.AST) -> str:
        raise NotImplementedError("unparse() is not supported on Python < 3.9")


def ast_rename_function(tree: ast.Module, new_function_name: str) -> ast.Module:
    """
    Take a body which contains a function def (may also contain function decorators). Alter the function definition
    node to use a new name
    """
    # For now, I think we can just handle the case where tree is a Module with a single node which is a function def
    assert isinstance(tree, Module)
    assert len(tree.body) == 1
    old_func = tree.body[0]
    assert isinstance(old_func, FunctionDef)
    new_func = copy(old_func)
    new_func.name = new_function_name
    new_module = Module(body=[new_func], type_ignores=tree.type_ignores)

    return new_module


def copy_ast_line_info(node: ast.AST) -> Mapping[str, Any]:
    """Extract the line and position attributes from a node so they can initialize a new node"""
    return dict(
        lineno=node.lineno,
        col_offset=node.col_offset,
        end_lineno=node.end_lineno,
        end_col_offset=node.end_col_offset,
    )


class AstCommentV2(ast.Expr):
    """
    Current `ast_comments` library represents comments as instances of a special base node, Comment.
    This implementation messes us up because the resulting tree can not run through `compile()`.  We need
    these nodes rewritten to be instances of ast.Expr(value=ast.Constant()).

    So, this class provides that new presentation. After ast_comments does a parse, the transform should be run to
    convert things into AstCommentsV2.

    Take this out if/when ast_comments base implementation is changed (issue 23 in their GH repo).
    """

    value: "ast.Constant"
    inline: bool

    _fields = ("value", "inline")

    if sys.version_info >= (3, 9):

        class Unparser(ast_comments._Unparser):  # type: ignore
            def visit_AstCommentV2(self, node: ast.AST) -> ast.AST:
                return self.visit_Expr(node)  # type: ignore

    @property
    def comment(self) -> str:
        v = self.value.value
        assert isinstance(v, str)
        return v

    @classmethod
    def from_comment(cls, comment: ast_comments.Comment) -> "Self":
        const = ast.Constant(
            value=comment.value,
            **copy_ast_line_info(comment),
        )

        expr = cls(
            value=const,
            inline=comment.inline,
            **copy_ast_line_info(comment),
        )
        return expr

    @classmethod
    def convert_tree(cls, tree: ast.AST) -> ast.AST:
        """
        Given an output from ast.parse() or from ast_comments.parse(), create a new tree where all instances of
        ast_comments.Comment are replaced with instances of AstCommentsV2
        """

        class RewriteComments(ast.NodeTransformer):
            def visit_Comment(self, node: ast.AST) -> ast.AST:
                assert isinstance(node, ast_comments.Comment)
                return AstCommentV2.from_comment(node)

        return cast(ast.AST, RewriteComments().visit(tree))


class NodeMerger(ast.NodeTransformer):
    """
    A type of visitor which looks at any series of nodes (where there is a list of nodes and the list is len > 1)
    and allows the opportunity to combine consecutive nodes (ie where we find a sequence of nodes A,B,C...Z, call
    a method which can look at that and decide to merge B into, resulting in nodes: A,C...Z

    Note this is a Depth-First walk, meaning leaf nodes get merged before parent nodes get merged.
    """

    def merge_nodes(self, node_a: ast.AST, node_b: ast.AST) -> Optional[ast.AST]:
        """
        If nodes a and b should be merged, return a new, merged node.  Otherwise, return None which will result in
        both nodes remain in the node list.

        Override this in subclass transformers.
        """
        _ = node_a, node_b
        return None

    def generic_visit(self, node: ast.AST) -> Any:
        """Implementation adapted from generic_visit() on NodeTransformer"""
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                new_values: List[Any] = []
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.generic_visit(value)
                        if new_values:
                            merged_node = self.merge_nodes(new_values[-1], value)
                            if merged_node:
                                new_values[-1] = merged_node
                            else:
                                new_values.append(value)
                        else:
                            new_values.append(value)
                    else:
                        new_values.append(value)

                old_value[:] = new_values
            elif isinstance(old_value, ast.AST):
                self.visit(old_value)

        return node
