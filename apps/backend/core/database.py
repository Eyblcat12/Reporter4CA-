"""SQLite database module for Reporter Pro.

Security:
- All queries use parameterized placeholders (?)
- Input validation via Pydantic before DB operations
- WAL mode for concurrent read safety
- Foreign keys enforced
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DB_DIR / "reporter.db"
_TEMPLATE_DIR = _DB_DIR.parent / "templates"
LATEST_SCHEMA_VERSION = 9

_SCHEMA_SQL = """
-- Templates: metadata for DOCX template files
CREATE TABLE IF NOT EXISTS templates (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    filename        TEXT NOT NULL UNIQUE,
    file_path       TEXT NOT NULL,
    file_size       INTEGER DEFAULT 0,
    file_hash       TEXT DEFAULT '',
    is_default      INTEGER DEFAULT 0,
    is_generated    INTEGER DEFAULT 0,
    has_tokens      INTEGER DEFAULT 0,
    template_mode   TEXT DEFAULT 'cover',
    report_type     TEXT DEFAULT 'full',
    table_count     INTEGER DEFAULT 0,
    heading_count   INTEGER DEFAULT 0,
    description     TEXT DEFAULT '',
    compatibility_status TEXT DEFAULT 'unknown',
    compatibility_version TEXT DEFAULT '',
    compatibility_json TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Presets: saved report configurations
CREATE TABLE IF NOT EXISTS presets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    settings_json   TEXT NOT NULL DEFAULT '{}',
    column_mapping_json TEXT DEFAULT NULL,
    template_id     TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
);

