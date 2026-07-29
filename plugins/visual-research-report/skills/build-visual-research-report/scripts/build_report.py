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
from pathlib import Path, PureWindowsPath
from typing import Any

from validate_report import load_report, validate_report


SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "site"
DEFAULT_MAX_IMAGE_BYTES = 2_500_000
DEFAULT_MAX_COVER_BYTES = 6_000_000
DEFAULT_MAX_SINGLE_FILE_BYTES = 10_000_000
DEFAULT_MAX_IMAGE_DIMENSION = 2000
DEFAULT_WEBP_QUALITY = 82
COVER_VIEW_IDS = ("recursive", "exploded", "blueprint", "impact")
SUPPORTED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _data_uri(path: Path, mime: str | None = None) -> str:
    mime = mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_report_asset(report_root: Path, raw_asset: Any, label: str) -> Path:
    if not isinstance(raw_asset, str) or not raw_asset.strip() or "\x00" in raw_asset:
        raise ValueError(f"{label} must be a non-empty report-relative path")
    relative = Path(raw_asset)
    if relative.is_absolute() or PureWindowsPath(raw_asset).is_absolute():
        raise ValueError(f"{label} must be report-relative, not absolute")
    source = (report_root / relative).resolve()
    if not _inside(report_root, source):
        raise ValueError(f"{label} escapes the report directory")
    return source


def _inspect_image(path: Path, label: str, required: bool) -> dict[str, Any] | None:
    """Decode an image and return normalized metadata; strict modes require Pillow."""
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError as exc:
        if required:
            raise ValueError(f"{label} cannot be verified because Pillow is unavailable") from exc
        return None

    try:
        with Image.open(path) as opened:
            image_format = str(opened.format or "").upper()
            frame_count = int(getattr(opened, "n_frames", 1))
            opened.verify()
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
            width, height = image.size
    except (OSError, SyntaxError, ValueError) as exc:
        if required:
            raise ValueError(f"{label} is not a decodable raster image: {exc}") from exc
        return None

    if image_format not in SUPPORTED_IMAGE_FORMATS:
        if required:
            raise ValueError(
                f"{label} decoded as unsupported {image_format or 'unknown'}; expected PNG, JPEG, or WebP"
            )
        return None
    if frame_count != 1:
        if required:
            raise ValueError(f"{label} must be a static image, not a {frame_count}-frame image")
        return None
    if width <= 0 or height <= 0:
        if required:
            raise ValueError(f"{label} has invalid decoded dimensions {width}x{height}")
        return None
    mime = Image.MIME.get(image_format) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "format": image_format.lower(),
        "mime_type": mime,
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 6),
        "orientation": "square" if width == height else ("landscape" if width > height else "portrait"),
        "frames": frame_count,
    }


def _clean_stale_cover_assets(assets_dir: Path) -> None:
    """A rebuilt package must not retain cover files from an earlier render."""
    for path in assets_dir.glob("cover-*"):
        if path.is_file() or path.is_symlink():
            path.unlink()


