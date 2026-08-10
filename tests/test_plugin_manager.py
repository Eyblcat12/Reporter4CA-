from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from plugins.manager import combined_cache_policy, load_plugins, plugin_manifest  # noqa: E402


class PluginManagerTests(unittest.TestCase):
    def test_loader_ignores_its_own_manager_module(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            (plugin_dir / "manager.py").write_text(
                "raise RuntimeError('manager must never be loaded')\n",
                encoding="utf-8",
            )
            (plugin_dir / "sample.py").write_text(
                """
class Plugin:
    def name(self):
        return "Sample"
    def process_input(self, data):
        return data
    def modify_document(self, document, data):
        return document
""",
                encoding="utf-8",
            )

            plugins = load_plugins(plugin_dir, strict=True)
            self.assertEqual([plugin.name() for plugin in plugins], ["Sample"])
            manifest = plugin_manifest(plugins)
            self.assertEqual(manifest[0]["pluginId"], "Sample")
            self.assertEqual(manifest[0]["cachePolicy"], "volatile")
            self.assertEqual(len(manifest[0]["sourceHash"]), 64)
            self.assertEqual(combined_cache_policy(manifest), "volatile")

    def test_manifest_uses_declared_identity_and_strictest_cache_policy(self) -> None:
        class Deterministic:
            plugin_id = "stable"
            version = "2.1"
            cache_policy = "deterministic"
            _reporter_source_hash = "a" * 64

            def name(self):
                return "Display Name"

            def cache_identity(self, config):
                return {"mode": config.get("mode", "default")}

        class NoStore(Deterministic):
            plugin_id = "external"
            cache_policy = "no_store"

        manifest = plugin_manifest(
            [Deterministic(), NoStore()],
            {"stable": {"mode": "strict"}},
        )
        self.assertEqual(manifest[0]["cacheIdentity"], {"mode": "strict"})
        self.assertEqual(combined_cache_policy(manifest), "no_store")

    def test_invalid_cache_policy_is_rejected_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory)
            (plugin_dir / "invalid.py").write_text(
                """
class Plugin:
    cache_policy = "forever"
    def name(self): return "Invalid"
    def process_input(self, data): return data
    def modify_document(self, document, data): return document
""",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_plugins(plugin_dir, strict=True)


if __name__ == "__main__":
    unittest.main()
