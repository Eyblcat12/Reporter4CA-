"""Benchmark the real asynchronous Preview Job API with an isolated workspace."""

from __future__ import annotations

import argparse
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import zipfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))
os.environ["AUTO_REPORT_PERF_METRICS"] = "1"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api import routes  # noqa: E402
from core import report_generator  # noqa: E402
from core.database import Database  # noqa: E402
from core.docx_field_updater import FieldUpdateResult  # noqa: E402
from core.performance_metrics import current_rss_mib, peak_rss_mib  # noqa: E402
from core.preview_artifacts import PreviewArtifactRegistry  # noqa: E402
from core.report_generator import ReportType  # noqa: E402
from core.report_jobs import ReportJobManager  # noqa: E402


def _wait_for_preview(
    client: TestClient,
    preview_id: str,
    *,
    timeout_seconds: float,
) -> dict:
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        response = client.get(f"/api/preview-jobs/{preview_id}")
        response.raise_for_status()
        payload = response.json()
        state = payload.get("job") or payload
        if state.get("status") in {"completed", "failed", "cancelled"}:
            return state
        time.sleep(0.05)
    raise TimeoutError(f"Preview did not finish within {timeout_seconds:.0f} seconds")


def run_benchmark(*, cache_state: str, timeout_seconds: float, target_ms: float) -> dict:
    sample = BACKEND / "samples" / "Tracking_2.csv"
    with tempfile.TemporaryDirectory(prefix="reporter-preview-benchmark-") as directory:
        workspace = Path(directory)
        database = Database(workspace / "data" / "reporter.db")
        database.initialize()
        jobs = ReportJobManager(max_workers=1, max_pending=2)
        artifacts = PreviewArtifactRegistry(workspace / "cache" / "previews")
        app = FastAPI()
        app.include_router(routes.router)
        patches = (
            patch.object(routes, "get_db", return_value=database),
            patch.object(routes, "_report_jobs", jobs),
            patch.object(routes, "_preview_artifacts", artifacts),
            patch.object(routes, "preview_jobs_enabled", return_value=True),
            patch.object(routes, "preview_cache_enabled", return_value=True),
            patch.object(
                routes,
                "refresh_docx_fields",
                return_value=FieldUpdateResult(False, "benchmark-deferred", "controlled"),
            ),
            patch.object(
                report_generator,
                "DEFAULT_PREPARED_TEMPLATE_CACHE_ROOT",
                workspace / "cache" / "prepared-templates",
            ),
        )
        try:
            for active in patches:
                active.start()
            report_generator._get_prepared_template_cache.cache_clear()

            template_path = BACKEND / "templates" / "report_template.docx"
            prewarm_ms = 0.0
            if cache_state == "prewarmed":
                warm_started = time.perf_counter()
                report_generator.warm_prepared_template(template_path, ReportType.FULL)
                prewarm_ms = (time.perf_counter() - warm_started) * 1000

            rss_baseline = current_rss_mib()
            with TestClient(app) as client:
                encoded = base64.b64encode(sample.read_bytes()).decode("ascii")
                column_preview = client.post("/api/column-preview", json={
                    "filename": sample.name,
                    "contentBase64": encoded,
                })
                column_preview.raise_for_status()
                imported = client.post("/api/import-file", json={
                    "filename": sample.name,
                    "contentBase64": encoded,
                    "defaultType": "client",
                    "columnMapping": column_preview.json()["suggestedMapping"],
                })
                imported.raise_for_status()
                rows = imported.json()["rows"]
                if len(rows) != 50:
                    raise AssertionError(f"Expected 50 imported rows, received {len(rows)}")

                started = time.perf_counter()
                submitted = client.post("/api/preview-jobs", json={
                    "rows": rows,
                    "reportType": "full",
                    "disablePlugins": True,
                    "clientRequestId": f"benchmark-{cache_state}-preview-50",
                })
                submitted.raise_for_status()
                accepted = submitted.json()
                preview_id = accepted["previewId"]
                job_id = accepted["jobId"]
                state = _wait_for_preview(
                    client,
                    preview_id,
                    timeout_seconds=timeout_seconds,
                )
                preview_ms = (time.perf_counter() - started) * 1000
                if state.get("status") != "completed":
                    raise AssertionError(f"Preview ended as {state.get('status', 'unknown')}")

                response = client.get(f"/api/preview-jobs/{preview_id}/content")
                response.raise_for_status()
                payload = response.content
                if not zipfile.is_zipfile(BytesIO(payload)):
                    raise AssertionError("Preview output is not a valid DOCX package")

                job = jobs.get(job_id)
                metrics = job.metrics.public() if job and job.metrics is not None else {}
                phases = sorted(
                    metrics.get("phases", []),
                    key=lambda item: item.get("durationMs", 0),
                    reverse=True,
                )
                integrity_valid = bool(job and job.integrity.get("valid"))
                return {
                    "schemaVersion": 1,
                    "fixture": sample.name,
                    "assets": len(rows),
                    "reportType": "full",
                    "requestedCacheState": cache_state,
                    "observedCacheState": metrics.get("metadata", {}).get("cacheState", ""),
                    "prewarmMs": round(prewarm_ms, 3),
                    "previewMs": round(preview_ms, 3),
                    "targetPreviewMs": round(target_ms, 3),
                    "productLatencyMs": metrics.get("productLatencyMs", 0),
                    "wallElapsedMs": metrics.get("wallElapsedMs", 0),
                    "rssBaselineMiB": round(rss_baseline, 3),
                    "rssFinalMiB": round(current_rss_mib(), 3),
                    "peakRssMiB": round(peak_rss_mib(), 3),
                    "bytes": len(payload),
                    "integrityValid": integrity_valid,
                    "topPhases": [
                        {"name": item.get("name", ""), "durationMs": item.get("durationMs", 0)}
                        for item in phases[:8]
                    ],
                    "passed": integrity_valid and preview_ms < target_ms,
                }
        finally:
            jobs.shutdown()
            artifacts.shutdown()
            database.close()
            report_generator._get_prepared_template_cache.cache_clear()
            for active in reversed(patches):
                active.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-state", choices=("cold", "prewarmed"), default="prewarmed")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--target-ms", type=float, default=10_000.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce-target", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(
        cache_state=args.cache_state,
        timeout_seconds=max(1.0, args.timeout),
        target_ms=max(1.0, args.target_ms),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if args.enforce_target and not result["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
