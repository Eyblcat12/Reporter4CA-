"""Small, dependency-free performance measurements for report workloads.

The collector deliberately accepts only aggregate scalar metadata.  Report rows,
hostnames, notes, evidence and other source content must never be written to a
performance artifact.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping

try:
    import resource
except ModuleNotFoundError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]


METRICS_SCHEMA_VERSION = 1
_SAFE_METADATA_KEYS = {
    "assetCount",
    "auditMode",
    "cacheState",
    "clientCount",
    "featureFlags",
    "fixtureHash",
    "fixtureId",
    "fixtureProfile",
    "operation",
    "pluginCount",
    "preparedFallback",
    "reportType",
    "serverCount",
    "templateHash",
    "trial",
    "wordFieldUpdater",
}
_SAFE_PHASE_ATTRIBUTES = {
    "bytes",
    "cacheHit",
    "count",
    "outcome",
    "rows",
}
_SENSITIVE_KEY_FRAGMENTS = {
    "assetdata",
    "evidence",
    "hostname",
    "ioc",
    "note",
    "payload",
    "raw",
    "rowdata",
}
_SAFE_AGGREGATE_NAMES = {"buildCheckpoint", "tableCreate", "tableStyle"}
_SAFE_TABLE_CATEGORIES = {
    "assetDetail",
    "assetInventory",
    "assetSummary",
    "findings",
    "incidentActions",
    "incidentAssets",
    "incidentMetadata",
    "ioc",
    "mitre",
    "other",
    "remediation",
    "rows",
    "timeline",
}


def _safe_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _contains_sensitive_fragment(key: str) -> bool:
    normalized = "".join(character for character in key.casefold() if character.isalnum())
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def sanitize_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    allowed_keys: set[str] | frozenset[str] = frozenset(_SAFE_METADATA_KEYS),
) -> dict[str, Any]:
    """Return only explicitly allowed, non-sensitive aggregate metadata.

    Unknown keys are ignored instead of serialized. This makes metrics opt-in and
    prevents a future caller from accidentally persisting report input.
    """

    safe: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        name = str(key)
        if name not in allowed_keys or _contains_sensitive_fragment(name):
            continue
        if _safe_scalar(value):
            safe[name] = value
            continue
        if isinstance(value, Mapping):
            nested = {
                str(nested_key): nested_value
                for nested_key, nested_value in value.items()
                if _safe_scalar(nested_value) and not _contains_sensitive_fragment(str(nested_key))
            }
            safe[name] = dict(sorted(nested.items()))
    return safe


def sanitize_phase_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    """Allow only aggregate counters and a bounded outcome vocabulary."""

    safe: dict[str, Any] = {}
    for key, value in (attributes or {}).items():
        name = str(key)
        if name not in _SAFE_PHASE_ATTRIBUTES or _contains_sensitive_fragment(name):
            continue
        if name in {"bytes", "count", "rows"}:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                safe[name] = value
        elif name == "cacheHit":
            if isinstance(value, bool):
                safe[name] = value
        elif name == "outcome" and value in {"passed", "failed", "cancelled", "deferred"}:
            safe[name] = value
    return safe


@dataclass(frozen=True)
class PhaseMeasurement:
    """One non-overlapping benchmark phase."""

    name: str
    latency_class: str
    duration_ms: float
    attributes: dict[str, Any]
    depth: int = 0

    def public(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "latencyClass": self.latency_class,
            "durationMs": round(self.duration_ms, 3),
        }
        if self.attributes:
            result["attributes"] = self.attributes
        if self.depth:
            result["nested"] = True
        return result


class PerformanceMetrics:
    """Thread-safe phase collector using a monotonic high-resolution clock."""

    def __init__(
        self,
        *,
        run_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
    ) -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self.metadata = sanitize_metadata(metadata)
        self._clock_ns = clock_ns
        self._created_ns = clock_ns()
        self._measurements: list[PhaseMeasurement] = []
        self._aggregates: dict[tuple[str, str], dict[str, float | int]] = {}
        self._lock = threading.Lock()
        self._local = threading.local()

    def update_metadata(self, metadata: Mapping[str, Any]) -> None:
        """Merge additional safe aggregates discovered after a run starts."""

        safe = sanitize_metadata(metadata)
        if not safe:
            return
        with self._lock:
            self.metadata.update(safe)

    @contextmanager
    def phase(
        self,
        name: str,
        *,
        latency_class: str = "product",
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[None]:
        """Measure a phase even when its operation raises.

        Product phases contribute to user-visible report latency. Audit phases are
        benchmark-only checks such as reopening and inspecting a saved DOCX.
        """

        if latency_class not in {"product", "audit"}:
            raise ValueError("latency_class must be 'product' or 'audit'")
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("phase name must not be empty")
        depth = int(getattr(self._local, "depth", 0))
        self._local.depth = depth + 1
        started_ns = self._clock_ns()
        try:
            yield
        finally:
            finished_ns = self._clock_ns()
            self._local.depth = depth
            safe_attributes = sanitize_phase_attributes(attributes)
            measurement = PhaseMeasurement(
                name=normalized_name,
                latency_class=latency_class,
                duration_ms=max(0, finished_ns - started_ns) / 1_000_000,
                attributes=safe_attributes,
                depth=depth,
            )
            with self._lock:
                self._measurements.append(measurement)

    def record(
        self,
        name: str,
        duration_ms: float,
        *,
        latency_class: str = "product",
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Record an externally measured phase, primarily queue wait time."""

        if latency_class not in {"product", "audit"}:
            raise ValueError("latency_class must be 'product' or 'audit'")
        if duration_ms < 0:
            raise ValueError("duration_ms must not be negative")
        measurement = PhaseMeasurement(
            name=str(name).strip(),
            latency_class=latency_class,
            duration_ms=float(duration_ms),
            attributes=sanitize_phase_attributes(attributes),
            depth=0,
        )
        if not measurement.name:
            raise ValueError("phase name must not be empty")
        with self._lock:
            self._measurements.append(measurement)

    def record_aggregate(
        self,
        name: str,
        category: str,
        duration_ms: float,
        *,
        count: int = 1,
    ) -> None:
        """Accumulate high-volume timings without one event per table or row."""

        if name not in _SAFE_AGGREGATE_NAMES:
            raise ValueError(f"Unsupported aggregate metric: {name}")
        safe_category = category if category in _SAFE_TABLE_CATEGORIES else "other"
        if duration_ms < 0 or count < 1:
            raise ValueError("Aggregate duration/count must be positive")
        key = (name, safe_category)
        with self._lock:
            current = self._aggregates.setdefault(
                key,
                {"count": 0, "totalDurationMs": 0.0, "maxDurationMs": 0.0},
            )
            current["count"] = int(current["count"]) + count
            current["totalDurationMs"] = float(current["totalDurationMs"]) + duration_ms
            current["maxDurationMs"] = max(float(current["maxDurationMs"]), duration_ms)

    def public(
        self,
        *,
        product_latency_ms: float | None = None,
        audit_latency_ms: float | None = None,
    ) -> dict[str, Any]:
        """Return a stable JSON-compatible payload without source data."""

        with self._lock:
            measurements = list(self._measurements)
            aggregates = [
                {
                    "name": name,
                    "category": category,
                    "count": int(values["count"]),
                    "totalDurationMs": round(float(values["totalDurationMs"]), 3),
                    "maxDurationMs": round(float(values["maxDurationMs"]), 3),
                }
                for (name, category), values in sorted(self._aggregates.items())
            ]
            metadata = {
                key: dict(value) if isinstance(value, dict) else value
                for key, value in self.metadata.items()
            }
        product_total = sum(
            item.duration_ms
            for item in measurements
            if item.latency_class == "product" and item.depth == 0
        )
        audit_total = sum(
            item.duration_ms
            for item in measurements
            if item.latency_class == "audit" and item.depth == 0
        )
        elapsed_ms = max(0, self._clock_ns() - self._created_ns) / 1_000_000
        return {
            "schemaVersion": METRICS_SCHEMA_VERSION,
            "runId": self.run_id,
            "metadata": metadata,
            "productLatencyMs": round(
                product_total if product_latency_ms is None else product_latency_ms,
                3,
            ),
            "auditLatencyMs": round(
                audit_total if audit_latency_ms is None else audit_latency_ms,
                3,
            ),
            "wallElapsedMs": round(elapsed_ms, 3),
            "phases": [item.public() for item in measurements],
            "aggregates": aggregates,
        }


