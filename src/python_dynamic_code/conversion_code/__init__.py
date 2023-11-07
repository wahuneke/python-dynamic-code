"""
Conversion code is a bit tricky to understand because it consists of two parallel streams of code.  When considered
as an AST, there will be two categories of nodes all mixed together in the tree:

1. The original code stream, which will often be precisely the original code from the decorated function but with
   a few sections eliminated, as appropriate

2. A new set of nodes mixed in with these whose only purpose is to generate new Python code (the code created by these
   will be 'exec code').  These nodes will initially reference nodes and trees that are copies of excerpts from the
   original tree.

In order to make this tree compile and execute again, multiple passes may be required in order to resolve the refer
to original code into brand new, concrete nodes which yield exec code.

The final output of this subpackage will be an AST containing 'conversion code' meaningful Python statements (prints /
yields) and it will be ready to be compiled into runnable conversion code.
"""
from .conversion import get_conversion_code_tree  # noreorder

__all__ = ["get_conversion_code_tree"]
