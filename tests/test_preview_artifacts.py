from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.preview_artifacts import (  # noqa: E402
    ArtifactCorrupt,
    ArtifactExpired,
    ArtifactStale,
    PreviewArtifactRegistry,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = 1_700_000_000.0

    def __call__(self) -> float:
        return self.value


class PreviewArtifactRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clock = MutableClock()
        self.registry = PreviewArtifactRegistry(
            self.root / "cache",
            ttl_seconds=60,
            max_artifacts=2,
            max_bytes=1024,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _register(self, content: bytes = b"preview", signature: str = "request-a"):
        source = self.root / f"source-{len(list(self.root.glob('source-*')))}.docx"
        source.write_bytes(content)
        return self.registry.register_ready(
            source,
            job_id="job-1",
            request_signature=signature,
            content_signature=f"content-{signature}",
            template_hash="template-a",
        )

    def test_register_moves_into_managed_cache_without_exposing_path(self):
        artifact = self._register()
        public = artifact.public()
        self.assertFalse((self.root / "source-0.docx").exists())
        self.assertTrue(artifact.path.is_file())
        self.assertNotIn("path", public)
        self.assertEqual(public["status"], "ready")

    def test_expired_artifact_cannot_be_leased(self):
        artifact = self._register()
        self.clock.value += 61
        with self.assertRaises(ArtifactExpired):
            with self.registry.lease(artifact.id):
                pass

    def test_signature_mismatch_marks_artifact_stale(self):
        artifact = self._register()
        with self.assertRaises(ArtifactStale):
            with self.registry.lease(artifact.id, request_signature="request-b"):
                pass
        self.assertEqual(self.registry.snapshot(artifact.id)["status"], "stale")

    def test_corrupt_artifact_is_rejected_and_removed(self):
        artifact = self._register()
        artifact.path.write_bytes(b"tampered")
        with self.assertRaises(ArtifactCorrupt):
            with self.registry.lease(artifact.id):
                pass
        self.assertFalse(artifact.path.exists())

    def test_cleanup_does_not_delete_an_active_download_lease(self):
        artifact = self._register()
        with self.registry.lease(artifact.id) as leased:
            self.clock.value += 61
            self.registry.cleanup()
            self.assertTrue(leased.path.exists())
        self.registry.cleanup()
        self.assertFalse(artifact.path.exists())

    def test_lru_quota_evicts_unleased_artifact(self):
        first = self._register(b"one", "request-1")
        self.clock.value += 1
        second = self._register(b"two", "request-2")
        self.clock.value += 1
        third = self._register(b"three", "request-3")
        self.assertIsNone(self.registry.snapshot(first.id))
        self.assertIsNotNone(self.registry.snapshot(second.id))
        self.assertIsNotNone(self.registry.snapshot(third.id))

    def test_find_ready_only_reuses_deterministic_artifact(self):
        artifact = self._register(signature="same")
        self.assertEqual(self.registry.find_ready("same").id, artifact.id)
        artifact.cache_mode = "volatile"
        self.assertIsNone(self.registry.find_ready("same"))

    def test_startup_sweep_only_removes_owned_orphans(self):
        cache = self.root / "startup"
        cache.mkdir()
        owned = cache / "preview-orphan.docx"
        unrelated = cache / "keep.docx"
        owned.write_bytes(b"orphan")
        unrelated.write_bytes(b"keep")
        PreviewArtifactRegistry(cache)
        self.assertFalse(owned.exists())
        self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
