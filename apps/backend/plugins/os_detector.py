from __future__ import annotations

from plugins.manager import BasePlugin


class Plugin(BasePlugin):
    plugin_id = "os-detector"
    cache_policy = "deterministic"
    version = "1.0.0"

    def name(self) -> str:
        return "OS Detector"

    def process_input(self, data: dict) -> dict:
        for section in ("servers", "clients"):
            for asset in data.get(section, []):
                current_os = str(asset.get("os", "")).strip()
                if current_os and current_os.upper() != "N/A":
                    continue
                asset["os"] = detect_os(asset.get("hostname", ""))
        return data


def detect_os(hostname: str) -> str:
    normalized = hostname.upper()

    if normalized.startswith(("SRV", "DC", "DB", "APP")):
        return "Windows Server / Linux Server"
    if normalized.startswith(("UBU", "LIN", "K8S")):
        return "Linux"
    if normalized.startswith(("MAC", "MBP", "IMAC")):
        return "macOS"
    return "Windows 10/11"
