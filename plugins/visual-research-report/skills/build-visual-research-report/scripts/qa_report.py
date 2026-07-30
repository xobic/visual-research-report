#!/usr/bin/env python3
"""Run deterministic offline-package QA for a built Visual Research Report."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path, PureWindowsPath
from typing import Any


REQUIRED = (
    "site/index.html", "site/styles.css", "site/app.js", "site/data/report-data.js",
    "report.html", "report.json", "build-manifest.json",
)
REQUIRED_APP_TOKENS = (
    "report.ui_labels", "app.inert", "data-stack-share", "data-scroll-latest",
    'role=\"tab\"', "ArrowRight", "drawerFocusable", "data-contained-overflow",
    "tension-balance", "history-scrolly", "causal-horizon-map", "data-history-mode",
    "data-node-id", "atom-engineering-svg", "editorial-dashboard", "chapter-track",
    "data-dashboard-state", "() => String(value)",
)
COVER_VIEW_IDS = ("recursive", "exploded", "blueprint", "impact")
DATA_URI_PATTERN = re.compile(r"^data:([^;,]+);base64,([A-Za-z0-9+/]*={0,2})$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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


def _parse_single_report_data(scripts: list[tuple[dict[str, str | None], str]]) -> dict[str, Any]:
    candidates: list[str] = []
    for _, content in scripts:
        stripped = content.strip()
        if stripped.startswith("window.REPORT_DATA="):
            candidates.append(stripped[len("window.REPORT_DATA="):].removesuffix(";"))
    if len(candidates) != 1:
        raise ValueError(f"report.html contains {len(candidates)} embedded REPORT_DATA assignments; expected one")
    parsed = json.loads(candidates[0])
    if not isinstance(parsed, dict):
        raise ValueError("embedded REPORT_DATA must be an object")
    return parsed


def _decode_data_uri(value: Any, label: str) -> tuple[str, bytes]:
    if not isinstance(value, str):
        raise ValueError(f"{label} is not a data URI string")
    matched = DATA_URI_PATTERN.fullmatch(value)
    if not matched:
        raise ValueError(f"{label} is not a canonical base64 data URI")
    mime, payload = matched.groups()
    if not mime.lower().startswith("image/"):
        raise ValueError(f"{label} has non-image media type {mime}")
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{label} has invalid base64: {exc}") from exc
    if not decoded:
        raise ValueError(f"{label} decodes to an empty asset")
    return mime.lower(), decoded


def _inspect_image_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError as exc:
        raise ValueError(f"{label} cannot be decoded because Pillow is unavailable") from exc
    try:
        with Image.open(io.BytesIO(payload)) as opened:
            image_format = str(opened.format or "").upper()
            frames = int(getattr(opened, "n_frames", 1))
            opened.verify()
        with Image.open(io.BytesIO(payload)) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
            width, height = image.size
    except (OSError, SyntaxError, ValueError) as exc:
        raise ValueError(f"{label} is not a decodable raster image: {exc}") from exc
    if image_format not in {"PNG", "JPEG", "WEBP"}:
        raise ValueError(f"{label} decoded as unsupported {image_format or 'unknown'}")
    if frames != 1 or width <= 0 or height <= 0:
        raise ValueError(f"{label} has invalid frames or dimensions")
    mime_by_format = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
    return {
        "format": image_format.lower(),
        "mime_type": mime_by_format[image_format],
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 6),
        "orientation": "square" if width == height else ("landscape" if width > height else "portrait"),
        "frames": frames,
    }


def _manifest_absolute_paths(value: Any, location: str = "manifest") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(_manifest_absolute_paths(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_manifest_absolute_paths(child, f"{location}[{index}]"))
    elif isinstance(value, str):
        if Path(value).is_absolute() or PureWindowsPath(value).is_absolute():
            found.append(location)
    return found


def _metadata_matches(actual: dict[str, Any], declared: Any) -> bool:
    if not isinstance(declared, dict):
        return False
    return all(declared.get(key) == value for key, value in actual.items())


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

    report: dict[str, Any] = {}
    single_report: dict[str, Any] = {}
    report_json: dict[str, Any] = {}
    embedded_by_view: dict[str, dict[str, Any]] = {}
    production_mode = "legacy"
    try:
        parsed_report = _parse_built_data(output / "site/data/report-data.js")
        parsed_single = _parse_single_report_data(single_parser.scripts)
        parsed_contract = json.loads((output / "report.json").read_text(encoding="utf-8"))
        if not all(isinstance(value, dict) for value in (parsed_report, parsed_single, parsed_contract)):
            raise ValueError("built, embedded, and contract report data must be objects")
        report = parsed_report
        single_report = parsed_single
        report_json = parsed_contract

        report_views = report.get("theme_atom", {}).get("views", [])
        single_views = single_report.get("theme_atom", {}).get("views", [])
        source_views = report_json.get("theme_atom", {}).get("views", [])
        if not all(isinstance(views, list) for views in (report_views, single_views, source_views)):
            raise ValueError("theme_atom.views must be arrays in every artifact")
        report_map = {view.get("id"): view for view in report_views if isinstance(view, dict)}
        single_map = {view.get("id"): view for view in single_views if isinstance(view, dict)}
        source_map = {view.get("id"): view for view in source_views if isinstance(view, dict)}
        if set(report_map) != set(COVER_VIEW_IDS) or len(report_views) != 4:
            errors.append("built report does not contain exactly the four required cover views")
        if set(single_map) != set(COVER_VIEW_IDS) or len(single_views) != 4:
            errors.append("single-file report does not contain exactly the four required cover views")

        production = report_json.get("theme_atom", {}).get("production")
        if isinstance(production, dict) and production.get("mode"):
            production_mode = str(production["mode"])
            if report.get("theme_atom", {}).get("production") != production:
                errors.append("multi-file report did not preserve theme_atom.production metadata")
            if single_report.get("theme_atom", {}).get("production") != production:
                errors.append("single-file report did not preserve theme_atom.production metadata")
        strict_assets = production_mode in {"image-2", "provided"}
        if production_mode == "image-2":
            if not isinstance(production, dict):
                errors.append("image-2 report is missing theme_atom.production")
            else:
                if production.get("model") != "gpt-image-2":
                    errors.append("image-2 report does not declare model gpt-image-2")
                if production.get("workflow") != "canonical-anchor-plus-direct-edits":
                    errors.append("image-2 report does not declare canonical-anchor-plus-direct-edits workflow")
                if production.get("master_format") != "png":
                    errors.append("image-2 report does not declare PNG master_format")
                if production.get("delivery_format") != "webp":
                    errors.append("image-2 report does not declare WebP delivery_format")
                if not production.get("anchor_asset"):
                    errors.append("image-2 report does not declare a canonical anchor_asset")

        for view_id in COVER_VIEW_IDS:
            source_view = source_map.get(view_id, {})
            built_view = report_map.get(view_id, {})
            embedded_view = single_map.get(view_id, {})
            source_has_asset = isinstance(source_view, dict) and bool(source_view.get("asset"))
            if strict_assets and not source_has_asset:
                errors.append(f"{production_mode} cover view {view_id} is missing its source asset declaration")
            if not source_has_asset:
                if isinstance(embedded_view, dict) and embedded_view.get("asset"):
                    errors.append(f"asset-free cover view {view_id} unexpectedly embeds an asset")
                continue
            try:
                built_asset = built_view.get("asset") if isinstance(built_view, dict) else None
                if not isinstance(built_asset, str) or not built_asset.startswith("assets/"):
                    raise ValueError("multi-file asset is not a canonical assets/ path")
                site_root = (output / "site").resolve()
                built_path = (site_root / built_asset).resolve()
                try:
                    built_path.relative_to(site_root)
                except ValueError as exc:
                    raise ValueError("multi-file asset escapes site directory") from exc
                if not built_path.is_file():
                    raise ValueError("multi-file asset is missing")
                data_uri = embedded_view.get("asset") if isinstance(embedded_view, dict) else None
                declared_mime, payload = _decode_data_uri(data_uri, f"single-file cover view {view_id}")
                if payload != built_path.read_bytes():
                    raise ValueError("embedded payload differs from multi-file cover asset")
                decoded_image = _inspect_image_bytes(payload, f"single-file cover view {view_id}")
                if declared_mime != decoded_image["mime_type"]:
                    raise ValueError(
                        f"declared media type {declared_mime} does not match decoded {decoded_image['mime_type']}"
                    )
                expected_status = "generated-image-2" if production_mode == "image-2" else "provided"
                if built_view.get("asset_status") != expected_status:
                    raise ValueError(f"multi-file asset_status must be {expected_status}")
                if embedded_view.get("asset_status") != "embedded":
                    raise ValueError("single-file asset_status must be embedded")
                embedded_by_view[view_id] = {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                    "data_uri_bytes": len(str(data_uri).encode("utf-8")),
                    "image": decoded_image,
                    "path": built_path.relative_to(output.resolve()).as_posix(),
                }
            except ValueError as exc:
                errors.append(f"cover view {view_id}: {exc}")

        if production_mode == "image-2":
            if set(embedded_by_view) != set(COVER_VIEW_IDS):
                errors.append("image-2 report does not contain four independently decoded embedded cover assets")
            hashes = [record["sha256"] for record in embedded_by_view.values()]
            if len(hashes) == 4 and len(set(hashes)) != 4:
                errors.append("image-2 embedded cover views must have distinct hashes")
            dimensions = {
                (record["image"]["width"], record["image"]["height"])
                for record in embedded_by_view.values()
            }
            if len(embedded_by_view) == 4 and len(dimensions) != 1:
                errors.append("image-2 embedded cover views must share canonical dimensions and aspect ratio")

        if report.get("evidence_status") in {"mixed", "synthetic"} and "data-disclosure" not in single:
            errors.append("synthetic or mixed report is missing the top data disclosure")
    except (json.JSONDecodeError, ValueError, AttributeError, TypeError) as exc:
        errors.append(f"built report data is invalid: {exc}")

    manifest_path = output / "build-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "visual-research-report/build-manifest@2":
            errors.append("build manifest does not use schema @2")
        absolute_locations = _manifest_absolute_paths({
            "source": manifest.get("source"),
            "resource_budget": manifest.get("resource_budget"),
        })
        if absolute_locations:
            errors.append(
                "build manifest exposes absolute filesystem paths at: "
                + ", ".join(absolute_locations[:4])
            )
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
            max_cover = budget.get("max_cover_bytes")
            max_single = budget.get("max_single_file_bytes")
            if not all(isinstance(limit, int) and limit > 0 for limit in (max_image, max_cover, max_single)):
                errors.append("resource budget limits must be integers")
            else:
                single_bytes = (output / "report.html").stat().st_size
                if single_bytes > max_single:
                    errors.append(f"report.html exceeds resource budget of {max_single} bytes")
                if budget.get("single_file_bytes") != single_bytes:
                    errors.append("resource budget single_file_bytes does not match report.html")
                if 4 * ((max_cover + 2) // 3) > max_single:
                    errors.append("max_cover_bytes is not base64-compatible with the single-file budget")

                assets = budget.get("assets", [])
                if not isinstance(assets, list):
                    errors.append("resource budget assets must be an array")
                    assets = []
                manifest_by_view: dict[str, dict[str, Any]] = {}
                for asset in assets:
                    if not isinstance(asset, dict) or not isinstance(asset.get("bytes"), int):
                        errors.append("resource budget contains an invalid asset record")
                        continue
                    view_id = asset.get("view_id")
                    if view_id in manifest_by_view:
                        errors.append(f"resource budget duplicates cover view {view_id}")
                    if isinstance(view_id, str):
                        manifest_by_view[view_id] = asset
                    if asset["bytes"] > max_image:
                        errors.append(f"{asset.get('path', 'asset')} exceeds resource budget of {max_image} bytes")
                    if not SHA256_PATTERN.fullmatch(str(asset.get("source_sha256", ""))):
                        errors.append(f"cover view {view_id} has invalid source_sha256 provenance")
                    if not SHA256_PATTERN.fullmatch(str(asset.get("built_sha256", ""))):
                        errors.append(f"cover view {view_id} has invalid built_sha256 provenance")
                    if production_mode == "image-2":
                        generation = asset.get("generation")
                        if not isinstance(generation, dict):
                            errors.append(f"cover view {view_id} is missing generation provenance")
                        elif generation.get("output_asset_sha256") != asset.get("source_sha256"):
                            errors.append(f"cover view {view_id} generation output hash does not match source master")
                    embedded = embedded_by_view.get(str(view_id))
                    if embedded:
                        if asset.get("path") != embedded["path"]:
                            errors.append(f"cover view {view_id} manifest path does not match built data")
                        if asset.get("bytes") != embedded["bytes"]:
                            errors.append(f"cover view {view_id} manifest byte count does not match decoded data URI")
                        if asset.get("built_sha256") != embedded["sha256"]:
                            errors.append(f"cover view {view_id} manifest hash does not match decoded data URI")
                        if asset.get("embedded_data_uri_bytes") != embedded["data_uri_bytes"]:
                            errors.append(f"cover view {view_id} manifest data URI size mismatch")
                        if not _metadata_matches(embedded["image"], asset.get("built_image")):
                            errors.append(f"cover view {view_id} built image metadata does not match real decode")
                    record_path = asset.get("path")
                    expected_prefix = f"site/assets/cover-{view_id}." if isinstance(view_id, str) else ""
                    if not isinstance(record_path, str) or not record_path.startswith(expected_prefix):
                        errors.append(f"cover view {view_id} does not use a canonical output filename")

                actual_cover_paths = {
                    path.relative_to(output).as_posix()
                    for path in (output / "site/assets").glob("cover-*")
                    if path.is_file()
                }
                declared_cover_paths = {
                    asset.get("path") for asset in assets
                    if isinstance(asset, dict) and isinstance(asset.get("path"), str)
                }
                if actual_cover_paths != declared_cover_paths:
                    errors.append("site/assets contains stale or undeclared cover assets")

                cover_bytes = sum(
                    asset.get("bytes", 0) for asset in assets
                    if isinstance(asset, dict) and isinstance(asset.get("bytes"), int)
                )
                embedded_uri_bytes = sum(
                    record["data_uri_bytes"] for record in embedded_by_view.values()
                )
                if budget.get("cover_bytes") != cover_bytes:
                    errors.append("resource budget cover_bytes does not equal the cover asset sum")
                if budget.get("cover_embedded_data_uri_bytes") != embedded_uri_bytes:
                    errors.append("resource budget cover_embedded_data_uri_bytes does not match embedded views")
                if cover_bytes > max_cover:
                    errors.append(f"cover assets total {cover_bytes} bytes; budget is {max_cover} bytes")

                cover_set = budget.get("cover_asset_set")
                if not isinstance(cover_set, dict):
                    errors.append("resource budget is missing cover_asset_set provenance")
                else:
                    if cover_set.get("mode") != production_mode:
                        errors.append("cover_asset_set mode does not match report production mode")
                    if cover_set.get("total_cover_bytes") != cover_bytes:
                        errors.append("cover_asset_set total_cover_bytes mismatch")
                    if cover_set.get("total_embedded_data_uri_bytes") != embedded_uri_bytes:
                        errors.append("cover_asset_set embedded byte count mismatch")
                    if cover_set.get("view_ids") != [
                        view_id for view_id in COVER_VIEW_IDS if view_id in manifest_by_view
                    ]:
                        errors.append("cover_asset_set view_ids are not canonical and ordered")
                    if cover_set.get("unique_built_hashes") != len({
                        asset.get("built_sha256") for asset in assets if isinstance(asset, dict)
                    }):
                        errors.append("cover_asset_set unique_built_hashes mismatch")

                    if production_mode == "image-2":
                        generator = cover_set.get("generator")
                        expected_generator = {
                            "model": "gpt-image-2",
                            "workflow": "canonical-anchor-plus-direct-edits",
                            "master_format": "png",
                            "delivery_format": "webp",
                        }
                        if not isinstance(generator, dict) or any(
                            generator.get(key) != value for key, value in expected_generator.items()
                        ):
                            errors.append("image-2 manifest generator provenance is incomplete")
                        anchor = cover_set.get("canonical_anchor")
                        if not isinstance(anchor, dict):
                            errors.append("image-2 manifest is missing canonical anchor provenance")
                        else:
                            anchor_hash = str(anchor.get("sha256", ""))
                            if not SHA256_PATTERN.fullmatch(anchor_hash):
                                errors.append("image-2 canonical anchor has invalid sha256")
                            if not isinstance(anchor.get("bytes"), int) or anchor.get("bytes", 0) <= 0:
                                errors.append("image-2 canonical anchor has invalid byte count")
                            anchor_image = anchor.get("image")
                            if not isinstance(anchor_image, dict) or anchor_image.get("format") != "png":
                                errors.append("image-2 canonical anchor is not declared as a decoded PNG")
                            elif isinstance(generator, dict) and generator.get("canvas") != {
                                "width": anchor_image.get("width"), "height": anchor_image.get("height")
                            }:
                                errors.append("image-2 generator canvas does not match canonical anchor dimensions")
                            source_hashes = [anchor_hash] + [
                                str(asset.get("source_sha256", "")) for asset in assets if isinstance(asset, dict)
                            ]
                            if len(source_hashes) != 5 or len(set(source_hashes)) != 5:
                                errors.append("image-2 anchor and view source hashes are not all distinct")
                            anchor_dimensions = (
                                anchor_image.get("width"), anchor_image.get("height")
                            ) if isinstance(anchor_image, dict) else None
                            for view_id, asset in manifest_by_view.items():
                                generation = asset.get("generation")
                                if isinstance(generation, dict) and generation.get("input_asset_sha256") != anchor_hash:
                                    errors.append(f"image-2 view {view_id} generation input hash does not match anchor")
                                source_image = asset.get("source_image")
                                if not isinstance(source_image, dict) or source_image.get("format") != "png":
                                    errors.append(f"image-2 source view {view_id} is not declared as a decoded PNG")
                                elif anchor_dimensions and (
                                    source_image.get("width"), source_image.get("height")
                                ) != anchor_dimensions:
                                    errors.append(f"image-2 source view {view_id} does not match anchor dimensions")
                                built_image = asset.get("built_image")
                                if not isinstance(built_image, dict) or built_image.get("format") != "webp":
                                    errors.append(f"image-2 built view {view_id} is not declared as WebP")
                        if set(manifest_by_view) != set(COVER_VIEW_IDS):
                            errors.append("image-2 manifest does not declare all four cover views")
                notes.append(f"Resource budget: {len(assets)} cover assets checked")
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
