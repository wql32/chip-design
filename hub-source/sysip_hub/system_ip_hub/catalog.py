from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    category TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    root_path TEXT NOT NULL,
    metadata_path TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (asset_id, tag_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS protocols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT '',
    UNIQUE(name, direction)
);
CREATE TABLE IF NOT EXISTS asset_protocols (
    asset_id INTEGER NOT NULL,
    protocol_id INTEGER NOT NULL,
    PRIMARY KEY (asset_id, protocol_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (protocol_id) REFERENCES protocols(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS dependencies (
    asset_id INTEGER NOT NULL,
    dependency_name TEXT NOT NULL,
    version_constraint TEXT NOT NULL DEFAULT '',
    relation TEXT NOT NULL DEFAULT 'required',
    PRIMARY KEY (asset_id, dependency_name),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    source_transaction TEXT NOT NULL,
    target_transaction TEXT NOT NULL,
    ordering TEXT NOT NULL DEFAULT '',
    split_behavior TEXT NOT NULL DEFAULT '',
    response_required INTEGER NOT NULL DEFAULT 0,
    error_mapping TEXT NOT NULL DEFAULT '',
    field_mapping TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS verification_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    check_type TEXT NOT NULL,
    status TEXT NOT NULL,
    command TEXT NOT NULL DEFAULT '',
    report_path TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE(asset_id, check_type),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);
"""


def _text(value: Any, default: str = "") -> str:
    return default if value is None else str(value)


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class Catalog:
    def __init__(self, asset_root: Path, database_path: Path) -> None:
        self.asset_root = asset_root.resolve()
        self.database_path = database_path.resolve()
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(mappings)")}
            if "field_mapping" not in columns:
                conn.execute("ALTER TABLE mappings ADD COLUMN field_mapping TEXT NOT NULL DEFAULT '[]'")

    def connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _metadata_files(self) -> Iterable[Path]:
        yield from self.asset_root.rglob("metadata.yaml")
        yield from self.asset_root.rglob("metadata.yml")
        yield from self.asset_root.rglob("metadata.json")

    def _read_metadata(self, path: Path) -> dict[str, Any]:
        # JSON is valid YAML syntax, so the first MVP can use JSON-formatted
        # metadata.yaml without adding a third-party YAML dependency.
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("metadata root must be an object")
        return data

    def scan(self) -> dict[str, Any]:
        scanned = 0
        errors: list[dict[str, str]] = []
        with self.connection() as conn:
            for metadata_path in self._metadata_files():
                try:
                    data = self._read_metadata(metadata_path)
                    name = _text(data.get("name"))
                    if not name:
                        raise ValueError("missing name")
                    root = metadata_path.parent.resolve()
                    if self.asset_root not in root.parents and root != self.asset_root:
                        raise ValueError("asset is outside asset root")
                    verification = data.get("verification") or {}
                    if isinstance(verification, dict):
                        configured_scope = data.get("verification_scope")
                        if isinstance(configured_scope, list) and configured_scope:
                            allowed_checks = {str(item) for item in configured_scope}
                        elif _text(data.get("kind")) in {"rtl_component", "component"}:
                            # Basic reusable blocks track implementation-oriented
                            # checks only. CDC/formal/performance belong to the
                            # consuming system or a dedicated verification flow.
                            allowed_checks = {"simulation", "lint", "synthesis"}
                        else:
                            allowed_checks = set(verification) - {"last_checked", "notes"}
                        verification = {key: value for key, value in verification.items() if key in allowed_checks or key in {"last_checked", "notes"}}
                    status = _text(data.get("status"), "draft")
                    if status == "draft" and isinstance(verification, dict):
                        statuses = [str(v) for v in verification.values()]
                        if "passed" in statuses:
                            status = "simulation_checked"
                    conn.execute(
                        """INSERT INTO assets
                        (name, display_name, kind, category, version, description,
                         status, root_path, metadata_path, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        ON CONFLICT(name) DO UPDATE SET
                          display_name=excluded.display_name,
                          kind=excluded.kind,
                          category=excluded.category,
                          version=excluded.version,
                          description=excluded.description,
                          status=excluded.status,
                          root_path=excluded.root_path,
                          metadata_path=excluded.metadata_path,
                          updated_at=excluded.updated_at""",
                        (
                            name,
                            _text(data.get("display_name"), name),
                            _text(data.get("kind"), "component"),
                            _text(data.get("category"), "uncategorized"),
                            _text(data.get("version"), "0.0.0"),
                            _text(data.get("description")),
                            status,
                            str(root),
                            str(metadata_path.resolve()),
                        ),
                    )
                    asset_id = conn.execute(
                        "SELECT id FROM assets WHERE name = ?", (name,)
                    ).fetchone()["id"]
                    conn.execute("DELETE FROM asset_tags WHERE asset_id = ?", (asset_id,))
                    for tag in _list(data.get("tags")):
                        tag_name = _text(tag).strip()
                        if not tag_name:
                            continue
                        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag_name,))
                        tag_id = conn.execute(
                            "SELECT id FROM tags WHERE name = ?", (tag_name,)
                        ).fetchone()["id"]
                        conn.execute(
                            "INSERT OR IGNORE INTO asset_tags(asset_id, tag_id) VALUES (?, ?)",
                            (asset_id, tag_id),
                        )
                    conn.execute("DELETE FROM asset_protocols WHERE asset_id = ?", (asset_id,))
                    protocols = data.get("protocols") or []
                    if isinstance(protocols, dict):
                        protocol_items = []
                        for direction, names in protocols.items():
                            protocol_items.extend((name, direction) for name in _list(names))
                    else:
                        protocol_items = [(name, "") for name in _list(protocols)]
                    for protocol, direction in protocol_items:
                        protocol_name = _text(protocol).strip()
                        if not protocol_name:
                            continue
                        conn.execute(
                            "INSERT OR IGNORE INTO protocols(name, direction) VALUES (?, ?)",
                            (protocol_name, _text(direction)),
                        )
                        protocol_id = conn.execute(
                            "SELECT id FROM protocols WHERE name = ? AND direction = ?",
                            (protocol_name, _text(direction)),
                        ).fetchone()["id"]
                        conn.execute(
                            "INSERT OR IGNORE INTO asset_protocols(asset_id, protocol_id) VALUES (?, ?)",
                            (asset_id, protocol_id),
                        )
                    conn.execute("DELETE FROM dependencies WHERE asset_id = ?", (asset_id,))
                    for dependency in _list(data.get("dependencies")):
                        if isinstance(dependency, str):
                            dep_name, constraint, relation = dependency, "", "required"
                        else:
                            dep_name = _text(dependency.get("name"))
                            constraint = _text(dependency.get("version_constraint"))
                            relation = _text(dependency.get("relation"), "required")
                        if dep_name:
                            conn.execute(
                                "INSERT OR REPLACE INTO dependencies(asset_id, dependency_name, version_constraint, relation) VALUES (?, ?, ?, ?)",
                                (asset_id, dep_name, constraint, relation),
                            )
                    conn.execute("DELETE FROM mappings WHERE asset_id = ?", (asset_id,))
                    for mapping in _list(data.get("mapping")):
                        if not isinstance(mapping, dict):
                            continue
                        source = _text(mapping.get("source_transaction"))
                        target = _text(mapping.get("target_transaction"))
                        if not source or not target:
                            continue
                        conn.execute(
                            """INSERT INTO mappings
                            (asset_id, source_transaction, target_transaction, ordering,
                             split_behavior, response_required, error_mapping, field_mapping, notes)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                asset_id,
                                source,
                                target,
                                _text(mapping.get("ordering")),
                                _text(mapping.get("split_behavior"), _text(mapping.get("split"))),
                                1 if mapping.get("response_required") else 0,
                                _text(mapping.get("error_mapping")),
                                json.dumps(mapping.get("field_mapping") or [], ensure_ascii=False),
                                _text(mapping.get("notes")),
                            ),
                        )
                    conn.execute("DELETE FROM verification_results WHERE asset_id = ?", (asset_id,))
                    for check_type, result in (verification.items() if isinstance(verification, dict) else []):
                        if check_type in {"last_checked", "notes"}:
                            continue
                        if isinstance(result, dict):
                            result_status = _text(result.get("status"), "unknown")
                            command = _text(result.get("command"))
                            report_path = _text(result.get("report_path"))
                            check_notes = _text(result.get("notes"))
                        else:
                            result_status = _text(result, "unknown")
                            command = report_path = check_notes = ""
                        conn.execute(
                            """INSERT INTO verification_results
                            (asset_id, check_type, status, command, report_path, checked_at, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (asset_id, _text(check_type), result_status, command, report_path, _text(verification.get("last_checked")), check_notes),
                        )
                    scanned += 1
                except Exception as exc:  # catalog scan should report all bad assets
                    errors.append({"path": str(metadata_path), "error": str(exc)})
        return {"scanned": scanned, "errors": errors}

    def list_assets(self, query: str = "", category: str = "", tag: str = "", protocol: str = "", status: str = "") -> list[dict[str, Any]]:
        sql = """SELECT DISTINCT a.* FROM assets a
                  LEFT JOIN asset_tags at ON at.asset_id = a.id
                  LEFT JOIN tags t ON t.id = at.tag_id
                  LEFT JOIN asset_protocols ap ON ap.asset_id = a.id
                  LEFT JOIN protocols p ON p.id = ap.protocol_id
                  WHERE 1=1"""
        params: list[str] = []
        if query:
            sql += " AND (a.name LIKE ? OR a.display_name LIKE ? OR a.description LIKE ?)"
            wildcard = f"%{query}%"
            params.extend([wildcard, wildcard, wildcard])
        if category:
            sql += " AND a.category = ?"
            params.append(category)
        if tag:
            sql += " AND t.name = ?"
            params.append(tag)
        if protocol:
            sql += " AND p.name = ?"
            params.append(protocol)
        if status:
            sql += " AND a.status = ?"
            params.append(status)
        sql += " ORDER BY a.updated_at DESC, a.name"
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._enrich_asset(conn, dict(row)) for row in rows]

    def get_asset(self, name: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM assets WHERE name = ?", (name,)).fetchone()
            return self._enrich_asset(conn, dict(row)) if row else None

    def delete_asset_record(self, name: str) -> bool:
        """Remove one catalog record and its dependent index rows."""
        with self.connection() as conn:
            row = conn.execute("SELECT id FROM assets WHERE name = ?", (name,)).fetchone()
            if not row:
                return False
            asset_id = row["id"]
            for table in ("asset_tags", "asset_protocols", "dependencies", "mappings", "verification_results"):
                conn.execute(f"DELETE FROM {table} WHERE asset_id = ?", (asset_id,))
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            return True

    def _enrich_asset(self, conn: sqlite3.Connection, asset: dict[str, Any]) -> dict[str, Any]:
        asset["tags"] = [r[0] for r in conn.execute(
            "SELECT t.name FROM tags t JOIN asset_tags at ON at.tag_id=t.id WHERE at.asset_id=? ORDER BY t.name",
            (asset["id"],),
        )]
        asset["protocols"] = [dict(r) for r in conn.execute(
            "SELECT p.name, p.direction FROM protocols p JOIN asset_protocols ap ON ap.protocol_id=p.id WHERE ap.asset_id=? ORDER BY p.name",
            (asset["id"],),
        )]
        asset["dependencies"] = [dict(r) for r in conn.execute(
            "SELECT dependency_name, version_constraint, relation FROM dependencies WHERE asset_id=? ORDER BY dependency_name",
            (asset["id"],),
        )]
        asset["mappings"] = [dict(r) for r in conn.execute(
            "SELECT source_transaction, target_transaction, ordering, split_behavior, response_required, error_mapping, field_mapping, notes FROM mappings WHERE asset_id=? ORDER BY id",
            (asset["id"],),
        )]
        for mapping in asset["mappings"]:
            try:
                mapping["field_mapping"] = json.loads(mapping["field_mapping"] or "[]")
            except (TypeError, json.JSONDecodeError):
                mapping["field_mapping"] = []
        asset["verification_results"] = [dict(r) for r in conn.execute(
            "SELECT check_type, status, command, report_path, checked_at, notes FROM verification_results WHERE asset_id=? ORDER BY check_type",
            (asset["id"],),
        )]
        try:
            asset["metadata"] = self._read_metadata(Path(asset["metadata_path"]))
        except Exception:
            asset["metadata"] = {}
        return asset

    def summary(self) -> dict[str, Any]:
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            categories = [dict(r) for r in conn.execute(
                "SELECT category, COUNT(*) AS count FROM assets GROUP BY category ORDER BY count DESC, category"
            )]
            statuses = [dict(r) for r in conn.execute(
                "SELECT status, COUNT(*) AS count FROM assets GROUP BY status ORDER BY count DESC, status"
            )]
            return {"total_assets": total, "categories": categories, "statuses": statuses}

    def protocols(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT p.name, p.direction, COUNT(DISTINCT ap.asset_id) AS asset_count
                   FROM protocols p LEFT JOIN asset_protocols ap ON ap.protocol_id=p.id
                   GROUP BY p.id ORDER BY p.name, p.direction"""
            ).fetchall()
            return [dict(row) for row in rows]

    def mappings(self, query: str = "") -> list[dict[str, Any]]:
        sql = """SELECT m.*, a.name AS asset_name, a.display_name, a.version
                 FROM mappings m JOIN assets a ON a.id=m.asset_id"""
        params: list[str] = []
        if query:
            sql += " WHERE m.source_transaction LIKE ? OR m.target_transaction LIKE ? OR a.name LIKE ?"
            wildcard = f"%{query}%"
            params = [wildcard, wildcard, wildcard]
        sql += " ORDER BY a.name, m.source_transaction"
        with self.connection() as conn:
            results = [dict(row) for row in conn.execute(sql, params).fetchall()]
            for mapping in results:
                try:
                    mapping["field_mapping"] = json.loads(mapping["field_mapping"] or "[]")
                except (TypeError, json.JSONDecodeError):
                    mapping["field_mapping"] = []
            return results

    def verification_summary(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT a.name, a.display_name, a.category, a.status AS asset_status,
                          vr.check_type, vr.status, vr.checked_at, vr.notes
                   FROM assets a LEFT JOIN verification_results vr ON vr.asset_id=a.id
                   ORDER BY a.name, vr.check_type"""
            ).fetchall()
            return [dict(row) for row in rows]

    def dependency_graph(self) -> dict[str, Any]:
        with self.connection() as conn:
            assets = [dict(row) for row in conn.execute("SELECT name, display_name, version, status FROM assets ORDER BY name")]
            edges = [dict(row) for row in conn.execute(
                "SELECT a.name AS asset_name, d.dependency_name, d.version_constraint, d.relation FROM dependencies d JOIN assets a ON a.id=d.asset_id ORDER BY a.name, d.dependency_name"
            )]
            known = {asset["name"] for asset in assets}
            missing = sorted({edge["dependency_name"] for edge in edges if edge["dependency_name"] not in known})
            return {"assets": assets, "edges": edges, "missing_dependencies": missing}

    def health_report(self) -> dict[str, Any]:
        assets = self.list_assets()
        checks = self.verification_summary()
        missing_metadata = [a["name"] for a in assets if not a["description"] or not a["tags"]]
        pending_checks = [
            {"asset": row["name"], "check_type": row["check_type"]}
            for row in checks if row["check_type"] and row["status"] in {"not_run", "unknown", "partial"}
        ]
        dependency = self.dependency_graph()
        return {
            "asset_count": len(assets),
            "mapping_count": len(self.mappings()),
            "missing_metadata": missing_metadata,
            "pending_checks": pending_checks,
            "missing_dependencies": dependency["missing_dependencies"],
        }
