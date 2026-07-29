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

    def history_chart(self) -> dict:
        return {
            "id": "C90",
            "type": "history-scrolly",
            "title": "The system changes across three regimes",
            "subtitle": "Synthetic index points on an actual scale",
            "source_ids": ["S01"],
            "data": {
                "scale": {"mode": "actual", "domain": [0, 100], "ticks": [0, 25, 50, 75, 100]},
                "series": [
                    {
                        "name": "Demand",
                        "color": "#2457ff",
                        "points": [
                            {"label": "2023", "value": 40, "fact_id": "F23"},
                            {"label": "2024", "value": 55, "fact_id": "F24"},
                            {"label": "2025", "value": 78, "fact_id": "F25"},
                            {"label": "2026E", "value": 96, "fact_id": "F26"},
                        ],
                    },
                    {
                        "name": "Supply",
                        "color": "#d8475f",
                        "points": [
                            {"label": "2023", "value": 43, "fact_id": "F27"},
                            {"label": "2024", "value": 48, "fact_id": "F28"},
                            {"label": "2025", "value": 63, "fact_id": "F29"},
                            {"label": "2026E", "value": 82, "fact_id": "F30"},
                        ],
                    },
                ],
                "scenes": [
                    {
                        "id": "baseline",
                        "title": "Baseline",
                        "body": "Demand and supply begin close together.",
                        "start_label": "2023",
                        "end_label": "2024",
                        "annotation_fact_ids": ["F23", "F27"],
                    },
                    {
                        "id": "divergence",
                        "title": "Divergence",
                        "start_label": "2024",
                        "end_label": "2026E",
                        "annotation_fact_ids": ["F26", "F30"],
                    },
                ],
            },
        }

    def causal_horizon_chart(self) -> dict:
        return {
            "id": "C91",
            "type": "causal-horizon-map",
            "title": "Signals propagate across decision horizons",
            "subtitle": "Synthetic signals and lags",
            "source_ids": ["S01", "S02"],
            "data": {
                "horizons": [
                    {"id": "now", "label": "Now"},
                    {"id": "next", "label": "Next 12 months"},
                ],
                "nodes": [
                    {
                        "id": "demand",
                        "label": "Demand signal",
                        "horizon_id": "now",
                        "direction": "up",
                        "confidence": "high",
                        "signal_fact_id": "F25",
                        "sparkline": {
                            "scale": {"mode": "actual", "domain": [0, 100], "ticks": [0, 50, 100]},
                            "points": [
                                {"label": "2023", "value": 40, "fact_id": "F23"},
                                {"label": "2024", "value": 55, "fact_id": "F24"},
                                {"label": "2025", "value": 78, "fact_id": "F25"},
                            ],
                        },
                    },
                    {
                        "id": "capacity",
                        "label": "Capacity response",
                        "horizon_id": "next",
                        "direction": "mixed",
                        "confidence": "medium",
                        "signal_fact_id": "F38",
                        "lag_fact_id": "F31",
                        "threshold_fact_id": "F43",
                        "sparkline": {
                            "scale": {"mode": "actual", "domain": [0, 100], "ticks": [0, 50, 100]},
                            "points": [
                                {"label": "2023", "value": 31, "fact_id": "F35"},
                                {"label": "2024", "value": 45, "fact_id": "F36"},
                                {"label": "2025", "value": 59, "fact_id": "F37"},
                                {"label": "2026E", "value": 76, "fact_id": "F38"},
                            ],
                        },
                    },
                ],
                "edges": [{"from": "demand", "to": "capacity", "label": "qualification lag"}],
            },
        }

    def test_v2_example_is_strictly_valid(self) -> None:
        errors, warnings = validate_report(self.example)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_unknown_presentation_preset_fails(self) -> None:
        report = self.mutate()
        report["presentation"]["preset"] = "dark-dashboard"
        self.assert_error_contains(report, "presentation.preset")

    def test_scrollspy_and_new_chart_contracts_are_valid(self) -> None:
        report = self.mutate()
        report["presentation"]["preset"] = "editorial-scrollspy"
        chart_types = {
            chart["type"]
            for section in report["sections"]
            for chart in section.get("charts", [])
        }
        self.assertTrue({"history-scrolly", "causal-horizon-map"}.issubset(chart_types))
        errors, warnings = validate_report(report)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_optional_theme_atom_schematic_is_valid(self) -> None:
        report = self.mutate()
        report["theme_atom"]["schematic"] = {
            "view_box": [1200, 800],
            "parts": [
                {"id": "substrate", "label": "Substrate", "shape": "rect", "x": 10, "y": 55, "width": 80, "height": 20, "role": "shell"},
                {"id": "die", "label": "Compute die", "shape": "rect", "x": 25, "y": 25, "width": 35, "height": 25, "role": "core"},
                {"id": "via", "label": "Interface via", "shape": "circle", "x": 67, "y": 45, "width": 4, "role": "interface"},
            ],
            "connections": [
                {"from": "substrate", "to": "die"},
                {"from": "die", "to": "via"},
            ],
        }
        errors, warnings = validate_report(report)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_theme_atom_schematic_rejects_invalid_contracts(self) -> None:
        def schematic() -> dict:
            return {
                "view_box": [1200, 800],
                "parts": [
                    {"id": "shell", "label": "Shell", "shape": "rect", "x": 10, "y": 10, "width": 80, "height": 80},
                    {"id": "core", "label": "Core", "shape": "circle", "x": 50, "y": 50, "width": 15, "role": "core"},
                ],
                "connections": [{"from": "shell", "to": "core"}],
            }

        mutations = {
            "invalid view box": ("view_box must contain", lambda value: value.update(view_box=[1200, 0])),
            "too few parts": ("between 2 and 12 parts", lambda value: value.update(parts=value["parts"][:1])),
            "duplicate part": ("duplicates part", lambda value: value["parts"][1].update(id="shell")),
            "invalid shape": ("shape must be", lambda value: value["parts"][0].update(shape="polygon")),
            "out of range coordinate": ("between 0 and 100", lambda value: value["parts"][0].update(x=101)),
            "missing rectangle height": ("parts[0].height", lambda value: value["parts"][0].pop("height")),
            "invalid role": ("role must be", lambda value: value["parts"][1].update(role="decoration")),
            "unknown connection": ("must connect declared parts", lambda value: value["connections"][0].update(to="missing")),
            "self connection": ("cannot connect a part to itself", lambda value: value["connections"][0].update(to="shell")),
        }
        for label, (fragment, mutate_schematic) in mutations.items():
            with self.subTest(label=label):
                report = self.mutate()
                report["theme_atom"]["schematic"] = schematic()
                mutate_schematic(report["theme_atom"]["schematic"])
                self.assert_error_contains(report, fragment)

    def test_history_scrolly_rejects_invalid_contracts(self) -> None:
        mutations = {
            "point fact drift": ("does not match F23.value", lambda chart: chart["data"]["series"][0]["points"][0].update(value=41)),
            "duplicate series name": ("duplicates series", lambda chart: chart["data"]["series"][1].update(name="Demand")),
            "duplicate series color": ("duplicates another series color", lambda chart: chart["data"]["series"][1].update(color="#2457ff")),
            "non-actual scale": ("scale.mode", lambda chart: chart["data"]["scale"].update(mode="normalized")),
            "too few scenes": ("at least two scenes", lambda chart: chart["data"].update(scenes=chart["data"]["scenes"][:1])),
            "duplicate scene id": ("duplicates scene", lambda chart: chart["data"]["scenes"][1].update(id="baseline")),
            "missing boundary": ("start_label must exist", lambda chart: chart["data"]["scenes"][0].update(start_label="2022")),
            "reversed boundary": ("start_label must precede", lambda chart: chart["data"]["scenes"][0].update(start_label="2025", end_label="2024")),
            "unknown annotation fact": ("references unknown id", lambda chart: chart["data"]["scenes"][0].update(annotation_fact_ids=["F999"])),
        }
        for label, (fragment, mutate_chart) in mutations.items():
            with self.subTest(label=label):
                report = self.mutate()
                chart = self.history_chart()
                mutate_chart(chart)
                report["sections"][0]["charts"].append(chart)
                self.assert_error_contains(report, fragment)

    def test_causal_horizon_map_rejects_invalid_contracts(self) -> None:
        mutations = {
            "too few horizons": ("at least two horizons", lambda chart: chart["data"].update(horizons=chart["data"]["horizons"][:1])),
            "duplicate horizon": ("duplicates horizon", lambda chart: chart["data"]["horizons"][1].update(id="now")),
            "duplicate node": ("duplicates node", lambda chart: chart["data"]["nodes"][1].update(id="demand")),
            "unknown horizon": ("horizon_id must reference", lambda chart: chart["data"]["nodes"][0].update(horizon_id="later")),
            "invalid direction": ("direction must be", lambda chart: chart["data"]["nodes"][0].update(direction="flat")),
            "invalid confidence": ("confidence must be", lambda chart: chart["data"]["nodes"][0].update(confidence="certain")),
            "unknown signal fact": ("signal_fact_id must reference", lambda chart: chart["data"]["nodes"][0].update(signal_fact_id="F999")),
            "unknown optional fact": ("lag_fact_id must reference", lambda chart: chart["data"]["nodes"][1].update(lag_fact_id="F999")),
            "sparkline fact drift": ("does not match F23.value", lambda chart: chart["data"]["nodes"][0]["sparkline"]["points"][0].update(value=41)),
            "non-actual sparkline scale": ("sparkline.scale.mode", lambda chart: chart["data"]["nodes"][0]["sparkline"]["scale"].update(mode="normalized")),
            "unknown edge node": ("must connect declared nodes", lambda chart: chart["data"]["edges"][0].update(to="missing")),
            "self edge": ("cannot connect a node to itself", lambda chart: chart["data"]["edges"][0].update(to="demand")),
        }
        for label, (fragment, mutate_chart) in mutations.items():
            with self.subTest(label=label):
                report = self.mutate()
                chart = self.causal_horizon_chart()
                mutate_chart(chart)
                report["sections"][0]["charts"].append(chart)
                self.assert_error_contains(report, fragment)

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
        balance = next(
            chart
            for section in report["sections"]
            for chart in section.get("charts", [])
            if chart.get("type") == "tension-balance"
        )
        del balance["data"]["tripwires"][0]["fact_id"]
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
