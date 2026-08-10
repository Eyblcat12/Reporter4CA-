from __future__ import annotations

import asyncio
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api.models import GenerateRequest  # noqa: E402
from api.routes import dashboard_summary, generate  # noqa: E402
from core.database import Database  # noqa: E402


class DashboardSummaryTests(unittest.TestCase):
    def test_legacy_report_history_is_migrated_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(path)
            connection.execute(
                "CREATE TABLE report_history (id TEXT PRIMARY KEY, created_at TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO report_history(id, created_at) VALUES(?, ?)",
                ("legacy", datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
            connection.close()

            database = Database(path)
            database.initialize()
            row = (
                database._get_conn()
                .execute("SELECT id, status, duration_ms, error_code FROM report_history")
                .fetchone()
            )
            self.assertEqual(tuple(row), ("legacy", "success", 0, ""))
            self.assertEqual(database.schema_version, 9)
            database.close()

    def test_summary_aggregates_success_failure_activity_and_previous_period(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "summary.db")
            database.initialize()
            now = datetime.now(timezone.utc)

            records = [
                ("Current full", "full", 10, "success", 100, now - timedelta(days=5)),
                ("Current summary", "summary", 20, "success", 200, now - timedelta(days=15)),
                ("Current failed", "full", 99, "failed", 50, now - timedelta(days=2)),
                ("Current cancelled", "full", 99, "cancelled", 30, now - timedelta(days=1)),
                ("Previous", "full", 5, "success", 80, now - timedelta(days=40)),
            ]
            for title, report_type, rows, status, duration, created_at in records:
                report_id = database.add_report(
                    title=title,
                    report_type=report_type,
                    row_count=rows,
                    status=status,
                    duration_ms=duration,
                    error_code="RuntimeError" if status == "failed" else "",
                )
                database._execute_commit(
                    "UPDATE report_history SET created_at = ? WHERE id = ?",
                    (created_at.isoformat(), report_id),
                )

            result = database.dashboard_summary(30)
            metrics = result["metrics"]
            self.assertEqual(metrics["reports"], 2)
            self.assertEqual(metrics["attempts"], 4)
            self.assertEqual(metrics["failed"], 1)
            self.assertEqual(metrics["cancelled"], 1)
            self.assertEqual(metrics["assets"], 30)
            self.assertEqual(metrics["reportTypes"], 2)
            self.assertEqual(metrics["avgDurationMs"], 150)
            self.assertEqual(metrics["successRate"], 50.0)
            self.assertEqual(metrics["deltaPercent"], 100)
            self.assertEqual(sum(item["count"] for item in result["series"]), 2)
            self.assertEqual(sum(item["attempts"] for item in result["series"]), 4)
            self.assertEqual(sum(item["failed"] for item in result["series"]), 1)
            self.assertEqual(sum(item["cancelled"] for item in result["series"]), 1)
            self.assertEqual(len(result["series"]), 8)
            self.assertTrue(all("start" in item and "end" in item for item in result["series"]))
            self.assertIn("generatedAt", result)
            self.assertEqual(set(result["range"]), {"start", "end", "previousStart"})
            self.assertLess(
                abs((datetime.fromisoformat(result["series"][-1]["end"]) - now).total_seconds()),
                2,
            )
            self.assertEqual(len(result["recent"]), 5)
            self.assertEqual(len(database.list_reports(limit=None)), 5)
            database.close()

    def test_dashboard_endpoint_validates_period_and_returns_database_result(self) -> None:
        expected = {"days": 90, "metrics": {}, "series": [], "recent": []}
        database = unittest.mock.Mock()
        database.dashboard_summary.return_value = expected
        with patch("api.routes.get_db", return_value=database):
            self.assertEqual(asyncio.run(dashboard_summary(90)), expected)
            database.dashboard_summary.assert_called_once_with(90)

            with self.assertRaises(HTTPException) as context:
                asyncio.run(dashboard_summary(7))
            self.assertEqual(context.exception.status_code, 422)

    def test_job_history_is_exactly_once_and_dashboard_ignores_active_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.db"
            database = Database(path)
            database.initialize()
            report_id = database.add_report(
                title="Queued",
                status="queued",
                job_id="job-unique-1",
                client_request_id="client-1",
                request_signature="request-1",
            )
            self.assertEqual(database.dashboard_summary(30)["metrics"]["attempts"], 0)
            with self.assertRaises(sqlite3.IntegrityError):
                database.add_report(status="queued", job_id="job-unique-1")

            database.update_report_execution(
                report_id,
                status="success",
                output_filename="report.docx",
                file_size=123,
                cache_status="cold_generate",
            )
            database.update_report_execution(report_id, status="success")
            row = database.get_report(report_id)
            self.assertEqual(row["output_filename"], "report.docx")
            self.assertEqual(database.dashboard_summary(30)["metrics"]["attempts"], 1)
            database.close()

    def test_startup_marks_orphaned_active_history_as_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "restart.db"
            database = Database(path)
            database.initialize()
            report_id = database.add_report(status="running", job_id="orphan-job")
            database.close()

            reopened = Database(path)
            reopened.initialize()
            row = reopened.get_report(report_id)
            self.assertEqual(row["status"], "failed")
            self.assertEqual(row["error_code"], "PROCESS_INTERRUPTED")
            reopened.close()

    def test_generation_failure_records_a_safe_error_code(self) -> None:
        database = unittest.mock.Mock()
        database.get_template_by_path.return_value = None
        database.get_default_template.return_value = None
        request = GenerateRequest(
            rows=[{"type": "server", "hostname": "srv-01", "ip": "10.0.0.1"}],
            title="Failure telemetry",
        )
        with (
            patch("api.routes.get_db", return_value=database),
            patch("api.routes._load_plugins", return_value=[]),
            patch("api.routes.generate_report", side_effect=RuntimeError("private detail")),
        ):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(generate(request))

        self.assertEqual(context.exception.status_code, 500)
        recorded = database.add_report.call_args.kwargs
        self.assertEqual(recorded["status"], "failed")
        self.assertEqual(recorded["error_code"], "RuntimeError")
        self.assertEqual(recorded["server_count"], 1)
        self.assertGreaterEqual(recorded["duration_ms"], 0)


if __name__ == "__main__":
    unittest.main()
