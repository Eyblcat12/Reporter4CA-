"""Trusted validation-run storage and atomic Template Pack publication.

This module is intentionally isolated from the Legacy Renderer.  Browser input
can request a validation, acknowledge an exact baseline artifact, and publish
an exact verified artifact; it cannot manufacture validation evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report_signature import canonical_sha256
from .report_snapshot import PreparedReportSnapshot
from .template_mapping_workspace import TemplateStudioService
from .template_pack_catalog import TemplatePackCatalog, build_template_pack
from .template_pack_validation import (
    TemplatePackValidationRun,
    ValidationIssue,
    approve_template_pack_validation,
    run_template_pack_validation,
)

PUBLISH_STORE_SCHEMA_VERSION = 1


class TemplatePackPublishError(ValueError):
    """Raised when persisted validation or publication trust checks fail."""


class TemplatePackPublishConflict(TemplatePackPublishError):
    """Raised when a workspace or validation revision is stale."""


class TemplatePackPublishService:
    """Own validation artifacts and publish only server-issued evidence."""

    def __init__(
        self,
        root: Path,
        studio: TemplateStudioService,
        catalog: TemplatePackCatalog,
    ) -> None:
        self.root = root.resolve()
        self.runs_root = self.root / "runs"
        self.studio = studio
        self.catalog = catalog
        self._lock = threading.RLock()

    def validate(
        self,
        workspace_id: str,
        prepared: PreparedReportSnapshot,
        *,
        fixture_id: str,
        expected_workspace_revision: int,
        baseline_run_id: str = "",
    ) -> dict[str, Any]:
        """Run backend validation and persist the exact artifact and structure."""

        with self._lock:
            workspace, template_bytes = self._pinned_workspace(
                workspace_id, expected_workspace_revision
            )
            if prepared.accepted.report_type != workspace.get("reportType"):
                raise TemplatePackPublishError("Fixture report type does not match workspace.")
            if prepared.accepted.template_hash != workspace.get("templateSha256"):
                raise TemplatePackPublishError("Prepared fixture is not pinned to this workspace.")

            baseline: dict[str, Any] | None = None
            normalized_baseline_id = baseline_run_id.strip().lower()
            if normalized_baseline_id:
                baseline_record = self._load_record(normalized_baseline_id)
                self._assert_same_workspace(workspace, baseline_record)
                approval = baseline_record.get("baselineApproval")
                if not isinstance(approval, dict) or not approval.get("reviewedBy"):
                    raise TemplatePackPublishError("Structural baseline has not been reviewed.")
                baseline = self._load_snapshot(normalized_baseline_id, baseline_record)

            run = run_template_pack_validation(
                workspace,
                template_bytes,
                prepared,
                fixture_id=fixture_id,
                structural_baseline=baseline,
            )
            record = {
                "storeSchemaVersion": PUBLISH_STORE_SCHEMA_VERSION,
                "runId": run.run_id,
                "workspaceId": workspace_id,
                "workspaceRevision": workspace["revision"],
                "workspaceSha256": canonical_sha256(workspace),
                "templateSha256": workspace["templateSha256"],
                "baselineRunId": normalized_baseline_id,
                "createdAt": _timestamp(),
                "state": "ready_for_review"
                if run.ready_for_visual_review
                else "baseline_candidate",
                "validation": run.public(),
                "baselineApproval": None,
            }
            stored = self._store_run(record, run.artifact_bytes, run.structural_snapshot)
            return self._public_record(stored)

    def list_runs(self, workspace_id: str, *, limit: int = 100) -> dict[str, Any]:
        """List resumable validation metadata without trusting cached client state."""

        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise TemplatePackPublishError("Validation run limit must be between 1 and 100.")
        with self._lock:
            workspace = self.studio.get(workspace_id)
            if not self.runs_root.exists():
                return {
                    "items": [],
                    "total": 0,
                    "hasMore": False,
                    "skippedCorrupt": 0,
                    "currentWorkspaceRevision": workspace["revision"],
                }
            records: list[dict[str, Any]] = []
            skipped_corrupt = 0
            try:
                children = tuple(self.runs_root.iterdir())
            except OSError as exc:
                raise TemplatePackPublishError("Validation run store is unavailable.") from exc
            for child in children:
                if child.is_symlink() or not child.is_dir():
                    continue
                try:
                    record = self._load_record(child.name)
                except TemplatePackPublishError:
                    skipped_corrupt += 1
                    continue
                if record.get("workspaceId") != workspace_id:
                    continue
                item = self._public_record(record)
                item["stale"] = bool(
                    record.get("workspaceRevision") != workspace.get("revision")
                    or record.get("workspaceSha256") != canonical_sha256(workspace)
                    or record.get("templateSha256") != workspace.get("templateSha256")
                )
                records.append(item)
            records.sort(
                key=lambda item: (item.get("createdAt", ""), item.get("runId", "")),
                reverse=True,
            )
            return {
                "items": records[:limit],
                "total": len(records),
                "hasMore": len(records) > limit,
                "skippedCorrupt": skipped_corrupt,
                "currentWorkspaceRevision": workspace["revision"],
            }

    def approve_baseline(
        self,
        workspace_id: str,
        run_id: str,
        *,
        expected_workspace_revision: int,
        reviewer: str,
        artifact_sha256: str,
    ) -> dict[str, Any]:
        """Approve an exact first-pass artifact as a structural baseline."""

        identity = _reviewer(reviewer)
        with self._lock:
            workspace, _ = self._pinned_workspace(workspace_id, expected_workspace_revision)
            record = self._load_record(run_id)
            self._assert_same_workspace(workspace, record)
            validation = record["validation"]
            if record.get("baselineRunId"):
                raise TemplatePackPublishError("Only a first-pass run can become a baseline.")
            if not validation.get("fixturePassed") or not validation.get("integrityPassed"):
                raise TemplatePackPublishError(
                    "Baseline has unresolved fixture or integrity issues."
                )
            self._verify_artifact(run_id, record, artifact_sha256)
            existing = record.get("baselineApproval")
            if isinstance(existing, dict):
                if (
                    existing.get("reviewedBy") == identity
                    and existing.get("artifactSha256") == artifact_sha256.lower()
                ):
                    return self._public_record(record)
                raise TemplatePackPublishConflict("Baseline was already reviewed.")
            record["baselineApproval"] = {
                "reviewedBy": identity,
                "reviewedAt": _timestamp(),
                "artifactSha256": artifact_sha256.strip().lower(),
                "structuralSha256": validation["structuralSha256"],
            }
            record["state"] = "baseline_approved"
            self._save_record(run_id, record)
            return self._public_record(record)

    def publish(
        self,
        workspace_id: str,
        run_id: str,
        *,
        expected_workspace_revision: int,
        expected_catalog_revision: int,
        reviewer: str,
        artifact_sha256: str,
    ) -> dict[str, Any]:
        """Build and atomically install a pack from one exact verified run."""

        with self._lock:
            workspace, template_bytes = self._pinned_workspace(
                workspace_id, expected_workspace_revision
            )
            record = self._load_record(run_id)
            self._assert_same_workspace(workspace, record)
            if not record.get("baselineRunId"):
                raise TemplatePackPublishError("Publish requires a verified second-pass run.")
            baseline_record = self._load_record(record["baselineRunId"])
            self._assert_same_workspace(workspace, baseline_record)
            if not isinstance(baseline_record.get("baselineApproval"), dict):
                raise TemplatePackPublishError("Referenced baseline is no longer approved.")
            self._verify_artifact(run_id, record, artifact_sha256)
            run = self._restore_run(record)
            evidence = approve_template_pack_validation(
                run,
                reviewer=_reviewer(reviewer),
                artifact_sha256=artifact_sha256,
            )
            pack_bytes = build_template_pack(workspace, template_bytes, evidence)
            catalog = self.catalog.install(
                pack_bytes,
                expected_revision=expected_catalog_revision,
                actor=reviewer,
            )
            return {
                "run": self._public_record(record),
                "packSha256": hashlib.sha256(pack_bytes).hexdigest(),
                "catalog": catalog,
                "selectionIntegrated": False,
                "legacyRendererUnchanged": True,
            }

    def artifact(self, workspace_id: str, run_id: str) -> tuple[bytes, dict[str, Any]]:
        """Return a checksum-verified validation artifact for human review."""

        with self._lock:
            workspace = self.studio.get(workspace_id)
            record = self._load_record(run_id)
            self._assert_same_workspace(workspace, record)
            data = self._verify_artifact(run_id, record)
            return data, self._public_record(record)

    def _pinned_workspace(
        self, workspace_id: str, expected_revision: int
    ) -> tuple[dict[str, Any], bytes]:
        workspace = self.studio.get(workspace_id)
        if workspace.get("revision") != expected_revision:
            raise TemplatePackPublishConflict(
                f"Workspace revision changed; expected {expected_revision}, "
                f"current {workspace.get('revision')}."
            )
        if workspace.get("status") != "mapping_complete":
            raise TemplatePackPublishError("Workspace must have 100% mapping before validation.")
        if workspace.get("archived"):
            raise TemplatePackPublishError("Archived workspaces cannot be validated or published.")
        return workspace, self.studio.source_bytes(workspace_id)

    def _assert_same_workspace(self, workspace: dict[str, Any], record: dict[str, Any]) -> None:
        if record.get("workspaceId") != workspace.get("workspaceId"):
            raise TemplatePackPublishError("Validation run belongs to another workspace.")
        if (
            record.get("workspaceRevision") != workspace.get("revision")
            or record.get("workspaceSha256") != canonical_sha256(workspace)
            or record.get("templateSha256") != workspace.get("templateSha256")
        ):
            raise TemplatePackPublishConflict("Workspace changed after validation; run it again.")

    def _store_run(
        self, record: dict[str, Any], artifact: bytes, snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        run_id = record["runId"]
        target = self._run_dir(run_id)
        if target.exists():
            existing = self._load_record(run_id)
            if existing["validation"]["artifactSha256"] != hashlib.sha256(artifact).hexdigest():
                raise TemplatePackPublishError("Validation run identity collision detected.")
            return existing
        self.runs_root.mkdir(parents=True, exist_ok=True)
        staging = self.runs_root / f".{run_id}.{uuid.uuid4().hex}.tmp"
        try:
            staging.mkdir()
            (staging / "artifact.docx").write_bytes(artifact)
            (staging / "structure.json").write_text(_pretty_json(snapshot), encoding="utf-8")
            sealed = self._seal_record(record)
            (staging / "record.json").write_text(_pretty_json(sealed), encoding="utf-8")
            os.replace(staging, target)
            return record
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def _save_record(self, run_id: str, record: dict[str, Any]) -> None:
        target = self._run_dir(run_id) / "record.json"
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(_pretty_json(self._seal_record(record)), encoding="utf-8")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _load_record(self, run_id: str) -> dict[str, Any]:
        normalized = _run_id(run_id)
        try:
            record = json.loads((self._run_dir(normalized) / "record.json").read_text("utf-8"))
        except FileNotFoundError as exc:
            raise TemplatePackPublishError("Validation run was not found.") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise TemplatePackPublishError("Validation run record is corrupt.") from exc
        seal = record.pop("recordSha256", "")
        if record.get("storeSchemaVersion") != PUBLISH_STORE_SCHEMA_VERSION:
            raise TemplatePackPublishError("Validation run schema is unsupported.")
        if seal != canonical_sha256(record):
            raise TemplatePackPublishError("Validation run record checksum is invalid.")
        if record.get("runId") != normalized:
            raise TemplatePackPublishError("Validation run identity is invalid.")
        return record

    def _load_snapshot(self, run_id: str, record: dict[str, Any]) -> dict[str, Any]:
        try:
            snapshot = json.loads(
                (self._run_dir(run_id) / "structure.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise TemplatePackPublishError("Structural baseline is missing or corrupt.") from exc
        if _json_sha256(snapshot) != record["validation"]["structuralSha256"]:
            raise TemplatePackPublishError("Structural baseline checksum is invalid.")
        return snapshot

    def _verify_artifact(
        self, run_id: str, record: dict[str, Any], claimed_sha256: str = ""
    ) -> bytes:
        try:
            data = (self._run_dir(run_id) / "artifact.docx").read_bytes()
        except OSError as exc:
            raise TemplatePackPublishError("Validation artifact is missing.") from exc
        actual = hashlib.sha256(data).hexdigest()
        expected = record["validation"]["artifactSha256"]
        if actual != expected:
            raise TemplatePackPublishError("Validation artifact checksum is invalid.")
        if claimed_sha256 and claimed_sha256.strip().lower() != expected:
            raise TemplatePackPublishError("Reviewed artifact checksum does not match this run.")
        return data

    def _restore_run(self, record: dict[str, Any]) -> TemplatePackValidationRun:
        validation = record["validation"]
        artifact = self._verify_artifact(record["runId"], record)
        snapshot = self._load_snapshot(record["runId"], record)
        issues = tuple(
            ValidationIssue(
                code=item.get("code", ""),
                message=item.get("message", ""),
                semantic=item.get("semantic", ""),
                path=item.get("path", ""),
                expected=item.get("expected"),
                actual=item.get("actual"),
            )
            for item in validation.get("issues", [])
        )
        return TemplatePackValidationRun(
            run_id=validation["runId"],
            fixture_id=validation["fixtureId"],
            report_type=validation["reportType"],
            candidate_pack_sha256=validation["candidatePackSha256"],
            template_sha256=validation["templateSha256"],
            request_signature=validation["requestSignature"],
            content_signature=validation["contentSignature"],
            artifact_sha256=validation["artifactSha256"],
            structural_sha256=validation["structuralSha256"],
            baseline_sha256=validation["baselineSha256"],
            fixture_passed=validation["fixturePassed"],
            integrity_passed=validation["integrityPassed"],
            structural_passed=validation["structuralPassed"],
            issues=issues,
            manifest=validation["manifest"],
            structural_snapshot=snapshot,
            artifact_bytes=artifact,
        )

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_root / _run_id(run_id)

    @staticmethod
    def _seal_record(record: dict[str, Any]) -> dict[str, Any]:
        result = json.loads(json.dumps(record, ensure_ascii=False))
        result["recordSha256"] = canonical_sha256(result)
        return result

    @staticmethod
    def _public_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "runId": record["runId"],
            "workspaceId": record["workspaceId"],
            "workspaceRevision": record["workspaceRevision"],
            "baselineRunId": record.get("baselineRunId", ""),
            "createdAt": record["createdAt"],
            "state": record["state"],
            "validation": record["validation"],
            "baselineApproval": record.get("baselineApproval"),
            "legacyRendererUnchanged": True,
        }


def _run_id(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise TemplatePackPublishError("Validation run id is invalid.")
    return normalized


def _reviewer(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 128:
        raise TemplatePackPublishError("Reviewer identity is required (1-128 chars).")
    return normalized


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
