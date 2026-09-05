"""Benchmark the isolated Profile Renderer with deterministic synthetic packs."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.performance_metrics import current_rss_mib, peak_rss_mib  # noqa: E402
from core.profile_renderer import render_profile_document, save_profile_report_atomic  # noqa: E402
from core.report_snapshot import AcceptedReportSnapshot, PreparedReportSnapshot  # noqa: E402
from core.template_mapping_workspace import TemplateStudioService  # noqa: E402
from core.template_pack_catalog import (  # noqa: E402
    TemplatePackValidationEvidence,
    build_template_pack,
)
from core.template_profiles import COMMON_REQUIREMENTS, REPORT_REQUIREMENTS  # noqa: E402
from docx import Document  # noqa: E402

DEFAULT_COUNTS = (50, 1_000, 10_000, 50_000)
REPORT_TYPES = tuple(REPORT_REQUIREMENTS)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def synthetic_template(report_type: str) -> tuple[bytes, dict[str, dict[str, str]]]:
    document = Document()
    anchors: dict[str, dict[str, str]] = {}
    for semantic in REPORT_REQUIREMENTS[report_type]:
        token = "{{" + semantic.upper().replace(".", "_") + "}}"
        document.add_paragraph(token)
        anchors[semantic] = {"kind": "token", "value": token}
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue(), anchors


def synthetic_pack(
    root: Path, report_type: str, template: bytes, anchors: dict[str, dict[str, str]]
) -> bytes:
    studio = TemplateStudioService(root / "studio")
    workspace = studio.create(
        template,
        report_type=report_type,
        profile_id=f"benchmark-{report_type.replace('_', '-')}",
        display_name=f"Synthetic benchmark {report_type}",
    )
    for semantic in REPORT_REQUIREMENTS[report_type]:
        requirement = COMMON_REQUIREMENTS[semantic]
        workspace = studio.approve(
            workspace["workspaceId"],
            semantic=semantic,
            anchor=anchors[semantic],
            fields=[
                {"source": source, "target": f"column:{index}"}
                for index, source in enumerate(requirement.required_fields, start=1)
            ],
            expected_revision=workspace["revision"],
        )
    evidence = TemplatePackValidationEvidence(
        fixture_id="synthetic-profile-benchmark-v1",
        fixture_passed=True,
        integrity_passed=True,
        visual_approved=True,
        validated_at="2026-09-01T00:00:00+00:00",
        validator_version="synthetic-benchmark/1.0",
        validation_run_id="1" * 64,
        artifact_sha256="2" * 64,
        structural_sha256="3" * 64,
        reviewed_by="benchmark-harness",
        reviewed_at="2026-09-01T00:00:00+00:00",
    )
    return build_template_pack(workspace, template, evidence)


def synthetic_payload(asset_count: int, report_type: str) -> dict[str, Any]:
    server_count = asset_count if report_type == "server_only" else asset_count * 2 // 5
    if report_type == "client_only":
        server_count = 0
    client_count = asset_count - server_count

    def assets(count: int, prefix: str, subnet: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for index in range(count):
            anomaly = index % 20 == 0
            finding = {
                "name": "Synthetic evidence-backed finding",
                "ruleId": "synthetic-finding",
                "severity": "medium",
                "classification": "anomaly",
                "evidence": [{"field": "result", "value": "synthetic-indicator"}],
                "remediation": "Review and contain the affected endpoint.",
            }
            result.append(
                {
                    "hostname": f"{prefix}-{index + 1:06d}",
                    "ip": f"10.{subnet}.{(index // 254) % 254}.{index % 254 + 1}",
                    "os": "Windows Server 2022" if prefix == "SRV" else "Windows 11",
                    "result": "Synthetic anomaly" if anomaly else "No anomaly detected",
                    "assessment": {
                        "classification": "anomaly" if anomaly else "clean",
                        "label": (
                            "Ghi nhận dấu hiệu bất thường"
                            if anomaly
                            else "Không phát hiện dấu hiệu bất thường"
                        ),
                    },
                    "findings": [finding] if anomaly else [],
                }
            )
        return result

    return {
        "servers": assets(server_count, "SRV", 20),
        "clients": assets(client_count, "PC", 30),
        "metadata": {"recommendations": ["Review evidence-backed synthetic findings."]},
    }


def run_worker(config: dict[str, Any]) -> dict[str, Any]:
    asset_count = int(config["assetCount"])
    report_type = str(config["reportType"])
    output = Path(config["outputDocx"])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        template, anchors = synthetic_template(report_type)
        pack = synthetic_pack(root, report_type, template, anchors)
        payload = synthetic_payload(asset_count, report_type)
        accepted = AcceptedReportSnapshot.create(
            rows=[],
            metadata={},
            title="Synthetic Profile Renderer Benchmark",
            organization="Reporter Pro",
            assessment_date="2026-09-01",
            report_type=report_type,
            template_bytes=template,
            template_key="synthetic-profile-benchmark",
        )
        prepared = PreparedReportSnapshot.create(accepted, payload=payload)
        render_started = time.perf_counter()
        rendered = render_profile_document(pack, prepared)
        render_seconds = time.perf_counter() - render_started
        save_started = time.perf_counter()
        save_profile_report_atomic(rendered, output)
        save_seconds = time.perf_counter() - save_started
        expected_assets = len(payload["servers"]) + len(payload["clients"])
        manifest_rows = rendered.manifest.get("rowCounts", {})
        if expected_assets != asset_count or not output.read_bytes().startswith(b"PK"):
            raise RuntimeError("Synthetic benchmark artifact verification failed.")
        return {
            "schemaVersion": 1,
            "status": "passed",
            "assetCount": asset_count,
            "serverCount": len(payload["servers"]),
            "clientCount": len(payload["clients"]),
            "reportType": report_type,
            "renderSeconds": round(render_seconds, 6),
            "saveSeconds": round(save_seconds, 6),
            "totalSeconds": round(render_seconds + save_seconds, 6),
            "outputBytes": output.stat().st_size,
            "outputSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "manifestRowTotal": sum(int(value) for value in manifest_rows.values()),
            "legacyRendererUsed": rendered.manifest.get("legacyRendererUsed"),
        }


def process_rss_mib(pid: int) -> float:
    if os.name != "nt":
        try:
            status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
            line = next(item for item in status.splitlines() if item.startswith("VmRSS:"))
            return int(line.split()[1]) / 1024
        except (OSError, StopIteration, ValueError):
            return 0.0

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    handle = kernel32.OpenProcess(0x0410, False, pid)
    if not handle:
        return 0.0
    try:
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
            return counters.WorkingSetSize / (1024 * 1024)
    finally:
        kernel32.CloseHandle(handle)
    return 0.0


def run_isolated_trial(
    *,
    asset_count: int,
    report_type: str,
    timeout_seconds: int,
    memory_limit_mib: int,
    run_dir: Path,
) -> dict[str, Any]:
    config = run_dir / f".{asset_count}.config.json"
    result_path = run_dir / f"trial-{asset_count}.json"
    docx = run_dir / f".{asset_count}.docx"
    atomic_json(
        config,
        {
            "assetCount": asset_count,
            "reportType": report_type,
            "outputDocx": str(docx),
            "memoryLimitMiB": memory_limit_mib,
            "timeoutSeconds": timeout_seconds,
        },
    )
    started = time.perf_counter()
    peak_rss = 0.0
    termination = ""
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker-config",
            str(config),
            "--worker-output",
            str(result_path),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    while process.poll() is None:
        elapsed = time.perf_counter() - started
        rss = process_rss_mib(process.pid)
        peak_rss = max(peak_rss, rss)
        if memory_limit_mib and rss > memory_limit_mib:
            termination = "memory_limit"
            process.terminate()
            break
        if elapsed > timeout_seconds:
            termination = "timeout"
            process.terminate()
            break
        time.sleep(0.2)
    if termination:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    else:
        process.wait()
    config.unlink(missing_ok=True)
    docx.unlink(missing_ok=True)
    if result_path.is_file():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        result = {
            "schemaVersion": 1,
            "status": "resource_limited" if termination else "failed",
            "assetCount": asset_count,
            "reportType": report_type,
            "terminationReason": termination or "worker_failed",
        }
    result["workerExitCode"] = process.returncode
    result["wallSeconds"] = round(time.perf_counter() - started, 6)
    result["observedPeakRssMiB"] = round(
        max(peak_rss, float(result.get("observedPeakRssMiB", 0.0))), 3
    )
    atomic_json(result_path, result)
    return result


def benchmark(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    counts = tuple(dict.fromkeys(args.asset_counts))
    if not counts or any(count < 1 or count > 50_000 for count in counts):
        raise ValueError("asset counts must be between 1 and 50000")
    if any(count > 1_000 for count in counts) and not args.allow_large:
        raise ValueError("counts above 1000 require --allow-large")
    if args.timeout_seconds < 10 or args.memory_limit_mib < 0:
        raise ValueError("timeout must be >= 10 seconds and memory limit cannot be negative")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = (
        args.output.resolve()
        if args.output
        else ROOT / "artifacts" / "benchmarks" / "profile-renderer" / timestamp / "benchmark.json"
    )
    run_dir = output.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    trials = [
        run_isolated_trial(
            asset_count=count,
            report_type=args.report_type,
            timeout_seconds=args.timeout_seconds,
            memory_limit_mib=args.memory_limit_mib,
            run_dir=run_dir,
        )
        for count in counts
    ]
    report = {
        "schemaVersion": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "benchmarkKind": "synthetic-profile-renderer-capacity",
        "publicationScope": "engineering-only-not-customer-benchmark",
        "reportType": args.report_type,
        "assetCounts": list(counts),
        "timeoutSeconds": args.timeout_seconds,
        "memoryLimitMiB": args.memory_limit_mib,
        "environment": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "logicalCpuCount": os.cpu_count(),
        },
        "trials": trials,
        "completed": all(trial["status"] == "passed" for trial in trials),
    }
    atomic_json(output, report)
    return report, output


def worker(config_path: Path, output_path: Path) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    stopped = threading.Event()
    started = time.perf_counter()

    def watchdog() -> None:
        while not stopped.wait(0.2):
            reason = ""
            memory_limit = int(config["memoryLimitMiB"])
            if memory_limit and current_rss_mib() > memory_limit:
                reason = "memory_limit"
            elif time.perf_counter() - started > int(config["timeoutSeconds"]):
                reason = "timeout"
            if reason:
                atomic_json(
                    output_path,
                    {
                        "schemaVersion": 1,
                        "status": "resource_limited",
                        "assetCount": int(config["assetCount"]),
                        "reportType": str(config["reportType"]),
                        "terminationReason": reason,
                        "observedPeakRssMiB": round(peak_rss_mib(), 3),
                    },
                )
                os._exit(75 if reason == "memory_limit" else 76)

    monitor = threading.Thread(target=watchdog, name="profile-benchmark-watchdog", daemon=True)
    monitor.start()
    try:
        result = run_worker(config)
        result["observedPeakRssMiB"] = round(peak_rss_mib(), 3)
    except Exception as exc:  # noqa: BLE001 - worker emits only sanitized type
        result = {
            "schemaVersion": 1,
            "status": "failed",
            "error": {"code": "profile_benchmark_failed", "type": type(exc).__name__},
        }
        atomic_json(output_path, result)
        return 1
    finally:
        stopped.set()
    atomic_json(output_path, result)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-counts", nargs="+", type=int, default=list(DEFAULT_COUNTS))
    parser.add_argument("--report-type", choices=REPORT_TYPES, default="full")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--memory-limit-mib", type=int, default=3072)
    parser.add_argument("--allow-large", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-config", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker_config or args.worker_output:
        if not args.worker_config or not args.worker_output:
            return 2
        return worker(args.worker_config.resolve(), args.worker_output.resolve())
    try:
        report, output = benchmark(args)
    except (OSError, ValueError) as exc:
        print(f"Profile benchmark setup failed: {exc}", file=sys.stderr)
        return 2
    print(f"Profile Renderer benchmark: {output}")
    for trial in report["trials"]:
        print(
            f"- {trial['assetCount']} assets: {trial['status']}, "
            f"{trial['wallSeconds']}s, peak {trial['observedPeakRssMiB']} MiB"
        )
    return 0 if report["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
