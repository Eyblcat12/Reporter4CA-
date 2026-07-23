"""Elasticsearch raw log fetcher plugin.

Plugin nay ket noi toi Elasticsearch de lay raw log cho tung asset
trong qua trinh danh gia. Yeu cau cau hinh ELASTIC_HOST, ELASTIC_INDEX
trong metadata hoac bien moi truong.

NOTE: Plugin nay can thu vien `elasticsearch` duoc cai dat rieng.
"""

from __future__ import annotations

import os
from typing import Any

from plugins.manager import BasePlugin


class Plugin(BasePlugin):
    version = "1.0.0"

    def name(self) -> str:
        return "Elastic RawLog Fetcher"

    def process_input(self, data: dict[str, Any]) -> dict[str, Any]:
        metadata = data.get("metadata", {})
        elastic_host = metadata.get("elastic_host") or os.environ.get("ELASTIC_HOST", "")
        elastic_index = metadata.get("elastic_index") or os.environ.get("ELASTIC_INDEX", "")

        if not elastic_host or not elastic_index:
            return data

        try:
            from elasticsearch import Elasticsearch
        except ImportError:
            print("Plugin Elastic RawLog Fetcher: Can cai dat elasticsearch (pip install elasticsearch)")
            return data

        try:
            es = Elasticsearch([elastic_host], request_timeout=30)
            if not es.ping():
                print(f"Plugin Elastic RawLog Fetcher: Khong ket noi duoc toi {elastic_host}")
                return data
        except Exception as exc:
            print(f"Plugin Elastic RawLog Fetcher: Loi ket noi - {exc}")
            return data

        for section in ("servers", "clients"):
            for asset in data.get(section, []):
                hostname = asset.get("hostname", "")
                if not hostname:
                    continue
                try:
                    raw_logs = _fetch_logs(es, elastic_index, hostname)
                    if raw_logs:
                        asset["raw_logs"] = raw_logs
                except Exception as exc:
                    asset["raw_logs_error"] = str(exc)

        return data


def _fetch_logs(es: Any, index: str, hostname: str, size: int = 100) -> list[dict[str, Any]]:
    """Truy van Elasticsearch de lay raw log theo hostname."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"hostname": hostname}},
                ]
            }
        },
        "size": size,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }

    response = es.search(index=index, body=query)
    hits = response.get("hits", {}).get("hits", [])
    return [hit.get("_source", {}) for hit in hits]
