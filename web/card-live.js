/** Pull-based live monitor for running kanban cards (multi-card tabs + sidebar views). */

import { KoiApi } from "./api.js";

const POLL_MS = 3000;
const DEFAULT_VIEW = "metrics";

/** @typedef {'status' | 'log' | 'metrics' | 'note'} LiveView */

let pollTimer = null;
/** @type {Map<string, { ctx: object, data: object | null, view: LiveView, error?: string }>} */
const monitored = new Map();
let activeKey = null;
/** @type {() => Array<object>} */
let getRunningSeedCards = () => [];

function cardKey(ctx) {
  return `${ctx.projectId}:${ctx.boardId}:${ctx.cardId}`;
}

function cardTabTitle(entry, allEntries) {
  const ctx = entry.ctx;
  const card = truncateTitle(ctx.cardTitle);
  const projectIds = new Set(allEntries.map(([, e]) => e.ctx.projectId));
  const project = String(ctx.projectTitle || "").trim();
  if (projectIds.size > 1 && project) {
    return `${truncateTitle(project, 18)} · ${card}`;
  }
  return card;
}

function upsertMonitoredCard(ctx) {
  const key = cardKey(ctx);
  if (!monitored.has(key)) {
    monitored.set(key, {
      ctx: { ...ctx },
      data: null,
      view: DEFAULT_VIEW,
    });
  } else {
    const entry = monitored.get(key);
    Object.assign(entry.ctx, ctx);
  }
}

/**
 * @param {Record<string, { title?: string, boards?: object | object[], nodes?: object[] }>} projectsById
 */
export function runningCardContextsFromProjects(projectsById) {
  /** @type {Array<object>} */
  const items = [];
  for (const [projectId, project] of Object.entries(projectsById || {})) {
    const boards = Array.isArray(project.boards)
      ? project.boards
      : Object.values(project.boards || {});
    for (const board of boards) {
      const ownerNode = (project.nodes || []).find((n) => n.id === board.owner_node_id);
      for (const card of board.cards || []) {
        if (card.column_id !== "running") continue;
        items.push({
          projectId,
          projectTitle: project.title || projectId,
          boardId: board.id,
          cardId: card.id,
          cardTitle: card.title,
          methodTitle: ownerNode?.title || "",
        });
      }
    }
  }
  items.sort((a, b) => {
    const pa = String(a.projectTitle || a.projectId);
    const pb = String(b.projectTitle || b.projectId);
    if (pa !== pb) return pa.localeCompare(pb, "ru");
    return String(a.cardTitle || a.cardId).localeCompare(
      String(b.cardTitle || b.cardId),
      "ru"
    );
  });
  return items;
}

