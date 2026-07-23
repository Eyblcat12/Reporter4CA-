from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from plugins.manager import load_plugins  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
