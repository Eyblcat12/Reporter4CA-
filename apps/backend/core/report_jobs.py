"""Bounded in-process report jobs for the local/team desktop runtime."""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.performance_metrics import PerformanceMetrics, current_rss_mib

TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobCancelled(Exception):
    """Raised cooperatively between report generation phases."""

    def __init__(
        self,
        message: str = "Job was cancelled",
        *,
        code: str = "CANCELLED",
        termination_reason: str = "user_cancelled",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.termination_reason = termination_reason


@dataclass
class ReportJob:
    id: str
    fingerprint: str
    request: dict[str, Any]
    kind: str = "report"
    requires_output: bool = False
    metrics: PerformanceMetrics | None = field(default=None, repr=False)
    context: Any = field(default=None, repr=False)
    failure: BaseException | None = field(default=None, repr=False)
    queued_at_ns: int = field(default_factory=time.perf_counter_ns, repr=False)
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
    termination_reason: str = ""
    elapsed_ms: int = 0
    current_rss_mib: float = 0.0
    peak_rss_mib: float = 0.0
    memory_limit_mib: int | None = None
    timeout_seconds: int | None = None
    integrity: dict[str, Any] = field(default_factory=dict)
    artifact: dict[str, Any] = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    future: Future | None = field(default=None, repr=False)
    on_cancel: Callable[["ReportJob"], None] | None = field(default=None, repr=False)
    resource_cancel_code: str = field(default="", repr=False)
    resource_cancel_message: str = field(default="", repr=False)
    started_at_ns: int = field(default=0, repr=False)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
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
            "terminationReason": self.termination_reason,
            "resources": {
                "elapsedMs": self.elapsed_ms,
                "currentRssMiB": round(self.current_rss_mib, 1),
                "peakRssMiB": round(self.peak_rss_mib, 1),
                "memoryLimitMiB": self.memory_limit_mib,
                "timeoutSeconds": self.timeout_seconds,
            },
            "integrity": self.integrity,
            "requestSignature": str(self.artifact.get("requestSignature", "")),
            "contentSignature": str(self.artifact.get("contentSignature", "")),
            "previewId": str(self.artifact.get("previewId", "")),
            "templateHash": str(self.artifact.get("templateHash", "")),
            "cacheMode": str(self.artifact.get("cacheMode", "")),
            "expiresAt": str(self.artifact.get("expiresAt", "")),
            "fallbackReason": str(self.artifact.get("fallbackReason", "")),
        }


