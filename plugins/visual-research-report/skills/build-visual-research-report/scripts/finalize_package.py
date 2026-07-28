#!/usr/bin/env python3
"""Finalize a Visual Research Report manifest after QA and optional PDF export."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def finalize(output: Path, require_design_qa: bool = False) -> dict[str, Any]:
    manifest_path = output / "build-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("build-manifest.json is missing; run build_report.py first")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid build manifest: {exc}") from exc
    for required in ("site/index.html", "report.html", "report.json"):
        if not (output / required).is_file():
            raise ValueError(f"required artifact is missing: {required}")
    if require_design_qa and not (output / "design-qa.md").is_file():
        raise ValueError("design-qa.md is required for this reference-led package")

    files = []
    for path in sorted(item for item in output.rglob("*") if item.is_file() and item != manifest_path):
        if not _inside(output, path):
            raise ValueError(f"artifact escapes output directory: {path}")
        relative = path.relative_to(output).as_posix()
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})

    browser_assets = [entry["path"] for entry in files if entry["path"].startswith("browser-qa/")]
    artifacts = {
        "site": "site/index.html",
        "single_file": "report.html",
        "data_contract": "report.json",
        "pdf": "report.pdf" if (output / "report.pdf").is_file() else None,
        "browser_qa": browser_assets,
        "design_qa": "design-qa.md" if (output / "design-qa.md").is_file() else None,
    }
    qa: dict[str, Any] = {"results": None, "pdf_export": None}
    for name, key in (("qa-results.json", "results"), ("pdf-export.json", "pdf_export")):
        path = output / name
        if path.is_file():
            try:
                qa[key] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid {name}: {exc}") from exc

    manifest.update({
        "schema": "visual-research-report/build-manifest@2",
        "state": "finalized",
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
        "qa": qa,
        "files": files,
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-design-qa", action="store_true")
    args = parser.parse_args()
    try:
        manifest = finalize(args.output.resolve(), args.require_design_qa)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: finalized {len(manifest['files'])} artifacts in {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
