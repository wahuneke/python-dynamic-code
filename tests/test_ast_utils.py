import _ast
import ast
from textwrap import dedent
from typing import Optional

from python_dynamic_code.parse import ast_util
from python_dynamic_code.parse.ast_util import AstCommentV2
from python_dynamic_code.parse.ast_util import NodeMerger


def test_node_merger() -> None:
    """Simple test of our ast visitor, NodeMerger"""

    class AlwaysMerge(NodeMerger):
        """This test merger will always cut child nodes down to just one. It will cause all nodes but first to drop"""

        def merge_nodes(self, node_a: _ast.AST, node_b: _ast.AST) -> Optional[_ast.AST]:
            return node_a

    source = dedent(
        """
        if True:
          im_nested()
          x = 1 + 2
          # Try a wide range of node types
          global abc_global_var
          for i in [1,2,3]:
            if hey := 123:
              yo.attribute += 3
              break
            elif dict()[3]:
              continue
          f = "a" + "b" + str(3)
          l = f"abc {i}"
          match l:
            case "hi":
              g = not h
            case _:
              g = h / y
          while True:
            break
          with cm:
            pass
          with cm as m:
            m *= 5
          def innergen(*args, **kwargs) -> rtype:
            yield kwargs
            yield from args
          try:
            wont_work()
          except Ooops:
            pass
          except Woops as e:
            pass
          @deco
          class Werd(OtherClass):
            pass

        y = 3 + 4
        another_statement()
        """
    )
    tree = ast.parse(source)
    tree = AlwaysMerge().visit(tree)
    assert len(tree.body) == 1


def test_find_ast_commentsv2() -> None:
    """Do a simple parse and compile to demonstrate that comments v2 is working"""
    source = dedent(
        """
        im_python()
        x = 1 + 2
        # I'm a comment
        # I'm also a comment
        assert x > 1
        """
    )
    tree = ast_util.parse(source)

    body_2 = tree.body[2]
    assert isinstance(body_2, AstCommentV2) and body_2.comment == "# I'm a comment"
    assert isinstance(tree.body[3], AstCommentV2)
    assert not isinstance(tree.body[4], AstCommentV2)
    # Ensure that the resulting tree can compile
    _ = compile(tree, "", "exec")