-- Report history
CREATE TABLE IF NOT EXISTS report_history (
    id              TEXT PRIMARY KEY,
    preset_id       TEXT DEFAULT NULL,
    template_id     TEXT DEFAULT NULL,
    title           TEXT DEFAULT '',
    organization    TEXT DEFAULT '',
    report_type     TEXT DEFAULT 'full',
    row_count       INTEGER DEFAULT 0,
    server_count    INTEGER DEFAULT 0,
    client_count    INTEGER DEFAULT 0,
    output_filename TEXT DEFAULT '',
    output_path     TEXT DEFAULT '',
    file_size       INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'success',
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    error_code      TEXT DEFAULT '',
    job_id          TEXT DEFAULT NULL,
    client_request_id TEXT DEFAULT '',
    request_signature TEXT DEFAULT '',
    source_artifact_id TEXT DEFAULT '',
    cache_status    TEXT DEFAULT '',
    updated_at      TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (preset_id) REFERENCES presets(id) ON DELETE SET NULL,
    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version         INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    applied_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS template_versions (
    id              TEXT PRIMARY KEY,
    template_id     TEXT NOT NULL,
    version_number  INTEGER NOT NULL,
    file_path       TEXT NOT NULL,
    file_size       INTEGER DEFAULT 0,
    file_hash       TEXT DEFAULT '',
    analysis_json   TEXT DEFAULT '{}',
    note            TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    UNIQUE(template_id, version_number),
    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
);

-- User-authored declarative detection rules. Built-in rules remain file-backed.
CREATE TABLE IF NOT EXISTS detection_rules (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    definition_json TEXT NOT NULL DEFAULT '{}',
    enabled         INTEGER NOT NULL DEFAULT 1,
    archived        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detection_rule_versions (
    id              TEXT PRIMARY KEY,
    rule_id         TEXT NOT NULL,
    version_number  INTEGER NOT NULL,
    definition_json TEXT NOT NULL,
    note            TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    UNIQUE(rule_id, version_number),
    FOREIGN KEY (rule_id) REFERENCES detection_rules(id) ON DELETE CASCADE
);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _migration_template_report_type(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(templates)").fetchall()}
    if "report_type" not in columns:
        conn.execute("ALTER TABLE templates ADD COLUMN report_type TEXT DEFAULT 'full'")


def _migration_query_indexes(conn: sqlite3.Connection) -> None:
    template_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(templates)").fetchall()
    }
    if {"report_type", "is_default"}.issubset(template_columns):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_templates_type_default "
            "ON templates(report_type, is_default)"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_presets_updated_at ON presets(updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_history_created_at "
        "ON report_history(created_at DESC)"
    )


def _migration_report_execution_metrics(conn: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(report_history)").fetchall()
    }
    additions = (
        ("status", "TEXT NOT NULL DEFAULT 'success'"),
        ("duration_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("error_code", "TEXT DEFAULT ''"),
    )
    for name, declaration in additions:
        if name not in columns:
            conn.execute(
                f"ALTER TABLE report_history ADD COLUMN {name} {declaration}"
            )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_history_status_created_at "
        "ON report_history(status, created_at DESC)"
    )


def _migration_template_compatibility(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(templates)").fetchall()}
    additions = (
        ("compatibility_status", "TEXT DEFAULT 'unknown'"),
        ("compatibility_version", "TEXT DEFAULT ''"),
        ("compatibility_json", "TEXT DEFAULT '{}'"),
    )
    for name, declaration in additions:
        if name not in columns:
            conn.execute(f"ALTER TABLE templates ADD COLUMN {name} {declaration}")


def _migration_template_versions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS template_versions (
            id TEXT PRIMARY KEY, template_id TEXT NOT NULL,
            version_number INTEGER NOT NULL, file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0, file_hash TEXT DEFAULT '',
            analysis_json TEXT DEFAULT '{}', note TEXT DEFAULT '', created_at TEXT NOT NULL,
            UNIQUE(template_id, version_number),
            FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_template_versions_template_number "
        "ON template_versions(template_id, version_number DESC)"
    )


def _migration_detection_rules(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS detection_rules (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
            definition_json TEXT NOT NULL DEFAULT '{}', enabled INTEGER NOT NULL DEFAULT 1,
            archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_detection_rules_active_updated "
        "ON detection_rules(archived, updated_at DESC)"
    )


def _migration_detection_rule_versions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS detection_rule_versions (
            id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, version_number INTEGER NOT NULL,
            definition_json TEXT NOT NULL, note TEXT DEFAULT '', created_at TEXT NOT NULL,
            UNIQUE(rule_id, version_number),
            FOREIGN KEY (rule_id) REFERENCES detection_rules(id) ON DELETE CASCADE
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_detection_rule_versions_rule_number "
        "ON detection_rule_versions(rule_id, version_number DESC)"
    )
    rows = conn.execute("SELECT * FROM detection_rules").fetchall()
    for row in rows:
        definition = json.loads(row[3] or "{}")
        definition.update({
            "id": row[0], "name": row[1], "description": row[2],
            "enabled": bool(row[4]),
        })
        conn.execute(
            """INSERT OR IGNORE INTO detection_rule_versions
               (id, rule_id, version_number, definition_json, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (_new_id(), row[0], 1, json.dumps(definition, ensure_ascii=False),
             "Baseline migrated to version history", row[6]),
        )


def _relocated_template_path(file_path: str) -> Path | None:
    """Map the pre-monorepo reporter-backend/templates path to apps/backend/templates."""
    source = Path(file_path)
    parts = list(source.parts)
    lowered = [part.casefold() for part in parts]
    for index in range(len(parts) - 1):
        if lowered[index:index + 2] != ["reporter-backend", "templates"]:
            continue
        relative_parts = parts[index + 2:]
        if not relative_parts:
            return None
        root = _TEMPLATE_DIR.resolve()
        candidate = root.joinpath(*relative_parts).resolve()
        if candidate.is_relative_to(root) and candidate.exists() and candidate.suffix.lower() == ".docx":
            return candidate
    return None


def _migration_relocated_template_paths(conn: sqlite3.Connection) -> None:
    """Repair persisted template paths after the repository directory migration."""
    now = _now_iso()
    template_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(templates)").fetchall()
    }
    if {"id", "file_path", "updated_at"}.issubset(template_columns):
        for template_id, file_path in conn.execute(
            "SELECT id, file_path FROM templates"
        ).fetchall():
            if not file_path or Path(file_path).exists():
                continue
            relocated = _relocated_template_path(file_path)
            if relocated:
                conn.execute(
                    "UPDATE templates SET file_path = ?, updated_at = ? WHERE id = ?",
                    (str(relocated), now, template_id),
                )

    version_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(template_versions)").fetchall()
    }
    if {"id", "file_path"}.issubset(version_columns):
        for version_id, file_path in conn.execute(
            "SELECT id, file_path FROM template_versions"
        ).fetchall():
            if not file_path or Path(file_path).exists():
                continue
            relocated = _relocated_template_path(file_path)
            if relocated:
                conn.execute(
                    "UPDATE template_versions SET file_path = ? WHERE id = ?",
                    (str(relocated), version_id),
                )


def _migration_report_job_history(conn: sqlite3.Connection) -> None:
    """Add exactly-once job identity and recover interrupted executions."""

    columns = {row[1] for row in conn.execute("PRAGMA table_info(report_history)").fetchall()}
    additions = (
        ("job_id", "TEXT DEFAULT NULL"),
        ("client_request_id", "TEXT DEFAULT ''"),
        ("request_signature", "TEXT DEFAULT ''"),
        ("source_artifact_id", "TEXT DEFAULT ''"),
        ("cache_status", "TEXT DEFAULT ''"),
        ("updated_at", "TEXT DEFAULT ''"),
    )
    for name, declaration in additions:
        if name not in columns:
            conn.execute(f"ALTER TABLE report_history ADD COLUMN {name} {declaration}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_report_history_job_id "
        "ON report_history(job_id) WHERE job_id IS NOT NULL AND job_id <> ''"
    )
    now = _now_iso()
    conn.execute(
        "UPDATE report_history SET status = 'failed', error_code = 'PROCESS_INTERRUPTED', "
        "updated_at = ? WHERE status IN ('queued', 'running')",
        (now,),
    )


_MIGRATIONS = (
    (1, "template_report_type", _migration_template_report_type),
    (2, "query_indexes", _migration_query_indexes),
    (3, "report_execution_metrics", _migration_report_execution_metrics),
    (4, "template_compatibility", _migration_template_compatibility),
    (5, "template_versions", _migration_template_versions),
    (6, "detection_rules", _migration_detection_rules),
    (7, "detection_rule_versions", _migration_detection_rule_versions),
    (8, "relocated_template_paths", _migration_relocated_template_paths),
    (9, "report_job_history", _migration_report_job_history),
)


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------

class Database:
    """Thin wrapper around sqlite3 with parameterized queries."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._path = Path(db_path) if db_path else _DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # ── Connection ──────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
                timeout=10,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        """Create tables and apply every pending schema migration in order."""
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        applied = {
            int(row[0])
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version, name, migrate in _MIGRATIONS:
            if version in applied:
                continue
            with conn:
                migrate(conn)
                conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES(?,?,?)",
                    (version, name, _now_iso()),
                )
        with conn:
            conn.execute(
                "UPDATE report_history SET status = 'failed', error_code = 'PROCESS_INTERRUPTED', "
                "updated_at = ? WHERE status IN ('queued', 'running')",
                (_now_iso(),),
            )

    @property
    def schema_version(self) -> int:
        row = self._get_conn().execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def backup_to(self, destination: Path | str) -> Path:
        """Create a transactionally consistent SQLite snapshot.

        SQLite's backup API includes committed data that may still live in the
        WAL file, so callers must use this instead of copying ``reporter.db``.
        """
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        source = self._get_conn()
        snapshot = sqlite3.connect(str(target))
        try:
            source.backup(snapshot)
            snapshot.commit()
        finally:
            snapshot.close()
        return target

    # ── Low-level query helpers ─────────────────────────────

    def _execute(
        self, sql: str, params: tuple = ()
    ) -> sqlite3.Cursor:
        conn = self._get_conn()
        return conn.execute(sql, params)

    def _execute_commit(
        self, sql: str, params: tuple = ()
    ) -> sqlite3.Cursor:
        cursor = self._execute(sql, params)
        self._get_conn().commit()
        return cursor

    def _fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        row = self._execute(sql, params).fetchone()
        return dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        rows = self._execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ══════════════════════════════════════════════════════════
    # Templates CRUD
    # ══════════════════════════════════════════════════════════

    def list_templates(self, report_type: str | None = None) -> list[dict]:
        if report_type:
            return self._fetch_all(
                """SELECT * FROM templates WHERE report_type = ?
                   ORDER BY is_default DESC, created_at DESC""",
                (report_type,),
            )
        return self._fetch_all(
            "SELECT * FROM templates ORDER BY is_default DESC, created_at DESC"
        )

    def get_default_template(self, report_type: str) -> dict | None:
        return self._fetch_one(
            """SELECT * FROM templates
               WHERE report_type = ? AND is_default = 1
               ORDER BY updated_at DESC LIMIT 1""",
            (report_type,),
        )

    def get_template(self, template_id: str) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        )

    def get_template_by_filename(self, filename: str) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM templates WHERE filename = ?", (filename,)
        )

    def get_template_by_path(self, file_path: str) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM templates WHERE file_path = ?", (file_path,)
        )

    def add_template(
        self,
        *,
        name: str,
        filename: str,
        file_path: str,
        file_size: int = 0,
        file_hash: str = "",
        is_default: bool = False,
        is_generated: bool = False,
        has_tokens: bool = False,
        template_mode: str = "cover",
        report_type: str = "full",
        table_count: int = 0,
        heading_count: int = 0,
        description: str = "",
        compatibility_status: str = "unknown",
        compatibility_version: str = "",
        compatibility_json: str = "{}",
    ) -> str:
        tid = _new_id()
        now = _now_iso()
        self._execute_commit(
            """INSERT INTO templates
               (id, name, filename, file_path, file_size, file_hash,
                is_default, is_generated, has_tokens, template_mode, report_type,
                table_count, heading_count, description, compatibility_status,
                compatibility_version, compatibility_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tid, name, filename, file_path, file_size, file_hash,
                int(is_default), int(is_generated), int(has_tokens),
                template_mode, report_type, table_count, heading_count, description,
                compatibility_status, compatibility_version, compatibility_json,
                now, now,
            ),
        )
        return tid

    def update_template(self, template_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        allowed = {
            "name", "description", "has_tokens", "template_mode",
            "report_type", "table_count", "heading_count", "file_hash", "file_size",
            "compatibility_status", "compatibility_version", "compatibility_json",
            "file_path", "file_hash", "file_size",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = tuple(fields.values()) + (template_id,)
        self._execute_commit(
            f"UPDATE templates SET {set_clause} WHERE id = ?", values
        )

    def add_template_version(
        self, template_id: str, *, file_path: str, file_size: int, file_hash: str,
        analysis: dict[str, Any], note: str = "",
    ) -> dict[str, Any]:
        row = self._fetch_one(
            "SELECT COALESCE(MAX(version_number), 0) AS number FROM template_versions WHERE template_id = ?",
            (template_id,),
        )
        version_number = int(row["number"]) + 1
        version_id = _new_id()
        self._execute_commit(
            """INSERT INTO template_versions
               (id, template_id, version_number, file_path, file_size, file_hash, analysis_json, note, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (version_id, template_id, version_number, file_path, file_size, file_hash,
             json.dumps(analysis, ensure_ascii=False), note, _now_iso()),
        )
        return self.get_template_version(template_id, version_number) or {}

    def list_template_versions(self, template_id: str) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM template_versions WHERE template_id = ? ORDER BY version_number DESC",
            (template_id,),
        )

    def get_template_version(self, template_id: str, version_number: int) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM template_versions WHERE template_id = ? AND version_number = ?",
            (template_id, version_number),
        )

    def set_default_template(self, template_id: str) -> bool:
        template = self.get_template(template_id)
        if not template:
            return False
        conn = self._get_conn()
        with conn:
            conn.execute(
                "UPDATE templates SET is_default = 0 WHERE report_type = ?",
                (template.get("report_type", "full"),),
            )
            conn.execute(
                "UPDATE templates SET is_default = 1, updated_at = ? WHERE id = ?",
                (_now_iso(), template_id),
            )
        return True

    def unset_default_template(self, template_id: str) -> None:
        self._execute_commit(
            "UPDATE templates SET is_default = 0, updated_at = ? WHERE id = ?",
            (_now_iso(), template_id),
        )

    def delete_template(self, template_id: str) -> bool:
        tpl = self.get_template(template_id)
        if not tpl or tpl["is_default"]:
            return False
        self._execute_commit(
            "DELETE FROM templates WHERE id = ? AND is_default = 0",
            (template_id,),
        )
        return True

    def seed_default_template(self, file_path: Path) -> str | None:
        """Register the default template if not already in DB."""
        existing = self.get_template_by_filename(file_path.name)
        if existing:
            return existing["id"]
        if not file_path.exists():
            return None
        return self.add_template(
            name="Report Template (Mặc định)",
            filename=file_path.name,
            file_path=str(file_path),
            file_size=file_path.stat().st_size,
            file_hash=file_sha256(file_path),
            is_default=True,
        )

    # ══════════════════════════════════════════════════════════
    # Presets CRUD
    # ══════════════════════════════════════════════════════════

    def list_presets(self) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM presets ORDER BY updated_at DESC"
        )
        for r in rows:
            r["settings"] = json.loads(r.pop("settings_json", "{}"))
            raw_mapping = r.pop("column_mapping_json", None)
            r["columnMapping"] = json.loads(raw_mapping) if raw_mapping else None
        return rows

    def get_preset(self, preset_id: str) -> dict | None:
        r = self._fetch_one("SELECT * FROM presets WHERE id = ?", (preset_id,))
        if r:
            r["settings"] = json.loads(r.pop("settings_json", "{}"))
            raw_mapping = r.pop("column_mapping_json", None)
            r["columnMapping"] = json.loads(raw_mapping) if raw_mapping else None
        return r

    def save_preset(
        self,
        *,
        name: str,
        settings: dict,
        column_mapping: dict | None = None,
        template_id: str | None = None,
        description: str = "",
        preset_id: str | None = None,
    ) -> str:
        now = _now_iso()
        settings_json = json.dumps(settings, ensure_ascii=False)
        mapping_json = json.dumps(column_mapping, ensure_ascii=False) if column_mapping else None

        if preset_id:
            existing = self.get_preset(preset_id)
            if existing:
                self._execute_commit(
                    """UPDATE presets
                       SET name=?, description=?, settings_json=?,
                           column_mapping_json=?, template_id=?, updated_at=?
                       WHERE id=?""",
                    (name, description, settings_json, mapping_json,
                     template_id, now, preset_id),
                )
                return preset_id

        pid = _new_id()
        self._execute_commit(
            """INSERT INTO presets
               (id, name, description, settings_json, column_mapping_json,
                template_id, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (pid, name, description, settings_json, mapping_json,
             template_id, now, now),
        )
        return pid

    def delete_preset(self, preset_id: str) -> bool:
        cursor = self._execute_commit(
            "DELETE FROM presets WHERE id = ?", (preset_id,)
        )
        return cursor.rowcount > 0

    # ══════════════════════════════════════════════════════════
    # Custom detection rules
    # ══════════════════════════════════════════════════════════

    def list_detection_rules(self, *, include_archived: bool = False) -> list[dict]:
        where = "" if include_archived else "WHERE archived = 0"
        rows = self._fetch_all(
            f"SELECT * FROM detection_rules {where} ORDER BY updated_at DESC"
        )
        for row in rows:
            definition = json.loads(row.pop("definition_json", "{}"))
            definition.update({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "enabled": bool(row["enabled"]),
                "archived": bool(row["archived"]),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "source": "custom",
                "editable": True,
            })
            row.clear()
            row.update(definition)
        return rows

    def get_detection_rule(self, rule_id: str) -> dict | None:
        row = self._fetch_one("SELECT * FROM detection_rules WHERE id = ?", (rule_id,))
        if not row:
            return None
        definition = json.loads(row["definition_json"])
        definition.update({
            "id": row["id"], "name": row["name"],
            "description": row["description"], "enabled": bool(row["enabled"]),
            "archived": bool(row["archived"]), "createdAt": row["created_at"],
            "updatedAt": row["updated_at"], "source": "custom", "editable": True,
        })
        return definition

    def save_detection_rule(self, definition: dict[str, Any]) -> dict:
        now = _now_iso()
        rule_id = str(definition.get("id") or f"CUSTOM_{_new_id().upper()}")
        stored = dict(definition)
        stored.pop("id", None)
        name = str(stored.pop("name", rule_id)).strip()
        description = str(stored.pop("description", "")).strip()
        enabled = bool(stored.pop("enabled", True))
        with self._get_conn():
            self._execute(
                """INSERT INTO detection_rules
                   (id, name, description, definition_json, enabled, archived, created_at, updated_at)
                   VALUES(?,?,?,?,?,0,?,?)""",
                (rule_id, name, description, json.dumps(stored, ensure_ascii=False), int(enabled), now, now),
            )
            snapshot = {**stored, "id": rule_id, "name": name, "description": description, "enabled": enabled}
            self._execute(
                """INSERT INTO detection_rule_versions
                   (id, rule_id, version_number, definition_json, note, created_at)
                   VALUES(?,?,?,?,?,?)""",
                (_new_id(), rule_id, 1, json.dumps(snapshot, ensure_ascii=False), "Initial version", now),
            )
        return self.get_detection_rule(rule_id) or {}

    def update_detection_rule(self, rule_id: str, definition: dict[str, Any]) -> dict | None:
        current = self.get_detection_rule(rule_id)
        if not current:
            return None
        merged = {**current, **definition}
        name = str(merged.get("name", rule_id)).strip()
        description = str(merged.get("description", "")).strip()
        enabled = bool(merged.get("enabled", True))
        latest = self._fetch_one(
            "SELECT COALESCE(MAX(version_number), 0) AS version FROM detection_rule_versions WHERE rule_id = ?",
            (rule_id,),
        ) or {"version": 0}
        next_version = int(latest["version"]) + 1
        stored = {
            key: value for key, value in merged.items()
            if key not in {"id", "name", "description", "enabled", "archived", "createdAt", "updatedAt", "source", "editable"}
        }
        stored["version"] = str(next_version)
        now = _now_iso()
        snapshot = {**stored, "id": rule_id, "name": name, "description": description, "enabled": enabled}
        with self._get_conn():
            self._execute(
                """UPDATE detection_rules SET name = ?, description = ?, definition_json = ?,
                   enabled = ?, updated_at = ? WHERE id = ?""",
                (name, description, json.dumps(stored, ensure_ascii=False), int(enabled), now, rule_id),
            )
            self._execute(
                """INSERT INTO detection_rule_versions
                   (id, rule_id, version_number, definition_json, note, created_at)
                   VALUES(?,?,?,?,?,?)""",
                (_new_id(), rule_id, next_version, json.dumps(snapshot, ensure_ascii=False), "Rule updated", now),
            )
        return self.get_detection_rule(rule_id)

    def list_detection_rule_versions(self, rule_id: str) -> list[dict]:
        rows = self._fetch_all(
            """SELECT id, rule_id, version_number, definition_json, note, created_at
               FROM detection_rule_versions WHERE rule_id = ? ORDER BY version_number DESC""",
            (rule_id,),
        )
        for row in rows:
            row["definition"] = json.loads(row.pop("definition_json"))
            row["ruleId"] = row.pop("rule_id")
            row["versionNumber"] = row.pop("version_number")
            row["createdAt"] = row.pop("created_at")
        return rows

    def rollback_detection_rule(self, rule_id: str, version_number: int) -> dict | None:
        row = self._fetch_one(
            "SELECT definition_json FROM detection_rule_versions WHERE rule_id = ? AND version_number = ?",
            (rule_id, version_number),
        )
        if not row:
            return None
        definition = json.loads(row["definition_json"])
        definition.pop("id", None)
        return self.update_detection_rule(rule_id, definition)

    # ══════════════════════════════════════════════════════════
    # Report History
    # ══════════════════════════════════════════════════════════

    def add_report(
        self,
        *,
        title: str = "",
        organization: str = "",
        report_type: str = "full",
        row_count: int = 0,
        server_count: int = 0,
        client_count: int = 0,
        output_filename: str = "",
        output_path: str = "",
        file_size: int = 0,
        status: str = "success",
        duration_ms: int = 0,
        error_code: str = "",
        preset_id: str | None = None,
        template_id: str | None = None,
        report_id: str | None = None,
        job_id: str | None = None,
        client_request_id: str = "",
        request_signature: str = "",
        source_artifact_id: str = "",
        cache_status: str = "",
    ) -> str:
        rid = report_id or _new_id()
        now = _now_iso()
        self._execute_commit(
            """INSERT INTO report_history
               (id, preset_id, template_id, title, organization,
                report_type, row_count, server_count, client_count,
                output_filename, output_path, file_size, status, duration_ms,
                error_code, job_id, client_request_id, request_signature,
                source_artifact_id, cache_status, updated_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid, preset_id, template_id, title, organization,
                report_type, row_count, server_count, client_count,
                output_filename, output_path, file_size, status,
                max(0, int(duration_ms)), error_code, job_id,
                client_request_id, request_signature, source_artifact_id,
                cache_status, now, now,
            ),
        )
        return rid

    def update_report_execution(
        self,
        report_id: str,
        *,
        status: str,
        output_filename: str = "",
        output_path: str = "",
        file_size: int = 0,
        duration_ms: int = 0,
        error_code: str = "",
        source_artifact_id: str | None = None,
        cache_status: str | None = None,
    ) -> None:
        existing = self.get_report(report_id)
        if not existing:
            raise KeyError(f"Report history row {report_id} does not exist.")
        terminal = {"success", "failed", "cancelled"}
        if str(existing.get("status")) in terminal:
            if status == existing.get("status"):
                return
            raise RuntimeError("Report history is already terminal.")
        source = existing.get("source_artifact_id", "") if source_artifact_id is None else source_artifact_id
        cache = existing.get("cache_status", "") if cache_status is None else cache_status
        self._execute_commit(
            """UPDATE report_history
               SET status = ?, output_filename = ?, output_path = ?, file_size = ?,
                   duration_ms = ?, error_code = ?, source_artifact_id = ?,
                   cache_status = ?, updated_at = ?
               WHERE id = ?""",
            (
                status, output_filename, output_path, max(0, int(file_size)),
                max(0, int(duration_ms)), error_code, source, cache,
                _now_iso(), report_id,
            ),
        )

    def list_reports(self, limit: int | None = 50, *, terminal_only: bool = False) -> list[dict]:
        query = """SELECT r.*, t.name AS template_name, t.file_path AS template_path
                   FROM report_history r
                   LEFT JOIN templates t ON t.id = r.template_id"""
        if terminal_only:
            query += " WHERE r.status IN ('success', 'failed', 'cancelled')"
        query += " ORDER BY r.created_at DESC"
        if limit is None:
            return self._fetch_all(query)
        return self._fetch_all(f"{query} LIMIT ?", (max(1, int(limit)),))

    def get_report(self, report_id: str) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM report_history WHERE id = ?", (report_id,)
        )

    def dashboard_summary(
        self,
        days: int = 90,
        *,
        bucket_count: int = 8,
        recent_limit: int = 8,
    ) -> dict:
        """Return server-side dashboard metrics for a bounded time window."""
        if days not in {30, 90, 180}:
            raise ValueError("days must be one of 30, 90, or 180")
        bucket_count = min(24, max(1, int(bucket_count)))
        recent_limit = min(50, max(1, int(recent_limit)))

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        previous_start = start - timedelta(days=days)
        start_iso = start.isoformat()
        previous_start_iso = previous_start.isoformat()
        now_iso = now.isoformat()

        metrics = self._fetch_one(
            """SELECT
                   COUNT(*) AS attempts,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS reports,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                   SUM(CASE WHEN status = 'success' THEN row_count ELSE 0 END) AS assets,
                   COUNT(DISTINCT CASE WHEN status = 'success' THEN report_type END) AS report_types,
                   AVG(CASE WHEN status = 'success' THEN duration_ms END) AS avg_duration_ms
               FROM report_history
               WHERE status IN ('success', 'failed', 'cancelled')
                 AND created_at >= ? AND created_at <= ?""",
            (start_iso, now_iso),
        ) or {}
        previous = self._fetch_one(
            """SELECT COUNT(*) AS reports FROM report_history
               WHERE status = 'success' AND created_at >= ? AND created_at < ?""",
            (previous_start_iso, start_iso),
        ) or {"reports": 0}

        attempts = int(metrics.get("attempts") or 0)
        reports = int(metrics.get("reports") or 0)
        failed = int(metrics.get("failed") or 0)
        cancelled = int(metrics.get("cancelled") or 0)
        previous_reports = int(previous.get("reports") or 0)
        delta_percent = (
            round(((reports - previous_reports) / previous_reports) * 100)
            if previous_reports
            else None
        )

        bucket_seconds = (days * 24 * 60 * 60) / bucket_count
        series = [
            {
                "start": (start + timedelta(seconds=index * bucket_seconds)).isoformat(),
                "end": min(
                    now,
                    start + timedelta(seconds=(index + 1) * bucket_seconds),
                ).isoformat(),
                "count": 0,
                "attempts": 0,
                "success": 0,
                "failed": 0,
                "cancelled": 0,
            }
            for index in range(bucket_count)
        ]
        activity = self._fetch_all(
            """SELECT created_at, status FROM report_history
               WHERE status IN ('success', 'failed', 'cancelled')
                 AND created_at >= ? AND created_at <= ?
               ORDER BY created_at""",
            (start_iso, now_iso),
        )
        for item in activity:
            try:
                created_at = datetime.fromisoformat(item["created_at"])
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                index = int((created_at - start).total_seconds() / bucket_seconds)
                index = min(bucket_count - 1, max(0, index))
                status = str(item.get("status") or "").lower()
                series[index]["attempts"] += 1
                if status == "success":
                    series[index]["success"] += 1
                    # Keep count for backwards-compatible chart consumers.
                    series[index]["count"] += 1
                elif status == "failed":
                    series[index]["failed"] += 1
                elif status == "cancelled":
                    series[index]["cancelled"] += 1
            except (TypeError, ValueError):
                continue

        return {
            "days": days,
            "generatedAt": now_iso,
            "range": {
                "start": start_iso,
                "end": now_iso,
                "previousStart": previous_start_iso,
            },
            "metrics": {
                "reports": reports,
                "attempts": attempts,
                "failed": failed,
                "cancelled": cancelled,
                "assets": int(metrics.get("assets") or 0),
                "reportTypes": int(metrics.get("report_types") or 0),
                "successRate": round((reports / attempts) * 100, 1) if attempts else None,
                "avgDurationMs": round(float(metrics.get("avg_duration_ms") or 0)),
                "deltaPercent": delta_percent,
            },
            "series": series,
            "recent": self.list_reports(recent_limit, terminal_only=True),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_db: Database | None = None


def get_db() -> Database:
    """Get or create the module-level Database singleton."""
    global _db
    if _db is None:
        _db = Database()
        _db.initialize()
    return _db
