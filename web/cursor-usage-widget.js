/**
 * Floating Cursor usage ring on the ResearchOS page (fixed overlay, draggable).
 */

import { KoiApi } from "./api.js";

const STORAGE_KEY = "koi-cursor-usage-widget-pos";
const USAGE_POLL_MS = 5 * 60 * 1000;
const RING_RADIUS = 32;
const RING_CIRC = 2 * Math.PI * RING_RADIUS;

const state = {
  dragging: false,
  moved: false,
  offsetX: 0,
  offsetY: 0,
  lastUsage: null,
  pollTimer: null,
};

function ringColor(percent) {
  if (percent == null) return "var(--cursor-usage-muted, #94a3b8)";
  if (percent >= 95) return "#f87171";
  if (percent >= 80) return "#fbbf24";
  return "#4ade80";
}

function loadPosition(root) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (Number.isFinite(data?.x) && Number.isFinite(data?.y)) {
      root.style.left = `${data.x}px`;
      root.style.top = `${data.y}px`;
      root.style.right = "auto";
    }
  } catch {
    /* ignore */
  }
}

function savePosition(root) {
  try {
    const rect = root.getBoundingClientRect();
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ x: Math.round(rect.left), y: Math.round(rect.top) })
    );
  } catch {
    /* ignore */
  }
}

function defaultPosition(root) {
  const margin = 18;
  const size = root.offsetWidth || 76;
  root.style.top = `${margin}px`;
  root.style.left = `${window.innerWidth - size - margin}px`;
  root.style.right = "auto";
}

function applyUsage(data) {
  const root = document.getElementById("cursor-usage-widget");
  if (!root) return;
  state.lastUsage = data;

  const primary = root.querySelector(".cursor-usage-widget__primary");
  const secondary = root.querySelector(".cursor-usage-widget__secondary");
  const progress = root.querySelector(".cursor-usage-widget__progress");
  const ringBtn = root.querySelector(".cursor-usage-widget__ring");

  if (data?.status === "ok") {
    primary.textContent = data.center_primary || "—";
    secondary.textContent = data.center_secondary ? `/ ${data.center_secondary}` : "";
    const pct = Number(data.used_percent);
    const ratio = Number.isFinite(pct) ? Math.min(Math.max(pct / 100, 0), 1) : 0;
    progress.style.strokeDashoffset = String(RING_CIRC * (1 - ratio));
    progress.style.stroke = ringColor(pct);
    const parts = [`Cursor: ${data.center_primary || "—"} / ${data.center_secondary || "—"}`];
    if (Number.isFinite(pct)) parts.push(`${Math.round(pct)}% used`);
    if (data.plan_name) parts.push(data.plan_name);
    if (data.reset_at) parts.push(`reset ${data.reset_at}`);
    ringBtn.title = parts.join(" · ");
    root.classList.toggle("cursor-usage-widget--warn", pct >= 80 && pct < 95);
    root.classList.toggle("cursor-usage-widget--danger", pct >= 95);
  } else if (data?.status === "no_auth") {
    primary.textContent = "login";
    secondary.textContent = "";
    progress.style.strokeDashoffset = String(RING_CIRC * 0.75);
    progress.style.stroke = "#64748b";
    ringBtn.title = data.message || "Войдите в Cursor IDE";
  } else {
    primary.textContent = "?";
    secondary.textContent = "";
    progress.style.strokeDashoffset = String(RING_CIRC);
    progress.style.stroke = "#64748b";
    ringBtn.title = data?.message || "Не удалось получить квоту Cursor";
  }
}

function setVisible(visible) {
  const root = document.getElementById("cursor-usage-widget");
  if (!root) return;
  root.classList.toggle("hidden", !visible);
}

async function refreshUsage() {
  try {
    const data = await KoiApi.getCursorUsage();
    applyUsage(data);
    setVisible(true);
  } catch (err) {
    applyUsage({ status: "error", message: err?.message || "API error" });
    setVisible(true);
  }
}

function bindDrag(root) {
  const handle = root.querySelector(".cursor-usage-widget__ring");
  if (!handle) return;

  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    state.dragging = true;
    state.moved = false;
    const rect = root.getBoundingClientRect();
    state.offsetX = event.clientX - rect.left;
    state.offsetY = event.clientY - rect.top;
    handle.setPointerCapture?.(event.pointerId);
    root.classList.add("cursor-usage-widget--dragging");
    event.preventDefault();
  });

  handle.addEventListener("pointermove", (event) => {
    if (!state.dragging) return;
    const x = event.clientX - state.offsetX;
    const y = event.clientY - state.offsetY;
    if (Math.abs(x - root.offsetLeft) > 2 || Math.abs(y - root.offsetTop) > 2) {
      state.moved = true;
    }
    const maxX = Math.max(0, window.innerWidth - root.offsetWidth);
    const maxY = Math.max(0, window.innerHeight - root.offsetHeight);
    root.style.left = `${Math.min(maxX, Math.max(0, x))}px`;
    root.style.top = `${Math.min(maxY, Math.max(0, y))}px`;
    root.style.right = "auto";
  });

  const endDrag = (event) => {
    if (!state.dragging) return;
    state.dragging = false;
    root.classList.remove("cursor-usage-widget--dragging");
    handle.releasePointerCapture?.(event.pointerId);
    savePosition(root);
    if (!state.moved) {
      void refreshUsage();
    }
  };

  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);

  handle.addEventListener("dblclick", () => {
    window.open("https://cursor.com/dashboard", "_blank", "noopener,noreferrer");
  });
}

export function initCursorUsageWidget() {
  const root = document.getElementById("cursor-usage-widget");
  if (!root) return;

  const progress = root.querySelector(".cursor-usage-widget__progress");
  if (progress) {
    progress.style.strokeDasharray = String(RING_CIRC);
    progress.style.strokeDashoffset = String(RING_CIRC);
  }

  loadPosition(root);
  if (!root.style.left) defaultPosition(root);
  bindDrag(root);

  void refreshUsage();
  state.pollTimer = window.setInterval(() => void refreshUsage(), USAGE_POLL_MS);

  window.addEventListener("resize", () => {
    const rect = root.getBoundingClientRect();
    const maxX = Math.max(0, window.innerWidth - root.offsetWidth);
    const maxY = Math.max(0, window.innerHeight - root.offsetHeight);
    if (rect.left > maxX || rect.top > maxY) {
      root.style.left = `${Math.min(rect.left, maxX)}px`;
      root.style.top = `${Math.min(rect.top, maxY)}px`;
      savePosition(root);
    }
  });
}
