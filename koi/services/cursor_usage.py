"""Fetch Cursor subscription usage from the local IDE session (unofficial API)."""

from __future__ import annotations

import base64
import json
import os
import platform
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

CURSOR_USAGE_SUMMARY_API = "https://cursor.com/api/usage-summary"
CURSOR_USAGE_API = "https://cursor.com/api/usage"
CURSOR_PLAN_INFO_API = "https://cursor.com/api/dashboard/get-plan-info"
CURSOR_SPENDING_DASHBOARD_URL = "https://cursor.com/dashboard/spending"
CURSOR_DASHBOARD_URL = "https://cursor.com/dashboard"


@dataclass(frozen=True)
class CursorUsageSnapshot:
    status: Literal["ok", "no_auth", "error"]
    used: float | None = None
    limit: float | None = None
    unit: Literal["usd", "requests", "percent"] = "percent"
    used_percent: float | None = None
    center_primary: str = "—"
    center_secondary: str = ""
    plan_name: str | None = None
    reset_at: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "used": self.used,
            "limit": self.limit,
            "unit": self.unit,
            "used_percent": self.used_percent,
            "center_primary": self.center_primary,
            "center_secondary": self.center_secondary,
            "plan_name": self.plan_name,
            "reset_at": self.reset_at,
            "message": self.message,
        }


def cursor_state_db_path() -> Path | None:
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            return None
        return Path(appdata) / "Cursor/User/globalStorage/state.vscdb"
    return home / ".config/Cursor/User/globalStorage/state.vscdb"


def parse_stored_access_token(raw: str) -> str | None:
    value = raw.strip()
    if value.startswith('"'):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = value.strip('"')
    return value or None


def read_cursor_access_token(db_path: Path | None = None) -> str | None:
    path = db_path or cursor_state_db_path()
    if path is None or not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=8.0)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key = 'cursorAuth/accessToken' LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if not row or row[0] is None:
        return None
    raw = row[0]
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return parse_stored_access_token(str(raw))


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def build_workos_session_cookie(access_token: str) -> tuple[str, str] | None:
    payload = decode_jwt_payload(access_token)
    sub = payload.get("sub") if payload else None
    if not isinstance(sub, str) or not sub:
        return None
    pipe = sub.find("|")
    user_id = sub[pipe + 1 :] if pipe >= 0 else sub
    if not user_id:
        return None
    session_token = f"{user_id}%3A%3A{access_token}"
    return session_token, user_id


