"""Verify that Template Studio remains isolated from Reporter Pro's default flow."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_PATHS = frozenset(
    {
        "apps/backend/core/report_generator.py",
        "apps/backend/core/report_orchestrator.py",
        "apps/backend/core/report_snapshot.py",
    }
)
PROTECTED_PREFIXES = ("apps/backend/templates/",)
FORBIDDEN_TRACKED_PREFIXES = (
    "apps/backend/data/",
    "artifacts/",
    "logs/",
)
FORBIDDEN_TRACKED_NAMES = frozenset({".env", ".env.local"})
FORBIDDEN_TRACKED_SUFFIXES = (".generated.docx", ".db", ".sqlite", ".sqlite3")
ALLOWED_TRACKED_ARTIFACT_PATHS = frozenset({"artifacts/README.md"})


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str


def normalize_repo_path(value: str) -> str:
    normalized = PurePosixPath(value.replace("\\", "/")).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized == "." or normalized.startswith("../"):
        raise ValueError(f"Unsafe repository path: {value}")
    return normalized


def protected_diff_violations(changes: Iterable[ChangedPath]) -> list[str]:
    violations: list[str] = []
    for change in changes:
        path = normalize_repo_path(change.path)
        if path in PROTECTED_PATHS or path.startswith(PROTECTED_PREFIXES):
            violations.append(f"{change.status}\t{path}")
    return sorted(set(violations))


def forbidden_tracked_violations(paths: Iterable[str]) -> list[str]:
    violations: list[str] = []
    for candidate in paths:
        path = normalize_repo_path(candidate)
        if path in ALLOWED_TRACKED_ARTIFACT_PATHS:
            continue
        name = PurePosixPath(path).name
        lower = path.lower()
        if (
            path.startswith(FORBIDDEN_TRACKED_PREFIXES)
            or name in FORBIDDEN_TRACKED_NAMES
            or lower.endswith(FORBIDDEN_TRACKED_SUFFIXES)
        ):
            violations.append(path)
    return sorted(set(violations))


def static_contract_violations(root: Path = ROOT) -> list[str]:
    violations: list[str] = []
    env_text = (root / ".env.example").read_text(encoding="utf-8")
    if not re.search(r"(?m)^AUTO_REPORT_TEMPLATE_PACKS=0$", env_text):
        violations.append(".env.example must keep AUTO_REPORT_TEMPLATE_PACKS=0")
    if not re.search(r"(?m)^VITE_TEMPLATE_STUDIO=0$", env_text):
        violations.append(".env.example must keep VITE_TEMPLATE_STUDIO=0")

    config_text = (root / "apps/backend/core/config.py").read_text(encoding="utf-8")
    if not re.search(r'os\.getenv\(\s*"AUTO_REPORT_TEMPLATE_PACKS"\s*,\s*"0"\s*\)', config_text):
        violations.append("Backend feature-flag fallback must remain disabled (0)")

    app_text = (root / "apps/frontend/src/App.jsx").read_text(encoding="utf-8")
    if "import.meta.env.VITE_TEMPLATE_STUDIO === '1'" not in app_text:
        violations.append("Frontend Template Studio route must require an explicit 1 flag")

    for relative in PROTECTED_PATHS:
        text = (root / relative).read_text(encoding="utf-8")
        if re.search(r"(?m)^\s*(?:from|import)\s+.*template_(?:pack|profile)", text):
            violations.append(f"Legacy module imports Template Pack runtime: {relative}")
    return violations


def parse_name_status_z(payload: bytes) -> list[ChangedPath]:
    fields = payload.decode("utf-8", errors="strict").split("\0")
    result: list[ChangedPath] = []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index]
        index += 1
        if index >= len(fields) or not fields[index]:
            raise ValueError("Incomplete git name-status payload")
        first_path = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            if index >= len(fields) or not fields[index]:
                raise ValueError("Incomplete git rename/copy payload")
            result.append(ChangedPath(status=status, path=first_path))
            result.append(ChangedPath(status=status, path=fields[index]))
            index += 1
        else:
            result.append(ChangedPath(status=status, path=first_path))
    return result


def git_output(root: Path, *arguments: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
    )
    if process.returncode:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"git {' '.join(arguments)} failed")
    return process.stdout


def repository_violations(root: Path = ROOT, base_ref: str = "") -> list[str]:
    tracked = git_output(root, "ls-files", "-z").decode("utf-8").split("\0")
    violations = [
        f"Forbidden tracked runtime/customer artifact: {path}"
        for path in forbidden_tracked_violations(path for path in tracked if path)
    ]
    violations.extend(static_contract_violations(root))
    if base_ref:
        changes = parse_name_status_z(
            git_output(root, "diff", "--name-status", "-z", f"{base_ref}...HEAD")
        )
        violations.extend(
            f"Protected default-flow path changed: {item}"
            for item in protected_diff_violations(changes)
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Template Studio's disabled-by-default merge boundary."
    )
    parser.add_argument(
        "--base-ref",
        default="",
        help="Optional trusted merge-base ref/SHA used to protect default templates and renderer.",
    )
    arguments = parser.parse_args()
    try:
        violations = repository_violations(ROOT, arguments.base_ref.strip())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        print(f"Template Studio merge gate could not run: {exc}", file=sys.stderr)
        return 2
    if violations:
        print("Template Studio merge gate failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    suffix = f" against {arguments.base_ref}" if arguments.base_ref else ""
    print(f"Template Studio merge boundary is intact{suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
