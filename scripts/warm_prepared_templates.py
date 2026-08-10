"""Prewarm content-addressed bundled templates during local setup."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.report_generator import warm_bundled_templates  # noqa: E402


def main() -> int:
    results = warm_bundled_templates(BACKEND / "templates")
    summary = {
        "templates": len(results),
        "prepared": sum(item["outcome"] == "prepared" for item in results),
        "disabled": sum(item["outcome"] == "disabled" for item in results),
        "deferred": sum(item["outcome"] == "deferred" for item in results),
        "durationMs": round(sum(item["durationMs"] for item in results), 3),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if not results or summary["deferred"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
