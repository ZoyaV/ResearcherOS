#!/usr/bin/env python3
"""Always-on-top circular Cursor usage widget for macOS/Linux/Windows."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import replace
from pathlib import Path
from tkinter import font as tkfont

ROOT = Path(__file__).resolve().parents[2]

from koi.cursor.app import cursor_is_active
from koi.cursor.usage import (
    CURSOR_DASHBOARD_URL,
    CursorUsageSnapshot,
    fetch_cursor_usage,
)

DEFAULT_SIZE = 76
DEFAULT_MARGIN = 18
POLL_MS = 5 * 60 * 1000
TOPMOST_REFRESH_MS = 2000
VISIBILITY_CHECK_MS = 600


def _ring_color(percent: float | None) -> str:
    if percent is None:
        return "#94a3b8"
    if percent >= 95:
        return "#f87171"
    if percent >= 80:
        return "#fbbf24"
    return "#4ade80"


def _snapshot_for_widget(snapshot: CursorUsageSnapshot) -> CursorUsageSnapshot:
    if snapshot.status != "ok":
        return snapshot
    if snapshot.center_secondary:
        return snapshot
    if snapshot.unit == "percent":
        return replace(snapshot, center_secondary="used")
    return snapshot


class CursorUsageWidget:
    def __init__(
        self,
        *,
        size: int = DEFAULT_SIZE,
        margin: int = DEFAULT_MARGIN,
        poll_ms: int = POLL_MS,
        x: int | None = None,
        y: int | None = None,
        only_when_cursor_active: bool = True,
    ) -> None:
        self.size = size
        self.margin = margin
        self.poll_ms = poll_ms
        self.only_when_cursor_active = only_when_cursor_active
        self.snapshot = CursorUsageSnapshot(status="error", message="Загрузка…")
        self._drag_offset: tuple[int, int] | None = None
        self._refreshing = False
        self._visible = False
        self._checking_visibility = False

        self.root = tk.Tk()
        self.root.title("Cursor usage")
        self.root.overrideredirect(True)
        self.root.configure(bg="#111827")
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.94)
        except tk.TclError:
            pass
        if self.only_when_cursor_active:
            self.root.withdraw()

        screen_w = self.root.winfo_screenwidth()
        pos_x = x if x is not None else screen_w - size - margin
        pos_y = y if y is not None else margin
        self.root.geometry(f"{size}x{size}+{pos_x}+{pos_y}")

        self.canvas = tk.Canvas(
            self.root,
            width=size,
            height=size,
            bg="#111827",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._title_font = tkfont.Font(family="Helvetica", size=9, weight="bold")
        self._sub_font = tkfont.Font(family="Helvetica", size=8)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_open_dashboard)
        self.canvas.bind("<Button-3>", self._on_open_dashboard)

        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.after(0, self._refresh_async)
        self.root.after(self.poll_ms, self._schedule_poll)
        self.root.after(TOPMOST_REFRESH_MS, self._keep_topmost)
        if self.only_when_cursor_active:
            self.root.after(0, self._schedule_visibility_check)

    def _set_visible(self, visible: bool) -> None:
        if visible == self._visible:
            return
        self._visible = visible
        try:
            if visible:
                self.root.deiconify()
                self.root.lift()
                self.root.attributes("-topmost", True)
            else:
                self.root.withdraw()
        except tk.TclError:
            pass

    def _schedule_visibility_check(self) -> None:
        if self._checking_visibility:
            self.root.after(VISIBILITY_CHECK_MS, self._schedule_visibility_check)
            return
        self._checking_visibility = True

        def worker() -> None:
            active = cursor_is_active()
            self.root.after(0, lambda: self._apply_visibility(active))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(VISIBILITY_CHECK_MS, self._schedule_visibility_check)

    def _apply_visibility(self, active: bool) -> None:
        self._checking_visibility = False
        if self._drag_offset is not None:
            return
        self._set_visible(active)

    def _keep_topmost(self) -> None:
        if not self._visible:
            self.root.after(TOPMOST_REFRESH_MS, self._keep_topmost)
            return
        try:
            self.root.attributes("-topmost", True)
            self.root.lift()
        except tk.TclError:
            pass
        self.root.after(TOPMOST_REFRESH_MS, self._keep_topmost)

    def _schedule_poll(self) -> None:
        self._refresh_async()
        self.root.after(self.poll_ms, self._schedule_poll)

    def _refresh_async(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True

        def worker() -> None:
            try:
                snapshot = _snapshot_for_widget(fetch_cursor_usage())
            except Exception as exc:  # noqa: BLE001
                snapshot = CursorUsageSnapshot(status="error", message=str(exc))
            self.root.after(0, lambda: self._apply_snapshot(snapshot))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_snapshot(self, snapshot: CursorUsageSnapshot) -> None:
        self._refreshing = False
        self.snapshot = snapshot
        self._redraw()

    def _redraw(self) -> None:
        self.canvas.delete("all")
        size = self.size
        pad = 8
        x0, y0 = pad, pad
        x1, y1 = size - pad, size - pad
        percent = self.snapshot.used_percent
        color = _ring_color(percent)

        self.canvas.create_oval(
            x0,
            y0,
            x1,
            y1,
            outline="#334155",
            width=5,
            fill="#111827",
        )

        if self.snapshot.status == "ok" and percent is not None:
            extent = -360.0 * min(max(percent / 100.0, 0.0), 1.0)
            self.canvas.create_arc(
                x0,
                y0,
                x1,
                y1,
                start=90,
                extent=extent,
                style="arc",
                outline=color,
                width=5,
            )
        elif self.snapshot.status == "no_auth":
            self.canvas.create_arc(
                x0,
                y0,
                x1,
                y1,
                start=90,
                extent=-90,
                style="arc",
                outline="#64748b",
                width=5,
            )

        if self.snapshot.status == "ok":
            primary = self.snapshot.center_primary
            secondary = self.snapshot.center_secondary
            self.canvas.create_text(
                size / 2,
                size / 2 - 5,
                text=primary,
                fill="#f8fafc",
                font=self._title_font,
            )
            self.canvas.create_text(
                size / 2,
                size / 2 + 9,
                text=f"/ {secondary}" if secondary else "",
                fill="#94a3b8",
                font=self._sub_font,
            )
        elif self.snapshot.status == "no_auth":
            self.canvas.create_text(
                size / 2,
                size / 2,
                text="login",
                fill="#94a3b8",
                font=self._sub_font,
            )
        else:
            self.canvas.create_text(
                size / 2,
                size / 2,
                text="?",
                fill="#94a3b8",
                font=self._title_font,
            )

        tooltip = self._tooltip_text()
        self.canvas.create_rectangle(0, 0, 0, 0, tags="tooltip-anchor")
        self.root.title(tooltip)

    def _tooltip_text(self) -> str:
        snap = self.snapshot
        if snap.status == "ok":
            parts = [f"Cursor: {snap.center_primary} / {snap.center_secondary or '—'}"]
            if snap.used_percent is not None:
                parts.append(f"{snap.used_percent:.0f}% used")
            if snap.plan_name:
                parts.append(snap.plan_name)
            if snap.reset_at:
                parts.append(f"reset {snap.reset_at}")
            parts.append("double-click: dashboard")
            return " · ".join(parts)
        return snap.message or "Cursor usage"

    def _on_press(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")

    def _on_release(self, event: tk.Event) -> None:
        moved = self._drag_offset is not None and (
            abs(event.x_root - self.root.winfo_x() - event.x) > 3
            or abs(event.y_root - self.root.winfo_y() - event.y) > 3
        )
        self._drag_offset = None
        if not moved:
            self._refresh_async()

    def _on_open_dashboard(self, _event: tk.Event | None = None) -> None:
        webbrowser.open(CURSOR_DASHBOARD_URL)

    def run(self) -> None:
        self._redraw()
        self.root.mainloop()


def _load_position_cache(path: Path) -> tuple[int | None, int | None]:
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    x = data.get("x")
    y = data.get("y")
    return (int(x) if isinstance(x, int) else None, int(y) if isinstance(y, int) else None)


def _save_position_cache(path: Path, widget: CursorUsageWidget) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"x": widget.root.winfo_x(), "y": widget.root.winfo_y()}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Floating Cursor usage ring widget")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--margin", type=int, default=DEFAULT_MARGIN)
    parser.add_argument("--poll-seconds", type=int, default=POLL_MS // 1000)
    parser.add_argument("--x", type=int, default=None)
    parser.add_argument("--y", type=int, default=None)
    parser.add_argument("--once", action="store_true", help="Fetch usage once and print JSON")
    parser.add_argument(
        "--always-visible",
        action="store_true",
        help="Keep the widget visible even when Cursor is not frontmost",
    )
    args = parser.parse_args()

    if args.once:
        print(json.dumps(fetch_cursor_usage().to_dict(), ensure_ascii=False, indent=2))
        return 0

    cache_path = ROOT / ".run" / "cursor-usage-widget.json"
    pos_x = args.x
    pos_y = args.y
    if pos_x is None and pos_y is None:
        pos_x, pos_y = _load_position_cache(cache_path)

    widget = CursorUsageWidget(
        size=args.size,
        margin=args.margin,
        poll_ms=max(60, args.poll_seconds) * 1000,
        x=pos_x,
        y=pos_y,
        only_when_cursor_active=not args.always_visible,
    )

    def on_close() -> None:
        _save_position_cache(cache_path, widget)
        widget.root.destroy()

    widget.root.protocol("WM_DELETE_WINDOW", on_close)
    widget.root.bind("<Destroy>", lambda _event: _save_position_cache(cache_path, widget))
    widget.run()
    return 0


if __name__ == "__main__":
    if sys.platform == "darwin" and not os.environ.get("TK_SILENCE_DEPRECATION"):
        os.environ["TK_SILENCE_DEPRECATION"] = "1"
    raise SystemExit(main())
