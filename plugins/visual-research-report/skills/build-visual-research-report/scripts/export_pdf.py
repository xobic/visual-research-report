#!/usr/bin/env python3
"""Export report.html to PDF with an installed Chromium-family browser."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


MAC_BROWSERS = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
)


def _find_browser(explicit: Path | None) -> Path | None:
    if explicit:
        return explicit if explicit.is_file() else None
    for candidate in MAC_BROWSERS:
        if candidate.is_file():
            return candidate
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)
    return None


def export_pdf(output: Path, browser: Path | None, optional: bool) -> dict[str, object]:
    html_path = output / "report.html"
    pdf_path = output / "report.pdf"
    status_path = output / "pdf-export.json"
    if not html_path.is_file():
        raise ValueError("report.html is missing; run build_report.py first")
    selected = _find_browser(browser)
    result: dict[str, object] = {
        "attempted_at": datetime.now(timezone.utc).isoformat(),
        "status": "skipped",
        "engine": str(selected) if selected else None,
        "artifact": None,
    }
    if selected is None:
        status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if optional:
            return result
        raise ValueError("no supported Chromium-family browser was found")

    with tempfile.TemporaryDirectory(prefix="vrr-pdf-") as profile:
        temporary_pdf = Path(profile) / "report.pdf"
        command = [
            str(selected), "--headless=new", "--disable-gpu", "--no-first-run",
            f"--user-data-dir={profile}", "--virtual-time-budget=4000",
            "--no-pdf-header-footer", f"--print-to-pdf={temporary_pdf}", html_path.resolve().as_uri(),
        ]
        timed_out = False
        terminated_after_write = False
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 60
        last_size = -1
        stable_checks = 0
        while process.poll() is None and time.monotonic() < deadline:
            if temporary_pdf.is_file() and temporary_pdf.stat().st_size > 1024:
                size = temporary_pdf.stat().st_size
                stable_checks = stable_checks + 1 if size == last_size else 0
                last_size = size
                if stable_checks >= 5 and temporary_pdf.read_bytes()[:5] == b"%PDF-":
                    terminated_after_write = True
                    process.terminate()
                    break
            time.sleep(0.2)
        if process.poll() is None:
            timed_out = True
            process.kill()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        valid_pdf = temporary_pdf.is_file() and temporary_pdf.read_bytes().startswith(b"%PDF-")
        if valid_pdf:
            shutil.copy2(temporary_pdf, pdf_path)
    if not valid_pdf or (process.returncode and not terminated_after_write):
        result["status"] = "skipped" if optional else "failed"
        detail = "browser timed out before writing a complete PDF" if timed_out else (stderr or stdout or "PDF artifact missing")
        result["detail"] = str(detail).strip()[-1000:]
        result["reason"] = "browser-environment-unavailable" if optional else "pdf-export-failed"
        status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if optional:
            return result
        raise ValueError(f"PDF export failed: {result['detail']}")
    result.update({"status": "passed", "artifact": "report.pdf", "bytes": pdf_path.stat().st_size})
    if terminated_after_write:
        result["detail"] = "Browser process was stopped after the PDF file stabilized; the complete artifact was retained."
    status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--optional", action="store_true")
    args = parser.parse_args()
    try:
        result = export_pdf(args.output.resolve(), args.browser.resolve() if args.browser else None, args.optional)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"PDF export: {result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