/** @param {() => Array<object>} provider */
export function setRunningSeedProvider(provider) {
  getRunningSeedCards = provider || (() => []);
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function truncateTitle(title, max = 28) {
  const t = String(title || "Эксперимент").trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

function subtasksHtml(subtasks) {
  const open = subtasks?.open || [];
  const done = subtasks?.done || [];
  if (!open.length && !done.length) {
    return `<p class="card-live-empty">Подзадачи не заданы в description карточки.</p>`;
  }
  const rows = [
    ...open.map(
      (t) =>
        `<li class="card-live-subtask is-open"><span class="card-live-subtask-mark">○</span>${escapeHtml(t)}</li>`
    ),
    ...done.map(
      (t) =>
        `<li class="card-live-subtask is-done"><span class="card-live-subtask-mark">✓</span>${escapeHtml(t)}</li>`
    ),
  ];
  return `<ul class="card-live-subtasks">${rows.join("")}</ul>`;
}

function metricsHtml(metrics, projectId) {
  if (!metrics?.configured) {
    return `<p class="card-live-empty">Укажите <code>metrics_dir: …</code> в description карточки или отчёте.</p>`;
  }
  if (metrics.error) {
    return `<p class="card-live-error">${escapeHtml(metrics.error)}</p>`;
  }
  if (!metrics.exists) {
    return `<p class="card-live-empty">Папка не найдена: <code>${escapeHtml(metrics.path)}</code></p>`;
  }
  const images = metrics.images || [];
  if (!images.length) {
    return `<p class="card-live-empty">В <code>${escapeHtml(metrics.path)}</code> пока нет png/jpg.</p>`;
  }
  const base = (metrics.resolved_path || metrics.path || "").replace(/\/$/, "");
  const tiles = images
    .map((img) => {
      const rel = `${base}/${img.name}`;
      const bust = img.mtime ? `&v=${encodeURIComponent(img.mtime)}` : "";
      const url = `${KoiApi.liveFileUrl(projectId, rel)}${bust}`;
      return `<a class="card-live-metric" href="${escapeHtml(url)}" target="_blank" rel="noopener">
        <img src="${escapeHtml(url)}" alt="${escapeHtml(img.name)}" loading="lazy" />
        <span>${escapeHtml(img.name)}</span>
      </a>`;
    })
    .join("");
  return `<div class="card-live-metrics-grid">${tiles}</div>`;
}

function logHtml(liveLog) {
  if (!liveLog?.configured) {
    return `<p class="card-live-empty">Укажите <code>live_log: …</code> в description карточки или отчёте.</p>`;
  }
  if (liveLog.error) {
    return `<p class="card-live-error">${escapeHtml(liveLog.error)}</p>`;
  }
  if (!liveLog.exists) {
    return `<p class="card-live-empty">Файл не найден: <code>${escapeHtml(liveLog.path)}</code></p>`;
  }
  const tail = liveLog.tail || "";
  return `<pre class="card-live-log" aria-live="polite">${escapeHtml(tail)}</pre>`;
}

function noteHtml(data) {
  const note = String(data?.live_note || "").trim();
  if (!note) {
    return `<p class="card-live-empty">Агент ещё не написал <code>live_note:</code> — краткий комментарий о ходе эксперимента (шаг, loss, статус).</p>`;
  }
  return `<div class="card-live-note-block"><p class="card-live-note-text">${escapeHtml(note)}</p></div>`;
}

function paneHtml(view, data, projectId) {
  switch (view) {
    case "status":
      return subtasksHtml(data?.subtasks);
    case "log":
      return logHtml(data?.live_log);
    case "metrics":
      return metricsHtml(data?.metrics_dir, projectId);
    case "note":
      return noteHtml(data);
    default:
      return "";
  }
}

function statusLine(entry) {
  const data = entry.data;
  if (entry.error) return entry.error;
  if (!data) return "Загрузка…";
  const current = data.subtasks?.open?.[0];
  if (current) return `Сейчас: ${current}`;
  if (data.column_id === "running") return "Эксперимент в работе";
  return "";
}

function renderCardTabs() {
  const tabsEl = document.getElementById("card-live-card-tabs");
  if (!tabsEl) return;

  if (!monitored.size) {
    tabsEl.innerHTML = `<p class="card-live-empty card-live-empty--tabs">Нет открытых карточек</p>`;
    return;
  }

  const entries = [...monitored.entries()];
  const tabs = entries
    .map(([key, entry]) => {
      const on = key === activeKey;
      const title = cardTabTitle(entry, entries);
      return `<button type="button" class="card-live-card-tab${on ? " is-active" : ""}" data-card-key="${escapeHtml(key)}" role="tab" aria-selected="${on}">
        <span class="card-live-card-tab__dot" aria-hidden="true"></span>
        <span class="card-live-card-tab__title">${escapeHtml(title)}</span>
      </button>`;
    })
    .join("");
  tabsEl.innerHTML = tabs;
}

function renderNav(view) {
  document.querySelectorAll(".card-live-nav-btn").forEach((btn) => {
    const on = btn.dataset.view === view;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-current", on ? "page" : "false");
  });
}

function renderActiveCard() {
  const methodEl = document.getElementById("card-live-method");
  const statusEl = document.getElementById("card-live-status");
  const paneHost = document.getElementById("card-live-pane-host");

  const entry = activeKey ? monitored.get(activeKey) : null;
  if (!entry) {
    if (methodEl) methodEl.textContent = "";
    if (statusEl) statusEl.textContent = "";
    if (paneHost) paneHost.innerHTML = `<p class="card-live-empty">Выберите карточку на карте (🔍) или вкладку выше.</p>`;
    renderNav(DEFAULT_VIEW);
    return;
  }

  const { ctx, data, view } = entry;
  if (methodEl) {
    methodEl.textContent = ctx.methodTitle ? `Метод: ${ctx.methodTitle}` : "";
  }
  if (statusEl) statusEl.textContent = statusLine(entry);
  renderNav(view);
  if (paneHost) {
    paneHost.innerHTML = paneHtml(view, data, ctx.projectId);
    if (view === "log") {
      const logPre = paneHost.querySelector(".card-live-log");
      if (logPre) logPre.scrollTop = logPre.scrollHeight;
    }
  }
}

function renderUI() {
  renderCardTabs();
  renderActiveCard();
}

function setActiveView(view) {
  if (!activeKey || !monitored.has(activeKey)) return;
  const entry = monitored.get(activeKey);
  if (!entry) return;
  entry.view = view;
  renderActiveCard();
}

function activateCard(key) {
  if (!monitored.has(key)) return;
  activeKey = key;
  renderUI();
}

async function syncRunningTabs(focusCtx, seedCards = []) {
  const focusKey = cardKey(focusCtx);
  const projectIds = new Set([focusCtx.projectId]);
  for (const ctx of seedCards) {
    if (ctx?.projectId) projectIds.add(ctx.projectId);
  }

  for (const ctx of seedCards) upsertMonitoredCard(ctx);

  for (const projectId of projectIds) {
    try {
      const data = await KoiApi.getKanbanRunningActivity(projectId);
      for (const item of data.items || []) {
        const existing = [...monitored.values()].find(
          (entry) =>
            entry.ctx.projectId === projectId &&
            entry.ctx.boardId === item.board_id &&
            entry.ctx.cardId === item.card_id
        );
        upsertMonitoredCard({
          projectId,
          projectTitle: existing?.ctx.projectTitle || "",
          boardId: item.board_id,
          cardId: item.card_id,
          cardTitle: item.title,
          methodTitle: existing?.ctx.methodTitle || "",
        });
      }
    } catch {
      /* running-activity optional */
    }
  }

  upsertMonitoredCard(focusCtx);
  if (!monitored.has(focusKey)) {
    activeKey = monitored.size ? [...monitored.keys()][0] : null;
  }
}

async function refreshCard(key) {
  const entry = monitored.get(key);
  if (!entry) return;
  try {
    const data = await KoiApi.getCardLive(
      entry.ctx.projectId,
      entry.ctx.boardId,
      entry.ctx.cardId
    );
    entry.data = data;
    entry.error = undefined;
    if (data.column_id && data.column_id !== "running") {
      monitored.delete(key);
      if (activeKey === key) {
        activeKey = monitored.size ? [...monitored.keys()][0] : null;
      }
    }
  } catch (err) {
    entry.error = String(err?.message || err);
  }
}

async function refreshAll() {
  if (!monitored.size) return;
  const anchor =
    (activeKey && monitored.get(activeKey)?.ctx) ||
    [...monitored.values()][0]?.ctx;
  if (anchor) {
    await syncRunningTabs(anchor, getRunningSeedCards());
  }
  await Promise.all([...monitored.keys()].map((key) => refreshCard(key)));
  renderUI();
  const stamp = document.getElementById("card-live-updated");
  if (stamp) stamp.textContent = `обновлено ${new Date().toLocaleTimeString()}`;
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function ensurePolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => void refreshAll(), POLL_MS);
}

/**
 * @param {{ projectId: string, boardId: string, cardId: string, cardTitle?: string, methodTitle?: string }} ctx
 * @param {{ showModal: (id: string) => void, hideModal: (id: string) => void }} ui
 */
export async function openCardLiveDrawer(ctx, ui) {
  const seedCards = getRunningSeedCards();
  const focusCtx = {
    ...ctx,
    projectTitle:
      ctx.projectTitle ||
      seedCards.find((item) => item.projectId === ctx.projectId)?.projectTitle ||
      "",
  };
  await syncRunningTabs(
    focusCtx,
    seedCards.length ? seedCards : [{ ...focusCtx, cardTitle: focusCtx.cardTitle || "Эксперимент" }]
  );
  activeKey = cardKey(focusCtx);
  if (!monitored.has(activeKey)) {
    activeKey = monitored.size ? [...monitored.keys()][0] : null;
  }
  ensurePolling();
  renderUI();
  ui.showModal("card-live-modal");
  void refreshAll();
}

export function closeCardLiveDrawer(ui) {
  stopPolling();
  monitored.clear();
  activeKey = null;
  ui.hideModal("card-live-modal");
}

export function bindCardLiveModal(ui) {
  document.getElementById("card-live-modal")?.addEventListener("click", (e) => {
    const cardTab = e.target.closest?.(".card-live-card-tab");
    if (cardTab?.dataset.cardKey) {
      activateCard(cardTab.dataset.cardKey);
      return;
    }

    const navBtn = e.target.closest?.(".card-live-nav-btn");
    if (navBtn?.dataset.view) setActiveView(/** @type {LiveView} */ (navBtn.dataset.view));
  });

  document.querySelectorAll('[data-close="card-live-modal"]').forEach((el) => {
    el.addEventListener("click", () => closeCardLiveDrawer(ui));
  });
}

/**
 * @param {HTMLElement} root
 * @param {{ projectId: string, boardId: string, card?: { id: string, title?: string }, cards?: Array<{ id: string, title?: string }>, methodTitle?: string }} ctx
 * @param {{ showModal: (id: string) => void, hideModal: (id: string) => void }} ui
 */
export function bindLiveInspectButtons(root, ctx, ui) {
  const cards = ctx.cards?.length ? ctx.cards : ctx.card ? [ctx.card] : [];
  const cardsById = Object.fromEntries(cards.map((c) => [c.id, c]));

  root.querySelectorAll(".method-activity-inspect").forEach((btn) => {
    if (btn.dataset.boundLive === "1") return;
    btn.dataset.boundLive = "1";
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const cardId =
        btn.dataset.cardId ||
        btn.closest("[data-card-id]")?.dataset.cardId ||
        ctx.card?.id;
      if (!cardId) return;
      const card = cardsById[cardId] || { id: cardId, title: "" };
      openCardLiveDrawer(
        {
          projectId: ctx.projectId,
          projectTitle: ctx.projectTitle || "",
          boardId: ctx.boardId,
          cardId: card.id,
          cardTitle: card.title,
          methodTitle: ctx.methodTitle,
        },
        ui
      );
    });
  });
}
