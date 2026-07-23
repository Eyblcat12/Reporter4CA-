"""Bounded in-process report jobs for the local/team desktop runtime."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobCancelled(Exception):
    """Raised cooperatively between report generation phases."""


@dataclass
class ReportJob:
    id: str
    fingerprint: str
    request: dict[str, Any]
    status: str = "queued"
    phase: str = "queued"
    progress: int = 0
    message: str = "Đang chờ xử lý"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    report_id: str = ""
    filename: str = ""
    output_path: str = ""
    error_code: str = ""
    error_message: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    future: Future | None = field(default=None, repr=False)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "phase": self.phase,
            "progress": self.progress,
            "message": self.message,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "reportId": self.report_id,
            "filename": self.filename,
            "downloadReady": self.status == "completed" and bool(self.output_path),
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
        }


class ReportJobManager:
    """One-worker queue with bounded capacity and active-request deduplication."""

    def __init__(self, *, max_workers: int = 1, max_pending: int = 2, max_retained: int = 100) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="report-job")
        self._capacity = max_workers + max_pending
        self._max_retained = max(max_retained, self._capacity)
        self._jobs: dict[str, ReportJob] = {}
        self._lock = threading.RLock()

    @staticmethod
    def fingerprint(request: dict[str, Any]) -> str:
        canonical = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def submit(
        self,
        request: dict[str, Any],
        runner: Callable[[ReportJob], dict[str, Any]],
    ) -> tuple[ReportJob, bool]:
        fingerprint = self.fingerprint(request)
        with self._lock:
            self._prune_terminal_jobs()
            for existing in self._jobs.values():
                if existing.fingerprint == fingerprint and existing.status not in TERMINAL_STATES:
                    return existing, True
            active = sum(1 for job in self._jobs.values() if job.status not in TERMINAL_STATES)
            if active >= self._capacity:
                raise RuntimeError("Report job queue is full")
            job = ReportJob(id=uuid.uuid4().hex[:12], fingerprint=fingerprint, request=request)
            self._jobs[job.id] = job
            job.future = self._executor.submit(self._execute, job, runner)
            return job, False

    def _prune_terminal_jobs(self) -> None:
        excess = len(self._jobs) - self._max_retained + 1
        if excess <= 0:
            return
        terminal = sorted(
            (job for job in self._jobs.values() if job.status in TERMINAL_STATES),
            key=lambda item: item.updated_at,
        )
        for job in terminal[:excess]:
            self._jobs.pop(job.id, None)

    def _execute(self, job: ReportJob, runner: Callable[[ReportJob], dict[str, Any]]) -> None:
        if job.cancel_event.is_set():
            self._finish_cancelled(job)
            return
        self.update(job, status="running", phase="preparing", progress=5, message="Đang chuẩn bị")
        job.started_at = _now_iso()
        try:
            result = runner(job)
            with self._lock:
                job.status = "completed"
                job.phase = "completed"
                job.progress = 100
                job.message = "Báo cáo đã sẵn sàng"
                job.report_id = str(result.get("reportId", ""))
                job.filename = str(result.get("filename", ""))
                job.output_path = str(result.get("outputPath", ""))
                job.completed_at = _now_iso()
                job.updated_at = job.completed_at
        except JobCancelled:
            self._finish_cancelled(job)
        except Exception as exc:
            with self._lock:
                job.status = "failed"
                job.phase = "failed"
                job.message = "Không thể tạo báo cáo"
                job.error_code = type(exc).__name__
                job.error_message = "Tác vụ tạo báo cáo thất bại."
                job.completed_at = _now_iso()
                job.updated_at = job.completed_at

    def _finish_cancelled(self, job: ReportJob) -> None:
        with self._lock:
            job.status = "cancelled"
            job.phase = "cancelled"
            job.message = "Đã hủy an toàn"
            job.error_code = "CANCELLED"
            job.completed_at = _now_iso()
            job.updated_at = job.completed_at
            if job.output_path:
                Path(job.output_path).unlink(missing_ok=True)
                job.output_path = ""

    def update(self, job: ReportJob, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                if key in {"status", "phase", "progress", "message"}:
                    setattr(job, key, value)
            job.updated_at = _now_iso()

    def check_cancelled(self, job: ReportJob) -> None:
        if job.cancel_event.is_set():
            raise JobCancelled()

    def get(self, job_id: str) -> ReportJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [job.public() for job in jobs[:limit]]

    def cancel(self, job_id: str) -> ReportJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in TERMINAL_STATES:
                return job
            job.cancel_event.set()
            job.message = "Đang hủy sau phase hiện tại"
            job.updated_at = _now_iso()
            if job.status == "queued" and job.future and job.future.cancel():
                self._finish_cancelled(job)
            return job

    def reset_for_tests(self) -> None:
        """Cancel and forget jobs; intended only for isolated test instances."""
        with self._lock:
            for job in self._jobs.values():
                job.cancel_event.set()
            self._jobs.clear()

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)
