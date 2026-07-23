from __future__ import annotations

import importlib.util
import sys
from abc import ABC
from pathlib import Path
from typing import Any


class BasePlugin(ABC):
    version = "0.1.0"

    def name(self) -> str:
        return self.__class__.__name__

    def process_input(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def modify_document(self, document: Any, data: dict[str, Any]) -> Any:
        return document


def load_plugins(directory: str | Path, *, strict: bool = False) -> list[BasePlugin]:
    plugin_dir = Path(directory)
    if not plugin_dir.exists():
        return []

    loaded_plugins: list[BasePlugin] = []
    for file_path in sorted(plugin_dir.glob("*.py")):
        if file_path.name.startswith("_") or file_path.name in {"__init__.py", "manager.py"}:
            continue

        try:
            plugin = _load_plugin(file_path)
            loaded_plugins.append(plugin)
        except Exception as exc:
            if strict:
                raise
            print(f"Bo qua plugin '{file_path.name}': {exc}", file=sys.stderr)

    return loaded_plugins


def apply_input_plugins(data: dict[str, Any], plugins: list[BasePlugin]) -> dict[str, Any]:
    current_data = data
    for plugin in plugins:
        current_data = plugin.process_input(current_data)
        if not isinstance(current_data, dict):
            raise TypeError(f"Plugin '{plugin.name()}' phai tra ve dict cho process_input().")
    return current_data


def apply_document_plugins(document: Any, data: dict[str, Any], plugins: list[BasePlugin]) -> Any:
    current_document = document
    modified_document = False
    for plugin in plugins:
        if _plugin_overrides_document_modifier(plugin):
            modified_document = True
        current_document = plugin.modify_document(current_document, data)
    if modified_document:
        setattr(current_document, "_codex_force_render", True)
    return current_document


def _load_plugin(file_path: Path) -> BasePlugin:
    module_name = f"codex_plugin_{file_path.stem}_{abs(hash(file_path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError("Khong the nap module plugin.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    plugin_class = getattr(module, "Plugin", None)
    if plugin_class is None:
        raise ValueError("Module plugin phai dinh nghia class 'Plugin'.")

    plugin = plugin_class()
    _validate_plugin(plugin)
    return plugin


def _validate_plugin(plugin: Any) -> None:
    if not callable(getattr(plugin, "process_input", None)):
        raise TypeError("Plugin thieu method process_input().")
    if not callable(getattr(plugin, "modify_document", None)):
        raise TypeError("Plugin thieu method modify_document().")
    if not callable(getattr(plugin, "name", None)):
        raise TypeError("Plugin thieu method name().")


def _plugin_overrides_document_modifier(plugin: BasePlugin) -> bool:
    return type(plugin).modify_document is not BasePlugin.modify_document