def _copy_or_optimize_image(
    source: Path,
    assets_dir: Path,
    stem: str,
    max_dimension: int,
    webp_quality: int,
    force_webp: bool = False,
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
        if force_webp or resized or destination.stat().st_size < source.stat().st_size:
            strategy = "webp-resized" if resized else ("webp-delivery" if force_webp else "webp-compressed")
            return destination, strategy
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
    max_cover_bytes: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    multi = copy.deepcopy(report)
    single = copy.deepcopy(report)
    theme_atom = report.get("theme_atom", {}) if isinstance(report.get("theme_atom"), dict) else {}
    production = theme_atom.get("production") if isinstance(theme_atom.get("production"), dict) else None
    production_mode = str(production.get("mode")) if production and production.get("mode") else "legacy"
    if production_mode not in {"legacy", "image-2", "provided", "schematic"}:
        raise ValueError(f"unsupported theme_atom.production.mode: {production_mode}")
    image_two = production_mode == "image-2"
    assets_required = production_mode in {"image-2", "provided"}
    source_views = theme_atom.get("views", []) if isinstance(theme_atom.get("views"), list) else []
    multi_views = multi.get("theme_atom", {}).get("views", [])
    single_views = single.get("theme_atom", {}).get("views", [])
    records: list[dict[str, Any]] = []
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    _clean_stale_cover_assets(assets_dir)

    anchor_record: dict[str, Any] | None = None
    if image_two:
        if not production:
            raise ValueError("theme_atom.production is required in image-2 mode")
        if production.get("model") != "gpt-image-2":
            raise ValueError("image-2 mode requires theme_atom.production.model='gpt-image-2'")
        if production.get("workflow") != "canonical-anchor-plus-direct-edits":
            raise ValueError(
                "image-2 mode requires theme_atom.production.workflow='canonical-anchor-plus-direct-edits'"
            )
        if production.get("master_format") != "png":
            raise ValueError("image-2 mode requires theme_atom.production.master_format='png'")
        if production.get("delivery_format") != "webp":
            raise ValueError("image-2 mode requires theme_atom.production.delivery_format='webp'")
        anchor_source = _resolve_report_asset(
            report_path.parent, production.get("anchor_asset"), "theme_atom.production.anchor_asset"
        )
        if not anchor_source.is_file():
            raise ValueError("theme_atom.production.anchor_asset does not resolve to a file")
        anchor_image = _inspect_image(anchor_source, "theme_atom.production.anchor_asset", required=True)
        assert anchor_image is not None
        if anchor_image["format"] != "png":
            raise ValueError("theme_atom.production.anchor_asset must decode as the declared PNG master format")
        canvas = production.get("canvas")
        if not isinstance(canvas, dict) or (
            canvas.get("width"), canvas.get("height")
        ) != (anchor_image["width"], anchor_image["height"]):
            raise ValueError("theme_atom.production.canvas must match the decoded canonical anchor dimensions")
        anchor_record = {
            "sha256": _sha256(anchor_source),
            "bytes": anchor_source.stat().st_size,
            "image": anchor_image,
        }

    if image_two:
        ids = [view.get("id") for view in source_views if isinstance(view, dict)]
        if len(ids) != 4 or set(ids) != set(COVER_VIEW_IDS):
            raise ValueError("image-2 mode requires exactly recursive, exploded, blueprint, and impact views")

    for index, view in enumerate(source_views):
        raw_asset = view.get("asset") if isinstance(view, dict) else None
        view_id = str(view.get("id", index)) if isinstance(view, dict) else str(index)
        if production_mode == "schematic":
            multi_views[index].pop("asset", None)
            single_views[index].pop("asset", None)
            multi_views[index]["asset_status"] = "schematic"
            single_views[index]["asset_status"] = "schematic"
            continue
        source = _resolve_report_asset(
            report_path.parent, raw_asset, f"theme_atom.views[{index}].asset"
        ) if raw_asset else None
        if source and source.is_file():
            source_image = _inspect_image(
                source, f"theme_atom.views[{index}].asset", required=assets_required
            )
            if image_two and source_image and source_image["format"] != "png":
                raise ValueError(f"image-2 source view {view_id} must decode as the declared PNG master format")
            destination, optimization = _copy_or_optimize_image(
                source, assets_dir, f"cover-{view_id}", max_dimension, webp_quality,
                force_webp=image_two,
            )
            built_image = _inspect_image(
                destination, f"built cover asset for {view_id}", required=assets_required
            )
            if image_two and built_image and built_image["format"] != "webp":
                raise ValueError(f"image-2 built view {view_id} must decode as the declared WebP delivery format")
            built_bytes = destination.stat().st_size
            built_mime = built_image.get("mime_type") if built_image else None
            embedded = _data_uri(destination, built_mime)
            source_sha256 = _sha256(source)
            generation_record: dict[str, Any] | None = None
            if image_two:
                generation = view.get("generation") if isinstance(view, dict) else None
                if not isinstance(generation, dict):
                    raise ValueError(f"image-2 view {view_id} is missing generation provenance")
                assert anchor_record is not None
                if generation.get("input_asset_sha256") != anchor_record["sha256"]:
                    raise ValueError(f"image-2 view {view_id} input hash does not match the canonical anchor")
                if generation.get("output_asset_sha256") != source_sha256:
                    raise ValueError(f"image-2 view {view_id} output hash does not match its decoded source master")
                generation_record = {
                    key: generation.get(key)
                    for key in (
                        "operation", "prompt_id", "invariants", "qa_status", "generated_at",
                        "input_asset_sha256", "output_asset_sha256",
                    )
                    if generation.get(key) is not None
                }
            multi_views[index]["asset"] = f"assets/{destination.name}"
            multi_views[index]["asset_status"] = "generated-image-2" if image_two else "provided"
            single_views[index]["asset"] = embedded
            single_views[index]["asset_status"] = "embedded"
            records.append({
                "view_id": view_id,
                "role": "cover-view",
                "path": f"site/assets/{destination.name}",
                "source_sha256": source_sha256,
                "built_sha256": _sha256(destination),
                "original_bytes": source.stat().st_size,
                "bytes": built_bytes,
                "embedded_data_uri_bytes": len(embedded.encode("utf-8")),
                "source_image": source_image,
                "built_image": built_image,
                "optimization": optimization,
                "within_budget": built_bytes <= max_image_bytes,
                "generation": generation_record,
            })
        else:
            if assets_required:
                raise ValueError(f"theme_atom.views[{index}].asset is required and must resolve to a file")
            multi_views[index].pop("asset", None)
            single_views[index].pop("asset", None)
            multi_views[index]["asset_status"] = "schematic"
            single_views[index]["asset_status"] = "schematic"

    total_cover_bytes = sum(record["bytes"] for record in records)
    total_embedded_bytes = sum(record["embedded_data_uri_bytes"] for record in records)
    for record in records:
        record["within_total_budget"] = total_cover_bytes <= max_cover_bytes

    cover_set: dict[str, Any] = {
        "mode": production_mode,
        "view_ids": [record["view_id"] for record in records],
        "view_count": len(records),
        "total_cover_bytes": total_cover_bytes,
        "total_embedded_data_uri_bytes": total_embedded_bytes,
        "unique_source_hashes": len({record["source_sha256"] for record in records}),
        "unique_built_hashes": len({record["built_sha256"] for record in records}),
    }
    if production:
        cover_set["generator"] = {
            key: production.get(key)
            for key in (
                "model", "engine", "workflow", "prompt_version", "generated_at",
                "master_format", "delivery_format", "canvas",
            )
            if production.get(key) is not None
        }
    if anchor_record:
        cover_set["canonical_anchor"] = anchor_record
        source_hashes = [anchor_record["sha256"], *(record["source_sha256"] for record in records)]
        built_hashes = [record["built_sha256"] for record in records]
        if len(set(source_hashes)) != 5:
            raise ValueError("image-2 canonical anchor and four view source assets must have distinct hashes")
        if len(set(built_hashes)) != 4:
            raise ValueError("image-2 built cover views must have distinct hashes")
        anchor_dimensions = (
            anchor_record["image"]["width"], anchor_record["image"]["height"]
        )
        for record in records:
            source_image = record.get("source_image") or {}
            if (source_image.get("width"), source_image.get("height")) != anchor_dimensions:
                raise ValueError(
                    f"image-2 view {record['view_id']} dimensions must match canonical anchor "
                    f"{anchor_dimensions[0]}x{anchor_dimensions[1]}"
                )
            if record["bytes"] > max_image_bytes:
                raise ValueError(
                    f"image-2 view {record['view_id']} exceeds per-image budget of {max_image_bytes} bytes"
                )
        if total_cover_bytes > max_cover_bytes:
            raise ValueError(
                f"image-2 cover assets total {total_cover_bytes} bytes; budget is {max_cover_bytes} bytes"
            )
    return multi, single, records, cover_set


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
    max_cover_bytes: int = DEFAULT_MAX_COVER_BYTES,
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
    if min(max_image_bytes, max_cover_bytes, max_single_file_bytes, max_image_dimension, webp_quality) <= 0:
        raise ValueError("resource-budget values must be positive")

    site_dir = output_dir / "site"
    data_dir = site_dir / "data"
    site_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in ("styles.css", "app.js"):
        shutil.copy2(TEMPLATE_DIR / name, site_dir / name)

    multi, single, asset_records, cover_set = _prepare_assets(
        report, report_path, site_dir, max_image_dimension, webp_quality, max_image_bytes,
        max_cover_bytes,
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
    single_file_bytes = len(single_html.encode("utf-8"))
    if cover_set["mode"] == "image-2" and single_file_bytes > max_single_file_bytes:
        raise ValueError(
            f"image-2 report.html would be {single_file_bytes} bytes; budget is {max_single_file_bytes} bytes"
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
            "max_cover_bytes": max_cover_bytes,
            "max_single_file_bytes": max_single_file_bytes,
            "max_image_dimension": max_image_dimension,
            "webp_quality": webp_quality,
            "single_file_bytes": single_path.stat().st_size,
            "cover_bytes": cover_set["total_cover_bytes"],
            "cover_embedded_data_uri_bytes": cover_set["total_embedded_data_uri_bytes"],
            "cover_asset_set": cover_set,
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
    parser.add_argument("--max-cover-bytes", type=int, default=DEFAULT_MAX_COVER_BYTES)
    parser.add_argument("--max-single-file-bytes", type=int, default=DEFAULT_MAX_SINGLE_FILE_BYTES)
    parser.add_argument("--max-image-dimension", type=int, default=DEFAULT_MAX_IMAGE_DIMENSION)
    parser.add_argument("--webp-quality", type=int, default=DEFAULT_WEBP_QUALITY)
    args = parser.parse_args()
    try:
        build(
            args.report.resolve(), args.output.resolve(), args.max_image_bytes,
            args.max_single_file_bytes, args.max_image_dimension, args.webp_quality,
            args.max_cover_bytes,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
