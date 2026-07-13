#!/usr/bin/env node
/**
 * Capture ResearchOS UI states for Figma storyboard handoff.
 * Usage: node scripts/capture-storyboard.mjs [--theme dark|light|both]
 */
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, ".figma-storyboard");
const BASE = process.env.KOI_UI_URL || "http://127.0.0.1:8080";
const VIEWPORT = { width: 1440, height: 900 };

async function waitForApp(page) {
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.waitForSelector("#project-list .project-list__item, #project-list button", {
    timeout: 60_000,
  });
  await page.waitForTimeout(1500);
}

async function resetUi(page) {
  await page.evaluate(() => {
    document.querySelectorAll(".modal").forEach((m) => m.classList.add("hidden"));
    document.getElementById("agent-chat-panel")?.classList.add("hidden");
    document.getElementById("rq-bell-panel")?.classList.add("hidden");
    document.getElementById("projects-sidebar")?.classList.remove("is-open");
    const toggle = document.getElementById("btn-projects-toggle");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  });
  await page.waitForTimeout(300);
}

async function setTheme(page, theme) {
  await page.evaluate((t) => {
    localStorage.setItem("koi-theme", t);
    document.documentElement.setAttribute("data-theme", t);
  }, theme);
  await page.waitForTimeout(200);
}

async function setViewMode(page, mode) {
  await page.selectOption("#view-mode-select", mode);
  await page.waitForTimeout(1200);
}

async function shot(page, name, opts = {}) {
  const file = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false, ...opts });
  return file;
}

async function openSidebar(page) {
  const toggle = page.locator("#btn-projects-toggle");
  if ((await toggle.getAttribute("aria-expanded")) !== "true") {
    await toggle.click();
    await page.waitForTimeout(400);
  }
}

async function pickProjectWithData(page) {
  const llm = page.locator("#project-list button", {
    hasText: "Проблема обучения LLM",
  });
  if (await llm.count()) {
    await llm.first().click();
    await page.waitForTimeout(1200);
    return;
  }
  const any = page.locator("#project-list button[data-project-id]").first();
  await any.click();
  await page.waitForTimeout(1200);
}

async function clickFirstMethodKanban(page) {
  const btn = page.locator('button.node-kanban-below, button[class*="kanban"]').first();
  if (await btn.count()) {
    await btn.click({ force: true });
    await page.waitForTimeout(800);
    return true;
  }
  const method = page.locator('button[data-node-type="method"], .node-wrap[data-node-type="method"]').first();
  if (await method.count()) {
    await method.click({ force: true });
    await page.waitForTimeout(400);
  }
  const kanbanLink = page.locator('button:has-text("канбан"), button[title*="анбан"], .node-kanban-below').first();
  if (await kanbanLink.count()) {
    await kanbanLink.click({ force: true });
    await page.waitForTimeout(800);
    return true;
  }
  return false;
}

