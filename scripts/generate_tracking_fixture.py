"""Generate deterministic CSV fixtures for Reporter Pro performance tests.

The committed 50-asset fixtures are intentionally small enough for correctness
tests. The same generator can create controlled 1,000/3,000/50,000-asset inputs
outside the repository without inventing a second data model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "tests" / "fixtures" / "performance"
GENERATOR_VERSION = "1.0"
DEFAULT_SEED = 20_260_730
DEFAULT_COUNT = 50
PROFILES = ("clean", "mixed", "finding_heavy", "long_notes")
REPORT_TYPES = (
    "full",
    "server_only",
    "client_only",
    "summary",
    "technical",
    "incident_response",
)
CSV_FIELDS = (
    "Type",
    "Hostname",
    "IP",
    "OS",
    "Result",
    "Notes",
    "Software",
    "Process",
    "Zone",
    "Owner",
)
_ASSESSMENT_PRIORITY = {
    "clean": 0,
    "insufficient_data": 1,
    "needs_review": 2,
    "anomaly": 3,
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_pick(values: tuple[str, ...], *, seed: int, index: int, namespace: str) -> str:
    digest = hashlib.sha256(f"{seed}:{index}:{namespace}".encode("ascii")).digest()
    return values[int.from_bytes(digest[:4], "big") % len(values)]


def _asset_type(index: int) -> str:
    return "server" if index % 5 in {0, 3} else "client"


def _profile_values(profile: str, index: int) -> tuple[dict[str, str], list[tuple[str, str, int]]]:
    """Return source fields and independently expected rule outcomes.

    Each expected tuple is ``(rule_id, classification, evidence_count)``. Keeping
    these expectations outside the rule engine lets the committed manifest catch
    accidental rule regressions.
    """

    if profile == "clean":
        return {
            "Result": "Không phát hiện - Đã kiểm tra",
            "Notes": "Đã hoàn tất đối chiếu telemetry; không có cảnh báo cần xử lý.",
            "Software": "Reporter Agent",
            "Process": "reporter-agent.exe",
        }, []

    if profile == "mixed":
        variant = index % 6
        if variant == 0:
            return {
                "Result": "Phát hiện mã độc",
                "Notes": "PlugX backdoor được xác nhận từ telemetry EDR.",
                "Software": "",
                "Process": "svchost.exe",
            }, [("MALWARE_EVIDENCE", "anomaly", 2)]
        if variant == 1:
            return {
                "Result": "Ghi nhận dấu hiệu bất thường",
                "Notes": "PowerShell encoded command cần được điều tra theo process tree.",
                "Software": "",
                "Process": "powershell.exe",
            }, [("DECLARED_ANOMALY", "anomaly", 1)]
        if variant == 2:
            return {
                "Result": "Cần xác minh",
                "Notes": "Proxifier được quan sát trong phiên người dùng, chưa rõ mục đích.",
                "Software": "",
                "Process": "proxifier.exe",
            }, [
                ("DECLARED_REVIEW", "needs_review", 1),
                ("PROXY_TOOL_REVIEW", "needs_review", 2),
            ]
        if variant == 3:
            return {
                "Result": "Chưa kết luận",
                "Notes": "Không đủ dữ liệu telemetry để hoàn tất đánh giá.",
                "Software": "",
                "Process": "",
            }, [("INCOMPLETE_ASSESSMENT", "insufficient_data", 2)]
        if variant == 4:
            return {
                "Result": "Không phát hiện - Đã kiểm tra",
                "Notes": "Tor Browser được phê duyệt cho bài kiểm thử nội bộ.",
                "Software": "Tor Browser",
                "Process": "firefox.exe",
            }, []
        return {
            "Result": "Không phát hiện",
            "Notes": "Đã đối chiếu nhật ký và xác nhận trạng thái bình thường.",
            "Software": "Reporter Agent",
            "Process": "reporter-agent.exe",
        }, []

    if profile == "finding_heavy":
        if index % 2 == 0:
            return {
                "Result": "Phát hiện mã độc",
                "Notes": "Mimikatz credential dumping được xác nhận từ cảm biến EDR.",
                "Software": "",
                "Process": "lsass.exe",
            }, [("MALWARE_EVIDENCE", "anomaly", 2)]
        return {
            "Result": "Ghi nhận dấu hiệu bất thường",
            "Notes": "Webshell được xác nhận trong thư mục dịch vụ web.",
            "Software": "",
            "Process": "w3wp.exe",
        }, [
            ("MALWARE_EVIDENCE", "anomaly", 1),
            ("DECLARED_ANOMALY", "anomaly", 1),
        ]

    if profile == "long_notes":
        paragraph = (
            "Đã hoàn tất đối chiếu nhật ký hệ thống, tiến trình, kết nối mạng và tài khoản; "
            "kết quả nhất quán với hoạt động vận hành được phê duyệt. "
            "Kiểm tra Unicode: tiếng Việt, 日本語, 한국어, Ελληνικά, emoji 🛡️. "
        )
        return {
            "Result": "Không phát hiện - Đã kiểm tra",
            "Notes": (paragraph * 12).strip(),
            "Software": "Reporter Agent",
            "Process": "reporter-agent.exe",
        }, []

    raise ValueError(f"Unsupported fixture profile: {profile}")


def build_fixture_rows(profile: str, *, count: int, seed: int) -> list[dict[str, Any]]:
    if profile not in PROFILES:
        raise ValueError(f"Unsupported fixture profile: {profile}")
    if count < 1 or count > 500_000:
        raise ValueError("count must be between 1 and 500000")

    rows: list[dict[str, Any]] = []
    for index in range(count):
        asset_type = _asset_type(index)
        source, expected = _profile_values(profile, index)
        os_values = (
            ("Windows Server 2022", "Windows Server 2019", "Ubuntu 22.04 LTS", "Rocky Linux 9")
            if asset_type == "server"
            else ("Windows 11", "Windows 10", "Ubuntu Desktop 22.04", "macOS 15")
        )
        rows.append({
            "Type": asset_type,
            "Hostname": f"{'SRV' if asset_type == 'server' else 'PC'}-{profile.upper().replace('_', '-')}-{index + 1:06d}",
            "IP": f"10.{20 + seed % 200}.{(index // 254) % 254}.{index % 254 + 1}",
            "OS": _stable_pick(os_values, seed=seed, index=index, namespace="os"),
            **source,
            "Zone": _stable_pick(
                ("Datacenter", "Office", "Management", "DMZ"),
                seed=seed,
                index=index,
                namespace="zone",
            ),
            "Owner": _stable_pick(
                ("Blue Team", "Infrastructure", "Endpoint", "Application"),
                seed=seed,
                index=index,
                namespace="owner",
            ),
            "_expected": expected,
        })
    return rows


def fixture_csv_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(CSV_FIELDS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _row_assessment(expected: list[tuple[str, str, int]]) -> str:
    if not expected:
        return "clean"
    return max(expected, key=lambda item: _ASSESSMENT_PRIORITY[item[1]])[1]


def expected_summary(rows: list[dict[str, Any]], report_type: str) -> dict[str, Any]:
    if report_type == "server_only":
        included = [row for row in rows if row["Type"] == "server"]
    elif report_type == "client_only":
        included = [row for row in rows if row["Type"] == "client"]
    else:
        included = rows
    assessments = Counter(_row_assessment(row["_expected"]) for row in included)
    return {
        "assetCount": len(included),
        "serverCount": sum(row["Type"] == "server" for row in included),
        "clientCount": sum(row["Type"] == "client" for row in included),
        "findingCount": sum(len(row["_expected"]) for row in included),
        "evidenceCount": sum(
            evidence_count
            for row in included
            for _rule_id, _classification, evidence_count in row["_expected"]
        ),
        "assessmentCounts": dict(sorted(assessments.items())),
    }


def build_fixture_set(
    *,
    count: int = DEFAULT_COUNT,
    seed: int = DEFAULT_SEED,
    profiles: Iterable[str] = PROFILES,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    selected_profiles = tuple(profiles)
    if not selected_profiles:
        raise ValueError("At least one profile is required")
    unknown = sorted(set(selected_profiles) - set(PROFILES))
    if unknown:
        raise ValueError(f"Unsupported fixture profiles: {', '.join(unknown)}")

    files: dict[str, bytes] = {}
    fixtures: list[dict[str, Any]] = []
    for offset, profile in enumerate(selected_profiles):
        fixture_seed = seed + offset
        rows = build_fixture_rows(profile, count=count, seed=fixture_seed)
        filename = f"tracking_{profile}_{count}.csv"
        payload = fixture_csv_bytes(rows)
        files[filename] = payload
        fixtures.append({
            "id": f"{profile}-{count}",
            "profile": profile,
            "file": filename,
            "seed": fixture_seed,
            "assetCount": count,
            "serverCount": sum(row["Type"] == "server" for row in rows),
            "clientCount": sum(row["Type"] == "client" for row in rows),
            "inputBytes": len(payload),
            "sha256": sha256_bytes(payload),
            "validReportTypes": list(REPORT_TYPES),
            "expectedByReportType": {
                report_type: expected_summary(rows, report_type)
                for report_type in REPORT_TYPES
            },
        })

    manifest = {
        "schemaVersion": 1,
        "fixtureSetId": f"reporter-performance-{count}-v1",
        "generator": {
            "script": "scripts/generate_tracking_fixture.py",
            "version": GENERATOR_VERSION,
            "baseSeed": seed,
        },
        "fixtures": fixtures,
    }
    return manifest, files


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_fixture_set(
    output_dir: Path,
    *,
    count: int = DEFAULT_COUNT,
    seed: int = DEFAULT_SEED,
    profiles: Iterable[str] = PROFILES,
) -> dict[str, Any]:
    manifest, files = build_fixture_set(count=count, seed=seed, profiles=profiles)
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in files.items():
        _atomic_write(output_dir / filename, payload)
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write(output_dir / "manifest.json", manifest_payload)
    return manifest


def verify_fixture_set(output_dir: Path) -> list[str]:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return [f"Missing manifest: {manifest_path}"]
    try:
        actual_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        generator = actual_manifest["generator"]
        fixtures = actual_manifest["fixtures"]
        profiles = [str(item["profile"]) for item in fixtures]
        count_values = {int(item["assetCount"]) for item in fixtures}
        if len(count_values) != 1:
            return ["Manifest fixtures do not use one controlled asset count"]
        expected_manifest, expected_files = build_fixture_set(
            count=count_values.pop(),
            seed=int(generator["baseSeed"]),
            profiles=profiles,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return [f"Invalid manifest: {exc}"]

    errors: list[str] = []
    if actual_manifest != expected_manifest:
        errors.append("Manifest content does not match deterministic generator output")
    for filename, expected_payload in expected_files.items():
        fixture_path = output_dir / filename
        if not fixture_path.is_file():
            errors.append(f"Missing fixture: {filename}")
        elif fixture_path.read_bytes() != expected_payload:
            errors.append(f"Fixture differs from deterministic output: {filename}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic Reporter Pro performance fixtures")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--profile", action="append", choices=PROFILES, dest="profiles")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify committed files without writing them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.verify:
        errors = verify_fixture_set(output_dir)
        if errors:
            for error in errors:
                print(f"[ERROR] {error}")
            return 1
        print(f"Fixture set is reproducible: {output_dir / 'manifest.json'}")
        return 0

    manifest = write_fixture_set(
        output_dir,
        count=args.count,
        seed=args.seed,
        profiles=args.profiles or PROFILES,
    )
    print(
        f"Generated {len(manifest['fixtures'])} deterministic fixture(s): "
        f"{output_dir / 'manifest.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
