"""Private SQLite library of immutable template sources and structural analyses."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TemplateLibrary:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            if connection.execute("PRAGMA user_version").fetchone()[0] not in (0, 1):
                raise ValueError("Unsupported template library database version.")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS templates (
                    sha256 TEXT PRIMARY KEY, filename TEXT NOT NULL,
                    source BLOB NOT NULL, size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    template_sha256 TEXT NOT NULL REFERENCES templates(sha256),
                    report_type TEXT NOT NULL, schema_version TEXT NOT NULL,
                    result_json TEXT NOT NULL, analyzed_at TEXT NOT NULL,
                    PRIMARY KEY(template_sha256, report_type)
                );
                CREATE TABLE IF NOT EXISTS workspace_sources (
                    workspace_id TEXT PRIMARY KEY,
                    template_sha256 TEXT NOT NULL REFERENCES templates(sha256)
                );
                PRAGMA user_version=1;
            """)
            with connection:
                yield connection
        finally:
            connection.close()

    def remember(
        self, source: bytes, filename: str, analysis: dict[str, Any], *, workspace_id: str = ""
    ) -> str:
        digest = hashlib.sha256(source).hexdigest()
        if analysis.get("templateSha256") != digest:
            raise ValueError("Template library checksum does not match the analysis.")
        timestamp = datetime.now(timezone.utc).isoformat()
        safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1][:200] or "template.docx"
        with self.connect() as db:
            db.execute(
                "INSERT INTO templates VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(sha256) DO UPDATE SET updated_at=excluded.updated_at",
                (digest, safe_name, source, len(source), timestamp, timestamp),
            )
            db.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?, ?) ON CONFLICT(template_sha256, report_type) DO UPDATE SET schema_version=excluded.schema_version, result_json=excluded.result_json, analyzed_at=excluded.analyzed_at",
                (
                    digest,
                    analysis["reportType"],
                    analysis["schemaVersion"],
                    json.dumps(analysis, ensure_ascii=False),
                    timestamp,
                ),
            )
            if workspace_id:
                db.execute(
                    "INSERT INTO workspace_sources VALUES (?, ?) ON CONFLICT(workspace_id) DO UPDATE SET template_sha256=excluded.template_sha256",
                    (workspace_id, digest),
                )
        return digest

    def list(self, *, query: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
        query = query[:200]
        limit = max(1, min(limit, 100))
        with self.connect() as db:
            total = db.execute(
                "SELECT COUNT(*) FROM templates WHERE instr(lower(filename), lower(?)) > 0",
                (query,),
            ).fetchone()[0]
            rows = db.execute(
                "SELECT sha256, filename, size_bytes, created_at, updated_at FROM templates WHERE instr(lower(filename), lower(?)) > 0 ORDER BY updated_at DESC, sha256 LIMIT ? OFFSET ?",
                (query, limit, max(offset, 0)),
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                item["reportTypes"] = [
                    entry[0]
                    for entry in db.execute(
                        "SELECT report_type FROM analyses WHERE template_sha256=? ORDER BY report_type",
                        (row["sha256"],),
                    )
                ]
                item["workspaceIds"] = [
                    entry[0]
                    for entry in db.execute(
                        "SELECT workspace_id FROM workspace_sources WHERE template_sha256=? ORDER BY workspace_id",
                        (row["sha256"],),
                    )
                ]
                items.append(item)
        return {"items": items, "total": total, "hasMore": offset + len(items) < total}

    def source(self, digest: str) -> tuple[str, bytes]:
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid template library identity.")
        with self.connect() as db:
            row = db.execute(
                "SELECT filename, source FROM templates WHERE sha256=?", (digest,)
            ).fetchone()
        if row is None:
            raise FileNotFoundError("Template not found in library.")
        if hashlib.sha256(row["source"]).hexdigest() != digest:
            raise ValueError("Stored template library checksum is invalid.")
        return row["filename"], row["source"]

    def analyses(self, digest: str) -> list[dict[str, Any]]:
        self.source(digest)
        with self.connect() as db:
            rows = db.execute(
                "SELECT result_json FROM analyses WHERE template_sha256=? ORDER BY report_type",
                (digest,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def backfill(self, studio: Any) -> int:
        skipped = 0
        for path in studio.workspaces.root.glob("*.json"):
            try:
                workspace = studio.get(path.stem)
                with self.connect() as db:
                    if db.execute(
                        "SELECT 1 FROM workspace_sources WHERE workspace_id=?", (path.stem,)
                    ).fetchone():
                        continue
                self.remember(
                    studio.source_bytes(path.stem),
                    workspace["displayName"] + ".docx",
                    workspace["analysis"],
                    workspace_id=path.stem,
                )
            except (ValueError, OSError):
                skipped += 1
        return skipped
