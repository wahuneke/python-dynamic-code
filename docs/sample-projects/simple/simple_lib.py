from dataclasses import dataclass
from typing import Callable
from typing import List
from typing import Mapping
from typing import Sequence

from pdc_optimizers import SimpleUnroll


@dataclass(frozen=True)
class PluginType:
    call_func: callable
    arg_names: Sequence[str]


@SimpleUnroll.pdc_attach()
def simple_unroll_fast_path(*call_funcs: Callable[[], int]) -> Sequence[int]:
    """In this toy example, PDC unrolls a loop"""
    # PDC-VerbatimLine
    results: List[int] = []

    for _i, f in enumerate(call_funcs):
        # PDC-Start Section 1
        # PDC-TemplateCode
        # PDC-Replace f()
        results.append(f())
        # PDC-End Section 1

    # PDC-VerbatimLine
    return results


def compound_fast_path(
    changes_every_call: Mapping,
    changes_less_often: Mapping[str, PluginType],
) -> list:
    """
    We want to use PDC to make this fast path function more efficient. It is called repeatedly, but one of the function
    inputs will remain static. Computed values from this should be factored out dynamically.
    """
    # PDC-Function
    #   GenDrop: changes_every_call
    # PDC-Start Section 1
    # PDC-Verbatim
    results = []
    # PDC-End Section 1
    for k, v in changes_less_often.items():
        # PDC-Start Section 2
        # PDC-TemplateCode
        # PDC-Eval GetValues ["changes_every_call[{n}]" for n in v.arg_names]
        # PDC-Eval ArgList ", ".join(GetValues)
        # PDC-Replace ArgList *args
        # PDC-Unroll v

        # PDC-KillLine
        args = [changes_every_call[n] for n in v.arg_names]

        results.append(v.call_func(*args))
        # PDC-End Section 2

    return results
