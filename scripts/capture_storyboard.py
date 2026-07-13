#!/usr/bin/env python3
"""Capture ResearchOS UI states for Figma storyboard handoff."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".figma-storyboard"
BASE = os.environ.get("KOI_UI_URL", "http://127.0.0.1:8080")
VIEWPORT = {"width": 1440, "height": 900}


def wait_for_app(page) -> None:
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_selector("#project-list .project-list__item, #project-list button", timeout=60_000)
    page.wait_for_timeout(1500)


def show_modal(page, modal_id: str) -> None:
    page.evaluate(
        """(id) => {
      document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
      document.getElementById('agent-chat-panel')?.classList.add('hidden');
      document.getElementById('rq-bell-panel')?.classList.add('hidden');
      document.getElementById(id)?.classList.remove('hidden');
    }""",
        modal_id,
    )
    page.wait_for_timeout(400)


def open_panel(page, panel_id: str) -> None:
    page.evaluate(
        """(id) => {
      document.getElementById(id)?.classList.remove('hidden');
    }""",
        panel_id,
    )
    page.wait_for_timeout(400)


def reset_ui(page) -> None:
    page.evaluate(
        """() => {
      document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
      document.getElementById('agent-chat-panel')?.classList.add('hidden');
      document.getElementById('rq-bell-panel')?.classList.add('hidden');
      document.getElementById('projects-sidebar')?.classList.remove('is-open');
      const toggle = document.getElementById('btn-projects-toggle');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    }"""
    )
    page.wait_for_timeout(300)


def set_theme(page, theme: str) -> None:
    page.evaluate(
        """(t) => {
      localStorage.setItem('koi-theme', t);
      document.documentElement.setAttribute('data-theme', t);
    }""",
        theme,
    )
    page.wait_for_timeout(200)


def set_view_mode(page, mode: str) -> None:
    page.select_option("#view-mode-select", mode)
    page.wait_for_timeout(1200)


def shot(page, name: str) -> str:
    file = OUT_DIR / f"{name}.png"
    page.screenshot(path=str(file), full_page=False)
    return str(file)


def open_sidebar(page) -> None:
    page.evaluate("""() => {
      const sidebar = document.getElementById('projects-sidebar');
      const toggle = document.getElementById('btn-projects-toggle');
      if (sidebar) sidebar.classList.add('is-open');
      if (toggle) toggle.setAttribute('aria-expanded', 'true');
    }""")
    page.wait_for_timeout(400)


def pick_project_with_data(page) -> None:
    llm = page.locator("#project-list button", has_text="Проблема обучения LLM")
    if llm.count():
        btn = llm.first
        if btn.get_attribute("aria-current") == "true":
            page.wait_for_timeout(400)
            return
        btn.click(force=True)
    else:
        page.locator("#project-list button[data-project-id]").first.click(force=True)
    page.wait_for_timeout(1200)


def click_first_method_kanban(page) -> bool:
    clicked = page.evaluate(
        """() => {
      const el = document.querySelector('.node-kanban-compact, .node-kanban-below');
      if (!el) return false;
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      return true;
    }"""
    )
    if clicked:
        page.wait_for_timeout(1000)
        return page.locator("#kanban-modal:not(.hidden)").count() > 0
    return False


def capture_theme(page, theme: str) -> list[str]:
    prefix = "light" if theme == "light" else "dark"
    files: list[str] = []

    wait_for_app(page)
    set_theme(page, theme)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    reset_ui(page)
    pick_project_with_data(page)

    for mode in ("chief", "teamlead", "researcher"):
        reset_ui(page)
        set_view_mode(page, mode)
        files.append(shot(page, f"{prefix}-01-lab-{mode}"))

    reset_ui(page)
    set_view_mode(page, "chief")
    open_sidebar(page)
    files.append(shot(page, f"{prefix}-02-sidebar-open"))

    reset_ui(page)
    set_view_mode(page, "chief")
    open_panel(page, "agent-chat-panel")
    files.append(shot(page, f"{prefix}-03-agent-chat"))

    reset_ui(page)
    open_panel(page, "rq-bell-panel")
    page.evaluate("""() => {
      const p = document.getElementById('rq-bell-panel');
      if (p) { p.hidden = false; p.classList.remove('hidden'); }
    }""")
    files.append(shot(page, f"{prefix}-04-rq-bell"))

    reset_ui(page)
    show_modal(page, "settings-modal")
    files.append(shot(page, f"{prefix}-05-settings"))

    reset_ui(page)
    show_modal(page, "create-project-modal")
    files.append(shot(page, f"{prefix}-06-create-project"))

    reset_ui(page)
    set_view_mode(page, "researcher")
    show_modal(page, "node-modal")
    page.evaluate("""() => {
      const t = document.getElementById('node-modal-type');
      const title = document.getElementById('node-title-display');
      const desc = document.getElementById('node-desc-display');
      if (t) t.textContent = 'Проблема';
      if (title) title.textContent = 'Проблема обучения LLM принятию решений в OOD средах';
      if (desc) { desc.textContent = 'Агент не обобщает на новые ситуации в embodied-средах.'; desc.classList.remove('is-empty'); }
      document.getElementById('node-edit-block')?.classList.remove('hidden');
      document.getElementById('add-child-block')?.classList.add('hidden');
    }""")
    files.append(shot(page, f"{prefix}-07-node-edit"))

    reset_ui(page)
    set_view_mode(page, "researcher")
    if click_first_method_kanban(page):
        files.append(shot(page, f"{prefix}-08-kanban"))

        page.evaluate(
            """() => {
          const el = document.querySelector('.method-questions-trigger');
          if (el) el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        }"""
        )
        page.wait_for_timeout(800)
        if page.locator("#method-questions-modal:not(.hidden)").count():
            files.append(shot(page, f"{prefix}-09-method-questions"))
            reset_ui(page)
            set_view_mode(page, "researcher")
            click_first_method_kanban(page)

        page.evaluate(
            """() => {
          const el = document.querySelector('.card-expand-report');
          if (el) el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        }"""
        )
        page.wait_for_timeout(1200)
        if page.locator("#card-report-modal:not(.hidden)").count():
            files.append(shot(page, f"{prefix}-10-card-report"))
        reset_ui(page)

    reset_ui(page)
    set_view_mode(page, "researcher")
    page.locator("#btn-knowledge").click(force=True)
    page.wait_for_timeout(1200)
    files.append(shot(page, f"{prefix}-11-knowledge-base"))

    page.locator("#knowledge-tab-log").click(force=True)
    page.wait_for_timeout(400)
    files.append(shot(page, f"{prefix}-12-knowledge-log"))
    reset_ui(page)

    reset_ui(page)
    set_view_mode(page, "researcher")
    page.locator("#btn-paper").click(force=True)
    page.wait_for_timeout(1200)
    files.append(shot(page, f"{prefix}-13-paper-draft"))
    reset_ui(page)

    live = page.locator('button.method-activity-inspect, button[title*="Live"], button[title*="монитор"]').first
    if live.count():
        reset_ui(page)
        set_view_mode(page, "researcher")
        live.click(force=True)
        page.wait_for_timeout(800)
        files.append(shot(page, f"{prefix}-14-live-monitor"))

    return files


def capture_standalone(page, theme: str) -> list[str]:
    prefix = "light" if theme == "light" else "dark"
    files: list[str] = []

    page.goto(f"{BASE}/literature.html", wait_until="networkidle")
    set_theme(page, theme)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    files.append(shot(page, f"{prefix}-15-literature"))

    page.goto(f"{BASE}/tour.html", wait_until="networkidle")
    set_theme(page, theme)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    files.append(shot(page, f"{prefix}-16-tour"))

    return files


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "both"
    themes = ["dark", "light"] if arg == "both" else (["light"] if arg == "light" else ["dark"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"capturedAt": datetime.now(timezone.utc).isoformat(), "base": BASE, "files": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = context.new_page()

        for theme in themes:
            manifest["files"].extend(capture_theme(page, theme))
            manifest["files"].extend(capture_standalone(page, theme))

        browser.close()

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Captured {len(manifest['files'])} screenshots → {OUT_DIR}")
    for f in manifest["files"]:
        print(" ", Path(f).name)


if __name__ == "__main__":
    main()
