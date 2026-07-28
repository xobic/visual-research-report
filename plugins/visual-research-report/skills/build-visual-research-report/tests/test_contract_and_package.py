from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_report import _replace_exactly_once, build  # noqa: E402
from export_pdf import export_pdf  # noqa: E402
from finalize_package import finalize  # noqa: E402
from qa_report import run_qa  # noqa: E402
from validate_report import load_report, validate_report  # noqa: E402


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.example_path = SKILL_DIR / "assets" / "report.example.json"
        cls.example = load_report(cls.example_path)

    def mutate(self) -> dict:
        return copy.deepcopy(self.example)

    def assert_error_contains(self, report: dict, fragment: str) -> None:
        errors, _ = validate_report(report)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_v2_example_is_strictly_valid(self) -> None:
        errors, warnings = validate_report(self.example)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_unknown_presentation_preset_fails(self) -> None:
        report = self.mutate()
        report["presentation"]["preset"] = "dark-dashboard"
        self.assert_error_contains(report, "presentation.preset")

    def test_chart_value_must_match_fact(self) -> None:
        report = self.mutate()
        matrix = report["sections"][1]["charts"][0]
        matrix["data"]["rows"][0]["values"][0]["value"] = 7
        self.assert_error_contains(report, "does not match F11.value")

    def test_synthetic_report_requires_structured_disclosure(self) -> None:
        report = self.mutate()
        del report["data_disclosure"]
        self.assert_error_contains(report, "data_disclosure is required")

    def test_fact_cited_source_requires_typed_locator(self) -> None:
        report = self.mutate()
        del report["sources"][0]["locator"]
        self.assert_error_contains(report, "locator is required")

    def test_matrix_and_line_require_actual_scales(self) -> None:
        report = self.mutate()
        del report["sections"][1]["charts"][0]["data"]["scale"]
        self.assert_error_contains(report, "scale is required")

    def test_tripwire_requires_fact(self) -> None:
        report = self.mutate()
        del report["sections"][2]["charts"][2]["data"]["tripwires"][0]["fact_id"]
        self.assert_error_contains(report, "tripwires[0].fact_id")

    def test_multiplier_display_is_canonical(self) -> None:
        report = self.mutate()
        next(fact for fact in report["facts"] if fact["id"] == "F44")["display"] = "1.5×"
        self.assert_error_contains(report, "canonical multiplier")

    def test_template_replacement_must_be_exact(self) -> None:
        self.assertEqual("aYc", _replace_exactly_once("abc", "b", "Y", "fixture"))
        with self.assertRaises(ValueError):
            _replace_exactly_once("abc", "z", "Y", "fixture")


class PackageTests(unittest.TestCase):
    def test_build_qa_and_finalize(self) -> None:
        source = load_report(SKILL_DIR / "assets" / "report.example.json")
        source.setdefault("ui_labels", {})["contract_summary"] = "$& $' $` </script> {facts}/{sources}/{date}"
        with tempfile.TemporaryDirectory(prefix="vrr-test-") as temporary:
            root = Path(temporary)
            report_path = root / "fixture.json"
            output = root / "output"
            report_path.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
            build(report_path, output)
            errors, _ = run_qa(output)
            self.assertEqual([], errors)
            manifest = finalize(output)
            self.assertEqual("finalized", manifest["state"])
            errors, _ = run_qa(output, require_final=True)
            self.assertEqual([], errors)
            single = (output / "report.html").read_text(encoding="utf-8")
            self.assertNotIn('<script src="', single)
            self.assertNotIn('<link rel="stylesheet"', single)
            self.assertTrue((output / "report.json").is_file())

    def test_optional_pdf_environment_failure_is_skipped(self) -> None:
        source = load_report(SKILL_DIR / "assets" / "report.example.json")
        with tempfile.TemporaryDirectory(prefix="vrr-pdf-test-") as temporary:
            root = Path(temporary)
            report_path = root / "fixture.json"
            output = root / "output"
            fake_browser = root / "not-a-browser"
            report_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            fake_browser.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake_browser.chmod(0o755)
            build(report_path, output)
            result = export_pdf(output, fake_browser, optional=True)
            self.assertEqual("skipped", result["status"])
            self.assertEqual("browser-environment-unavailable", result["reason"])


if __name__ == "__main__":
    unittest.main()
