from typing import Mapping

from python_dynamic_code import DynamicCodeBuilder


class SimpleUnroll(DynamicCodeBuilder):
    def compute_template(self, section_name: str, replace_str: str, local_values: Mapping) -> str:
        if section_name == "Section 1" and replace_str == "f()":
            return f"call_funcs[{local_values['_i']}]"
        else:
            raise ValueError("Unknown section, replace_str: " + repr((section_name, replace_str)))
