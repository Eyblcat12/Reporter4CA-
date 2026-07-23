"""Long-running, isolated soak test for the local report job runtime.

No workspace database or generated-report directory is used. DOCX artifacts are built
in memory; only the final JSON metrics file is written under artifacts/soak.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import json
import os
import statistics
import sys
import threading
import time
import tracemalloc
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.report_generator import ReportType, generate_report  # noqa: E402
from core.report_jobs import ReportJob, ReportJobManager, TERMINAL_STATES  # noqa: E402


PROFILES = {
    "smoke": {"duration_minutes": 1.0, "rows": 50, "max_jobs": 4, "job_timeout": 180.0, "memory_growth_mb": 128.0},
    "long": {"duration_minutes": 120.0, "rows": 1000, "max_jobs": 0, "job_timeout": 900.0, "memory_growth_mb": 384.0},
}


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Replace a JSON state file atomically so a killed process cannot truncate it."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return False
        ctypes.windll.kernel32.CloseHandle(process)
        return True
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def current_rss_mb() -> float:
    """Return resident/working-set memory without adding a runtime dependency."""
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory_info.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong,
        ]
        get_memory_info.restype = ctypes.c_int
        process = get_current_process()
        if get_memory_info(process, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / 1024 / 1024
        return 0.0
    statm = Path("/proc/self/statm")
    if statm.exists():
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE") / 1024 / 1024
    return 0.0
def reconcile_stale_statuses(directory: Path) -> list[Path]:
    """Mark orphaned running statuses as interrupted on the next harness launch."""
    reconciled: list[Path] = []
    for path in directory.glob("*.status.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if state.get("status") != "running" or process_is_alive(int(state.get("pid", 0))):
                continue
            state.update({
                "status": "interrupted",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
                "reason": "Process exited before writing a terminal result",
            })
            atomic_write_json(path, state)
            reconciled.append(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return reconciled


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def evaluate_thresholds(metrics: dict[str, Any], memory_limit_mb: float) -> list[str]:
    failures: list[str] = []
    if metrics["completed"] < 1:
        failures.append("No report job completed")
    if metrics["timeouts"]:
        failures.append(f"{metrics['timeouts']} job(s) exceeded the timeout")
    if metrics["unexpectedFailures"]:
        failures.append(f"{metrics['unexpectedFailures']} unexpected job failure(s)")
    if metrics["dedupMismatches"]:
        failures.append(f"{metrics['dedupMismatches']} deduplication mismatch(es)")
    if metrics["heapGrowthMb"] > memory_limit_mb:
        failures.append(
            f"Python heap grew {metrics['heapGrowthMb']:.2f} MB; limit is {memory_limit_mb:.2f} MB"
        )
    if metrics.get("rssGrowthMb", 0) > memory_limit_mb:
        failures.append(
            f"Process RSS grew {metrics['rssGrowthMb']:.2f} MB; limit is {memory_limit_mb:.2f} MB"
        )
    return failures


def build_rows(count: int, iteration: int) -> dict[str, Any]:
    servers, clients = [], []
    for index in range(count):
        target = servers if index % 3 == 0 else clients
        is_proxy = index == count - 1 and iteration % 2 == 0
        target.append({
            "type": "server" if target is servers else "client",
            "hostname": f"SOAK-{iteration:04d}-{index:06d}",
            "ip": f"10.{iteration % 250}.{(index // 250) % 250}.{index % 250 + 1}",
            "os": "Windows Server 2022" if target is servers else "Windows 11",
            "result": "Needs review" if is_proxy else "No finding",
            "notes": "Proxifier observed in software inventory" if is_proxy else "Validated by soak fixture",
            "software": "Proxifier 4" if is_proxy else "",
        })
    return {"servers": servers, "clients": clients, "metadata": {"soakIteration": iteration}}


def run_soak(config: dict[str, Any], checkpoint: Any | None = None) -> dict[str, Any]:
    manager = ReportJobManager(max_workers=1, max_pending=2, max_retained=12)
    durations: list[float] = []
    heap_samples: list[float] = []
    rss_samples: list[float] = []
    statuses: dict[str, int] = {state: 0 for state in TERMINAL_STATES}
    submitted = deduplicated = dedup_mismatches = timeouts = unexpected_failures = 0
    iteration = 0
    started = time.perf_counter()
    deadline = started + float(config["duration_minutes"]) * 60
    tracemalloc.start()
    gc.collect()
    baseline_heap = tracemalloc.get_traced_memory()[0]
    baseline_rss = current_rss_mb()
    report_types = list(ReportType)
    iteration_gates: dict[int, threading.Event] = {}

    def runner(job: ReportJob) -> dict[str, Any]:
        gate = iteration_gates.get(int(job.request["iteration"]))
        if gate and not gate.wait(timeout=10):
            raise RuntimeError("deduplication gate timeout")
        manager.check_cancelled(job)
        if job.request.get("plannedFailure"):
            raise RuntimeError("planned soak failure")
        document = generate_report(
            job.request["payload"], title=f"Soak report {job.request['iteration']}",
            organization="Reporter Soak", assessment_date="2026-07-20",
            report_type=ReportType(job.request["reportType"]),
        )
        manager.check_cancelled(job)
        output = BytesIO()
        document.save(output)
        payload = output.getvalue()
        if len(payload) < 1000 or not payload.startswith(b"PK"):
            raise RuntimeError("invalid in-memory DOCX output")
        return {"filename": f"soak-{job.request['iteration']}.docx", "bytes": len(payload)}

    try:
        while time.perf_counter() < deadline:
            if config["max_jobs"] and iteration >= config["max_jobs"]:
                break
            iteration += 1
            planned_failure = iteration % 11 == 0
            planned_cancel = iteration % 7 == 0
            request = {
                "iteration": iteration,
                "reportType": report_types[(iteration - 1) % len(report_types)].value,
                "payload": build_rows(int(config["rows"]), iteration),
                "plannedFailure": planned_failure,
            }
            gate = threading.Event()
            iteration_gates[iteration] = gate
            try:
                job, was_duplicate = manager.submit(request, runner)
                submitted += 1
                duplicate_job, duplicate = manager.submit(request, runner)
                deduplicated += int(duplicate)
                if not duplicate or duplicate_job.id != job.id or was_duplicate:
                    dedup_mismatches += 1
                if planned_cancel:
                    manager.cancel(job.id)
            finally:
                gate.set()

            job_started = time.perf_counter()
            while job.status not in TERMINAL_STATES:
                if time.perf_counter() - job_started > float(config["job_timeout"]):
                    timeouts += 1
                    manager.cancel(job.id)
                    break
                time.sleep(0.05)
            durations.append(time.perf_counter() - job_started)
            statuses[job.status] = statuses.get(job.status, 0) + 1
            expected = "cancelled" if planned_cancel else "failed" if planned_failure else "completed"
            if job.status != expected:
                unexpected_failures += 1
            iteration_gates.pop(iteration, None)
            gc.collect()
            current_heap_mb = tracemalloc.get_traced_memory()[0] / 1024 / 1024
            heap_samples.append(current_heap_mb)
            current_rss = current_rss_mb()
            rss_samples.append(current_rss)
            if checkpoint:
                checkpoint({
                    "iteration": iteration, "submitted": submitted,
                    "completed": statuses.get("completed", 0),
                    "failed": statuses.get("failed", 0),
                    "cancelled": statuses.get("cancelled", 0),
                    "deduplicated": deduplicated, "timeouts": timeouts,
                    "unexpectedFailures": unexpected_failures,
                    "dedupMismatches": dedup_mismatches,
                    "heapCurrentMb": round(current_heap_mb, 3),
                    "rssCurrentMb": round(current_rss, 3),
                    "elapsedSeconds": round(time.perf_counter() - started, 3),
                })
    finally:
        manager.shutdown(wait=True)

    current_heap, peak_heap = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started
    metrics = {
        "profile": config["profile"], "elapsedSeconds": round(elapsed, 3),
        "configuredRows": int(config["rows"]), "submitted": submitted,
        "completed": statuses.get("completed", 0), "failed": statuses.get("failed", 0),
        "cancelled": statuses.get("cancelled", 0), "deduplicated": deduplicated,
        "dedupMismatches": dedup_mismatches, "timeouts": timeouts,
        "unexpectedFailures": unexpected_failures,
        "durationSeconds": {
            "min": round(min(durations, default=0), 3),
            "p50": round(percentile(durations, 0.50), 3),
            "p95": round(percentile(durations, 0.95), 3),
            "max": round(max(durations, default=0), 3),
        },
        "heapBaselineMb": round(baseline_heap / 1024 / 1024, 3),
        "heapFinalMb": round(current_heap / 1024 / 1024, 3),
        "heapPeakMb": round(peak_heap / 1024 / 1024, 3),
        "heapGrowthMb": round((current_heap - baseline_heap) / 1024 / 1024, 3),
        "heapSamplesMb": [round(value, 3) for value in heap_samples],
        "rssBaselineMb": round(baseline_rss, 3),
        "rssFinalMb": round(current_rss_mb(), 3),
        "rssPeakMb": round(max(rss_samples, default=baseline_rss), 3),
    }
    metrics["rssGrowthMb"] = round(metrics["rssFinalMb"] - baseline_rss, 3)
    metrics["failures"] = evaluate_thresholds(metrics, float(config["memory_growth_mb"]))
    metrics["passed"] = not metrics["failures"]
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reporter Pro local report-job soak test")
    parser.add_argument("--profile", choices=PROFILES, default="long")
    parser.add_argument("--duration-minutes", type=float)
    parser.add_argument("--rows", type=int)
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--job-timeout", type=float)
    parser.add_argument("--memory-growth-mb", type=float)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = {"profile": args.profile, **PROFILES[args.profile]}
    for key in ("duration_minutes", "rows", "max_jobs", "job_timeout", "memory_growth_mb"):
        value = getattr(args, key)
        if value is not None:
            config[key] = value
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = args.output or ROOT / "artifacts" / "soak" / f"soak-{args.profile}-{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    reconcile_stale_statuses(output.parent)
    status_path = output.with_suffix(".status.json")
    checkpoint_path = output.with_suffix(".checkpoint.json")
    started_at = datetime.now(timezone.utc).isoformat()
    base_status = {
        "status": "running", "pid": os.getpid(), "startedAt": started_at,
        "config": config, "output": str(output), "checkpoint": str(checkpoint_path),
    }
    atomic_write_json(status_path, base_status)

    def save_checkpoint(progress: dict[str, Any]) -> None:
        heartbeat = datetime.now(timezone.utc).isoformat()
        atomic_write_json(checkpoint_path, {
            "status": "running", "pid": os.getpid(), "startedAt": started_at,
            "heartbeatAt": heartbeat, "config": config, "progress": progress,
        })
        atomic_write_json(status_path, {**base_status, "heartbeatAt": heartbeat, "progress": progress})

    try:
        metrics = run_soak(config, checkpoint=save_checkpoint)
    except KeyboardInterrupt:
        terminal = {
            **base_status, "status": "interrupted",
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "reason": "Interrupted by operator", "lastCheckpoint": str(checkpoint_path),
        }
        atomic_write_json(status_path, terminal)
        atomic_write_json(checkpoint_path, terminal)
        return 130
    except Exception as exc:
        terminal = {
            **base_status, "status": "failed",
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "reason": type(exc).__name__, "lastCheckpoint": str(checkpoint_path),
        }
        atomic_write_json(status_path, terminal)
        atomic_write_json(checkpoint_path, terminal)
        raise
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "config": config, "metrics": metrics}
    atomic_write_json(output, report)
    terminal = {
        "status": "completed" if metrics["passed"] else "failed", "pid": os.getpid(),
        "finishedAt": datetime.now(timezone.utc).isoformat(), "output": str(output),
        "passed": metrics["passed"], "failures": metrics["failures"],
        "lastCheckpoint": str(checkpoint_path),
    }
    atomic_write_json(status_path, terminal)
    atomic_write_json(checkpoint_path, {**terminal, "metrics": metrics})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Soak report: {output}")
    return 0 if metrics["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
