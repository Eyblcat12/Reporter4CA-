from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api.errors import (  # noqa: E402
    http_exception_handler,
    normalized_request_id,
    unhandled_exception_handler,
)


def request_with_id(request_id: str) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/api/test", "headers": []})
    request.state.request_id = request_id
    return request


class ApiErrorTests(unittest.TestCase):
    def test_http_error_keeps_detail_and_adds_machine_readable_context(self) -> None:
        response = asyncio.run(
            http_exception_handler(
                request_with_id("team-request-123"),
                HTTPException(status_code=404, detail="Không tìm thấy."),
            )
        )
        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(payload["detail"], "Không tìm thấy.")
        self.assertEqual(payload["error"]["code"], "HTTP_404")
        self.assertEqual(payload["requestId"], "team-request-123")
        self.assertEqual(response.headers["x-request-id"], "team-request-123")

    def test_internal_error_does_not_expose_exception_detail(self) -> None:
        response = asyncio.run(
            unhandled_exception_handler(
                request_with_id("team-request-456"),
                RuntimeError("secret filesystem detail"),
            )
        )
        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(payload["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("secret filesystem detail", response.body.decode("utf-8"))

    def test_request_id_accepts_safe_team_value_and_replaces_unsafe_input(self) -> None:
        self.assertEqual(normalized_request_id("team-run_2026"), "team-run_2026")
        generated = normalized_request_id("bad id with spaces")
        self.assertRegex(generated, r"^[0-9a-f]{32}$")


if __name__ == "__main__":
    unittest.main()
