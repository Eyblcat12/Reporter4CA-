"""Unapproved editor checkpoints, isolated from report and template-library databases."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .template_profiles import COMMON_REQUIREMENTS, REPORT_REQUIREMENTS


class EditorDraftConflict(ValueError):
    """A draft revision or operation identity no longer matches."""


class EditorDraftStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Unsupported editor draft database version.")
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE IF NOT EXISTS drafts ("
                "id TEXT PRIMARY KEY, workspace TEXT NOT NULL, revision INTEGER NOT NULL, "
                "payload TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS operations ("
                "id TEXT PRIMARY KEY, signature TEXT NOT NULL, result TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS retired_drafts ("
                "draft_id TEXT PRIMARY KEY, reason TEXT NOT NULL, retired_at TEXT NOT NULL)"
            )
            db.execute("PRAGMA user_version=1")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
            raise ValueError("Draft, session and operation IDs must be 32 hexadecimal characters.")

    @staticmethod
    def _editor(value, semantic):
        if not isinstance(value, dict) or set(value) != {"anchorKey", "fields"}:
            raise ValueError("Draft must contain only anchorKey and fields.")
        if not isinstance(value["anchorKey"], str) or len(value["anchorKey"]) > 512:
            raise ValueError("Invalid draft anchor.")
        fields = value["fields"]
        if not isinstance(fields, dict) or set(fields) - set(
            COMMON_REQUIREMENTS[semantic].required_fields
        ):
            raise ValueError("Unsupported draft fields.")
        if any(not isinstance(v, str) or len(v) > 64 for v in fields.values()):
            raise ValueError("Draft field values exceed the editor limit.")

    def save(self, workspace, draft_id, payload):
        self.identifier(draft_id)
        if not isinstance(payload, dict) or set(payload) != {
            "sessionId",
            "operationId",
            "expectedDraftRevision",
            "baseRevision",
            "templateSha256",
            "semantic",
            "draft",
            "baseline",
        }:
            raise ValueError("Unsupported editor draft payload.")
        self.identifier(payload["sessionId"])
        self.identifier(payload["operationId"])
        for key in ("expectedDraftRevision", "baseRevision"):
            if type(payload[key]) is not int or payload[key] < (1 if key == "baseRevision" else 0):
                raise ValueError("Invalid draft revision.")
        semantic = payload["semantic"]
        if (
            not isinstance(semantic, str)
            or semantic not in REPORT_REQUIREMENTS[workspace["reportType"]]
        ):
            raise ValueError("Unsupported draft semantic.")
        if payload["templateSha256"] != workspace["templateSha256"]:
            raise EditorDraftConflict("Draft source does not match workspace source.")
        if payload["baseRevision"] > workspace["revision"]:
            raise EditorDraftConflict("Draft base revision is newer than the workspace.")
        self._editor(payload["draft"], semantic)
        self._editor(payload["baseline"], semantic)
        request = json.dumps([workspace["workspaceId"], draft_id, payload], sort_keys=True)
        signature = hashlib.sha256(request.encode()).hexdigest()
        with self.connect() as db:
            if db.execute("SELECT 1 FROM retired_drafts WHERE draft_id=?", (draft_id,)).fetchone():
                raise EditorDraftConflict("Draft is retired; create a new draft identity.")
            previous = db.execute(
                "SELECT signature,result FROM operations WHERE id=?", (payload["operationId"],)
            ).fetchone()
            if previous:
                if previous["signature"] != signature:
                    raise EditorDraftConflict("Operation ID was already used for another request.")
                return json.loads(previous["result"])
            current = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            revision = current["revision"] if current else 0
            if revision != payload["expectedDraftRevision"]:
                raise EditorDraftConflict("Editor draft revision changed.")
            if current:
                old = json.loads(current["payload"])
                if current["workspace"] != workspace["workspaceId"] or any(
                    old[k] != payload[k]
                    for k in ("sessionId", "templateSha256", "semantic", "baseRevision", "baseline")
                ):
                    raise EditorDraftConflict("Draft identity and baseline are immutable.")
            timestamp = datetime.now(timezone.utc).isoformat()
            record = {
                "draftId": draft_id,
                "workspaceId": workspace["workspaceId"],
                "schemaVersion": 1,
                "draftRevision": revision + 1,
                "updatedAt": timestamp,
                **{
                    k: v
                    for k, v in payload.items()
                    if k not in ("operationId", "expectedDraftRevision")
                },
            }
            encoded = json.dumps(record, ensure_ascii=False, sort_keys=True)
            db.execute(
                "INSERT INTO drafts VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "revision=excluded.revision,payload=excluded.payload,updated_at=excluded.updated_at",
                (draft_id, workspace["workspaceId"], revision + 1, encoded, timestamp),
            )
            db.execute(
                "INSERT INTO operations VALUES (?,?,?)",
                (payload["operationId"], signature, encoded),
            )
            return record

    def list(self, workspace, *, offset=0, limit=20):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid editor draft pagination.")
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM drafts WHERE workspace=? "
                "AND id NOT IN (SELECT draft_id FROM retired_drafts) "
                "ORDER BY updated_at DESC,id LIMIT ? OFFSET ?",
                (workspace["workspaceId"], limit + 1, offset),
            ).fetchall()
            items = []
            for row in rows[:limit]:
                item = json.loads(row["payload"])
                item["stale"] = item["baseRevision"] != workspace["revision"]
                item["sourceChanged"] = item["templateSha256"] != workspace["templateSha256"]
                items.append(item)
            return {"items": items, "nextOffset": offset + limit if len(rows) > limit else None}

    def retire(self, workspace, draft_id, payload):
        """Hide a checkpoint without deleting its content or changing approved mappings."""
        self.identifier(draft_id)
        if not isinstance(payload, dict) or set(payload) != {
            "operationId",
            "expectedDraftRevision",
            "reason",
        }:
            raise ValueError("Unsupported draft retirement request.")
        self.identifier(payload["operationId"])
        if (
            type(payload["expectedDraftRevision"]) is not int
            or payload["expectedDraftRevision"] < 1
        ):
            raise ValueError("Invalid draft revision.")
        if payload["reason"] not in ("discarded", "approved"):
            raise ValueError("Invalid draft retirement reason.")
        request = json.dumps(
            ["retire", workspace["workspaceId"], draft_id, payload], sort_keys=True
        )
        signature = hashlib.sha256(request.encode()).hexdigest()
        with self.connect() as db:
            previous = db.execute(
                "SELECT * FROM operations WHERE id=?", (payload["operationId"],)
            ).fetchone()
            if previous:
                if previous["signature"] != signature:
                    raise EditorDraftConflict("Operation ID was already used for another request.")
                return json.loads(previous["result"])
            row = db.execute(
                "SELECT * FROM drafts WHERE id=? AND workspace=?",
                (draft_id, workspace["workspaceId"]),
            ).fetchone()
            if row is None:
                raise FileNotFoundError("Editor draft not found.")
            if row["revision"] != payload["expectedDraftRevision"]:
                raise EditorDraftConflict("Editor draft revision changed.")
            draft = json.loads(row["payload"])
            if payload["reason"] == "approved":
                slot = next(
                    (s for s in workspace.get("slots", []) if s["semantic"] == draft["semantic"]),
                    None,
                )
                fields = {
                    key: f"column:{value.strip()}"
                    if re.fullmatch(r"[1-9][0-9]{0,2}", value.strip())
                    else value.strip()
                    for key, value in draft["draft"]["fields"].items()
                }
                if (
                    not slot
                    or workspace["templateSha256"] != draft["templateSha256"]
                    or f"{slot['anchor']['kind']}:{slot['anchor']['value']}"
                    != draft["draft"]["anchorKey"]
                    or {f["source"]: f["target"] for f in slot.get("fields", [])} != fields
                ):
                    raise EditorDraftConflict("Saved mapping does not match this checkpoint.")
            already = db.execute(
                "SELECT reason FROM retired_drafts WHERE draft_id=?", (draft_id,)
            ).fetchone()
            if already and already["reason"] != payload["reason"]:
                raise EditorDraftConflict("Draft was retired for another reason.")
            db.execute(
                "INSERT OR IGNORE INTO retired_drafts VALUES (?,?,?)",
                (draft_id, payload["reason"], datetime.now(timezone.utc).isoformat()),
            )
            result = {"draftId": draft_id, "retired": True, "reason": payload["reason"]}
            encoded = json.dumps(result, sort_keys=True)
            db.execute(
                "INSERT INTO operations VALUES (?,?,?)",
                (payload["operationId"], signature, encoded),
            )
            return result
