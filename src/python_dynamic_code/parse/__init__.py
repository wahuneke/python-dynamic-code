"""
In this subpackage, we focus on parsing the original source Python code into an AST which will contain a few
non-standard nodes in it.  Ultimately, the output from this will merely be a tree which formalizes our interpretation
of any PDC annotations that have been written into the source code.

Our 'understanding' of the annotations will be represented by occurrences of our custom node types and attributes
attached to those nodes.

During troubleshooting, this tree can be inspected using `ast.dump()` or written as code using `pdc_nodes.unparse()`.
When written as code, annotations will appear as string literals in the output and will reveal the internal
representation of how the original, annotated code was parsed.
"""

from .pdc_nodes import parse, unparse, PdcNodeBase
from .parser import PdcSection

__all__ = ["parse", "unparse", "PdcSection"]
