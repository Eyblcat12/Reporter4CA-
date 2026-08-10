"""Validate and summarize repeated Preview Job benchmark result files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


def percentile(values: Iterable[float], percent: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("At least one sample is required")
    position = (len(ordered) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def metric_summary(values: Iterable[float], *, publish_p95: bool) -> dict[str, Any]:
    samples = [float(value) for value in values]
    return {
        "min": round(min(samples), 3),
        "p50": round(percentile(samples, 0.50), 3),
        "p95": round(percentile(samples, 0.95), 3) if publish_p95 else None,
        "p95Published": publish_p95,
        "max": round(max(samples), 3),
    }


def summarize(directory: Path, *, required_trials: int) -> dict[str, Any]:
    paths = sorted(directory.glob("trial-*.json"))
    if len(paths) != required_trials:
        raise ValueError(f"Expected exactly {required_trials} trial files, found {len(paths)}")
    trials = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    identity_fields = (
        "schemaVersion",
        "fixture",
        "assets",
        "reportType",
        "requestedCacheState",
        "targetPreviewMs",
    )
    baseline = {field: trials[0].get(field) for field in identity_fields}
    for path, trial in zip(paths, trials, strict=True):
        identity = {field: trial.get(field) for field in identity_fields}
        if identity != baseline:
            raise ValueError(f"Incompatible benchmark identity in {path.name}")
        if trial.get("observedCacheState") != "cache-warm/prepared-hit":
            raise ValueError(f"Unexpected cache state in {path.name}")

    target_ms = float(baseline["targetPreviewMs"])
    preview_values = [float(trial["previewMs"]) for trial in trials]
    all_integrity_valid = all(bool(trial.get("integrityValid")) for trial in trials)
    all_under_target = all(value < target_ms for value in preview_values)
    publish_p95 = len(trials) >= 10
    return {
        "schemaVersion": 1,
        "benchmark": "preview-job-api",
        "sampleCount": len(trials),
        "fixture": baseline["fixture"],
        "assets": baseline["assets"],
        "reportType": baseline["reportType"],
        "cacheState": "prewarmed",
        "observedCacheState": "cache-warm/prepared-hit",
        "targetPreviewMs": target_ms,
        "previewMs": metric_summary(preview_values, publish_p95=publish_p95),
        "productLatencyMs": metric_summary(
            (trial["productLatencyMs"] for trial in trials),
            publish_p95=publish_p95,
        ),
        "peakRssMiB": metric_summary(
            (trial["peakRssMiB"] for trial in trials),
            publish_p95=publish_p95,
        ),
        "integrityPasses": sum(bool(trial.get("integrityValid")) for trial in trials),
        "targetPasses": sum(float(trial["previewMs"]) < target_ms for trial in trials),
        "allIntegrityValid": all_integrity_valid,
        "allUnderTarget": all_under_target,
        "releaseGatePassed": all_integrity_valid and all_under_target and publish_p95,
        "trials": [path.name for path in paths],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--required-trials", type=int, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce-gate", action="store_true")
    args = parser.parse_args()
    try:
        result = summarize(args.directory.resolve(), required_trials=max(1, args.required_trials))
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if args.enforce_gate and not result["releaseGatePassed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
