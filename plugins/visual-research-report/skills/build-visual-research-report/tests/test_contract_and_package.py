from __future__ import annotations

import copy
import json
import shutil
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

    def with_image2_theme_atom(self, report: dict) -> dict:
        atom = report["theme_atom"]
        part_ids = [part["id"] for part in atom["schematic"]["parts"]]
        anchor = "theme-atom-image2/identity-anchor.png"
        atom["production"] = {
            "mode": "image-2",
            "model": "gpt-image-2",
            "workflow": "canonical-anchor-plus-direct-edits",
            "anchor_asset": anchor,
            "prompt_version": "atom-cover-v1",
            "canvas": {"width": 1448, "height": 1086},
            "master_format": "png",
            "delivery_format": "webp",
            "print_view_id": "recursive",
            "fallback": "schematic-explicit-only",
        }
        atom["identity_lock"] = {
            "object_key": "chip-package-2-5d",
            "physical_class": "2.5D semiconductor package",
            "silhouette": "low rectangular package with one compute die and two memory stacks",
            "part_ids": part_ids,
            "topology": ["compute-to-interposer", "memory-to-interposer", "interposer-to-substrate"],
            "materials": ["silicon", "copper", "epoxy"],
            "fiducials": ["offset compute die", "paired memory stacks"],
        }
        atom["camera_lock"] = {
            "projection": "three-quarter orthographic",
            "yaw_deg": 32,
            "pitch_deg": 24,
            "roll_deg": 0,
            "focal_length_equiv_mm": 70,
            "object_center": [0.5, 0.5],
            "safe_margin": 0.12,
        }
        output_digests = {
            "recursive": "b" * 64,
            "exploded": "c" * 64,
            "blueprint": "d" * 64,
            "impact": "e" * 64,
        }
        for view in atom["views"]:
            view_id = view["id"]
            view["asset"] = f"theme-atom-image2/{view_id}.png"
            view["focal_point"] = [0.5, 0.5]
            view["generation"] = {
                "operation": "edit",
                "parent_asset": anchor,
                "prompt_id": f"atom-cover-v1/{view_id}",
                "invariants": ["identity_lock", "camera_lock"],
                "qa_status": "passed",
                "input_asset_sha256": "a" * 64,
                "output_asset_sha256": output_digests[view_id],
            }
        return report

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

    def test_editorial_dashboard_contract_is_valid(self) -> None:
        report = self.mutate()
        self.assertEqual("editorial-dashboard", report["presentation"]["preset"])
        self.assertTrue(all(section.get("nav_label") for section in report["sections"]))
        self.assertTrue(all(section.get("dashboard") for section in report["sections"]))
        errors, warnings = validate_report(report)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_editorial_dashboard_supports_deterministic_fallback(self) -> None:
        report = self.mutate()
        for section in report["sections"]:
            section.pop("dashboard", None)
            section.pop("nav_label", None)
        errors, warnings = validate_report(report)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_dashboard_rejects_bad_fact_shapes(self) -> None:
        mutations = {
            "unknown primary": lambda dashboard: dashboard.update(primary_fact_id="F999"),
            "duplicate metrics": lambda dashboard: dashboard.update(metric_fact_ids=["F06", "F06"]),
            "mixed trend units": lambda dashboard: dashboard.update(trend_fact_ids=["F01", "F03"]),
            "non-probability scenario": lambda dashboard: dashboard.update(scenario_fact_ids=["F01"]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                report = self.mutate()
                mutate(report["sections"][0]["dashboard"])
                self.assert_error_contains(report, "dashboard")

    def test_optional_theme_atom_schematic_is_valid(self) -> None:
        report = self.mutate()
        atom = report["theme_atom"]
        atom.pop("production", None)
        atom.pop("identity_lock", None)
        atom.pop("camera_lock", None)
        for view in atom["views"]:
            view.pop("asset", None)
            view.pop("focal_point", None)
            view.pop("generation", None)
        atom["schematic"] = {
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

    def test_image2_theme_atom_production_contract_is_valid(self) -> None:
        report = self.with_image2_theme_atom(self.mutate())
        errors, warnings = validate_report(report)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_explicit_provided_and_schematic_production_modes_are_valid(self) -> None:
        provided = self.mutate()
        provided_atom = provided["theme_atom"]
        provided_atom["production"] = {
            "mode": "provided",
            "canvas": {"width": 1448, "height": 1086},
            "print_view_id": "recursive",
        }
        for view in provided_atom["views"]:
            view["asset"] = f"provided/{view['id']}.png"
            view["focal_point"] = [0.5, 0.5]
            view.pop("generation", None)
        errors, warnings = validate_report(provided)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

        schematic = self.mutate()
        schematic["theme_atom"]["production"] = {"mode": "schematic"}
        for view in schematic["theme_atom"]["views"]:
            view.pop("asset", None)
            view.pop("focal_point", None)
            view.pop("generation", None)
        errors, warnings = validate_report(schematic)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_theme_atom_production_rejects_unsafe_asset_paths(self) -> None:
        mutations = {
            "remote view asset": (
                "remote, data, and absolute paths are forbidden",
                lambda report: report["theme_atom"]["views"][0].update(asset="https://example.com/recursive.webp"),
            ),
            "data URI view asset": (
                "remote, data, and absolute paths are forbidden",
                lambda report: report["theme_atom"]["views"][0].update(asset="data:image/webp;base64,AAAA"),
            ),
            "remote contact sheet": (
                "production.contact_sheet_asset must be a safe relative local image path",
                lambda report: report["theme_atom"]["production"].update(contact_sheet_asset="ftp://example.com/contact.png"),
            ),
            "absolute anchor asset": (
                "remote, data, and absolute paths are forbidden",
                lambda report: report["theme_atom"]["production"].update(anchor_asset="/tmp/anchor.png"),
            ),
            "parent traversal": (
                "must not contain '..' path traversal",
                lambda report: report["theme_atom"]["views"][0].update(asset="../recursive.webp"),
            ),
            "duplicate output asset": (
                "duplicates theme_atom.views[0].asset",
                lambda report: report["theme_atom"]["views"][1].update(asset="theme-atom-image2/recursive.png"),
            ),
            "missing output asset": (
                ".asset must be a non-empty safe relative local image path",
                lambda report: report["theme_atom"]["views"][0].pop("asset"),
            ),
        }
        for label, (fragment, mutate_report) in mutations.items():
            with self.subTest(label=label):
                report = self.with_image2_theme_atom(self.mutate())
                mutate_report(report)
                self.assert_error_contains(report, fragment)

    def test_image2_theme_atom_rejects_broken_generation_continuity(self) -> None:
        mutations = {
            "missing canonical view": (
                "theme_atom.views must contain exactly",
                lambda report: report["theme_atom"].update(views=report["theme_atom"]["views"][:-1]),
            ),
            "non-canonical view id": (
                "theme_atom.views must contain exactly",
                lambda report: report["theme_atom"]["views"][0].update(id="hero"),
            ),
            "unknown mode": (
                "production.mode must be one of",
                lambda report: report["theme_atom"]["production"].update(mode="imagegen"),
            ),
            "wrong model": (
                "production.model must be 'gpt-image-2'",
                lambda report: report["theme_atom"]["production"].update(model="gpt-image-1"),
            ),
            "wrong workflow": (
                "production.workflow must be 'canonical-anchor-plus-direct-edits'",
                lambda report: report["theme_atom"]["production"].update(workflow="four-independent-generations"),
            ),
            "wrong master format": (
                "production.master_format must be 'png'",
                lambda report: report["theme_atom"]["production"].update(master_format="jpeg"),
            ),
            "wrong delivery format": (
                "production.delivery_format must be 'webp'",
                lambda report: report["theme_atom"]["production"].update(delivery_format="png"),
            ),
            "invalid canvas": (
                "production.canvas.width must be a positive integer",
                lambda report: report["theme_atom"]["production"]["canvas"].update(width=0),
            ),
            "invalid print view": (
                "production.print_view_id must be one of",
                lambda report: report["theme_atom"]["production"].update(print_view_id="hero"),
            ),
            "invalid fallback": (
                "production.fallback must be 'schematic-explicit-only'",
                lambda report: report["theme_atom"]["production"].update(fallback="generic-art"),
            ),
            "invalid focal point": (
                ".focal_point must contain exactly two finite numbers between 0 and 1",
                lambda report: report["theme_atom"]["views"][0].update(focal_point=[0.5, 1.1]),
            ),
            "wrong master extension": (
                ".asset extension must match theme_atom.production.master_format 'png'",
                lambda report: report["theme_atom"]["views"][0].update(asset="theme-atom-image2/recursive.webp"),
            ),
            "missing generation": (
                ".generation must be an object for image-2 production",
                lambda report: report["theme_atom"]["views"][0].pop("generation"),
            ),
            "non-edit operation": (
                ".generation.operation must be 'edit'",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(operation="generate"),
            ),
            "different parent": (
                ".generation.parent_asset must equal theme_atom.production.anchor_asset",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(parent_asset="theme-atom-image2/other.png"),
            ),
            "prompt discontinuity": (
                ".generation.prompt_id must be 'atom-cover-v1/recursive'",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(prompt_id="other/recursive"),
            ),
            "missing invariant": (
                ".generation.invariants must contain exactly",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(invariants=["identity_lock"]),
            ),
            "qa not passed": (
                ".generation.qa_status must be 'passed'",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(qa_status="pending"),
            ),
            "invalid input digest": (
                ".generation.input_asset_sha256 must be a lowercase 64-character SHA-256",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(input_asset_sha256="ABC"),
            ),
            "different input anchor digest": (
                "input_asset_sha256 values must all identify the same canonical anchor",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(input_asset_sha256="f" * 64),
            ),
            "duplicate output digest": (
                ".generation.output_asset_sha256 duplicates",
                lambda report: report["theme_atom"]["views"][1]["generation"].update(output_asset_sha256="b" * 64),
            ),
            "unchanged output digest": (
                ".generation.output_asset_sha256 must differ from its anchor input digest",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(output_asset_sha256="a" * 64),
            ),
            "inconsistent generation canvas": (
                ".generation.canvas must match theme_atom.production.canvas",
                lambda report: report["theme_atom"]["views"][0]["generation"].update(canvas={"width": 1024, "height": 1024}),
            ),
        }
        for label, (fragment, mutate_report) in mutations.items():
            with self.subTest(label=label):
                report = self.with_image2_theme_atom(self.mutate())
                mutate_report(report)
                self.assert_error_contains(report, fragment)

    def test_image2_theme_atom_rejects_broken_identity_and_camera_locks(self) -> None:
        mutations = {
            "identity lock missing": (
                "theme_atom.identity_lock must be an object",
                lambda report: report["theme_atom"].pop("identity_lock"),
            ),
            "unknown canonical part": (
                "part_ids references unknown schematic parts",
                lambda report: report["theme_atom"]["identity_lock"]["part_ids"].append("invented-part"),
            ),
            "canonical part omitted": (
                "part_ids must include every canonical schematic part",
                lambda report: report["theme_atom"]["identity_lock"].update(
                    part_ids=report["theme_atom"]["identity_lock"]["part_ids"][:-1]
                ),
            ),
            "insufficient fiducials": (
                "identity_lock.fiducials must contain at least 2 non-empty strings",
                lambda report: report["theme_atom"]["identity_lock"].update(fiducials=["one marker"]),
            ),
            "camera lock missing": (
                "theme_atom.camera_lock must be an object",
                lambda report: report["theme_atom"].pop("camera_lock"),
            ),
            "invalid object center": (
                "camera_lock.object_center must contain exactly two finite numbers between 0 and 1",
                lambda report: report["theme_atom"]["camera_lock"].update(object_center=[-0.1, 0.5]),
            ),
            "invalid safe margin": (
                "camera_lock.safe_margin must be a finite number between 0 and 0.4",
                lambda report: report["theme_atom"]["camera_lock"].update(safe_margin=0.5),
            ),
        }
        for label, (fragment, mutate_report) in mutations.items():
            with self.subTest(label=label):
                report = self.with_image2_theme_atom(self.mutate())
                mutate_report(report)
                self.assert_error_contains(report, fragment)

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
            shutil.copytree(SKILL_DIR / "assets" / "theme-atom-image2", root / "theme-atom-image2")
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
            shutil.copytree(SKILL_DIR / "assets" / "theme-atom-image2", root / "theme-atom-image2")
            report_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            fake_browser.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake_browser.chmod(0o755)
            build(report_path, output)
            result = export_pdf(output, fake_browser, optional=True)
            self.assertEqual("skipped", result["status"])
            self.assertEqual("browser-environment-unavailable", result["reason"])


if __name__ == "__main__":
    unittest.main()
