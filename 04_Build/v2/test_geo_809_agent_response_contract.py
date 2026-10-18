"""Regression contract for #809 GEO browser-agent fast HTTP responses.

Run:
    python 04_Build/v2/test_geo_809_agent_response_contract.py
This regression verifies the extension transport response is not coupled to
the heavy owner dashboard, while legacy GEO POST endpoints retain it.
It does not replace live Windows/browser acceptance.
"""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source" / "backend" / "r8_19_geo_validation_patch.py"


class AgentResponseContractTest(unittest.TestCase):
    def test_agent_response_has_no_synchronous_dashboard(self):
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(SOURCE))
        matches = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            check = ast.get_source_segment(source, node.test) or ""
            if 'path.startswith("/api/r8-27/geo-browser-agent/")' in check:
                matches.append(node)
        self.assertTrue(matches, "Browser-agent transport response branch missing")
        response_branch = matches[-1]
        then_code = "\n".join(ast.get_source_segment(source, n) or "" for n in response_branch.body)
        else_code = "\n".join(ast.get_source_segment(source, n) or "" for n in response_branch.orelse)
        self.assertIn('handler._json_ok({"result": result})', then_code)
        self.assertNotIn("_dashboard_with_executor(", then_code)
        self.assertIn('_dashboard_with_executor()', else_code)
        self.assertIn('"geo"', else_code)


if __name__ == "__main__":
    unittest.main()
