"""
In these tests, we run transformations on the test project(s) and check the resulting
code text output.
"""

from _pytest.pytester import RunResult


class TestPluggy:
    def test_codegen(self, pytester):
        example_dir = pytester.copy_example('mini-pluggy')
        results = pytester.runpytest(example_dir)
        assert isinstance(results, RunResult)
        results.assert_outcomes(passed=1)