class ReportJobManager:
    """One-worker queue with bounded capacity and active-request deduplication."""

    def __init__(
        self,
        *,
        max_workers: int = 1,
        max_pending: int = 2,
        max_retained: int = 100,
        memory_limit_mib: int | None = None,
        timeout_seconds: int | None = None,
        resource_poll_seconds: float = 0.5,
        resource_sampler: Callable[[], float] = current_rss_mib,
    ) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="report-job"
        )
        self._capacity = max_workers + max_pending
        self._max_retained = max(max_retained, self._capacity)
        self._jobs: dict[str, ReportJob] = {}
        self._lock = threading.RLock()
        self._memory_limit_mib = memory_limit_mib
        self._timeout_seconds = timeout_seconds
        self._resource_poll_seconds = min(max(resource_poll_seconds, 0.05), 5.0)
        self._resource_sampler = resource_sampler

    @staticmethod
    def fingerprint(request: dict[str, Any]) -> str:
        canonical = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def submit(
        self,
        request: dict[str, Any],
        runner: Callable[[ReportJob], dict[str, Any]],
        *,
        metrics: PerformanceMetrics | None = None,
        context: Any = None,
        fingerprint: str | None = None,
        kind: str = "report",
        requires_output: bool = False,
        artifact_metadata: dict[str, Any] | None = None,
        job_id: str | None = None,
        on_accept: Callable[[ReportJob], None] | None = None,
        on_cancel: Callable[[ReportJob], None] | None = None,
    ) -> tuple[ReportJob, bool]:
        fingerprint = fingerprint or f"{kind}:{self.fingerprint(request)}"
        with self._lock:
            self._prune_terminal_jobs()
            for existing in self._jobs.values():
                if existing.fingerprint == fingerprint and existing.status not in TERMINAL_STATES:
                    return existing, True
            active = sum(1 for job in self._jobs.values() if job.status not in TERMINAL_STATES)
            if active >= self._capacity:
                raise RuntimeError("Report job queue is full")
            effective_job_id = job_id or uuid.uuid4().hex[:12]
            if effective_job_id in self._jobs:
                raise RuntimeError("Report job identifier already exists")
            job = ReportJob(
                id=effective_job_id,
                fingerprint=fingerprint,
                request=request,
                kind=kind,
                requires_output=requires_output,
                metrics=metrics,
                context=context,
                artifact=dict(artifact_metadata or {}),
                on_cancel=on_cancel,
                memory_limit_mib=self._memory_limit_mib,
                timeout_seconds=self._timeout_seconds,
            )
            if on_accept is not None:
                on_accept(job)
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
        if job.metrics is not None:
            job.metrics.record(
                "queueWait",
                max(0, time.perf_counter_ns() - job.queued_at_ns) / 1_000_000,
            )
        if job.cancel_event.is_set():
            self._finish_cancelled(job)
            return
        self.update(job, status="running", phase="preparing", progress=5, message="Đang chuẩn bị")
        job.started_at = _now_iso()
        job.started_at_ns = time.perf_counter_ns()
        monitor_stop = threading.Event()
        monitor = threading.Thread(
            target=self._monitor_resources,
            args=(job, monitor_stop),
            name=f"resource-monitor-{job.id}",
            daemon=True,
        )
        monitor.start()
        try:
            result = runner(job)
            with self._lock:
                output_path = str(result.get("outputPath", ""))
                if job.requires_output and (not output_path or not Path(output_path).is_file()):
                    raise RuntimeError("Document job completed without an output artifact")
                job.report_id = str(result.get("reportId", ""))
                job.filename = str(result.get("filename", ""))
                job.output_path = output_path
                job.integrity = dict(result.get("integrity") or {})
                job.artifact = {
                    **job.artifact,
                    **{
                        key: result.get(key)
                        for key in (
                            "fieldEngine",
                            "requestSignature",
                            "contentSignature",
                            "previewId",
                            "templateHash",
                            "cacheMode",
                            "expiresAt",
                            "fallbackReason",
                        )
                        if result.get(key) is not None
                    },
                }
                self._transition_terminal_locked(
                    job,
                    status="completed",
                    phase="completed",
                    progress=100,
                    message="Báo cáo đã sẵn sàng",
                )
        except JobCancelled as exc:
            self._finish_cancelled(job, exc)
        except Exception as exc:
            with self._lock:
                job.failure = exc
                job.error_code = type(exc).__name__
                job.error_message = "Tác vụ tạo báo cáo thất bại."
                self._transition_terminal_locked(
                    job,
                    status="failed",
                    phase="failed",
                    message="Không thể tạo báo cáo",
                )
        finally:
            monitor_stop.set()
            monitor.join(timeout=max(0.1, self._resource_poll_seconds * 2))
            self._sample_resources(job, enforce_limits=False)

    def _monitor_resources(self, job: ReportJob, stop: threading.Event) -> None:
        while not stop.is_set():
            self._sample_resources(job, enforce_limits=True)
            if job.cancel_event.is_set():
                return
            stop.wait(self._resource_poll_seconds)

    def _sample_resources(self, job: ReportJob, *, enforce_limits: bool) -> None:
        try:
            rss_mib = max(0.0, float(self._resource_sampler()))
        except Exception:
            rss_mib = 0.0
        elapsed_ms = (
            max(0, time.perf_counter_ns() - job.started_at_ns) // 1_000_000
            if job.started_at_ns
            else 0
        )
        with self._lock:
            job.elapsed_ms = int(elapsed_ms)
            job.current_rss_mib = rss_mib
            job.peak_rss_mib = max(job.peak_rss_mib, rss_mib)
            if not enforce_limits or job.status in TERMINAL_STATES or job.cancel_event.is_set():
                return
            if job.memory_limit_mib is not None and rss_mib > job.memory_limit_mib:
                job.resource_cancel_code = "MEMORY_LIMIT_EXCEEDED"
                job.resource_cancel_message = "Đã dừng an toàn vì tác vụ vượt giới hạn RAM."
                job.termination_reason = "memory_limit"
            elif job.timeout_seconds is not None and elapsed_ms > job.timeout_seconds * 1_000:
                job.resource_cancel_code = "JOB_TIMEOUT"
                job.resource_cancel_message = "Đã dừng an toàn vì tác vụ vượt thời gian cho phép."
                job.termination_reason = "timeout"
            else:
                return
            job.message = job.resource_cancel_message
            job.updated_at = _now_iso()
            job.cancel_event.set()

    def _finish_cancelled(self, job: ReportJob, exc: JobCancelled | None = None) -> None:
        with self._lock:
            job.error_code = exc.code if exc is not None else "CANCELLED"
            job.error_message = exc.public_message if exc is not None else "Đã hủy theo yêu cầu."
            job.termination_reason = exc.termination_reason if exc is not None else "user_cancelled"
            if job.output_path:
                Path(job.output_path).unlink(missing_ok=True)
                job.output_path = ""
            self._transition_terminal_locked(
                job,
                status="cancelled",
                phase="cancelled",
                message=job.error_message,
            )
            if job.on_cancel is not None:
                job.on_cancel(job)

    def _transition_terminal_locked(
        self,
        job: ReportJob,
        *,
        status: str,
        phase: str,
        message: str,
        progress: int | None = None,
    ) -> None:
        """Perform one idempotent terminal transition under the manager lock."""

        if job.status in TERMINAL_STATES:
            return
        job.status = status
        job.phase = phase
        job.message = message
        if progress is not None:
            job.progress = progress
        job.completed_at = _now_iso()
        job.updated_at = job.completed_at

    def update(self, job: ReportJob, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                if key in {"status", "phase", "progress", "message"}:
                    setattr(job, key, value)
            job.updated_at = _now_iso()

    def check_cancelled(self, job: ReportJob) -> None:
        if job.cancel_event.is_set():
            if job.resource_cancel_code:
                raise JobCancelled(
                    job.resource_cancel_message,
                    code=job.resource_cancel_code,
                    termination_reason=job.termination_reason,
                )
            raise JobCancelled("Đã hủy theo yêu cầu.")

    def get(self, job_id: str) -> ReportJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        """Read one complete public state while holding the manager lock."""

        with self._lock:
            job = self._jobs.get(job_id)
            return job.public() if job is not None else None

    def list(self, limit: int = 20, *, kind: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(
                (job for job in self._jobs.values() if kind is None or job.kind == kind),
                key=lambda item: item.created_at,
                reverse=True,
            )
            return [job.public() for job in jobs[:limit]]

    def cancel(self, job_id: str) -> ReportJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in TERMINAL_STATES:
                return job
            if not job.termination_reason:
                job.termination_reason = "user_cancelled"
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
        with self._lock:
            active_ids = [
                job.id for job in self._jobs.values() if job.status not in TERMINAL_STATES
            ]
        for job_id in active_ids:
            self.cancel(job_id)
        self._executor.shutdown(wait=wait, cancel_futures=True)
