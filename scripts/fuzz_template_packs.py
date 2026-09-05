"""Deterministic long-running fuzz harness for the Template Pack inspector."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import sys
import tempfile
import time
import uuid
import zipfile
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.template_pack import (  # noqa: E402
    MAX_PACK_SIZE,
    TemplatePackError,
    inspect_template_pack,
)
from core.template_pack_catalog import TemplatePackCatalog  # noqa: E402
from core.template_workspace_transfer import (  # noqa: E402
    TemplateWorkspaceTransferError,
    inspect_template_workspace_archive,
)

REPORT_SCHEMA_VERSION = 1
MAX_LATENCY_SAMPLES = 100_000
OPERATIONS = (
    "truncate",
    "bit_flip",
    "append",
    "zero_range",
    "delete_range",
    "duplicate_range",
    "overwrite_range",
)


@dataclass(frozen=True)
class MutationRecipe:
    case: int
    operation: str
    start: int = 0
    length: int = 0
    positions: tuple[int, ...] = ()
    payload_hex: str = ""


def build_recipe(source_length: int, seed: int, case: int) -> MutationRecipe:
    if source_length < 2:
        raise ValueError("Fuzz source must contain at least two bytes.")
    digest = hashlib.sha256(f"{seed}:{case}".encode()).digest()
    randomizer = random.Random(int.from_bytes(digest, "big"))
    operation = OPERATIONS[case % len(OPERATIONS)]
    if operation == "truncate":
        return MutationRecipe(case, operation, length=randomizer.randrange(1, source_length))
    if operation == "bit_flip":
        count = randomizer.randint(1, min(8, source_length))
        positions = tuple(randomizer.sample(range(source_length), count))
        payload = bytes(randomizer.randrange(1, 256) for _ in positions)
        return MutationRecipe(case, operation, positions=positions, payload_hex=payload.hex())
    if operation == "append":
        payload = randomizer.randbytes(randomizer.randint(1, 64))
        return MutationRecipe(case, operation, payload_hex=payload.hex())

    start = randomizer.randrange(source_length)
    length = randomizer.randint(1, min(64, source_length - start))
    if operation == "overwrite_range":
        payload = randomizer.randbytes(length)
        return MutationRecipe(case, operation, start, length, payload_hex=payload.hex())
    return MutationRecipe(case, operation, start, length)


def apply_recipe(source: bytes, recipe: MutationRecipe) -> bytes:
    mutated = bytearray(source)
    if recipe.operation == "truncate":
        return bytes(mutated[: recipe.length])
    if recipe.operation == "bit_flip":
        masks = bytes.fromhex(recipe.payload_hex)
        if len(masks) != len(recipe.positions):
            raise ValueError("Bit-flip recipe payload is inconsistent.")
        for position, mask in zip(recipe.positions, masks, strict=True):
            mutated[position] ^= mask
    elif recipe.operation == "append":
        mutated.extend(bytes.fromhex(recipe.payload_hex))
    elif recipe.operation == "zero_range":
        mutated[recipe.start : recipe.start + recipe.length] = b"\0" * recipe.length
    elif recipe.operation == "delete_range":
        del mutated[recipe.start : recipe.start + recipe.length]
    elif recipe.operation == "duplicate_range":
        selected = mutated[recipe.start : recipe.start + recipe.length]
        mutated[recipe.start : recipe.start] = selected
    elif recipe.operation == "overwrite_range":
        payload = bytes.fromhex(recipe.payload_hex)
        if len(payload) != recipe.length:
            raise ValueError("Overwrite recipe payload is inconsistent.")
        mutated[recipe.start : recipe.start + recipe.length] = payload
    else:
        raise ValueError(f"Unsupported mutation operation: {recipe.operation}")
    if len(mutated) > MAX_PACK_SIZE:
        return bytes(mutated[:MAX_PACK_SIZE])
    return bytes(mutated)


def nested_member_length(source: bytes, member: str = "template.docx") -> int:
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        return len(archive.read(member))


def mutate_nested_member(
    source: bytes,
    recipe: MutationRecipe,
    *,
    artifact_kind: str = "pack",
    member: str = "template.docx",
) -> bytes:
    """Mutate a nested payload while keeping outer checksums internally consistent."""

    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        payloads = {info.filename: archive.read(info) for info in archive.infolist()}
    payloads[member] = apply_recipe(payloads[member], recipe)
    manifest = json.loads(payloads["manifest.json"].decode("utf-8"))
    if artifact_kind == "workspace":
        workspace = json.loads(payloads["workspace.json"].decode("utf-8"))
        workspace["templateSha256"] = hashlib.sha256(payloads[member]).hexdigest()
        workspace_without_hash = {
            key: value for key, value in workspace.items() if key != "workspaceHash"
        }
        workspace["workspaceHash"] = hashlib.sha256(
            _canonical_json(workspace_without_hash)
        ).hexdigest()
        payloads["workspace.json"] = _canonical_json(workspace)
        manifest["checksums"]["workspace.json"] = hashlib.sha256(
            payloads["workspace.json"]
        ).hexdigest()
    elif artifact_kind != "pack":
        raise ValueError("artifact_kind must be 'pack' or 'workspace'")
    manifest["checksums"][member] = hashlib.sha256(payloads[member]).hexdigest()
    payloads["manifest.json"] = _canonical_json(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(payloads):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, payloads[name])
    return output.getvalue()


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def workspace_inspector(data: bytes, *, require_publishable: bool = True) -> Any:
    del require_publishable
    try:
        return inspect_template_workspace_archive(data, actor="fuzz-harness")
    except TemplateWorkspaceTransferError as exc:
        raise TemplatePackError(str(exc)) from exc


def catalog_inspector(catalog: TemplatePackCatalog) -> Callable[..., Any]:
    """Adapt catalog install to the fuzz contract and audit rejected writes."""

    def inspect(data: bytes, *, require_publishable: bool = True) -> Any:
        del require_publishable
        before = catalog.snapshot()
        try:
            return catalog.install(
                data,
                expected_revision=int(before["revision"]),
                actor="fuzz-harness",
            )
        except ValueError as exc:
            after = catalog.snapshot()
            if after != before:
                raise RuntimeError("Rejected catalog mutation changed persistent state.") from exc
            raise TemplatePackError(str(exc)) from exc

    return inspect


def percentile(samples: list[float], value: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = (len(ordered) - 1) * value
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
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


def _process_rss_mib() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except (ImportError, OSError):
        return 0.0


def _report(
    *,
    source_sha256: str,
    seed: int,
    requested_iterations: int,
    duration_limit_seconds: float,
    started_at: str,
    started: float,
    completed: int,
    accepted: int,
    rejected: int,
    latency_samples: deque[float],
    peak_rss_mib: float,
    outcome: str,
    failure: dict[str, Any] | None,
) -> dict[str, Any]:
    latencies = list(latency_samples)
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "sourceSha256": source_sha256,
        "seed": seed,
        "requestedIterations": requested_iterations,
        "durationLimitSeconds": duration_limit_seconds,
        "startedAt": started_at,
        "updatedAt": utc_now(),
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        "completedIterations": completed,
        "acceptedMutations": accepted,
        "controlledRejections": rejected,
        "unexpectedErrors": 1 if failure else 0,
        "outcome": outcome,
        "latencyMs": {
            "sampleCount": len(latencies),
            "p50": round(percentile(latencies, 0.50), 6),
            "p95": round(percentile(latencies, 0.95), 6),
            "max": round(max(latencies, default=0.0), 6),
        },
        "peakRssMiB": round(peak_rss_mib, 3),
        "failure": failure,
        "containsSourceBytes": False,
    }


def run_fuzz(
    source: bytes,
    *,
    iterations: int,
    duration_seconds: float,
    seed: int,
    output: Path,
    checkpoint_every: int = 250,
    inspector: Callable[..., Any] = inspect_template_pack,
    mutator: Callable[[bytes, MutationRecipe], bytes] = apply_recipe,
    mutation_source_length: int | None = None,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if duration_seconds < 0:
        raise ValueError("duration_seconds cannot be negative")
    if checkpoint_every < 1:
        raise ValueError("checkpoint_every must be at least 1")
    if len(source) < 2 or len(source) > MAX_PACK_SIZE:
        raise ValueError("source size is outside the Template Pack safety boundary")

    inspector(source, require_publishable=True)
    source_sha256 = hashlib.sha256(source).hexdigest()
    started_at = utc_now()
    started = time.perf_counter()
    deadline = started + duration_seconds if duration_seconds else None
    latencies: deque[float] = deque(maxlen=MAX_LATENCY_SAMPLES)
    completed = accepted = rejected = 0
    peak_rss_mib = _process_rss_mib()
    failure: dict[str, Any] | None = None

    for case in range(iterations):
        if deadline is not None and time.perf_counter() >= deadline:
            break
        recipe = build_recipe(mutation_source_length or len(source), seed, case)
        mutated = mutator(source, recipe)
        case_started = time.perf_counter()
        try:
            inspector(mutated, require_publishable=True)
            accepted += 1
        except TemplatePackError:
            rejected += 1
        except Exception as exc:  # noqa: BLE001 - the harness audits escaped exceptions
            failure = {
                "case": case,
                "recipe": asdict(recipe),
                "exceptionType": type(exc).__name__,
                "message": "Unexpected exception escaped Template Pack inspection.",
            }
        finally:
            latencies.append((time.perf_counter() - case_started) * 1000)
            completed += 1
            peak_rss_mib = max(peak_rss_mib, _process_rss_mib())

        outcome = "failed" if failure else "running"
        if failure or completed % checkpoint_every == 0:
            atomic_json_write(
                output,
                _report(
                    source_sha256=source_sha256,
                    seed=seed,
                    requested_iterations=iterations,
                    duration_limit_seconds=duration_seconds,
                    started_at=started_at,
                    started=started,
                    completed=completed,
                    accepted=accepted,
                    rejected=rejected,
                    latency_samples=latencies,
                    peak_rss_mib=peak_rss_mib,
                    outcome=outcome,
                    failure=failure,
                ),
            )
        if failure:
            break

    final = _report(
        source_sha256=source_sha256,
        seed=seed,
        requested_iterations=iterations,
        duration_limit_seconds=duration_seconds,
        started_at=started_at,
        started=started,
        completed=completed,
        accepted=accepted,
        rejected=rejected,
        latency_samples=latencies,
        peak_rss_mib=peak_rss_mib,
        outcome="failed" if failure else "passed",
        failure=failure,
    )
    atomic_json_write(output, final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pack",
        required=True,
        type=Path,
        help="Published .rptpack or exported workspace draft seed file",
    )
    parser.add_argument(
        "--target",
        choices=("outer-pack", "nested-pack", "nested-workspace", "catalog"),
        default="outer-pack",
    )
    parser.add_argument("--iterations", type=int, default=10_000)
    parser.add_argument("--duration-minutes", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0xC0DEC0DE)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "template-pack-fuzz" / "result.json",
    )
    arguments = parser.parse_args()
    try:
        source = arguments.pack.resolve().read_bytes()
        options: dict[str, Any] = {}
        catalog_context: tempfile.TemporaryDirectory[str] | None = None
        if arguments.target in {"nested-pack", "nested-workspace", "catalog"}:
            kind = "workspace" if arguments.target == "nested-workspace" else "pack"
            options["mutator"] = lambda data, recipe: mutate_nested_member(
                data, recipe, artifact_kind=kind
            )
            options["mutation_source_length"] = nested_member_length(source)
        if arguments.target == "nested-workspace":
            options["inspector"] = workspace_inspector
        elif arguments.target == "catalog":
            catalog_context = tempfile.TemporaryDirectory(prefix="reporter-catalog-fuzz-")
            options["inspector"] = catalog_inspector(
                TemplatePackCatalog(Path(catalog_context.name) / "catalog")
            )
        try:
            result = run_fuzz(
                source,
                iterations=arguments.iterations,
                duration_seconds=arguments.duration_minutes * 60,
                seed=arguments.seed,
                output=arguments.output.resolve(),
                checkpoint_every=arguments.checkpoint_every,
                **options,
            )
        finally:
            if catalog_context is not None:
                catalog_context.cleanup()
    except (OSError, TemplatePackError, ValueError) as exc:
        print(f"Template Pack fuzz setup failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["outcome"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
