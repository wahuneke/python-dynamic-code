"""
Require that all tests should pass in all the sample projects (docs/sample_projects).

* Refer to the `pytester_example_dir` setting in pyproject.toml
"""
import pytest


@pytest.mark.parametrize(
    ("project", "expect_results"),
    [
        ("mini-pluggy", {"passed": 1}),
        ("simple", {"passed": 1}),
    ],
)
@pytest.mark.xfail(reason="Not yet implemented")
def test_sample_project(pytester, project, expect_results) -> None:
    example_dir = pytester.copy_example(project)
    results = pytester.runpytest(example_dir)
    results.assert_outcomes(**expect_results)
