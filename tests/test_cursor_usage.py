from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from koi.services.cursor_usage import (
    CursorUsageSnapshot,
    build_workos_session_cookie,
    fetch_cursor_usage,
    parse_stored_access_token,
    _snapshot_from_percent,
)


class CursorUsageHelpersTest(unittest.TestCase):
    def test_parse_stored_access_token_json_string(self) -> None:
        self.assertEqual(parse_stored_access_token('"abc.def.ghi"'), "abc.def.ghi")

    def test_build_workos_session_cookie(self) -> None:
        token = (
            "eyJhbGciOiJub25lIn0."
            "eyJzdWIiOiJhdXRoMHx1c2VyXzEyMyJ9."
            "sig"
        )
        session = build_workos_session_cookie(token)
        self.assertIsNotNone(session)
        session_token, user_id = session
        self.assertEqual(user_id, "user_123")
        self.assertTrue(session_token.startswith("user_123%3A%3A"))

    def test_snapshot_from_percent_usd(self) -> None:
        snap = _snapshot_from_percent(
            percent=42.5,
            used=42.3,
            limit=400.0,
            unit="usd",
            plan_name="Pro",
            reset_at="10 Jul",
        )
        self.assertEqual(snap.status, "ok")
        self.assertEqual(snap.center_primary, "$42.30")
        self.assertEqual(snap.center_secondary, "$400")


class CursorUsageFetchTest(unittest.TestCase):
    def test_fetch_without_token(self) -> None:
        with patch("koi.services.cursor_usage.read_cursor_access_token", return_value=None):
            snap = fetch_cursor_usage()
        self.assertEqual(snap.status, "no_auth")

    def test_fetch_summary_usd(self) -> None:
        token = (
            "eyJhbGciOiJub25lIn0."
            "eyJzdWIiOiJhdXRoMHx1c2VyXzEyMyJ9."
            "sig"
        )
        summary = {
            "individualUsage": {
                "plan": {
                    "used": 4230,
                    "limit": 40000,
                    "totalPercentUsed": 10.6,
                }
            }
        }

        def fake_http(url, *, headers, method="GET", body=None, timeout=20.0):
            if url.endswith("/usage-summary"):
                return summary
            return None

        with patch("koi.services.cursor_usage.read_cursor_access_token", return_value=token):
            with patch("koi.services.cursor_usage._http_json", side_effect=fake_http):
                snap = fetch_cursor_usage()
        self.assertEqual(snap.status, "ok")
        self.assertEqual(snap.unit, "usd")
        self.assertEqual(snap.used_percent, 10.6)
        self.assertEqual(snap.center_primary, "$42.30")

    def test_fetch_legacy_requests(self) -> None:
        token = (
            "eyJhbGciOiJub25lIn0."
            "eyJzdWIiOiJhdXRoMHx1c2VyXzEyMyJ9."
            "sig"
        )
        legacy = {"gpt-4": {"numRequests": 120, "maxRequestUsage": 500}}

        def fake_http(url, *, headers, method="GET", body=None, timeout=20.0):
            if url.endswith("/usage-summary"):
                return {}
            if "/api/usage" in url:
                return legacy
            return None

        with patch("koi.services.cursor_usage.read_cursor_access_token", return_value=token):
            with patch("koi.services.cursor_usage._http_json", side_effect=fake_http):
                snap = fetch_cursor_usage()
        self.assertEqual(snap.status, "ok")
        self.assertEqual(snap.unit, "requests")
        self.assertEqual(snap.center_primary, "120")
        self.assertEqual(snap.center_secondary, "500")

    def test_to_dict_roundtrip(self) -> None:
        snap = CursorUsageSnapshot(status="ok", used_percent=12.0, center_primary="12%", center_secondary="used")
        data = snap.to_dict()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(json.loads(json.dumps(data))["used_percent"], 12.0)


if __name__ == "__main__":
    unittest.main()
