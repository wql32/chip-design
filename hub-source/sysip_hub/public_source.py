"""Explicitly approved, reproducible source snapshot for the public repository."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path


SOURCE_FOLDER = "hub-source"
SNAPSHOT_NAME = "SOURCE_SNAPSHOT.json"
ASSET_SUFFIXES = {".md", ".v", ".sv", ".vh", ".svh", ".yaml", ".yml", ".json"}
FORBIDDEN_PARTS = {".git", ".codex", ".aws", ".ssh", "__pycache__", ".rtl_tools", ".env", "node_modules",
                   "credentials.json", "credentials.yaml", "credentials.yml", "secrets.json", "secrets.yaml", "secrets.yml"}
PRIVATE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".exe", ".zip", ".vcd", ".fst"}
SECRET_RE = re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")


def deploy_repo(project_root: Path) -> Path:
    """Support the existing workspace as well as a fresh clone/hub-source."""
    project_root = project_root.resolve()
    nested = project_root / ".deploy_repo"
    if (nested / ".git").exists():
        return nested
    if project_root.name == SOURCE_FOLDER and (project_root.parent / ".git").exists():
        return project_root.parent
    return nested


def safe_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {"..", "."} for part in path.parts):
        raise ValueError(f"Unsafe source path: {relative}")
    if path.suffix.lower() in PRIVATE_SUFFIXES or any((part.startswith(".") and part != ".gitignore") or part.lower() in FORBIDDEN_PARTS for part in path.parts):
        raise ValueError(f"Private/runtime path is not publishable: {relative}")
    target = root / path
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Source path escapes root: {relative}")
    # Resolve-before-copy checks also reject links/junctions within the root.
    if any(parent.is_symlink() or getattr(parent, "is_junction", lambda: False)()
           for parent in [target, *target.parents] if parent != root and parent.is_relative_to(root)):
        raise ValueError(f"Linked paths are not publishable: {relative}")
    return target


def load_manifest(project_root: Path) -> dict:
    manifest = json.loads((project_root / "sysip_hub/source_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported public source manifest")
    return manifest


def file_digest(path: Path) -> str:
    # Normalize LF/CRLF so Git autocrlf does not look like a user content edit.
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def source_files(project_root: Path) -> dict[str, Path]:
    """Only exact project files plus reviewed public asset roots are eligible."""
    manifest = load_manifest(project_root)
    files: dict[str, Path] = {}
    for relative in manifest["project_files"]:
        files[relative] = safe_path(project_root, relative)
    for relative in manifest["public_asset_roots"]:
        asset = safe_path(project_root, relative)
        if not asset.is_dir() or not (asset / "metadata.yaml").is_file():
            raise ValueError(f"Missing approved public asset: {relative}")
        for item in asset.rglob("*"):
            if item.is_file() and item.suffix.lower() in ASSET_SUFFIXES:
                rel = item.relative_to(project_root).as_posix()
                files[rel] = safe_path(project_root, rel)
    files["README.md"] = safe_path(project_root, "sysip_hub/SOURCE_CONTROL.md")
    files[".gitignore"] = safe_path(project_root, "sysip_hub/source.gitignore")
    for relative, path in files.items():
        if not path.is_file():
            raise ValueError(f"Missing source file: {relative}")
        raw = path.read_bytes()
        if len(raw) > 1024 * 1024 or b"\0" in raw:
            raise ValueError(f"Binary/oversized file excluded: {relative}")
        text = raw.decode("utf-8")
        if SECRET_RE.search(text):
            raise ValueError(f"Possible credential in public source: {relative}")
    return files


def validate_public_assets(project_root: Path, assets: list[dict]) -> None:
    allowed = {safe_path(project_root, relative).resolve()
               for relative in load_manifest(project_root)["public_asset_roots"]}
    actual = {Path(asset["root_path"]).resolve() for asset in assets}
    if actual != allowed:
        raise ValueError("Public asset list differs from source_manifest.json; review additions/removals before publishing")


def sync_public_source(project_root: Path, repository: Path) -> dict:
    """Update owned files only; never recursively delete a user directory."""
    files = source_files(project_root)  # Validate everything before touching output.
    target = repository.resolve() / SOURCE_FOLDER
    if not (repository / ".git").exists() or not target.resolve().is_relative_to(repository.resolve()):
        raise ValueError("Expected an existing Git checkout with a safe hub-source target")
    if target.is_symlink() or getattr(target, "is_junction", lambda: False)():
        raise ValueError("Source target cannot be a link/junction")
    previous_path = safe_path(target, SNAPSHOT_NAME)
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {"files": {}}
    stale = [safe_path(target, name) for name in previous["files"] if name not in files]
    # Never delete working sources when publishing directly from a fresh clone.
    if target.resolve() == project_root.resolve() and stale:
        raise ValueError("Source manifest removed tracked files; explicitly review/remove them with Git first")
    for name, source in files.items():
        destination = safe_path(target, name)
        if (destination.is_file() and name in previous["files"]
                and destination.resolve() != source.resolve()
                and file_digest(destination) != previous["files"][name]
                and file_digest(destination) != file_digest(source)):
            raise ValueError(f"Destination source has local edits; reconcile first: {name}")
        if (destination.exists() and name not in previous["files"]
                and destination.resolve() != source.resolve()
                and destination.read_bytes() != source.read_bytes()):
            raise ValueError(f"Refusing to overwrite unmanaged source file: {name}")
    for path in stale:
        if path.is_file() and file_digest(path) != previous["files"][path.relative_to(target).as_posix()]:
            raise ValueError(f"Removed source has local edits; reconcile first: {path.name}")
    snapshot = {"schema_version": 1, "files": {name: file_digest(path)
                                              for name, path in sorted(files.items())}}
    target.mkdir(parents=True, exist_ok=True)
    for name, path in files.items():
        destination = safe_path(target, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != destination.resolve():
            shutil.copy2(path, destination)
    for path in stale:
        if path.is_file():
            path.unlink()
    previous_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Public source: {len(files)} files, {len(load_manifest(project_root)['public_asset_roots'])} approved assets -> {target}")
    return snapshot
