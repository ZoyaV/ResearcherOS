#!/usr/bin/env python3
"""Run a disposable two-instance WebRTC paper collaboration test on one Mac.

The script clones a project twice, gives each clone a unique local project ID,
starts two ResearcherOS APIs, two web proxies, and a content-blind signaling
service, then drives two isolated Chromium pages through concurrent edits.
All temporary repositories and processes are removed on exit.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ENGINE_ROOT / ".venv" / "bin" / "python"


def free_ports(count: int) -> list[int]:
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [int(sock.getsockname()[1]) for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def wait_http(url: str, processes: list[subprocess.Popen[Any]], timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"service exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"service did not become ready: {url}")


def project_mount(project_id: str) -> tuple[Path, Path]:
    sys.path.insert(0, str(ENGINE_ROOT))
    from koi.adapters.project_mount import get_mount_or_raise

    mount = get_mount_or_raise(project_id)
    return mount.repo_root, mount.koi_root


def set_project_id(project_md: Path, project_id: str) -> None:
    text = project_md.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"^id:\s*.*$",
        f"id: {project_id}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        if not text.startswith("---\n"):
            raise RuntimeError(f"cannot add project id to {project_md}")
        updated = f"---\nid: {project_id}\n{text[4:]}"
    project_md.write_text(updated, encoding="utf-8")


def clone_koi_relative(source_repo: Path, source_koi: Path) -> Path:
    try:
        return source_koi.resolve().relative_to(source_repo.resolve())
    except ValueError:
        # Canonical ResearchOS mounts may keep koi-structure in a separate
        # tree worktree while repo_root points at the project's code clone.
        return Path("koi-structure")


def clone_instance(
    source_repo: Path,
    source_koi: Path,
    destination: Path,
    *,
    project_id: str,
    slug: str,
) -> None:
    run(
        "git",
        "clone",
        "--quiet",
        "--no-hardlinks",
        str(source_repo),
        str(destination),
    )
    relative_koi = clone_koi_relative(source_repo, source_koi)
    clone_koi = destination / relative_koi
    clone_koi.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_koi / "project.md", clone_koi / "project.md")
    source_paper = source_koi / "paper" / slug
    if not source_paper.is_dir():
        raise FileNotFoundError(f"paper slot not found: {source_paper}")
    shutil.copytree(source_paper, clone_koi / "paper" / slug, dirs_exist_ok=True)
    set_project_id(clone_koi / "project.md", project_id)


def start_service(
    *command: str,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[Any]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.Popen(
        command,
        cwd=ENGINE_ROOT,
        env=merged,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_services(processes: list[subprocess.Popen[Any]]) -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5
    for process in reversed(processes):
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
    for process in processes:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


async def browser_test(
    *,
    web_a: int,
    web_b: int,
    project_a: str,
    project_b: str,
    slug: str,
    expected_text: str,
    tex_a: Path,
    tex_b: Path,
) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is unavailable. Install development dependencies first."
        ) from exc

    async def setup(page: Any, base: str, project_id: str) -> None:
        await page.goto(base, wait_until="domcontentloaded")
        await page.evaluate("window.__KOI_API_BASE__ = '/api'")
        await page.evaluate(
            """async ({project, slug}) => {
              const mod = await import('/paper-collab.js?v=p2p-disposable-test');
              window.testClient = mod.createPaperCollabClient({
                onState: () => {},
                onStatus: status => { window.testStatus = status; },
              });
              await window.testClient.connect(project, slug);
            }""",
            {"project": project_id, "slug": slug},
        )
        await page.wait_for_function("window.testClient?.isActive() === true")

    async def append(page: Any, text: str) -> None:
        await page.evaluate(
            """text => {
              const client = window.testClient;
              const before = client.currentText();
              const input = document.createElement('textarea');
              input.value = before;
              input.selectionStart = input.selectionEnd = before.length;
              client.rememberCaret(input);
              input.value = before + text;
              input.selectionStart = input.selectionEnd = input.value.length;
              client.queueInput(input, {inputType: 'insertText', data: text});
            }""",
            text,
        )

    errors: list[str] = []
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
        except Exception as exc:
            raise RuntimeError(
                "Chromium is unavailable. Run: ./.venv/bin/playwright install chromium"
            ) from exc
        page_a = await browser.new_page()
        page_b = await browser.new_page()
        page_a.on("pageerror", lambda exc: errors.append(f"A: {exc}"))
        page_b.on("pageerror", lambda exc: errors.append(f"B: {exc}"))
        try:
            await setup(page_a, f"http://127.0.0.1:{web_a}/", project_a)
            await setup(page_b, f"http://127.0.0.1:{web_b}/", project_b)
            await page_a.wait_for_function(
                "window.testStatus?.network?.remotePeerCount === 1"
            )
            await page_b.wait_for_function(
                "window.testStatus?.network?.remotePeerCount === 1"
            )
            if await page_a.evaluate("window.testClient.currentText()") != expected_text:
                raise AssertionError("instance A did not load the expected initial text")
            if await page_b.evaluate("window.testClient.currentText()") != expected_text:
                raise AssertionError("instance B did not converge to the expected initial text")

            await append(page_a, "\n% P2P from Alice")
            await page_b.wait_for_function(
                "window.testClient.currentText().includes('% P2P from Alice')"
            )

            await asyncio.gather(
                append(page_a, "[A]"),
                append(page_b, "[B]"),
            )
            both = (
                "window.testClient.currentText().includes('[A]') && "
                "window.testClient.currentText().includes('[B]')"
            )
            await page_a.wait_for_function(both)
            await page_b.wait_for_function(both)
            converged_a = await page_a.evaluate("window.testClient.currentText()")
            converged_b = await page_b.evaluate("window.testClient.currentText()")
            if converged_a != converged_b:
                raise AssertionError("concurrent browser edits did not converge")

            await page_b.evaluate("window.testClient.disconnect()")
            await append(page_a, "\n% while Bob was offline")
            await page_b.evaluate(
                """async ({project, slug}) => {
                  await window.testClient.connect(project, slug);
                }""",
                {"project": project_b, "slug": slug},
            )
            await page_b.wait_for_function(
                "window.testClient.currentText().includes('while Bob was offline')"
            )
            if await page_a.evaluate("window.testClient.currentText()") != await page_b.evaluate(
                "window.testClient.currentText()"
            ):
                raise AssertionError("reconnected peer did not converge")

            await page_a.evaluate("window.testClient.requestFlush()")
            await page_b.evaluate("window.testClient.requestFlush()")
            final_text = await page_a.evaluate("window.testClient.currentText()")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if (
                    tex_a.read_text(encoding="utf-8") == final_text
                    and tex_b.read_text(encoding="utf-8") == final_text
                ):
                    break
                await asyncio.sleep(0.1)
            else:
                raise AssertionError("isolated main.tex files were not materialized equally")
            if errors:
                raise AssertionError(f"browser errors: {errors}")
            return {
                "p2p_connected": True,
                "concurrent_edits_converged": True,
                "reconnect_converged": True,
                "isolated_files_equal": True,
            }
        finally:
            await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test paper WebRTC collaboration using two disposable local clones."
    )
    parser.add_argument("--project", required=True, help="Source ResearchOS project ID")
    parser.add_argument("--slug", required=True, help="Paper slug under koi-structure/paper")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not VENV_PYTHON.is_file():
        print("ResearchOS virtualenv is missing; run ./scripts/koi-serve.sh start", file=sys.stderr)
        return 2
    source_repo, source_koi = project_mount(args.project)
    expected_text = (source_koi / "paper" / args.slug / "main.tex").read_text(encoding="utf-8")
    processes: list[subprocess.Popen[Any]] = []
    with tempfile.TemporaryDirectory(prefix="researchos-p2p-") as raw_temp:
        temp = Path(raw_temp)
        clone_a = temp / "instance-a"
        clone_b = temp / "instance-b"
        project_a = "p2p-test-a"
        project_b = "p2p-test-b"
        clone_instance(
            source_repo,
            source_koi,
            clone_a,
            project_id=project_a,
            slug=args.slug,
        )
        clone_instance(
            source_repo,
            source_koi,
            clone_b,
            project_id=project_b,
            slug=args.slug,
        )
        relative_koi = clone_koi_relative(source_repo, source_koi)
        tex_a = clone_a / relative_koi / "paper" / args.slug / "main.tex"
        tex_b = clone_b / relative_koi / "paper" / args.slug / "main.tex"

        signal_port, api_a, api_b, web_a, web_b = free_ports(5)
        secret = "disposable-p2p-test-secret"
        common = {
            "KOI_SCAN_ROOTS": str(temp),
            "KOI_COLLAB_SIGNALING_URL": f"ws://127.0.0.1:{signal_port}/signal",
            "KOI_COLLAB_TOKEN_SECRET": secret,
        }
        try:
            processes.append(
                start_service(
                    str(VENV_PYTHON),
                    "-m",
                    "uvicorn",
                    "koi.paper.collaboration.signaling_service:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(signal_port),
                    env={"KOI_COLLAB_TOKEN_SECRET": secret},
                )
            )
            for port in (api_a, api_b):
                processes.append(
                    start_service(
                        str(VENV_PYTHON),
                        "-m",
                        "uvicorn",
                        "api.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        env=common,
                    )
                )
            processes.append(
                start_service(
                    str(VENV_PYTHON),
                    "-m",
                    "api.web_proxy",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(web_a),
                    "--api-host",
                    "127.0.0.1",
                    "--api-port",
                    str(api_a),
                )
            )
            processes.append(
                start_service(
                    str(VENV_PYTHON),
                    "-m",
                    "api.web_proxy",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(web_b),
                    "--api-host",
                    "127.0.0.1",
                    "--api-port",
                    str(api_b),
                )
            )
            wait_http(f"http://127.0.0.1:{signal_port}/health", processes)
            wait_http(f"http://127.0.0.1:{api_a}/health", processes)
            wait_http(f"http://127.0.0.1:{api_b}/health", processes)
            wait_http(f"http://127.0.0.1:{web_a}/api/health", processes)
            wait_http(f"http://127.0.0.1:{web_b}/api/health", processes)
            result = asyncio.run(
                browser_test(
                    web_a=web_a,
                    web_b=web_b,
                    project_a=project_a,
                    project_b=project_b,
                    slug=args.slug,
                    expected_text=expected_text,
                    tex_a=tex_a,
                    tex_b=tex_b,
                )
            )
            print("P2P paper collaboration test passed:")
            for key, value in result.items():
                print(f"  {key}: {value}")
            return 0
        finally:
            stop_services(processes)


if __name__ == "__main__":
    raise SystemExit(main())
