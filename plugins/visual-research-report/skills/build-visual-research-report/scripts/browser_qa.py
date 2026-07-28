#!/usr/bin/env python3
"""Run real-browser responsive and interaction QA through the Playwright CLI wrapper."""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WRAPPER = Path.home() / ".codex" / "skills" / "playwright" / "scripts" / "playwright_cli.sh"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


def _run(wrapper: Path, session: str, command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(wrapper), "--session", session, *command],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def browser_qa(output: Path, wrapper: Path, artifacts: Path) -> None:
    if not (output / "site/index.html").is_file() or not (output / "report.html").is_file():
        raise ValueError("output must contain site/index.html and report.html")
    if not wrapper.is_file():
        raise ValueError(f"Playwright CLI wrapper not found: {wrapper}")
    if not shutil.which("npx"):
        raise ValueError("npx is required by the Playwright CLI wrapper")

    artifacts.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(QuietHandler, directory=str(output))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = f"vrr-qa-{os.getpid()}"
    base_url = f"http://127.0.0.1:{server.server_port}"
    env = os.environ.copy()
    env["npm_config_cache"] = str(Path(tempfile.gettempdir()) / "codex-npm-cache")
    env["PWTEST_DAEMON_SESSION_DIR"] = str(Path(tempfile.gettempdir()) / "vrr-playwright-daemon")
    code = (SCRIPT_DIR / "browser_qa.js").read_text(encoding="utf-8")
    code = code.replace("__BASE_URL__", json.dumps(base_url)).replace("__ARTIFACT_DIR__", json.dumps(str(artifacts.resolve())))
    try:
        opened = _run(wrapper, session, ["open", f"{base_url}/site/index.html"], env)
        if opened.returncode:
            raise ValueError(f"Playwright open failed: {opened.stderr.strip() or opened.stdout.strip()}")
        result = _run(wrapper, session, ["run-code", code], env)
        combined = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        failed = "### Error" in combined
        success = re.search(r'\{"ok":true,"checks":(?P<checks>\d+),"screenshots":(?P<screenshots>\d+)\}', combined)
        if failed or not success:
            raise ValueError(f"browser assertions failed: {combined or f'CLI exit {result.returncode}'}")
        print(f"Playwright result: {success.group(0)}")
        (output / "qa-results.json").write_text(json.dumps({
            "schema": "visual-research-report/browser-qa@1",
            "status": "passed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "checks": int(success.group("checks")),
            "screenshots": int(success.group("screenshots")),
            "viewports": ["1440x1000", "1024x900", "390x844"],
            "targets": ["site/index.html", "report.html"],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        _run(wrapper, session, ["close"], env)
        server.shutdown()
        server.server_close()
    print(f"OK: browser QA passed; screenshots: {artifacts.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--playwright-cli", type=Path, default=DEFAULT_WRAPPER)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    artifacts = args.artifacts.resolve() if args.artifacts else output / "browser-qa"
    try:
        browser_qa(output, args.playwright_cli.resolve(), artifacts)
    except ValueError as exc:
        output.mkdir(parents=True, exist_ok=True)
        (output / "qa-results.json").write_text(json.dumps({
            "schema": "visual-research-report/browser-qa@1",
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "checks": 0,
            "screenshots": 0,
            "detail": str(exc),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
