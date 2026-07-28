#!/usr/bin/env python3
"""Build offline multi-file and single-file research websites from report JSON."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import mimetypes
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_report import load_report, validate_report


SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "site"
DEFAULT_MAX_IMAGE_BYTES = 2_500_000
DEFAULT_MAX_SINGLE_FILE_BYTES = 10_000_000
DEFAULT_MAX_IMAGE_DIMENSION = 2000
DEFAULT_WEBP_QUALITY = 82


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _copy_or_optimize_image(
    source: Path,
    assets_dir: Path,
    stem: str,
    max_dimension: int,
    webp_quality: int,
) -> tuple[Path, str]:
    """Copy an asset, preferring a smaller or resized WebP when Pillow is available."""
    suffix = source.suffix.lower() or ".bin"
    fallback = assets_dir / f"{stem}{suffix}"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        shutil.copy2(source, fallback)
        return fallback, "copied"
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError:
        shutil.copy2(source, fallback)
        return fallback, "copied-pillow-unavailable"

    destination = assets_dir / f"{stem}.webp"
    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            original_size = image.size
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            resized = image.size != original_size
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.save(destination, "WEBP", quality=webp_quality, method=6)
        if resized or destination.stat().st_size < source.stat().st_size:
            return destination, "webp-resized" if resized else "webp-compressed"
        destination.unlink(missing_ok=True)
    except (OSError, ValueError):
        destination.unlink(missing_ok=True)
    shutil.copy2(source, fallback)
    return fallback, "copied"


def _prepare_assets(
    report: dict[str, Any],
    report_path: Path,
    site_dir: Path,
    max_dimension: int,
    webp_quality: int,
    max_image_bytes: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    multi = copy.deepcopy(report)
    single = copy.deepcopy(report)
    multi_views = multi.get("theme_atom", {}).get("views", [])
    single_views = single.get("theme_atom", {}).get("views", [])
    records: list[dict[str, Any]] = []
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for index, view in enumerate(report.get("theme_atom", {}).get("views", [])):
        raw_asset = view.get("asset") if isinstance(view, dict) else None
        source = (report_path.parent / raw_asset).resolve() if raw_asset else None
        if source and source.is_file():
            destination, optimization = _copy_or_optimize_image(
                source, assets_dir, f"cover-{view['id']}", max_dimension, webp_quality
            )
            built_bytes = destination.stat().st_size
            multi_views[index]["asset"] = f"assets/{destination.name}"
            multi_views[index]["asset_status"] = "provided"
            single_views[index]["asset"] = _data_uri(destination)
            single_views[index]["asset_status"] = "embedded"
            records.append({
                "view_id": view["id"],
                "source": str(source),
                "path": f"site/assets/{destination.name}",
                "original_bytes": source.stat().st_size,
                "bytes": built_bytes,
                "optimization": optimization,
                "within_budget": built_bytes <= max_image_bytes,
            })
        else:
            multi_views[index].pop("asset", None)
            single_views[index].pop("asset", None)
            multi_views[index]["asset_status"] = "schematic"
            single_views[index]["asset_status"] = "schematic"
    return multi, single, records


def _safe_script_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _replace_exactly_once(text: str, needle: str, replacement: str, label: str) -> str:
    count = text.count(needle)
    if count != 1:
        raise ValueError(f"template placeholder {label!r} occurred {count} times; expected exactly once")
    return text.replace(needle, replacement, 1)


def _localized_shell(template: str, report: dict[str, Any]) -> str:
    language = str(report.get("meta", {}).get("language", "en-US"))
    chinese = language.lower().startswith("zh")
    defaults = {
        "skip_to_report": "跳至报告正文" if chinese else "Skip to report",
        "close_drawer": "关闭证据抽屉" if chinese else "Close evidence drawer",
        "close": "关闭" if chinese else "Close",
        "javascript_required": "请启用 JavaScript 以使用图表与证据钻取。" if chinese else "Enable JavaScript to use charts and evidence drilldowns.",
    }
    defaults.update({key: value for key, value in (report.get("ui_labels") or {}).items() if key in defaults})
    title = str(report.get("meta", {}).get("title", "Visual Research Report"))
    return (
        template.replace('<html lang="zh-CN">', f'<html lang="{html.escape(language, quote=True)}">')
        .replace("<title>Visual Research Report</title>", f"<title>{html.escape(title)}</title>")
        .replace(">Skip to report</a>", f">{html.escape(defaults['skip_to_report'])}</a>")
        .replace('aria-label="Close evidence drawer"', f'aria-label="{html.escape(defaults["close_drawer"], quote=True)}"')
        .replace(">Close ×</button>", f">{html.escape(defaults['close'])} ×</button>")
        .replace(">This report requires JavaScript for charts and evidence drilldowns.</noscript>", f">{html.escape(defaults['javascript_required'])}</noscript>")
    )


def build(
    report_path: Path,
    output_dir: Path,
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    max_single_file_bytes: int = DEFAULT_MAX_SINGLE_FILE_BYTES,
    max_image_dimension: int = DEFAULT_MAX_IMAGE_DIMENSION,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
) -> None:
    report = load_report(report_path)
    errors, warnings = validate_report(report)
    for issue in warnings:
        print(f"WARNING: {issue}")
    if errors:
        for issue in errors:
            print(f"ERROR: {issue}", file=sys.stderr)
        raise ValueError("report validation failed")
    if not TEMPLATE_DIR.is_dir():
        raise ValueError(f"template directory not found: {TEMPLATE_DIR}")
    if min(max_image_bytes, max_single_file_bytes, max_image_dimension, webp_quality) <= 0:
        raise ValueError("resource-budget values must be positive")

    site_dir = output_dir / "site"
    data_dir = site_dir / "data"
    site_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in ("styles.css", "app.js"):
        shutil.copy2(TEMPLATE_DIR / name, site_dir / name)

    multi, single, asset_records = _prepare_assets(
        report, report_path, site_dir, max_image_dimension, webp_quality, max_image_bytes
    )
    (data_dir / "report-data.js").write_text(
        "window.REPORT_DATA=" + _safe_script_json(multi) + ";\n", encoding="utf-8"
    )

    index_html = _localized_shell((TEMPLATE_DIR / "index.html").read_text(encoding="utf-8"), report)
    (site_dir / "index.html").write_text(index_html, encoding="utf-8")
    css = (TEMPLATE_DIR / "styles.css").read_text(encoding="utf-8")
    js = (TEMPLATE_DIR / "app.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    single_html = _replace_exactly_once(
        index_html, '<link rel="stylesheet" href="styles.css">', f"<style>\n{css}\n</style>", "stylesheet"
    )
    single_html = _replace_exactly_once(
        single_html,
        '<script src="data/report-data.js"></script>',
        f"<script>window.REPORT_DATA={_safe_script_json(single)};</script>",
        "report data",
    )
    single_html = _replace_exactly_once(
        single_html, '<script src="app.js"></script>', f"<script>\n{js}\n</script>", "application JavaScript"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    single_path = output_dir / "report.html"
    single_path.write_text(single_html, encoding="utf-8")
    report_json_path = output_dir / "report.json"
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for record in asset_records:
        if not record["within_budget"]:
            print(f"WARNING: {record['path']} is {record['bytes']} bytes (budget {max_image_bytes})")
    if single_path.stat().st_size > max_single_file_bytes:
        print(f"WARNING: report.html is {single_path.stat().st_size} bytes (budget {max_single_file_bytes})")

    files = sorted(
        [site_dir / "index.html", site_dir / "styles.css", site_dir / "app.js", data_dir / "report-data.js", single_path, report_json_path]
        + [path for path in (site_dir / "assets").rglob("*") if path.is_file()]
    )
    disclosure = report.get("data_disclosure") if isinstance(report.get("data_disclosure"), dict) else None
    manifest = {
        "schema": "visual-research-report/build-manifest@2",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "state": "built",
        "source": {"name": report_path.name, "sha256": _sha256(report_path)},
        "title": report.get("meta", {}).get("title"),
        "report_schema": report.get("schema"),
        "evidence_status": report.get("evidence_status"),
        "data_disclosure": disclosure if disclosure and "package-manifest" in disclosure.get("placements", []) else None,
        "artifacts": {
            "site": "site/index.html",
            "single_file": "report.html",
            "data_contract": "report.json",
            "pdf": None,
            "browser_qa": [],
        },
        "resource_budget": {
            "max_image_bytes": max_image_bytes,
            "max_single_file_bytes": max_single_file_bytes,
            "max_image_dimension": max_image_dimension,
            "webp_quality": webp_quality,
            "single_file_bytes": single_path.stat().st_size,
            "assets": asset_records,
        },
        "files": [
            {"path": str(path.relative_to(output_dir)), "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in files
        ],
    }
    (output_dir / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Built multi-file site: {site_dir / 'index.html'}")
    print(f"Built single-file report: {single_path}")
    print(f"Built data contract: {report_json_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-image-bytes", type=int, default=DEFAULT_MAX_IMAGE_BYTES)
    parser.add_argument("--max-single-file-bytes", type=int, default=DEFAULT_MAX_SINGLE_FILE_BYTES)
    parser.add_argument("--max-image-dimension", type=int, default=DEFAULT_MAX_IMAGE_DIMENSION)
    parser.add_argument("--webp-quality", type=int, default=DEFAULT_WEBP_QUALITY)
    args = parser.parse_args()
    try:
        build(
            args.report.resolve(), args.output.resolve(), args.max_image_bytes,
            args.max_single_file_bytes, args.max_image_dimension, args.webp_quality,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