def emit_performance_metrics(
    metrics: PerformanceMetrics,
    *,
    outcome: str,
    logger_name: str = "reporter.performance",
) -> dict[str, Any]:
    """Write one sanitized JSON record to the application's rotating logger."""

    normalized_outcome = outcome if outcome in {"passed", "failed", "cancelled"} else "failed"
    payload = metrics.public()
    payload["outcome"] = normalized_outcome
    logging.getLogger(logger_name).info(
        "performance_metrics %s",
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )
    return payload


def current_rss_mib() -> float:
    """Return the current process resident/working-set size in MiB."""

    if os.name == "nt":
        counters = _windows_memory_counters()
        return counters.WorkingSetSize / 1024 / 1024 if counters else 0.0
    statm = os.path.join("/proc", "self", "statm")
    if os.path.isfile(statm):
        with open(statm, encoding="ascii") as handle:
            resident_pages = int(handle.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE") / 1024 / 1024
    return 0.0


def peak_rss_mib() -> float:
    """Return peak resident/working-set memory for the current process in MiB."""

    if os.name == "nt":
        counters = _windows_memory_counters()
        return counters.PeakWorkingSetSize / 1024 / 1024 if counters else 0.0
    if resource is None:
        return current_rss_mib()
    peak = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if platform.system() == "Darwin":
        return peak / 1024 / 1024
    return peak / 1024


class _ProcessMemoryCounters(ctypes.Structure):
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


def _windows_memory_counters() -> _ProcessMemoryCounters | None:
    if os.name != "nt":
        return None
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.c_void_p
    get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_memory_info.restype = ctypes.c_int
    process = get_current_process()
    if not get_memory_info(process, ctypes.byref(counters), counters.cb):
        return None
    return counters
