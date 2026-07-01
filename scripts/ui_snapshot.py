#!/usr/bin/env python3
"""Headless UI snapshots for KOI visual QA (agent-readable PNGs)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / ".run" / "ui-screenshots"
DEFAULT_URL = "http://127.0.0.1:8080/"


async def capture(url: str, out_dir: Path) -> list[Path]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright not installed. Run:\n"
            "  .venv/bin/pip install playwright\n"
            "  .venv/bin/playwright install chromium"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await page.wait_for_selector("#mindmap-canvas", timeout=30_000)
        await page.wait_for_timeout(900)

        lab_checks = await page.evaluate(
            """() => {
              const frame = document.querySelector('.lab-project-frame');
              const style = frame ? getComputedStyle(frame) : null;
              return {
                canvas: !!document.getElementById('mindmap-canvas'),
                agentChat: !!document.getElementById('btn-agent-chat'),
                zoomControls: !!document.getElementById('btn-zoom-fit-project'),
                projectFrames: document.querySelectorAll('.lab-project-frame').length,
                frameBorderWidth: style ? style.borderWidth : null,
                frameBackground: style ? style.backgroundColor : null,
              };
            }"""
        )
        print(f"lab canvas: {lab_checks}")

        p1 = out_dir / "01-mindmap.png"
        await page.screenshot(path=str(p1), full_page=True)
        saved.append(p1)

        fit_lab = page.locator("#btn-zoom-fit-lab")
        if await fit_lab.count() > 0:
            await fit_lab.click()
            await page.wait_for_timeout(450)
            p5 = out_dir / "05-lab-overview.png"
            await page.screenshot(path=str(p5), full_page=True)
            saved.append(p5)

        fit_project = page.locator("#btn-zoom-fit-project")
        if await fit_project.count() > 0:
            await fit_project.click()
            await page.wait_for_timeout(550)
            p6 = out_dir / "06-project-zoom.png"
            await page.screenshot(path=str(p6), full_page=True)
            saved.append(p6)

        toggle = page.locator("#btn-projects-toggle")
        if await toggle.count() > 0:
            await toggle.click()
            await page.wait_for_timeout(450)
            p7 = out_dir / "07-sidebar-programs.png"
            await page.screenshot(path=str(p7), full_page=True)
            saved.append(p7)
            await toggle.click()
            await page.wait_for_timeout(300)

        method = page.locator(".node-wrap.has-research-questions").first
        if await method.count() > 0:
            await method.hover()
            await page.wait_for_timeout(350)
            p2 = out_dir / "02-method-hover.png"
            await page.screenshot(path=str(p2), full_page=True)
            saved.append(p2)

            trigger = method.locator(".method-questions-trigger")
            if await trigger.count() > 0:
                gap_ok = await page.evaluate(
                    """() => {
                      const wrap = document.querySelector('.node-wrap.has-research-questions');
                      const trig = wrap?.querySelector('.method-questions-trigger');
                      const node = wrap?.querySelector('.map-node.method');
                      if (!trig || !node) return false;
                      const t = trig.getBoundingClientRect();
                      const n = node.getBoundingClientRect();
                      return t.bottom <= n.top - 2;
                    }"""
                )
                print(f"badge above method: {gap_ok}")
                await trigger.screenshot(path=str(out_dir / "02b-badge.png"))
                saved.append(out_dir / "02b-badge.png")
                await trigger.click()
                await page.wait_for_timeout(400)
                p3 = out_dir / "03-questions-modal.png"
                await page.screenshot(path=str(p3), full_page=True)
                saved.append(p3)

        kanban_method = page.locator(".map-node.method.has-kanban").first
        if await kanban_method.count() > 0:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
            await kanban_method.click()
            await page.wait_for_timeout(400)
            p4 = out_dir / "04-kanban-modal.png"
            await page.screenshot(path=str(p4), full_page=True)
            saved.append(p4)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)

        bell = page.locator("#btn-rq-bell")
        if await bell.count() > 0:
            await page.evaluate(
                """() => {
                  localStorage.removeItem('koi-rq-discoveries-read');
                }"""
            )
            await page.reload(wait_until="networkidle")
            await page.wait_for_timeout(900)
            p8 = out_dir / "08-rq-bell-badge.png"
            await page.locator(".topbar").screenshot(path=str(p8))
            saved.append(p8)

            await bell.click()
            await page.wait_for_timeout(350)
            p9 = out_dir / "09-rq-bell-panel.png"
            panel = page.locator("#rq-bell-panel")
            if await panel.count() > 0:
                await panel.screenshot(path=str(p9))
            else:
                await page.screenshot(path=str(p9), full_page=True)
            saved.append(p9)

            await page.evaluate(
                """() => {
                  const stack = document.getElementById('rq-discovery-stack');
                  if (!stack) return;
                  const el = document.createElement('article');
                  el.className = 'rq-discovery-toast';
                  el.innerHTML = `
                    <button type="button" class="rq-discovery-toast__close" aria-label="Закрыть">×</button>
                    <p class="rq-discovery-toast__badge">Новое открытие</p>
                    <p class="rq-discovery-toast__title">wingrune ответил(а) на исследовательский вопрос!</p>
                    <p class="rq-discovery-toast__q">Масштабируется ли успех zero-shot агента с оператором?</p>
                    <p class="rq-discovery-toast__a">Да в KARA: чем больше модель, тем дальше по crafting hierarchy.</p>
                  `;
                  stack.appendChild(el);
                }"""
            )
            await page.wait_for_timeout(400)
            p10 = out_dir / "10-rq-discovery-toast.png"
            await page.screenshot(path=str(p10), full_page=True)
            saved.append(p10)

        await browser.close()

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture KOI UI screenshots")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    paths = asyncio.run(capture(args.url, args.out))
    for path in paths:
        print(path)
    if not paths:
        print("No screenshots captured", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
