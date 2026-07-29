#!/usr/bin/env python3
"""Run deterministic offline-package QA for a built Visual Research Report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path


REQUIRED = (
    "site/index.html", "site/styles.css", "site/app.js", "site/data/report-data.js",
    "report.html", "report.json", "build-manifest.json",
)
REQUIRED_APP_TOKENS = (
    "report.ui_labels", "app.inert", "data-stack-share", "data-scroll-latest",
    'role=\"tab\"', "ArrowRight", "drawerFocusable", "data-contained-overflow",
    "tension-balance", "history-scrolly", "causal-horizon-map", "data-history-mode",
    "data-node-id", "atom-engineering-svg", "() => String(value)",
)


class InlineCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[tuple[dict[str, str | None], str]] = []
        self.styles: list[str] = []
        self.images: list[str] = []
        self.resources: list[tuple[str, str]] = []
        self._script_attrs: dict[str, str | None] | None = None
        self._script_parts: list[str] = []
        self._style_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script":
            self._script_attrs = values
            self._script_parts = []
        elif tag == "style":
            self._style_parts = []
        if tag == "img" and values.get("src"):
            self.images.append(str(values["src"]))
        if tag in {"script", "img", "source", "video", "audio"} and values.get("src"):
            self.resources.append((tag, str(values["src"])))
        if tag == "link" and values.get("href") and str(values.get("rel", "")).lower() in {"stylesheet", "preload", "modulepreload"}:
            self.resources.append((tag, str(values["href"])))

    def handle_data(self, data: str) -> None:
        if self._script_attrs is not None:
            self._script_parts.append(data)
        if self._style_parts is not None:
            self._style_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script_attrs is not None:
            self.scripts.append((self._script_attrs, "".join(self._script_parts)))
            self._script_attrs = None
            self._script_parts = []
        elif tag == "style" and self._style_parts is not None:
            self.styles.append("".join(self._style_parts))
            self._style_parts = None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_remote_runtime(value: str) -> bool:
    return bool(re.match(r"^(?:https?:)?//", value.strip(), flags=re.I))


def _parse_built_data(path: Path) -> dict[str, object]:
    data_text = path.read_text(encoding="utf-8")
    if not data_text.startswith("window.REPORT_DATA=") or not data_text.rstrip().endswith(";"):
        raise ValueError("site/data/report-data.js has an invalid wrapper")
    return json.loads(data_text[len("window.REPORT_DATA="):].rstrip().removesuffix(";"))


def _check_node_script(node: str, content: str, label: str, errors: list[str]) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        result = subprocess.run([node, "--check", str(temporary)], capture_output=True, text=True, check=False)
    finally:
        temporary.unlink(missing_ok=True)
    if result.returncode:
        errors.append(f"JavaScript syntax check failed for {label}: {result.stderr.strip()}")


def run_qa(output: Path, require_final: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    for relative in REQUIRED:
        if not (output / relative).is_file():
            errors.append(f"missing required file: {relative}")
    if errors:
        return errors, notes

    index = (output / "site/index.html").read_text(encoding="utf-8")
    single = (output / "report.html").read_text(encoding="utf-8")
    css = (output / "site/styles.css").read_text(encoding="utf-8")
    app = output / "site/app.js"
    app_text = app.read_text(encoding="utf-8")
    single_parser = InlineCollector()
    single_parser.feed(single)
    index_parser = InlineCollector()
    index_parser.feed(index)

    for name, parser in (("site/index.html", index_parser), ("report.html", single_parser)):
        remote = [(tag, value) for tag, value in parser.resources if _is_remote_runtime(value)]
        if remote:
            errors.append(f"{name} contains remote runtime resources: {remote[:3]}")
    if any(attrs.get("src") for attrs, _ in single_parser.scripts):
        errors.append("report.html contains an external script source")
    if any(tag == "link" for tag, _ in single_parser.resources):
        errors.append("report.html contains an external stylesheet/preload link")
    local_images = [src for src in single_parser.images if not src.startswith(("data:", "blob:"))]
    if local_images:
        errors.append(f"report.html contains non-embedded images: {local_images[:3]}")
    if "window.REPORT_DATA=" not in single:
        errors.append("report.html does not embed report data")
    if "evidence-drawer" not in single or "cover-switcher" not in single:
        errors.append("report.html is missing core interactive components")
    for token in REQUIRED_APP_TOKENS:
        if token not in app_text:
            errors.append(f"site/app.js is missing required behavior token: {token}")

    css_runtime = re.findall(r"(?:@import\s+|url\(\s*)[\"']?(?:https?:)?//", css, flags=re.I)
    inline_css_runtime = [match for style in single_parser.styles for match in re.findall(r"(?:@import\s+|url\(\s*)[\"']?(?:https?:)?//", style, flags=re.I)]
    if css_runtime or inline_css_runtime:
        errors.append("package CSS contains a remote runtime dependency")
    if re.search(r"(?:import\s*\(|fetch\s*\(|new\s+Worker\s*\()[\s\n]*[\"'](?:https?:)?//", app_text, flags=re.I):
        errors.append("site/app.js imports or fetches a remote runtime dependency")

    try:
        report = _parse_built_data(output / "site/data/report-data.js")
        view_ids = {view.get("id") for view in report.get("theme_atom", {}).get("views", []) if isinstance(view, dict)}
        if view_ids != {"recursive", "exploded", "blueprint", "impact"}:
            errors.append("built report does not contain the four required cover views")
        if report.get("evidence_status") in {"mixed", "synthetic"} and "data-disclosure" not in single:
            errors.append("synthetic or mixed report is missing the top data disclosure")
    except (json.JSONDecodeError, ValueError, AttributeError) as exc:
        errors.append(f"built report data is invalid: {exc}")

    report_json = json.loads((output / "report.json").read_text(encoding="utf-8"))
    provided_views = [
        view for view in report_json.get("theme_atom", {}).get("views", [])
        if isinstance(view, dict) and view.get("asset")
    ]
    if provided_views:
        embedded_data = next((content for attrs, content in single_parser.scripts if "window.REPORT_DATA=" in content), "")
        for view in provided_views:
            if f'\"id\":\"{view["id"]}\"' not in embedded_data or "data:image/" not in embedded_data:
                errors.append(f"single-file cover asset was not embedded for view {view['id']}")

    manifest_path = output / "build-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "visual-research-report/build-manifest@2":
            errors.append("build manifest does not use schema @2")
        if require_final and manifest.get("state") != "finalized":
            errors.append("build manifest is not finalized")
        manifest_entries = manifest.get("files", [])
        declared_paths = [entry.get("path") for entry in manifest_entries if isinstance(entry, dict)]
        if len(declared_paths) != len(set(declared_paths)):
            errors.append("build manifest contains duplicate paths")
        actual_paths = {
            path.relative_to(output).as_posix() for path in output.rglob("*")
            if path.is_file() and path.name != "build-manifest.json"
        }
        for relative in declared_paths:
            if not isinstance(relative, str) or relative.startswith(("/", "../")) or "/../" in relative:
                errors.append(f"manifest contains unsafe path: {relative!r}")
        for undeclared in sorted(actual_paths - set(declared_paths)):
            errors.append(f"delivered file is missing from manifest: {undeclared}")
        for absent in sorted(set(declared_paths) - actual_paths):
            errors.append(f"manifest references missing file: {absent}")
        for entry in manifest_entries:
            path = output / entry.get("path", "")
            if path.is_file():
                if entry.get("bytes") != path.stat().st_size:
                    errors.append(f"manifest byte count mismatch: {entry.get('path')}")
                if sha256(path) != entry.get("sha256"):
                    errors.append(f"manifest hash mismatch: {entry.get('path')}")
        budget = manifest.get("resource_budget")
        if not isinstance(budget, dict):
            errors.append("build manifest is missing resource_budget")
        else:
            max_image = budget.get("max_image_bytes")
            max_single = budget.get("max_single_file_bytes")
            if not isinstance(max_image, int) or not isinstance(max_single, int):
                errors.append("resource budget limits must be integers")
            else:
                if (output / "report.html").stat().st_size > max_single:
                    errors.append(f"report.html exceeds resource budget of {max_single} bytes")
                for asset in budget.get("assets", []):
                    if not isinstance(asset, dict) or not isinstance(asset.get("bytes"), int):
                        errors.append("resource budget contains an invalid asset record")
                    elif asset["bytes"] > max_image:
                        errors.append(f"{asset.get('path', 'asset')} exceeds resource budget of {max_image} bytes")
                notes.append(f"Resource budget: {len(budget.get('assets', []))} cover assets checked")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f"invalid build manifest: {exc}")

    pdf = output / "report.pdf"
    if pdf.is_file() and not pdf.read_bytes().startswith(b"%PDF-"):
        errors.append("report.pdf is not a valid PDF header")
    reference_contract = report_json.get("presentation", {}).get("reference_contract")
    if reference_contract:
        design_qa = output / "design-qa.md"
        if not design_qa.is_file() or "final result: passed" not in design_qa.read_text(encoding="utf-8").lower():
            errors.append("reference-led package requires design-qa.md with 'final result: passed'")

    node = shutil.which("node")
    if node:
        _check_node_script(node, app_text, "site/app.js", errors)
        executable = [
            content for attrs, content in single_parser.scripts
            if not attrs.get("type") or attrs.get("type") in {"text/javascript", "application/javascript", "module"}
        ]
        for index, content in enumerate(executable, start=1):
            _check_node_script(node, content, f"report.html inline script {index}", errors)
        if not errors:
            notes.append(f"JavaScript syntax: OK ({1 + len(executable)} scripts)")
    else:
        notes.append("JavaScript syntax: SKIPPED (node not found)")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-final", action="store_true")
    args = parser.parse_args()
    errors, notes = run_qa(args.output.resolve(), args.require_final)
    for note in notes:
        print(f"NOTE: {note}")
    for issue in errors:
        print(f"ERROR: {issue}", file=sys.stderr)
    if errors:
        return 1
    print(f"OK: offline package QA passed for {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
