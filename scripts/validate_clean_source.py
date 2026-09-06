"""Validate that a clean Reporter Pro source tree is clone/setup ready."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = (
    "VERSION",
    ".env.example",
    "setup.bat",
    "start.bat",
    "scripts/setup.ps1",
    "scripts/start-reporter.ps1",
    "apps/backend/main.py",
    "apps/backend/requirements.lock.txt",
    "apps/backend/requirements-dev.lock.txt",
    "apps/frontend/package.json",
    "apps/frontend/package-lock.json",
)
FORBIDDEN_PARTS = frozenset({".venv", "node_modules", "__pycache__", ".git"})
FORBIDDEN_PREFIXES = ("apps/backend/data/", "logs/", "artifacts/")
FORBIDDEN_FILES = frozenset({".env", "BUNDLE-MANIFEST.json"})
ALLOWED_RUNTIME_PATHS = frozenset({"artifacts/README.md"})


def validate_source_tree(root: Path) -> list[str]:
    root = root.resolve()
    issues = [
        f"Missing required source path: {item}" for item in REQUIRED if not (root / item).exists()
    ]
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if relative in ALLOWED_RUNTIME_PATHS:
            continue
        if any(part in FORBIDDEN_PARTS for part in path.relative_to(root).parts):
            issues.append(f"Generated dependency/cache path is present: {relative}")
        elif relative.startswith(FORBIDDEN_PREFIXES):
            issues.append(f"Runtime artifact path is present: {relative}")
        elif path.name in FORBIDDEN_FILES:
            issues.append(f"Local-only file is present: {relative}")

    env_example = root / ".env.example"
    if env_example.is_file() and "AUTO_REPORT_TEMPLATE_PACKS=1" not in env_example.read_text(
        encoding="utf-8"
    ):
        issues.append("Template Studio must be available in .env.example")

    package_lock = root / "apps/frontend/package-lock.json"
    if package_lock.is_file():
        try:
            lock = json.loads(package_lock.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append("Frontend package-lock.json is invalid JSON")
        else:
            if int(lock.get("lockfileVersion", 0)) < 3:
                issues.append("Frontend package-lock.json must use lockfileVersion >= 3")
    return sorted(set(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    issues = validate_source_tree(arguments.root)
    if issues:
        print("Clean source validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Clean source tree contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
