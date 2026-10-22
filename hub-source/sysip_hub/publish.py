"""Build and publish the System IP Design Hub to GitHub Pages.

The command is intentionally stdlib-only so it can run with the bundled Python:

    python publish.py

Use ``--no-push`` to validate and build without committing or pushing.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

if __package__:
    from .public_source import SNAPSHOT_NAME, SOURCE_FOLDER, deploy_repo, source_files, sync_public_source, validate_public_assets
else:
    from public_source import SNAPSHOT_NAME, SOURCE_FOLDER, deploy_repo, source_files, sync_public_source, validate_public_assets


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DEPLOY_REPO = deploy_repo(PROJECT_ROOT)
EXPORT_DIR = DEPLOY_REPO / "system-ip-hub"
SERVER_URL = "http://127.0.0.1:8765"
BASE_PATH = "/chip-design/system-ip-hub"


def log(message: str) -> None:
    print(f"\n==> {message}")


def run(command: list[str], cwd: Path | None = None, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")
    return result


def server_is_ready() -> bool:
    try:
        with urlopen(SERVER_URL + "/api/health", timeout=1) as response:
            health = json.loads(response.read())
            if Path(health["asset_root"]).resolve() != (ROOT / "assets").resolve():
                raise RuntimeError("Port 8765 belongs to a different asset root; stop that service before publishing")
            return response.status == 200
    except (OSError, URLError):
        return False


def start_server_if_needed() -> subprocess.Popen[str] | None:
    if server_is_ready():
        print("Local service is already running.")
        return None

    log("Starting local service")
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "start_system_ip_hub.py")],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    for _ in range(40):
        if server_is_ready():
            print("Local service is ready.")
            return process
        if process.poll() is not None:
            raise RuntimeError("Local service exited before becoming ready.")
        time.sleep(0.25)
    process.terminate()
    raise RuntimeError("Timed out waiting for the local service at http://127.0.0.1:8765")


def run_tests() -> None:
    log("Running Python compile check")
    run([sys.executable, "-m", "py_compile", "system_ip_hub/app.py", "system_ip_hub/catalog.py", "system_ip_hub/rtl_importer.py"] , ROOT)
    log("Running unit tests")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], PROJECT_ROOT)


def export_static_site() -> None:
    log("Generating GitHub Pages snapshot")
    with urlopen(SERVER_URL + "/api/assets", timeout=10) as response:
        validate_public_assets(PROJECT_ROOT, json.loads(response.read()))
    # This directory is generated output only. Source RTL, metadata, and the
    # local database live elsewhere and are not touched by this cleanup.
    if EXPORT_DIR.exists():
        if EXPORT_DIR.resolve() != DEPLOY_REPO.resolve() / "system-ip-hub" or EXPORT_DIR.is_symlink() or getattr(EXPORT_DIR, "is_junction", lambda: False)():
            raise RuntimeError("Unsafe static export target")
        shutil.rmtree(EXPORT_DIR)
    run([sys.executable, str(ROOT / "build_github_pages.py")], ROOT)
    if not (EXPORT_DIR / "index.html").exists():
        raise RuntimeError("Static export did not produce system-ip-hub/index.html")


class StaticPageLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for name in ("href", "action", "src"):
            if values.get(name):
                self.links.append(str(values[name]))
        if tag == "form" and str(values.get("method", "get")).lower() != "get":
            self.errors.append("Public snapshot contains a form requiring a server")
        if "local-only" in (values.get("class") or "").split():
            self.errors.append("Public snapshot still contains a local-only control")


def check_static_links(export_dir: Path | None = None) -> None:
    log("Checking static page links")
    export_dir = export_dir or EXPORT_DIR
    html_files = list(export_dir.rglob("*.html"))
    missing: list[str] = []
    for page in html_files:
        parser = StaticPageLinks()
        parser.feed(page.read_text(encoding="utf-8"))
        missing.extend(f"{page.relative_to(export_dir)} -> {error}" for error in parser.errors)
        for link in parser.links:
            path = unquote(urlsplit(link).path)
            if path != BASE_PATH and not path.startswith(BASE_PATH + "/"):
                continue
            relative = path[len(BASE_PATH):].strip("/")
            target = export_dir / relative
            if not target.is_file():
                target = target / "index.html"
            if not target.exists():
                missing.append(f"{page.relative_to(export_dir)} -> {link}")
    if missing:
        print("Missing static links:")
        print("\n".join(missing[:20]))
        raise RuntimeError(f"Found {len(missing)} missing static links")
    print(f"Checked {len(html_files)} HTML pages; no missing local links found.")


def git_publish(message: str, push: bool) -> None:
    if not DEPLOY_REPO.exists():
        raise RuntimeError(f"Deployment repository not found: {DEPLOY_REPO}")

    log("Checking Git changes")
    run(["git", "diff", "--check"], DEPLOY_REPO)
    status = run(["git", "status", "--short"], DEPLOY_REPO).stdout.strip()
    if not status:
        print("No changes to publish.")
        return
    print(status)

    if not push:
        print("--no-push specified; leaving changes uncommitted.")
        return

    log("Committing public source and generated site")
    run(["git", "add", "--all", "--", "system-ip-hub"], DEPLOY_REPO)
    paths = [f"{SOURCE_FOLDER}/{name}" for name in source_files(PROJECT_ROOT)]
    paths.append(f"{SOURCE_FOLDER}/{SNAPSHOT_NAME}")
    run(["git", "add", "--", *paths], DEPLOY_REPO)
    run(["git", "add", "--update", "--", SOURCE_FOLDER], DEPLOY_REPO)
    run(["git", "commit", "-m", message], DEPLOY_REPO)
    log("Pushing to GitHub")
    run(["git", "push", "origin", "main"], DEPLOY_REPO)
    remote = run(["git", "rev-parse", "HEAD"], DEPLOY_REPO).stdout.strip()
    print(f"Published commit: {remote}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish System IP Design Hub")
    parser.add_argument("-m", "--message", default="Update System IP Design Hub", help="Git commit message")
    parser.add_argument("--no-push", action="store_true", help="Build and validate without committing or pushing")
    args = parser.parse_args()

    started_process: subprocess.Popen[str] | None = None
    try:
        source_files(PROJECT_ROOT)  # Fail closed on private/missing files before any build.
        staged = run(["git", "diff", "--cached", "--quiet"], DEPLOY_REPO, check=False)
        if staged.returncode != 0:
            raise RuntimeError("Existing staged changes must be committed or unstaged before publishing")
        started_process = start_server_if_needed()
        run_tests()
        export_static_site()
        check_static_links()
        log("Syncing approved public source")
        sync_public_source(PROJECT_ROOT, DEPLOY_REPO)
        git_publish(args.message, not args.no_push)
        print("\nPublish workflow completed successfully.")
        return 0
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if started_process is not None and started_process.poll() is None:
            started_process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
