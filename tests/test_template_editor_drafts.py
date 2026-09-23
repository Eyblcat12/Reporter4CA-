import copy
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from apps.backend.core.template_editor_drafts import EditorDraftConflict, EditorDraftStore
from tests import test_api_integration
from tests.test_profile_renderer import _template_for


class EditorDraftTests(unittest.TestCase):
    def test_discard_is_idempotent_and_late_save_cannot_revive_checkpoint(self):
        original = copy.deepcopy(self.workspace)
        self.store.save(self.workspace, "e" * 32, self.payload)
        command = {"operationId": "f" * 32, "expectedDraftRevision": 1, "reason": "discarded"}
        result = self.store.retire(self.workspace, "e" * 32, command)
        self.assertEqual(self.store.retire(self.workspace, "e" * 32, command), result)
        self.assertEqual(self.store.list(self.workspace)["items"], [])
        with self.assertRaises(EditorDraftConflict):
            self.store.save(self.workspace, "e" * 32, self.payload)
        self.assertEqual(self.workspace, original)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM drafts").fetchone()[0], 1)

    def test_approved_retirement_requires_exact_mapping_and_source(self):
        payload = {
            **self.payload,
            "draft": {
                "anchorKey": "token:{{REMEDIATION}}",
                "fields": {"hostname": "1", "ip": "2", "status": "3"},
            },
        }
        self.store.save(self.workspace, "e" * 32, payload)
        command = {"operationId": "f" * 32, "expectedDraftRevision": 1, "reason": "approved"}
        with self.assertRaises(EditorDraftConflict):
            self.store.retire(self.workspace, "e" * 32, command)
        mapped = {
            **self.workspace,
            "revision": 13,
            "slots": [
                {
                    "semantic": "remediation",
                    "anchor": {"kind": "token", "value": "{{REMEDIATION}}"},
                    "fields": [
                        {"source": field, "target": f"column:{index}"}
                        for index, field in enumerate(("hostname", "ip", "status"), 1)
                    ],
                }
            ],
        }
        with self.assertRaises(EditorDraftConflict):
            self.store.retire({**mapped, "templateSha256": "0" * 64}, "e" * 32, command)
        result = self.store.retire(mapped, "e" * 32, command)
        self.assertTrue(result["retired"])

    def test_stale_discard_does_not_hide_newer_draft(self):
        self.store.save(self.workspace, "e" * 32, self.payload)
        self.store.save(
            self.workspace,
            "e" * 32,
            {**self.payload, "operationId": "1" * 32, "expectedDraftRevision": 1},
        )
        with self.assertRaises(EditorDraftConflict):
            self.store.retire(
                self.workspace,
                "e" * 32,
                {"operationId": "f" * 32, "expectedDraftRevision": 1, "reason": "discarded"},
            )
        self.assertEqual(self.store.list(self.workspace)["items"][0]["draftRevision"], 2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "editor_drafts.sqlite3"
        self.store = EditorDraftStore(self.path)
        self.workspace = {
            "workspaceId": "a" * 32,
            "templateSha256": "b" * 64,
            "revision": 12,
            "reportType": "full",
            "coveragePercent": 0,
        }
        self.payload = {
            "sessionId": "c" * 32,
            "operationId": "d" * 32,
            "expectedDraftRevision": 0,
            "baseRevision": 12,
            "templateSha256": "b" * 64,
            "semantic": "remediation",
            "draft": {"anchorKey": "", "fields": {"hostname": "column:"}},
            "baseline": {"anchorKey": "", "fields": {}},
        }

    def test_restart_preserves_incomplete_draft_without_approval(self):
        original = copy.deepcopy(self.workspace)
        self.store.save(self.workspace, "e" * 32, self.payload)
        loaded = EditorDraftStore(self.path).list(self.workspace)["items"][0]
        self.assertEqual(loaded["draft"], self.payload["draft"])
        self.assertEqual(loaded["draftRevision"], 1)
        self.assertEqual(self.workspace, original)

    def test_future_schema_is_not_modified(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(ValueError, "version"):
            self.store.save(self.workspace, "e" * 32, self.payload)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)
            self.assertEqual(
                db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 0
            )

    def test_list_is_paginated_and_isolates_workspaces(self):
        for index in (1, 2):
            self.store.save(
                self.workspace,
                str(index) * 32,
                {
                    **self.payload,
                    "operationId": str(index) * 32,
                },
            )
        page = self.store.list(self.workspace, limit=1)
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(page["nextOffset"], 1)
        other = self.store.list({**self.workspace, "workspaceId": "9" * 32})
        self.assertEqual(other["items"], [])

    def test_response_loss_retry_is_idempotent(self):
        first = self.store.save(self.workspace, "e" * 32, self.payload)
        self.assertEqual(first, self.store.save(self.workspace, "e" * 32, self.payload))
        changed = {**self.payload, "draft": {"anchorKey": "different", "fields": {}}}
        with self.assertRaises(EditorDraftConflict):
            self.store.save(self.workspace, "e" * 32, changed)
        self.assertEqual(len(self.store.list(self.workspace)["items"]), 1)

    def test_two_writers_only_one_commits(self):
        self.store.save(self.workspace, "e" * 32, self.payload)

        def write(operation):
            try:
                self.store.save(
                    self.workspace,
                    "e" * 32,
                    {
                        **self.payload,
                        "expectedDraftRevision": 1,
                        "operationId": operation * 32,
                    },
                )
                return "saved"
            except EditorDraftConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(write, ["1", "2"]))
        self.assertCountEqual(result, ["saved", "conflict"])

    def test_new_revision_is_stale_not_rebased(self):
        self.store.save(self.workspace, "e" * 32, self.payload)
        loaded = self.store.list({**self.workspace, "revision": 13})["items"][0]
        self.assertTrue(loaded["stale"])
        self.assertEqual(loaded["baseRevision"], 12)

    def test_rejects_unknown_data_and_wrong_source_before_creating_database(self):
        for payload in (
            {**self.payload, "tracking": []},
            {**self.payload, "templateSha256": "0" * 64},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.store.save(self.workspace, "e" * 32, payload)
        self.assertFalse(self.path.exists())

    def test_cannot_move_existing_draft_to_another_session(self):
        self.store.save(self.workspace, "e" * 32, self.payload)
        with self.assertRaises(EditorDraftConflict):
            self.store.save(
                self.workspace,
                "e" * 32,
                {
                    **self.payload,
                    "operationId": "f" * 32,
                    "sessionId": "1" * 32,
                    "expectedDraftRevision": 1,
                },
            )


class EditorDraftApiTests(unittest.TestCase):
    setUp = test_api_integration.ApiIntegrationTests.setUp
    tearDown = test_api_integration.ApiIntegrationTests.tearDown

    def test_save_and_restore_do_not_approve_mapping(self):
        source, _ = _template_for("full")
        workspace = self.template_studio.create(
            source, report_type="full", profile_id="draft-test", display_name="Draft test"
        )
        endpoint = f"/api/template-packs/workspaces/{workspace['workspaceId']}/editor-drafts"
        payload = {
            "sessionId": "c" * 32,
            "operationId": "d" * 32,
            "expectedDraftRevision": 0,
            "baseRevision": workspace["revision"],
            "templateSha256": workspace["templateSha256"],
            "semantic": "remediation",
            "draft": {"anchorKey": "", "fields": {"hostname": "column:"}},
            "baseline": {"anchorKey": "", "fields": {}},
        }
        saved = self.client.put(endpoint + "/" + "e" * 32, json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        retry = self.client.put(endpoint + "/" + "e" * 32, json=payload)
        self.assertEqual(saved.json(), retry.json())
        listed = self.client.get(endpoint)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()["items"]), 1)
        self.assertEqual(self.template_studio.get(workspace["workspaceId"]), workspace)
        conflict = self.client.put(
            endpoint + "/" + "e" * 32, json={**payload, "operationId": "f" * 32}
        )
        self.assertEqual(conflict.status_code, 409)
        with patch("api.routes.template_packs_enabled", return_value=False):
            self.assertEqual(self.client.get(endpoint).status_code, 404)
            self.assertEqual(
                self.client.put(endpoint + "/" + "e" * 32, json=payload).status_code, 404
            )
            self.assertEqual(
                self.client.post(endpoint + "/" + "e" * 32 + "/retire", json={}).status_code, 404
            )
        retired = self.client.post(
            endpoint + "/" + "e" * 32 + "/retire",
            json={
                "operationId": "1" * 32,
                "expectedDraftRevision": 1,
                "reason": "discarded",
            },
        )
        self.assertEqual(retired.status_code, 200, retired.text)
        self.assertEqual(self.client.get(endpoint).json()["items"], [])
        self.assertEqual(self.template_studio.get(workspace["workspaceId"]), workspace)
        with patch.object(
            self.template_studio.editor_drafts,
            "save",
            side_effect=sqlite3.OperationalError("disk full secret path"),
        ):
            failure = self.client.put(endpoint + "/" + "e" * 32, json=payload)
            self.assertEqual(failure.status_code, 503)
            self.assertNotIn("secret path", failure.text)
