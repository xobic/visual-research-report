#!/usr/bin/env python3
"""Validate the Visual Research Report JSON contract with no third-party packages."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SOURCE_ID = re.compile(r"^S\d{2,}$")
FACT_ID = re.compile(r"^F\d{2,}$")
CHART_TYPES = {
    "entity-ramp", "destiny-flow", "timeline", "matrix-heat",
    "value-stack", "odds-board", "line", "paired-bars", "tension-balance",
    "history-scrolly", "causal-horizon-map",
}
FACT_KINDS = {"reported", "estimate", "derived", "scenario", "threshold", "probability"}
COVER_VIEWS = {"recursive", "exploded", "blueprint", "impact"}
THEME_ATOM_PRODUCTION_MODES = {"image-2", "provided", "schematic"}
IMAGE_2_MODEL = "gpt-image-2"
IMAGE_2_WORKFLOW = "canonical-anchor-plus-direct-edits"
IMAGE_2_INVARIANTS = {"identity_lock", "camera_lock"}
IMAGE_2_FALLBACK = "schematic-explicit-only"
IMAGE_OUTPUT_FORMATS = {"png", "jpeg", "webp"}
IMAGE_ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
STACK_ENCODINGS = {"absolute", "share"}
SOURCE_CLASSIFICATIONS = {"primary", "secondary"}
CURRENT_SCHEMA = "visual-research-report@2"
PRESENTATION_PRESETS = {"institutional-rail", "editorial-longform", "editorial-scrollspy", "editorial-dashboard"}
EVIDENCE_STATUSES = {"verified", "mixed", "synthetic"}
LOCATOR_KINDS = {"document", "dataset", "web", "audio-video", "visual"}
EARNINGS_PRESET = "public-equity-earnings"
EARNINGS_CHECKS = {
    "expectation_delta", "organic_growth", "segment_cost_boundary", "one_offs",
    "guidance_change", "capex_to_fcf", "valuation_implied", "falsifiers",
}
SEMANTIC_TEXT_FIELDS = ("formula", "comparison_basis", "adjustment_scope", "boundary")


def load_report(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("report root must be a JSON object")
    return data


def _ids(items: Any, label: str, pattern: re.Pattern[str], errors: list[str]) -> set[str]:
    result: set[str] = set()
    if not isinstance(items, list):
        errors.append(f"{label} must be an array")
        return result
    for index, item in enumerate(items):
        path = f"{label}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not pattern.match(item_id):
            errors.append(f"{path}.id must match {pattern.pattern}")
            continue
        if item_id in result:
            errors.append(f"duplicate {label} id: {item_id}")
        result.add(item_id)
    return result


def _require_text(obj: dict[str, Any], keys: Iterable[str], path: str, errors: list[str]) -> None:
    for key in keys:
        if not isinstance(obj.get(key), str) or not obj[key].strip():
            errors.append(f"{path}.{key} must be a non-empty string")


def _check_refs(refs: Any, valid: set[str], path: str, errors: list[str], required: bool = False) -> None:
    if refs is None and not required:
        return
    if not isinstance(refs, list) or (required and not refs):
        errors.append(f"{path} must be a{' non-empty' if required else ''} array")
        return
    for ref in refs:
        if ref not in valid:
            errors.append(f"{path} references unknown id {ref!r}")


def _fact_ref(value: Any, path: str, fact_ids: set[str], errors: list[str], required: bool = True) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or value not in fact_ids:
        errors.append(f"{path} must reference an existing fact")


def _validate_dashboard(
    dashboard: Any,
    path: str,
    fact_ids: set[str],
    fact_lookup: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    if dashboard is None:
        return
    if not isinstance(dashboard, dict):
        errors.append(f"{path} must be an object")
        return

    _fact_ref(dashboard.get("primary_fact_id"), f"{path}.primary_fact_id", fact_ids, errors)

    def validate_fact_list(key: str, minimum: int, maximum: int, *, required: bool) -> list[str]:
        value = dashboard.get(key)
        if value is None and not required:
            return []
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            errors.append(f"{path}.{key} must contain between {minimum} and {maximum} fact ids")
            return []
        if len(value) != len(set(value)):
            errors.append(f"{path}.{key} must not contain duplicate fact ids")
        _check_refs(value, fact_ids, f"{path}.{key}", errors, required=required)
        return [item for item in value if isinstance(item, str) and item in fact_ids]

    trend_ids = validate_fact_list("trend_fact_ids", 2, 12, required=False)
    validate_fact_list("metric_fact_ids", 2, 4, required=True)
    scenario_ids = validate_fact_list("scenario_fact_ids", 1, 3, required=False)

    trend_units = {fact_lookup[fact_id].get("unit") for fact_id in trend_ids if fact_lookup.get(fact_id, {}).get("unit")}
    if len(trend_units) > 1:
        errors.append(f"{path}.trend_fact_ids must reference facts with one shared unit")
    for fact_id in scenario_ids:
        if fact_lookup.get(fact_id, {}).get("kind") != "probability":
            errors.append(f"{path}.scenario_fact_ids must reference probability facts")


def _number(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"{path} must be numeric")


def _normalized_number(value: Any, path: str, errors: list[str]) -> None:
    if not _finite_number(value) or not 0 <= float(value) <= 100:
        errors.append(f"{path} must be a finite number between 0 and 100")


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _validate_local_image_asset(value: Any, path: str, errors: list[str], *, required: bool) -> str | None:
    """Return a normalized safe relative asset path, or record a contract error."""
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty safe relative local image path")
        return None
    asset = value.strip()
    if (
        re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", asset)
        or asset.startswith(("/", "//", "\\\\"))
    ):
        errors.append(f"{path} must be a safe relative local image path; remote, data, and absolute paths are forbidden")
        return None
    if "\\" in asset or "?" in asset or "#" in asset or any(ord(character) < 32 for character in asset):
        errors.append(f"{path} must be a normalized relative local image path without backslashes, query strings, or fragments")
        return None
    normalized = PurePosixPath(asset)
    if ".." in normalized.parts:
        errors.append(f"{path} must not contain '..' path traversal")
        return None
    if normalized.name in {"", ".", ".."}:
        errors.append(f"{path} must name a local image file")
        return None
    if normalized.suffix.lower() not in IMAGE_ASSET_SUFFIXES:
        errors.append(f"{path} must use one of {sorted(IMAGE_ASSET_SUFFIXES)}")
        return None
    return normalized.as_posix()


def _validate_string_array(
    value: Any,
    path: str,
    errors: list[str],
    *,
    minimum: int = 1,
) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        errors.append(f"{path} must contain at least {minimum} non-empty string{'s' if minimum != 1 else ''}")
        return []
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        errors.append(f"{path} must not contain duplicates")
    return normalized


def _validate_focal_point(value: Any, path: str, errors: list[str]) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(_finite_number(item) and 0 <= float(item) <= 1 for item in value)
    ):
        errors.append(f"{path} must contain exactly two finite numbers between 0 and 1")


def _validate_canvas(value: Any, path: str, errors: list[str]) -> dict[str, int] | None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return None
    for key in ("width", "height"):
        dimension = value.get(key)
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension <= 0:
            errors.append(f"{path}.{key} must be a positive integer")
    if all(isinstance(value.get(key), int) and not isinstance(value.get(key), bool) and value[key] > 0 for key in ("width", "height")):
        return {"width": value["width"], "height": value["height"]}
    return None


def _validate_identity_lock(
    value: Any,
    path: str,
    schematic_part_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object for image-2 production")
        return
    _require_text(value, ("object_key", "physical_class", "silhouette"), path, errors)
    locked_part_ids = _validate_string_array(value.get("part_ids"), f"{path}.part_ids", errors)
    _validate_string_array(value.get("topology"), f"{path}.topology", errors)
    _validate_string_array(value.get("materials"), f"{path}.materials", errors)
    _validate_string_array(value.get("fiducials"), f"{path}.fiducials", errors, minimum=2)
    if locked_part_ids and schematic_part_ids:
        locked = set(locked_part_ids)
        unknown = locked - schematic_part_ids
        missing = schematic_part_ids - locked
        if unknown:
            errors.append(f"{path}.part_ids references unknown schematic parts: {sorted(unknown)}")
        if missing:
            errors.append(f"{path}.part_ids must include every canonical schematic part: {sorted(missing)}")


def _validate_camera_lock(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object for image-2 production")
        return
    _require_text(value, ("projection",), path, errors)
    for key in ("yaw_deg", "pitch_deg", "roll_deg"):
        if not _finite_number(value.get(key)):
            errors.append(f"{path}.{key} must be a finite number")
    focal_length = value.get("focal_length_equiv_mm")
    if not _finite_number(focal_length) or float(focal_length) <= 0:
        errors.append(f"{path}.focal_length_equiv_mm must be a positive finite number")
    _validate_focal_point(value.get("object_center"), f"{path}.object_center", errors)
    safe_margin = value.get("safe_margin")
    if not _finite_number(safe_margin) or not 0 <= float(safe_margin) <= 0.4:
        errors.append(f"{path}.safe_margin must be a finite number between 0 and 0.4")


def _validate_sha256(value: Any, path: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not SHA256_HEX.fullmatch(value):
        errors.append(f"{path} must be a lowercase 64-character SHA-256 hex digest")
        return None
    return value


def _validate_theme_atom_production(
    atom: dict[str, Any],
    views: Any,
    schematic_part_ids: set[str],
    errors: list[str],
) -> None:
    production = atom.get("production")
    mode: str | None = None
    if production is not None:
        if not isinstance(production, dict):
            errors.append("theme_atom.production must be an object")
        else:
            candidate_mode = production.get("mode")
            if candidate_mode not in THEME_ATOM_PRODUCTION_MODES:
                errors.append(f"theme_atom.production.mode must be one of {sorted(THEME_ATOM_PRODUCTION_MODES)}")
            else:
                mode = candidate_mode

    require_raster_views = mode in {"image-2", "provided"}
    normalized_assets: list[tuple[str, str]] = []
    for index, view in enumerate(views if isinstance(views, list) else []):
        if not isinstance(view, dict):
            continue
        path = f"theme_atom.views[{index}]"
        asset = _validate_local_image_asset(view.get("asset"), f"{path}.asset", errors, required=require_raster_views)
        if asset:
            normalized_assets.append((path, asset))
        if require_raster_views:
            _validate_focal_point(view.get("focal_point"), f"{path}.focal_point", errors)

    seen_assets: dict[str, str] = {}
    for path, asset in normalized_assets:
        asset_key = asset.casefold()
        if asset_key in seen_assets:
            errors.append(f"{path}.asset duplicates {seen_assets[asset_key]}.asset ({asset!r})")
        else:
            seen_assets[asset_key] = path

    if not isinstance(production, dict) or mode is None:
        return
    if mode == "schematic":
        if not isinstance(atom.get("schematic"), dict):
            errors.append("theme_atom.schematic is required when theme_atom.production.mode is 'schematic'")
        return

    canvas = _validate_canvas(production.get("canvas"), "theme_atom.production.canvas", errors)
    print_view_id = production.get("print_view_id")
    if print_view_id not in COVER_VIEWS:
        errors.append(f"theme_atom.production.print_view_id must be one of {sorted(COVER_VIEWS)}")

    for field in ("output_format", "master_format", "delivery_format"):
        value = production.get(field)
        if value is not None and value not in IMAGE_OUTPUT_FORMATS:
            errors.append(f"theme_atom.production.{field} must be one of {sorted(IMAGE_OUTPUT_FORMATS)}")

    if mode == "provided":
        return

    if production.get("model") != IMAGE_2_MODEL:
        errors.append(f"theme_atom.production.model must be {IMAGE_2_MODEL!r} for image-2 production")
    if production.get("workflow") != IMAGE_2_WORKFLOW:
        errors.append(f"theme_atom.production.workflow must be {IMAGE_2_WORKFLOW!r} for image-2 production")
    master_format = production.get("master_format")
    delivery_format = production.get("delivery_format")
    if master_format != "png":
        errors.append("theme_atom.production.master_format must be 'png' for image-2 source masters")
    if delivery_format != "webp":
        errors.append("theme_atom.production.delivery_format must be 'webp' for optimized delivery")
    if production.get("fallback") != IMAGE_2_FALLBACK:
        errors.append(f"theme_atom.production.fallback must be {IMAGE_2_FALLBACK!r} for image-2 production")
    if not isinstance(atom.get("schematic"), dict):
        errors.append("theme_atom.schematic is required as the explicit image-2 fallback")

    prompt_version = production.get("prompt_version")
    if not isinstance(prompt_version, str) or not prompt_version.strip():
        errors.append("theme_atom.production.prompt_version must be a non-empty string")
        prompt_version = None
    else:
        prompt_version = prompt_version.strip()

    anchor_asset = _validate_local_image_asset(
        production.get("anchor_asset"), "theme_atom.production.anchor_asset", errors, required=True
    )
    _validate_local_image_asset(
        production.get("contact_sheet_asset"), "theme_atom.production.contact_sheet_asset", errors, required=False
    )
    if anchor_asset and master_format == "png" and PurePosixPath(anchor_asset).suffix.lower() != ".png":
        errors.append("theme_atom.production.anchor_asset extension must match master_format 'png'")
    if anchor_asset and anchor_asset.casefold() in seen_assets:
        errors.append("theme_atom.production.anchor_asset must be distinct from all four output assets")

    _validate_identity_lock(atom.get("identity_lock"), "theme_atom.identity_lock", schematic_part_ids, errors)
    _validate_camera_lock(atom.get("camera_lock"), "theme_atom.camera_lock", errors)

    expected_master_suffixes = {
        "png": {".png"},
        "jpeg": {".jpg", ".jpeg"},
        "webp": {".webp"},
    }.get(master_format, set())
    input_hashes: list[tuple[str, str]] = []
    output_hashes: list[tuple[str, str]] = []
    for index, view in enumerate(views if isinstance(views, list) else []):
        if not isinstance(view, dict):
            continue
        path = f"theme_atom.views[{index}]"
        view_id = view.get("id")
        raw_asset = view.get("asset")
        if isinstance(raw_asset, str) and expected_master_suffixes:
            suffix = PurePosixPath(raw_asset.strip()).suffix.lower()
            if suffix not in expected_master_suffixes:
                errors.append(f"{path}.asset extension must match theme_atom.production.master_format {master_format!r}")
        if "canvas" in view:
            view_canvas = _validate_canvas(view.get("canvas"), f"{path}.canvas", errors)
            if canvas and view_canvas and view_canvas != canvas:
                errors.append(f"{path}.canvas must match theme_atom.production.canvas")

        generation = view.get("generation")
        if not isinstance(generation, dict):
            errors.append(f"{path}.generation must be an object for image-2 production")
            continue
        if generation.get("operation") != "edit":
            errors.append(f"{path}.generation.operation must be 'edit'")
        parent_asset = _validate_local_image_asset(
            generation.get("parent_asset"), f"{path}.generation.parent_asset", errors, required=True
        )
        if anchor_asset and parent_asset and parent_asset != anchor_asset:
            errors.append(f"{path}.generation.parent_asset must equal theme_atom.production.anchor_asset")
        expected_prompt_id = f"{prompt_version}/{view_id}" if prompt_version and isinstance(view_id, str) else None
        if expected_prompt_id and generation.get("prompt_id") != expected_prompt_id:
            errors.append(f"{path}.generation.prompt_id must be {expected_prompt_id!r}")
        invariants = generation.get("invariants")
        if (
            not isinstance(invariants, list)
            or len(invariants) != len(IMAGE_2_INVARIANTS)
            or set(invariants) != IMAGE_2_INVARIANTS
        ):
            errors.append(f"{path}.generation.invariants must contain exactly {sorted(IMAGE_2_INVARIANTS)}")
        if generation.get("qa_status") != "passed":
            errors.append(f"{path}.generation.qa_status must be 'passed'")
        input_hash = _validate_sha256(
            generation.get("input_asset_sha256"), f"{path}.generation.input_asset_sha256", errors
        )
        output_hash = _validate_sha256(
            generation.get("output_asset_sha256"), f"{path}.generation.output_asset_sha256", errors
        )
        if input_hash:
            input_hashes.append((path, input_hash))
        if output_hash:
            output_hashes.append((path, output_hash))
        if input_hash and output_hash and input_hash == output_hash:
            errors.append(f"{path}.generation.output_asset_sha256 must differ from its anchor input digest")
        if "canvas" in generation:
            generation_canvas = _validate_canvas(generation.get("canvas"), f"{path}.generation.canvas", errors)
            if canvas and generation_canvas and generation_canvas != canvas:
                errors.append(f"{path}.generation.canvas must match theme_atom.production.canvas")

    if len({digest for _, digest in input_hashes}) > 1:
        errors.append("theme_atom.views generation input_asset_sha256 values must all identify the same canonical anchor")
    seen_output_hashes: dict[str, str] = {}
    for path, digest in output_hashes:
        if digest in seen_output_hashes:
            errors.append(f"{path}.generation.output_asset_sha256 duplicates {seen_output_hashes[digest]}.generation output")
        else:
            seen_output_hashes[digest] = path


def _normalized_unit(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r"[\s_-]+", " ", value.strip().lower())


def _assert_mark_matches_fact(
    value: Any,
    fact_id: Any,
    fact_lookup: dict[str, dict[str, Any]],
    path: str,
    errors: list[str],
) -> None:
    fact = fact_lookup.get(fact_id) if isinstance(fact_id, str) else None
    if not fact or not _finite_number(value) or not _finite_number(fact.get("value")):
        return
    if not math.isclose(float(value), float(fact["value"]), rel_tol=1e-9, abs_tol=1e-9):
        errors.append(f"{path} value {value!r} does not match {fact_id}.value {fact['value']!r}")


def _validate_scale(
    scale: Any,
    path: str,
    values: list[float],
    errors: list[str],
    *,
    required: bool = False,
    allowed_modes: set[str] | None = None,
) -> str | None:
    if scale is None:
        if required:
            errors.append(f"{path} is required and must use an actual scale")
        return None
    if not isinstance(scale, dict):
        errors.append(f"{path} must be an object")
        return None
    allowed = allowed_modes or {"actual"}
    mode = scale.get("mode")
    if mode not in allowed:
        errors.append(f"{path}.mode must be one of {sorted(allowed)}")
        return None
    if mode == "per-pair-actual":
        return mode
    domain = scale.get("domain")
    if not isinstance(domain, list) or len(domain) != 2 or not all(_finite_number(item) for item in domain):
        errors.append(f"{path}.domain must contain two finite numbers")
        return mode
    low, high = float(domain[0]), float(domain[1])
    if low >= high:
        errors.append(f"{path}.domain must be strictly increasing")
    ticks = scale.get("ticks")
    if not isinstance(ticks, list) or len(ticks) < 2 or not all(_finite_number(item) for item in ticks):
        errors.append(f"{path}.ticks must contain at least two finite numbers")
    else:
        numeric_ticks = [float(item) for item in ticks]
        if any(left >= right for left, right in zip(numeric_ticks, numeric_ticks[1:])):
            errors.append(f"{path}.ticks must be strictly increasing")
        if any(item < low or item > high for item in numeric_ticks):
            errors.append(f"{path}.ticks must stay inside the declared domain")
    if not scale.get("allow_overflow") and any(item < low or item > high for item in values):
        errors.append(f"{path}.domain does not contain every chart value")
    unit = scale.get("unit")
    if unit is not None and _normalized_unit(unit) is None:
        errors.append(f"{path}.unit must be a non-empty string")
    return mode


def _validate_locator(locator: Any, source: dict[str, Any], path: str, errors: list[str], required: bool) -> None:
    if locator is None:
        if required:
            errors.append(f"{path} is required for a fact-cited source")
        return
    if not isinstance(locator, dict) or not locator:
        errors.append(f"{path} must be a non-empty object")
        return
    if any(not isinstance(value, (str, int)) or isinstance(value, bool) for value in locator.values()):
        errors.append(f"{path} values must be strings or integers")
        return
    kind = locator.get("kind")
    if kind not in LOCATOR_KINDS:
        errors.append(f"{path}.kind must be one of {sorted(LOCATOR_KINDS)}")
        return
    populated = {key for key, value in locator.items() if key != "kind" and str(value).strip()}
    required_any = {
        "document": {"page", "section", "table"},
        "dataset": {"table", "row", "cell", "version", "section"},
        "web": {"section", "anchor"},
        "audio-video": {"timestamp"},
        "visual": {"asset", "region"},
    }[kind]
    if not populated & required_any:
        errors.append(f"{path} needs at least one of {sorted(required_any)} for kind {kind!r}")
    if kind == "document" and "page" in locator and (not isinstance(locator["page"], int) or locator["page"] < 1):
        errors.append(f"{path}.page must be an integer >= 1")
    if kind == "web":
        url = source.get("url")
        if not isinstance(url, str) or not re.match(r"^https?://", url, flags=re.I):
            errors.append(f"{path} requires an http/https source URL for kind 'web'")
        if not isinstance(source.get("accessed_at"), str) or not source["accessed_at"].strip():
            errors.append(f"{path} requires source.accessed_at for kind 'web'")


def _fact_unit(fact_id: Any, fact_lookup: dict[str, dict[str, Any]]) -> str | None:
    fact = fact_lookup.get(fact_id) if isinstance(fact_id, str) else None
    unit = fact.get("unit") if fact else None
    return _normalized_unit(unit)


def _validate_chart(
    chart: Any,
    path: str,
    fact_ids: set[str],
    fact_lookup: dict[str, dict[str, Any]],
    source_ids: set[str],
    errors: list[str],
    schema_v2: bool,
) -> None:
    if not isinstance(chart, dict):
        errors.append(f"{path} must be an object")
        return
    _require_text(chart, ("id", "type", "title", "subtitle"), path, errors)
    chart_type = chart.get("type")
    if chart_type not in CHART_TYPES:
        errors.append(f"{path}.type must be one of {sorted(CHART_TYPES)}")
        return
    _check_refs(chart.get("source_ids"), source_ids, f"{path}.source_ids", errors, required=True)
    data = chart.get("data")
    if not isinstance(data, dict):
        errors.append(f"{path}.data must be an object")
        return

    if chart_type == "entity-ramp":
        periods = data.get("periods")
        if not isinstance(periods, list) or not periods:
            errors.append(f"{path}.data.periods must be a non-empty array")
        else:
            for i, period in enumerate(periods):
                p = f"{path}.data.periods[{i}]"
                if not isinstance(period, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(period, ("label",), p, errors)
                _number(period.get("value"), f"{p}.value", errors)
                fact_id = period.get("fact_id")
                _fact_ref(fact_id, f"{p}.fact_id", fact_ids, errors)
                _assert_mark_matches_fact(period.get("value"), fact_id, fact_lookup, p, errors)

    elif chart_type == "destiny-flow":
        nodes, links = data.get("nodes"), data.get("links")
        node_ids: set[str] = set()
        if not isinstance(nodes, list) or not nodes:
            errors.append(f"{path}.data.nodes must be a non-empty array")
        else:
            for i, node in enumerate(nodes):
                p = f"{path}.data.nodes[{i}]"
                if not isinstance(node, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(node, ("id", "label", "stage"), p, errors)
                if node.get("id") in node_ids:
                    errors.append(f"{p}.id duplicates node {node.get('id')!r}")
                node_ids.add(node.get("id"))
                fact_id = node.get("fact_id")
                _fact_ref(fact_id, f"{p}.fact_id", fact_ids, errors, required=schema_v2 and node.get("value") is not None)
                _assert_mark_matches_fact(node.get("value"), fact_id, fact_lookup, p, errors)
        if not isinstance(links, list) or not links:
            errors.append(f"{path}.data.links must be a non-empty array")
        else:
            for i, link in enumerate(links):
                p = f"{path}.data.links[{i}]"
                if not isinstance(link, dict):
                    errors.append(f"{p} must be an object")
                    continue
                if link.get("source") not in node_ids or link.get("target") not in node_ids:
                    errors.append(f"{p} must connect declared nodes")
                _number(link.get("value"), f"{p}.value", errors)
                fact_id = link.get("fact_id")
                shows_value = bool(link.get("show_value") or link.get("display"))
                _fact_ref(fact_id, f"{p}.fact_id", fact_ids, errors, required=schema_v2 and shows_value)
                _assert_mark_matches_fact(link.get("value"), fact_id, fact_lookup, p, errors)

    elif chart_type == "timeline":
        events = data.get("events")
        if not isinstance(events, list) or not events:
            errors.append(f"{path}.data.events must be a non-empty array")
        else:
            for i, event in enumerate(events):
                p = f"{path}.data.events[{i}]"
                if not isinstance(event, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(event, ("date", "title", "description"), p, errors)
                _fact_ref(event.get("fact_id"), f"{p}.fact_id", fact_ids, errors, required=False)
                _check_refs(event.get("source_ids"), source_ids, f"{p}.source_ids", errors)

    elif chart_type == "matrix-heat":
        columns, rows = data.get("columns"), data.get("rows")
        matrix_values: list[float] = []
        if not isinstance(columns, list) or not columns:
            errors.append(f"{path}.data.columns must be a non-empty array")
        if not isinstance(rows, list) or not rows:
            errors.append(f"{path}.data.rows must be a non-empty array")
        else:
            for i, row in enumerate(rows):
                p = f"{path}.data.rows[{i}]"
                if not isinstance(row, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(row, ("label",), p, errors)
                values = row.get("values")
                if not isinstance(values, list) or len(values) != len(columns or []):
                    errors.append(f"{p}.values must match columns length")
                    continue
                for j, cell in enumerate(values):
                    c = f"{p}.values[{j}]"
                    if not isinstance(cell, dict):
                        errors.append(f"{c} must be an object")
                        continue
                    _number(cell.get("value"), f"{c}.value", errors)
                    fact_id = cell.get("fact_id")
                    _fact_ref(fact_id, f"{c}.fact_id", fact_ids, errors)
                    _assert_mark_matches_fact(cell.get("value"), fact_id, fact_lookup, c, errors)
                    if _finite_number(cell.get("value")):
                        matrix_values.append(float(cell["value"]))
        _validate_scale(data.get("scale"), f"{path}.data.scale", matrix_values, errors, required=schema_v2)

    elif chart_type == "value-stack":
        encoding = data.get("encoding", "absolute")
        if encoding not in STACK_ENCODINGS:
            errors.append(f"{path}.data.encoding must be one of {sorted(STACK_ENCODINGS)}")
        layers = data.get("layers")
        values: list[float] = []
        if not isinstance(layers, list) or not layers:
            errors.append(f"{path}.data.layers must be a non-empty array")
        else:
            for i, layer in enumerate(layers):
                p = f"{path}.data.layers[{i}]"
                if not isinstance(layer, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(layer, ("label",), p, errors)
                _number(layer.get("value"), f"{p}.value", errors)
                if isinstance(layer.get("value"), (int, float)) and not isinstance(layer.get("value"), bool):
                    values.append(float(layer["value"]))
                fact_id = layer.get("fact_id")
                _fact_ref(fact_id, f"{p}.fact_id", fact_ids, errors)
                _assert_mark_matches_fact(layer.get("value"), fact_id, fact_lookup, p, errors)
        if encoding == "share" and values:
            if any(value < 0 for value in values):
                errors.append(f"{path}.data.layers cannot contain negative values when encoding is share")
            share_total = data.get("share_total", 1 if sum(values) <= 1.01 else 100)
            _number(share_total, f"{path}.data.share_total", errors)
            tolerance = data.get("share_tolerance", 0.005 if share_total == 1 else 0.5)
            _number(tolerance, f"{path}.data.share_tolerance", errors)
            if isinstance(share_total, (int, float)) and isinstance(tolerance, (int, float)):
                if abs(sum(values) - share_total) > tolerance:
                    errors.append(f"{path}.data.layers sum to {sum(values):g}; expected {share_total:g} ± {tolerance:g}")

    elif chart_type == "odds-board":
        items = data.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"{path}.data.items must be a non-empty array")
        else:
            for i, item in enumerate(items):
                p = f"{path}.data.items[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(item, ("label",), p, errors)
                if schema_v2:
                    _require_text(item, ("horizon", "trigger"), p, errors)
                probability = item.get("probability")
                _number(probability, f"{p}.probability", errors)
                if isinstance(probability, (int, float)) and not 0 <= probability <= 1:
                    errors.append(f"{p}.probability must be between 0 and 1")
                fact_id = item.get("fact_id")
                _fact_ref(fact_id, f"{p}.fact_id", fact_ids, errors)
                _assert_mark_matches_fact(probability, fact_id, fact_lookup, p, errors)

    elif chart_type == "line":
        series = data.get("series")
        names: set[str] = set()
        colors: set[str] = set()
        units: set[str] = set()
        line_values: list[float] = []
        if not isinstance(series, list) or not series:
            errors.append(f"{path}.data.series must be a non-empty array")
        else:
            for i, item in enumerate(series):
                p = f"{path}.data.series[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(item, ("name",), p, errors)
                name = item.get("name")
                if name in names:
                    errors.append(f"{p}.name duplicates series {name!r}")
                names.add(name)
                color = item.get("color")
                if color is not None:
                    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{3,8}|(?:rgb|hsl)a?\([^;{}]+\)|[a-zA-Z]+", color.strip()):
                        errors.append(f"{p}.color must be a safe CSS color")
                    elif color.lower() in colors:
                        errors.append(f"{p}.color duplicates another series color")
                    else:
                        colors.add(color.lower())
                points = item.get("points")
                if not isinstance(points, list) or len(points) < 2:
                    errors.append(f"{p}.points must contain at least two points")
                    continue
                for j, point in enumerate(points):
                    c = f"{p}.points[{j}]"
                    if not isinstance(point, dict) or "x" not in point:
                        errors.append(f"{c} must be an object with x")
                        continue
                    _number(point.get("y"), f"{c}.y", errors)
                    fact_id = point.get("fact_id")
                    _fact_ref(fact_id, f"{c}.fact_id", fact_ids, errors)
                    _assert_mark_matches_fact(point.get("y"), fact_id, fact_lookup, c, errors)
                    if _finite_number(point.get("y")):
                        line_values.append(float(point["y"]))
                    unit = _fact_unit(fact_id, fact_lookup)
                    if unit:
                        units.add(unit)
        if len(units) > 1 and not data.get("allow_mixed_units"):
            errors.append(f"{path}.data line facts use inconsistent units: {sorted(units)}")
        _validate_scale(data.get("scale"), f"{path}.data.scale", line_values, errors, required=schema_v2)

    elif chart_type == "history-scrolly":
        series = data.get("series")
        names: set[str] = set()
        colors: set[str] = set()
        units: set[str] = set()
        history_values: list[float] = []
        first_series_labels: list[str] = []
        if not isinstance(series, list) or not series:
            errors.append(f"{path}.data.series must be a non-empty array")
        else:
            for i, item in enumerate(series):
                p = f"{path}.data.series[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(item, ("name",), p, errors)
                name = item.get("name")
                if name in names:
                    errors.append(f"{p}.name duplicates series {name!r}")
                names.add(name)
                color = item.get("color")
                if color is not None:
                    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{3,8}|(?:rgb|hsl)a?\([^;{}]+\)|[a-zA-Z]+", color.strip()):
                        errors.append(f"{p}.color must be a safe CSS color")
                    elif color.lower() in colors:
                        errors.append(f"{p}.color duplicates another series color")
                    else:
                        colors.add(color.lower())
                points = item.get("points")
                if not isinstance(points, list) or len(points) < 2:
                    errors.append(f"{p}.points must contain at least two points")
                    continue
                point_labels: set[str] = set()
                for j, point in enumerate(points):
                    c = f"{p}.points[{j}]"
                    if not isinstance(point, dict):
                        errors.append(f"{c} must be an object")
                        continue
                    _require_text(point, ("label",), c, errors)
                    label = point.get("label")
                    if isinstance(label, str) and label.strip():
                        if label in point_labels:
                            errors.append(f"{c}.label duplicates point {label!r} in the same series")
                        point_labels.add(label)
                        if i == 0:
                            first_series_labels.append(label)
                    _number(point.get("value"), f"{c}.value", errors)
                    fact_id = point.get("fact_id")
                    _fact_ref(fact_id, f"{c}.fact_id", fact_ids, errors)
                    _assert_mark_matches_fact(point.get("value"), fact_id, fact_lookup, c, errors)
                    if _finite_number(point.get("value")):
                        history_values.append(float(point["value"]))
                    unit = _fact_unit(fact_id, fact_lookup)
                    if unit:
                        units.add(unit)
        if len(units) > 1 and not data.get("allow_mixed_units"):
            errors.append(f"{path}.data history facts use inconsistent units: {sorted(units)}")
        _validate_scale(data.get("scale"), f"{path}.data.scale", history_values, errors, required=True)

        scenes = data.get("scenes")
        scene_ids: set[str] = set()
        label_positions = {label: index for index, label in enumerate(first_series_labels)}
        if not isinstance(scenes, list) or len(scenes) < 2:
            errors.append(f"{path}.data.scenes must contain at least two scenes")
        else:
            for i, scene in enumerate(scenes):
                p = f"{path}.data.scenes[{i}]"
                if not isinstance(scene, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(scene, ("id", "title", "start_label", "end_label"), p, errors)
                scene_id = scene.get("id")
                if isinstance(scene_id, str) and scene_id.strip():
                    if scene_id in scene_ids:
                        errors.append(f"{p}.id duplicates scene {scene_id!r}")
                    scene_ids.add(scene_id)
                if "body" in scene and (not isinstance(scene["body"], str) or not scene["body"].strip()):
                    errors.append(f"{p}.body must be a non-empty string")
                _check_refs(scene.get("annotation_fact_ids"), fact_ids, f"{p}.annotation_fact_ids", errors)
                start_label, end_label = scene.get("start_label"), scene.get("end_label")
                if start_label not in label_positions:
                    errors.append(f"{p}.start_label must exist in the first series")
                if end_label not in label_positions:
                    errors.append(f"{p}.end_label must exist in the first series")
                if start_label in label_positions and end_label in label_positions:
                    if label_positions[start_label] >= label_positions[end_label]:
                        errors.append(f"{p} start_label must precede end_label in the first series")

    elif chart_type == "causal-horizon-map":
        horizons = data.get("horizons")
        horizon_ids: set[str] = set()
        if not isinstance(horizons, list) or len(horizons) < 2:
            errors.append(f"{path}.data.horizons must contain at least two horizons")
        else:
            for i, horizon in enumerate(horizons):
                p = f"{path}.data.horizons[{i}]"
                if not isinstance(horizon, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(horizon, ("id", "label"), p, errors)
                horizon_id = horizon.get("id")
                if isinstance(horizon_id, str) and horizon_id.strip():
                    if horizon_id in horizon_ids:
                        errors.append(f"{p}.id duplicates horizon {horizon_id!r}")
                    horizon_ids.add(horizon_id)

        nodes = data.get("nodes")
        node_ids: set[str] = set()
        if not isinstance(nodes, list) or len(nodes) < 2:
            errors.append(f"{path}.data.nodes must contain at least two nodes")
        else:
            for i, node in enumerate(nodes):
                p = f"{path}.data.nodes[{i}]"
                if not isinstance(node, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(node, ("id", "label", "horizon_id", "direction", "confidence"), p, errors)
                node_id = node.get("id")
                if isinstance(node_id, str) and node_id.strip():
                    if node_id in node_ids:
                        errors.append(f"{p}.id duplicates node {node_id!r}")
                    node_ids.add(node_id)
                if node.get("horizon_id") not in horizon_ids:
                    errors.append(f"{p}.horizon_id must reference a declared horizon")
                if node.get("direction") not in {"up", "down", "mixed"}:
                    errors.append(f"{p}.direction must be up, down, or mixed")
                if node.get("confidence") not in {"low", "medium", "high"}:
                    errors.append(f"{p}.confidence must be low, medium, or high")
                _fact_ref(node.get("signal_fact_id"), f"{p}.signal_fact_id", fact_ids, errors)
                _fact_ref(node.get("lag_fact_id"), f"{p}.lag_fact_id", fact_ids, errors, required=False)
                _fact_ref(node.get("threshold_fact_id"), f"{p}.threshold_fact_id", fact_ids, errors, required=False)

                sparkline = node.get("sparkline")
                if not isinstance(sparkline, dict):
                    errors.append(f"{p}.sparkline must be an object")
                    continue
                points = sparkline.get("points")
                sparkline_values: list[float] = []
                point_labels: set[str] = set()
                if not isinstance(points, list) or len(points) < 2:
                    errors.append(f"{p}.sparkline.points must contain at least two points")
                else:
                    for j, point in enumerate(points):
                        c = f"{p}.sparkline.points[{j}]"
                        if not isinstance(point, dict):
                            errors.append(f"{c} must be an object")
                            continue
                        _require_text(point, ("label",), c, errors)
                        label = point.get("label")
                        if isinstance(label, str) and label.strip():
                            if label in point_labels:
                                errors.append(f"{c}.label duplicates point {label!r} in the same sparkline")
                            point_labels.add(label)
                        _number(point.get("value"), f"{c}.value", errors)
                        fact_id = point.get("fact_id")
                        _fact_ref(fact_id, f"{c}.fact_id", fact_ids, errors)
                        _assert_mark_matches_fact(point.get("value"), fact_id, fact_lookup, c, errors)
                        if _finite_number(point.get("value")):
                            sparkline_values.append(float(point["value"]))
                _validate_scale(
                    sparkline.get("scale"), f"{p}.sparkline.scale", sparkline_values, errors, required=True,
                )

        edges = data.get("edges")
        if not isinstance(edges, list) or not edges:
            errors.append(f"{path}.data.edges must be a non-empty array")
        else:
            for i, edge in enumerate(edges):
                p = f"{path}.data.edges[{i}]"
                if not isinstance(edge, dict):
                    errors.append(f"{p} must be an object")
                    continue
                source, target = edge.get("from"), edge.get("to")
                if source not in node_ids or target not in node_ids:
                    errors.append(f"{p} must connect declared nodes")
                if source is not None and source == target:
                    errors.append(f"{p} cannot connect a node to itself")
                if "label" in edge and (not isinstance(edge["label"], str) or not edge["label"].strip()):
                    errors.append(f"{p}.label must be a non-empty string")

    elif chart_type == "paired-bars":
        items = data.get("items")
        scale = data.get("scale")
        scale_mode = scale.get("mode") if isinstance(scale, dict) else None
        all_pair_values: list[float] = []
        if not isinstance(items, list) or not items:
            errors.append(f"{path}.data.items must be a non-empty array")
        else:
            for i, item in enumerate(items):
                p = f"{path}.data.items[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(item, ("label",), p, errors)
                pair_units: set[str] = set()
                for side in ("left", "right"):
                    member, s = item.get(side), f"{p}.{side}"
                    if not isinstance(member, dict):
                        errors.append(f"{s} must be an object")
                        continue
                    _require_text(member, ("label",), s, errors)
                    _number(member.get("value"), f"{s}.value", errors)
                    fact_id = member.get("fact_id")
                    _fact_ref(fact_id, f"{s}.fact_id", fact_ids, errors)
                    _assert_mark_matches_fact(member.get("value"), fact_id, fact_lookup, s, errors)
                    if _finite_number(member.get("value")):
                        all_pair_values.append(float(member["value"]))
                    unit = _fact_unit(fact_id, fact_lookup)
                    if unit:
                        pair_units.add(unit)
                if len(pair_units) > 1 and not data.get("allow_mixed_units"):
                    errors.append(f"{p} compares incompatible units: {sorted(pair_units)}")
                if scale_mode == "per-pair-actual":
                    pair_values = [
                        float(member["value"]) for member in (item.get("left"), item.get("right"))
                        if isinstance(member, dict) and _finite_number(member.get("value"))
                    ]
                    _validate_scale(item.get("scale"), f"{p}.scale", pair_values, errors, required=True)
                multiplier_id = item.get("multiplier_fact_id")
                if multiplier_id is not None:
                    _fact_ref(multiplier_id, f"{p}.multiplier_fact_id", fact_ids, errors)
                    multiplier = fact_lookup.get(multiplier_id) if isinstance(multiplier_id, str) else None
                    left, right = item.get("left"), item.get("right")
                    if isinstance(left, dict) and isinstance(right, dict) and multiplier:
                        baseline = left.get("value")
                        if _finite_number(baseline) and float(baseline) == 0:
                            errors.append(f"{p}.multiplier_fact_id cannot divide by a zero baseline")
                        elif _finite_number(baseline) and _finite_number(right.get("value")):
                            expected = float(right["value"]) / float(baseline)
                            _assert_mark_matches_fact(expected, multiplier_id, fact_lookup, f"{p}.multiplier", errors)
                        if multiplier.get("kind") != "derived":
                            errors.append(f"{p}.multiplier_fact_id must reference a derived fact")
                        pair_fact_ids = {left.get("fact_id"), right.get("fact_id")}
                        if set(multiplier.get("derived_from") or []) != pair_fact_ids:
                            errors.append(f"{p}.multiplier_fact_id derived_from must contain the paired facts")
        _validate_scale(
            scale, f"{path}.data.scale", all_pair_values, errors,
            required=schema_v2, allowed_modes={"actual", "per-pair-actual"},
        )

    elif chart_type == "tension-balance":
        balance_values: list[float] = []
        for group in ("long", "short", "tripwires"):
            items = data.get(group)
            if not isinstance(items, list) or not items:
                errors.append(f"{path}.data.{group} must be a non-empty array")
                continue
            for index, item in enumerate(items):
                p = f"{path}.data.{group}[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{p} must be an object")
                    continue
                _require_text(item, ("label",), p, errors)
                fact_id = item.get("fact_id")
                _fact_ref(fact_id, f"{p}.fact_id", fact_ids, errors)
                fact = fact_lookup.get(fact_id) if isinstance(fact_id, str) else None
                if fact and _finite_number(fact.get("value")):
                    balance_values.append(float(fact["value"]))
                if group == "tripwires" and fact and fact.get("kind") not in {"scenario", "threshold"}:
                    errors.append(f"{p}.fact_id must reference a scenario or threshold fact")
        _require_text(data, ("center_label",), f"{path}.data", errors)
        _validate_scale(data.get("scale"), f"{path}.data.scale", balance_values, errors, required=True)


def validate_report(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    schema = data.get("schema")
    schema_v2 = schema == CURRENT_SCHEMA
    if schema is None:
        warnings.append(f"schema should be {CURRENT_SCHEMA!r}; legacy input accepted only for migration")
    elif not schema_v2:
        errors.append(f"schema must be {CURRENT_SCHEMA!r}")

    presentation = data.get("presentation")
    if not isinstance(presentation, dict):
        if schema_v2:
            errors.append("presentation must be an object for schema @2")
    else:
        if presentation.get("preset") not in PRESENTATION_PRESETS:
            errors.append(f"presentation.preset must be one of {sorted(PRESENTATION_PRESETS)}")
        reference = presentation.get("reference_contract")
        if reference is not None:
            if not isinstance(reference, dict):
                errors.append("presentation.reference_contract must be an object")
            else:
                _require_text(reference, ("asset", "notes"), "presentation.reference_contract", errors)
                for key in ("width", "height"):
                    if not isinstance(reference.get(key), int) or isinstance(reference.get(key), bool) or reference[key] <= 0:
                        errors.append(f"presentation.reference_contract.{key} must be a positive integer")

    evidence_status = data.get("evidence_status")
    if evidence_status not in EVIDENCE_STATUSES:
        if schema_v2 or evidence_status is not None:
            errors.append(f"evidence_status must be one of {sorted(EVIDENCE_STATUSES)}")

    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
    else:
        _require_text(meta, ("title", "subtitle", "kicker", "publisher", "as_of", "language", "summary"), "meta", errors)
        if meta.get("language") not in {"en-US", "zh-CN"}:
            if schema_v2:
                errors.append("meta.language must be 'en-US' or 'zh-CN'")
            else:
                warnings.append("meta.language should be normalized to 'en-US' or 'zh-CN'")

    ui_labels = data.get("ui_labels")
    if ui_labels is not None:
        if not isinstance(ui_labels, dict):
            errors.append("ui_labels must be an object")
        else:
            for key, value in ui_labels.items():
                if not isinstance(key, str) or not key or not isinstance(value, str) or not value.strip():
                    errors.append("ui_labels keys and values must be non-empty strings")

    atom = data.get("theme_atom")
    if not isinstance(atom, dict):
        errors.append("theme_atom must be an object")
    else:
        _require_text(atom, ("name", "description"), "theme_atom", errors)
        views = atom.get("views")
        if not isinstance(views, list):
            errors.append("theme_atom.views must be an array")
        else:
            view_ids = {view.get("id") for view in views if isinstance(view, dict)}
            if view_ids != COVER_VIEWS or len(views) != 4:
                errors.append(f"theme_atom.views must contain exactly {sorted(COVER_VIEWS)}")
            for index, view in enumerate(views):
                if isinstance(view, dict):
                    _require_text(view, ("id", "label", "alt"), f"theme_atom.views[{index}]", errors)

        schematic = atom.get("schematic")
        schematic_part_ids: set[str] = set()
        if schematic is not None:
            if not isinstance(schematic, dict):
                errors.append("theme_atom.schematic must be an object")
            else:
                view_box = schematic.get("view_box")
                if (
                    not isinstance(view_box, list)
                    or len(view_box) != 2
                    or not all(_finite_number(value) and float(value) > 0 for value in view_box)
                ):
                    errors.append("theme_atom.schematic.view_box must contain exactly two positive finite numbers")

                parts = schematic.get("parts")
                if not isinstance(parts, list) or not 2 <= len(parts) <= 12:
                    errors.append("theme_atom.schematic.parts must contain between 2 and 12 parts")
                else:
                    for index, part in enumerate(parts):
                        path = f"theme_atom.schematic.parts[{index}]"
                        if not isinstance(part, dict):
                            errors.append(f"{path} must be an object")
                            continue
                        _require_text(part, ("id", "label", "shape"), path, errors)
                        part_id = part.get("id")
                        if isinstance(part_id, str) and part_id.strip():
                            if part_id in schematic_part_ids:
                                errors.append(f"{path}.id duplicates part {part_id!r}")
                            schematic_part_ids.add(part_id)
                        shape = part.get("shape")
                        if shape not in {"rect", "circle"}:
                            errors.append(f"{path}.shape must be rect or circle")
                        coordinate_keys = ("x", "y", "width") if shape == "circle" else ("x", "y", "width", "height")
                        for key in coordinate_keys:
                            _normalized_number(part.get(key), f"{path}.{key}", errors)
                        if shape == "circle" and "height" in part:
                            _normalized_number(part.get("height"), f"{path}.height", errors)
                        role = part.get("role")
                        if role is not None and role not in {"shell", "core", "interface", "detail"}:
                            errors.append(f"{path}.role must be shell, core, interface, or detail")

                connections = schematic.get("connections")
                if connections is not None:
                    if not isinstance(connections, list):
                        errors.append("theme_atom.schematic.connections must be an array")
                    else:
                        for index, connection in enumerate(connections):
                            path = f"theme_atom.schematic.connections[{index}]"
                            if not isinstance(connection, dict):
                                errors.append(f"{path} must be an object")
                                continue
                            source, target = connection.get("from"), connection.get("to")
                            if source not in schematic_part_ids or target not in schematic_part_ids:
                                errors.append(f"{path} must connect declared parts")
                            if source is not None and source == target:
                                errors.append(f"{path} cannot connect a part to itself")

        _validate_theme_atom_production(atom, views, schematic_part_ids, errors)

    sources = data.get("sources")
    source_ids = _ids(sources, "sources", SOURCE_ID, errors)
    source_lookup = {source["id"]: source for source in sources or [] if isinstance(source, dict) and isinstance(source.get("id"), str)}
    for index, source in enumerate(sources or []):
        if not isinstance(source, dict):
            continue
        path = f"sources[{index}]"
        _require_text(source, ("title", "publisher", "date"), path, errors)
        for field in ("source_type", "accessed_at"):
            if field in source and (not isinstance(source[field], str) or not source[field].strip()):
                errors.append(f"{path}.{field} must be a non-empty string")
        classification = source.get("classification")
        if classification is not None and classification not in SOURCE_CLASSIFICATIONS:
            errors.append(f"{path}.classification must be one of {sorted(SOURCE_CLASSIFICATIONS)}")
        if schema_v2 and not isinstance(source.get("synthetic"), bool):
            errors.append(f"{path}.synthetic must be a boolean for schema @2")

    facts = data.get("facts")
    fact_ids = _ids(facts, "facts", FACT_ID, errors)
    fact_lookup = {fact["id"]: fact for fact in facts or [] if isinstance(fact, dict) and isinstance(fact.get("id"), str)}
    cited_source_ids: set[str] = set()
    synthetic_fact_ids: set[str] = set()
    for index, fact in enumerate(facts or []):
        if not isinstance(fact, dict):
            continue
        path = f"facts[{index}]"
        _require_text(fact, ("label", "display", "basis", "date", "kind"), path, errors)
        _number(fact.get("value"), f"{path}.value", errors)
        if fact.get("kind") not in FACT_KINDS:
            errors.append(f"{path}.kind must be one of {sorted(FACT_KINDS)}")
        fact_sources = fact.get("source_ids")
        _check_refs(fact_sources, source_ids, f"{path}.source_ids", errors, required=True)
        if isinstance(fact_sources, list):
            cited_source_ids.update(item for item in fact_sources if isinstance(item, str))
        _check_refs(fact.get("derived_from"), fact_ids, f"{path}.derived_from", errors)
        if fact.get("kind") == "derived" and not fact.get("derived_from"):
            errors.append(f"{path}.derived_from is required for derived facts")
        if schema_v2 and fact.get("kind") == "derived" and (not isinstance(fact.get("formula"), str) or not fact["formula"].strip()):
            errors.append(f"{path}.formula is required for derived facts in schema @2")
        if schema_v2 and not isinstance(fact.get("synthetic"), bool):
            errors.append(f"{path}.synthetic must be a boolean for schema @2")
        if fact.get("synthetic") is True:
            synthetic_fact_ids.add(fact.get("id"))
        if fact.get("kind") == "probability" and isinstance(fact.get("value"), (int, float)) and not 0 <= fact["value"] <= 1:
            errors.append(f"{path}.value must be between 0 and 1 for probability facts")
        for field in SEMANTIC_TEXT_FIELDS:
            if field in fact and (not isinstance(fact[field], str) or not fact[field].strip()):
                errors.append(f"{path}.{field} must be a non-empty string")
        precision = fact.get("precision")
        if precision is not None and not (isinstance(precision, int) and not isinstance(precision, bool) and precision >= 0):
            errors.append(f"{path}.precision must be a non-negative integer")
        formatting = fact.get("format")
        if formatting is not None:
            if not isinstance(formatting, dict):
                errors.append(f"{path}.format must be an object")
            elif formatting.get("style") == "multiplier":
                if precision is None:
                    errors.append(f"{path}.precision is required for multiplier formatting")
                elif _finite_number(fact.get("value")):
                    expected = f"×{float(fact['value']):.{precision}f}"
                    if fact.get("display") != expected:
                        errors.append(f"{path}.display must be canonical multiplier {expected!r}")
        boundary = str(fact.get("boundary", "")).lower()
        value = fact.get("value")
        if boundary == "percentage-share" and isinstance(value, (int, float)) and not 0 <= value <= 100:
            errors.append(f"{path}.value must be between 0 and 100 for percentage-share")
        if boundary == "probability" and isinstance(value, (int, float)) and not 0 <= value <= 1:
            errors.append(f"{path}.value must be between 0 and 1 for probability boundary")
        comparison = str(fact.get("comparison_basis", "")).lower()
        scope = str(fact.get("adjustment_scope", "")).lower()
        if any(token in comparison for token in ("yoy", "year-over-year", "同比")) and scope in {"current-period-only", "本期仅调整"}:
            errors.append(f"{path}.adjustment_scope is asymmetric for a year-over-year comparison")

    for source_id in cited_source_ids:
        source = source_lookup.get(source_id)
        if source:
            if schema_v2:
                _validate_locator(source.get("locator"), source, f"sources[{source_id}].locator", errors, required=True)
            elif source.get("locator") is not None and not isinstance(source.get("locator"), dict):
                errors.append(f"sources[{source_id}].locator must be an object")

    if schema_v2:
        if evidence_status == "verified" and synthetic_fact_ids:
            errors.append("verified evidence_status cannot contain synthetic facts")
        if evidence_status == "synthetic" and len(synthetic_fact_ids) != len(fact_lookup):
            errors.append("synthetic evidence_status requires every fact to set synthetic: true")
        for fact_id in synthetic_fact_ids:
            fact_sources = fact_lookup[fact_id].get("source_ids") or []
            if not any(source_lookup.get(source_id, {}).get("synthetic") is True for source_id in fact_sources):
                errors.append(f"{fact_id} is synthetic but cites no synthetic source")
        disclosure = data.get("data_disclosure")
        if evidence_status in {"mixed", "synthetic"}:
            if not isinstance(disclosure, dict):
                errors.append("data_disclosure is required for mixed or synthetic evidence")
            else:
                _require_text(disclosure, ("label", "scope"), "data_disclosure", errors)
                placements = disclosure.get("placements")
                if not isinstance(placements, list) or not {"top-banner", "package-manifest"}.issubset(set(placements)):
                    errors.append("data_disclosure.placements must include top-banner and package-manifest")

    _check_refs(data.get("kpis"), fact_ids, "kpis", errors, required=True)

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty array")
    else:
        section_ids: set[str] = set()
        chart_ids: set[str] = set()
        for index, section in enumerate(sections):
            path = f"sections[{index}]"
            if not isinstance(section, dict):
                errors.append(f"{path} must be an object")
                continue
            _require_text(section, ("id", "eyebrow", "title", "dek"), path, errors)
            if "nav_label" in section and (not isinstance(section.get("nav_label"), str) or not section["nav_label"].strip()):
                errors.append(f"{path}.nav_label must be a non-empty string")
            section_id = section.get("id")
            if section_id in section_ids:
                errors.append(f"duplicate section id: {section_id}")
            section_ids.add(section_id)
            _validate_dashboard(section.get("dashboard"), f"{path}.dashboard", fact_ids, fact_lookup, errors)
            body = section.get("body")
            if not isinstance(body, list) or not body:
                errors.append(f"{path}.body must be a non-empty array")
            else:
                for j, block in enumerate(body):
                    b = f"{path}.body[{j}]"
                    if not isinstance(block, dict) or block.get("type") not in {"paragraph", "quote", "callout"}:
                        errors.append(f"{b}.type must be paragraph, quote, or callout")
                        continue
                    _require_text(block, ("text",), b, errors)
                    if block.get("type") == "callout":
                        _require_text(block, ("title",), b, errors)
                    _check_refs(block.get("fact_ids"), fact_ids, f"{b}.fact_ids", errors)
                    _check_refs(block.get("source_ids"), source_ids, f"{b}.source_ids", errors, required=block.get("type") == "quote")
            charts = section.get("charts", [])
            if not isinstance(charts, list):
                errors.append(f"{path}.charts must be an array")
            else:
                for j, chart in enumerate(charts):
                    _validate_chart(chart, f"{path}.charts[{j}]", fact_ids, fact_lookup, source_ids, errors, schema_v2)
                    if isinstance(chart, dict):
                        chart_id = chart.get("id")
                        if chart_id in chart_ids:
                            errors.append(f"duplicate chart id: {chart_id}")
                        chart_ids.add(chart_id)

    preset = data.get("preset")
    if preset is not None and preset != EARNINGS_PRESET:
        errors.append(f"preset must be {EARNINGS_PRESET!r} when provided")
    if preset == EARNINGS_PRESET:
        checks = data.get("preset_checks")
        if not isinstance(checks, dict):
            errors.append("preset_checks must be an object for public-equity-earnings")
        else:
            missing = EARNINGS_CHECKS - set(checks)
            if missing:
                errors.append(f"preset_checks is missing required keys: {sorted(missing)}")
            for key in EARNINGS_CHECKS & set(checks):
                value = checks[key]
                if key == "falsifiers":
                    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
                        errors.append("preset_checks.falsifiers must be a non-empty array of strings")
                elif not isinstance(value, str) or not value.strip():
                    errors.append(f"preset_checks.{key} must be a non-empty string")

    methodology, disclosures = data.get("methodology"), data.get("disclosures")
    if not isinstance(methodology, list) or not methodology:
        warnings.append("methodology should contain at least one item")
    if not isinstance(disclosures, list) or not disclosures:
        warnings.append("disclosures should contain at least one item")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as validation failures")
    args = parser.parse_args()
    try:
        data = load_report(args.report)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors, warnings = validate_report(data)
    for issue in warnings:
        print(f"WARNING: {issue}")
    for issue in errors:
        print(f"ERROR: {issue}", file=sys.stderr)
    if errors or (args.strict and warnings):
        return 1
    print(f"OK: {args.report} ({len(data.get('facts', []))} facts, {len(data.get('sources', []))} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
