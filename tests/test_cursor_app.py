from __future__ import annotations

import unittest
from unittest.mock import patch

from koi.services.cursor_app import (
    cursor_frontmost_app_name,
    cursor_is_active,
    cursor_is_frontmost,
    cursor_is_running,
)


class CursorAppTest(unittest.TestCase):
    def test_cursor_is_running_macos(self) -> None:
        with patch("koi.services.cursor_app.platform.system", return_value="Darwin"):
            with patch(
                "koi.services.cursor_app._run_command",
                return_value=type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            ):
                self.assertTrue(cursor_is_running())

    def test_cursor_is_frontmost(self) -> None:
        with patch("koi.services.cursor_app.cursor_frontmost_app_name", return_value="Cursor"):
            self.assertTrue(cursor_is_frontmost())
        with patch("koi.services.cursor_app.cursor_frontmost_app_name", return_value="Safari"):
            self.assertFalse(cursor_is_frontmost())

    def test_cursor_is_active_uses_frontmost(self) -> None:
        with patch("koi.services.cursor_app.cursor_is_frontmost", return_value=True):
            self.assertTrue(cursor_is_active())
        with patch("koi.services.cursor_app.cursor_is_frontmost", return_value=False):
            self.assertFalse(cursor_is_active())

    def test_cursor_frontmost_app_name_macos(self) -> None:
        with patch("koi.services.cursor_app.platform.system", return_value="Darwin"):
            with patch(
                "koi.services.cursor_app._run_command",
                return_value=type("P", (), {"returncode": 0, "stdout": "Cursor\n", "stderr": ""})(),
            ):
                self.assertEqual(cursor_frontmost_app_name(), "Cursor")


if __name__ == "__main__":
    unittest.main()