def _to_finite_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) == float(value):
            return float(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = float(value)
        except ValueError:
            return None
        if parsed == parsed:
            return parsed
    return None


def _as_record(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _format_date(value: Any) -> str | None:
    if value is None:
        return None
    date: datetime | None = None
    if isinstance(value, (int, float)):
        epoch_ms = float(value) * 1000 if float(value) < 1_000_000_000_000 else float(value)
        date = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    elif isinstance(value, str) and value.strip():
        numeric = _to_finite_number(value)
        if numeric is not None:
            epoch_ms = numeric * 1000 if numeric < 1_000_000_000_000 else numeric
            date = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        else:
            try:
                date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
    if date is None:
        return None
    return date.astimezone().strftime("%d %b")


def _format_usd(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 100:
        return f"${int(round(value))}"
    if abs(value - round(value)) < 0.05:
        return f"${int(round(value))}"
    return f"${value:.2f}"


def _normalize_usd_amount(value: float | None) -> float | None:
    if value is None:
        return None
    # Cursor dashboard often reports plan caps in cents (e.g. 40000 -> $400).
    if value >= 500 and abs(value - round(value)) < 0.01:
        return value / 100.0
    return value


def _resolve_usd_usage(
    *,
    used: float | None,
    limit: float | None,
    percent: float | None,
) -> tuple[float | None, float | None]:
    limit_usd = _normalize_usd_amount(limit)
    used_usd = _normalize_usd_amount(used)
    if (
        percent is not None
        and limit_usd is not None
        and (used_usd is None or (limit is not None and used is not None and used >= limit * 0.99))
    ):
        used_usd = limit_usd * min(max(percent / 100.0, 0.0), 1.0)
    return used_usd, limit_usd


def _format_count(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value - round(value)) < 0.001:
        return str(int(round(value)))
    return f"{value:.1f}"


def _snapshot_from_percent(
    *,
    percent: float,
    used: float | None,
    limit: float | None,
    unit: Literal["usd", "requests", "percent"],
    plan_name: str | None,
    reset_at: str | None,
) -> CursorUsageSnapshot:
    ratio = min(max(percent / 100.0, 0.0), 1.0)
    if unit == "usd":
        primary = _format_usd(used)
        secondary = _format_usd(limit)
    elif unit == "requests":
        primary = _format_count(used)
        secondary = _format_count(limit)
    else:
        primary = f"{int(round(percent))}%"
        secondary = "used"
    return CursorUsageSnapshot(
        status="ok",
        used=used,
        limit=limit,
        unit=unit,
        used_percent=round(percent, 1),
        center_primary=primary,
        center_secondary=secondary,
        plan_name=plan_name,
        reset_at=reset_at,
    )


def _extract_subscription_details(summary_data: dict[str, Any]) -> tuple[str | None, str | None]:
    individual_usage = _as_record(summary_data.get("individualUsage"))
    plan = _as_record(individual_usage.get("plan") if individual_usage else None)
    subscription = _as_record(individual_usage.get("subscription") if individual_usage else None)
    plan_name = _first_string(
        plan.get("displayName") if plan else None,
        plan.get("name") if plan else None,
        plan.get("planName") if plan else None,
        plan.get("tier") if plan else None,
        subscription.get("name") if subscription else None,
        subscription.get("planName") if subscription else None,
        individual_usage.get("planName") if individual_usage else None,
        summary_data.get("planName"),
    )
    reset_at = _format_date(
        (plan or {}).get("expiresAt")
        or (plan or {}).get("currentPeriodEnd")
        or (plan or {}).get("renewsAt")
        or (subscription or {}).get("currentPeriodEnd")
        or (subscription or {}).get("renewsAt")
        or summary_data.get("billingCycleEnd")
    )
    return plan_name, reset_at


def _dashboard_headers(session_token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Cookie": f"WorkosCursorSessionToken={session_token}",
        "Origin": "https://cursor.com",
        "Referer": CURSOR_SPENDING_DASHBOARD_URL,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _http_json(
    url: str,
    *,
    headers: dict[str, str],
    method: str = "GET",
    body: bytes | None = None,
    timeout: float = 20.0,
) -> dict[str, Any] | None:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def fetch_cursor_usage(
    *,
    access_token: str | None = None,
    db_path: Path | None = None,
) -> CursorUsageSnapshot:
    token = access_token or read_cursor_access_token(db_path)
    if not token:
        return CursorUsageSnapshot(
            status="no_auth",
            message="Не удалось прочитать сессию Cursor. Войдите в Cursor IDE.",
        )

    session = build_workos_session_cookie(token)
    if session is None:
        return CursorUsageSnapshot(
            status="no_auth",
            message="Сессия Cursor найдена, но токен не распознан. Перелогиньтесь в Cursor.",
        )
    session_token, user_id = session
    headers = _dashboard_headers(session_token)

    plan_name: str | None = None
    reset_at: str | None = None

    plan_info = _http_json(
        CURSOR_PLAN_INFO_API,
        headers={**headers, "Accept": "*/*", "Content-Type": "application/json"},
        method="POST",
        body=b"{}",
    )
    if plan_info:
        plan_info_record = _as_record(plan_info.get("planInfo"))
        if plan_info_record:
            plan_name = _first_string(
                plan_info_record.get("planName"),
                plan_info_record.get("name"),
                plan_info_record.get("tier"),
            )
            reset_at = _format_date(
                plan_info_record.get("billingCycleEnd")
                or plan_info_record.get("expiresAt")
                or plan_info_record.get("currentPeriodEnd")
                or plan_info_record.get("renewsAt")
            )

    summary = _http_json(CURSOR_USAGE_SUMMARY_API, headers=headers)
    if summary:
        summary_plan_name, summary_reset_at = _extract_subscription_details(summary)
        plan_name = plan_name or summary_plan_name
        reset_at = reset_at or summary_reset_at

        individual_usage = _as_record(summary.get("individualUsage"))
        plan = _as_record(individual_usage.get("plan") if individual_usage else None)
        total_percent = _to_finite_number(plan.get("totalPercentUsed") if plan else None)
        auto_percent = _to_finite_number(plan.get("autoPercentUsed") if plan else None)
        api_percent = _to_finite_number(plan.get("apiPercentUsed") if plan else None)
        included_used = _to_finite_number(plan.get("used") if plan else None)
        included_limit = _to_finite_number(plan.get("limit") if plan else None)

        if total_percent is not None or auto_percent is not None or api_percent is not None:
            primary_percent = total_percent if total_percent is not None else (auto_percent or api_percent or 0.0)
            used_usd, limit_usd = _resolve_usd_usage(
                used=included_used,
                limit=included_limit,
                percent=primary_percent,
            )
            if limit_usd is not None and included_used is not None:
                return _snapshot_from_percent(
                    percent=primary_percent,
                    used=used_usd,
                    limit=limit_usd,
                    unit="usd",
                    plan_name=plan_name,
                    reset_at=reset_at,
                )
            if included_limit is not None and included_used is not None:
                return _snapshot_from_percent(
                    percent=primary_percent,
                    used=included_used,
                    limit=included_limit,
                    unit="requests",
                    plan_name=plan_name,
                    reset_at=reset_at,
                )
            return _snapshot_from_percent(
                percent=primary_percent,
                used=None,
                limit=None,
                unit="percent",
                plan_name=plan_name,
                reset_at=reset_at,
            )

    usage_url = f"{CURSOR_USAGE_API}?user={urllib.parse.quote(user_id)}"
    legacy = _http_json(usage_url, headers=headers)
    if legacy:
        g4 = _as_record(legacy.get("gpt-4")) or _as_record((_as_record(legacy.get("usage")) or {}).get("gpt_4"))
        premium_used = _to_finite_number((g4 or {}).get("numRequests") or (g4 or {}).get("num_requests")) or 0.0
        premium_limit = _to_finite_number((g4 or {}).get("maxRequestUsage") or (g4 or {}).get("max_requests"))
        if premium_limit and premium_limit > 0:
            percent = min(max(premium_used / premium_limit * 100.0, 0.0), 100.0)
            return _snapshot_from_percent(
                percent=percent,
                used=premium_used,
                limit=premium_limit,
                unit="requests",
                plan_name=plan_name,
                reset_at=reset_at,
            )

    return CursorUsageSnapshot(
        status="error",
        message="Не удалось получить квоту Cursor (API не ответил).",
    )