async function captureTheme(page, theme) {
  const prefix = theme === "light" ? "light" : "dark";
  await setTheme(page, theme);
  await resetUi(page);
  await waitForApp(page);
  await pickProjectWithData(page);

  const captures = [];

  // View modes
  for (const mode of ["chief", "teamlead", "researcher"]) {
    await resetUi(page);
    await setViewMode(page, mode);
    captures.push(await shot(page, `${prefix}-01-lab-${mode}`));
  }

  await resetUi(page);
  await setViewMode(page, "chief");
  await openSidebar(page);
  captures.push(await shot(page, `${prefix}-02-sidebar-open`));

  await resetUi(page);
  await setViewMode(page, "chief");
  await page.locator("#btn-agent-chat").click();
  await page.waitForTimeout(500);
  captures.push(await shot(page, `${prefix}-03-agent-chat`));

  await resetUi(page);
  await page.locator("#btn-rq-bell").click();
  await page.waitForTimeout(400);
  captures.push(await shot(page, `${prefix}-04-rq-bell`));

  await resetUi(page);
  await page.locator("#btn-settings").click();
  await page.waitForTimeout(400);
  captures.push(await shot(page, `${prefix}-05-settings`));

  await resetUi(page);
  await page.locator("#btn-new-project").click();
  await page.waitForTimeout(400);
  captures.push(await shot(page, `${prefix}-06-create-project`));

  await resetUi(page);
  await setViewMode(page, "researcher");
  const problem = page.locator('.node-wrap[data-node-type="problem"] button, button[data-node-type="problem"]').first();
  if (await problem.count()) {
    await problem.click({ force: true });
    await page.waitForTimeout(600);
    captures.push(await shot(page, `${prefix}-07-node-edit`));
  }

  await resetUi(page);
  await setViewMode(page, "researcher");
  if (await clickFirstMethodKanban(page)) {
    captures.push(await shot(page, `${prefix}-08-kanban`));

    const rqBtn = page.locator('button:has-text("Выводы:")').first();
    if (await rqBtn.count()) {
      await rqBtn.click({ force: true });
      await page.waitForTimeout(600);
      captures.push(await shot(page, `${prefix}-09-method-questions`));
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }

    const reportBtn = page.locator('.kanban-card .card-report-link, .kanban-card button[title*="отч"]').first();
    if (await reportBtn.count()) {
      await reportBtn.click({ force: true });
      await page.waitForTimeout(600);
      captures.push(await shot(page, `${prefix}-10-card-report`));
      await page.locator('[data-close="card-report-modal"]').first().click();
      await page.waitForTimeout(300);
    }

    await page.locator('[data-close="kanban-modal"]').first().click();
    await page.waitForTimeout(300);
  }

  await resetUi(page);
  await setViewMode(page, "researcher");
  await page.locator("#btn-knowledge").click();
  await page.waitForTimeout(800);
  captures.push(await shot(page, `${prefix}-11-knowledge-base`));

  await page.locator("#knowledge-tab-log").click();
  await page.waitForTimeout(400);
  captures.push(await shot(page, `${prefix}-12-knowledge-log`));
  await page.locator('[data-close="knowledge-modal"]').first().click();

  await resetUi(page);
  await setViewMode(page, "researcher");
  await page.locator("#btn-paper").click();
  await page.waitForTimeout(800);
  captures.push(await shot(page, `${prefix}-13-paper-draft`));
  await page.locator('[data-close="paper-modal"]').first().click();

  const liveBtn = page.locator('button[title*="Live"], button[title*="монитор"], .method-activity-inspect').first();
  if (await liveBtn.count()) {
    await resetUi(page);
    await setViewMode(page, "researcher");
    await liveBtn.click({ force: true });
    await page.waitForTimeout(800);
    captures.push(await shot(page, `${prefix}-14-live-monitor`));
  }

  return captures;
}

async function captureStandalone(page, theme) {
  const prefix = theme === "light" ? "light" : "dark";
  const files = [];

  await setTheme(page, theme);

  await page.goto(`${BASE}/literature.html`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, `${prefix}-15-literature`));

  await page.goto(`${BASE}/tour.html`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, `${prefix}-16-tour`));

  return files;
}

async function main() {
  const arg = process.argv[2] || "both";
  const themes =
    arg === "both" ? ["dark", "light"] : arg === "light" ? ["light"] : ["dark"];

  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 2 });
  const page = await context.newPage();

  const manifest = { capturedAt: new Date().toISOString(), base: BASE, files: [] };

  for (const theme of themes) {
    manifest.files.push(...(await captureTheme(page, theme)));
    manifest.files.push(...(await captureStandalone(page, theme)));
  }

  await browser.close();

  await writeFile(
    path.join(OUT_DIR, "manifest.json"),
    JSON.stringify(manifest, null, 2),
    "utf8"
  );
  console.log(`Captured ${manifest.files.length} screenshots → ${OUT_DIR}`);
  for (const f of manifest.files) console.log(" ", path.basename(f));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
