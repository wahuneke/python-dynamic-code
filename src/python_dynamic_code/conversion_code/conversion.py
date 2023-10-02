"""
In this module, we figure out how to go from a PdcSection to a block of 'conversion code' which can be run in
combination with slow-changing input, to produce exec code.
"""
import ast

from python_dynamic_code.parse.parser import PdcSection
from python_dynamic_code.runner import PdcStream
from python_dynamic_code.conversion_code.writer import ConversionCodeWriter


def get_conversion_code_tree(stream: "PdcStream") -> ast.Module:
    """
    Given a PdcStream, generate the conversion code that can be run in combination with slow-changing input.

    e.g:

    The conversion code will:
    * Echo 'verbatim' sections from the stream
    * Make template replacements for dynamic sections from the stream
    * Drop lines or sections that are marked for removal
    """
    annotated_tree = stream.source_ast
    writer = ConversionCodeWriter(stream.name, stream.source_code, rule_group_class=PdcSection)
    conversion_tree = writer.visit(annotated_tree)
    assert isinstance(conversion_tree, ast.Module)
    return conversion_tree
