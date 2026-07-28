#!/usr/bin/env python3
"""Validate the Visual Research Report JSON contract with no third-party packages."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable


SOURCE_ID = re.compile(r"^S\d{2,}$")
FACT_ID = re.compile(r"^F\d{2,}$")
CHART_TYPES = {
    "entity-ramp", "destiny-flow", "timeline", "matrix-heat",
    "value-stack", "odds-board", "line", "paired-bars", "tension-balance",
}
FACT_KINDS = {"reported", "estimate", "derived", "scenario", "threshold", "probability"}
COVER_VIEWS = {"recursive", "exploded", "blueprint", "impact"}
STACK_ENCODINGS = {"absolute", "share"}
SOURCE_CLASSIFICATIONS = {"primary", "secondary"}
CURRENT_SCHEMA = "visual-research-report@2"
PRESENTATION_PRESETS = {"institutional-rail", "editorial-longform"}
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


def _number(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"{path} must be numeric")


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


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
            section_id = section.get("id")
            if section_id in section_ids:
                errors.append(f"duplicate section id: {section_id}")
            section_ids.add(section_id)
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
