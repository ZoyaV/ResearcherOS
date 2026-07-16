import {
  bindCardLiveModal,
  bindLiveInspectButtons,
  cardHasLiveHints,
  cardHasLiveHintsFromSources,
  runningCardContextsFromProjects,
  setRunningSeedProvider,
} from "./card-live.js";
import { KoiApi } from "./api.js?v=20260715a";
import { destroyKanbanDagView, fitKanbanDagView, refreshKanbanDagView } from "./kanban-dag.js?v=20260715a";
import {
  koiLoaderTypingHtml,
  refreshInlineLoaderHints,
  clearInlineLoaderHints,
  showKoiLoader,
  hideKoiLoader,
} from "./koi-loader.js";
import { MindmapCamera } from "./lab-canvas.js";
import { renderMarkdown } from "./markdown.js";
import { initImageLightbox } from "./image-lightbox.js?v=20260703b";
import { initCursorUsageWidget } from "./cursor-usage-widget.js?v=20260710f";
import {
  METHOD_ACTIVITY_H,
  bindMethodActivityZoomPreview,
  getMethodActivityState,
  isMapZoomedOut,
  shouldUseActivityOverlay,
  syncMethodActivity,
  syncMethodActivityOverlay,
  syncMethodActivityZoomMode,
  subtasksFromDescription,
} from "./method-activity.js";
import {
  NODE_TYPE_HELP,
  formatAddChildContextHint,
  formatAddChildFormatHint,
  formatAddParentIntro,
  mountAddNodeButton,
  mountNodeTypeHelp,
} from "./node-tree-help.js";

function isHubMode() {
  return Boolean(window.__HUB__?.slug);
}

function escapeHubHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function bindHubAccountMenu(root) {
  const trigger = root.querySelector("#hub-account-trigger");
  const menu = root.querySelector("#hub-account-menu");
  if (!trigger || !menu) return;

  function closeMenu() {
    menu.classList.add("hidden");
    trigger.setAttribute("aria-expanded", "false");
  }

  function openMenu() {
    menu.classList.remove("hidden");
    trigger.setAttribute("aria-expanded", "true");
  }

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    if (menu.classList.contains("hidden")) openMenu();
    else closeMenu();
  });

  menu.querySelector('[data-action="logout"]')?.addEventListener("click", async () => {
    closeMenu();
    await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
    location.href = "/";
  });

  document.addEventListener("click", (e) => {
    if (!root.contains(e.target)) closeMenu();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
  });
}

function renderHubViewerAccount(slot, me) {
  if (!slot) return;
  if (!me?.authenticated || !me.user) {
    slot.innerHTML =
      '<a class="hub-nav-link hub-nav-link--accent" href="/auth/github">Войти</a>';
    return;
  }
  const u = me.user;
  slot.innerHTML =
    '<div class="hub-account">' +
    '<button type="button" class="user-chip hub-account__trigger" id="hub-account-trigger" aria-expanded="false" aria-haspopup="menu" aria-controls="hub-account-menu">' +
    '<img src="' +
    escapeHubHtml(u.avatar_url) +
    '" alt="" width="22" height="22" />' +
    "<span>@" +
    escapeHubHtml(u.login) +
    "</span>" +
    '<span class="hub-account__chevron" aria-hidden="true">▾</span>' +
    "</button>" +
    '<div class="hub-account__menu hidden" id="hub-account-menu" role="menu">' +
    '<a class="hub-account__item" href="/connect" role="menuitem">Подключить репозиторий</a>' +
    '<button type="button" class="hub-account__item hub-account__item--danger" data-action="logout" role="menuitem">Выйти</button>' +
    "</div>" +
    "</div>";
  bindHubAccountMenu(slot);
}

async function hydrateHubViewerAccount() {
  const slot = document.getElementById("hub-viewer-account");
  if (!slot) return;
  try {
    const res = await fetch("/api/me", { credentials: "same-origin" });
    if (!res.ok) throw new Error("auth");
    renderHubViewerAccount(slot, await res.json());
  } catch {
    renderHubViewerAccount(slot, null);
  }
}

function applyHubReadonlyChrome() {
  document.body.classList.add("hub-readonly");
  for (const id of [
    "btn-sync",
    "btn-settings",
    "btn-new-project",
    "btn-agent-chat",
    "btn-knowledge",
    "btn-related-work",
    "btn-paper",
    "cursor-usage-widget",
    "btn-rq-bell",
    "card-live-modal",
  ]) {
    document.getElementById(id)?.classList.add("hidden");
  }
  document.querySelector(".workspace-dock")?.classList.add("hidden");
  document.querySelector(".projects-sidebar__footer")?.classList.add("hidden");
  document.querySelector(".agent-chat-panel")?.classList.add("hidden");
  document.querySelector(".topbar-nav a[href='tour.html']")?.classList.add("hidden");
  const toolbar = document.querySelector(".toolbar");
  if (toolbar) {
    let wrap = document.getElementById("hub-toolbar-links");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "hub-toolbar-links";
      toolbar.prepend(wrap);
    }
    wrap.className = "hub-toolbar-links";
    wrap.innerHTML =
      '<a class="hub-nav-link" href="/" title="К каталогу Hub">← Каталог</a>' +
      '<span class="hub-toolbar-sep" aria-hidden="true"></span>' +
      '<div id="hub-viewer-account" class="hub-viewer-account">' +
      '<span class="hub-nav-link hub-nav-link--muted">…</span>' +
      "</div>";
    void hydrateHubViewerAccount();
  }
  const tagline = document.getElementById("brand-tagline");
  if (tagline && window.__HUB__?.meta?.owner_login) {
    tagline.textContent =
      "Hub · @" + window.__HUB__.meta.owner_login + " · только просмотр";
  }
}

async function resolveHubProjectId() {
  const slug = window.__HUB__.slug;
  const token = new URLSearchParams(window.location.search).get("token");
  const url =
    "/api/projects/" +
    encodeURIComponent(slug) +
    (token ? "?token=" + encodeURIComponent(token) : "");
  const res = await fetch(url, { credentials: "same-origin" });
  if (!res.ok) {
    const detail = res.status === 403 ? "Нет доступа к проекту" : "Проект не найден";
    throw new Error(detail);
  }
  const snap = await res.json();
  window.__HUB__.meta = snap.meta || {};
  return snap.project?.id || null;
}

/** Бейдж вердикта на узле-гипотезе (cause): подтверждена / опровергнута. */
const VERDICT_BADGES = {
  supported: { mark: "✔", label: "Гипотеза подтверждена" },
  refuted: { mark: "✗", label: "Гипотеза опровергнута" },
};

const TYPE_LABELS = {
  problem: "Проблема",
  cause: "Причина",
  cause_evidence: "Доказательство",
  remediation: "Гипотеза",
  method: "Метод",
  experiment: "Эксперимент",
};

const LAYOUT = {
  vGap: 44,
  hGap: 32,
  edgeCurve: 12,
  pad: 48,
  topPad: 52,
  kanbanExtra: 28,
};

/** Высота блока «канбан» + статистика + progress bar под карточкой (вне узла). */
const KANBAN_BELOW_H = 34;
const KANBAN_BELOW_W = 88;

const TYPE_ORDER = {
  problem: 0,
  cause: 1,
  cause_evidence: 2,
  remediation: 3,
  method: 4,
  experiment: 5,
};

const PROBLEM_MIN_W = 200;
const PROBLEM_MAX_W = 300;
const PROBLEM_MIN_H = 72;
const PROBLEM_MAX_H = 110;
const EXP_SIZE = 48;
const ADD_NODE_SIZE = { w: 80, h: 80, round: "50%" };

function addSlotId(parentId) {
  return `__add__${parentId}`;
}

function isAddSlot(id) {
  return typeof id === "string" && id.startsWith("__add__");
}

function addNodeSize() {
  return ADD_NODE_SIZE;
}

function canShowAddButton(node) {
  return (
    node.node_type === "problem" ||
    node.node_type === "cause" ||
    node.node_type === "cause_evidence" ||
    node.node_type === "remediation"
  );
}

function shouldShowAddSlot(node) {
  return canShowAddButton(node) && allowedChildTypes(node.node_type).length > 0;
}

const TEXT_METRICS = {
  maxW: 248,
  minW: 118,
  maxH: 220,
  padX: 12,
  padY: 9,
  labelH: 13,
  lineH: 12.5,
  titleFont: "600 10.5px Outfit, system-ui, sans-serif",
  labelFont: "700 8px Outfit, system-ui, sans-serif",
};

/** Компактные прямоугольники для гипотез (remediation). */
const HYPOTHESIS_METRICS = {
  maxW: 210,
  minW: 128,
  maxH: 88,
  padX: 10,
  padY: 6,
  labelH: 11,
  lineH: 11,
  round: "4px",
};

const RQ_BADGE_HOLD_MS = 2500;
const RQ_BADGE_FADE_MS = 5_000;
const RQ_IMPORTANCE_FILTER_KEY = "koi-rq-importance-min";
const RQ_IMPORTANCE_FILTER_OPTIONS = [
  { min: 1, label: "Все", title: "Показать все выводы" },
  { min: 2, label: "≥2", title: "Важность 2 и выше" },
  { min: 3, label: "≥3", title: "Важность 3 и выше" },
  { min: 4, label: "≥4", title: "Важность 4 и выше" },
  { min: 5, label: "★5", title: "Только ключевые выводы" },
];

const RESEARCH_CERTAINTY_LABELS = {
  definite: "С чётким ответом",
  tentative: "Предварительные выводы",
};

let state = {
  project: null,
  meta: null,
  lab: null,
  activeNodeId: null,
  kanbanNodeId: null,
  kanbanDisabledTagFilters: [],
  questionsNodeId: null,
  reportCardId: null,
  reportBoardId: null,
  reportRelativePath: null,
  reportDirty: false,
  nodeSizes: {},
  literatureResults: [],
};

let labCamera = null;
/** @type {string | null} projectId:nodeId pinned by fly-to-method */
let labWorldLayoutFull = null;
/** @type {Map<string, Record<string, string>>} */
const runningAuthorsByProject = new Map();
let labWorldLayout = null;

let _measureCtx;

function measureCtx() {
  if (!_measureCtx) {
    const canvas = document.createElement("canvas");
    _measureCtx = canvas.getContext("2d");
  }
  return _measureCtx;
}

function wrapTitleLines(title, maxInnerW) {
  const ctx = measureCtx();
  ctx.font = TEXT_METRICS.titleFont;
  const words = (title || "").split(/\s+/).filter(Boolean);
  if (!words.length) return [""];

  const lines = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxInnerW && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function computeNodeSize(node) {
  if (node.node_type === "experiment") {
    return { w: EXP_SIZE, h: EXP_SIZE, round: "50%" };
  }

  const isHypothesis =
    node.node_type === "remediation" || node.node_type === "method";
  const m = isHypothesis ? HYPOTHESIS_METRICS : TEXT_METRICS;
  const label = TYPE_LABELS[node.node_type] || "";
  const maxInnerW = m.maxW - m.padX * 2;
  const lines = wrapTitleLines(displayTitle(node), maxInnerW);
  const ctx = measureCtx();
  ctx.font = TEXT_METRICS.labelFont;
  const labelW = ctx.measureText(label).width;
  ctx.font = TEXT_METRICS.titleFont;
  const textW = Math.max(labelW, ...lines.map((l) => ctx.measureText(l).width), 0);

  const w = Math.ceil(Math.min(m.maxW, Math.max(m.minW, textW + m.padX * 2)));
  let h = m.padY * 2 + m.labelH + lines.length * m.lineH;
  h = Math.ceil(Math.min(m.maxH, Math.max(isHypothesis ? 44 : 50, h)));

  if (node.node_type === "problem") {
    const pw = Math.ceil(
      Math.min(PROBLEM_MAX_W, Math.max(PROBLEM_MIN_W, textW + m.padX * 2 + 8))
    );
    const ph = Math.ceil(
      Math.min(PROBLEM_MAX_H, Math.max(PROBLEM_MIN_H, h))
    );
    return { w: pw, h: ph, round: "50%", shape: "oval", lines };
  }

  return {
    w,
    h,
    round: isHypothesis ? HYPOTHESIS_METRICS.round : "12px",
    lines,
  };
}

function buildSizeCache() {
  const sizes = {};
  for (const n of state.project.nodes) {
    sizes[n.id] = computeNodeSize(n);
  }
  state.nodeSizes = sizes;
}

function nodeSize(node) {
  return state.nodeSizes[node.id] || computeNodeSize(node);
}

function formatAgentChatInline(text) {
  let s = escapeHtml(text);
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__(.+?)__/g, "<strong>$1</strong>");
  s = s.replace(/\*(.+?)\*/g, "<em>$1</em>");
  s = s.replace(/_(.+?)_/g, "<em>$1</em>");
  s = s.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  return s;
}

function formatAgentChatReply(text) {
  const src = text || "";
  const parts = [];
  let last = 0;
  const codeRe = /`([^`\n]+)`/g;
  let match;
  while ((match = codeRe.exec(src)) !== null) {
    if (match.index > last) {
      parts.push({ type: "text", value: src.slice(last, match.index) });
    }
    parts.push({ type: "code", value: match[1] });
    last = match.index + match[0].length;
  }
  if (last < src.length) parts.push({ type: "text", value: src.slice(last) });

  const body = parts.length
    ? parts
        .map((part) =>
          part.type === "code"
            ? `<code>${escapeHtml(part.value)}</code>`
            : formatAgentChatInline(part.value)
        )
        .join("")
    : formatAgentChatInline(src);

  return body.replace(/\n/g, "<br>");
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

/** Drop redundant «Причина:» / «Доказательство:» prefix when label is already shown. */
function getBoard(project, boardId) {
  if (!project?.boards || !boardId) return null;
  const boards = project.boards;
  if (Array.isArray(boards)) return boards.find((b) => b.id === boardId) || null;
  return boards[boardId] || null;
}

function getBoardForNode(project, node) {
  if (node.board_id) return getBoard(project, node.board_id);
  if (!project?.boards) return null;
  const list = Array.isArray(project.boards)
    ? project.boards
    : Object.values(project.boards);
  return list.find((b) => b.owner_node_id === node.id) || null;
}

function nodeHasKanban(node) {
  if (node.node_type !== "method") return false;
  return !!getBoardForNode(state.project, node);
}

function hasResearchQuestions(node) {
  return (node.research_questions?.length ?? 0) > 0;
}

function researchQuestionCounts(node) {
  const qs = node.research_questions || [];
  let definite = 0;
  let tentative = 0;
  for (const q of qs) {
    if (q.certainty === "definite") definite += 1;
    else tentative += 1;
  }
  return { definite, tentative, total: qs.length };
}

function researchQuestionNarrative(q) {
  const narrative = (q.narrative || "").trim();
  if (narrative) return narrative;
  return (q.answer || "").trim();
}

const rqBadgeTimers = new WeakMap();

function clearRqBadgeTimers(wrap) {
  const t = rqBadgeTimers.get(wrap);
  if (!t) return;
  if (t.hold) clearTimeout(t.hold);
  if (t.fadeEnd) clearTimeout(t.fadeEnd);
  rqBadgeTimers.delete(wrap);
}

function showResearchQuestionBadge(wrap, qBtn) {
  clearRqBadgeTimers(wrap);
  qBtn.classList.remove("is-fading", "is-hidden");
  void qBtn.offsetWidth;
  qBtn.classList.add("is-visible");
}

function scheduleResearchQuestionBadgeFade(wrap, qBtn) {
  clearRqBadgeTimers(wrap);
  const hold = setTimeout(() => {
    qBtn.classList.remove("is-visible");
    void qBtn.offsetWidth;
    qBtn.classList.add("is-fading");
    const fadeEnd = setTimeout(() => {
      qBtn.classList.remove("is-fading");
      qBtn.classList.add("is-hidden");
      rqBadgeTimers.delete(wrap);
    }, RQ_BADGE_FADE_MS);
    rqBadgeTimers.set(wrap, { fadeEnd });
  }, RQ_BADGE_HOLD_MS);
  rqBadgeTimers.set(wrap, { hold });
}

function wireResearchQuestionBadge(wrap, qBtn) {
  qBtn.classList.add("is-hidden");
  wrap.addEventListener("mouseenter", () => showResearchQuestionBadge(wrap, qBtn));
  wrap.addEventListener("mouseleave", () =>
    scheduleResearchQuestionBadgeFade(wrap, qBtn)
  );
  qBtn.addEventListener("focus", () => showResearchQuestionBadge(wrap, qBtn));
  qBtn.addEventListener("blur", () => scheduleResearchQuestionBadgeFade(wrap, qBtn));
}

function methodRegionKey(projectId, nodeId) {
  return `${projectId}:${nodeId}`;
}

function estimateKanbanBelowSize(board, nodeSizes, node) {
  const size = nodeSizes?.[node.id] || computeNodeSize(node);
  const inProc = (board?.cards || []).filter((c) => c.column_id === "running").length;
  const belowH = inProc > 0 ? KANBAN_BELOW_H + METHOD_ACTIVITY_H : KANBAN_BELOW_H;
  return {
    w: Math.max(size.w, KANBAN_BELOW_W),
    h: belowH,
  };
}

function computeMethodRegions(placements) {
  const regions = {};
  for (const placement of placements) {
    const { project, positions, nodeSizes } = placement;
    for (const node of project.nodes || []) {
      if (node.node_type !== "method") continue;
      const board = getBoardForNode(project, node);
      if (!board) continue;
      const pos = positions[node.id];
      if (!pos) continue;
      const size = nodeSizes?.[node.id] || computeNodeSize(node);
      const below = estimateKanbanBelowSize(board, nodeSizes, node);
      const w = Math.max(size.w, below.w) + 16;
      const h = size.h + 10 + below.h;
      const key = methodRegionKey(project.id, node.id);
      regions[key] = {
        projectId: project.id,
        nodeId: node.id,
        title: node.title,
        x: pos.x - w / 2,
        y: pos.y - size.h / 2,
        width: w,
        height: h,
      };
    }
  }
  return regions;
}

function findMethodRegion(projectId, nodeId) {
  return labCameraLayout()?.methodRegions?.[methodRegionKey(projectId, nodeId)] ?? null;
}

function flyToMethodNode(project, node) {
  const region = findMethodRegion(project.id, node.id);
  if (!region || !labCamera) return;
  labCamera.flyToRegion(region, 380, 8);
}

function kanbanStatsForNode(node, project = state.project) {
  const board = getBoardForNode(project, node);
  if (!board) return null;
  const cards = board.cards || [];
  const inProc = cards.filter((c) => c.column_id === "running").length;
  const done = cards.filter((c) => isKanbanCompletedColumn(c.column_id)).length;
  const tot = cards.length;
  return {
    tot,
    inProc,
    done,
    backlog: Math.max(0, tot - inProc - done),
  };
}

function kanbanProgressBarHtml(s) {
  return `<div class="node-kanban-progress${s.tot ? "" : " is-empty"}" role="progressbar"${
    s.tot
      ? ` aria-valuenow="${s.done}" aria-valuemin="0" aria-valuemax="${s.tot}" aria-label="done ${s.done} of ${s.tot}"`
      : ` aria-hidden="true"`
  }>
    <span class="node-kanban-progress-seg seg-done" style="flex:${s.done || 0}"></span>
    <span class="node-kanban-progress-seg seg-proc" style="flex:${s.inProc || 0}"></span>
    <span class="node-kanban-progress-seg seg-backlog" style="flex:${s.backlog || 0}"></span>
  </div>`;
}

function syncKanbanProgressBar(el, s) {
  if (!el) return;
  el.classList.toggle("is-empty", !s.tot);
  if (s.tot) {
    el.setAttribute("aria-valuenow", String(s.done));
    el.setAttribute("aria-valuemax", String(s.tot));
    el.setAttribute("aria-label", `done ${s.done} of ${s.tot}`);
    el.removeAttribute("aria-hidden");
  } else {
    el.removeAttribute("aria-valuenow");
    el.removeAttribute("aria-valuemax");
    el.removeAttribute("aria-label");
    el.setAttribute("aria-hidden", "true");
  }
  const segs = el.querySelectorAll(".node-kanban-progress-seg");
  if (segs.length === 3) {
    segs[0].style.flex = String(s.done || 0);
    segs[1].style.flex = String(s.inProc || 0);
    segs[2].style.flex = String(s.backlog || 0);
  }
}

function activityContextForProject(project) {
  const pid = project?.id;
  const authors = pid ? runningAuthorsByProject.get(pid) || {} : {};
  const hubOwner = window.__HUB__?.meta?.owner_login || "";
  return {
    projectTitle: project?.title || pid || "",
    authors,
    author: hubOwner || Object.values(authors)[0] || "",
    hideInspect: isHubMode(),
  };
}

const cardLiveUi = { showModal, hideModal };

function syncRunningSeedProvider() {
  const byId = state.lab?.projectsById;
  if (byId && Object.keys(byId).length) {
    setRunningSeedProvider(() => runningCardContextsFromProjects(state.lab.projectsById));
    return;
  }
  if (state.project?.id) {
    setRunningSeedProvider(() =>
      runningCardContextsFromProjects({ [state.project.id]: state.project })
    );
    return;
  }
  setRunningSeedProvider(() => []);
}

function bindMethodLiveInspect(root, node, board, project) {
  if (!root || !board?.id || !project?.id) return;
  const running = (board.cards || []).filter((c) => c.column_id === "running");
  if (!running.length) return;
  bindLiveInspectButtons(
    root,
    {
      projectId: nodeWriteProjectId(node) || project.id,
      projectTitle: project.title || project.id,
      boardId: board.id,
      cards: running,
      card: running[0],
      methodTitle: node?.title || "",
    },
    cardLiveUi
  );
}

async function ensureRunningAuthors(projectId, { force = false } = {}) {
  if (!projectId || (!force && runningAuthorsByProject.has(projectId))) {
    return runningAuthorsByProject.get(projectId) || {};
  }
  try {
    let authors = {};
    if (isCompositeVirtualId(projectId)) {
      const project =
        state.lab?.projectsById?.[projectId] ||
        (state.project?.id === projectId ? state.project : null);
      const memberIds = [
        ...new Set(
          (project?.members || [])
            .map((m) => m.project_id || m.id)
            .filter((id) => id && !isCompositeVirtualId(id))
        ),
      ];
      const maps = await Promise.all(
        memberIds.map((id) => ensureRunningAuthors(id, { force }))
      );
      for (const map of maps) Object.assign(authors, map);
    } else {
      const data = await KoiApi.getKanbanRunningActivity(projectId);
      authors = Object.fromEntries(
        (data.items || []).map((item) => [item.card_id, item.author || "коллега"])
      );
    }
    runningAuthorsByProject.set(projectId, authors);
    return authors;
  } catch {
    // Cache miss so we do not retry a failing endpoint on every paint.
    runningAuthorsByProject.set(projectId, {});
    return {};
  }
}

function formatRunningAuthorHint(author, task) {
  const who = String(author || "коллега").trim() || "коллега";
  const what = String(task || "эксперимент").trim() || "эксперимент";
  return `${who} и агент работают над задачей «${what}»`;
}

function applyRunningCardAuthorTitles(root, projectId) {
  if (!root || !projectId) return;
  const authors = runningAuthorsByProject.get(projectId) || {};
  const project =
    state.lab?.projectsById?.[projectId] ||
    (state.project?.id === projectId ? state.project : null);
  if (!project) return;
  const fallbackAuthor = window.__HUB__?.meta?.owner_login || "";

  const cardsById = new Map();
  for (const board of Object.values(project.boards || {})) {
    for (const card of board.cards || []) cardsById.set(card.id, card);
  }

  root.querySelectorAll(".kanban-card[data-card-id]").forEach((el) => {
    el.querySelector(":scope > .kanban-card-author")?.remove();
    const cardId = el.dataset.cardId;
    const card = cardsById.get(cardId);
    if (!card || card.column_id !== "running") return;
    const author = authors[cardId] || fallbackAuthor;
    if (!author) return;
    let task = card.title;
    const body = String(card.description || "").replace(/\\n/g, "\n");
    const m = body.match(/-\s*\[ \]\s*([^\n]+)/);
    if (m?.[1]?.trim()) task = m[1].trim();
    el.title = formatRunningAuthorHint(author, task);
    el.classList.add("kanban-card--running-active");
  });

  root.querySelectorAll(".kanban-dag-card--running[data-node-id]").forEach((el) => {
    el.querySelector(":scope > .kanban-dag-card__author")?.remove();
    const cardId = el.dataset.nodeId;
    const author = authors[cardId] || fallbackAuthor;
    if (!author) return;
    const card = cardsById.get(cardId);
    el.title = formatRunningAuthorHint(author, card?.title || cardId);
  });
}

/** @type {HTMLElement | null} */
let nodeWorkersPanelEl = null;
/** @type {ReturnType<typeof setTimeout> | null} */
let nodeWorkersHideTimer = null;
/** @type {HTMLElement | null} */
let nodeWorkersAnchor = null;

function descendantNodeIds(project, rootId) {
  const children = new Map();
  for (const node of project?.nodes || []) {
    const parent = node.parent_id;
    if (!parent) continue;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(node.id);
  }
  const out = new Set([rootId]);
  const stack = [rootId];
  while (stack.length) {
    const id = stack.pop();
    for (const child of children.get(id) || []) {
      if (out.has(child)) continue;
      out.add(child);
      stack.push(child);
    }
  }
  return out;
}

function authorMapsForProject(project) {
  const maps = [];
  const seen = new Set();
  const push = (id) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    maps.push(runningAuthorsByProject.get(id) || {});
  };
  push(project?.id);
  for (const m of project?.members || []) {
    push(m.project_id || m.id);
  }
  return maps;
}

function resolveRunningAuthor(project, cardId) {
  for (const map of authorMapsForProject(project)) {
    const who = String(map[cardId] || "").trim();
    if (who) return who;
  }
  return String(window.__HUB__?.meta?.owner_login || "").trim();
}

/**
 * People with running cards under this node (self + descendants).
 * @returns {Array<{ login: string, tasks: string[] }>}
 */
function runningWorkersUnderNode(project, nodeId) {
  if (!project || !nodeId) return [];
  const scope = descendantNodeIds(project, nodeId);
  /** @type {Map<string, string[]>} */
  const byAuthor = new Map();

  for (const node of project.nodes || []) {
    if (!scope.has(node.id) || node.node_type !== "method") continue;
    const board = getBoardForNode(project, node);
    for (const card of board?.cards || []) {
      if (card.column_id !== "running") continue;
      const login = resolveRunningAuthor(project, card.id) || "коллега";
      const task = String(card.title || card.id).trim();
      if (!byAuthor.has(login)) byAuthor.set(login, []);
      if (task) byAuthor.get(login).push(task);
    }
  }

  return [...byAuthor.entries()].map(([login, tasks]) => ({ login, tasks }));
}

function runningWorkersForCard(project, cardId) {
  if (!project || !cardId) return [];
  let card = null;
  for (const board of Object.values(project.boards || {})) {
    card = (board.cards || []).find((c) => c.id === cardId) || null;
    if (card) break;
  }
  if (!card || card.column_id !== "running") return [];
  const login = resolveRunningAuthor(project, cardId) || "коллега";
  return [{ login, tasks: [String(card.title || cardId).trim()].filter(Boolean) }];
}

function ensureNodeWorkersPanel() {
  if (nodeWorkersPanelEl) return nodeWorkersPanelEl;
  nodeWorkersPanelEl = document.createElement("aside");
  nodeWorkersPanelEl.id = "node-workers-panel";
  nodeWorkersPanelEl.className = "node-workers-panel hidden";
  nodeWorkersPanelEl.setAttribute("aria-live", "polite");
  document.body.appendChild(nodeWorkersPanelEl);
  nodeWorkersPanelEl.addEventListener("mouseenter", () => {
    if (nodeWorkersHideTimer) {
      clearTimeout(nodeWorkersHideTimer);
      nodeWorkersHideTimer = null;
    }
  });
  nodeWorkersPanelEl.addEventListener("mouseleave", () => hideNodeWorkersPanel());
  return nodeWorkersPanelEl;
}

function positionNodeWorkersPanel(anchor) {
  const panel = ensureNodeWorkersPanel();
  if (!anchor) return;
  const rect = anchor.getBoundingClientRect();
  const margin = 12;
  const panelRect = panel.getBoundingClientRect();
  let left = rect.right + margin;
  let top = rect.top;
  if (left + panelRect.width > window.innerWidth - margin) {
    left = rect.left - panelRect.width - margin;
  }
  if (left < margin) left = margin;
  if (top + panelRect.height > window.innerHeight - margin) {
    top = Math.max(margin, window.innerHeight - panelRect.height - margin);
  }
  if (top < margin) top = margin;
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}

function githubAvatarUrl(login) {
  const who = String(login || "").trim().replace(/^@/, "");
  if (!who || who === "коллега") return "";
  // Direct avatars host (no redirect). github.com/{user}.png is flaky with no-referrer.
  return `https://avatars.githubusercontent.com/${encodeURIComponent(who)}?s=64&v=4`;
}

function resolveWorkerAvatar(login) {
  const who = String(login || "").trim().replace(/^@/, "");
  const hubLogin = String(window.__HUB__?.meta?.owner_login || "").trim();
  const hubAvatar = String(window.__HUB__?.meta?.owner_avatar_url || "").trim();
  if (hubAvatar && who && who.toLowerCase() === hubLogin.toLowerCase()) {
    return hubAvatar;
  }
  return githubAvatarUrl(who);
}

function workerInitials(login) {
  const who = String(login || "·").trim().replace(/^@/, "");
  return (who.slice(0, 1) || "·").toUpperCase();
}

function renderNodeWorkersPanel(workers, _scopeLabel) {
  const panel = ensureNodeWorkersPanel();
  panel.innerHTML =
    `<p class="node-workers-panel__head">Тут работают:</p>` +
    `<ul class="node-workers-panel__list" role="list">` +
    workers
      .map((w) => {
        const login = String(w.login || "коллега").trim() || "коллега";
        const avatar = resolveWorkerAvatar(login);
        const initials = escapeHtml(workerInitials(login));
        const avatarHtml = avatar
          ? `<img class="node-workers-panel__avatar" src="${escapeHtml(avatar)}" alt="" width="28" height="28" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-fallback="${initials}" />`
          : `<span class="node-workers-panel__avatar node-workers-panel__avatar--fallback" aria-hidden="true">${initials}</span>`;
        return (
          `<li class="node-workers-panel__item">` +
          avatarHtml +
          `<span class="node-workers-panel__nick">@${escapeHtml(login)}</span>` +
          `</li>`
        );
      })
      .join("") +
    `</ul>`;

  panel.querySelectorAll("img.node-workers-panel__avatar").forEach((img) => {
    img.addEventListener(
      "error",
      () => {
        const fallback = document.createElement("span");
        fallback.className = "node-workers-panel__avatar node-workers-panel__avatar--fallback";
        fallback.setAttribute("aria-hidden", "true");
        fallback.textContent = img.dataset.fallback || "·";
        img.replaceWith(fallback);
      },
      { once: true }
    );
  });
}

function showNodeWorkersPanel(anchor, workers, scopeLabel) {
  if (!anchor || !workers?.length) {
    hideNodeWorkersPanel(true);
    return;
  }
  if (nodeWorkersHideTimer) {
    clearTimeout(nodeWorkersHideTimer);
    nodeWorkersHideTimer = null;
  }
  nodeWorkersAnchor = anchor;
  renderNodeWorkersPanel(workers, scopeLabel);
  const panel = ensureNodeWorkersPanel();
  panel.classList.remove("hidden", "is-leaving");
  panel.classList.add("is-entering");
  positionNodeWorkersPanel(anchor);
  requestAnimationFrame(() => {
    positionNodeWorkersPanel(anchor);
    panel.classList.add("is-visible");
    panel.classList.remove("is-entering");
  });
}

function hideNodeWorkersPanel(immediate = false) {
  const panel = ensureNodeWorkersPanel();
  const hide = () => {
    nodeWorkersHideTimer = null;
    nodeWorkersAnchor = null;
    panel.classList.remove("is-visible", "is-entering", "is-leaving");
    panel.classList.add("hidden");
  };
  if (immediate) {
    if (nodeWorkersHideTimer) clearTimeout(nodeWorkersHideTimer);
    hide();
    return;
  }
  if (nodeWorkersHideTimer) clearTimeout(nodeWorkersHideTimer);
  panel.classList.add("is-leaving");
  panel.classList.remove("is-visible");
  nodeWorkersHideTimer = setTimeout(hide, 180);
}

function wireNodeWorkersHover(wrap, project, node) {
  if (!wrap || !project || !node || wrap.dataset.workersBound === "1") return;
  wrap.dataset.workersBound = "1";
  const scopeLabel = TYPE_LABELS[node.node_type] || "узел";

  const show = () => {
    const reveal = () => {
      const workers = runningWorkersUnderNode(project, node.id);
      if (!workers.length) {
        hideNodeWorkersPanel(true);
        return;
      }
      showNodeWorkersPanel(wrap, workers, scopeLabel);
    };
    reveal();
    if (project?.id) {
      void ensureRunningAuthors(project.id).then(() => {
        if (!wrap.matches(":hover") && !ensureNodeWorkersPanel().matches(":hover")) return;
        reveal();
      });
    }
  };

  wrap.addEventListener("mouseenter", show);
  wrap.addEventListener("mouseleave", () => hideNodeWorkersPanel());
  wrap.addEventListener("focusin", show);
  wrap.addEventListener("focusout", () => hideNodeWorkersPanel());
}

function wireCardWorkersHover(root, project) {
  if (!root) return;
  if (project?.id) root.dataset.workersProjectId = project.id;
  if (root.dataset.workersBound === "1") return;
  root.dataset.workersBound = "1";

  const resolveProject = () => {
    const pid = root.dataset.workersProjectId;
    return (
      (pid && state.lab?.projectsById?.[pid]) ||
      (pid && state.project?.id === pid ? state.project : null) ||
      state.project
    );
  };

  root.addEventListener("pointerover", (e) => {
    const card =
      e.target.closest?.(".kanban-card[data-card-id]") ||
      e.target.closest?.(".kanban-dag-card[data-node-id]");
    if (!card || !root.contains(card)) return;
    const proj = resolveProject();
    if (!proj) return;
    const cardId = card.dataset.cardId || card.dataset.nodeId;
    const workers = runningWorkersForCard(proj, cardId);
    if (!workers.length) return;
    if (proj.id) void ensureRunningAuthors(proj.id);
    showNodeWorkersPanel(card, workers, "карточкой");
  });

  root.addEventListener("pointerout", (e) => {
    const card =
      e.target.closest?.(".kanban-card[data-card-id]") ||
      e.target.closest?.(".kanban-dag-card[data-node-id]");
    if (!card) return;
    const related = e.relatedTarget;
    if (related && (card.contains(related) || ensureNodeWorkersPanel().contains(related))) return;
    hideNodeWorkersPanel();
  });
}

function rebuildLabWorldLayoutFull() {
  if (!state.lab?.grouped || !state.lab?.projectsById) {
    labWorldLayoutFull = null;
    return null;
  }
  labWorldLayoutFull = layoutLaboratory(state.lab.grouped, state.lab.projectsById);
  return labWorldLayoutFull;
}

function runningActivityProjectIds() {
  const grouped = state.lab?.grouped;
  if (!grouped) return null;
  const mode = getViewMode();
  if (mode === "chief") return null;

  if (mode === "teamlead") {
    const programId = findProgramIdForProject(grouped, state.project?.id) ?? "";
    const ids = new Set();
    for (const g of grouped.groups || []) {
      if (g.id !== programId) continue;
      for (const c of g.composites || []) ids.add(compositeVirtualId(c.id));
      for (const p of g.projects || []) {
        if (!state.lab?.hiddenMemberIds?.has(p.id)) ids.add(p.id);
      }
    }
    if (programId === "") {
      for (const p of grouped.ungrouped || []) ids.add(p.id);
    }
    return ids;
  }

  const pid = state.project?.id;
  return pid ? new Set([pid]) : new Set();
}

function collectAllRunningActivityItems() {
  const layout = labWorldLayoutFull || rebuildLabWorldLayoutFull();
  if (!layout) return [];
  /** @type {Array<{ key: string, wx: number, wy: number, node: object, state: object, context: object }>} */
  const items = [];
  for (const placement of layout.placements) {
    const { project, positions, nodeSizes } = placement;
    for (const node of project.nodes || []) {
      if (node.node_type !== "method") continue;
      const board = getBoardForNode(project, node);
      const activityState = getMethodActivityState(board);
      if (!activityState.running.length) continue;
      const pos = positions[node.id];
      if (!pos) continue;
      const size = nodeSizes?.[node.id] || computeNodeSize(node);
      const belowH =
        activityState.running.length > 0
          ? KANBAN_BELOW_H + METHOD_ACTIVITY_H
          : KANBAN_BELOW_H;
      items.push({
        key: `${project.id}:${node.id}`,
        projectId: project.id,
        nodeId: node.id,
        wx: pos.x,
        wy: pos.y + size.h / 2 + belowH / 2,
        node,
        state: activityState,
        context: activityContextForProject(project),
      });
    }
  }
  return items;
}

function collectRunningActivityItems() {
  const scope = runningActivityProjectIds();
  const items = collectAllRunningActivityItems();
  if (!scope) return items;
  return items.filter((item) => scope.has(item.projectId));
}

function labCameraLayout() {
  return labWorldLayoutFull || labWorldLayout;
}

function refreshAllMethodActivityAuthors() {
  const ids = new Set(runningAuthorsByProject.keys());
  for (const item of collectAllRunningActivityItems()) {
    if (item.projectId) ids.add(item.projectId);
  }
  for (const pid of ids) refreshMethodActivityAuthors(pid);
  syncLabActivityOverlay();
}

async function preloadAllRunningAuthors() {
  if (!state.lab?.projectsById) return;
  const ids = new Set();
  for (const item of collectAllRunningActivityItems()) {
    if (item.projectId) ids.add(item.projectId);
  }
  await Promise.all([...ids].map((id) => ensureRunningAuthors(id)));
  refreshAllMethodActivityAuthors();
}

function syncLabActivityOverlay() {
  const viewport = document.getElementById("mindmap-viewport");
  if (!viewport || !labCamera || !state.lab?.projectsById) return;
  const items = collectRunningActivityItems();
  const showOverlay = shouldUseActivityOverlay(labCamera) && items.length > 0;
  const overlayRebuilt = syncMethodActivityOverlay(viewport, labCamera, items, showOverlay);
  syncMethodActivityZoomMode(viewport, labCamera, showOverlay);
  if (showOverlay && overlayRebuilt && !isHubMode()) {
    const layer = document.getElementById("method-activity-overlay");
    for (const item of items) {
      const project = state.lab.projectsById[item.projectId];
      if (!project || !layer) continue;
      const board = getBoardForNode(project, item.node);
      bindMethodLiveInspect(layer, item.node, board, project);
    }
  }
}

function refreshMethodActivityAuthors(projectId) {
  if (!projectId) return;
  const authors = runningAuthorsByProject.get(projectId);
  if (!authors) return;
  const project = state.lab?.projectsById?.[projectId] || state.project;
  if (!project || project.id !== projectId) return;
  const context = activityContextForProject(project);
  document
    .querySelectorAll(`.node-wrap[data-project-id="${projectId}"] .node-kanban-below`)
    .forEach((below) => {
      const wrap = below.closest(".node-wrap");
      const nodeId = wrap?.dataset?.nodeId;
      const node = project.nodes?.find((n) => n.id === nodeId);
      if (!node) return;
      const board = getBoardForNode(project, node);
      syncMethodActivity(below, node, board, context);
    });
  applyRunningCardAuthorTitles(document.getElementById("kanban-board"), projectId);
  applyRunningCardAuthorTitles(document.getElementById("kanban-dag-view"), projectId);
  syncLabActivityOverlay();
}

function refreshMapKanbansForProject(_projectId, _nodeId = null) {
  /* inline map kanban removed — modal only */
}

function appendKanbanBelow(wrap, node, project = state.project) {
  const s = kanbanStatsForNode(node, project);
  if (!s) return;
  const board = getBoardForNode(project, node);
  const activityState = getMethodActivityState(board);
  const context = activityContextForProject(project);
  const below = document.createElement("div");
  below.className = "node-kanban-below";
  below.title = "exp_tot / in proc / done";
  below.innerHTML = `
    <div class="node-kanban-compact">
      <span class="node-kanban-label">канбан</span>
      <span class="node-kanban-stats">tot ${s.tot} · proc ${s.inProc} · done ${s.done}</span>
      ${kanbanProgressBarHtml(s)}
    </div>`;
  const openKanbanFromBelow = (e) => {
    e.stopPropagation();
    if (e.target.closest(".method-activity-inspect")) return;
    if (state.project?.id !== project.id) state.project = project;
    openKanbanModal(node);
  };
  below.querySelector(".node-kanban-compact")?.addEventListener("click", openKanbanFromBelow);
  below.addEventListener("click", (e) => {
    if (e.target.closest(".method-activity-inspect")) return;
    if (e.target.closest(".node-kanban-compact")) return;
    openKanbanFromBelow(e);
  });
  wrap.appendChild(below);
  syncMethodActivity(below, node, board, context);
  if (!isHubMode()) {
    bindMethodLiveInspect(below, node, board, project);
  }
  if (project?.id && activityState.running.length) {
    void ensureRunningAuthors(project.id).then(() => refreshMethodActivityAuthors(project.id));
  }
}

function refreshKanbanActivityForProject(projectId, { nodeId = null } = {}) {
  const project =
    state.lab?.projectsById?.[projectId] ||
    (state.project?.id === projectId ? state.project : null);
  if (!project) return;

  if (state.project?.id === projectId) {
    state.project = project;
  }
  syncLabProject(project);

  let needsLayout = false;
  const context = activityContextForProject(project);

  for (const node of project.nodes || []) {
    if (nodeId && node.id !== nodeId) continue;
    if (node.node_type !== "method") continue;
    const board = getBoardForNode(project, node);
    if (!board) continue;

    const below = document.querySelector(
      `.node-wrap[data-project-id="${projectId}"][data-node-id="${node.id}"] .node-kanban-below`
    );
    const s = kanbanStatsForNode(node, project);
    if (!below) {
      if (s?.inProc > 0) needsLayout = true;
      continue;
    }

    const oldInProc = Number(
      below.querySelector(".node-kanban-stats")?.textContent?.match(/proc\s+(\d+)/)?.[1]
    );
    if (s && !Number.isNaN(oldInProc) && oldInProc !== s.inProc) {
      needsLayout = true;
      break;
    }
  }

  if (needsLayout) {
    scheduleMindmapRender();
    if (
      state.kanbanNodeId &&
      state.project?.id === projectId &&
      (!nodeId || state.kanbanNodeId === nodeId)
    ) {
      const openNode = project.nodes.find((n) => n.id === state.kanbanNodeId);
      if (openNode?.board_id) {
        renderKanbanBoard(project.boards[openNode.board_id]);
      }
    }
    return;
  }

  for (const node of project.nodes || []) {
    if (nodeId && node.id !== nodeId) continue;
    if (node.node_type !== "method") continue;
    const board = getBoardForNode(project, node);
    if (!board) continue;

    const below = document.querySelector(
      `.node-wrap[data-project-id="${projectId}"][data-node-id="${node.id}"] .node-kanban-below`
    );
    if (!below) continue;

    const s = kanbanStatsForNode(node, project);
    if (s) {
      const statsEl = below.querySelector(".node-kanban-stats");
      if (statsEl) {
        statsEl.textContent = `tot ${s.tot} · proc ${s.inProc} · done ${s.done}`;
      }
      syncKanbanProgressBar(below.querySelector(".node-kanban-progress"), s);
    }
    syncMethodActivity(below, node, board, context);
    bindMethodLiveInspect(below, node, board, project);
  }

  runningAuthorsByProject.delete(projectId);
  void ensureRunningAuthors(projectId, { force: true }).then(() => {
    refreshMethodActivityAuthors(projectId);
    syncLabActivityOverlay();
  });
  syncLabActivityOverlay();

  if (
    state.kanbanNodeId &&
    state.project?.id === projectId &&
    (!nodeId || state.kanbanNodeId === nodeId)
  ) {
    const openNode = project.nodes.find((n) => n.id === state.kanbanNodeId);
    if (openNode?.board_id) {
      renderKanbanBoard(project.boards[openNode.board_id]);
    }
  }
}

function refreshKanbanBelowForNode(nodeId) {
  const pid = state.project?.id;
  if (!pid) return;
  refreshKanbanActivityForProject(pid, { nodeId });
}

function displayTitle(node) {
  let t = (node.title || "").trim();
  const prefixes = {
    cause: /^причина:\s*/i,
    cause_evidence: /^доказательство:\s*/i,
    remediation: /^устранение:\s*/i,
  };
  const re = prefixes[node.node_type];
  if (re) t = t.replace(re, "");
  return t || node.title || "";
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("save-status");
  if (!el) return;
  el.textContent = msg;
}

function setSyncError(msg) {
  const btn = document.getElementById("btn-sync");
  if (!btn) return;
  btn.classList.toggle("has-error", Boolean(msg));
  if (msg) btn.title = msg;
}

function updatePaperReviewLink() {
  const link = document.getElementById("btn-related-work");
  if (!link) return;
  const pid = primaryMemberProjectId();
  link.href = pid
    ? `literature.html?project=${encodeURIComponent(pid)}`
    : "literature.html";
}

function setLiteratureStatus(msg, isError = false) {
  const el = document.getElementById("literature-search-status");
  if (!el) return;
  el.textContent = msg;
  el.className =
    "literature-search-status" + (isError ? " error" : msg ? " ok" : "");
}

function updateReviewSetButton() {
  const btn = document.getElementById("literature-create-review-set");
  if (!btn) return;
  btn.disabled = !state.literatureResults?.length;
}

function selectedLiteratureLimit() {
  const input = document.getElementById("literature-limit");
  const raw = Number(input?.value || 10);
  const limit = Math.max(1, Math.min(50, Number.isFinite(raw) ? Math.round(raw) : 10));
  if (input) input.value = String(limit);
  return limit;
}

function renderLiteratureResults(results = [], query = "") {
  const root = document.getElementById("literature-results");
  if (!root) return;

  if (!results.length) {
    const text = query
      ? `No strong matches found for "${query}". Try more specific keywords from the topic or method name.`
      : "Enter a research question and press the button to rank relevant papers automatically.";
    root.innerHTML = `<p class="literature-empty">${escapeHtml(text)}</p>`;
    updateReviewSetButton();
    return;
  }

  root.innerHTML = results
    .map(
      (paper, index) => `
        <article class="literature-result-card">
          <div class="literature-result-rank">${index + 1}</div>
          <div class="literature-result-body">
            <a class="literature-result-title" href="${escapeHtml(paper.arxiv_url)}" target="_blank" rel="noreferrer">${escapeHtml(paper.title)}</a>
            <p class="literature-result-meta">
              <span>score ${paper.score.toFixed(3)}</span>
              ${
                paper.matched_terms?.length
                  ? `<span>matched: ${escapeHtml(paper.matched_terms.join(", "))}</span>`
                  : "<span>matched by title similarity</span>"
              }
            </p>
            ${
              paper.abstract_preview
                ? `<p class="literature-result-abstract">${escapeHtml(paper.abstract_preview)}</p>`
                : ""
            }
          </div>
        </article>`
    )
    .join("");
  updateReviewSetButton();
}

async function onLiteratureSearchSubmit(e) {
  e.preventDefault();
  const queryEl = document.getElementById("literature-query");
  const button = document.getElementById("literature-search-button");
  const query = queryEl?.value?.trim() || "";
  const limit = selectedLiteratureLimit();
  if (!query) {
    setLiteratureStatus("Enter a research question first.", true);
    renderLiteratureResults([], "");
    return;
  }

  button?.setAttribute("disabled", "disabled");
  setLiteratureStatus("Searching the local paper library…");
  try {
    const data = await KoiApi.searchLibrary(query, limit);
    state.literatureResults = data.results || [];
    renderLiteratureResults(state.literatureResults, query);
    setLiteratureStatus(
      `${data.count} paper${data.count === 1 ? "" : "s"} ranked using title and abstract relevance.`
    );
  } catch (err) {
    renderLiteratureResults([], query);
    setLiteratureStatus(err.message, true);
  } finally {
    button?.removeAttribute("disabled");
  }
}

async function createReviewSetFromResults() {
  const queryEl = document.getElementById("literature-query");
  const btn = document.getElementById("literature-create-review-set");
  const query = queryEl?.value?.trim() || "";
  const limit = selectedLiteratureLimit();
  if (!query) {
    setLiteratureStatus("Enter a research question first.", true);
    return;
  }
  if (!state.literatureResults?.length) {
    setLiteratureStatus("Run the literature search before creating a review set.", true);
    return;
  }

  btn?.setAttribute("disabled", "disabled");
  setLiteratureStatus("Creating a ResearchOS review set…");
  try {
    const data = await KoiApi.createReviewSet(query, limit);
    await loadProjectList(data.project?.id);
    await switchProject(data.project?.id);
    setLiteratureStatus(
      `Review set created with ${data.count} paper${data.count === 1 ? "" : "s"} and opened as a new project.`
    );
  } catch (err) {
    setLiteratureStatus(err.message, true);
  } finally {
    updateReviewSetButton();
  }
}

/** Эксперименты живут в канбане, на карте не показываем. */
function isVisualNode(node) {
  return node.node_type !== "experiment";
}

function buildTree(nodes, parentId = null) {
  return nodes
    .filter((n) => n.parent_id === parentId && isVisualNode(n))
    .sort(
      (a, b) =>
        (TYPE_ORDER[a.node_type] ?? 9) - (TYPE_ORDER[b.node_type] ?? 9)
    )
    .map((n) => ({ ...n, children: buildTree(nodes, n.id) }));
}

function kanbanBelowExtra(node) {
  if (!nodeHasKanban(node)) return 0;
  const board = getBoardForNode(state.project, node);
  const inProc = board?.cards?.filter((c) => c.column_id === "running").length ?? 0;
  return inProc > 0 ? KANBAN_BELOW_H + METHOD_ACTIVITY_H : KANBAN_BELOW_H;
}

function halfH(node) {
  const s = nodeSize(node);
  return s.h / 2 + kanbanBelowExtra(node) / 2 + (nodeHasKanban(node) ? 8 : 0);
}

/** Y center for each tree level (top → bottom). */
function buildDepthY(root) {
  const maxH = {};
  function walk(n, d) {
    maxH[d] = Math.max(maxH[d] || 0, halfH(n));
    if (shouldShowAddSlot(n)) {
      maxH[d + 1] = Math.max(maxH[d + 1] || 0, addNodeSize().h / 2 + 4);
    }
    (n.children || []).forEach((c) => walk(c, d + 1));
  }
  walk(root, 0);
  const maxDepth = Math.max(0, ...Object.keys(maxH).map(Number));
  const y = {};
  let cur = LAYOUT.topPad + (maxH[0] || 0);
  y[0] = cur;
  for (let d = 1; d <= maxDepth; d++) {
    cur += maxH[d - 1] + LAYOUT.vGap + maxH[d];
    y[d] = cur;
  }
  return y;
}

function subtreeWidth(node) {
  const kids = node.children || [];
  const addW = shouldShowAddSlot(node) ? addNodeSize().w : 0;
  if (!kids.length) return Math.max(nodeSize(node).w, addW);
  let total = 0;
  kids.forEach((child, i) => {
    if (i > 0) total += LAYOUT.hGap;
    total += subtreeWidth(child);
  });
  if (shouldShowAddSlot(node)) {
    total += LAYOUT.hGap + addW;
  }
  return Math.max(nodeSize(node).w, total);
}

/**
 * Top-down tree: problem on top, children spread horizontally below.
 */
function layoutTopDown(node, depth, xLeft, yByDepth, positions) {
  const kids = node.children || [];
  const showAdd = shouldShowAddSlot(node);
  const childDepth = depth + 1;
  const childY = yByDepth[childDepth];

  if (!kids.length && !showAdd) {
    const w = nodeSize(node).w;
    positions[node.id] = { x: xLeft + w / 2, y: yByDepth[depth], node };
    return xLeft + w;
  }

  let cursor = xLeft;
  const centers = [];

  kids.forEach((child, i) => {
    if (i > 0) cursor += LAYOUT.hGap;
    cursor = layoutTopDown(child, childDepth, cursor, yByDepth, positions);
    centers.push(positions[child.id].x);
  });

  if (showAdd) {
    if (kids.length) cursor += LAYOUT.hGap;
    const s = addNodeSize();
    const aid = addSlotId(node.id);
    positions[aid] = {
      x: cursor + s.w / 2,
      y: childY,
      isAdd: true,
      parentNode: node,
    };
    centers.push(positions[aid].x);
    cursor += s.w;
  }

  positions[node.id] = {
    x:
      centers.length > 0
        ? (centers[0] + centers[centers.length - 1]) / 2
        : xLeft + nodeSize(node).w / 2,
    y: yByDepth[depth],
    node,
  };
  return cursor;
}

function collectDescendants(nodeId, nodes) {
  const ids = [nodeId];
  const children = nodes.filter((n) => n.parent_id === nodeId);
  children.forEach((c) => ids.push(...collectDescendants(c.id, nodes)));
  return ids;
}

function shiftSubtree(nodeId, dx, dy, positions) {
  for (const id of collectDescendants(nodeId, state.project.nodes)) {
    if (positions[id]) {
      positions[id].x += dx;
      positions[id].y += dy;
    }
  }
}

/** Children always below parent with a vertical gap. */
function enforceVerticalOrder(positions) {
  for (const n of state.project.nodes) {
    if (!n.parent_id || !isVisualNode(n)) continue;
    const parent = state.project.nodes.find((p) => p.id === n.parent_id);
    const pPos = positions[n.parent_id];
    const cPos = positions[n.id];
    if (!parent || !pPos || !cPos) continue;
    const pb = bboxFromPos(pPos, parent);
    const cb = bboxFromPos(cPos, n);
    const needTop = pb.bottom + LAYOUT.vGap;
    if (cb.top < needTop - 2) {
      shiftSubtree(n.id, 0, needTop - cb.top, positions);
    }
  }
  for (const [id, pos] of Object.entries(positions)) {
    if (!pos.isAdd || !pos.parentNode) continue;
    const pPos = positions[pos.parentNode.id];
    if (!pPos) continue;
    const pb = bboxFromPos(pPos, pos.parentNode);
    const cb = bboxFromPos(pos, null);
    const needTop = pb.bottom + LAYOUT.vGap;
    if (cb.top < needTop - 2) {
      pos.y += needTop - cb.top;
    }
  }
}

function bboxFromPos(pos, node) {
  const s = pos.isAdd ? addNodeSize() : nodeSize(node);
  const below = node && !pos.isAdd ? kanbanBelowExtra(node) : 0;
  return {
    left: pos.x - s.w / 2,
    right: pos.x + s.w / 2,
    top: pos.y - s.h / 2,
    bottom: pos.y + s.h / 2 + below,
    w: s.w,
    h: s.h + below,
  };
}

function nodeBBox(pos, node) {
  return bboxFromPos(pos, node);
}

function bboxesOverlap(a, b, margin = 14) {
  return !(
    a.right + margin < b.left ||
    a.left - margin > b.right ||
    a.bottom + margin < b.top ||
    a.top - margin > b.bottom
  );
}

function isParentChild(idA, idB) {
  if (isAddSlot(idA) || isAddSlot(idB)) return true;
  const a = state.project.nodes.find((n) => n.id === idA);
  const b = state.project.nodes.find((n) => n.id === idB);
  if (!a || !b) return false;
  return a.parent_id === idB || b.parent_id === idA;
}

/** Resolve horizontal overlaps between siblings/cousins. */
function resolveOverlaps(positions) {
  const ids = Object.keys(positions);
  for (let iter = 0; iter < 16; iter++) {
    let moved = false;
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const idA = ids[i];
        const idB = ids[j];
        if (isParentChild(idA, idB)) continue;
        const pa = positions[idA];
        const pb = positions[idB];
        const ba = bboxFromPos(pa, pa.node);
        const bb = bboxFromPos(pb, pb.node);
        if (!bboxesOverlap(ba, bb, 10)) continue;

        const overlapX =
          Math.min(ba.right, bb.right) - Math.max(ba.left, bb.left);
        const push = overlapX / 2 + 12;
        pa.x -= push;
        pb.x += push;
        moved = true;
      }
    }
    if (!moved) break;
  }
}

/** Fit tree into viewport; keep top anchor. */
function scaleTreeToFit(positions, width, height) {
  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  for (const p of Object.values(positions)) {
    const b = bboxFromPos(p, p.node);
    minX = Math.min(minX, b.left);
    maxX = Math.max(maxX, b.right);
    minY = Math.min(minY, b.top);
    maxY = Math.max(maxY, b.bottom);
  }
  const treeW = maxX - minX;
  const treeH = maxY - minY;
  if (treeW <= 0 || treeH <= 0) return;

  const availW = width - LAYOUT.pad * 2;
  const availH = height - LAYOUT.pad * 2;
  const scale = Math.min(availW / treeW, availH / treeH, 1);
  const offsetX = (width - treeW * scale) / 2 - minX * scale;
  const offsetY = LAYOUT.topPad - minY * scale;

  for (const p of Object.values(positions)) {
    p.x = p.x * scale + offsetX;
    p.y = p.y * scale + offsetY;
  }
}

function boundaryPoint(fromX, fromY, toX, toY, size) {
  const dx = toX - fromX;
  const dy = toY - fromY;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const isOval = size.shape === "oval" || (size.round === "50%" && size.w !== size.h);
  if (size.round === "50%" && !isOval) {
    const rad = size.w / 2;
    return { x: fromX + ux * rad, y: fromY + uy * rad };
  }
  if (isOval) {
    const a = size.w / 2 - 6;
    const b = size.h / 2 - 6;
    const t = 1 / Math.sqrt((ux / a) ** 2 + (uy / b) ** 2);
    return { x: fromX + ux * t, y: fromY + uy * t };
  }
  const hw = size.w / 2 - 6;
  const hh = size.h / 2 - 6;
  const scale = Math.min(
    Math.abs(ux) > 1e-6 ? hw / Math.abs(ux) : Infinity,
    Math.abs(uy) > 1e-6 ? hh / Math.abs(uy) : Infinity
  );
  return { x: fromX + ux * scale, y: fromY + uy * scale };
}

function renderEdges(svg, positions, width, height) {
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.innerHTML = `
    <defs>
      <linearGradient id="edge-grad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#ff6bcb"/>
        <stop offset="50%" stop-color="#7b5cff"/>
        <stop offset="100%" stop-color="#3de8ff"/>
      </linearGradient>
      <filter id="edge-glow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#3de8ff"/>
      </marker>
    </defs>`;

  const drawEdge = (from, to, fs, ts, dashed = false) => {
    if (!from || !to) return;
    const start = boundaryPoint(from.x, from.y, to.x, to.y, fs);
    const end = boundaryPoint(to.x, to.y, from.x, from.y, ts);
    const x1 = start.x;
    const y1 = start.y;
    const x2 = end.x;
    const y2 = end.y;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const curve = Math.min(LAYOUT.edgeCurve, dist * 0.08);
    const mx = (x1 + x2) / 2 + (Math.abs(ux) > 0.5 ? curve * Math.sign(dx || 1) : 0);
    const my = (y1 + y2) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`);
    path.setAttribute("class", dashed ? "edge edge-add" : "edge");
    path.setAttribute("stroke", "url(#edge-grad)");
    path.setAttribute("filter", "url(#edge-glow)");
    if (!dashed) path.setAttribute("marker-end", "url(#arrow)");
    svg.appendChild(path);
  };

  state.project.nodes.forEach((n) => {
    if (!n.parent_id || !isVisualNode(n)) return;
    const parent = state.project.nodes.find((x) => x.id === n.parent_id);
    if (!parent || !isVisualNode(parent)) return;
    drawEdge(
      positions[n.parent_id],
      positions[n.id],
      nodeSize(parent),
      nodeSize(n)
    );
  });

  for (const [id, pos] of Object.entries(positions)) {
    if (!pos.isAdd || !pos.parentNode) continue;
    drawEdge(
      positions[pos.parentNode.id],
      pos,
      nodeSize(pos.parentNode),
      addNodeSize(),
      true
    );
  }
}

const LAB_LAYOUT = {
  programGap: 56,
  programHeader: 40,
  projectGap: 48,
  framePad: 20,
};

function withProject(project, fn) {
  const savedProject = state.project;
  const savedSizes = state.nodeSizes;
  state.project = project;
  try {
    return fn();
  } finally {
    state.project = savedProject;
    state.nodeSizes = savedSizes;
  }
}

function shiftPositions(positions, dx, dy) {
  const out = {};
  for (const [id, pos] of Object.entries(positions)) {
    out[id] = { ...pos, x: pos.x + dx, y: pos.y + dy };
  }
  return out;
}

function positionsBBox(positions) {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const p of Object.values(positions)) {
    const b = bboxFromPos(p, p.node);
    minX = Math.min(minX, b.left);
    maxX = Math.max(maxX, b.right);
    minY = Math.min(minY, b.top);
    maxY = Math.max(maxY, b.bottom);
  }
  if (!Number.isFinite(minX)) {
    return { x: 0, y: 0, width: 1, height: 1 };
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function computeProjectLayout(project) {
  return withProject(project, () => {
    buildSizeCache();
    const trees = buildTree(project.nodes);
    const root = trees[0];
    if (!root) return null;
    const yByDepth = buildDepthY(root);
    const positions = {};
    layoutTopDown(root, 0, 0, yByDepth, positions);
    enforceVerticalOrder(positions);
    resolveOverlaps(positions);
    enforceVerticalOrder(positions);
    resolveOverlaps(positions);
    return {
      positions,
      bbox: positionsBBox(positions),
      nodeSizes: { ...state.nodeSizes },
    };
  });
}

function layoutProgramRow(group, projectsById, startY, startX, hiddenMemberIds = new Set()) {
  const placements = [];
  const projectRegions = {};
  let cursorX = startX;
  let rowMaxH = 0;

  for (const item of programLayoutItems(group, hiddenMemberIds)) {
    const project = projectsById[item.id];
    if (!project) continue;
    const layout = computeProjectLayout(project);
    if (!layout) continue;

    const frameX = cursorX;
    const frameY = startY + LAB_LAYOUT.programHeader;
    const offsetX = frameX + LAB_LAYOUT.framePad - layout.bbox.x;
    const offsetY = frameY + LAB_LAYOUT.framePad - layout.bbox.y;
    const shifted = shiftPositions(layout.positions, offsetX, offsetY);
    const innerW = layout.bbox.width + LAB_LAYOUT.framePad * 2;
    const innerH = layout.bbox.height + LAB_LAYOUT.framePad * 2;

    projectRegions[item.id] = {
      projectId: item.id,
      programId: group.id || "",
      title: item.title,
      x: frameX,
      y: frameY,
      width: innerW,
      height: innerH,
    };

    placements.push({
      project,
      positions: shifted,
      nodeSizes: layout.nodeSizes,
      region: projectRegions[item.id],
    });

    cursorX += innerW + LAB_LAYOUT.projectGap;
    rowMaxH = Math.max(rowMaxH, innerH);
  }

  const rowWidth = Math.max(cursorX - startX - LAB_LAYOUT.projectGap, 240);
  return {
    placements,
    projectRegions,
    program: {
      id: group.id || "",
      title: group.title,
      description: group.description || "",
      x: startX,
      y: startY,
      width: rowWidth,
      height: LAB_LAYOUT.programHeader + rowMaxH,
    },
    nextY: startY + LAB_LAYOUT.programHeader + rowMaxH + LAB_LAYOUT.programGap,
    rowMaxX: cursorX,
  };
}

function getViewMode() {
  return state.view?.mode || "chief";
}

function findProgramIdForProject(grouped, projectId) {
  if (!grouped || !projectId) return null;
  const compositeKey = isCompositeVirtualId(projectId)
    ? projectId.slice("composite:".length)
    : null;
  for (const g of grouped.groups || []) {
    if (g.projects?.some((p) => p.id === projectId)) return g.id;
    if (compositeKey && g.composites?.some((c) => c.id === compositeKey)) return g.id;
  }
  if (grouped.ungrouped?.some((p) => p.id === projectId)) return "";
  return grouped.groups?.[0]?.id ?? "";
}

function findProgramRegion(layout, programId) {
  const program = layout?.programs?.find((p) => p.id === (programId ?? ""));
  if (!program) return null;
  return {
    x: program.x,
    y: program.y,
    width: program.width,
    height: program.height,
  };
}

function filterGroupedForView(grouped) {
  if (!grouped) return grouped;
  const mode = getViewMode();
  const hiddenMemberIds = hiddenCompositeMemberIds(grouped);

  if (mode === "chief") {
    return {
      ...grouped,
      groups: (grouped.groups || []).map((g) => ({
        ...g,
        projects: visibleProjectsForGroup(g, hiddenMemberIds),
      })),
    };
  }

  if (mode === "teamlead") {
    const programId = findProgramIdForProject(grouped, state.project?.id) ?? "";
    const groups = (grouped.groups || [])
      .filter((g) => g.id === programId)
      .map((g) => ({
        ...g,
        projects: visibleProjectsForGroup(g, hiddenMemberIds),
      }));
    const ungrouped = programId === "" ? [...(grouped.ungrouped || [])] : [];
    return { ...grouped, groups, ungrouped };
  }

  const projectId = state.project?.id;
  if (!projectId) {
    return { ...grouped, groups: [], ungrouped: [] };
  }
  const groups = (grouped.groups || [])
    .map((g) => {
      const composites = (g.composites || []).filter(
        (c) => compositeVirtualId(c.id) === projectId
      );
      const projects = (g.projects || []).filter((p) => p.id === projectId);
      if (!composites.length && !projects.length) return null;
      return {
        ...g,
        composites,
        projects: projects.filter((p) => !hiddenMemberIds.has(p.id)),
      };
    })
    .filter(Boolean);
  const ungrouped = (grouped.ungrouped || []).filter((p) => p.id === projectId);
  return { ...grouped, groups, ungrouped };
}

function getFilteredGrouped() {
  return filterGroupedForView(state.lab?.grouped);
}

function projectIdsInGrouped(grouped) {
  const ids = new Set();
  if (!grouped) return ids;
  const hidden = hiddenCompositeMemberIds(grouped);
  for (const g of grouped.groups || []) {
    for (const c of g.composites || []) ids.add(compositeVirtualId(c.id));
    for (const p of g.projects || []) {
      if (!hidden.has(p.id)) ids.add(p.id);
    }
  }
  for (const p of grouped.ungrouped || []) ids.add(p.id);
  return ids;
}

function layoutLaboratory(grouped, projectsById) {
  const programs = [];
  const placements = [];
  const projectRegions = {};
  let y = LAYOUT.topPad;
  let maxX = LAYOUT.pad;
  const hiddenMemberIds = hiddenCompositeMemberIds(grouped);

  const groups = [...(grouped.groups || [])];
  if (grouped.ungrouped?.length) {
    groups.push({
      id: "",
      title: grouped.groups?.length ? "Без программы" : "Проекты",
      description: "",
      projects: grouped.ungrouped,
      composites: [],
    });
  }

  for (const group of groups) {
    const row = layoutProgramRow(group, projectsById, y, LAYOUT.pad, hiddenMemberIds);
    programs.push(row.program);
    placements.push(...row.placements);
    Object.assign(projectRegions, row.projectRegions);
    y = row.nextY;
    maxX = Math.max(maxX, row.rowMaxX);
  }

  const height = Math.max(y, LAYOUT.topPad + 200);
  const width = Math.max(maxX + LAYOUT.pad, 640);
  return {
    programs,
    placements,
    projectRegions,
    methodRegions: computeMethodRegions(placements),
    bbox: { x: 0, y: 0, width, height },
  };
}

function syncLabProject(project) {
  if (!state.lab?.projectsById || !project?.id) return;
  state.lab.projectsById[project.id] = project;
  syncRunningSeedProvider();
  rebuildLabWorldLayoutFull();
}

function ensureLabCamera() {
  if (labCamera) return;
  const viewport = document.getElementById("mindmap-viewport");
  const canvas = document.getElementById("mindmap-canvas");
  if (!viewport || !canvas) return;

  labCamera = new MindmapCamera(viewport, canvas, {
    onChange: () => {
      syncLabActivityOverlay();
    },
  });
  bindMethodActivityZoomPreview(viewport, () => labCamera);
  syncLabActivityOverlay();

  document.getElementById("btn-zoom-in")?.addEventListener("click", () => labCamera.zoomBy(1.2));
  document.getElementById("btn-zoom-out")?.addEventListener("click", () => labCamera.zoomBy(1 / 1.2));
  document.getElementById("btn-zoom-fit-lab")?.addEventListener("click", () => labCamera.fitWorld());
  document.getElementById("btn-zoom-fit-project")?.addEventListener("click", () => {
    const id = state.project?.id;
    const regions = labCameraLayout()?.projectRegions;
    if (id && regions?.[id]) {
      labCamera.flyToRegion(regions[id]);
    }
  });
}

async function loadLab() {
  const grouped = await KoiApi.listProjectsGrouped();
  const hiddenMemberIds = hiddenCompositeMemberIds(grouped);
  const ids = new Set();
  for (const g of grouped.groups || []) {
    for (const p of g.projects || []) ids.add(p.id);
  }
  for (const p of grouped.ungrouped || []) ids.add(p.id);

  const compositeSlugs = new Set();
  for (const g of grouped.groups || []) {
    for (const c of g.composites || []) compositeSlugs.add(c.id);
  }

  const [projects, composites] = await Promise.all([
    Promise.all([...ids].map((id) => KoiApi.getProject(id))),
    Promise.all([...compositeSlugs].map((id) => KoiApi.getComposite(id))),
  ]);

  const projectsById = Object.fromEntries(projects.map((p) => [p.id, p]));
  for (const composite of composites) {
    projectsById[composite.id] = composite;
  }

  state.lab = {
    grouped,
    projectsById,
    hiddenMemberIds,
  };
  runningAuthorsByProject.clear();
  syncRunningSeedProvider();
  rebuildLabWorldLayoutFull();
  ensureLabCamera();
  void preloadAllRunningAuthors();
}

function mountMapNode(pos, layer, project, node, nodeSizes) {
  const savedSizes = state.nodeSizes;
  state.nodeSizes = nodeSizes;
  const size = nodeSizes[node.id] || computeNodeSize(node);
  const hasKanban = node.node_type === "method" && !!getBoardForNode(project, node);
  const el = document.createElement("button");
  el.type = "button";
  const verdictBadge = node.node_type === "cause" ? VERDICT_BADGES[node.verdict] : null;
  el.className = `map-node ${node.node_type}${hasKanban ? " has-kanban clickable" : ""}${verdictBadge ? ` verdict-${node.verdict}` : ""}`;
  el.innerHTML = `
    <span class="node-label">${TYPE_LABELS[node.node_type]}</span>
    <span class="node-title">${escapeHtml(displayTitle(node))}</span>
    ${verdictBadge ? `<span class="node-verdict node-verdict--${node.verdict}" title="${verdictBadge.label}">${verdictBadge.mark}</span>` : ""}`;

  const activateProject = () => {
    if (state.project?.id !== project.id) {
      state.project = project;
      setActiveProjectInList(project.id);
    }
  };

  el.addEventListener("click", (e) => {
    e.stopPropagation();
    activateProject();
    if (hasKanban) openKanbanModal(node);
    else openNodeModal(node);
  });
  el.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    activateProject();
    if (hasKanban) flyToMethodNode(project, node);
    else openNodeModal(node);
  });
  el.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    activateProject();
    if (hasKanban) openKanbanModal(node);
    else openNodeModal(node);
  });

  const wrap = document.createElement("div");
  wrap.className = "node-wrap" + (hasKanban ? " has-kanban-wrap" : "");
  wrap.dataset.nodeId = node.id;
  wrap.dataset.projectId = project.id;
  wrap.style.left = `${pos.x}px`;
  if (hasKanban) {
    wrap.style.top = `${pos.y - size.h / 2}px`;
    wrap.style.transform = "translateX(-50%)";
  } else {
    wrap.style.top = `${pos.y}px`;
    wrap.style.transform = "translate(-50%, -50%)";
  }
  el.style.width = `${size.w}px`;
  el.style.height = `${size.h}px`;
  el.style.borderRadius = size.round;
  wrap.appendChild(el);
  layer.appendChild(wrap);

  if (node.node_type === "method" && (node.research_questions?.length ?? 0) > 0) {
    const counts = researchQuestionCounts(node);
    const mapEl = wrap.firstElementChild;
    const core = document.createElement("div");
    core.className = "node-core has-method-questions";
    wrap.classList.add("has-research-questions");
    wrap.insertBefore(core, mapEl);
    core.appendChild(mapEl);
    const qBtn = document.createElement("button");
    qBtn.type = "button";
    qBtn.className = "method-questions-trigger";
    qBtn.setAttribute(
      "aria-label",
      `Выводы: ${counts.definite} с чётким ответом, ${counts.tentative} предварительных`
    );
    qBtn.title = "Выводы по экспериментам";
    qBtn.innerHTML = `<span class="rq-badge-q">?</span><span class="rq-badge-def">${counts.definite}</span><span class="rq-badge-sep">|</span><span class="rq-badge-tent">${counts.tentative}</span>`;
    qBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      activateProject();
      openMethodQuestionsModal(node);
    });
    qBtn.addEventListener("mousedown", (e) => e.stopPropagation());
    core.appendChild(qBtn);
    wireResearchQuestionBadge(wrap, qBtn);
  }

  mountNodeTypeHelp(wrap, node.node_type);

  if (hasKanban) {
    appendKanbanBelow(wrap, node, project);
  }
  wireNodeWorkersHover(wrap, project, node);
  state.nodeSizes = savedSizes;
  return wrap;
}

function renderLabEdges(svg, placements, worldW, worldH) {
  svg.setAttribute("width", String(worldW));
  svg.setAttribute("height", String(worldH));
  svg.setAttribute("viewBox", `0 0 ${worldW} ${worldH}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.style.width = `${worldW}px`;
  svg.style.height = `${worldH}px`;
  svg.innerHTML = `
    <defs>
      <linearGradient id="edge-grad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${worldW}" y2="0">
        <stop offset="0%" stop-color="#ff6bcb"/>
        <stop offset="50%" stop-color="#7b5cff"/>
        <stop offset="100%" stop-color="#3de8ff"/>
      </linearGradient>
      <filter id="edge-glow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#3de8ff"/>
      </marker>
    </defs>`;

  const drawEdge = (from, to, fs, ts, dashed = false) => {
    if (!from || !to) return;
    const start = boundaryPoint(from.x, from.y, to.x, to.y, fs);
    const end = boundaryPoint(to.x, to.y, from.x, from.y, ts);
    const x1 = start.x;
    const y1 = start.y;
    const x2 = end.x;
    const y2 = end.y;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const curve = Math.min(LAYOUT.edgeCurve, dist * 0.08);
    const mx = (x1 + x2) / 2 + (Math.abs(ux) > 0.5 ? curve * Math.sign(dx || 1) : 0);
    const my = (y1 + y2) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`);
    path.setAttribute("class", dashed ? "edge edge-add" : "edge");
    path.setAttribute("stroke", "url(#edge-grad)");
    path.setAttribute("filter", "url(#edge-glow)");
    if (!dashed) path.setAttribute("marker-end", "url(#arrow)");
    svg.appendChild(path);
  };

  for (const placement of placements) {
    const savedProject = state.project;
    const savedSizes = state.nodeSizes;
    state.project = placement.project;
    state.nodeSizes = placement.nodeSizes || {};
    try {
      const { positions } = placement;
      placement.project.nodes.forEach((n) => {
        if (!n.parent_id || !isVisualNode(n)) return;
        const parent = placement.project.nodes.find((x) => x.id === n.parent_id);
        if (!parent || !isVisualNode(parent)) return;
        drawEdge(
          positions[n.parent_id],
          positions[n.id],
          nodeSize(parent),
          nodeSize(n)
        );
      });
      for (const [id, pos] of Object.entries(positions)) {
        if (!pos.isAdd || !pos.parentNode) continue;
        drawEdge(
          positions[pos.parentNode.id],
          pos,
          nodeSize(pos.parentNode),
          addNodeSize(),
          true
        );
      }
    } finally {
      state.project = savedProject;
      state.nodeSizes = savedSizes;
    }
  }
}

function renderLabMindmap(options = {}) {
  if (!state.lab?.projectsById) return;
  const wrap = document.getElementById("mindmap");
  const layer = document.getElementById("nodes-layer");
  const svg = document.getElementById("edges");
  const canvas = document.getElementById("mindmap-canvas");
  if (!wrap || !layer || !svg || !canvas) return;

  rebuildLabWorldLayoutFull();
  const fullLayout = labWorldLayoutFull;
  if (!fullLayout) return;

  const visibleIds = projectIdsInGrouped(getFilteredGrouped());
  labWorldLayout = fullLayout;
  const visiblePlacements = fullLayout.placements.filter((p) =>
    visibleIds.has(p.project.id)
  );
  const { width: worldW, height: worldH } = fullLayout.bbox;

  canvas.style.width = `${worldW}px`;
  canvas.style.height = `${worldH}px`;
  layer.style.width = `${worldW}px`;
  layer.style.minHeight = `${worldH}px`;
  layer.innerHTML = "";
  svg.innerHTML = "";

  for (const program of fullLayout.programs) {
    const hasVisible = visiblePlacements.some(
      (p) => (p.region?.programId ?? "") === program.id
    );
    if (!hasVisible) continue;
    const label = document.createElement("div");
    label.className = "lab-program-label";
    label.style.left = `${program.x}px`;
    label.style.top = `${program.y}px`;
    label.style.width = `${program.width}px`;
    label.title = program.description || "";
    label.innerHTML = `<span class="lab-program-label__text">${escapeHtml(program.title)}</span>`;
    layer.appendChild(label);
  }

  for (const placement of visiblePlacements) {
    const region = placement.region;
    const frame = document.createElement("button");
    frame.type = "button";
    frame.className = "lab-project-frame";
    frame.dataset.projectId = placement.project.id;
    frame.style.left = `${region.x}px`;
    frame.style.top = `${region.y}px`;
    frame.style.width = `${region.width}px`;
    frame.style.height = `${region.height}px`;
    frame.title = region.title;
    frame.setAttribute("aria-label", `Проект: ${region.title}`);
    frame.addEventListener("click", (e) => {
      e.stopPropagation();
      void focusLabProject(placement.project.id, { animate: true });
    });
    layer.appendChild(frame);

    const { positions, project, nodeSizes } = placement;
    project.nodes.forEach((n) => {
      if (!isVisualNode(n)) return;
      const pos = positions[n.id];
      if (!pos) return;
      mountMapNode(pos, layer, project, n, nodeSizes);
    });

    for (const [, pos] of Object.entries(positions)) {
      if (!pos.isAdd || !pos.parentNode) continue;
      const labels = state.meta?.labels || TYPE_LABELS;
      mountAddNodeButton({
        pos,
        parent: pos.parentNode,
        projectId: project.id,
        labels,
        allowedTypes: allowedChildTypes(pos.parentNode.node_type),
        readOnly: isHubMode(),
        onOpen: (parent) => {
          state.project = project;
          openAddChildModal(parent);
        },
        mount: (addWrap) => layer.appendChild(addWrap),
      });
    }
  }

  renderLabEdges(svg, visiblePlacements, worldW, worldH);

  ensureLabCamera();
  if (labCamera) {
    labCamera.setWorldBounds(fullLayout.bbox);
    labCamera.setProjectRegions(fullLayout.projectRegions);
    labCamera.setNodeRegions(fullLayout.methodRegions);
    applyViewCamera(fullLayout, options);
    syncLabActivityOverlay();
    requestAnimationFrame(() => {
      syncLabActivityOverlay();
    });
    void preloadAllRunningAuthors();
  }
  updateViewChrome();
}

function fitCameraToProgram(layout, projectId, { animate = false } = {}) {
  const programId = findProgramIdForProject(state.lab?.grouped, projectId);
  const programRegion = findProgramRegion(layout, programId ?? "");
  if (programRegion) {
    if (animate) labCamera.flyToRegion(programRegion);
    else labCamera.fitRegion(programRegion);
  } else {
    labCamera.fitWorld();
  }
}

function applyViewCamera(layout, options = {}) {
  if (!labCamera) return;
  const mode = getViewMode();
  const projectId = options.flyToProjectId || state.project?.id;

  if (options.fitLab) {
    labCamera.fitWorld();
    return;
  }
  if (options.fitProgram) {
    fitCameraToProgram(layout, projectId, { animate: options.flyAnimate });
    return;
  }
  if (options.flyToProjectId && layout.projectRegions[options.flyToProjectId]) {
    const region = layout.projectRegions[options.flyToProjectId];
    if (options.flyAnimate) labCamera.flyToRegion(region);
    else labCamera.fitRegion(region);
    return;
  }
  if (mode === "researcher" && projectId && layout.projectRegions[projectId]) {
    labCamera.flyToRegion(layout.projectRegions[projectId]);
    return;
  }
  if (mode === "teamlead") {
    fitCameraToProgram(layout, projectId);
    return;
  }
  if (mode === "chief") {
    labCamera.fitWorld();
  }
}

function updateCanvasHint() {
  const el = document.getElementById("canvas-hint");
  if (!el) return;
  const mode = VIEW_MODES[getViewMode()] || VIEW_MODES.chief;
  el.textContent = `${mode.label}: ${mode.hint}`;
}

function updateViewChrome() {
  updateCanvasHint();
  const mode = getViewMode();
  document.body.dataset.viewMode = mode;
  const modeSelect = document.getElementById("view-mode-select");
  if (modeSelect) modeSelect.value = mode;
  document.querySelectorAll("[data-view-mode]").forEach((btn) => {
    const active = btn.getAttribute("data-view-mode") === mode;
    btn.setAttribute("aria-checked", active ? "true" : "false");
    btn.classList.toggle("is-active", active);
  });
}

function setViewMode(mode, { rerender = true } = {}) {
  if (!VIEW_MODES[mode]) mode = "chief";
  state.view.mode = mode;
  localStorage.setItem(VIEW_MODE_KEY, mode);
  updateViewChrome();

  if (!rerender || !state.lab) return;
  renderLabMindmap({
    fitLab: mode === "chief",
    fitProgram: mode === "teamlead",
    flyToProjectId: mode === "researcher" ? state.project?.id : null,
  });
}

function loadViewPreferences() {
  const stored = localStorage.getItem(VIEW_MODE_KEY);
  if (stored && VIEW_MODES[stored]) {
    state.view.mode = stored;
  }
}

function initViewControls() {
  loadViewPreferences();
  const group = document.getElementById("view-mode-group");
  group?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-view-mode]");
    if (!btn || !group.contains(btn)) return;
    setViewMode(btn.getAttribute("data-view-mode"));
  });
  group?.addEventListener("keydown", (e) => {
    const modes = Object.keys(VIEW_MODES);
    const current = modes.indexOf(getViewMode());
    if (current < 0) return;
    let next = current;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (current + 1) % modes.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (current - 1 + modes.length) % modes.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = modes.length - 1;
    else return;
    e.preventDefault();
    setViewMode(modes[next]);
    group.querySelector(`[data-view-mode="${modes[next]}"]`)?.focus();
  });
  document.getElementById("view-mode-select")?.addEventListener("change", (e) => {
    setViewMode(e.target.value);
  });
  updateViewChrome();
}

async function focusLabProject(projectId, { animate = false, reload = false } = {}) {
  if (!state.lab?.projectsById) return;
  if (reload || !state.lab.projectsById[projectId]) {
    if (isCompositeVirtualId(projectId)) {
      const compositeId = projectId.slice("composite:".length);
      state.lab.projectsById[projectId] = await KoiApi.getComposite(compositeId);
    } else {
      state.lab.projectsById[projectId] = await KoiApi.getProject(projectId);
    }
  }
  state.project = state.lab.projectsById[projectId];
  setActiveProjectInList(projectId);
  updatePaperReviewLink();
  updateAgentChatScope();
  void refreshAgentChat();
  const mode = getViewMode();
  if (mode === "teamlead") {
    renderLabMindmap({ fitProgram: true, flyAnimate: animate });
  } else {
    renderLabMindmap({
      flyToProjectId: projectId,
      flyAnimate: animate,
    });
  }
}

let _mindmapRetryTimer;
let _mindmapRenderRaf = 0;

function scheduleMindmapRender() {
  if (_mindmapRenderRaf) return;
  _mindmapRenderRaf = requestAnimationFrame(() => {
    _mindmapRenderRaf = 0;
    renderMindmap();
  });
}

function initMindmapResizeObserver() {
  const viewport = document.getElementById("mindmap-viewport");
  const wrap = document.getElementById("mindmap");
  const target = viewport || wrap;
  if (!target) return;

  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => {
      if (labCamera && labWorldLayout) {
        const camLayout = labCameraLayout() || labWorldLayout;
        labCamera.setWorldBounds(camLayout.bbox);
        labCamera.setProjectRegions(camLayout.projectRegions);
        labCamera.setNodeRegions(camLayout.methodRegions || {});
        syncLabActivityOverlay();
      } else {
        scheduleMindmapRender();
      }
    }).observe(target);
  }

  document.getElementById("projects-sidebar")?.addEventListener("transitionend", (e) => {
    if (e.propertyName === "width") scheduleMindmapRender();
  });
}

function renderMindmap(options = {}) {
  if (state.project) syncLabProject(state.project);
  if (state.lab?.projectsById) {
    renderLabMindmap(options);
    return;
  }
  if (!state.project) return;
  const wrap = document.getElementById("mindmap");
  const layer = document.getElementById("nodes-layer");
  const svg = document.getElementById("edges");
  if (!wrap || !layer || !svg) return;

  const rect = wrap.getBoundingClientRect();
  if (rect.width < 8 || rect.height < 8) {
    clearTimeout(_mindmapRetryTimer);
    _mindmapRetryTimer = setTimeout(renderMindmap, 80);
    return;
  }

  const trees = buildTree(state.project.nodes);
  const root = trees[0];
  if (!root) {
    setStatus("В проекте нет корневого узла (problem)", true);
    return;
  }

  buildSizeCache();
  const yByDepth = buildDepthY(root);
  const totalW = subtreeWidth(root);
  const startX = Math.max(LAYOUT.pad, (rect.width - totalW) / 2);

  const positions = {};
  layoutTopDown(root, 0, startX, yByDepth, positions);
  enforceVerticalOrder(positions);
  resolveOverlaps(positions);
  scaleTreeToFit(positions, rect.width, rect.height);
  enforceVerticalOrder(positions);
  resolveOverlaps(positions);

  svg.innerHTML = "";
  renderEdges(svg, positions, rect.width, rect.height);
  layer.innerHTML = "";

  function mountNode(pos, el, size, withKanbanBelow, nodeId) {
    const wrap = document.createElement("div");
    wrap.className = "node-wrap" + (withKanbanBelow ? " has-kanban-wrap" : "");
    if (nodeId) wrap.dataset.nodeId = nodeId;
    wrap.style.left = `${pos.x}px`;
    if (withKanbanBelow) {
      wrap.style.top = `${pos.y - size.h / 2}px`;
      wrap.style.transform = "translateX(-50%)";
    } else {
      wrap.style.top = `${pos.y}px`;
      wrap.style.transform = "translate(-50%, -50%)";
    }
    el.style.width = `${size.w}px`;
    el.style.height = `${size.h}px`;
    el.style.borderRadius = size.round;
    wrap.appendChild(el);
    layer.appendChild(wrap);
    return wrap;
  }

  function updateLayerExtent() {
    let maxBottom = LAYOUT.topPad;
    for (const p of Object.values(positions)) {
      const b = bboxFromPos(p, p.node);
      maxBottom = Math.max(maxBottom, b.bottom);
    }
    const h = maxBottom + LAYOUT.pad;
    layer.style.minHeight = `${h}px`;
    svg.setAttribute("height", String(h));
  }

  state.project.nodes.forEach((n) => {
    if (!isVisualNode(n)) return;
    const pos = positions[n.id];
    if (!pos) return;
    const size = nodeSize(n);
    const hasKanban = nodeHasKanban(n);
    const el = document.createElement("button");
    el.type = "button";
    const verdictBadge =
      n.node_type === "cause" ? VERDICT_BADGES[n.verdict] : null;
    el.className = `map-node ${n.node_type}${hasKanban ? " has-kanban clickable" : ""}${verdictBadge ? ` verdict-${n.verdict}` : ""}`;
    el.innerHTML = `
      <span class="node-label">${TYPE_LABELS[n.node_type]}</span>
      <span class="node-title">${escapeHtml(displayTitle(n))}</span>
      ${verdictBadge ? `<span class="node-verdict node-verdict--${n.verdict}" title="${verdictBadge.label}">${verdictBadge.mark}</span>` : ""}`;
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      if (hasKanban) openKanbanModal(n);
      else openNodeModal(n);
    });
    el.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      if (!hasKanban) openNodeModal(n);
    });
    el.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      if (hasKanban) openKanbanModal(n);
      else openNodeModal(n);
    });
    const wrap = mountNode(pos, el, size, hasKanban, n.id);
    if (n.node_type === "method" && hasResearchQuestions(n)) {
      const counts = researchQuestionCounts(n);
      const mapEl = wrap.firstElementChild;
      const core = document.createElement("div");
      core.className = "node-core has-method-questions";
      wrap.classList.add("has-research-questions");
      wrap.insertBefore(core, mapEl);
      core.appendChild(mapEl);

      const qBtn = document.createElement("button");
      qBtn.type = "button";
      qBtn.className = "method-questions-trigger";
      qBtn.setAttribute(
        "aria-label",
        `Выводы: ${counts.definite} с чётким ответом, ${counts.tentative} предварительных`
      );
      qBtn.title = "Выводы по экспериментам";
      qBtn.innerHTML = `<span class="rq-badge-q">?</span><span class="rq-badge-def">${counts.definite}</span><span class="rq-badge-sep">|</span><span class="rq-badge-tent">${counts.tentative}</span>`;
      qBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        openMethodQuestionsModal(n);
      });
      qBtn.addEventListener("mousedown", (e) => e.stopPropagation());
      core.appendChild(qBtn);
      wireResearchQuestionBadge(wrap, qBtn);
    }
    mountNodeTypeHelp(wrap, n.node_type);
    if (hasKanban) appendKanbanBelow(wrap, n);
    wireNodeWorkersHover(wrap, state.project, n);
  });

  updateLayerExtent();

  for (const [id, pos] of Object.entries(positions)) {
    if (!pos.isAdd || !pos.parentNode) continue;
    const labels = state.meta?.labels || TYPE_LABELS;
    mountAddNodeButton({
      pos,
      parent: pos.parentNode,
      labels,
      allowedTypes: allowedChildTypes(pos.parentNode.node_type),
      readOnly: isHubMode(),
      onOpen: openAddChildModal,
      mount: (addWrap) => layer.appendChild(addWrap),
    });
  }
}

function showModal(id) {
  document.getElementById(id).classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function hideModal(id) {
  document.getElementById(id).classList.add("hidden");
  if (id === "node-modal") resetNodeModal();
  if (id === "method-questions-modal") resetMethodQuestionsEditMode();
  if (!document.querySelector(".modal:not(.hidden)")) {
    document.body.classList.remove("modal-open");
  }
}

let reportPreviewTimer;

function setReportViewMode(mode) {
  const isWrite = mode === "write";
  const writeBtn = document.getElementById("card-report-mode-write");
  const viewBtn = document.getElementById("card-report-mode-view");
  const writePane = document.getElementById("card-report-pane-write");
  const viewPane = document.getElementById("card-report-pane-view");
  if (!writeBtn || !viewBtn || !writePane || !viewPane) return;

  writeBtn.classList.toggle("is-active", isWrite);
  viewBtn.classList.toggle("is-active", !isWrite);
  writeBtn.setAttribute("aria-selected", String(isWrite));
  viewBtn.setAttribute("aria-selected", String(!isWrite));
  writePane.classList.toggle("is-active", isWrite);
  viewPane.classList.toggle("is-active", !isWrite);
  writePane.hidden = !isWrite;
  viewPane.hidden = isWrite;

  if (isWrite) {
    document.getElementById("card-report-editor")?.focus();
  } else {
    updateReportPreview();
  }
}

function reportWriteProjectId() {
  return state.reportProjectId || primaryMemberProjectId() || state.project?.id;
}

function reportAssetUrlFn(markdownPath) {
  const pid = reportWriteProjectId();
  if (!pid) return markdownPath;
  const rel = state.reportRelativePath || "";
  if (String(markdownPath || "").startsWith("assets/") && rel.startsWith("reports/")) {
    const dir = rel.replace(/\/[^/]+\.md$/i, "");
    return KoiApi.knowledgeAssetUrl(pid, `${dir}/${markdownPath}`);
  }
  if (!state.reportBoardId || !state.reportCardId) return markdownPath;
  return KoiApi.reportAssetUrl(
    pid,
    state.reportBoardId,
    state.reportCardId,
    markdownPath
  );
}

function hookReportLinks(container) {
  const docPath = (state.reportRelativePath || "").replace(/^reports\//, "");
  if (!docPath || !state.project?.id) return;
  container.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (/^(https?:)?\/\//i.test(href) || href.startsWith("#") || href.startsWith("mailto:")) {
      a.setAttribute("target", "_blank");
      return;
    }
    const resolved = resolveKbPath(docPath, href);
    if (!resolved.endsWith(".md")) {
      a.removeAttribute("href");
      return;
    }
    const knowledgePath = resolved.startsWith("docs/")
      ? resolved
      : `reports/${resolved}`;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      void openLinkedReportMarkdown(knowledgePath);
    });
  });
}

async function openLinkedReportMarkdown(knowledgePath) {
  if (!state.project?.id) return;
  const editor = document.getElementById("card-report-editor");
  if (!editor) return;
  setStatus("Загрузка отчёта…");
  try {
    const content = await KoiApi.getKnowledgeFile(state.project.id, knowledgePath);
    editor.value = content;
    state.reportRelativePath = knowledgePath;
    state.reportDirty = false;
    document.getElementById("card-report-filename").textContent = knowledgePath;
    updateReportPreview();
    setStatus("");
  } catch (err) {
    setStatus(err.message, true);
  }
}

function updateReportPreview() {
  const preview = document.getElementById("card-report-preview");
  if (!preview) return;
  preview.innerHTML = renderMarkdown(
    document.getElementById("card-report-editor")?.value ?? "",
    { assetUrlFn: reportAssetUrlFn }
  );
  hookReportLinks(preview);
}

function insertReportMarkdown(editor, start, end, snippet) {
  const before = editor.value.slice(0, start);
  const after = editor.value.slice(end);
  editor.value = before + snippet + after;
  const pos = start + snippet.length;
  editor.selectionStart = editor.selectionEnd = pos;
  editor.focus();
  editor.dispatchEvent(new Event("input", { bubbles: true }));
}

function clipboardImageFile(clipboardData) {
  if (!clipboardData) return null;
  const items = clipboardData.items;
  if (items) {
    for (const item of items) {
      if (item.kind === "file" && item.type.startsWith("image/")) {
        const f = item.getAsFile();
        if (f) return f;
      }
    }
  }
  const files = clipboardData.files;
  if (files?.length) {
    const f = files[0];
    if (f.type.startsWith("image/")) return f;
  }
  return null;
}

async function onReportEditorPaste(e) {
  const editor = document.getElementById("card-report-editor");
  if (!editor || !state.reportCardId || !state.reportBoardId || !state.project) {
    return;
  }

  const file = clipboardImageFile(e.clipboardData);
  if (!file) return;

  e.preventDefault();
  e.stopPropagation();

  const selStart = editor.selectionStart ?? editor.value.length;
  const selEnd = editor.selectionEnd ?? selStart;

  setStatus("Загрузка изображения…");
  try {
    const data = await KoiApi.uploadReportAsset(
      reportWriteProjectId(),
      state.reportBoardId,
      state.reportCardId,
      file
    );
    const mdPath =
      data.markdown_path ||
      (data.filename ? `assets/${data.filename}` : null);
    if (!mdPath) {
      throw new Error("Сервер не вернул путь к картинке");
    }
    const snippet = `\n![image](${mdPath})\n`;
    insertReportMarkdown(editor, selStart, selEnd, snippet);
    state.reportDirty = true;
    scheduleReportPreview();
    setStatus("Изображение вставлено");
  } catch (err) {
    setStatus(err.message, true);
  }
}

function scheduleReportPreview() {
  clearTimeout(reportPreviewTimer);
  reportPreviewTimer = setTimeout(updateReportPreview, 100);
}

function closeCardReport() {
  closeCardTagPopover();
  hideModal("card-report-modal");
  state.reportCardId = null;
  state.reportBoardId = null;
  state.reportProjectId = null;
  state.reportRelativePath = null;
  state.reportDirty = false;
}

async function saveCardReport(force = false) {
  if (!state.reportCardId || !state.reportBoardId || !state.project) return;
  const editor = document.getElementById("card-report-editor");
  if (!force && !state.reportDirty) return;
  setStatus("Сохранение отчёта…");
  try {
    const data = await KoiApi.saveCardReport(
      reportWriteProjectId(),
      state.reportBoardId,
      state.reportCardId,
      editor.value
    );
    document.getElementById("card-report-filename").textContent =
      data.relative_path;
    state.reportDirty = false;
    setStatus("Отчёт сохранён");
  } catch (err) {
    setStatus(err.message, true);
  }
}

async function openCardReport(card, board) {
  if (!state.project?.id) {
    setStatus("Сначала выберите проект", true);
    return;
  }
  state.reportCardId = card.id;
  state.reportBoardId = board.id;
  state.reportProjectId = boardWriteProjectId(board);
  const editor = document.getElementById("card-report-editor");
  if (!editor) {
    setStatus("Модалка отчёта не найдена в DOM", true);
    return;
  }
  editor.value = "";
  document.getElementById("card-report-card-title").textContent = card.title;
  renderCardReportTags(card);
  document.getElementById("card-report-filename").textContent = "…";
  showModal("card-report-modal");
  setStatus("Загрузка отчёта…");
  try {
    const data = await KoiApi.getCardReport(
      reportWriteProjectId(),
      board.id,
      card.id
    );
    const content = typeof data?.content === "string" ? data.content : "";
    if (!content.trim()) {
      setStatus(
        `Отчёт пуст (${data?.source || "unknown"}). Проверьте файл ${data?.relative_path || ""}`,
        true
      );
    } else {
      setStatus("");
    }
    editor.value = content;
    state.reportRelativePath = data.relative_path || null;
    const fnameEl = document.getElementById("card-report-filename");
    if (data.source === "run") {
      fnameEl.textContent = `${data.run_relative_path || data.relative_path} — рабочий отчёт (основание вердикта и инсайтов); сохранение создаст публичную версию в ${data.relative_path}`;
    } else if (data.source === "template") {
      fnameEl.textContent = `${data.relative_path} — преднаполненный шаблон: заполните и сохраните`;
    } else {
      fnameEl.textContent = data.relative_path || "reports/";
    }
    state.reportDirty = false;
    setReportViewMode(content.trim() ? "view" : "write");
    updateReportPreview();
    if (!content.trim()) editor.focus();
  } catch (err) {
    const msg = String(err?.message || err || "Не удалось загрузить отчёт");
    editor.value = "";
    document.getElementById("card-report-filename").textContent = `Ошибка загрузки: ${msg}`;
    updateReportPreview();
    setStatus(msg, true);
  }
}

async function refreshReportFilenameIfOpen(cardId) {
  if (state.reportCardId !== cardId || !state.reportBoardId) return;
  const board = state.project.boards[state.reportBoardId];
  const card = board?.cards.find((c) => c.id === cardId);
  if (!card) return;
  try {
    const data = await KoiApi.getCardReport(
      reportWriteProjectId(),
      state.reportBoardId,
      cardId
    );
    document.getElementById("card-report-filename").textContent =
      data.relative_path;
  } catch {
    /* ignore */
  }
}

const FALLBACK_ALLOWED_CHILDREN = {
  problem: ["cause"],
  cause: ["cause_evidence", "remediation"],
  cause_evidence: ["method"],
  remediation: ["method"],
  method: [],
};

function allowedChildTypes(parentType) {
  const fromMeta = state.meta?.allowed_children?.[parentType];
  const list = (fromMeta?.length ? fromMeta : FALLBACK_ALLOWED_CHILDREN[parentType]) || [];
  return list.filter((t) => t !== "experiment");
}

function fillAddChildTypeSelect(parent) {
  const allowed = allowedChildTypes(parent.node_type);
  const typeSelect = document.querySelector("#add-child-form select");
  const typeLabel = document.getElementById("add-child-type-label");
  const labels = state.meta?.labels || TYPE_LABELS;
  const parentIntro = document.getElementById("add-child-parent-intro");
  const contextHint = document.getElementById("add-child-context-hint");
  const formatHint = document.getElementById("add-child-format-hint");
  const titleInput = document.querySelector("#add-child-form input[name=title]");
  const defaults = {
    cause: "Причина: …",
    cause_evidence: "Доказательство: …",
    remediation: "Устранение: …",
    method: "Название метода",
  };

  if (!allowed.length) {
    typeSelect.innerHTML = "";
    typeLabel?.classList.add("hidden");
    if (parentIntro) parentIntro.textContent = "";
    if (contextHint) contextHint.textContent = "";
    if (formatHint) formatHint.innerHTML = "";
    return;
  }

  typeSelect.innerHTML = allowed
    .map((t) => `<option value="${t}">${labels[t] || TYPE_LABELS[t] || t}</option>`)
    .join("");
  typeLabel?.classList.toggle("hidden", allowed.length === 1);

  const updateHints = () => {
    const nodeType = typeSelect.value || allowed[0];
    if (parentIntro) {
      parentIntro.textContent = formatAddParentIntro(parent.node_type, allowed, labels);
    }
    if (contextHint) {
      contextHint.textContent = formatAddChildContextHint(parent.node_type, nodeType);
    }
    if (formatHint) {
      formatHint.innerHTML = formatAddChildFormatHint(nodeType);
    }
    if (titleInput) {
      titleInput.placeholder = defaults[nodeType] || "Заголовок";
    }
  };

  typeSelect.onchange = updateHints;
  updateHints();
  if (titleInput) titleInput.value = "";
}

function updateNodeContentHint(nodeType) {
  const el = document.getElementById("node-content-hint");
  if (!el) return;
  const help = NODE_TYPE_HELP[nodeType];
  if (!help) {
    el.textContent = "";
    el.classList.add("hidden");
    return;
  }
  el.textContent = help.content;
  el.classList.remove("hidden");
}

function renderInlineDisplay(el, text, placeholder) {
  const empty = !String(text || "").trim();
  el.textContent = empty ? "" : text;
  el.classList.toggle("is-empty", empty);
  if (placeholder) el.dataset.placeholder = placeholder;
}

function renderCardDescDisplay(descEl, description, columnId) {
  if (!descEl) return;
  const text = cardDescriptionForDisplay(description, columnId);
  const placeholder = cardDescPlaceholder(columnId);
  renderInlineDisplay(descEl, text, placeholder);
  syncCardDescTodoOnlyState(descEl, description);
}

const CARD_DESC_PLACEHOLDER_PLAN = "План / заметка (двойной клик)";
const CARD_DESC_PLACEHOLDER_RUNNING =
  "Заметка или подзадачи: - [ ] пункт, - [x] готово (двойной клик)";
const CARD_DESC_PLACEHOLDER_CONCLUSION = "Краткий вывод (двойной клик)";
const KANBAN_CONCLUSION_COLUMNS = new Set(["done", "successful"]);

function isKanbanConclusionColumn(columnId) {
  return KANBAN_CONCLUSION_COLUMNS.has(columnId);
}

function isKanbanCompletedColumn(columnId) {
  return columnId === "done" || columnId === "successful";
}

function cardDescPlaceholder(columnId) {
  if (isKanbanConclusionColumn(columnId)) return CARD_DESC_PLACEHOLDER_CONCLUSION;
  if (columnId === "running") return CARD_DESC_PLACEHOLDER_RUNNING;
  return CARD_DESC_PLACEHOLDER_PLAN;
}

function cardDescriptionProse(description) {
  return String(description || "")
    .replace(/\\n/g, "\n")
    .replace(/-\s*\[([ xX])\]\s*([^\n]*?)(?=\s*-\s*\[|$)/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function cardDescriptionForDisplay(description, columnId) {
  const prose = cardDescriptionProse(description);
  if (prose) return prose;
  const subs = subtasksFromDescription(description);
  if (subs.open.length + subs.done.length > 0) return "";
  return String(description || "").trim();
}

function syncCardDescConclusionClass(descEl, columnId) {
  if (!descEl) return;
  descEl.classList.toggle("card-desc-conclusion", isKanbanConclusionColumn(columnId));
}

async function patchNodeFields(nodeId, fields) {
  const node = state.project.nodes.find((n) => n.id === nodeId);
  if (!node) return null;
  setStatus("Сохранение…");
  try {
    await KoiApi.patchNode(nodeWriteProjectId(node), nodeId, fields);
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    setStatus("Сохранено в project.md");
    renderMindmap();
    return state.project.nodes.find((n) => n.id === nodeId);
  } catch (err) {
    setStatus(err.message, true);
    return null;
  }
}

function wireInlineEdit({ display, input, getValue, setDisplay, onCommit }) {
  let committing = false;

  const showDisplay = () => {
    display.classList.remove("hidden");
    input.classList.add("hidden");
  };

  const showEdit = () => {
    input.value = getValue();
    display.classList.add("hidden");
    input.classList.remove("hidden");
    input.focus();
    if (input.select) input.select();
  };

  display.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    showEdit();
  });

  const commit = async () => {
    if (committing) return;
    const next = input.value.trim();
    const prev = getValue();
    showDisplay();
    setDisplay(next);
    if (next === prev) return;
    committing = true;
    const saved = await onCommit(next);
    committing = false;
    if (saved != null) setDisplay(saved);
    else setDisplay(prev);
  };

  input.addEventListener("blur", () => {
    void commit();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      setDisplay(getValue());
      showDisplay();
      return;
    }
    if (e.key === "Enter" && input.tagName !== "TEXTAREA") {
      e.preventDefault();
      input.blur();
    }
  });
}

function setupInlineEdits() {
  wireInlineEdit({
    display: document.getElementById("kanban-node-title-display"),
    input: document.getElementById("kanban-node-title-input"),
    getValue: () =>
      state.project?.nodes.find((n) => n.id === state.kanbanNodeId)?.title ?? "",
    setDisplay: (v) =>
      renderInlineDisplay(
        document.getElementById("kanban-node-title-display"),
        v,
        ""
      ),
    onCommit: async (title) => {
      const updated = await patchNodeFields(state.kanbanNodeId, { title });
      return updated?.title ?? null;
    },
  });

  wireInlineEdit({
    display: document.getElementById("kanban-node-desc-display"),
    input: document.getElementById("kanban-node-desc-input"),
    getValue: () =>
      state.project?.nodes.find((n) => n.id === state.kanbanNodeId)
        ?.description ?? "",
    setDisplay: (v) => {
      renderInlineDisplay(
        document.getElementById("kanban-node-desc-display"),
        v,
        "Описание (двойной клик)"
      );
      syncKanbanDescClamp();
    },
    onCommit: async (description) => {
      const updated = await patchNodeFields(state.kanbanNodeId, {
        description,
      });
      syncKanbanDescClamp();
      return updated?.description ?? null;
    },
  });

  wireInlineEdit({
    display: document.getElementById("node-title-display"),
    input: document.getElementById("node-title-input"),
    getValue: () =>
      state.project?.nodes.find((n) => n.id === state.activeNodeId)?.title ?? "",
    setDisplay: (v) =>
      renderInlineDisplay(document.getElementById("node-title-display"), v, ""),
    onCommit: async (title) => {
      const updated = await patchNodeFields(state.activeNodeId, { title });
      return updated?.title ?? null;
    },
  });

  wireInlineEdit({
    display: document.getElementById("node-desc-display"),
    input: document.getElementById("node-desc-input"),
    getValue: () =>
      state.project?.nodes.find((n) => n.id === state.activeNodeId)
        ?.description ?? "",
    setDisplay: (v) =>
      renderInlineDisplay(
        document.getElementById("node-desc-display"),
        v,
        "Описание (двойной клик)"
      ),
    onCommit: async (description) => {
      const updated = await patchNodeFields(state.activeNodeId, {
        description,
      });
      return updated?.description ?? null;
    },
  });
}

function fillKanbanNodeMeta(node) {
  renderInlineDisplay(
    document.getElementById("kanban-node-title-display"),
    node.title,
    ""
  );
  renderInlineDisplay(
    document.getElementById("kanban-node-desc-display"),
    node.description || "",
    "Описание (двойной клик)"
  );
  syncKanbanDescClamp();
}

function syncKanbanDescClamp() {
  const desc = document.getElementById("kanban-node-desc-display");
  const toggle = document.getElementById("kanban-desc-toggle");
  if (!desc || !toggle) return;
  const expanded = desc.classList.contains("is-expanded");
  if (expanded) {
    toggle.classList.remove("hidden");
    toggle.textContent = "свернуть";
    toggle.setAttribute("aria-expanded", "true");
    return;
  }
  desc.classList.add("is-clamped");
  const needsToggle =
    !!desc.textContent.trim() &&
    (desc.scrollHeight > desc.clientHeight + 2 || desc.textContent.length > 120);
  toggle.classList.toggle("hidden", !needsToggle);
  toggle.textContent = "развернуть";
  toggle.setAttribute("aria-expanded", "false");
}

function initKanbanModalChrome() {
  document.getElementById("kanban-desc-toggle")?.addEventListener("click", () => {
    const desc = document.getElementById("kanban-node-desc-display");
    const toggle = document.getElementById("kanban-desc-toggle");
    if (!desc || !toggle) return;
    const expand = !desc.classList.contains("is-expanded");
    desc.classList.toggle("is-expanded", expand);
    desc.classList.toggle("is-clamped", !expand);
    toggle.textContent = expand ? "свернуть" : "развернуть";
    toggle.setAttribute("aria-expanded", expand ? "true" : "false");
    if (!expand) syncKanbanDescClamp();
  });
  document.getElementById("kanban-hint-toggle")?.addEventListener("click", () => {
    const hint = document.getElementById("kanban-modal-hint");
    const btn = document.getElementById("kanban-hint-toggle");
    if (!hint || !btn) return;
    const show = hint.classList.toggle("hidden");
    btn.classList.toggle("is-active", !show);
    btn.setAttribute("aria-pressed", show ? "false" : "true");
  });
}

function fillNodeEdit(node) {
  renderInlineDisplay(
    document.getElementById("node-title-display"),
    node.title,
    ""
  );
  updateNodeContentHint(node.node_type);
  const descPlaceholder = NODE_TYPE_HELP[node.node_type]
    ? "Подробности (двойной клик)"
    : "Описание (двойной клик)";
  renderInlineDisplay(
    document.getElementById("node-desc-display"),
    node.description || "",
    descPlaceholder
  );
}

function openAddChildModal(parent) {
  if (isHubMode()) {
    setStatus("В Hub нельзя добавлять узлы — только просмотр", true);
    return;
  }
  state.activeNodeId = parent.id;
  document.getElementById("node-edit-block").classList.add("hidden");
  document.getElementById("node-content-hint")?.classList.add("hidden");
  document.getElementById("btn-delete-node").classList.add("hidden");
  document.getElementById("add-child-block").classList.remove("hidden");
  document.getElementById("node-modal-type").textContent =
    TYPE_LABELS[parent.node_type];
  const pt = parent.node_type;
  document.getElementById("node-modal-title").textContent =
    pt === "problem"
      ? "Добавить причину"
      : pt === "cause"
        ? "Добавить доказательство или гипотезу"
        : "Добавить метод";
  fillAddChildTypeSelect(parent);
  document.querySelector("#add-child-form").reset();
  fillAddChildTypeSelect(parent);
  showModal("node-modal");
}

function openNodeModal(node) {
  hideModal("kanban-modal");
  state.activeNodeId = node.id;
  document.getElementById("node-edit-block").classList.remove("hidden");
  document.getElementById("add-child-block").classList.add("hidden");
  document.getElementById("node-modal-type").textContent =
    TYPE_LABELS[node.node_type];
  fillNodeEdit(node);

  const delBtn = document.getElementById("btn-delete-node");
  delBtn.classList.toggle("hidden", node.node_type === "problem");

  const addMethodBtn = document.getElementById("btn-add-method");
  const canAddMethod =
    node.node_type === "cause_evidence" || node.node_type === "remediation";
  addMethodBtn.classList.toggle("hidden", !canAddMethod);
  addMethodBtn.onclick = () => openAddChildModal(node);

  showModal("node-modal");
}

function resetNodeModal() {
  document.getElementById("node-edit-block").classList.remove("hidden");
  document.getElementById("add-child-block").classList.add("hidden");
  document.getElementById("add-child-parent-intro").textContent = "";
  document.getElementById("add-child-context-hint").textContent = "";
  document.getElementById("add-child-format-hint").innerHTML = "";
  document.getElementById("btn-add-method")?.classList.add("hidden");
}

async function onAddChildSubmit(e) {
  e.preventDefault();
  const parentId = state.activeNodeId;
  const parent = state.project?.nodes?.find((n) => n.id === parentId);
  const fd = new FormData(e.target);
  const allowed = parent ? allowedChildTypes(parent.node_type) : [];
  const nodeType = fd.get("node_type") || allowed[0];
  const title = fd.get("title").toString().trim();
  if (!nodeType) {
    setStatus("Нельзя добавить узел: неизвестный тип родителя", true);
    return;
  }
  if (!title) {
    setStatus("Введите заголовок", true);
    return;
  }
  setStatus("Добавление…");
  try {
    await KoiApi.addNode(nodeWriteProjectId(parent), {
      parent_id: parentId,
      node_type: nodeType,
      title,
      description: "",
    });
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    e.target.reset();
    setStatus("Сохранено в project.md");
    hideModal("node-modal");
    resetNodeModal();
    renderMindmap();
  } catch (err) {
    setStatus(err.message, true);
  }
}

async function onDeleteNode() {
  const node = state.project.nodes.find((n) => n.id === state.activeNodeId);
  if (!node || node.node_type === "problem") return;
  if (!confirm(`Удалить узел «${node.title}» и всех потомков?`)) return;
  setStatus("Удаление…");
  try {
    await KoiApi.deleteNode(nodeWriteProjectId(node), node.id);
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    setStatus("Сохранено в project.md");
    hideModal("node-modal");
    renderMindmap();
  } catch (err) {
    setStatus(err.message, true);
  }
}

function formatImportance(importance) {
  const n = Math.max(1, Math.min(5, Number(importance) || 3));
  return "★".repeat(n) + "☆".repeat(5 - n);
}

function normalizeResearchImportance(importance) {
  return Math.max(1, Math.min(5, Number(importance) || 3));
}

function rqImportanceMin() {
  try {
    const raw = localStorage.getItem(
      `${RQ_IMPORTANCE_FILTER_KEY}:${state.project?.id || ""}`
    );
    const n = parseInt(raw, 10);
    return Number.isFinite(n) && n >= 1 && n <= 5 ? n : 1;
  } catch {
    return 1;
  }
}

function setRqImportanceMin(min) {
  const clamped = Math.max(1, Math.min(5, Number(min) || 1));
  try {
    localStorage.setItem(
      `${RQ_IMPORTANCE_FILTER_KEY}:${state.project?.id || ""}`,
      String(clamped)
    );
  } catch {
    /* ignore */
  }
  return clamped;
}

function filterResearchQuestionsByImportance(questions, minImportance) {
  const min = normalizeResearchImportance(minImportance);
  return (questions || []).filter(
    (q) => normalizeResearchImportance(q.importance) >= min
  );
}

function sortResearchQuestionsByImportance(questions) {
  return [...(questions || [])].sort(
    (a, b) =>
      normalizeResearchImportance(b.importance) -
        normalizeResearchImportance(a.importance) ||
      String(a.question || "").localeCompare(String(b.question || ""), "ru")
  );
}

function importanceBadgeHtml(importance) {
  const n = normalizeResearchImportance(importance);
  const stars = formatImportance(n);
  return `<span class="method-question-importance" title="Важность ${n} из 5" aria-label="Важность ${n} из 5"><span class="method-question-importance-stars" aria-hidden="true">${stars}</span><span class="method-question-importance-num">${n}</span></span>`;
}

function researchQuestionCardLabel(q, node) {
  if (q.card_title) return q.card_title;
  if (!q.card_id) return null;
  const board = getBoardForNode(state.project, node);
  const card = board && getBoardCard(board, q.card_id);
  return card?.title || null;
}

function researchQuestionCardSourceHtml(q, node) {
  const title = researchQuestionCardLabel(q, node);
  if (!q.card_id) {
    return `<p class="method-question-source method-question-source--missing">Эксперимент не привязан</p>`;
  }
  if (!title) {
    return `<p class="method-question-source method-question-source--missing">Эксперимент: карточка не найдена</p>`;
  }
  return `<p class="method-question-source">Эксперимент: <button type="button" class="method-question-card-link" data-card-id="${escapeHtml(q.card_id)}">${escapeHtml(title)}</button></p>`;
}

function renderMethodQuestionItem(q, node) {
  const narrative = researchQuestionNarrative(q);
  return `
    <article class="method-question-item" data-importance="${normalizeResearchImportance(q.importance)}">
      ${researchQuestionCardSourceHtml(q, node)}
      <div class="method-question-head">
        <p class="method-question-q">${escapeHtml(q.question)}</p>
        ${importanceBadgeHtml(q.importance)}
      </div>
      <p class="method-question-narrative">${escapeHtml(narrative || "Ответ пока не сформулирован.")}</p>
    </article>`;
}

function bindMethodQuestionsCardLinks(node) {
  const body = document.getElementById("method-questions-body");
  const board = getBoardForNode(state.project, node);
  if (!body || !board) return;
  body.querySelectorAll(".method-question-card-link").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const card = getBoardCard(board, btn.dataset.cardId);
      if (card) void openCardReport(card, board);
    });
  });
}

function renderMethodQuestionsToolbar(node, { totalCount, filteredCount, minImportance }) {
  const toolbar = document.getElementById("method-questions-toolbar");
  const chipsEl = toolbar?.querySelector(".method-questions-filter-chips");
  const countEl = document.getElementById("method-questions-filter-count");
  if (!toolbar || !chipsEl) return;

  if (!totalCount) {
    toolbar.classList.add("hidden");
    return;
  }

  toolbar.classList.remove("hidden");
  chipsEl.innerHTML = RQ_IMPORTANCE_FILTER_OPTIONS.map((opt) => {
    const active = opt.min === minImportance;
    return `<button type="button" class="method-questions-filter-chip${active ? " is-active" : ""}" data-min="${opt.min}" aria-pressed="${active ? "true" : "false"}" title="${escapeHtml(opt.title)}">${escapeHtml(opt.label)}</button>`;
  }).join("");

  if (countEl) {
    countEl.textContent =
      filteredCount === totalCount
        ? `${totalCount}`
        : `${filteredCount} / ${totalCount}`;
    countEl.title =
      filteredCount === totalCount
        ? `${totalCount} выводов`
        : `Показано ${filteredCount} из ${totalCount}`;
  }

  chipsEl.querySelectorAll(".method-questions-filter-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const min = setRqImportanceMin(Number(btn.dataset.min) || 1);
      renderMethodQuestionsBody(node, { minImportance: min });
    });
  });
}

function renderMethodQuestionsBody(node, { minImportance } = {}) {
  const body = document.getElementById("method-questions-body");
  const allQuestions = node.research_questions || [];
  const min = minImportance ?? rqImportanceMin();
  const questions = sortResearchQuestionsByImportance(
    filterResearchQuestionsByImportance(allQuestions, min)
  );

  renderMethodQuestionsToolbar(node, {
    totalCount: allQuestions.length,
    filteredCount: questions.length,
    minImportance: min,
  });

  if (!allQuestions.length) {
    body.innerHTML =
      '<p class="method-questions-empty">Пока нет выводов по экспериментам этого метода.</p>';
    document.getElementById("method-questions-toolbar")?.classList.add("hidden");
    return;
  }

  if (!questions.length) {
    body.innerHTML = `<p class="method-questions-empty method-questions-empty--filter">Нет выводов с важностью ≥ ${min}. <button type="button" class="method-questions-filter-reset" data-reset-min="1">Показать все</button></p>`;
    body.querySelector(".method-questions-filter-reset")?.addEventListener("click", () => {
      setRqImportanceMin(1);
      renderMethodQuestionsBody(node, { minImportance: 1 });
    });
    return;
  }

  const definite = questions.filter((q) => q.certainty === "definite");
  const tentative = questions.filter((q) => q.certainty !== "definite");
  const parts = [];
  if (definite.length) {
    parts.push(
      `<section class="method-questions-section method-questions-section--definite">
        <h3>${RESEARCH_CERTAINTY_LABELS.definite}</h3>
        ${definite.map((q) => renderMethodQuestionItem(q, node)).join("")}
      </section>`
    );
  }
  if (tentative.length) {
    parts.push(
      `<section class="method-questions-section method-questions-section--tentative">
        <h3>${RESEARCH_CERTAINTY_LABELS.tentative}</h3>
        ${tentative.map((q) => renderMethodQuestionItem(q, node)).join("")}
      </section>`
    );
  }
  body.innerHTML = parts.join("");
  bindMethodQuestionsCardLinks(node);
}

function resetMethodQuestionsEditMode() {
  document.getElementById("method-questions-body")?.classList.remove("hidden");
  document.getElementById("method-questions-edit")?.classList.add("hidden");
  document.getElementById("method-questions-toolbar")?.classList.remove("hidden");
  document.getElementById("btn-save-rq")?.classList.add("hidden");
  document
    .querySelector("#method-questions-modal .modal-panel--questions")
    ?.classList.remove("is-editing");
  const toggle = document.getElementById("btn-toggle-rq-edit");
  if (toggle) toggle.textContent = "Редактировать";
}

function updateAddResearchQuestionButton() {
  const addBtn = document.getElementById("btn-add-rq-row");
  if (addBtn) addBtn.disabled = false;
}

function buildResearchQuestionCardOptions(node, selectedId) {
  const board = getBoardForNode(state.project, node);
  const cards = board?.cards || [];
  const opts = ['<option value="">— не выбран —</option>'];
  for (const c of cards) {
    const sel = c.id === selectedId ? " selected" : "";
    opts.push(
      `<option value="${escapeHtml(c.id)}"${sel}>${escapeHtml(c.title)}</option>`
    );
  }
  return opts.join("");
}

const RQ_EDIT_CERTAINTY_LABELS = {
  definite: "Точный ответ",
  tentative: "Неточный / предварительный",
};

const RQ_EDIT_PENCIL_SVG = `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`;

const RQ_CERTAINTY_CHECK_SVG = `<svg viewBox="0 0 12 12" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" d="M2.4 6.2 4.8 8.6 9.6 3.4"/></svg>`;

const RQ_CERTAINTY_TENTATIVE_SVG = `<svg viewBox="0 0 12 12" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" d="M3.2 4.2h5.6M3.2 6h3.8M3.2 7.8h5.6"/></svg>`;

function rqCertaintyBadgeHtml(certainty) {
  const kind = certainty === "tentative" ? "tentative" : "definite";
  const label =
    kind === "definite" ? "Точный ответ" : "Предварительный вывод";
  const icon =
    kind === "definite" ? RQ_CERTAINTY_CHECK_SVG : RQ_CERTAINTY_TENTATIVE_SVG;
  return `<span class="method-rq-certainty-badge method-rq-certainty-badge--${kind}" title="${label}" aria-label="${label}">${icon}</span>`;
}

function syncRqRowCertaintyBadge(row) {
  const certainty = row.querySelector(".rq-certainty")?.value || "definite";
  const kind = certainty === "tentative" ? "tentative" : "definite";
  const label =
    kind === "definite" ? "Точный ответ" : "Предварительный вывод";
  const badge = row.querySelector(".method-rq-certainty-badge");
  if (!badge) return;
  badge.className = `method-rq-certainty-badge method-rq-certainty-badge--${kind}`;
  badge.title = label;
  badge.setAttribute("aria-label", label);
  badge.innerHTML =
    kind === "definite" ? RQ_CERTAINTY_CHECK_SVG : RQ_CERTAINTY_TENTATIVE_SVG;
}

function rqCardDisplayLabel(node, cardId) {
  if (!cardId) return "— не выбран —";
  const board = getBoardForNode(state.project, node);
  const card = board?.cards?.find((c) => c.id === cardId);
  return card?.title || "— не выбран —";
}

function rqFieldBlockHtml(label, displayText, inputHtml, placeholder) {
  const empty = !String(displayText || "").trim();
  return `
    <div class="method-rq-edit-field-block">
      <span class="method-rq-field-label">${label}</span>
      <div class="method-rq-field-value">
        <p class="rq-editable-display${empty ? " is-empty" : ""}" data-placeholder="${escapeHtml(placeholder)}" title="Двойной клик — редактировать">${escapeHtml(displayText)}</p>
        ${inputHtml}
        <span class="rq-edit-pencil" aria-hidden="true">${RQ_EDIT_PENCIL_SVG}</span>
      </div>
    </div>`;
}

function wireRqEditableText(block) {
  const display = block.querySelector(".rq-editable-display");
  const input = block.querySelector(".rq-editable-input");
  if (!display || !input) return;

  const readDisplay = () =>
    display.classList.contains("is-empty") ? "" : display.textContent;

  const syncDisplay = () => {
    const v = input.value.trim();
    display.textContent = v;
    display.classList.toggle("is-empty", !v);
  };

  const showEdit = (e) => {
    e.stopPropagation();
    input.value = readDisplay();
    display.classList.add("hidden");
    input.classList.remove("hidden");
    input.focus();
    if (input.select) input.select();
  };

  display.addEventListener("dblclick", showEdit);

  const commit = () => {
    syncDisplay();
    display.classList.remove("hidden");
    input.classList.add("hidden");
  };

  input.addEventListener("blur", commit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      input.value = readDisplay();
      commit();
      return;
    }
    if (e.key === "Enter" && input.tagName !== "TEXTAREA") {
      e.preventDefault();
      input.blur();
    }
  });
}

function wireRqEditableSelect(block) {
  const display = block.querySelector(".rq-editable-display");
  const select = block.querySelector(".rq-editable-input");
  if (!display || !select) return;

  const syncDisplay = () => {
    const opt = select.options[select.selectedIndex];
    const label = opt?.textContent?.trim() || "";
    display.textContent = label;
    display.classList.toggle("is-empty", !label || label === "— не выбран —");
  };

  const showEdit = (e) => {
    e.stopPropagation();
    display.classList.add("hidden");
    select.classList.remove("hidden");
    select.focus();
  };

  display.addEventListener("dblclick", showEdit);

  const commit = () => {
    syncDisplay();
    display.classList.remove("hidden");
    select.classList.add("hidden");
  };

  select.addEventListener("change", commit);
  select.addEventListener("blur", commit);
  select.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      commit();
    }
  });
}

function setRqRowExpanded(row, open) {
  row.classList.toggle("is-expanded", open);
  row.querySelector(".method-rq-edit-details")?.classList.toggle("hidden", !open);
  const toggle = row.querySelector(".method-rq-edit-toggle");
  if (toggle) toggle.setAttribute("aria-expanded", String(open));
}

function bindResearchQuestionEditRow(row, node) {
  row.querySelector(".method-rq-edit-toggle")?.addEventListener("click", (e) => {
    e.stopPropagation();
    setRqRowExpanded(row, !row.classList.contains("is-expanded"));
  });

  row.querySelectorAll(".method-rq-edit-field-block").forEach((block) => {
    if (block.querySelector("select.rq-editable-input")) {
      wireRqEditableSelect(block);
    } else {
      wireRqEditableText(block);
    }
  });

  const certaintySelect = row.querySelector(".rq-certainty");
  certaintySelect?.addEventListener("change", () => syncRqRowCertaintyBadge(row));
  certaintySelect?.addEventListener("blur", () => syncRqRowCertaintyBadge(row));

  row.querySelector(".btn-remove-rq")?.addEventListener("click", (e) => {
    e.stopPropagation();
    row.remove();
    updateAddResearchQuestionButton();
  });
}

function createResearchQuestionEditRow(q, node, { expand = false } = {}) {
  const questionText = q.question || "";
  const narrativeText = q.narrative || "";
  const answerText = q.answer || "";
  const certainty = q.certainty || "definite";
  const importance = q.importance ?? 3;
  const cardLabel = rqCardDisplayLabel(node, q.card_id || "");

  const row = document.createElement("div");
  row.className = `method-rq-edit-row${expand ? " is-expanded" : ""}`;
  if (q.id) row.dataset.id = q.id;
  row.innerHTML = `
    <div class="method-rq-edit-summary">
      <button type="button" class="method-rq-edit-toggle" aria-expanded="${expand}" aria-label="Развернуть вопрос">
        <svg class="method-rq-chevron" viewBox="0 0 12 12" aria-hidden="true"><path fill="currentColor" d="M4.2 2.4 8.4 6 4.2 9.6 3.3 8.7 6.6 6 3.3 3.3z"/></svg>
      </button>
      ${rqCertaintyBadgeHtml(certainty)}
      ${rqFieldBlockHtml(
        "Вопрос",
        questionText,
        `<textarea class="rq-editable-input rq-question inline-edit-field hidden" rows="2" placeholder="Формулировка понятна без знания метрик…">${escapeHtml(questionText)}</textarea>`,
        "Вопрос (без жаргона: SFT, RL, diversity…)"
      )}
      <button type="button" class="btn btn-danger btn-remove-rq" aria-label="Удалить вопрос">×</button>
    </div>
    <div class="method-rq-edit-details${expand ? "" : " hidden"}">
      ${rqFieldBlockHtml(
        "Эксперимент (карточка канбана)",
        cardLabel,
        `<select class="rq-editable-input rq-card-id inline-edit-field hidden">${buildResearchQuestionCardOptions(node, q.card_id || "")}</select>`,
        "— не выбран —"
      )}
      ${rqFieldBlockHtml(
        "Ответ (человеческим языком)",
        narrativeText,
        `<textarea class="rq-editable-input rq-narrative inline-edit-field hidden" rows="3" placeholder="Развёрнутый ответ без жаргона и сырых цифр…">${escapeHtml(narrativeText)}</textarea>`,
        "Развёрнутый ответ…"
      )}
      ${rqFieldBlockHtml(
        "Заметка (техническая, не показывается)",
        answerText,
        `<textarea class="rq-editable-input rq-answer inline-edit-field hidden" rows="2" placeholder="mean diversity 2.02 vs 1.46…">${escapeHtml(answerText)}</textarea>`,
        "Техническая заметка…"
      )}
      <div class="method-rq-edit-meta">
        ${rqFieldBlockHtml(
          "Тип ответа",
          RQ_EDIT_CERTAINTY_LABELS[certainty] || RQ_EDIT_CERTAINTY_LABELS.definite,
          `<select class="rq-editable-input rq-certainty inline-edit-field hidden">
            <option value="definite"${certainty === "definite" ? " selected" : ""}>Точный ответ</option>
            <option value="tentative"${certainty === "tentative" ? " selected" : ""}>Неточный / предварительный</option>
          </select>`,
          "Точный ответ"
        )}
        ${rqFieldBlockHtml(
          "Важность (1–5)",
          String(importance),
          `<select class="rq-editable-input rq-importance inline-edit-field hidden">
            ${[1, 2, 3, 4, 5]
              .map(
                (n) =>
                  `<option value="${n}"${importance === n ? " selected" : ""}>${n}</option>`
              )
              .join("")}
          </select>`,
          "3"
        )}
      </div>
    </div>`;

  bindResearchQuestionEditRow(row, node);
  return row;
}

function renderMethodQuestionsEdit(node) {
  const edit = document.getElementById("method-questions-edit");
  if (!edit) return;
  edit.innerHTML = `
    <p class="method-questions-edit-hint">▶ развернуть детали · двойной клик — редактировать поле</p>
    <div id="method-rq-edit-list" class="method-rq-edit-list"></div>
    <button type="button" id="btn-add-rq-row" class="btn">+ Вопрос</button>`;
  const list = edit.querySelector("#method-rq-edit-list");
  for (const q of node.research_questions || []) {
    list.appendChild(createResearchQuestionEditRow(q, node));
  }
  edit.querySelector("#btn-add-rq-row").addEventListener("click", () => {
    list.appendChild(
      createResearchQuestionEditRow(
        {
          question: "",
          narrative: "",
          answer: "",
          certainty: "definite",
          importance: 3,
          card_id: "",
        },
        node,
        { expand: true }
      )
    );
    updateAddResearchQuestionButton();
  });
  updateAddResearchQuestionButton();
}

function collectResearchQuestionsFromEdit() {
  const rows = document.querySelectorAll(
    "#method-questions-edit .method-rq-edit-row"
  );
  return Array.from(rows)
    .map((row, i) => ({
      id: row.dataset.id || `rq-${Date.now()}-${i}`,
      question: row.querySelector(".rq-question")?.value.trim() || "",
      narrative: row.querySelector(".rq-narrative")?.value.trim() || "",
      answer: row.querySelector(".rq-answer")?.value.trim() || "",
      certainty: row.querySelector(".rq-certainty")?.value || "definite",
      importance: Number(row.querySelector(".rq-importance")?.value) || 3,
      card_id: row.querySelector(".rq-card-id")?.value.trim() || null,
    }))
    .filter((q) => q.question);
}

function toggleMethodQuestionsEdit() {
  const body = document.getElementById("method-questions-body");
  const edit = document.getElementById("method-questions-edit");
  const saveBtn = document.getElementById("btn-save-rq");
  const toggle = document.getElementById("btn-toggle-rq-edit");
  const editing = !edit.classList.contains("hidden");
  if (editing) {
    resetMethodQuestionsEditMode();
    return;
  }
  const node = state.project?.nodes.find((n) => n.id === state.questionsNodeId);
  if (!node) return;
  renderMethodQuestionsEdit(node);
  body.classList.add("hidden");
  edit.classList.remove("hidden");
  document.getElementById("method-questions-toolbar")?.classList.add("hidden");
  saveBtn.classList.remove("hidden");
  document
    .querySelector("#method-questions-modal .modal-panel--questions")
    ?.classList.add("is-editing");
  toggle.textContent = "Отмена";
}

async function saveMethodQuestions() {
  if (!state.questionsNodeId) return;
  const active = document.activeElement;
  if (active?.closest("#method-questions-edit")) active.blur();
  const questions = collectResearchQuestionsFromEdit();
  const updated = await patchNodeFields(state.questionsNodeId, {
    research_questions: questions,
  });
  if (!updated) return;
  resetMethodQuestionsEditMode();
  renderMethodQuestionsBody(updated);
}

function openMethodQuestionsModal(node) {
  hideModal("kanban-modal");
  state.questionsNodeId = node.id;
  resetMethodQuestionsEditMode();
  document.getElementById("method-questions-title").textContent = node.title;
  renderMethodQuestionsBody(node);
  showModal("method-questions-modal");
}

function openKanbanModal(node) {
  state.kanbanNodeId = node.id;
  const board = getBoardForNode(state.project, node);
  if (!board) return;

  state.kanbanDisabledTagFilters = loadKanbanDisabledTagFilters(state.project?.id, board.id);
  state.kanbanViewMode = state.kanbanViewMode || "board";

  document.getElementById("kanban-modal-type").textContent =
    TYPE_LABELS[node.node_type];
  fillKanbanNodeMeta(node);

  setKanbanViewMode(state.kanbanViewMode);
  renderActiveKanbanView(board, node);
  showModal("kanban-modal");
}

function setKanbanViewMode(mode) {
  const boardTab = document.getElementById("kanban-tab-board");
  const dagTab = document.getElementById("kanban-tab-dag");
  const boardPane = document.getElementById("kanban-pane-board");
  const dagPane = document.getElementById("kanban-pane-dag");
  const tagFilter = document.getElementById("kanban-tag-filter");
  const hint = document.getElementById("kanban-modal-hint");
  const modalPanel = document.querySelector(".modal-panel--kanban");
  const isBoard = mode !== "dag";
  state.kanbanViewMode = isBoard ? "board" : "dag";
  modalPanel?.classList.toggle("is-dag-mode", !isBoard);
  boardTab?.classList.toggle("is-active", isBoard);
  dagTab?.classList.toggle("is-active", !isBoard);
  boardTab?.setAttribute("aria-selected", isBoard ? "true" : "false");
  dagTab?.setAttribute("aria-selected", isBoard ? "false" : "true");
  boardPane?.classList.toggle("is-active", isBoard);
  dagPane?.classList.toggle("is-active", !isBoard);
  if (boardPane) boardPane.hidden = !isBoard;
  if (dagPane) dagPane.hidden = isBoard;
  if (isBoard) destroyKanbanDagView();
  tagFilter?.classList.toggle("hidden", !tagFilter.childElementCount);
  if (hint) {
    hint.textContent = isHubMode()
      ? "Только просмотр · ↗ — отчёт · фильтр по тегам · DAG — связи между карточками"
      : isBoard
        ? "⠿ — перетащить · + — новая карточка · двойной клик — правка · ↗ — отчёт"
        : "DAG — → зажать на карточке, отпустить на цели · двойной клик на стрелке — удалить";
  }
}

function getKanbanDagContext(board, node) {
  const writeProjectId = boardWriteProjectId(board);
  const boardId = board.id;
  const liveBoard = () => state.project?.boards?.[boardId] || board;
  const liveNode = () =>
    state.project?.nodes?.find((n) => n.id === node?.id) || node;
  if (isHubMode()) {
    return {
      node,
      projectId: state.project?.id,
      tagFilters: state.kanbanDisabledTagFilters || [],
      cardMatchesFilter: cardMatchesKanbanTagFilter,
      cardTagsHtml: (card) => cardTagsRowHtml(card.tags, { dag: true }),
      onOpenReport: (card) => void openCardReport(card, liveBoard()),
      readOnly: true,
    };
  }
  const refreshDag = async () => {
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    const refreshedNode = liveNode();
    const refreshedBoard = liveBoard();
    if (refreshedBoard) {
      const dagEl = document.getElementById("kanban-dag-view");
      if (dagEl) refreshKanbanDagView(dagEl, refreshedBoard, getKanbanDagContext(refreshedBoard, refreshedNode));
    }
  };
  return {
    node,
    projectId: writeProjectId || state.project?.id,
    tagFilters: state.kanbanDisabledTagFilters || [],
    cardMatchesFilter: cardMatchesKanbanTagFilter,
    cardTagsHtml: (card) => cardTagsRowHtml(card.tags, { dag: true }),
    onOpenReport: (card) => void openCardReport(card, liveBoard()),
    onStatus: (msg, isError = false) => setStatus(msg, isError),
    onRefresh: refreshDag,
    onSuggestDag: async () => {
      if (!writeProjectId) throw new Error("Не удалось определить проект");
      return KoiApi.suggestBoardDag(writeProjectId, boardId, { apply: false });
    },
    onApplySuggestions: async (selected) => {
      if (!selected?.length || !writeProjectId) return;
      const byTo = new Map();
      for (const item of selected) {
        const toId = item.to_card_id;
        if (!byTo.has(toId)) byTo.set(toId, []);
        byTo.get(toId).push(item.from_card_id);
      }
      for (const [toId, fromIds] of byTo.entries()) {
        const b = liveBoard();
        const card = getBoardCard(b, toId);
        if (!card) continue;
        const deps = [...new Set([...(card.depends_on || []), ...fromIds])];
        await persistCard(b, toId, { depends_on: deps }, { rerenderKanban: false });
      }
      await refreshDag();
    },
    onAddEdge: async (toCardId, fromCardId) => {
      const b = liveBoard();
      const writeProjectId = boardWriteProjectId(b);
      if (!writeProjectId) {
        setStatus("Не удалось определить проект для сохранения связи", true);
        throw new Error("No write project id");
      }
      const card = getBoardCard(b, toCardId);
      if (!card) {
        setStatus("Целевая карточка не найдена", true);
        throw new Error("Target card not found");
      }
      if ((card.depends_on || []).includes(fromCardId)) return;
      const deps = [...new Set([...(card.depends_on || []), fromCardId])];
      const updated = await persistCard(b, toCardId, { depends_on: deps }, { rerenderKanban: false });
      if (!updated) {
        setStatus("Ошибка сохранения связи в project.md", true);
        throw new Error("Persist failed");
      }
      const dagEl = document.getElementById("kanban-dag-view");
      if (dagEl && state.kanbanViewMode === "dag") {
        refreshKanbanDagView(dagEl, liveBoard(), getKanbanDagContext(liveBoard(), liveNode()));
      }
    },
    onRemoveEdge: async (toCardId, fromCardId) => {
      const b = liveBoard();
      const writeProjectId = boardWriteProjectId(b);
      if (!writeProjectId) {
        setStatus("Не удалось определить проект для удаления связи", true);
        throw new Error("No write project id");
      }
      const card = getBoardCard(b, toCardId);
      if (!card) {
        setStatus("Целевая карточка не найдена", true);
        throw new Error("Target card not found");
      }
      const deps = (card.depends_on || []).filter((d) => d !== fromCardId);
      const updated = await persistCard(b, toCardId, { depends_on: deps }, { rerenderKanban: false });
      if (!updated) {
        setStatus("Не удалось удалить связь в project.md", true);
        throw new Error("Persist failed");
      }
      const dagEl = document.getElementById("kanban-dag-view");
      if (dagEl && state.kanbanViewMode === "dag") {
        refreshKanbanDagView(dagEl, liveBoard(), getKanbanDagContext(liveBoard(), liveNode()));
      }
    },
    onLinkCardToQuestion: async (cardId, rqId) => {
      if (!node?.id) return;
      const questions = (node.research_questions || []).map((q) =>
        q.id === rqId ? { ...q, card_id: cardId } : q
      );
      await patchNodeFields(node.id, { research_questions: questions });
      await refreshDag();
    },
    onUnlinkQuestion: async (rqId) => {
      if (!node?.id) return;
      const questions = (node.research_questions || []).map((q) =>
        q.id === rqId ? { ...q, card_id: null } : q
      );
      await patchNodeFields(node.id, { research_questions: questions });
      await refreshDag();
    },
    onClearAllLinks: async () => {
      const b = liveBoard();
      for (const card of b.cards || []) {
        if (!(card.depends_on || []).length) continue;
        await persistCard(b, card.id, { depends_on: [] }, { rerenderKanban: false });
      }
      await refreshDag();
    },
  };
}

function renderKanbanDagBoard(board, node) {
  const dagEl = document.getElementById("kanban-dag-view");
  if (!dagEl || !board) return;
  refreshKanbanDagView(dagEl, board, getKanbanDagContext(board, node));
  requestAnimationFrame(() => fitKanbanDagView());
  if (state.project) wireCardWorkersHover(dagEl, state.project);
}

function renderActiveKanbanView(board, node) {
  renderKanbanTagFilter(state.project, board);
  if (state.kanbanViewMode === "dag") {
    renderKanbanDagBoard(board, node);
    return;
  }
  renderKanbanBoard(board);
}

function initKanbanViewTabs() {
  const boardTab = document.getElementById("kanban-tab-board");
  const dagTab = document.getElementById("kanban-tab-dag");
  boardTab?.addEventListener("click", () => {
    setKanbanViewMode("board");
    const node = state.project?.nodes?.find((n) => n.id === state.kanbanNodeId);
    const board = node?.board_id ? state.project?.boards?.[node.board_id] : null;
    if (board && node) renderActiveKanbanView(board, node);
  });
  dagTab?.addEventListener("click", () => {
    setKanbanViewMode("dag");
    const node = state.project?.nodes?.find((n) => n.id === state.kanbanNodeId);
    const board = node?.board_id ? state.project?.boards?.[node.board_id] : null;
    if (board && node) renderActiveKanbanView(board, node);
  });
}

function getBoardCard(board, cardId) {
  return board.cards.find((c) => c.id === cardId);
}

function readCardTextFields(cardEl, card) {
  const titleEl = cardEl.querySelector(".card-title-display");
  const descEl = cardEl.querySelector(".card-desc-display");
  const descText = descEl?.classList.contains("is-empty")
    ? ""
    : descEl?.textContent.trim() || "";
  return {
    title: titleEl?.textContent.trim() || card.title,
    description: descText || card.description || "",
  };
}

function fillCardDisplay(cardEl, card) {
  const titleEl = cardEl.querySelector(".card-title-display");
  const descEl = cardEl.querySelector(".card-desc-display");
  renderInlineDisplay(titleEl, card.title, "");
  syncCardDescConclusionClass(descEl, card.column_id);
  renderCardDescDisplay(descEl, card.description, card.column_id);
  syncKanbanCardTodoProgress(cardEl, card);
}

async function persistCard(board, cardId, fields, opts = {}) {
  const { rerenderKanban = false, refreshMapStats = false } = opts;
  setStatus("Сохранение…");
  try {
    const card = getBoardCard(board, cardId);
    const payload = { ...fields };
    if (card) {
      if (payload.title === undefined) payload.title = card.title;
      if (payload.description === undefined) payload.description = card.description ?? "";
      if (payload.column_id === undefined) payload.column_id = card.column_id;
      if (payload.tags === undefined) payload.tags = card.tags || [];
      if (payload.depends_on === undefined) payload.depends_on = card.depends_on || [];
    }
    await KoiApi.patchCard(boardWriteProjectId(board), board.id, cardId, payload);
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    setStatus("Сохранено в project.md");
    if (rerenderKanban) {
      const node = state.project.nodes.find((n) => n.id === state.kanbanNodeId);
      if (node?.board_id) {
        renderActiveKanbanView(state.project.boards[node.board_id], node);
      }
    }
    const activityTouched = "description" in fields || "column_id" in fields;
    if (refreshMapStats || activityTouched) {
      refreshKanbanActivityForProject(state.project.id);
    }
    const b = state.project.boards[board.id];
    return getBoardCard(b, cardId) || null;
  } catch (err) {
    setStatus(err.message, true);
    return null;
  }
}

async function moveCardToColumn(board, cardId, targetColumnId, context = {}) {
  const card = board.cards.find((c) => c.id === cardId);
  if (!card || card.column_id === targetColumnId) return;
  const cardEl = document
    .querySelector(`.kanban-card[data-card-id="${cardId}"]`);
  const text = cardEl ? readCardTextFields(cardEl, card) : card;
  if (context.project) state.project = context.project;
  if (context.node) state.kanbanNodeId = context.node.id;
  await persistCard(
    board,
    cardId,
    {
      title: text.title,
      description: text.description,
      column_id: targetColumnId,
      tags: card.tags || [],
    },
    { rerenderKanban: true, refreshMapStats: true }
  );
}

function setupKanbanDragDrop(boardEl, board, context = {}) {
  const clearDragOver = () => {
    boardEl.querySelectorAll(".kanban-col-body.drag-over").forEach((el) => {
      el.classList.remove("drag-over");
    });
  };

  boardEl.querySelectorAll(".kanban-card").forEach((cardEl) => {
    const handle = cardEl.querySelector(".card-drag-handle");
    if (!handle) return;

    handle.addEventListener("dragstart", (e) => {
      cardEl.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("application/x-koi-card", cardEl.dataset.cardId);
      e.dataTransfer.setData("text/plain", cardEl.dataset.cardId);
    });

    handle.addEventListener("dragend", () => {
      cardEl.classList.remove("dragging");
      clearDragOver();
    });
  });

  boardEl.querySelectorAll(".kanban-col-body").forEach((colBody) => {
    colBody.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      clearDragOver();
      colBody.classList.add("drag-over");
    });

    colBody.addEventListener("dragleave", (e) => {
      if (!colBody.contains(e.relatedTarget)) {
        colBody.classList.remove("drag-over");
      }
    });

    colBody.addEventListener("drop", async (e) => {
      e.preventDefault();
      colBody.classList.remove("drag-over");
      const columnId = colBody.closest(".kanban-col")?.dataset.col;
      const cardId =
        e.dataTransfer.getData("application/x-koi-card") ||
        e.dataTransfer.getData("text/plain");
      if (!cardId || !columnId) return;
      await moveCardToColumn(board, cardId, columnId, context);
    });
  });
}

function bindKanbanCardInline(cardEl, board, card) {
  const cardId = card.id;
  const titleDisplay = cardEl.querySelector(".card-title-display");
  const titleInput = cardEl.querySelector(".card-title-input");
  const descDisplay = cardEl.querySelector(".card-desc-display");
  const descInput = cardEl.querySelector(".card-desc-input");

  const currentBoard = () => state.project.boards[board.id] || board;
  const getCard = () => getBoardCard(currentBoard(), cardId) || card;

  fillCardDisplay(cardEl, getCard());

  const saveFields = async (fields) => {
    const c = getCard();
    const updated = await persistCard(
      board,
      cardId,
      {
        title: fields.title ?? c.title,
        description: fields.description ?? c.description ?? "",
        column_id: fields.column_id ?? c.column_id,
      },
      { rerenderKanban: false, refreshMapStats: false }
    );
    return updated;
  };

  wireInlineEdit({
    display: titleDisplay,
    input: titleInput,
    getValue: () => getCard().title,
    setDisplay: (v) => renderInlineDisplay(titleDisplay, v, ""),
    onCommit: async (title) => {
      const c = getCard();
      const updated = await saveFields({
        title,
        description: c.description ?? "",
        column_id: c.column_id,
      });
      if (updated) void refreshReportFilenameIfOpen(cardId);
      return updated?.title ?? null;
    },
  });

  wireInlineEdit({
    display: descDisplay,
    input: descInput,
    getValue: () => getCard().description ?? "",
    setDisplay: (v) => {
      const c = getCard();
      syncCardDescConclusionClass(descDisplay, c.column_id);
      renderCardDescDisplay(descDisplay, v, c.column_id);
    },
    onCommit: async (description) => {
      const c = getCard();
      const updated = await saveFields({
        title: c.title,
        description,
        column_id: c.column_id,
      });
      if (updated) syncKanbanCardTodoProgress(cardEl, updated);
      return updated?.description ?? null;
    },
  });
}

async function copyCardReportPath(card, board) {
  if (!state.project) return;
  try {
    const data = await KoiApi.getCardReportPath(
      boardWriteProjectId(board),
      board.id,
      card.id
    );
    const path = data.repo_path || data.koi_path || data.relative_path;
    await navigator.clipboard.writeText(path);
  } catch {
    /* silent — no status hint for copy */
  }
}

function bindKanbanCardEvents(boardEl, board, context = {}) {
  if (isHubMode()) {
    boardEl.querySelectorAll(".kanban-card").forEach((cardEl) => {
      const cardId = cardEl.dataset.cardId;
      cardEl.querySelector(".card-expand-report")?.addEventListener("click", (e) => {
        e.stopPropagation();
        if (context.project) state.project = context.project;
        if (context.node) state.kanbanNodeId = context.node.id;
        const c =
          getBoardCard(state.project.boards[board.id] || board, cardId) ||
          board.cards.find((item) => item.id === cardId);
        void openCardReport(c, board);
      });
    });
    return;
  }
  boardEl.querySelectorAll(".kanban-card").forEach((cardEl) => {
    const cardId = cardEl.dataset.cardId;
    const card = board.cards.find((c) => c.id === cardId);
    if (!card) return;

    bindKanbanCardInline(cardEl, board, card);

    bindCardTagsContainer(
      cardEl.querySelector(".card-tags"),
      board,
      () => getBoardCard(state.project.boards[board.id] || board, cardId) || card,
      { rerenderKanban: true }
    );

    cardEl.querySelector(".card-copy-path")?.addEventListener("click", (e) => {
      e.stopPropagation();
      const c =
        getBoardCard(state.project.boards[board.id] || board, cardId) || card;
      void copyCardReportPath(c, board);
    });

    cardEl.querySelector(".card-expand-report")?.addEventListener("click", (e) => {
      e.stopPropagation();
      if (context.project) state.project = context.project;
      if (context.node) state.kanbanNodeId = context.node.id;
      const c =
        getBoardCard(state.project.boards[board.id] || board, cardId) || card;
      void openCardReport(c, board);
    });

    cardEl.querySelector(".card-delete")?.addEventListener("click", async () => {
      if (state.reportCardId === cardId) closeCardReport();
      if (!confirm("Удалить карточку?")) return;
      setStatus("Удаление…");
      try {
        await KoiApi.deleteCard(boardWriteProjectId(board), board.id, cardId);
        state.project = await reloadProjectView();
        syncLabProject(state.project);
        setStatus("Сохранено в project.md");
        const node = state.project.nodes.find((n) => n.id === state.kanbanNodeId);
        if (node?.board_id) renderKanbanBoard(state.project.boards[node.board_id]);
        if (state.kanbanNodeId) refreshKanbanBelowForNode(state.kanbanNodeId);
        refreshMapKanbansForProject(state.project.id);
      } catch (err) {
        setStatus(err.message, true);
      }
    });
  });

  setupKanbanDragDrop(boardEl, board, context);
}

const CARD_TAG_NAME_RE = /^[a-zA-Z0-9_-]+$/;

function cardTagHue(tag) {
  let hash = 0;
  const s = String(tag || "").toLowerCase();
  for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  return hash % 360;
}

function cardTagHueStyle(tag) {
  return `--tag-h:${cardTagHue(tag)}`;
}

function isKanbanModalOpen() {
  return !document.getElementById("kanban-modal")?.classList.contains("hidden");
}

function normalizeCardTagName(raw) {
  return validateCardTagName(raw).tag;
}

function validateCardTagName(raw) {
  const t = String(raw || "").trim();
  if (!t) {
    return { tag: null, error: "Введите название тега" };
  }
  if (!CARD_TAG_NAME_RE.test(t)) {
    return {
      tag: null,
      error: "Недопустимый формат: только латиница, цифры, дефис и подчёркивание (например gpu, sft_v2)",
    };
  }
  return { tag: t, error: null };
}

function setCardTagPopoverError(pop, message) {
  if (!pop) return;
  let el = pop.querySelector(".card-tag-popover-error");
  const input = pop.querySelector(".card-tag-popover-input");
  if (!message) {
    el?.remove();
    input?.classList.remove("is-invalid");
    return;
  }
  if (!el) {
    el = document.createElement("p");
    el.className = "card-tag-popover-error";
    el.setAttribute("role", "alert");
    pop.querySelector(".card-tag-popover-new")?.after(el);
  }
  el.textContent = message;
  input?.classList.add("is-invalid");
  input?.focus();
}

function collectCardTagVocabulary(add, tags) {
  (tags || []).forEach((tag) => {
    const norm = normalizeCardTagName(tag);
    if (!norm) return;
    const key = norm.toLowerCase();
    if (!add.seen.has(key)) add.seen.set(key, norm);
  });
}

function boardCardTagVocabulary(board) {
  const seen = new Map();
  const add = { seen };
  (board?.cards || []).forEach((card) => collectCardTagVocabulary(add, card.tags));
  return [...seen.values()].sort((a, b) => a.localeCompare(b, "ru"));
}

/** Tags on this board plus project-level suggestions (not other boards). */
function boardCardTagSuggestions(board, project) {
  const seen = new Map();
  const add = { seen };
  (board?.cards || []).forEach((card) => collectCardTagVocabulary(add, card.tags));
  (project?.card_tags || []).forEach((tag) => collectCardTagVocabulary(add, [tag]));
  return [...seen.values()].sort((a, b) => a.localeCompare(b, "ru"));
}

const KANBAN_TAG_FILTER_KEY = "koi-kanban-tag-filter-disabled";

function kanbanTagFilterStorageKey(projectId, boardId) {
  return `${KANBAN_TAG_FILTER_KEY}:${projectId || ""}:${boardId || ""}`;
}

function loadKanbanDisabledTagFilters(projectId, boardId) {
  try {
    const raw = localStorage.getItem(kanbanTagFilterStorageKey(projectId, boardId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.map((t) => String(t).toLowerCase()) : [];
  } catch {
    return [];
  }
}

function saveKanbanDisabledTagFilters(projectId, boardId, disabled) {
  try {
    localStorage.setItem(
      kanbanTagFilterStorageKey(projectId, boardId),
      JSON.stringify(disabled.map((t) => String(t).toLowerCase()))
    );
  } catch {
    /* ignore quota */
  }
}

function reconcileKanbanDisabledTagFilters(board, project = state.project) {
  const vocab = boardCardTagSuggestions(board, project);
  const allowed = new Set(vocab.map((t) => t.toLowerCase()));
  const disabled = (state.kanbanDisabledTagFilters || []).filter((t) => allowed.has(t));
  if (disabled.length !== (state.kanbanDisabledTagFilters || []).length) {
    state.kanbanDisabledTagFilters = disabled;
    if (state.project?.id && board?.id) {
      saveKanbanDisabledTagFilters(state.project.id, board.id, disabled);
    }
  }
  return disabled;
}

function cardMatchesKanbanTagFilter(card, disabledFilters) {
  if (!disabledFilters?.length) return true;
  const cardTags = (card.tags || []).map((t) => String(t).toLowerCase());
  return !disabledFilters.some((f) => cardTags.includes(f));
}

function kanbanTagFilterChipHtml(tag, isEnabled) {
  const activeClass = isEnabled ? " is-active" : "";
  const pressed = isEnabled ? "true" : "false";
  return `<button type="button" class="kanban-tag-filter-chip card-tag--hue${activeClass}" style="${cardTagHueStyle(tag)}" data-tag="${escapeHtml(tag)}" aria-pressed="${pressed}" title="${escapeHtml(tag)} — ${isEnabled ? "скрыть карточки с тегом" : "показать карточки с тегом"}">
    <span class="kanban-tag-filter-dot" aria-hidden="true"></span>
    <span class="kanban-tag-filter-label">${escapeHtml(tag)}</span>
  </button>`;
}

function renderKanbanTagFilter(project, board) {
  const el = document.getElementById("kanban-tag-filter");
  if (!el) return;

  const tags = boardCardTagSuggestions(board, project);
  if (!tags.length) {
    el.classList.add("hidden");
    el.innerHTML = "";
    return;
  }

  const disabled = reconcileKanbanDisabledTagFilters(board);
  const chips = tags
    .map((t) => kanbanTagFilterChipHtml(t, !disabled.includes(t.toLowerCase())))
    .join("");
  const clearBtn =
    disabled.length > 0
      ? `<button type="button" class="kanban-tag-filter-clear" title="Включить все теги">Сбросить</button>`
      : "";

  el.classList.remove("hidden");
  el.innerHTML = `
    <div class="kanban-tag-filter-row">
      <span class="kanban-tag-filter-title">Теги</span>
      <div class="kanban-tag-filter-chips" role="group" aria-label="Фильтр по тегам">${chips}</div>
      ${clearBtn}
    </div>`;

  bindKanbanTagFilter(project, board);
}

function bindKanbanTagFilter(project, board) {
  const el = document.getElementById("kanban-tag-filter");
  if (!el) return;

  el.querySelectorAll(".kanban-tag-filter-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tag = btn.dataset.tag;
      if (!tag) return;
      const key = tag.toLowerCase();
      const disabled = [...(state.kanbanDisabledTagFilters || [])];
      const idx = disabled.indexOf(key);
      if (idx >= 0) disabled.splice(idx, 1);
      else disabled.push(key);
      state.kanbanDisabledTagFilters = disabled;
      if (project?.id && board?.id) saveKanbanDisabledTagFilters(project.id, board.id, disabled);
      rerenderKanbanAfterTagFilter(board);
    });
  });

  el.querySelector(".kanban-tag-filter-clear")?.addEventListener("click", () => {
    state.kanbanDisabledTagFilters = [];
    if (project?.id && board?.id) saveKanbanDisabledTagFilters(project.id, board.id, []);
    rerenderKanbanAfterTagFilter(board);
  });
}

function rerenderKanbanAfterTagFilter(board) {
  const node = state.project?.nodes?.find((n) => n.id === state.kanbanNodeId);
  renderKanbanTagFilter(state.project, board);
  if (state.kanbanViewMode === "dag") {
    renderKanbanDagBoard(board, node);
    return;
  }
  renderKanbanBoard(board);
}

function cardTagsEqual(a, b) {
  const norm = (arr) => [...(arr || [])].map((t) => t.toLowerCase()).sort();
  const aa = norm(a);
  const bb = norm(b);
  return aa.length === bb.length && aa.every((v, i) => v === bb[i]);
}

function cardTagsRowHtml(tags, { kanban = false, dag = false } = {}) {
  const list = tags || [];
  if (dag) {
    const maxVisible = 3;
    const visible = list.slice(0, maxVisible);
    const hidden = list.slice(maxVisible);
    const chips = visible
      .map(
        (t) =>
          `<span class="card-tag-kanban card-tag-kanban--readonly card-tag--hue" style="${cardTagHueStyle(t)}" title="${escapeHtml(t)}">
            <span class="card-tag-kanban-dot" aria-hidden="true"></span>
            <span class="card-tag-kanban-label">${escapeHtml(t)}</span>
          </span>`
      )
      .join("");
    const overflowHtml =
      hidden.length > 0
        ? `<span class="card-tag-kanban-overflow" title="${escapeHtml(hidden.join(", "))}">+${hidden.length}</span>`
        : "";
    return list.length
      ? `<div class="card-tags card-tags--kanban card-tags--dag-readonly">${chips}${overflowHtml}</div>`
      : "";
  }
  if (kanban) {
    const maxVisible = 2;
    const visible = list.slice(0, maxVisible);
    const hidden = list.slice(maxVisible);
    const chips = visible
      .map(
        (t) =>
          `<button type="button" class="card-tag-kanban card-tag--hue" style="${cardTagHueStyle(t)}" data-tag="${escapeHtml(t)}" title="${escapeHtml(t)} — изменить теги">
            <span class="card-tag-kanban-dot" aria-hidden="true"></span>
            <span class="card-tag-kanban-label">${escapeHtml(t)}</span>
          </button>`
      )
      .join("");
    const overflowHtml =
      hidden.length > 0
        ? `<span class="card-tag-kanban-overflow" title="${escapeHtml(hidden.join(", "))}">+${hidden.length}</span>`
        : "";
    const addBtn =
      '<button type="button" class="card-tag-add card-tag-add--kanban" title="Добавить тег" aria-label="Добавить тег">+</button>';
    return `<div class="card-tags card-tags--kanban">${chips}${overflowHtml}${addBtn}</div>`;
  }
  const chips = list
    .map(
      (t) =>
        `<span class="card-tag-chip card-tag--hue" style="${cardTagHueStyle(t)}" data-tag="${escapeHtml(t)}" title="Клик по названию — изменить теги">
        <span class="card-tag-chip-label">${escapeHtml(t)}</span><span class="card-tag-chip-x" title="Снять">×</span>
      </span>`
    )
    .join("");
  const addBtn =
    '<button type="button" class="card-tag-add" title="Добавить тег" aria-label="Добавить тег">+</button>';
  return `<div class="card-tags">${chips}${addBtn}</div>`;
}

let cardTagPopoverState = null;

function closeCardTagPopover() {
  document.getElementById("card-tag-popover")?.remove();
  cardTagPopoverState = null;
  document.removeEventListener("keydown", onCardTagPopoverKeydown, true);
  document.removeEventListener("click", onCardTagPopoverOutside, true);
}

function onCardTagPopoverKeydown(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    void commitCardTagPopover(false);
  }
}

function onCardTagPopoverOutside(e) {
  const pop = document.getElementById("card-tag-popover");
  if (!pop || !cardTagPopoverState) return;
  if (pop.contains(e.target)) return;
  if (cardTagPopoverState.anchorEl?.contains(e.target)) return;
  void commitCardTagPopover(true);
}

function positionCardTagPopover(pop, anchorEl) {
  const rect = anchorEl.getBoundingClientRect();
  pop.style.left = `${Math.max(8, rect.left)}px`;
  pop.style.top = `${rect.bottom + 6}px`;
  requestAnimationFrame(() => {
    const popRect = pop.getBoundingClientRect();
    let left = rect.left;
    let top = rect.bottom + 6;
    if (left + popRect.width > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - popRect.width - 8);
    }
    if (top + popRect.height > window.innerHeight - 8) {
      top = Math.max(8, rect.top - popRect.height - 6);
    }
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
  });
}

function renderCardTagPopoverContent(pop, vocabulary, selectedTags) {
  const selectedLower = new Set(selectedTags.map((t) => t.toLowerCase()));
  const selectedHtml = selectedTags.length
    ? selectedTags
        .map(
          (t) =>
            `<button type="button" class="card-tag-popover-chip is-selected card-tag--hue" style="${cardTagHueStyle(t)}" data-tag="${escapeHtml(t)}" title="Снять с карточки">
              <span class="card-tag-popover-chip-label">${escapeHtml(t)}</span>
              <span class="card-tag-popover-chip-x" aria-hidden="true">×</span>
            </button>`
        )
        .join("")
    : '<span class="card-tag-popover-empty">Тегов нет — выберите ниже или создайте новый</span>';

  const optionsHtml = vocabulary.length
    ? vocabulary
        .map((t) => {
          const active = selectedLower.has(t.toLowerCase()) ? " is-active" : "";
          return `<button type="button" class="card-tag-popover-option card-tag--hue${active}" style="${cardTagHueStyle(t)}" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</button>`;
        })
        .join("")
    : '<span class="card-tag-popover-empty">Создайте первый тег ниже</span>';

  pop.innerHTML = `
    <div class="card-tag-popover-section">
      <p class="card-tag-popover-label">На карточке <span class="card-tag-popover-label-hint">клик × — снять</span></p>
      <div class="card-tag-popover-selected">${selectedHtml}</div>
    </div>
    <div class="card-tag-popover-section">
      <p class="card-tag-popover-label">Теги проекта <span class="card-tag-popover-label-hint">клик — добавить или снять</span></p>
      <div class="card-tag-popover-options">${optionsHtml}</div>
    </div>
    <div class="card-tag-popover-new">
      <input type="text" class="card-tag-popover-input" placeholder="Новый тег" maxlength="32" />
      <button type="button" class="btn btn-small card-tag-popover-add">Добавить</button>
    </div>
    <p class="card-tag-popover-hint">Латиница, цифры, дефис и подчёркивание — например gpu, ablation_v2</p>
    <div class="card-tag-popover-actions">
      <button type="button" class="btn btn-small card-tag-popover-done">Готово</button>
    </div>
  `;
}

function toggleCardTagInPopover(tag, pop) {
  if (!cardTagPopoverState) return;
  const norm = normalizeCardTagName(tag);
  if (!norm) return;
  const lower = norm.toLowerCase();
  let selected = [...cardTagPopoverState.selectedTags];
  const idx = selected.findIndex((t) => t.toLowerCase() === lower);
  if (idx >= 0) {
    selected.splice(idx, 1);
  } else {
    selected.push(norm);
  }
  cardTagPopoverState.selectedTags = selected;
  if (!cardTagPopoverState.vocabulary.some((t) => t.toLowerCase() === lower)) {
    cardTagPopoverState.vocabulary = [...cardTagPopoverState.vocabulary, norm].sort(
      (a, b) => a.localeCompare(b, "ru")
    );
  }
  renderCardTagPopoverContent(pop, cardTagPopoverState.vocabulary, selected);
  bindCardTagPopoverEvents(pop);
}

function bindCardTagPopoverEvents(pop) {
  pop.querySelectorAll(".card-tag-popover-option, .card-tag-popover-chip.is-selected").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleCardTagInPopover(btn.dataset.tag, pop);
    });
  });

  const input = pop.querySelector(".card-tag-popover-input");
  const addBtn = pop.querySelector(".card-tag-popover-add");
  const addNew = () => {
    const { tag, error } = validateCardTagName(input?.value || "");
    if (error) {
      setCardTagPopoverError(pop, error);
      return;
    }
    setCardTagPopoverError(pop, null);
    if (!cardTagPopoverState.selectedTags.some((t) => t.toLowerCase() === tag.toLowerCase())) {
      cardTagPopoverState.selectedTags = [...cardTagPopoverState.selectedTags, tag];
    }
    if (!cardTagPopoverState.vocabulary.some((t) => t.toLowerCase() === tag.toLowerCase())) {
      cardTagPopoverState.vocabulary = [...cardTagPopoverState.vocabulary, tag].sort(
        (a, b) => a.localeCompare(b, "ru")
      );
    }
    if (input) input.value = "";
    renderCardTagPopoverContent(pop, cardTagPopoverState.vocabulary, cardTagPopoverState.selectedTags);
    bindCardTagPopoverEvents(pop);
    pop.querySelector(".card-tag-popover-input")?.focus();
  };
  addBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    addNew();
  });
  input?.addEventListener("input", () => setCardTagPopoverError(pop, null));
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      addNew();
    }
  });
  pop.querySelector(".card-tag-popover-done")?.addEventListener("click", (e) => {
    e.stopPropagation();
    void commitCardTagPopover(true);
  });
}

async function removeCardTag(board, cardId, tagToRemove, { rerenderKanban = false, onUpdated = null } = {}) {
  const card = getBoardCard(board, cardId);
  if (!card) return null;
  const nextTags = (card.tags || []).filter(
    (t) => t.toLowerCase() !== String(tagToRemove || "").toLowerCase()
  );
  if (nextTags.length === (card.tags || []).length) return card;
  const updated = await persistCard(
    board,
    cardId,
    { tags: nextTags },
    { rerenderKanban, refreshMapStats: false }
  );
  if (updated && onUpdated) onUpdated(updated);
  return updated;
}

async function commitCardTagPopover(shouldSave) {
  const st = cardTagPopoverState;
  if (!st) return;
  const { board, cardId, selectedTags, originalTags, onUpdated, rerenderKanban } = st;
  closeCardTagPopover();
  if (!shouldSave || cardTagsEqual(selectedTags, originalTags)) return;
  const updated = await persistCard(
    board,
    cardId,
    { tags: selectedTags },
    { rerenderKanban: rerenderKanban ?? false, refreshMapStats: false }
  );
  if (updated && onUpdated) onUpdated(updated);
}

function openCardTagPopover(anchorEl, { card, board, rerenderKanban = false, onUpdated = null }) {
  if (!anchorEl || !card || !board) return;
  closeCardTagPopover();
  const vocabulary = boardCardTagSuggestions(board, state.project);
  const selectedTags = [...(card.tags || [])];
  cardTagPopoverState = {
    board,
    cardId: card.id,
    selectedTags,
    originalTags: [...selectedTags],
    vocabulary,
    anchorEl,
    rerenderKanban,
    onUpdated,
  };

  const pop = document.createElement("div");
  pop.id = "card-tag-popover";
  pop.className = "card-tag-popover";
  pop.setAttribute("role", "dialog");
  pop.addEventListener("click", (e) => e.stopPropagation());
  renderCardTagPopoverContent(pop, vocabulary, selectedTags);
  bindCardTagPopoverEvents(pop);
  document.body.appendChild(pop);
  positionCardTagPopover(pop, anchorEl);

  document.addEventListener("keydown", onCardTagPopoverKeydown, true);
  setTimeout(() => {
    document.addEventListener("click", onCardTagPopoverOutside, true);
  }, 0);
}

function bindCardTagsContainer(container, board, getCard, { rerenderKanban = false, onUpdated = null } = {}) {
  if (!container) return;
  const resolveCard = () => (typeof getCard === "function" ? getCard() : getCard);

  container.querySelectorAll(".card-tag-chip, .card-tag-kanban").forEach((chip) => {
    chip.addEventListener("click", (e) => {
      e.stopPropagation();
      const card = resolveCard();
      if (!card) return;
      if (e.target.closest(".card-tag-chip-x")) {
        void removeCardTag(board, card.id, chip.dataset.tag, { rerenderKanban, onUpdated });
        return;
      }
      openCardTagPopover(chip, {
        card,
        board,
        rerenderKanban,
        onUpdated,
      });
    });
  });

  container.querySelectorAll(".card-tag-add").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const card = resolveCard();
      if (!card) return;
      openCardTagPopover(btn, {
        card,
        board,
        rerenderKanban,
        onUpdated,
      });
    });
  });
}

function renderCardTagsInto(container, tags, { kanban = false } = {}) {
  if (!container) return;
  container.innerHTML = cardTagsRowHtml(tags, { kanban });
}

function renderCardReportTags(card) {
  const el = document.getElementById("card-report-tags");
  if (!el) return;
  renderCardTagsInto(el, card?.tags || []);
  const board = state.project?.boards?.[state.reportBoardId];
  if (!board) return;
  bindCardTagsContainer(
    el,
    board,
    () => getBoardCard(state.project.boards[state.reportBoardId], state.reportCardId),
    {
      rerenderKanban: isKanbanModalOpen(),
      onUpdated: (updated) => renderCardReportTags(updated),
    }
  );
}

function mergedSubtasks(...sources) {
  const open = [];
  const done = [];
  const seen = new Set();
  for (const src of sources) {
    const part = subtasksFromDescription(src);
    for (const t of part.done) {
      if (seen.has(t)) continue;
      seen.add(t);
      done.push(t);
    }
    for (const t of part.open) {
      if (seen.has(t)) continue;
      seen.add(t);
      open.push(t);
    }
  }
  return { open, done };
}

function cardHasSubtasks(description, reportContent = "") {
  const { open, done } = mergedSubtasks(description, reportContent);
  return open.length + done.length > 0;
}

function syncCardDescTodoOnlyState(descEl, description, reportContent = "") {
  if (!descEl) return;
  const prose = cardDescriptionProse(description);
  const todoOnly = !prose && cardHasSubtasks(description, reportContent);
  descEl.classList.toggle("has-todo-only", todoOnly);
  descEl.classList.toggle("is-empty", !prose && !todoOnly);
}

function cardTodoProgressHtml(description, reportContent = "") {
  const { open, done } = mergedSubtasks(description, reportContent);
  const total = open.length + done.length;
  if (!total) return "";
  const donePct = Math.max(0, Math.min(100, Math.round((done.length / total) * 100)));
  const current = open[0] || "";
  const currentHtml = current
    ? `<p class="kanban-card-todo-current" title="${escapeHtml(current)}">${escapeHtml(current.length > 56 ? `${current.slice(0, 55)}…` : current)}</p>`
    : `<p class="kanban-card-todo-current kanban-card-todo-current--done">Все подзадачи выполнены</p>`;
  return `<div class="kanban-card-todo">
    <div class="kanban-card-todo-head">
      <span class="kanban-card-todo-label">Подзадачи</span>
      <span class="kanban-card-todo-meta">${done.length}/${total}</span>
    </div>
    <div class="kanban-card-todo-progress" role="progressbar" aria-valuenow="${done.length}" aria-valuemin="0" aria-valuemax="${total}" aria-label="${done.length} из ${total} подзадач выполнено">
      <div class="kanban-card-todo-fill" style="width:${donePct}%"></div>
    </div>
    ${currentHtml}
  </div>`;
}

function applyKanbanCardTodoProgress(cardEl, card, reportContent = "") {
  if (!cardEl || !card) return;
  const existing = cardEl.querySelector(".kanban-card-todo");
  const html =
    card.column_id === "running" ? cardTodoProgressHtml(card.description, reportContent) : "";
  if (!html) {
    existing?.remove();
    return;
  }
  if (existing) {
    existing.outerHTML = html;
    return;
  }
  const footer = cardEl.querySelector(".kanban-card-footer");
  footer?.insertAdjacentHTML("beforebegin", html);
}

function syncKanbanCardTodoProgress(cardEl, card, reportContent = "") {
  const cached = cardEl?.dataset?.reportTodoSource || "";
  applyKanbanCardTodoProgress(cardEl, card, reportContent || cached);
}

async function hydrateKanbanCardTodoFromReports(boardEl, board, project, liveCtx = null) {
  if (!boardEl || !board) return;
  const projectId = boardWriteProjectId(board);
  const running = (board.cards || []).filter((c) => c.column_id === "running");
  let addedLiveBtn = false;
  await Promise.all(
    running.map(async (card) => {
      const cardEl = boardEl.querySelector(`.kanban-card[data-card-id="${card.id}"]`);
      if (!cardEl) return;
      let reportContent = cardEl.dataset.reportTodoSource || "";
      const needsTodoFromReport = !cardHasSubtasks(card.description);
      const needsLiveFromReport =
        !cardHasLiveHints(card.description) && !cardEl.querySelector(".card-live-inspect");
      if (needsTodoFromReport || needsLiveFromReport) {
        try {
          const data = await KoiApi.getCardReport(projectId, board.id, card.id);
          reportContent = data.content || "";
          if (reportContent) {
            cardEl.dataset.reportTodoSource = reportContent;
            cardEl.dataset.reportLiveSource = reportContent;
          }
        } catch {
          /* no report yet */
        }
      }
      applyKanbanCardTodoProgress(cardEl, card, reportContent);
      const descEl = cardEl.querySelector(".card-desc-display");
      if (descEl) syncCardDescTodoOnlyState(descEl, card.description, reportContent);
      if (syncKanbanCardLiveInspect(cardEl, card, reportContent)) addedLiveBtn = true;
    })
  );
  if (addedLiveBtn && liveCtx) {
    bindLiveInspectButtons(boardEl, liveCtx, cardLiveUi);
  }
  const pid = boardWriteProjectId(board) || project?.id;
  if (pid) {
    void ensureRunningAuthors(pid).then(() => applyRunningCardAuthorTitles(boardEl, pid));
  }
  const workersProject =
    project ||
    state.lab?.projectsById?.[pid] ||
    (state.project?.id === pid ? state.project : null) ||
    state.project;
  if (workersProject) wireCardWorkersHover(boardEl, workersProject);
}

function kanbanCardLiveInspectBtnHtml(cardId) {
  return `<button type="button" class="card-live-inspect" data-card-id="${escapeHtml(cardId)}" title="Live монитор" aria-label="Live монитор">
              <svg class="card-live-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2"/></svg>
            </button>`;
}

function syncKanbanCardLiveInspect(cardEl, card, reportContent = "") {
  if (!cardEl || card.column_id !== "running") return false;
  if (cardEl.querySelector(".card-live-inspect")) return false;
  const reportText =
    reportContent || cardEl.dataset.reportLiveSource || cardEl.dataset.reportTodoSource || "";
  if (!cardHasLiveHintsFromSources(card.description, reportText)) return false;

  const textBlock = cardEl.querySelector(".card-text-block");
  const titleDisplay = textBlock?.querySelector(":scope > .card-title-display");
  const titleInput = textBlock?.querySelector(":scope > .card-title-input");
  if (!textBlock || !titleDisplay || textBlock.querySelector(".kanban-card-title-row")) return false;

  const row = document.createElement("div");
  row.className = "kanban-card-title-row";
  row.insertAdjacentHTML("afterbegin", kanbanCardLiveInspectBtnHtml(card.id));
  row.appendChild(titleDisplay);
  if (titleInput) row.appendChild(titleInput);
  textBlock.insertBefore(row, textBlock.firstChild);
  cardEl.classList.add("has-live");
  return true;
}

function kanbanCardHtml(c, col, variant = "modal") {
  const displayDesc = cardDescriptionForDisplay(c.description, col.id);
  const descEmpty = !displayDesc.trim() && !cardHasSubtasks(c.description);
  const descTodoOnly = !displayDesc.trim() && cardHasSubtasks(c.description);
  const descConclusion = isKanbanConclusionColumn(col.id) ? " card-desc-conclusion" : "";
  const descPlaceholder = cardDescPlaceholder(col.id);
  const map = variant === "map" || isHubMode();
  const deleteBtn = map
    ? ""
    : `<button type="button" class="card-delete" title="Удалить" aria-label="Удалить карточку">×</button>`;
  const copyBtn = map
    ? ""
    : `<button type="button" class="card-copy-path card-action-btn" title="Скопировать путь к файлу отчёта" aria-label="Скопировать путь к файлу отчёта">
              <svg class="card-action-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" fill="none" stroke="currentColor" stroke-width="2"/><path fill="none" stroke="currentColor" stroke-width="2" d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>`;
  const liveBtn =
    col.id === "running" && !map && cardHasLiveHints(c.description)
      ? kanbanCardLiveInspectBtnHtml(c.id)
      : "";
  const accentStyle = c.tags?.[0] ? cardTagHueStyle(c.tags[0]) : "";
  const hasTags = (c.tags || []).length > 0;
  const todoProgress =
    col.id === "running" && cardHasSubtasks(c.description)
      ? cardTodoProgressHtml(c.description)
      : "";
  const gripIcon = `<svg class="card-drag-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="7" r="1.35" fill="currentColor"/><circle cx="15" cy="7" r="1.35" fill="currentColor"/><circle cx="9" cy="12" r="1.35" fill="currentColor"/><circle cx="15" cy="12" r="1.35" fill="currentColor"/><circle cx="9" cy="17" r="1.35" fill="currentColor"/><circle cx="15" cy="17" r="1.35" fill="currentColor"/></svg>`;
  const titleBlock = liveBtn
    ? `<div class="kanban-card-title-row">
                ${liveBtn}
                <p class="card-title-display inline-edit-text" title="Двойной клик — редактировать">${escapeHtml(c.title)}</p>
                <input type="text" class="card-title-input inline-edit-field hidden" />
              </div>`
    : `<p class="card-title-display inline-edit-text" title="Двойной клик — редактировать">${escapeHtml(c.title)}</p>
              <input type="text" class="card-title-input inline-edit-field hidden" />`;
  return `
        <div class="kanban-card${hasTags ? " has-tag-accent" : ""}${liveBtn ? " has-live" : ""}" data-card-id="${c.id}"${accentStyle ? ` style="${accentStyle}"` : ""}>
          <div class="kanban-card-head">
            <span class="card-drag-handle" draggable="true" title="Перетащить в другую колонку" aria-label="Перетащить">${gripIcon}</span>
            <div class="card-text-block">
              ${titleBlock}
              <p class="card-desc-display inline-edit-text card-desc-text${descEmpty ? " is-empty" : ""}${descTodoOnly ? " has-todo-only" : ""}${descConclusion}" data-placeholder="${escapeHtml(descPlaceholder)}">${escapeHtml(displayDesc)}</p>
              <textarea class="card-desc-input inline-edit-field hidden" rows="3"></textarea>
            </div>
            ${deleteBtn}
          </div>
          ${todoProgress}
          <div class="kanban-card-footer">
            ${cardTagsRowHtml(c.tags, { dag: isHubMode(), kanban: !isHubMode() })}
            <div class="kanban-card-actions">
              ${copyBtn}
              <button type="button" class="card-expand-report card-action-btn" title="Открыть отчёт" aria-label="Открыть отчёт">
                <svg class="card-action-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M15 3h6v6M10 14L21 3M21 14v7h-7"/></svg>
              </button>
            </div>
          </div>
        </div>`;
}

function kanbanBoardHtml(board, variant = "modal", { tagFilters = [] } = {}) {
  const filtering = tagFilters?.length > 0;
  return (board.columns || [])
    .map((col) => {
      const cards = board.cards.filter(
        (c) => c.column_id === col.id && cardMatchesKanbanTagFilter(c, tagFilters)
      );
      const totalInCol = board.cards.filter((c) => c.column_id === col.id).length;
      const hiddenByFilter = filtering ? totalInCol - cards.length : 0;
      const countHtml =
        hiddenByFilter > 0
          ? `<span class="col-count-inline">${cards.length}<span class="col-count-total">/${totalInCol}</span></span>`
          : `<span class="col-count-inline">${cards.length}</span>`;
      const cardsHtml = cards.map((c) => kanbanCardHtml(c, col, variant)).join("");
      const emptyHtml =
        filtering && totalInCol > 0
          ? '<span class="col-empty col-empty--filtered">Все карточки скрыты фильтром</span>'
          : '<span class="col-empty">Перетащите сюда</span>';
      return `
        <div class="kanban-col" data-col="${col.id}">
          <div class="kanban-col-head">
            <h3>
              <span class="col-title">${escapeHtml(col.title)}</span>
              ${countHtml}
            </h3>
            <button type="button" class="col-add-btn" title="Добавить карточку" aria-label="Добавить карточку в ${escapeHtml(col.title)}">+</button>
          </div>
          <div class="kanban-col-body">
            ${cardsHtml || emptyHtml}
          </div>
        </div>`;
    })
    .join("");
}

function renderKanbanBoardInto(boardEl, board, { variant = "modal", node = null, project = null, tagFilters = [] } = {}) {
  if (!boardEl || !board) return;
  boardEl.innerHTML = kanbanBoardHtml(board, variant, { tagFilters });
  const ctx = { variant, node, project: project || state.project };
  bindKanbanCardEvents(boardEl, board, ctx);
  bindKanbanColumnActions(boardEl, board, ctx);
  const proj = ctx.project;
  const running = (board.cards || []).filter((c) => c.column_id === "running");
  const liveCtx =
    proj?.id && board.id && running.length
      ? {
          projectId: proj.id,
          projectTitle: proj.title || proj.id,
          boardId: board.id,
          cards: running,
          card: running[0],
          methodTitle: node?.title || "",
        }
      : null;
  void hydrateKanbanCardTodoFromReports(boardEl, board, ctx.project, liveCtx);
  if (liveCtx && !isHubMode()) {
    bindLiveInspectButtons(boardEl, liveCtx, cardLiveUi);
  }
}

function renderKanbanBoard(board) {
  const project = state.project;
  const node = project?.nodes?.find((n) => n.id === state.kanbanNodeId) || null;
  const boardEl = document.getElementById("kanban-board");
  if (!boardEl) return;
  renderKanbanBoardInto(boardEl, board, {
    variant: "modal",
    tagFilters: state.kanbanDisabledTagFilters || [],
    node,
    project,
  });
}

function bindKanbanColumnActions(boardEl, board, context = {}) {
  if (isHubMode()) return;
  boardEl.querySelectorAll(".col-add-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const columnId = btn.closest(".kanban-col")?.dataset.col;
      if (!columnId) return;
      if (context.node && context.project) {
        state.project = context.project;
        state.kanbanNodeId = context.node.id;
      }
      void addCardToColumn(board, columnId, context);
    });
  });
}

async function addCardToColumn(board, columnId, context = {}) {
  if (!board?.id) {
    setStatus("Не удалось определить доску", true);
    return;
  }
  if (context.project) state.project = context.project;
  const node = context.node ||
    state.project?.nodes?.find((n) => n.id === state.kanbanNodeId);
  const writeProjectId = boardWriteProjectId(board);
  if (!writeProjectId) {
    setStatus("Не удалось определить проект для сохранения карточки", true);
    return;
  }
  const beforeIds = new Set((board.cards || []).map((c) => c.id));
  const project = context.project || state.project;
  setStatus("Добавление…");
  try {
    await KoiApi.addCard(writeProjectId, board.id, {
      title: "Новый эксперимент",
      column_id: columnId,
      description: "",
      tags: [],
    });
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    setStatus("Сохранено в project.md");
    const updatedBoard = getBoard(state.project, board.id);
    if (updatedBoard) renderKanbanBoard(updatedBoard);
    if (state.kanbanNodeId) refreshKanbanBelowForNode(state.kanbanNodeId);
    refreshMapKanbansForProject(state.project.id, node?.id);
    const newCard = updatedBoard?.cards?.find(
      (c) => c.column_id === columnId && !beforeIds.has(c.id)
    );
    if (newCard) {
      const titleDisplay = document.querySelector(
        `.kanban-card[data-card-id="${newCard.id}"] .card-title-display`
      );
      titleDisplay?.dispatchEvent(
        new MouseEvent("dblclick", { bubbles: true, cancelable: true })
      );
    }
  } catch (err) {
    setStatus(err.message, true);
  }
}

const PROJECTS_SIDEBAR_KEY = "koi-projects-sidebar";
const VIEW_MODE_KEY = "koi-view-mode";

const VIEW_MODES = {
  chief: {
    id: "chief",
    label: "Chief researcher",
    shortLabel: "Chief",
    hint: "На экране — вся лаборатория · колёсико — масштаб до карточек метода · перетаскивание — панорама",
  },
  teamlead: {
    id: "teamlead",
    label: "Team lead researcher",
    shortLabel: "Lead",
    hint: "На экране — программа выбранного проекта · список слева — полный",
  },
  researcher: {
    id: "researcher",
    label: "Researcher",
    shortLabel: "Focus",
    hint: "На экране — один проект · зум до карточек метода · двойной клик по методу — приблизить",
  },
};

state.view = {
  mode: "chief",
};

function renderProjectListButton(p, currentId) {
  const active = p.id === currentId;
  const compositeHint = p.composite_id
    ? ` title="composite: ${escapeHtml(p.composite_id)}"`
    : "";
  return (
    `<li class="project-list__item">` +
    `<button type="button" class="project-list__btn${active ? " is-active" : ""}"` +
    ` data-project-id="${escapeHtml(p.id)}"` +
    compositeHint +
    (active ? ' aria-current="true"' : "") +
    `>${escapeHtml(p.title)}</button>` +
    `</li>`
  );
}

function renderCompositeListButton(c, currentId) {
  const virtualId = `composite:${c.id}`;
  const active = currentId === virtualId;
  return (
    `<li class="project-list__item project-list__item--composite">` +
    `<button type="button" class="project-list__btn project-list__btn--composite${active ? " is-active" : ""}"` +
    ` data-composite-id="${escapeHtml(c.id)}"` +
    (active ? ' aria-current="true"' : "") +
    `><span class="project-list__composite-mark" aria-hidden="true">⎇</span> ${escapeHtml(c.title)}</button>` +
    `</li>`
  );
}

function renderProgramGroupHeader(group) {
  return (
    `<div class="program-group__header">` +
    `<div class="program-group__label" title="${escapeHtml(group.description || "")}">` +
    `${escapeHtml(group.title)}</div>` +
    `</div>`
  );
}

function renderProgramGroup(group, currentId) {
  const hiddenMemberIds = state.lab?.hiddenMemberIds || hiddenCompositeMemberIds({ groups: [group] });
  const projects = visibleProjectsForGroup(group, hiddenMemberIds);
  const composites = group.composites || [];
  return (
    `<li class="program-group">` +
    renderProgramGroupHeader(group) +
    `<ul class="project-list project-list--nested" role="list">` +
    (composites.length
      ? composites.map((c) => renderCompositeListButton(c, currentId)).join("")
      : "") +
    (projects.length
      ? projects.map((p) => renderProjectListButton(p, currentId)).join("")
      : !composites.length
        ? `<li class="program-group__empty">Нет проектов</li>`
        : "") +
    `</ul>` +
    `</li>`
  );
}

function isCompositeView() {
  return Boolean(state.project?.is_composite);
}

function compositeVirtualId(compositeId) {
  return `composite:${compositeId}`;
}

function resolvePreferredProjectId(requestedId, grouped, projectsById) {
  const memberToComposite = new Map();
  for (const g of grouped?.groups || []) {
    for (const c of g.composites || []) {
      for (const mid of c.member_ids || []) {
        memberToComposite.set(mid, compositeVirtualId(c.id));
      }
    }
  }

  if (requestedId && projectsById[requestedId]) {
    return memberToComposite.get(requestedId) || requestedId;
  }
  if (requestedId && memberToComposite.has(requestedId)) {
    const compositeId = memberToComposite.get(requestedId);
    if (projectsById[compositeId]) return compositeId;
  }

  for (const g of grouped?.groups || []) {
    for (const c of g.composites || []) {
      const virtualId = compositeVirtualId(c.id);
      if (projectsById[virtualId]) return virtualId;
    }
  }

  if (projectsById["ai-agents-embodied"]) return "ai-agents-embodied";

  const hidden = hiddenCompositeMemberIds(grouped);
  for (const id of Object.keys(projectsById || {})) {
    if (!hidden.has(id) && !isCompositeVirtualId(id)) return id;
  }
  return Object.keys(projectsById || {})[0] || null;
}

function isCompositeVirtualId(id) {
  return String(id || "").startsWith("composite:");
}

function compositeIdsFromGroup(group) {
  return new Set((group?.composites || []).map((c) => c.id));
}

function hiddenCompositeMemberIds(grouped) {
  const hidden = new Set();
  for (const g of grouped?.groups || []) {
    for (const c of g.composites || []) {
      for (const mid of c.member_ids || []) hidden.add(mid);
    }
  }
  return hidden;
}

function visibleProjectsForGroup(group, hiddenMemberIds) {
  return (group?.projects || []).filter((p) => !hiddenMemberIds.has(p.id));
}

function programLayoutItems(group, hiddenMemberIds) {
  const items = [];
  for (const c of group?.composites || []) {
    items.push({
      kind: "composite",
      id: compositeVirtualId(c.id),
      title: c.title || c.id,
    });
  }
  for (const meta of visibleProjectsForGroup(group, hiddenMemberIds)) {
    items.push({ kind: "project", id: meta.id, title: meta.title || meta.id });
  }
  return items;
}

function nodeWriteProjectId(node) {
  if (!node) return state.project?.id;
  return node.source_project_id || node.project_id || state.project?.id;
}

function boardWriteProjectId(board) {
  if (board?.source_project_id) return board.source_project_id;
  if (board?.owner_node_id) {
    const owner = state.project?.nodes?.find((n) => n.id === board.owner_node_id);
    const viaOwner = nodeWriteProjectId(owner);
    if (viaOwner && !isCompositeVirtualId(viaOwner)) return viaOwner;
  }
  const pid = state.project?.id;
  if (pid && !isCompositeVirtualId(pid)) return pid;
  return null;
}

function primaryMemberProjectId() {
  if (isCompositeView() && state.project?.members?.length) {
    return state.project.members[0].project_id;
  }
  return state.project?.id;
}

async function reloadProjectView() {
  if (isCompositeView() && state.project?.composite_id) {
    return KoiApi.getComposite(state.project.composite_id);
  }
  if (isCompositeVirtualId(state.project?.id)) {
    return KoiApi.getComposite(state.project.id.slice("composite:".length));
  }
  if (state.project?.id) {
    return KoiApi.getProject(state.project.id);
  }
  return null;
}

async function loadProjectList(activeId) {
  const ul = document.getElementById("project-list");
  const titleEl = document.getElementById("projects-sidebar-title");
  const currentId = activeId || state.project?.id;
  const list = [];

  let grouped = null;
  if (state.lab?.grouped) {
    grouped = state.lab.grouped;
  } else {
    try {
      grouped = await KoiApi.listProjectsGrouped();
    } catch (err) {
      console.warn("Grouped projects unavailable, falling back to flat list:", err.message);
    }
  }

  if (!grouped) {
    const flat = await KoiApi.listProjects();
    if (ul) {
      ul.innerHTML = renderProgramGroup(
        { id: "", title: "Проекты", description: "", projects: flat },
        currentId
      );
    }
    return flat;
  }

  if (titleEl && grouped.laboratory?.title) {
    titleEl.textContent = grouped.laboratory.title;
  }

  if (ul) {
    const parts = [];

    for (const group of grouped.groups || []) {
      const hidden = state.lab?.hiddenMemberIds || hiddenCompositeMemberIds(grouped);
      for (const c of group.composites || []) {
        list.push({ id: compositeVirtualId(c.id), title: c.title || c.id });
      }
      list.push(...visibleProjectsForGroup(group, hidden));
      parts.push(renderProgramGroup(group, currentId));
    }

    if (grouped.ungrouped?.length) {
      list.push(...grouped.ungrouped);
      parts.push(
        renderProgramGroup(
          {
            id: "",
            title: grouped.groups?.length ? "Без программы" : "Проекты",
            description: "",
            projects: grouped.ungrouped,
          },
          currentId
        )
      );
    }

    ul.innerHTML = parts.join("");
  }
  return list;
}

function setActiveProjectInList(id) {
  document.querySelectorAll(".project-list__btn").forEach((btn) => {
    const active =
      btn.dataset.projectId === id ||
      (id?.startsWith("composite:") && btn.dataset.compositeId === id.slice("composite:".length));
    btn.classList.toggle("is-active", active);
    if (active) btn.setAttribute("aria-current", "true");
    else btn.removeAttribute("aria-current");
  });
}

function setProjectsSidebarOpen(open) {
  const sidebar = document.getElementById("projects-sidebar");
  const toggle = document.getElementById("btn-projects-toggle");
  const workspace = document.getElementById("workspace");
  sidebar?.classList.toggle("is-open", open);
  workspace?.classList.toggle("is-projects-open", open);
  if (toggle) {
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Свернуть панель проектов" : "смотреть все проекты");
  }
}

const PROJECT_TAG_RE = /^[a-zA-Z][a-zA-Z0-9_-]*$/;

function validateProjectTag(tag) {
  const value = String(tag || "").trim();
  if (!value) return "Введите тег проекта";
  if (!PROJECT_TAG_RE.test(value)) {
    return "Тег: только латиница, цифры, _ и -; без пробелов; начинается с буквы";
  }
  return "";
}

function populateCreateProjectPrograms() {
  const select = document.getElementById("create-project-program-select");
  if (!select) return;
  const groups = state.lab?.grouped?.groups || [];
  const options = ['<option value="">— без программы —</option>'];
  for (const group of groups) {
    if (!group?.id) continue;
    options.push(
      `<option value="${escapeHtml(group.id)}">${escapeHtml(group.title || group.id)}</option>`
    );
  }
  select.innerHTML = options.join("");
}

function setCreateProjectProgramMode(mode) {
  const existing = mode === "existing";
  const select = document.getElementById("create-project-program-select");
  const newInput = document.getElementById("create-project-program-new");
  if (select) select.disabled = !existing;
  if (newInput) newInput.disabled = existing;
}

function openCreateProjectModal() {
  const form = document.getElementById("create-project-form");
  const errorEl = document.getElementById("create-project-error");
  const tagInput = document.getElementById("create-project-tag");
  form?.reset();
  if (errorEl) {
    errorEl.textContent = "";
    errorEl.classList.add("hidden");
  }
  tagInput?.classList.remove("field-invalid");
  populateCreateProjectPrograms();
  const existingRadio = form?.querySelector('input[name="program_mode"][value="existing"]');
  if (existingRadio instanceof HTMLInputElement) existingRadio.checked = true;
  setCreateProjectProgramMode("existing");
  showModal("create-project-modal");
  document.getElementById("create-project-title-input")?.focus();
}

async function submitCreateProjectForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const errorEl = document.getElementById("create-project-error");
  const tagInput = document.getElementById("create-project-tag");
  const title = form.title.value.trim();
  const description = form.description.value.trim();
  const tag = form.tag.value.trim();
  const programMode = form.program_mode.value;
  const tagError = validateProjectTag(tag);

  if (errorEl) {
    errorEl.textContent = "";
    errorEl.classList.add("hidden");
  }
  tagInput?.classList.remove("field-invalid");

  if (!title) {
    if (errorEl) {
      errorEl.textContent = "Введите название проекта";
      errorEl.classList.remove("hidden");
    }
    return;
  }
  if (tagError) {
    tagInput?.classList.add("field-invalid");
    if (errorEl) {
      errorEl.textContent = tagError;
      errorEl.classList.remove("hidden");
    }
    return;
  }

  let programId = null;
  let programTitle = null;
  if (programMode === "existing") {
    programId = form.program_id.value.trim() || null;
  } else {
    programTitle = form.program_title.value.trim();
    if (!programTitle) {
      if (errorEl) {
        errorEl.textContent = "Введите название новой программы";
        errorEl.classList.remove("hidden");
      }
      return;
    }
  }

  const submitBtn = document.getElementById("create-project-submit");
  if (submitBtn) submitBtn.disabled = true;
  setStatus("Создание проекта…");
  try {
    const p = await KoiApi.createProject({
      title,
      description,
      tag,
      programId,
      programTitle,
    });
    hideModal("create-project-modal");
    if (state.lab) {
      state.lab.projectsById[p.id] = p;
      state.lab.grouped = await KoiApi.listProjectsGrouped();
    }
    await loadProjectList(p.id);
    await switchProject(p.id);
    setProjectsSidebarOpen(true);
    setStatus("Проект создан");
  } catch (err) {
    if (errorEl) {
      errorEl.textContent = err.message || "Не удалось создать проект";
      errorEl.classList.remove("hidden");
    }
    setStatus(err.message || "Не удалось создать проект", true);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function initCreateProjectModal() {
  document.getElementById("btn-new-project")?.addEventListener("click", () => {
    openCreateProjectModal();
  });
  document.getElementById("create-project-form")?.addEventListener("submit", (e) => {
    void submitCreateProjectForm(e);
  });
  document.querySelectorAll('#create-project-form input[name="program_mode"]').forEach((el) => {
    el.addEventListener("change", () => {
      if (el instanceof HTMLInputElement && el.checked) {
        setCreateProjectProgramMode(el.value);
      }
    });
  });
  document.getElementById("create-project-tag")?.addEventListener("input", (e) => {
    const input = e.currentTarget;
    const hint = document.getElementById("create-project-tag-hint");
    const errorEl = document.getElementById("create-project-error");
    const err = validateProjectTag(input.value);
    input.classList.toggle("field-invalid", Boolean(err) && input.value.trim().length > 0);
    if (hint) {
      hint.textContent = err && input.value.trim()
        ? err
        : "Латиница, цифры, _ и -; без пробелов; с буквы.";
    }
    if (errorEl && !errorEl.textContent) {
      errorEl.classList.add("hidden");
    }
  });
}

function initProjectsSidebar() {
  const saved = localStorage.getItem(PROJECTS_SIDEBAR_KEY);
  setProjectsSidebarOpen(saved === "open");

  document.getElementById("btn-projects-toggle")?.addEventListener("click", () => {
    const open = !document.getElementById("projects-sidebar")?.classList.contains("is-open");
    setProjectsSidebarOpen(open);
    localStorage.setItem(PROJECTS_SIDEBAR_KEY, open ? "open" : "closed");
  });

  document.getElementById("project-list")?.addEventListener("click", (e) => {
    const compositeBtn = e.target.closest("[data-composite-id]");
    if (compositeBtn) {
      const compositeId = compositeBtn.dataset.compositeId;
      if (!compositeId) return;
      const virtualId = `composite:${compositeId}`;
      if (virtualId !== state.project?.id) void switchComposite(compositeId);
      else if (state.lab?.projectsById) void focusLabProject(virtualId, { animate: true });
      return;
    }
    const btn = e.target.closest(".project-list__btn");
    if (!btn) return;
    const id = btn.dataset.projectId;
    if (!id) return;
    if (id !== state.project?.id) void switchProject(id);
    else if (state.lab?.projectsById) void focusLabProject(id, { animate: true });
  });
}

async function switchComposite(compositeId) {
  const virtualId = compositeVirtualId(compositeId);
  setStatus("Загрузка…");
  try {
    if (state.lab?.projectsById) {
      await focusLabProject(virtualId, { animate: true, reload: true });
    } else {
      state.project = await KoiApi.getComposite(compositeId);
      setActiveProjectInList(virtualId);
      renderMindmap();
    }
    setStatus("");
    updatePaperReviewLink();
    updateAgentChatScope();
    void refreshAgentChat();
  } catch (err) {
    setStatus(err.message, true);
  }
}

async function switchProject(id) {
  setStatus("Загрузка…");
  try {
    if (state.lab?.projectsById) {
      await focusLabProject(id, { animate: true, reload: true });
    } else {
      state.project = await KoiApi.getProject(id);
      setActiveProjectInList(id);
      renderMindmap();
    }
    setStatus("");
    updatePaperReviewLink();
    updateAgentChatScope();
    void refreshAgentChat();
  } catch (err) {
    setStatus(err.message, true);
  }
}

async function closeReportModal() {
  await saveCardReport();
  closeCardReport();
}

let agentChatItems = [];
let agentChatPollTimer = null;
let lastAgentChatInboxMessage = "";
const AGENT_CHAT_POLL_MS = 5000;
let appSettings = {
  agent_chat_mode: "cursor_inbox",
  cursor_api_key_configured: false,
  cursor_api_key_masked: null,
  cursor_api_key_url: "https://cursor.com/dashboard/integrations",
  cursor_sdk_installed: false,
  agent_worker_running: false,
  chat_inbox_bootstrap_prompt: "",
  chat_inbox_configured: false,
  chat_inbox_watcher_running: false,
  inbox_bootstrap_prompt: "",
  inbox_loop_prompt: "",
  inbox_pending_command: "",
  inbox_configured: false,
  inbox_pending_counts: { agent_chat: 0, related_work: 0, paper: 0 },
  paper_inbox_bootstrap_prompt: "",
  paper_inbox_configured: false,
  paper_inbox_watcher_running: false,
};

function isApiAgentMode() {
  return appSettings.agent_chat_mode === "api";
}

function isInboxAgentMode() {
  return appSettings.agent_chat_mode === "cursor_inbox";
}

function isCursorIdeAgentMode() {
  return appSettings.agent_chat_mode === "cursor_ide";
}

async function copyInboxBootstrap(targetStatusEl) {
  const text =
    appSettings.chat_inbox_bootstrap_prompt ||
    appSettings.inbox_bootstrap_prompt ||
    "Загрузите настройки (обновите страницу) или выполните: python -m koi.agent_chat.inbox_cli bootstrap";
  try {
    await navigator.clipboard.writeText(text);
    if (targetStatusEl) {
      targetStatusEl.textContent = "Скопировано — вставьте в новый чат «ResearchOS Chat Inbox» в Cursor.";
      setTimeout(() => {
        if (targetStatusEl.textContent.startsWith("Скопировано")) targetStatusEl.textContent = "";
      }, 5000);
    }
    return true;
  } catch {
    if (targetStatusEl) targetStatusEl.textContent = "Не удалось скопировать — попробуйте ещё раз.";
    return false;
  }
}

function storeAgentChatInboxMessage(message) {
  lastAgentChatInboxMessage = String(message || "").trim();
}

function showAgentChatInboxPrompt(message) {
  const box = document.getElementById("agent-chat-inbox-prompt");
  if (!box) return;
  const trimmed = String(message || "").trim();
  if (!trimmed || !isInboxAgentMode()) {
    box.classList.add("hidden");
    lastAgentChatInboxMessage = "";
    return;
  }
  storeAgentChatInboxMessage(trimmed);
  box.classList.remove("hidden");
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function copyAgentChatInboxPrompt(statusEl) {
  const text = lastAgentChatInboxMessage;
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    if (statusEl) {
      statusEl.textContent = "Скопировано — вставьте в чат ResearchOS Chat Inbox.";
      setTimeout(() => {
        if (statusEl.textContent.startsWith("Скопировано")) statusEl.textContent = "";
      }, 5000);
    }
    return true;
  } catch {
    if (statusEl) statusEl.textContent = "Не удалось скопировать.";
    return false;
  }
}

const INBOX_HINT_DISMISSED_KEY = "koi_inbox_hint_dismissed";
const INBOX_CONFIGURED_KEY = "koi_chat_inbox_configured";

function isInboxHintDismissed() {
  try {
    return localStorage.getItem(INBOX_HINT_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

function isInboxConfigured() {
  return Boolean(appSettings.chat_inbox_configured);
}

function isChatInboxWatcherRunning() {
  return Boolean(appSettings.chat_inbox_watcher_running);
}

function isChatInboxOperational() {
  return isInboxConfigured() && isChatInboxWatcherRunning();
}

function ensureChatInboxBootstrapCached() {
  const bootstrap =
    appSettings.chat_inbox_bootstrap_prompt || appSettings.inbox_bootstrap_prompt || "";
  if (bootstrap && !lastAgentChatInboxMessage) {
    storeAgentChatInboxMessage(bootstrap);
  }
}

async function markInboxConfigured() {
  try {
    const data = await KoiApi.setInboxConfigured(true, "chat");
    appSettings = { ...appSettings, ...data, chat_inbox_configured: true, inbox_configured: true };
  } catch {
    appSettings.chat_inbox_configured = true;
    appSettings.inbox_configured = true;
  }
  try {
    localStorage.setItem(INBOX_CONFIGURED_KEY, "1");
    localStorage.setItem(INBOX_HINT_DISMISSED_KEY, "1");
  } catch {
    /* private mode */
  }
  updateAgentChatInboxNotice();
}

function dismissInboxHint() {
  try {
    localStorage.setItem(INBOX_HINT_DISMISSED_KEY, "1");
  } catch {
    /* private mode */
  }
  updateAgentChatInboxNotice();
}

function showInboxHint() {
  try {
    localStorage.removeItem(INBOX_HINT_DISMISSED_KEY);
  } catch {
    /* private mode */
  }
  const box = document.getElementById("agent-chat-inbox-notice");
  const showHint = document.getElementById("agent-chat-inbox-show-hint");
  if (box && isInboxAgentMode()) {
    ensureChatInboxBootstrapCached();
    box.classList.remove("hidden");
    showHint?.classList.add("hidden");
  }
}

function updateAgentChatInboxNotice() {
  const box = document.getElementById("agent-chat-inbox-notice");
  const showHint = document.getElementById("agent-chat-inbox-show-hint");
  const keyNotice = document.getElementById("agent-chat-key-notice");
  if (!box) return;

  if (!isInboxAgentMode()) {
    box.classList.add("hidden");
    showHint?.classList.add("hidden");
    return;
  }

  if (isChatInboxOperational()) {
    box.classList.add("hidden");
    showHint?.classList.remove("hidden");
    return;
  }

  ensureChatInboxBootstrapCached();

  const dismissed = isInboxHintDismissed() && isInboxConfigured();
  box.classList.toggle("hidden", dismissed);
  showHint?.classList.toggle("hidden", !dismissed);

  if (keyNotice) {
    keyNotice.classList.add("hidden");
    keyNotice.textContent = "";
  }

  const label = box.querySelector(".agent-chat-inbox-title");
  if (label) {
    label.textContent = isInboxConfigured()
      ? "Chat Inbox: watcher не запущен"
      : "Chat Inbox не настроен";
  }

  if (dismissed) return;

  const watcherEl = document.getElementById("agent-chat-inbox-watcher-status");
  if (watcherEl) {
    watcherEl.classList.remove("is-ok", "is-warn");
    if (isInboxConfigured()) {
      watcherEl.textContent =
        "Inbox отмечен, но watcher не запущен. Выполните ./scripts/koi-serve.sh start и loop в ResearchOS Chat Inbox.";
      watcherEl.classList.add("is-warn");
    } else {
      watcherEl.textContent =
        "Один раз: скопируйте сообщение → ResearchOS Chat Inbox → tail -f agent-chat-watch.log → «Inbox готов».";
    }
  }
}

function agentChatPendingLabel(item) {
  if (item?.status === "processing") return "";
  if (isApiAgentMode()) return "Агент обрабатывает…";
  if (isInboxAgentMode()) {
    if (!isInboxConfigured()) return "Отправлено — настройте Chat Inbox";
    if (!isChatInboxWatcherRunning()) return "Watcher не запущен — koi-serve.sh start";
    return "В очереди — ждём ResearchOS Chat Inbox…";
  }
  return "Ожидает агента в Cursor (hooks)…";
}

function agentChatDeliveryHtml(item) {
  const status = item?.status || "pending";
  if (status === "answered") return "";
  const read = status === "processing";
  const title = read ? "Прочитано агентом" : "Отправлено";
  return (
    `<span class="agent-chat-delivery" title="${title}" aria-label="${title}">` +
    `<span class="agent-chat-check is-sent" aria-hidden="true">✓</span>` +
    (read ? `<span class="agent-chat-check is-read" aria-hidden="true">✓</span>` : "") +
    `</span>`
  );
}

function agentChatTypingHtml() {
  return koiLoaderTypingHtml("agent");
}

function agentChatContext() {
  const project = state.project;
  if (!project) return { method_id: null, node_id: null, label: null };

  const methodId =
    state.kanbanNodeId ||
    state.questionsNodeId ||
    (() => {
      const n = project.nodes?.find((x) => x.id === state.activeNodeId);
      return n?.node_type === "method" ? n.id : null;
    })();

  const nodeId = state.activeNodeId || state.kanbanNodeId || state.questionsNodeId || null;
  let label = null;
  if (methodId) {
    const m = project.nodes?.find((x) => x.id === methodId);
    if (m) label = `Контекст: метод «${m.title}»`;
  } else if (nodeId) {
    const n = project.nodes?.find((x) => x.id === nodeId);
    if (n) label = `Контекст: ${TYPE_LABELS[n.node_type] || n.node_type} «${n.title}»`;
  }
  return { method_id: methodId || null, node_id: nodeId, label };
}

function formatAgentChatTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

function agentChatHasPending() {
  return agentChatItems.some((i) => i.status !== "answered");
}

const AGENT_CHAT_SCROLL_THRESHOLD = 64;

function agentChatLogNearBottom(log) {
  if (!log) return true;
  return log.scrollHeight - log.scrollTop - log.clientHeight <= AGENT_CHAT_SCROLL_THRESHOLD;
}

function renderAgentChatLog({ scrollToBottom = false } = {}) {
  const log = document.getElementById("agent-chat-log");
  if (!log) return;
  clearInlineLoaderHints(log);
  const stickToBottom = scrollToBottom || agentChatLogNearBottom(log);
  const prevScrollTop = log.scrollTop;
  const items = [...agentChatItems].reverse();
  if (!items.length) {
    log.innerHTML = '<p class="agent-chat-empty">Задайте вопрос по проекту — ответ появится здесь.</p>';
    return;
  }
  log.innerHTML = items
    .map((item) => {
      const status = item.status || "pending";
      const pending = status !== "answered";
      const isProcessing = status === "processing";
      const isWarning = item.answer_kind === "warning";
      const pendingLabel = agentChatPendingLabel(item);
      let answerHtml;
      if (isProcessing) {
        answerHtml = agentChatTypingHtml();
      } else if (pending) {
        answerHtml =
          `<div class="agent-chat-reply agent-chat-reply--pending" data-koi-loader-pool="agent">` +
          `<span class="agent-chat-typing-label">${escapeHtml(pendingLabel)}</span>` +
          `<span class="koi-loader__hint koi-loader__hint--inline"></span>` +
          `</div>`;
      } else {
        answerHtml = `<div class="agent-chat-reply${isWarning ? " agent-chat-reply--warning" : ""}">${formatAgentChatReply(item.answer || "")}</div>`;
      }
      return (
        `<article class="agent-chat-thread${pending ? " is-pending" : ""}${isProcessing ? " is-processing" : ""}" data-id="${escapeHtml(item.id)}">` +
        `<div class="agent-chat-q-row">` +
        `<p class="agent-chat-q">${escapeHtml(item.question)}</p>` +
        agentChatDeliveryHtml(item) +
        `<button type="button" class="btn btn-small btn-danger agent-chat-delete" title="Удалить" aria-label="Удалить вопрос">×</button>` +
        `</div>` +
        answerHtml +
        `<time>${escapeHtml(formatAgentChatTime(item.enqueued_at))}</time>` +
        `</article>`
      );
    })
    .join("");
  refreshInlineLoaderHints(log);
  if (stickToBottom) {
    log.scrollTop = log.scrollHeight;
  } else {
    log.scrollTop = prevScrollTop;
  }
}

async function refreshAgentChat({ scrollToBottom = false } = {}) {
  const pid = primaryMemberProjectId();
  if (!pid) return;
  try {
    const data = await KoiApi.listAgentChat(pid);
    agentChatItems = data.items || [];
    renderAgentChatLog({ scrollToBottom });
    syncAgentChatPolling();
  } catch {
    /* API may be restarting */
  }
}

function syncAgentChatPolling() {
  const panel = document.getElementById("agent-chat-panel");
  const panelOpen = panel && !panel.classList.contains("hidden");
  const shouldPoll = panelOpen || agentChatHasPending();
  if (shouldPoll && !agentChatPollTimer) {
    agentChatPollTimer = setInterval(() => {
      void refreshAgentChat();
    }, AGENT_CHAT_POLL_MS);
  } else if (!shouldPoll && agentChatPollTimer) {
    clearInterval(agentChatPollTimer);
    agentChatPollTimer = null;
  }
}

function updateAgentChatScope() {
  const el = document.getElementById("agent-chat-scope");
  if (!el) return;
  const { label } = agentChatContext();
  if (label) {
    el.textContent = label;
    el.hidden = false;
  } else {
    el.textContent = "";
    el.hidden = true;
  }
}

function toggleAgentChatPanel(open) {
  const panel = document.getElementById("agent-chat-panel");
  const workspace = document.getElementById("workspace");
  if (!panel) return;
  const show = open ?? panel.classList.contains("hidden");
  panel.classList.toggle("hidden", !show);
  workspace?.classList.toggle("is-chat-open", show);
  document.getElementById("btn-agent-chat")?.classList.toggle("hidden", show);
  if (show) {
    void refreshAppSettings().then(() => {
      updateAgentChatInboxNotice();
      updateAgentChatKeyNotice();
    });
    updateAgentChatScope();
    void refreshAgentChat({ scrollToBottom: true });
    document.getElementById("agent-chat-input")?.focus();
  } else {
    syncAgentChatPolling();
  }
  scheduleMindmapRender();
}

async function submitAgentQuestion(e) {
  e.preventDefault();
  if (!state.project?.id) {
    setStatus("Сначала выберите проект", true);
    return;
  }
  const input = document.getElementById("agent-chat-input");
  const text = input?.value?.trim();
  if (!text) return;

  const { method_id, node_id } = agentChatContext();
  const btn = document.getElementById("btn-agent-chat-send");
  if (btn) btn.disabled = true;
  setStatus("Отправка вопроса агенту…");

  try {
    const res = await KoiApi.sendAgentQuestion({
      project_id: primaryMemberProjectId(),
      question: text,
      method_id: method_id || undefined,
      node_id: node_id || undefined,
    });
    if (res?.item) {
      agentChatItems = [res.item, ...agentChatItems.filter((i) => i.id !== res.item.id)];
      renderAgentChatLog({ scrollToBottom: true });
    }
    if (isInboxAgentMode() && res?.inbox_message && res?.item?.status !== "answered" && !isInboxConfigured()) {
      showAgentChatInboxPrompt(res.inbox_message);
    } else if (isInboxAgentMode() && !isInboxConfigured()) {
      const bootstrap =
        appSettings.chat_inbox_bootstrap_prompt || appSettings.inbox_bootstrap_prompt || "";
      if (bootstrap) showAgentChatInboxPrompt(bootstrap);
      else showAgentChatInboxPrompt("");
    } else {
      showAgentChatInboxPrompt("");
    }
    input.value = "";
    void refreshAgentChat();
    syncAgentChatPolling();
    setStatus("Вопрос отправлен — ждём ответ в панели");
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function updateAgentChatKeyNotice() {
  const el = document.getElementById("agent-chat-key-notice");
  if (!el) return;
  if (isInboxAgentMode()) {
    updateAgentChatInboxNotice();
    return;
  }
  document.getElementById("agent-chat-inbox-notice")?.classList.add("hidden");
  if (isApiAgentMode()) {
    if (appSettings.cursor_api_key_configured) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    const url = appSettings.cursor_api_key_url || "https://cursor.com/dashboard/integrations";
    el.classList.remove("hidden");
    el.innerHTML =
      'Режим API: укажите <button type="button" class="agent-chat-key-link" id="agent-chat-open-settings">ключ Cursor API</button> в настройках. ' +
      `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Как получить ключ</a>`;
    return;
  }
  el.classList.remove("hidden");
  el.innerHTML =
    'Режим hooks: откройте чат агента в IDE — вопросы подхватятся при старте/stop сессии. ' +
    '<button type="button" class="agent-chat-key-link" id="agent-chat-open-settings">Настройки</button>';
}

async function refreshAppSettings() {
  try {
    appSettings = await KoiApi.getSettings();
    appSettings.chat_inbox_configured = Boolean(appSettings.chat_inbox_configured);
    appSettings.chat_inbox_watcher_running = Boolean(appSettings.chat_inbox_watcher_running);
    appSettings.paper_inbox_configured = Boolean(appSettings.paper_inbox_configured);
    appSettings.paper_inbox_watcher_running = Boolean(appSettings.paper_inbox_watcher_running);
    try {
      if (appSettings.chat_inbox_configured) {
        localStorage.setItem(INBOX_CONFIGURED_KEY, "1");
      } else {
        localStorage.removeItem(INBOX_CONFIGURED_KEY);
        localStorage.removeItem(INBOX_HINT_DISMISSED_KEY);
      }
    } catch {
      /* private mode */
    }
    updateAgentChatKeyNotice();
    updateAgentChatInboxNotice();
    updatePaperInboxNotice();
    return appSettings;
  } catch {
    return appSettings;
  }
}

function hideSettingsSaveNotice() {
  const notice = document.getElementById("settings-save-notice");
  if (!notice) return;
  notice.classList.add("hidden");
  notice.classList.remove("is-success", "is-error");
  notice.textContent = "";
}

function showSettingsSaveNotice(message, { error = false } = {}) {
  const notice = document.getElementById("settings-save-notice");
  if (!notice) return;
  notice.textContent = message;
  notice.classList.remove("hidden", "is-success", "is-error");
  notice.classList.add(error ? "is-error" : "is-success");
}

function selectedAgentChatMode() {
  const checked = document.querySelector('input[name="agent_chat_mode"]:checked');
  return checked?.value || appSettings.agent_chat_mode || "cursor_ide";
}

function syncSettingsModeBlocksVisibility(mode = selectedAgentChatMode()) {
  document.getElementById("settings-api-block")?.classList.toggle("hidden", mode !== "api");
  document.getElementById("settings-inbox-block")?.classList.toggle("hidden", mode !== "cursor_inbox");
}

function applySettingsToForm(data = appSettings) {
  const mode = data.agent_chat_mode || "cursor_ide";
  document.querySelectorAll('input[name="agent_chat_mode"]').forEach((el) => {
    el.checked = el.value === mode;
  });
  syncSettingsModeBlocksVisibility(mode);

  const status = document.getElementById("settings-key-status");
  const link = document.getElementById("settings-key-link");
  const sdkHint = document.getElementById("settings-sdk-hint");
  const input = document.getElementById("settings-cursor-key");
  if (link && data.cursor_api_key_url) {
    link.href = data.cursor_api_key_url;
  }
  if (status) {
    if (mode === "api") {
      status.textContent = data.cursor_api_key_configured
        ? `Ключ сохранён (${data.cursor_api_key_masked || "••••"}). Оставьте поле пустым, чтобы не менять.`
        : "Укажите ключ — без него фоновый агент не запустится.";
      status.classList.toggle("is-ok", Boolean(data.cursor_api_key_configured));
    } else if (mode === "cursor_inbox") {
      status.textContent = isChatInboxOperational()
        ? "Inbox работает — watcher пишет в agent-chat-watch.log."
        : isInboxConfigured()
          ? "Inbox отмечен, но watcher не запущен — ./scripts/koi-serve.sh start."
          : "Скопируйте bootstrap и отправьте в чат «ResearchOS Chat Inbox» в Cursor.";
      status.classList.toggle("is-ok", isChatInboxOperational());
    } else {
      status.textContent = data.agent_worker_running
        ? "Фоновый воркер ещё запущен — перезапустите KOI после смены режима."
        : "Ключ API не нужен — вопросы через hooks.";
      status.classList.toggle("is-ok", !data.agent_worker_running);
    }
  }
  if (sdkHint) {
    if (mode === "api" && data.cursor_sdk_installed === false) {
      sdkHint.classList.remove("hidden");
      sdkHint.textContent =
        "Пакет cursor-sdk не установлен в .venv — после сохранения ключа выполните: pip install cursor-sdk";
    } else {
      sdkHint.classList.add("hidden");
      sdkHint.textContent = "";
    }
  }
  if (input && !input.matches(":focus")) {
    input.value = "";
    input.placeholder = data.cursor_api_key_configured ? "Новый ключ (необязательно)" : "crsr_…";
  }
  document
    .getElementById("btn-settings-clear-key")
    ?.classList.toggle("hidden", mode !== "api" || !data.cursor_api_key_configured);
}

async function openSettingsModal() {
  await refreshAppSettings();
  hideSettingsSaveNotice();
  applySettingsToForm();
  updateThemeControl(getTheme());
  showModal("settings-modal");
  document.getElementById("settings-cursor-key")?.focus();
}

async function saveSettings(e) {
  e.preventDefault();
  const input = document.getElementById("settings-cursor-key");
  const btn = document.getElementById("btn-settings-save");
  const mode = selectedAgentChatMode();
  const key = input?.value?.trim() || "";
  if (mode === "api" && !key && !appSettings.cursor_api_key_configured) {
    showSettingsSaveNotice("В режиме API нужен ключ Cursor", { error: true });
    setStatus("Введите ключ Cursor API", true);
    return;
  }
  hideSettingsSaveNotice();
  if (btn) btn.disabled = true;
  setStatus("Сохранение настроек…");
  try {
    const body = { agent_chat_mode: mode };
    if (key) body.cursor_api_key = key;
    const data = await KoiApi.saveAgentChatSettings(body);
    appSettings = data;
    applySettingsToForm(data);
    updateAgentChatKeyNotice();
    renderAgentChatLog();
    updateAgentChatInboxNotice();
    const msg =
      mode === "api"
        ? "Режим API сохранён" + (key ? ", ключ обновлён" : "")
        : mode === "cursor_inbox"
          ? "Режим Inbox-чат сохранён — откройте панель «Спросить агента» для инструкции"
          : "Режим hooks сохранён";
    showSettingsSaveNotice(msg);
    setStatus(msg);
  } catch (err) {
    showSettingsSaveNotice(err.message, { error: true });
    setStatus(err.message, true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function clearCursorApiKey() {
  const btn = document.getElementById("btn-settings-clear-key");
  if (btn) btn.disabled = true;
  setStatus("Удаление ключа…");
  try {
    const data = await KoiApi.saveAgentChatSettings({ cursor_api_key: "" });
    appSettings = data;
    applySettingsToForm(data);
    updateAgentChatKeyNotice();
    showSettingsSaveNotice("Ключ удалён");
    setStatus("Ключ Cursor API удалён");
  } catch (err) {
    showSettingsSaveNotice(err.message, { error: true });
    setStatus(err.message, true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

let syncStatus = null;
let syncPollTimer = null;
let rqDiscoveryPollTimer = null;
const SYNC_POLL_MS = 30 * 60 * 1000;
const RQ_DISCOVERY_POLL_MS = 4000;
const RQ_DISCOVERY_AUTO_MS = 60 * 1000;
const PROJECT_DISCOVERY_POLL_MS = 3000;
let projectDiscoveryRevision = 0;
let projectDiscoveryPollTimer = null;
const RQ_DISCOVERY_FADE_MS = 550;
const RQ_DISCOVERY_STAGGER_MS = 180;
const RQ_DISCOVERY_SEEN_KEY = "koi-rq-discoveries-seen";
const RQ_DISCOVERY_READ_KEY = "koi-rq-discoveries-read";

let rqDiscoveryFeed = [];
let rqBellPanelOpen = false;

function loadSeenRqDiscoveryKeys() {
  try {
    const raw = localStorage.getItem(RQ_DISCOVERY_SEEN_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

function rememberSeenRqDiscoveryKeys(keys) {
  if (!keys.length) return;
  const seen = loadSeenRqDiscoveryKeys();
  for (const key of keys) seen.add(key);
  const trimmed = [...seen].slice(-200);
  localStorage.setItem(RQ_DISCOVERY_SEEN_KEY, JSON.stringify(trimmed));
}

function loadReadRqDiscoveryKeys() {
  try {
    const raw = localStorage.getItem(RQ_DISCOVERY_READ_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

function rememberReadRqDiscoveryKeys(keys) {
  if (!keys.length) return;
  const read = loadReadRqDiscoveryKeys();
  for (const key of keys) read.add(key);
  const trimmed = [...read].slice(-200);
  localStorage.setItem(RQ_DISCOVERY_READ_KEY, JSON.stringify(trimmed));
}

function filterUnseenRqDiscoveries(items) {
  const seen = loadSeenRqDiscoveryKeys();
  return (items || []).filter((d) => d?.key && !seen.has(d.key));
}

function rqDiscoveryUnreadCount() {
  const read = loadReadRqDiscoveryKeys();
  return rqDiscoveryFeed.filter((d) => d?.key && !read.has(d.key)).length;
}

function formatRqDiscoveryWhen(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "";
  const diff = Date.now() - dt.getTime();
  if (diff < 60_000) return "только что";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} мин назад`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} ч назад`;
  return dt.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function updateRqBellBadge() {
  const badge = document.getElementById("rq-bell-badge");
  const btn = document.getElementById("btn-rq-bell");
  if (!badge || !btn) return;
  const unread = rqDiscoveryUnreadCount();
  if (unread > 0) {
    badge.textContent = unread > 9 ? "+9" : `+${unread}`;
    badge.classList.remove("hidden");
    btn.classList.add("has-unread");
    btn.title = `Открытия: ${unread} новых`;
  } else {
    badge.classList.add("hidden");
    btn.classList.remove("has-unread");
    btn.title = "Открытия — новые ответы на исследовательские вопросы";
  }
}

function renderRqBellList() {
  const list = document.getElementById("rq-bell-list");
  const empty = document.getElementById("rq-bell-empty");
  if (!list || !empty) return;

  const read = loadReadRqDiscoveryKeys();
  if (!rqDiscoveryFeed.length) {
    list.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  list.innerHTML = rqDiscoveryFeed
    .map((d) => {
      const author = escapeHtml((d.author || "коллега").trim());
      const unread = d.key && !read.has(d.key);
      const when = formatRqDiscoveryWhen(d.discovered_at);
      const project = d.project_id
        ? `<span class="rq-bell-item__project">${escapeHtml(d.project_id)}</span>`
        : "";
      return `
        <li class="rq-bell-item${unread ? " is-unread" : ""}" data-key="${escapeHtml(d.key || "")}">
          <div class="rq-bell-item__head">
            <span class="rq-bell-item__author">${author}</span>
            ${project}
            ${when ? `<time class="rq-bell-item__when">${escapeHtml(when)}</time>` : ""}
          </div>
          <p class="rq-bell-item__title">ответил(а) на исследовательский вопрос</p>
          <p class="rq-bell-item__q">${escapeHtml(d.question || "")}</p>
          <p class="rq-bell-item__a">${escapeHtml(d.answer || "")}</p>
        </li>`;
    })
    .join("");
}

function setRqBellPanelOpen(open) {
  const panel = document.getElementById("rq-bell-panel");
  const btn = document.getElementById("btn-rq-bell");
  rqBellPanelOpen = open;
  if (!panel || !btn) return;
  panel.classList.toggle("hidden", !open);
  panel.hidden = !open;
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) {
    const unreadKeys = rqDiscoveryFeed
      .filter((d) => d?.key && !loadReadRqDiscoveryKeys().has(d.key))
      .map((d) => d.key);
    rememberReadRqDiscoveryKeys(unreadKeys);
    updateRqBellBadge();
    renderRqBellList();
  }
}

function showRqDiscoveryToast(discovery) {
  const stack = document.getElementById("rq-discovery-stack");
  if (!stack || !discovery) return;

  const author = (discovery.author || "коллега").trim();
  const el = document.createElement("article");
  el.className = "rq-discovery-toast";
  el.setAttribute("role", "status");
  el.innerHTML = `
    <button type="button" class="rq-discovery-toast__close" aria-label="Закрыть">×</button>
    <p class="rq-discovery-toast__badge">Новое открытие</p>
    <p class="rq-discovery-toast__title">${escapeHtml(author)} ответил(а) на исследовательский вопрос!</p>
    <p class="rq-discovery-toast__q">${escapeHtml(discovery.question || "")}</p>
    <p class="rq-discovery-toast__a">${escapeHtml(discovery.answer || "")}</p>
  `;
  stack.appendChild(el);

  let gone = false;
  const leave = () => {
    if (gone) return;
    gone = true;
    clearTimeout(autoTimer);
    el.classList.add("is-leaving");
    setTimeout(() => el.remove(), RQ_DISCOVERY_FADE_MS);
  };
  const autoTimer = setTimeout(leave, RQ_DISCOVERY_AUTO_MS);
  el.querySelector(".rq-discovery-toast__close")?.addEventListener("click", leave);
}

function mergeRqDiscoveryFeed(items) {
  if (!items?.length) return;
  const known = new Set(rqDiscoveryFeed.map((d) => d.key));
  for (const item of items) {
    if (!item?.key || known.has(item.key)) continue;
    rqDiscoveryFeed.unshift(item);
    known.add(item.key);
  }
  rqDiscoveryFeed.sort(
    (a, b) =>
      new Date(b.discovered_at || 0).getTime() - new Date(a.discovered_at || 0).getTime()
  );
  rqDiscoveryFeed = rqDiscoveryFeed.slice(0, 80);
  updateRqBellBadge();
  if (rqBellPanelOpen) renderRqBellList();
}

async function loadRqDiscoveryFeed() {
  try {
    const data = await KoiApi.getRqDiscoveriesFeed();
    if (data?.items?.length) mergeRqDiscoveryFeed(data.items);
    else updateRqBellBadge();
  } catch {
    updateRqBellBadge();
  }
}

async function presentRqDiscoveries(items) {
  if (!items?.length) return;
  const normalized = items.map((d) => ({
    ...d,
    discovered_at: d.discovered_at || new Date().toISOString(),
  }));
  mergeRqDiscoveryFeed(normalized);

  const fresh = filterUnseenRqDiscoveries(items);
  if (fresh.length) {
    rememberSeenRqDiscoveryKeys(fresh.map((d) => d.key));
    fresh.forEach((d, i) => {
      setTimeout(() => showRqDiscoveryToast(d), i * RQ_DISCOVERY_STAGGER_MS);
    });
  }
  try {
    await KoiApi.ackRqDiscoveries();
  } catch {
    /* server ack is best-effort */
  }
}

async function refreshProjectsForDiscoveries(discoveries) {
  const ids = new Set(discoveries.map((d) => d.project_id).filter(Boolean));
  if (!ids.size) return;
  const currentId = state.project?.id;
  if (!currentId || !ids.has(currentId)) return;
  try {
    if (state.lab?.projectsById) {
      await focusLabProject(currentId, { reload: true });
    } else if (isCompositeVirtualId(currentId)) {
      state.project = await KoiApi.getComposite(currentId.slice("composite:".length));
      renderMindmap();
    } else {
      state.project = await KoiApi.getProject(currentId);
      renderMindmap();
    }
    const openKanban = state.project?.nodes?.find((n) => n.id === state.kanbanNodeId);
    if (openKanban?.board_id && state.project.boards) {
      renderKanbanBoard(state.project.boards[openKanban.board_id]);
    }
    const mqNode = state.project?.nodes?.find((n) => n.id === state.questionsNodeId);
    if (mqNode) renderMethodQuestionsBody(mqNode);
  } catch (err) {
    console.warn("Project refresh after RQ discovery failed:", err.message);
  }
}

async function checkPendingRqDiscoveries() {
  try {
    const data = await KoiApi.getRqDiscoveries();
    const discoveries = data?.discoveries || [];
    if (!discoveries.length) return;
    await presentRqDiscoveries(discoveries);
    await refreshProjectsForDiscoveries(discoveries);
  } catch {
    /* git/sync may be unavailable */
  }
}

function initRqBell() {
  const btn = document.getElementById("btn-rq-bell");
  const wrap = document.querySelector(".rq-bell-wrap");
  if (!btn || !wrap) return;

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    setRqBellPanelOpen(!rqBellPanelOpen);
  });

  document.addEventListener("click", (e) => {
    if (!rqBellPanelOpen) return;
    if (wrap.contains(e.target)) return;
    setRqBellPanelOpen(false);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && rqBellPanelOpen) setRqBellPanelOpen(false);
  });

  void loadRqDiscoveryFeed();
  renderRqBellList();
  updateRqBellBadge();
}

function applySyncStatus(data) {
  syncStatus = data;
  const btn = document.getElementById("btn-sync");
  const badge = document.getElementById("sync-behind-badge");
  if (!btn) return;

  if (!data?.ok) {
    btn.classList.remove("has-updates");
    setSyncError(data?.error || "Git недоступен");
    if (badge) badge.classList.add("hidden");
    return;
  }

  const behind = Number(data.behind) || 0;
  btn.classList.toggle("has-updates", behind > 0);
  if (!btn.classList.contains("has-error")) {
    btn.title =
      behind > 0
        ? `Синхронизировать: на origin ${behind} новых коммитов`
        : "Синхронизировать с git";
  }
  if (badge) {
    if (behind > 0) {
      badge.textContent = behind > 9 ? "9+" : String(behind);
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }
}

async function refreshSyncStatus() {
  try {
    const data = await KoiApi.getSyncStatus();
    applySyncStatus(data);
    return data;
  } catch {
    applySyncStatus({ ok: false, error: "Не удалось проверить git" });
    return null;
  }
}

async function runProjectSync() {
  const btn = document.getElementById("btn-sync");
  if (btn?.classList.contains("is-syncing")) return;

  btn?.classList.add("is-syncing");
  setSyncError(null);
  try {
    const result = await KoiApi.pullSync();
    applySyncStatus(result);

    if (result.action === "pulled") {
      const currentId = state.project?.id;
      await loadProjectList(currentId);
      if (currentId) await switchProject(currentId);
      if (result.rq_discoveries?.length) {
        await presentRqDiscoveries(result.rq_discoveries);
      } else {
        await loadRqDiscoveryFeed();
      }
      setSyncError(null);
      return;
    }

    if (result.action === "none") {
      setSyncError(null);
      return;
    }

    const isError =
      result.action === "failed" ||
      result.action === "blocked" ||
      result.needs_console;
    if (isError) {
      setSyncError(result.message || "Синхронизация не выполнена");
    }
  } catch (err) {
    setSyncError(err.message);
  } finally {
    btn?.classList.remove("is-syncing");
    void refreshSyncStatus();
  }
}

function initSync() {
  initRqBell();
  document.getElementById("btn-sync")?.addEventListener("click", () => {
    void runProjectSync();
  });
  void refreshSyncStatus();
  void checkPendingRqDiscoveries();
  if (syncPollTimer) clearInterval(syncPollTimer);
  syncPollTimer = setInterval(() => {
    void refreshSyncStatus();
  }, SYNC_POLL_MS);
  if (rqDiscoveryPollTimer) clearInterval(rqDiscoveryPollTimer);
  rqDiscoveryPollTimer = setInterval(() => {
    void checkPendingRqDiscoveries();
  }, RQ_DISCOVERY_POLL_MS);
}

async function refreshProjectDiscovery() {
  try {
    const data = await KoiApi.getProjectDiscovery(projectDiscoveryRevision);
    if (!data?.ok) return;
    projectDiscoveryRevision = data.revision ?? projectDiscoveryRevision;
    const changes = data.changes || {};
    const added = changes.added || [];
    const removed = changes.removed || [];
    const changed = changes.changed || [];
    if (!added.length && !removed.length && !changed.length) return;

    const currentId = state.project?.id;
    await loadLab();
    if (currentId) {
      await loadProjectList(currentId);
      if (state.lab?.projectsById?.[currentId]) {
        state.project = state.lab.projectsById[currentId];
        setActiveProjectInList(currentId);
      }
    } else {
      await loadProjectList();
    }

    if (added.length || removed.length) {
      renderLabMindmap({ fitLab: getViewMode() === "chief" });
    } else {
      for (const item of changed) {
        refreshKanbanActivityForProject(item.id);
      }
    }

    for (const item of added) {
      const title = (item.title || item.id || "проект").trim();
      setStatus(`Новый проект на диске: ${title}`);
    }
  } catch (err) {
    console.warn("Project discovery poll failed:", err.message);
  }
}

function initProjectDiscoveryPoll() {
  void refreshProjectDiscovery();
  if (projectDiscoveryPollTimer) clearInterval(projectDiscoveryPollTimer);
  projectDiscoveryPollTimer = setInterval(() => {
    void refreshProjectDiscovery();
  }, PROJECT_DISCOVERY_POLL_MS);
}

function initSettings() {
  document.getElementById("btn-settings")?.addEventListener("click", () => {
    void openSettingsModal();
  });
  document.getElementById("settings-form")?.addEventListener("submit", (e) => {
    void saveSettings(e);
  });
  document.querySelectorAll('input[name="agent_chat_mode"]').forEach((el) => {
    el.addEventListener("change", () => {
      syncSettingsModeBlocksVisibility();
      applySettingsToForm({ ...appSettings, agent_chat_mode: selectedAgentChatMode() });
    });
  });
  document.getElementById("btn-dismiss-inbox-hint")?.addEventListener("click", () => {
    dismissInboxHint();
  });
  document.getElementById("btn-show-inbox-hint")?.addEventListener("click", () => {
    showInboxHint();
  });
  document.getElementById("btn-copy-inbox-bootstrap")?.addEventListener("click", () => {
    void copyInboxBootstrap(document.getElementById("agent-chat-inbox-copy-status"));
  });
  document.getElementById("btn-mark-inbox-configured")?.addEventListener("click", () => {
    void markInboxConfigured().then(() => {
      showAgentChatInboxPrompt("");
      const status = document.getElementById("agent-chat-inbox-copy-status");
      if (status) status.textContent = "Inbox отмечен как настроенный.";
    });
  });
  document.getElementById("agent-chat-inbox-prompt-copy")?.addEventListener("click", async () => {
    const status = document.getElementById("agent-chat-inbox-prompt-status");
    await copyAgentChatInboxPrompt(status);
  });
  document.getElementById("btn-settings-copy-inbox")?.addEventListener("click", () => {
    void copyInboxBootstrap(document.getElementById("settings-inbox-copy-status"));
  });
  document.getElementById("agent-chat-open-settings-from-inbox")?.addEventListener("click", () => {
    void openSettingsModal();
  });
  document.getElementById("btn-settings-clear-key")?.addEventListener("click", () => {
    void clearCursorApiKey();
  });
  document.getElementById("agent-chat-key-notice")?.addEventListener("click", (e) => {
    if (e.target.closest("#agent-chat-open-settings")) {
      void openSettingsModal();
    }
  });
  void refreshAppSettings();
}

function initAgentChat() {
  document.getElementById("btn-agent-chat")?.addEventListener("click", () => {
    toggleAgentChatPanel(true);
    void refreshAppSettings();
  });
  document.getElementById("btn-agent-chat-close")?.addEventListener("click", () => {
    toggleAgentChatPanel(false);
  });
  document.getElementById("agent-chat-form")?.addEventListener("submit", (e) => {
    void submitAgentQuestion(e);
  });
  document.getElementById("agent-chat-log")?.addEventListener("click", (e) => {
    const btn = e.target.closest(".agent-chat-delete");
    if (!btn) return;
    const itemId = btn.closest(".agent-chat-thread")?.dataset.id;
    if (itemId) void deleteAgentChatItem(itemId);
  });
}

async function deleteAgentChatItem(itemId) {
  if (!confirm("Удалить вопрос и ответ из чата?")) return;
  try {
    await KoiApi.deleteAgentChatItem(itemId);
    agentChatItems = agentChatItems.filter((i) => i.id !== itemId);
    renderAgentChatLog();
    syncAgentChatPolling();
  } catch (err) {
    setStatus(err.message, true);
  }
}

const THEME_STORAGE_KEY = "koi-theme";

const BRAND_TAGLINES = [
  "Discovery through collaboration across minds",
  "Every experiment should make the next one smarter",
  "Creating a memory that grows with every question",
  "Organizing ideas for discovery",
  "Making research cumulative, not repetitive.",
];

const TAGLINE_ROTATE_MS = 60_000;
const TAGLINE_FADE_MS = 450;

function initTaglineRotation() {
  const el = document.getElementById("brand-tagline");
  if (!el) return;

  let index = Math.floor(Math.random() * BRAND_TAGLINES.length);
  el.textContent = BRAND_TAGLINES[index];

  setInterval(() => {
    el.classList.add("is-fading");
    setTimeout(() => {
      index = (index + 1) % BRAND_TAGLINES.length;
      el.textContent = BRAND_TAGLINES[index];
      el.classList.remove("is-fading");
    }, TAGLINE_FADE_MS);
  }, TAGLINE_ROTATE_MS);
}

function getTheme() {
  return document.documentElement.getAttribute("data-theme") === "light"
    ? "light"
    : "dark";
}

function updateThemeControl(theme) {
  const select = document.getElementById("settings-theme-select");
  if (select) select.value = theme === "light" ? "light" : "dark";
}

function setTheme(theme) {
  const next = theme === "light" ? "light" : "dark";
  if (next === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  localStorage.setItem(THEME_STORAGE_KEY, next);
  updateThemeControl(next);
}

function initTheme() {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  const theme = stored === "light" ? "light" : "dark";
  if (theme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  }
  updateThemeControl(theme);
  document.getElementById("settings-theme-select")?.addEventListener("change", (e) => {
    setTheme(e.target.value);
  });
}

/* ------------------------- База знаний проекта ------------------------- */

const knowledgeState = { tab: "index", docPath: null };

/** Относительная ссылка из markdown → путь от корня проекта (с обработкой «..»). */
function resolveKbPath(fromDoc, href) {
  const clean = href.split(/[?#]/)[0];
  const parts = fromDoc ? fromDoc.split("/").slice(0, -1) : [];
  for (const seg of clean.split("/")) {
    if (!seg || seg === ".") continue;
    if (seg === "..") parts.pop();
    else parts.push(seg);
  }
  return parts.join("/");
}

function updateKnowledgeChrome() {
  const isLog = knowledgeState.tab === "log";
  const tabIndex = document.getElementById("knowledge-tab-index");
  const tabLog = document.getElementById("knowledge-tab-log");
  tabIndex?.classList.toggle("is-active", !isLog);
  tabIndex?.setAttribute("aria-selected", String(!isLog));
  tabLog?.classList.toggle("is-active", isLog);
  tabLog?.setAttribute("aria-selected", String(isLog));
  const crumb = document.getElementById("knowledge-breadcrumb");
  if (crumb) {
    crumb.hidden = isLog || !knowledgeState.docPath;
    const cur = document.getElementById("knowledge-current-path");
    if (cur) cur.textContent = knowledgeState.docPath || "";
  }
  const title = document.getElementById("knowledge-modal-title");
  if (title && state.project) title.textContent = state.project.title;
}

/** Перехват ссылок в контейнере: внутренние .md открываем в этой же модалке. */
function hookKnowledgeLinks(container) {
  container.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (/^(https?:)?\/\//i.test(href) || href.startsWith("#") || href.startsWith("mailto:")) {
      a.setAttribute("target", "_blank");
      return;
    }
    const resolved = resolveKbPath(knowledgeState.docPath, href);
    if (!resolved.endsWith(".md")) {
      a.removeAttribute("href");
      return;
    }
    a.addEventListener("click", (e) => {
      e.preventDefault();
      knowledgeState.tab = "index";
      knowledgeState.docPath = resolved;
      void loadKnowledgeTab();
    });
  });
}

function renderKnowledgeMarkdown(md) {
  const body = document.getElementById("knowledge-body");
  if (!body) return;
  // Медиа в отчётах ссылаются на assets/… относительно папки документа —
  // переписываем в URL ассет-эндпоинта, иначе графики и видео не грузятся.
  const docPath = knowledgeState.docPath;
  const assetUrlFn =
    docPath && state.project
      ? (markdownPath) =>
          KoiApi.knowledgeAssetUrl(
            state.project.id,
            resolveKbPath(docPath, markdownPath)
          )
      : undefined;
  body.innerHTML = renderMarkdown(md, { collapsibleSections: false, assetUrlFn });
  hookKnowledgeLinks(body);
  body.scrollTop = 0;
}

const KB_VERDICTS = {
  supported: { mark: "✔", word: "подтверждена", cls: "supported" },
  refuted: { mark: "✗", word: "опровергнута", cls: "refuted" },
  open: { mark: "…", word: "открыта", cls: "open" },
};

function kbInsightHtml(ins) {
  const imp = Math.max(1, Math.min(5, ins.importance || 3));
  const dots = "●".repeat(imp) + "○".repeat(5 - imp);
  const cert =
    ins.certainty === "definite"
      ? '<span class="kb-cert kb-cert--definite" title="certainty: definite">точно</span>'
      : '<span class="kb-cert kb-cert--tentative" title="certainty: tentative">предварительно</span>';
  const report = ins.report
    ? `<a href="${escapeHtml(ins.report)}" class="kb-link">отчёт</a>`
    : "";
  return `
    <li class="kb-insight">
      <div class="kb-insight-q">${escapeHtml(ins.question)}</div>
      <div class="kb-insight-a">${escapeHtml(ins.narrative || ins.answer || "—")}</div>
      <div class="kb-insight-meta">
        <span class="kb-dots" title="Важность ${imp}/5">${dots}</span>
        ${cert}
        ${ins.card_id ? `<code title="Карточка эксперимента">${escapeHtml(ins.card_id)}</code>` : ""}
        ${report}
      </div>
    </li>`;
}

/** Вкладка «База» — структурированный дашборд из /knowledge/summary. */
function renderKnowledgeDashboard(s) {
  const body = document.getElementById("knowledge-body");
  if (!body) return;
  const st = s.stats || {};
  const seg = (n, cls) =>
    n
      ? `<span class="kb-progress-seg kb-progress-seg--${cls}" style="flex:${n}"></span>`
      : "";
  const chips = `
    <div class="kb-chips">
      <span class="kb-chip kb-chip--supported" title="Подтверждённые гипотезы">✔ подтверждено: ${st.supported ?? 0}</span>
      <span class="kb-chip kb-chip--refuted" title="Опровергнутые гипотезы">✗ опровергнуто: ${st.refuted ?? 0}</span>
      <span class="kb-chip kb-chip--open" title="Открытые гипотезы">… открыто: ${st.open ?? 0}</span>
      <span class="kb-chip" title="Инсайтов в research.json">инсайтов: ${st.insights ?? 0}</span>
      <span class="kb-chip" title="Документов в knowledge/">документов: ${st.docs ?? 0}</span>
      <span class="kb-chip" title="Отчётов по карточкам экспериментов">отчётов: ${st.reports ?? 0}</span>
    </div>
    <div class="kb-progress" title="Гипотезы: ${st.supported ?? 0} ✔ · ${st.refuted ?? 0} ✗ · ${st.open ?? 0} открыто">
      ${seg(st.supported, "supported")}${seg(st.refuted, "refuted")}${seg(st.open, "open")}
    </div>`;
  const problem = s.problem
    ? `<p class="kb-problem"><strong>${escapeHtml(s.problem.title)}.</strong> ${escapeHtml(s.problem.summary || "")}</p>`
    : "";
  const hyps = (s.hypotheses || [])
    .map((h) => {
      const v = KB_VERDICTS[h.verdict] || KB_VERDICTS.open;
      const insights = h.insights.length
        ? `<details class="kb-hyp-insights"${h.verdict === "open" ? " open" : ""}>
             <summary>инсайты (${h.insights.length})</summary>
             <ul>${h.insights.map(kbInsightHtml).join("")}</ul>
           </details>`
        : '<p class="kb-hyp-none">Инсайтов пока нет — эксперимент не закрыт.</p>';
      return `
        <article class="kb-hyp kb-hyp--${v.cls}">
          <header class="kb-hyp-head">
            <span class="kb-verdict-pill kb-verdict-pill--${v.cls}">${v.mark} ${v.word}</span>
            <h4>${escapeHtml(h.title)}</h4>
          </header>
          ${h.description ? `<p class="kb-hyp-desc">${escapeHtml(h.description)}</p>` : ""}
          ${insights}
        </article>`;
    })
    .join("");
  const docs = (s.docs || [])
    .map(
      (d) => `
      <a href="${escapeHtml(d.path)}" class="kb-doc">
        <span class="kb-doc-title">${escapeHtml(d.title)}${d.generated ? ' <span class="kb-doc-auto">автоген</span>' : ""}</span>
        ${d.summary ? `<span class="kb-doc-summary">${escapeHtml(d.summary)}</span>` : ""}
      </a>`
    )
    .join("");
  const log = (s.log_recent || [])
    .slice(0, 3)
    .map(
      (sec) => `
      <div class="kb-log-sec">
        <div class="kb-log-stamp">${escapeHtml(sec.stamp)}</div>
        ${renderMarkdown(sec.entries.map((e) => `- ${e}`).join("\n"), { collapsibleSections: false })}
      </div>`
    )
    .join("");
  body.innerHTML = `
    <div class="kb-dash">
      ${chips}
      ${problem}
      <h3 class="kb-h">Гипотезы</h3>
      <div class="kb-hyps">${hyps || '<p class="md-empty">Гипотез пока нет.</p>'}</div>
      <h3 class="kb-h">Документы знаний</h3>
      <div class="kb-docs">${docs || '<p class="md-empty">Документов пока нет — положите .md в <code>knowledge/</code>.</p>'}</div>
      <h3 class="kb-h">Последние пополнения <button type="button" class="btn kb-log-all" id="kb-open-log">весь журнал</button></h3>
      <div class="kb-log">${log || '<p class="md-empty">Журнал пуст.</p>'}</div>
    </div>`;
  hookKnowledgeLinks(body);
  document.getElementById("kb-open-log")?.addEventListener("click", () => {
    knowledgeState.tab = "log";
    void loadKnowledgeTab();
  });
  body.scrollTop = 0;
}

async function loadKnowledgeTab() {
  if (!state.project) return;
  updateKnowledgeChrome();
  const body = document.getElementById("knowledge-body");
  if (body) body.innerHTML = '<p class="md-empty">Загрузка…</p>';
  try {
    if (knowledgeState.tab === "log") {
      renderKnowledgeMarkdown(await KoiApi.getKnowledgeLog(state.project.id));
    } else if (knowledgeState.docPath) {
      renderKnowledgeMarkdown(
        await KoiApi.getKnowledgeFile(state.project.id, knowledgeState.docPath)
      );
    } else {
      renderKnowledgeDashboard(await KoiApi.getKnowledgeSummary(state.project.id));
    }
  } catch (err) {
    if (body) body.innerHTML = `<p class="md-empty">Не удалось загрузить базу знаний: ${escapeHtml(err.message)}</p>`;
  }
}

function openKnowledgeModal() {
  if (!state.project) return;
  knowledgeState.tab = "index";
  knowledgeState.docPath = null;
  showModal("knowledge-modal");
  void loadKnowledgeTab();
}

const PAPER_TOAST_MS = 3200;

const PAPER_COMMENT_ICONS = {
  copy: `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`,
  send: `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z"/></svg>`,
  resolve: `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`,
  reopen: `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24 4.26L6.7 14.8A5.87 5.87 0 0 1 6 12c0-3.31 2.69-6 6-6zm6.76 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z"/></svg>`,
  delete: `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`,
  check: `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`,
  save: `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M17 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/></svg>`,
  cancel: `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`,
};

function showPaperToast(message, { variant = "success" } = {}) {
  const stack =
    document.getElementById("paper-toast-stack") ||
    paperEls().modal?.querySelector(".paper-toast-stack");
  if (!stack) return;
  const el = document.createElement("div");
  el.className = `paper-toast paper-toast--${variant}`;
  el.setAttribute("role", "status");
  el.innerHTML = `
    <span class="paper-toast__icon">${variant === "error" ? PAPER_COMMENT_ICONS.alert : PAPER_COMMENT_ICONS.check}</span>
    <span class="paper-toast__text">${escapeHtml(message)}</span>`;
  stack.appendChild(el);
  requestAnimationFrame(() => el.classList.add("is-visible"));
  setTimeout(() => {
    el.classList.add("is-leaving");
    setTimeout(() => el.remove(), 220);
  }, PAPER_TOAST_MS);
}

function paperCommentBtn(label, icon, attrs, extraClass = "", { iconOnly = false } = {}) {
  const safeLabel = escapeHtml(label);
  const a11y = `aria-label="${safeLabel}" title="${safeLabel}"`;
  if (iconOnly) {
    return `<button type="button" class="paper-comment-btn paper-comment-btn--icon ${extraClass}" ${a11y} ${attrs}>
      <span class="paper-comment-btn__icon">${icon}</span>
    </button>`;
  }
  return `<button type="button" class="paper-comment-btn ${extraClass}" ${a11y} ${attrs}>
    <span class="paper-comment-btn__icon">${icon}</span>
    <span class="paper-comment-btn__label">${safeLabel}</span>
  </button>`;
}

function paperCommentStatusHtml(comment, stale = false) {
  if (comment.resolved) {
    return `<span class="paper-comment-card__status is-resolved">Resolved</span>`;
  }
  if (stale) {
    return `<span class="paper-comment-card__status is-stale">Устарел</span>`;
  }
  return `<span class="paper-comment-card__status is-open">Review</span>`;
}

function paperCommentQuoteHtml(snippet) {
  if (!snippet) return "";
  return `<blockquote class="paper-comment-card__quote">${snippet}</blockquote>`;
}

function markPaperCopyButton(btn, copied = true) {
  if (!btn) return;
  const iconEl = btn.querySelector(".paper-comment-btn__icon");
  if (!btn.dataset.originalLabel) {
    btn.dataset.originalLabel = btn.getAttribute("aria-label") || "Копировать";
  }
  if (iconEl && !btn.dataset.originalIcon) {
    btn.dataset.originalIcon = iconEl.innerHTML;
  }
  btn.classList.toggle("is-copied", copied);
  const label = copied ? "Скопировано" : btn.dataset.originalLabel;
  btn.setAttribute("aria-label", label);
  btn.setAttribute("title", label);
  if (iconEl) {
    iconEl.innerHTML = copied
      ? PAPER_COMMENT_ICONS.check.replace('width="16"', 'width="14"').replace('height="16"', 'height="14"')
      : btn.dataset.originalIcon;
  }
  const textLabel = btn.querySelector(".paper-comment-btn__label");
  if (textLabel) textLabel.textContent = label;
  if (copied) {
    clearTimeout(btn._copyResetTimer);
    btn._copyResetTimer = setTimeout(() => markPaperCopyButton(btn, false), 2000);
  }
}

/* --------------------- Статья по проекту (NeurIPS PDF) --------------------- */

const paperState = {
  pollTimer: null,
  texPollTimer: null,
  lastRemoteTexMtime: null,
  lastRemotePdfMtime: null,
  pendingRemoteTexMtime: null,
  lastPdfStamp: null,
  lastPdfKey: null,
  lastTexKey: null,
  activeKey: null,
  papers: [],
  texText: "",
  texLines: [],
  comments: [],
  selectedLineStart: null,
  selectedLineEnd: null,
  selectedCharStart: null,
  selectedCharEnd: null,
  selectedText: "",
  activeCommentId: null,
  composeOpen: false,
  pendingDeepLink: null,
  texDirty: false,
  texSaving: false,
  texCompiling: false,
  texSavedAt: 0,
  gutterLineCount: 0,
  progressSettingsOpen: false,
  progressDeadlineTimer: null,
};
const PAPER_INBOX_CONFIGURED_KEY = "koi_paper_inbox_configured";
const PAPER_TEX_POLL_MS = 3000;
const PAPER_TEX_SAVE_GRACE_MS = 15000;
let paperInboxBootstrapCopied = false;
let lastPaperInboxMessage = "";

function isPaperInboxConfigured() {
  return Boolean(appSettings.paper_inbox_configured);
}

function isPaperInboxOperational() {
  return isPaperInboxConfigured() && Boolean(appSettings.paper_inbox_watcher_running);
}

function paperInboxBootstrapText() {
  return (
    lastPaperInboxMessage ||
    appSettings.paper_inbox_bootstrap_prompt ||
    ""
  );
}

function updatePaperInboxNotice() {
  const box = document.getElementById("paper-inbox-message");
  const markBtn = document.getElementById("paper-inbox-mark-configured");
  const watcherEl = document.getElementById("paper-inbox-watcher-status");
  if (!box) return;

  const show = isInboxAgentMode() && !isPaperInboxConfigured();
  box.classList.toggle("hidden", !show);

  if (markBtn) {
    markBtn.disabled = !paperInboxBootstrapCopied;
    markBtn.title = paperInboxBootstrapCopied
      ? "Отметить Paper Inbox как настроенный"
      : "Сначала скопируйте сообщение и вставьте в Cursor";
  }

  if (watcherEl) {
    if (!isInboxAgentMode()) {
      watcherEl.textContent = "";
    } else if (isPaperInboxConfigured() && !appSettings.paper_inbox_watcher_running) {
      watcherEl.textContent =
        "Watcher не запущен — выполните ./scripts/koi-serve.sh start";
    } else if (isPaperInboxOperational()) {
      watcherEl.textContent = "Paper Inbox готов — генерация подхватится автоматически.";
    } else {
      watcherEl.textContent = "";
    }
  }
}

async function copyPaperInboxBootstrap(statusEl) {
  const text = paperInboxBootstrapText();
  if (!text) {
    if (statusEl) statusEl.textContent = "Bootstrap ещё не загружен — обновите страницу.";
    return false;
  }
  try {
    await navigator.clipboard.writeText(text);
    paperInboxBootstrapCopied = true;
    updatePaperInboxNotice();
    if (statusEl) {
      statusEl.textContent =
        "Скопировано — вставьте в чат «ResearchOS Paper Inbox» в Cursor.";
      setTimeout(() => {
        if (statusEl.textContent.startsWith("Скопировано")) statusEl.textContent = "";
      }, 5000);
    }
    return true;
  } catch {
    if (statusEl) statusEl.textContent = "Не удалось скопировать.";
    return false;
  }
}

async function markPaperInboxConfigured() {
  try {
    await KoiApi.setInboxConfigured(true, "paper");
    appSettings.paper_inbox_configured = true;
    try {
      localStorage.setItem(PAPER_INBOX_CONFIGURED_KEY, "1");
    } catch {
      /* private mode */
    }
    updatePaperInboxNotice();
    return true;
  } catch {
    return false;
  }
}

function paperScopeProjectIds() {
  if (isCompositeView() && state.project?.members?.length) {
    return state.project.members.map((member) => member.project_id).filter(Boolean);
  }
  const pid = state.project?.id;
  if (pid && !isCompositeVirtualId(pid)) return [pid];
  return [];
}

function paperTabKey(paper) {
  return `${paper.project_id}:${paper.slug}`;
}

function activePaperEntry() {
  if (!paperState.papers.length) return null;
  return (
    paperState.papers.find((paper) => paperTabKey(paper) === paperState.activeKey) ||
    paperState.papers[0]
  );
}

function paperTabLabel(paper) {
  const title = paper.title || paper.slug;
  if (isCompositeView() && paper.project_id) {
    const member = state.project?.members?.find((m) => m.project_id === paper.project_id);
    const short =
      member?.title?.split(/[—\-·]/)[0]?.trim() ||
      member?.title ||
      paper.project_id;
    return `${short} · ${title}`;
  }
  return title;
}

function paperEls() {
  return {
    modal: document.getElementById("paper-modal"),
    title: document.getElementById("paper-modal-title"),
    tabs: document.getElementById("paper-tabs"),
    progressWrap: document.getElementById("paper-progress-wrap"),
    progressSummary: document.getElementById("paper-progress-summary"),
    progressDeadlineBadge: document.getElementById("paper-progress-deadline-badge"),
    progressSettings: document.getElementById("paper-progress-settings"),
    progressSettingsToggle: document.getElementById("btn-paper-progress-settings"),
    progressMain: document.getElementById("paper-progress-main"),
    progressReferences: document.getElementById("paper-progress-references"),
    progressAppendix: document.getElementById("paper-progress-appendix"),
    progressDeadline: document.getElementById("paper-progress-deadline"),
    progressSave: document.getElementById("btn-paper-progress-save"),
    generate: document.getElementById("btn-paper-generate"),
    regenerate: document.getElementById("btn-paper-regenerate"),
    pdfLink: document.getElementById("paper-pdf-link"),
    texLink: document.getElementById("paper-tex-link"),
    status: document.getElementById("paper-status"),
    empty: document.getElementById("paper-empty"),
    split: document.getElementById("paper-split"),
    frame: document.getElementById("paper-frame"),
    pdfMissing: document.getElementById("paper-pdf-missing"),
    texScroll: document.getElementById("paper-tex-scroll"),
    texScrollInner: document.getElementById("paper-tex-scroll-inner"),
    texGutter: document.getElementById("paper-tex-gutter"),
    texInput: document.getElementById("paper-tex-input"),
    texMirror: document.getElementById("paper-tex-mirror"),
    commentMargin: document.getElementById("paper-comment-margin"),
    texDirty: document.getElementById("paper-tex-dirty"),
    texExternalChange: document.getElementById("paper-tex-external-change"),
    texSave: document.getElementById("btn-paper-tex-save"),
    texCompile: document.getElementById("btn-paper-tex-compile"),
    texSelection: document.getElementById("paper-tex-selection"),
    commentAdd: document.getElementById("btn-paper-comment-add"),
    commentsCount: document.getElementById("paper-comments-count"),
    panel: document.querySelector(".paper-panel"),
  };
}

function paperProgressHasConfig(progress = {}) {
  return Boolean(
    progress?.main_pages ||
      progress?.references_pages ||
      progress?.appendix_pages ||
      progress?.deadline
  );
}

function paperProgressTargetLabel(target) {
  return target != null && target > 0 ? String(target) : "∞";
}

function paperProgressChipClass(current, target) {
  if (target == null || target <= 0) return "is-unlimited";
  if (current > target) return "is-over";
  if (current >= target) return "is-complete";
  if (current > 0) return "is-active";
  return "is-empty";
}

function paperProgressFillPercent(current, target) {
  if (target == null || target <= 0) {
    return current > 0 ? 100 : 18;
  }
  if (target <= 0) return 0;
  return Math.min(100, Math.round((current / target) * 100));
}

function paperProgressMetricHtml(label, current, target) {
  const targetLabel = paperProgressTargetLabel(target);
  const stateClass = paperProgressChipClass(current, target);
  const fill = paperProgressFillPercent(current, target);
  return `<span class="paper-progress-metric ${stateClass}" title="${escapeHtml(label)}">
    <span class="paper-progress-metric__label">${escapeHtml(label)}</span>
    <span class="paper-progress-metric__value">${current}/${escapeHtml(targetLabel)}</span>
    <span class="paper-progress-metric__bar" aria-hidden="true"><span class="paper-progress-metric__fill" style="width:${fill}%"></span></span>
  </span>`;
}

function paperProgressDeadlineIconHtml() {
  return `<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.25" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M10 5.8v4.4l2.6 1.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
}

function formatPaperDeadlineHours(hours, { compact = false } = {}) {
  if (hours == null || Number.isNaN(hours)) return "";
  const rounded = Math.max(0, Math.round(Math.abs(hours)));
  if (hours >= 0) {
    if (compact) {
      if (rounded === 0) return "<1 ч";
      if (rounded < 24) return `${rounded} ч`;
      const days = Math.floor(rounded / 24);
      const rest = rounded % 24;
      return rest === 0 ? `${days} д` : `${days} д ${rest} ч`;
    }
    if (rounded === 0) return "до отправки меньше часа";
    if (rounded === 1) return "до отправки 1 час";
    if (rounded < 24) return `до отправки ${rounded} ч`;
    const days = Math.floor(rounded / 24);
    const rest = rounded % 24;
    if (rest === 0) return `до отправки ${days} д`;
    return `до отправки ${days} д ${rest} ч`;
  }
  if (compact) {
    if (rounded === 0) return "просрочено";
    if (rounded < 24) return `−${rounded} ч`;
    return `−${Math.floor(rounded / 24)} д`;
  }
  if (rounded === 1) return "дедлайн прошёл 1 час назад";
  if (rounded < 24) return `дедлайн прошёл ${rounded} ч назад`;
  const days = Math.floor(rounded / 24);
  return `дедлайн прошёл ${days} д назад`;
}

function computePaperDeadlineHoursLeft(deadline) {
  if (!deadline) return null;
  const parsed = Date.parse(deadline);
  if (Number.isNaN(parsed)) return null;
  return (parsed - Date.now()) / 3600000;
}

function isoToDatetimeLocalValue(iso) {
  if (!iso) return "";
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return "";
  const date = new Date(parsed);
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function datetimeLocalToIso(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  const parsed = Date.parse(text);
  if (Number.isNaN(parsed)) return null;
  return new Date(parsed).toISOString();
}

function parseOptionalPaperTargetInput(input) {
  const text = String(input?.value ?? "").trim();
  if (!text) return null;
  const parsed = Number.parseInt(text, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function stopPaperProgressDeadlineTimer() {
  if (paperState.progressDeadlineTimer) {
    clearInterval(paperState.progressDeadlineTimer);
    paperState.progressDeadlineTimer = null;
  }
}

function startPaperProgressDeadlineTimer() {
  stopPaperProgressDeadlineTimer();
  paperState.progressDeadlineTimer = setInterval(() => {
    renderPaperProgress(activePaperEntry());
  }, 60000);
}

function renderPaperProgress(entry) {
  const els = paperEls();
  if (!els.progressWrap || !els.progressSummary) return;

  if (!entry) {
    els.progressWrap.classList.add("hidden");
    els.progressDeadlineBadge?.classList.add("hidden");
    stopPaperProgressDeadlineTimer();
    return;
  }

  const progress = entry.progress || {};
  const counts = entry.page_counts || null;
  const hasConfig = paperProgressHasConfig(progress);
  const hasCounts = Boolean(counts && counts.total > 0);

  els.progressWrap.classList.remove("hidden");
  const metrics = [];

  if (hasCounts || hasConfig || progress.main_pages != null) {
    metrics.push(paperProgressMetricHtml("Главный", counts?.main ?? 0, progress.main_pages));
  }

  if (hasCounts || hasConfig || progress.references_pages != null) {
    metrics.push(
      paperProgressMetricHtml("Реф.", counts?.references ?? 0, progress.references_pages)
    );
  }

  if (hasCounts || hasConfig || progress.appendix_pages != null) {
    metrics.push(
      paperProgressMetricHtml("Апп.", counts?.appendix ?? 0, progress.appendix_pages)
    );
  }

  if (!metrics.length) {
    metrics.push(`<span class="paper-progress__empty">PDF не собран</span>`);
  }

  els.progressSummary.innerHTML = metrics.join("");

  const hoursLeft =
    entry.deadline_hours_left != null
      ? entry.deadline_hours_left
      : computePaperDeadlineHoursLeft(progress.deadline);
  if (progress.deadline && els.progressDeadlineBadge) {
    const deadlineText = formatPaperDeadlineHours(hoursLeft, { compact: true });
    if (deadlineText) {
      const urgent = hoursLeft != null && hoursLeft >= 0 && hoursLeft <= 24;
      const overdue = hoursLeft != null && hoursLeft < 0;
      els.progressDeadlineBadge.className = `paper-progress__deadline${
        overdue ? " is-overdue" : urgent ? " is-urgent" : ""
      }`;
      els.progressDeadlineBadge.innerHTML = `${paperProgressDeadlineIconHtml()}<span>${escapeHtml(deadlineText)}</span>`;
      els.progressDeadlineBadge.classList.remove("hidden");
    } else {
      els.progressDeadlineBadge.classList.add("hidden");
    }
  } else {
    els.progressDeadlineBadge?.classList.add("hidden");
  }

  if (progress.deadline) startPaperProgressDeadlineTimer();
  else stopPaperProgressDeadlineTimer();

  if (els.progressSettingsToggle) {
    els.progressSettingsToggle.setAttribute("aria-expanded", String(paperState.progressSettingsOpen));
  }
  els.progressSettings?.classList.toggle("hidden", !paperState.progressSettingsOpen);
  els.progressWrap.classList.toggle("is-settings-open", paperState.progressSettingsOpen);
}

function fillPaperProgressForm(entry) {
  const els = paperEls();
  const progress = entry?.progress || {};
  if (els.progressMain) els.progressMain.value = progress.main_pages ?? "";
  if (els.progressReferences) els.progressReferences.value = progress.references_pages ?? "";
  if (els.progressAppendix) els.progressAppendix.value = progress.appendix_pages ?? "";
  if (els.progressDeadline) els.progressDeadline.value = isoToDatetimeLocalValue(progress.deadline);
}

async function savePaperProgress(event) {
  event?.preventDefault();
  const entry = activePaperEntry();
  const els = paperEls();
  if (!entry || !els.progressSave) return;

  const payload = {
    main_pages: parseOptionalPaperTargetInput(els.progressMain),
    references_pages: parseOptionalPaperTargetInput(els.progressReferences),
    appendix_pages: parseOptionalPaperTargetInput(els.progressAppendix),
    deadline: datetimeLocalToIso(els.progressDeadline?.value),
  };

  els.progressSave.disabled = true;
  try {
    const res = await KoiApi.updatePaperProgress(entry.project_id, entry.slug, payload);
    const idx = paperState.papers.findIndex((paper) => paperTabKey(paper) === paperTabKey(entry));
    const progress = res?.progress || payload;
    const updated = {
      ...entry,
      progress,
      deadline_hours_left: computePaperDeadlineHoursLeft(progress.deadline),
    };
    if (idx >= 0) paperState.papers[idx] = { ...paperState.papers[idx], ...updated };
    renderPaperProgress(updated);
    paperState.progressSettingsOpen = false;
    showPaperToast("Настройки прогресса сохранены");
  } catch (err) {
    showPaperToast(`Не удалось сохранить прогресс: ${err.message}`, "error");
  } finally {
    els.progressSave.disabled = false;
  }
}

function renderPaperTabs() {
  const { tabs } = paperEls();
  if (!tabs) return;
  const papers = paperState.papers || [];
  if (!papers.length) {
    tabs.innerHTML = `<p class="card-live-empty card-live-empty--tabs">Нет статей — добавьте <code>paper/&lt;slug&gt;/</code> в member-проекте или сгенерируйте черновик</p>`;
    return;
  }
  tabs.innerHTML = papers
    .map((paper) => {
      const key = paperTabKey(paper);
      const active = key === paperState.activeKey;
      return `<button type="button" class="card-live-card-tab${active ? " is-active" : ""}${paper.pdf_exists ? "" : " paper-tab--no-pdf"}" data-paper-key="${escapeHtml(key)}" role="tab" aria-selected="${active}" title="${escapeHtml(paper.pdf_exists ? "" : "PDF не собран")}">
        <span class="card-live-card-tab__dot" aria-hidden="true"></span>
        <span class="card-live-card-tab__title">${escapeHtml(paperTabLabel(paper))}</span>
      </button>`;
    })
    .join("");
  tabs.querySelectorAll("[data-paper-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.getAttribute("data-paper-key");
      if (!key || key === paperState.activeKey) return;
      if (paperState.texDirty && !window.confirm("Есть несохранённые изменения в main.tex. Переключить статью?")) {
        return;
      }
      paperState.activeKey = key;
      paperState.lastPdfStamp = null;
      paperState.lastPdfKey = null;
      paperState.lastTexKey = null;
      paperState.lastRemoteTexMtime = null;
      paperState.lastRemotePdfMtime = null;
      paperState.pendingRemoteTexMtime = null;
      paperState.texDirty = false;
      paperState.activeCommentId = null;
      resetPaperSelection();
      if (paperEls().frame) paperEls().frame.src = "about:blank";
      paperState.progressSettingsOpen = false;
      renderPaperTabs();
      renderPaperFromEntry(activePaperEntry());
      void refreshPaperStatus({ quiet: true });
    });
  });
}

async function loadProjectPapers() {
  const projectIds = paperScopeProjectIds();
  if (!projectIds.length) {
    paperState.papers = [];
    paperState.activeKey = null;
    return;
  }
  const payloads = await Promise.all(projectIds.map((id) => KoiApi.listProjectPapers(id)));
  const merged = [];
  projectIds.forEach((projectId, index) => {
    for (const paper of payloads[index]?.papers || []) {
      merged.push({ ...paper, project_id: projectId });
    }
  });
  paperState.papers = merged;
  if (!merged.length) {
    paperState.activeKey = `${projectIds[0]}:default`;
    return;
  }
  if (!paperState.activeKey || !merged.some((paper) => paperTabKey(paper) === paperState.activeKey)) {
    const withPdf = merged.find((paper) => paper.pdf_exists);
    paperState.activeKey = paperTabKey(withPdf || merged[0]);
  }
}

function renderPaperFromEntry(entry) {
  if (!entry) return;
  fillPaperProgressForm(entry);
  renderPaperProgress(entry);
  renderPaperState({ ...entry, slug: entry.slug });
}

function bindPaperFrameLoad() {
  const { frame } = paperEls();
  if (!frame || frame.dataset.paperLoadBound === "1") return;
  frame.dataset.paperLoadBound = "1";
  frame.addEventListener("load", () => {
    if (!frame.src || frame.src === "about:blank") return;
    hidePaperLoader();
    frame.classList.remove("hidden");
    paperEls().pdfMissing?.classList.add("hidden");
  });
  frame.addEventListener("error", () => {
    hidePaperLoader();
    const { status, pdfMissing } = paperEls();
    if (status) status.textContent = "Не удалось загрузить PDF в просмотрщике — откройте ссылку «Открыть PDF».";
    pdfMissing?.classList.remove("hidden");
  });
}

function stopPaperPolling() {
  if (paperState.pollTimer) {
    clearInterval(paperState.pollTimer);
    paperState.pollTimer = null;
  }
}

function stopPaperTexPolling() {
  if (paperState.texPollTimer) {
    clearInterval(paperState.texPollTimer);
    paperState.texPollTimer = null;
  }
}

function startPaperTexPolling() {
  stopPaperTexPolling();
  paperState.texPollTimer = setInterval(() => {
    void pollPaperDiskChanges();
  }, PAPER_TEX_POLL_MS);
}

function isPaperModalOpen() {
  return !paperEls().modal?.classList.contains("hidden");
}

function isPaperWorkspaceVisible() {
  return isPaperModalOpen() && !paperEls().split?.classList.contains("hidden");
}

function showPaperTexExternalChangeBanner(show = true) {
  paperEls().texExternalChange?.classList.toggle("hidden", !show);
}

function dismissPaperTexExternalChange() {
  paperState.pendingRemoteTexMtime = null;
  showPaperTexExternalChangeBanner(false);
}

async function syncPaperTexRemoteMtime(projectId, slug) {
  try {
    const meta = await KoiApi.getPaperTexMeta(projectId, slug);
    if (meta?.tex_mtime != null) paperState.lastRemoteTexMtime = meta.tex_mtime;
    return meta;
  } catch {
    return null;
  }
}

async function reloadPaperTexFromDisk({ quiet = false, remoteText = null } = {}) {
  const entry = activePaperEntry();
  if (!entry) return false;
  try {
    const text = remoteText ?? (await KoiApi.getPaperTex(entry.project_id, entry.slug));
    if (text === paperState.texText) {
      await syncPaperTexRemoteMtime(entry.project_id, entry.slug);
      dismissPaperTexExternalChange();
      return true;
    }
    paperState.lastTexKey = null;
    paperState.composeOpen = false;
    dismissPaperTexExternalChange();
    setTexEditorContent(text, { markClean: true });
    await syncPaperTexRemoteMtime(entry.project_id, entry.slug);
    if (!quiet) showPaperToast("main.tex перезагружен с диска");
    return true;
  } catch (err) {
    if (!quiet && paperEls().status) {
      paperEls().status.textContent = `Не удалось перезагрузить main.tex: ${err.message}`;
    }
    return false;
  }
}

async function pollPaperDiskChanges() {
  const entry = activePaperEntry();
  if (!entry || !isPaperWorkspaceVisible()) return;
  if (paperState.texSaving) return;

  try {
    const st = await KoiApi.getPaperStatus(entry.project_id, entry.slug);
    await pollPaperPdfChanges(entry, st);
    if (!paperState.texCompiling) {
      await pollPaperTexChanges(entry, st);
    }
  } catch {
    /* transient network errors */
  }
}

async function pollPaperPdfChanges(entry, st) {
  if (!st?.pdf_exists) return;
  const remoteMtime = st.pdf_mtime;
  if (remoteMtime == null) return;

  if (paperState.lastRemotePdfMtime == null) {
    paperState.lastRemotePdfMtime = remoteMtime;
    return;
  }

  if (remoteMtime === paperState.lastRemotePdfMtime) return;

  paperState.lastRemotePdfMtime = remoteMtime;
  paperState.lastPdfStamp = null;
  showPaperPdf(entry.project_id, entry.slug, remoteMtime);
  const idx = paperState.papers.findIndex((paper) => paperTabKey(paper) === paperTabKey(entry));
  if (idx >= 0) {
    paperState.papers[idx] = {
      ...paperState.papers[idx],
      pdf_exists: true,
      pdf_mtime: remoteMtime,
      page_counts: st?.page_counts ?? paperState.papers[idx].page_counts,
    };
    renderPaperProgress(paperState.papers[idx]);
    renderPaperTabs();
  }
}

async function pollPaperTexChanges(entry, st) {
  if (Date.now() - paperState.texSavedAt < PAPER_TEX_SAVE_GRACE_MS) return;

  const remoteMtime = st?.tex_mtime;
  if (remoteMtime == null) return;

  if (paperState.lastRemoteTexMtime == null) {
    paperState.lastRemoteTexMtime = remoteMtime;
    return;
  }

  if (Math.abs(remoteMtime - paperState.lastRemoteTexMtime) < 0.001) return;

  let remoteText = null;
  try {
    remoteText = await KoiApi.getPaperTex(entry.project_id, entry.slug);
  } catch {
    return;
  }

  if (remoteText === paperState.texText) {
    paperState.lastRemoteTexMtime = remoteMtime;
    paperState.pendingRemoteTexMtime = null;
    showPaperTexExternalChangeBanner(false);
    return;
  }

  if (paperState.texDirty || paperState.composeOpen) {
    paperState.pendingRemoteTexMtime = remoteMtime;
    showPaperTexExternalChangeBanner(true);
    return;
  }

  paperState.lastRemoteTexMtime = remoteMtime;
  await reloadPaperTexFromDisk({ quiet: true, remoteText });
  showPaperToast("main.tex обновлён с диска");
}

function stopPaperPollingAll() {
  stopPaperPolling();
  stopPaperTexPolling();
}

function showPaperLoader(step = "Генерация статьи…") {
  showKoiLoader("paper-loader", { step, pool: "paper" });
}

function hidePaperLoader() {
  hideKoiLoader("paper-loader");
}

function paperViewerKey(projectId, slug) {
  return `${projectId}:${slug}`;
}

function paperLineRangeLabel(lineStart, lineEnd) {
  if (!lineStart) return "";
  if (lineEnd === lineStart) return `строка ${lineStart}`;
  return `строки ${lineStart}–${lineEnd}`;
}

function commentAnchorMeta(comment) {
  const anchor = comment?.anchor || {};
  return {
    start: Number(anchor.line_start) || 1,
    end: Number(anchor.line_end) || Number(anchor.line_start) || 1,
    charStart: anchor.char_start ?? null,
    charEnd: anchor.char_end ?? null,
    selectedText: anchor.selected_text || "",
  };
}

function commentLinesFor(comment) {
  const { start, end } = commentAnchorMeta(comment);
  return { start, end };
}

function paperSelectionLabel() {
  const {
    selectedLineStart: start,
    selectedLineEnd: end,
    selectedCharStart: cs,
    selectedCharEnd: ce,
    selectedText,
  } = paperState;
  if (!start) return "Выделите фрагмент текста";
  let label = paperLineRangeLabel(start, end);
  if (start === end && cs != null && ce != null) {
    const lineLen = (paperState.texLines[start - 1] || "").length;
    if (cs > 0 || ce < lineLen) label += ` · col ${cs + 1}–${ce}`;
  }
  const excerpt = (selectedText || "").replace(/\s+/g, " ").trim();
  if (excerpt) {
    label += excerpt.length <= 42 ? ` · “${excerpt}”` : ` · “${excerpt.slice(0, 40)}…”`;
  }
  return label;
}

async function paperContentHash(lineStart, lineEnd, charStart = null, charEnd = null) {
  const lines = paperState.texLines || [];
  const start = Math.max(1, lineStart);
  const end = Math.min(lines.length, lineEnd);
  if (start > end || !lines.length || !crypto?.subtle) return "";
  let chunk;
  if (start === end) {
    const line = lines[start - 1] || "";
    chunk =
      charStart != null && charEnd != null ? line.slice(charStart, charEnd) : line;
  } else {
    const parts = [];
    for (let lineNo = start; lineNo <= end; lineNo += 1) {
      const line = lines[lineNo - 1] || "";
      if (lineNo === start && charStart != null) parts.push(line.slice(charStart));
      else if (lineNo === end && charEnd != null) parts.push(line.slice(0, charEnd));
      else parts.push(line);
    }
    chunk = parts.join("\n");
  }
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(chunk));
  const hex = Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 16);
  return `sha256:${hex}`;
}

function commentFirstMessage(comment) {
  const thread = comment?.thread || [];
  return thread[0]?.body || "";
}

function paperCommentUrl(projectId, slug, commentId) {
  const url = new URL(window.location.href);
  url.searchParams.set("project", projectId);
  url.searchParams.set("paper", slug);
  url.searchParams.set("paper_comment", commentId);
  return url.toString();
}

function paperCommentClipboardText(projectId, slug, comment) {
  const { start, end, charStart, charEnd, selectedText } = commentAnchorMeta(comment);
  const body = commentFirstMessage(comment);
  const url = paperCommentUrl(projectId, slug, comment.id);
  const loc =
    start === end && charStart != null && charEnd != null
      ? `L${start}:${charStart + 1}–${charEnd}`
      : `L${start}${end !== start ? `–${end}` : ""}`;
  const lines = [
    `Paper review · main.tex ${loc} · ${projectId}/${slug}`,
    "",
  ];
  if (selectedText) lines.push(`Selected: ${selectedText}`, "");
  lines.push(
    `> ${body}`,
    "",
    `Link: ${url}`,
    `Storage: koi-structure/paper/${slug}/comments.json · id=${comment.id}`
  );
  return lines.join("\n");
}

function setPaperViewerVisible({ split = false, empty = false } = {}) {
  const els = paperEls();
  els.empty?.classList.toggle("hidden", !empty);
  els.split?.classList.toggle("hidden", !split);
  els.panel?.classList.toggle("is-workspace", split);
  if (split && isPaperModalOpen()) startPaperTexPolling();
  else stopPaperTexPolling();
}

function resetPaperSelection() {
  paperState.selectedLineStart = null;
  paperState.selectedLineEnd = null;
  paperState.selectedCharStart = null;
  paperState.selectedCharEnd = null;
  paperState.selectedText = "";
  paperState.composeOpen = false;
  updatePaperSelectionUi();
}

function applyPaperTextSelection(parsed) {
  if (!parsed) {
    paperState.selectedLineStart = null;
    paperState.selectedLineEnd = null;
    paperState.selectedCharStart = null;
    paperState.selectedCharEnd = null;
    paperState.selectedText = "";
  } else {
    let { lineStart, lineEnd, charStart, charEnd, selectedText } = parsed;
    if (lineStart > lineEnd) {
      [lineStart, lineEnd] = [lineEnd, lineStart];
      [charStart, charEnd] = [charEnd, charStart];
    }
    paperState.selectedLineStart = lineStart;
    paperState.selectedLineEnd = lineEnd;
    paperState.selectedCharStart = charStart;
    paperState.selectedCharEnd = charEnd;
    paperState.selectedText = selectedText;
  }
  updatePaperSelectionUi();
}

function parseTexareaSelection(ta) {
  if (!ta) return null;
  const start = ta.selectionStart;
  const end = ta.selectionEnd;
  if (start == null || end == null || start === end) return null;
  const selectedText = ta.value.slice(start, end);
  if (!selectedText.trim()) return null;
  const value = ta.value;
  const lineStart = value.slice(0, start).split("\n").length;
  const lineEnd = value.slice(0, end).split("\n").length;
  const charStart = start - (value.lastIndexOf("\n", start - 1) + 1);
  const charEnd = end - (value.lastIndexOf("\n", end - 1) + 1);
  return { lineStart, lineEnd, charStart, charEnd, selectedText };
}

function syncPaperTextSelection() {
  const ta = paperEls().texInput;
  if (!ta || document.activeElement !== ta) {
    applyPaperTextSelection(null);
    return;
  }
  applyPaperTextSelection(parseTexareaSelection(ta));
}

function renderPaperTexMirror() {
  const mirror = paperEls().texMirror;
  if (!mirror) return;
  const lines = paperState.texLines || [];
  if (!lines.length) {
    mirror.innerHTML = `<div class="paper-tex-mirror-line" data-line="1">\u200b</div>`;
    return;
  }
  mirror.innerHTML = lines
    .map((line, index) => {
      const lineNo = index + 1;
      const text = escapeHtml(line);
      return `<div class="paper-tex-mirror-line" data-line="${lineNo}">${text || "\u200b"}</div>`;
    })
    .join("");
}

function syncPaperGutterFromMirror() {
  const els = paperEls();
  const mirror = els.texMirror;
  const gutter = els.texGutter;
  if (!mirror || !gutter) return;
  mirror.querySelectorAll(".paper-tex-mirror-line").forEach((mirrorLine) => {
    const lineNo = mirrorLine.getAttribute("data-line");
    const gutterLine = gutter.querySelector(`.paper-tex-gutter-line[data-line="${lineNo}"]`);
    if (gutterLine) gutterLine.style.minHeight = `${mirrorLine.offsetHeight}px`;
  });
}

function measurePaperAnchorTop(lineNo, charOffset = 0) {
  const mirror = paperEls().texMirror;
  if (!mirror) return 0;
  const lineEl = mirror.querySelector(`.paper-tex-mirror-line[data-line="${lineNo}"]`);
  if (!lineEl) return 0;
  const offset = Math.max(0, Number(charOffset) || 0);
  if (!offset) return lineEl.offsetTop;

  const text = paperState.texLines[lineNo - 1] || "";
  const safeBefore = escapeHtml(text.slice(0, offset));
  const safeAfter = escapeHtml(text.slice(offset));
  const originalHtml = lineEl.innerHTML;
  lineEl.innerHTML = `${safeBefore}<span class="paper-tex-mirror-marker">\u200b</span>${safeAfter || "\u200b"}`;
  const marker = lineEl.querySelector(".paper-tex-mirror-marker");
  let top = lineEl.offsetTop;
  if (marker) {
    const lineRect = lineEl.getBoundingClientRect();
    const markerRect = marker.getBoundingClientRect();
    top = lineEl.offsetTop + (markerRect.top - lineRect.top);
  }
  lineEl.innerHTML = originalHtml;
  return top;
}

function measurePaperLineTop(lineNo, charOffset = 0) {
  return measurePaperAnchorTop(lineNo, charOffset);
}

function commentAnchorTop(comment) {
  const { start, end, charStart } = commentAnchorMeta(comment);
  const charOffset = start === end && charStart != null ? charStart : 0;
  return measurePaperAnchorTop(start, charOffset);
}

function selectionAnchorTop() {
  const start = paperState.selectedLineStart;
  if (!start) return 0;
  const charOffset =
    paperState.selectedLineStart === paperState.selectedLineEnd
      ? paperState.selectedCharStart ?? 0
      : 0;
  return measurePaperAnchorTop(start, charOffset);
}

function syncPaperLayoutMetrics() {
  renderPaperTexMirror();
  syncPaperGutterFromMirror();
  syncPaperTexEditorHeight();
}

async function refreshPaperCommentLayout({ rebuildGutter = false } = {}) {
  const lineCount = Math.max(1, paperState.texLines.length || 1);
  if (rebuildGutter || lineCount !== paperState.gutterLineCount) {
    await renderPaperTexGutter();
    paperState.gutterLineCount = lineCount;
  }
  syncPaperLayoutMetrics();
  const margin = paperEls().commentMargin;
  if (!margin) return;
  margin.querySelectorAll(".paper-comment-anchor").forEach((anchor) => {
    let top = 0;
    if (anchor.hasAttribute("data-compose")) {
      top = selectionAnchorTop();
      if (paperState.selectedLineStart) {
        anchor.dataset.lineNo = String(paperState.selectedLineStart);
      }
    } else {
      const comment = paperState.comments.find(
        (item) => item.id === anchor.getAttribute("data-comment-id")
      );
      if (comment) {
        top = commentAnchorTop(comment);
        anchor.dataset.lineNo = String(commentLinesFor(comment).start);
      }
    }
    anchor.dataset.lineTop = String(top);
    anchor.style.top = `${top}px`;
  });
  layoutPaperCommentAnchors();
}

function syncTexFromInput() {
  const ta = paperEls().texInput;
  if (!ta) return;
  paperState.texText = ta.value;
  paperState.texLines = ta.value.split("\n");
  paperState.texDirty = true;
  updatePaperSaveUi();
  void refreshPaperCommentLayout({ rebuildGutter: true });
}

function updatePaperSaveUi() {
  const els = paperEls();
  const busy = paperState.texSaving || paperState.texCompiling;
  els.texDirty?.classList.toggle("hidden", !paperState.texDirty);
  if (els.texSave) {
    els.texSave.disabled = !paperState.texDirty || busy;
    els.texSave.textContent = paperState.texSaving ? "Сохранение…" : "Сохранить";
  }
  if (els.texCompile) {
    els.texCompile.disabled = busy;
    els.texCompile.textContent = paperState.texCompiling ? "Сборка…" : "Собрать PDF";
  }
}

function setTexEditorContent(text, { markClean = true } = {}) {
  const els = paperEls();
  paperState.texText = text;
  paperState.texLines = text.split("\n");
  if (els.texInput && els.texInput.value !== text) els.texInput.value = text;
  if (markClean) paperState.texDirty = false;
  updatePaperSaveUi();
  syncPaperTexEditorHeight();
  void renderPaperTexEditor();
}

function offsetForLine(text, lineNo, charOffset = 0) {
  const lines = text.split("\n");
  let pos = 0;
  for (let i = 0; i < lineNo - 1 && i < lines.length; i += 1) {
    pos += lines[i].length + 1;
  }
  return pos + Math.max(0, charOffset);
}

function selectPaperLines(lineStart, lineEnd, anchor = {}) {
  const maxLine = Math.max(1, paperState.texLines.length || 1);
  let start = Math.max(1, Math.min(lineStart, maxLine));
  let end = Math.max(1, Math.min(lineEnd, maxLine));
  if (start > end) [start, end] = [end, start];
  paperState.selectedLineStart = start;
  paperState.selectedLineEnd = end;
  paperState.selectedCharStart = anchor.charStart ?? null;
  paperState.selectedCharEnd = anchor.charEnd ?? null;
  paperState.selectedText = anchor.selectedText || "";
  updatePaperSelectionUi();
  void renderPaperTexGutter();

  const ta = paperEls().texInput;
  if (!ta) return;
  const value = ta.value;
  let selStart = offsetForLine(value, start, anchor.charStart ?? 0);
  let selEnd = offsetForLine(
    value,
    end,
    anchor.charEnd ?? (paperState.texLines[end - 1] || "").length
  );
  if (selStart > selEnd) [selStart, selEnd] = [selEnd, selStart];
  ta.focus();
  ta.setSelectionRange(selStart, selEnd);
}

function updatePaperSelectionUi() {
  const els = paperEls();
  const { selectedLineStart: start, selectedLineEnd: end } = paperState;
  const hasSelection = Boolean(start && paperState.selectedText);
  if (els.texSelection) {
    els.texSelection.textContent = paperSelectionLabel();
    els.texSelection.classList.toggle("has-selection", hasSelection);
  }
  if (els.commentAdd) els.commentAdd.disabled = !hasSelection || paperState.composeOpen;
}

function linesWithComments() {
  const map = new Map();
  for (const comment of paperState.comments) {
    const { start, end } = commentLinesFor(comment);
    for (let line = start; line <= end; line += 1) {
      if (!map.has(line)) map.set(line, comment.id);
    }
  }
  return map;
}

async function renderPaperTexGutter() {
  const els = paperEls();
  if (!els.texGutter) return;
  const commentByLine = linesWithComments();
  const staleChecks = await Promise.all(
    paperState.comments.map(async (comment) => {
      const { start, end, charStart, charEnd } = commentAnchorMeta(comment);
      const current = await paperContentHash(start, end, charStart, charEnd);
      return [comment.id, comment.anchor?.content_hash && current !== comment.anchor.content_hash];
    })
  );
  const staleById = new Map(staleChecks);
  const { selectedLineStart: selStart, selectedLineEnd: selEnd } = paperState;
  const lineCount = Math.max(1, paperState.texLines.length);

  els.texGutter.innerHTML = `<div class="paper-tex-gutter-inner">${Array.from({ length: lineCount }, (_, index) => {
    const lineNo = index + 1;
    const commentId = commentByLine.get(lineNo) || "";
    const hasComment = Boolean(commentId);
    const stale = hasComment && staleById.get(commentId);
    const inRange = Boolean(selStart) && lineNo >= selStart && lineNo <= selEnd;
    const activeComment =
      Boolean(paperState.activeCommentId) && commentId === paperState.activeCommentId;
    return `<div class="paper-tex-gutter-line${hasComment ? " is-commented" : ""}${stale ? " is-stale" : ""}${inRange ? " is-in-range" : ""}${activeComment ? " is-active-comment" : ""}" data-line="${lineNo}">
      <span class="paper-tex-gutter-ln">${lineNo}</span>
      <button type="button" class="paper-tex-gutter-mark" aria-label="Комментарий на строке ${lineNo}"${commentId ? ` data-focus-comment="${escapeHtml(commentId)}"` : ""}></button>
    </div>`;
  }).join("")}</div>`;

  els.texGutter.querySelectorAll("[data-focus-comment]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      focusPaperComment(btn.getAttribute("data-focus-comment"));
    });
  });
}

function syncPaperTexEditorHeight() {
  const els = paperEls();
  const ta = els.texInput;
  const mirror = els.texMirror;
  if (!ta) return;
  const scrollMin = Math.max((els.texScroll?.clientHeight || 0) - 8, 120);
  const mirrorHeight = mirror?.offsetHeight || ta.scrollHeight;
  const contentHeight = Math.max(mirrorHeight, scrollMin);
  ta.style.height = `${contentHeight}px`;
  if (els.commentMargin) els.commentMargin.style.minHeight = `${contentHeight}px`;
}

function layoutPaperCommentAnchors() {
  const margin = paperEls().commentMargin;
  if (!margin) return;
  const anchors = [...margin.querySelectorAll(".paper-comment-anchor")];
  anchors.sort(
    (a, b) => Number(a.dataset.lineTop || 0) - Number(b.dataset.lineTop || 0)
  );
  let lastBottom = 0;
  for (const anchor of anchors) {
    let top = Number(anchor.dataset.lineTop || 0);
    if (top < lastBottom + 4) top = lastBottom + 4;
    anchor.style.top = `${top}px`;
    lastBottom = top + anchor.offsetHeight;
  }
  const ta = paperEls().texInput;
  if (ta) {
    const needed = Math.max(ta.scrollHeight, lastBottom + 24, margin.clientHeight);
    ta.style.height = `${needed}px`;
    margin.style.minHeight = `${needed}px`;
  }
}

function bindPaperTexEditor() {
  const ta = paperEls().texInput;
  const wrap = ta?.closest(".paper-tex-input-wrap");
  if (!ta || ta.dataset.editorBound === "1") return;
  ta.dataset.editorBound = "1";

  ta.addEventListener("input", () => {
    syncTexFromInput();
  });
  ta.addEventListener("mouseup", () => {
    requestAnimationFrame(syncPaperTextSelection);
  });
  ta.addEventListener("keyup", () => {
    requestAnimationFrame(syncPaperTextSelection);
  });
  ta.addEventListener("select", () => {
    requestAnimationFrame(syncPaperTextSelection);
  });
  ta.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "s") {
      event.preventDefault();
      void savePaperTex();
    }
  });

  if (wrap && window.ResizeObserver && !wrap.dataset.resizeBound) {
    wrap.dataset.resizeBound = "1";
    let resizeTimer = null;
    const observer = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        void refreshPaperCommentLayout();
      }, 80);
    });
    observer.observe(wrap);
  }
}

async function renderPaperTexEditor() {
  await renderPaperTexGutter();
  paperState.gutterLineCount = Math.max(1, paperState.texLines.length || 1);
  syncPaperLayoutMetrics();
  await renderPaperCommentMargin();
  updatePaperSelectionUi();
  if (paperState.activeCommentId) scrollPaperToComment(paperState.activeCommentId);
}

async function savePaperTex({ quiet = false } = {}) {
  const entry = activePaperEntry();
  const els = paperEls();
  if (!entry) {
    if (els.status) els.status.textContent = "Не удалось сохранить: статья не выбрана";
    return false;
  }
  if (paperState.texSaving) return false;
  syncTexFromInput();
  const content = paperState.texText ?? els.texInput?.value ?? "";
  paperState.texSaving = true;
  updatePaperSaveUi();
  try {
    const res = await KoiApi.savePaperTex(entry.project_id, entry.slug, content);
    paperState.texDirty = false;
    paperState.texText = content;
    paperState.texLines = content.split("\n");
    if (res?.tex_mtime != null) {
      paperState.lastRemoteTexMtime = res.tex_mtime;
    } else {
      await syncPaperTexRemoteMtime(entry.project_id, entry.slug);
    }
    dismissPaperTexExternalChange();
    updatePaperSaveUi();
    paperState.texSavedAt = Date.now();
    const label = `${entry.project_id}/${entry.slug}`;
    if (!quiet && els.status) {
      els.status.textContent = `main.tex сохранён · ${label}`;
      setTimeout(() => {
        if (els.status?.textContent?.startsWith("main.tex сохранён")) els.status.textContent = "";
      }, 5000);
    }
    if (!quiet) showPaperToast(`main.tex сохранён · ${label}`);
    return true;
  } catch (err) {
    if (els.status) els.status.textContent = `Не удалось сохранить main.tex: ${err.message}`;
    showPaperToast(`Ошибка сохранения: ${err.message}`, { variant: "error" });
    return false;
  } finally {
    paperState.texSaving = false;
    updatePaperSaveUi();
  }
}

async function compilePaperPdf() {
  const entry = activePaperEntry();
  const els = paperEls();
  if (!entry || paperState.texCompiling) return;
  if (paperState.texDirty) {
    const saved = await savePaperTex({ quiet: true });
    if (!saved) return;
  }
  paperState.texCompiling = true;
  updatePaperSaveUi();
  showPaperLoader("Сборка PDF…");
  try {
    const res = await KoiApi.compilePaper(entry.project_id, entry.slug);
    hidePaperLoader();
    if (els.status) {
      els.status.textContent = res?.engine ? `PDF собран (${res.engine})` : "PDF собран";
      setTimeout(() => {
        if (els.status?.textContent?.startsWith("PDF собран")) els.status.textContent = "";
      }, 4000);
    }
    const pdfMtime = res?.pdf_mtime || Date.now();
    paperState.lastPdfStamp = null;
    paperState.lastRemotePdfMtime = pdfMtime;
    showPaperPdf(entry.project_id, entry.slug, pdfMtime);
    const idx = paperState.papers.findIndex((paper) => paperTabKey(paper) === paperTabKey(entry));
    if (idx >= 0) {
      paperState.papers[idx] = {
        ...paperState.papers[idx],
        pdf_exists: true,
        pdf_mtime: pdfMtime,
        page_counts: res?.page_counts ?? paperState.papers[idx].page_counts,
      };
      renderPaperProgress(paperState.papers[idx]);
    }
    renderPaperTabs();
    showPaperToast(`PDF собран (${res?.engine || "ok"})`);
  } catch (err) {
    hidePaperLoader();
    const detail = String(err.message || err).trim();
    if (els.status) els.status.textContent = `Ошибка сборки PDF: ${detail}`;
    showPaperToast(detail.slice(0, 240) || "Ошибка сборки PDF", { variant: "error" });
  } finally {
    paperState.texCompiling = false;
    updatePaperSaveUi();
  }
}

function paperCommentAnchorHtml(comment, { expanded = false, stale = false } = {}) {
  const { start, end, selectedText } = commentAnchorMeta(comment);
  const snippet = selectedText
    ? escapeHtml(selectedText.replace(/\s+/g, " ").trim().slice(0, 72))
    : "";
  const firstBody = escapeHtml(commentFirstMessage(comment));
  const messages = comment.thread || [];
  const lineTop = commentAnchorTop(comment);

  if (!expanded) {
    return `<div class="paper-comment-anchor is-collapsed${comment.resolved ? " is-resolved" : ""}" data-comment-id="${escapeHtml(comment.id)}" data-line-no="${start}" data-line-top="${lineTop}" style="top:${lineTop}px">
      <article class="paper-comment-card">
        <div class="paper-comment-card__rail" aria-hidden="true"></div>
        <div class="paper-comment-card__content">
          <header class="paper-comment-card__head">
            <span class="paper-comment-card__badge">L${start}${end !== start ? `–${end}` : ""}</span>
            ${paperCommentStatusHtml(comment, stale)}
          </header>
          ${paperCommentQuoteHtml(snippet)}
          <p class="paper-comment-card__body">${firstBody || "…"}</p>
        </div>
      </article>
    </div>`;
  }

  return `<div class="paper-comment-anchor is-active${comment.resolved ? " is-resolved" : ""}" data-comment-id="${escapeHtml(comment.id)}" data-line-no="${start}" data-line-top="${lineTop}" style="top:${lineTop}px">
    <article class="paper-comment-card">
      <div class="paper-comment-card__rail" aria-hidden="true"></div>
      <div class="paper-comment-card__content">
        <header class="paper-comment-card__head">
          <span class="paper-comment-card__badge">L${start}${end !== start ? `–${end}` : ""}</span>
          ${paperCommentStatusHtml(comment, stale)}
        </header>
        ${paperCommentQuoteHtml(snippet)}
        <div class="paper-comment-thread__messages">
          ${messages
            .map(
              (msg) => `<div class="paper-comment-message">
                <div class="paper-comment-message__meta">${escapeHtml(msg.author || "reviewer")} · ${escapeHtml(new Date(msg.created_at || "").toLocaleString() || "")}</div>
                <div class="paper-comment-message__body">${escapeHtml(msg.body || "")}</div>
              </div>`
            )
            .join("")}
        </div>
        <textarea class="paper-comment-thread-reply" rows="2" placeholder="Ответ…" data-paper-thread-reply="${escapeHtml(comment.id)}"></textarea>
        <footer class="paper-comment-card__actions paper-comment-card__actions--compact">
          ${paperCommentBtn("Ответить", PAPER_COMMENT_ICONS.send, `data-paper-thread-send="${escapeHtml(comment.id)}"`, "paper-comment-btn--primary", { iconOnly: true })}
          ${paperCommentBtn("Копировать", PAPER_COMMENT_ICONS.copy, `data-paper-thread-copy="${escapeHtml(comment.id)}"`, "", { iconOnly: true })}
          ${paperCommentBtn(comment.resolved ? "Открыть снова" : "Resolve", comment.resolved ? PAPER_COMMENT_ICONS.reopen : PAPER_COMMENT_ICONS.resolve, `data-paper-thread-resolve="${escapeHtml(comment.id)}"`, "", { iconOnly: true })}
          ${paperCommentBtn("Удалить", PAPER_COMMENT_ICONS.delete, `data-paper-thread-delete="${escapeHtml(comment.id)}"`, "paper-comment-btn--danger", { iconOnly: true })}
        </footer>
      </div>
    </article>
  </div>`;
}

function paperCommentComposeHtml() {
  const start = paperState.selectedLineStart;
  if (!start) return "";
  const lineTop = selectionAnchorTop();
  return `<div class="paper-comment-anchor is-compose is-active" data-compose="1" data-line-no="${start}" data-line-top="${lineTop}" style="top:${lineTop}px">
    <article class="paper-comment-card paper-comment-card--compose">
      <div class="paper-comment-card__rail" aria-hidden="true"></div>
      <div class="paper-comment-card__content">
        <header class="paper-comment-card__head">
          <span class="paper-comment-card__badge">Новый комментарий</span>
          <span class="paper-comment-card__status is-compose">Draft</span>
        </header>
        <p class="paper-comment-card__range">${escapeHtml(paperSelectionLabel())}</p>
        <textarea class="paper-comment-compose-body" rows="3" placeholder="Комментарий для агента…" data-paper-compose-body="1"></textarea>
        <footer class="paper-comment-card__actions paper-comment-card__actions--compact">
          ${paperCommentBtn("Сохранить", PAPER_COMMENT_ICONS.save, `data-paper-compose-save="1"`, "paper-comment-btn--primary", { iconOnly: true })}
          ${paperCommentBtn("Отмена", PAPER_COMMENT_ICONS.cancel, `data-paper-compose-cancel="1"`, "", { iconOnly: true })}
        </footer>
      </div>
    </article>
  </div>`;
}

function bindPaperCommentMarginEvents() {
  const margin = paperEls().commentMargin;
  if (!margin) return;

  margin.querySelectorAll(".paper-comment-anchor.is-collapsed[data-comment-id]").forEach((anchor) => {
    anchor.addEventListener("click", () => {
      focusPaperComment(anchor.getAttribute("data-comment-id"), { scroll: false });
    });
  });

  margin.querySelector("[data-paper-compose-save]")?.addEventListener("click", () => {
    void savePaperComment();
  });
  margin.querySelector("[data-paper-compose-cancel]")?.addEventListener("click", () => {
    closePaperCommentCompose();
  });
  margin.querySelector("[data-paper-compose-body]")?.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void savePaperComment();
    }
  });

  margin.querySelectorAll("[data-paper-thread-copy]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      void copyPaperCommentLink(btn.getAttribute("data-paper-thread-copy"), btn);
    });
  });
  margin.querySelectorAll("[data-paper-thread-send]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      void replyPaperComment(btn.getAttribute("data-paper-thread-send"));
    });
  });
  margin.querySelectorAll("[data-paper-thread-resolve]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      const comment = paperState.comments.find((item) => item.id === btn.getAttribute("data-paper-thread-resolve"));
      void togglePaperCommentResolved(btn.getAttribute("data-paper-thread-resolve"), !comment?.resolved);
    });
  });
  margin.querySelectorAll("[data-paper-thread-delete]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      void deletePaperComment(btn.getAttribute("data-paper-thread-delete"));
    });
  });
}

async function renderPaperCommentMargin() {
  const els = paperEls();
  if (!els.commentMargin) return;
  syncPaperLayoutMetrics();

  const staleChecks = await Promise.all(
    paperState.comments.map(async (comment) => {
      const { start, end, charStart, charEnd } = commentAnchorMeta(comment);
      const current = await paperContentHash(start, end, charStart, charEnd);
      return [comment.id, comment.anchor?.content_hash && current !== comment.anchor.content_hash];
    })
  );
  const staleById = new Map(staleChecks);

  const comments = [...(paperState.comments || [])].sort(
    (a, b) => commentLinesFor(a).start - commentLinesFor(b).start
  );
  if (els.commentsCount) els.commentsCount.textContent = String(comments.length);

  const composeDraft = paperState.composeOpen
    ? els.commentMargin?.querySelector("[data-paper-compose-body]")?.value || ""
    : "";
  const replyDrafts = new Map();
  els.commentMargin?.querySelectorAll("[data-paper-thread-reply]").forEach((field) => {
    if (field.value) replyDrafts.set(field.getAttribute("data-paper-thread-reply"), field.value);
  });

  const parts = [];
  if (paperState.composeOpen) parts.push(paperCommentComposeHtml());
  for (const comment of comments) {
    const expanded = comment.id === paperState.activeCommentId && !paperState.composeOpen;
    parts.push(
      paperCommentAnchorHtml(comment, {
        expanded,
        stale: Boolean(staleById.get(comment.id)),
      })
    );
  }
  els.commentMargin.innerHTML = parts.join("");
  if (composeDraft) {
    const field = els.commentMargin.querySelector("[data-paper-compose-body]");
    if (field) field.value = composeDraft;
  }
  replyDrafts.forEach((value, commentId) => {
    const field = els.commentMargin.querySelector(
      `[data-paper-thread-reply="${commentId}"]`
    );
    if (field) field.value = value;
  });
  layoutPaperCommentAnchors();
  bindPaperCommentMarginEvents();
}

function scrollPaperToComment(commentId) {
  const els = paperEls();
  const comment = paperState.comments.find((item) => item.id === commentId);
  if (!comment || !els.texScroll) return;
  const top = commentAnchorTop(comment);
  els.texScroll.scrollTop = Math.max(0, top - 48);
}

function focusPaperComment(commentId, { scroll = true } = {}) {
  if (!commentId) return;
  paperState.composeOpen = false;
  paperState.activeCommentId = commentId;
  const comment = paperState.comments.find((item) => item.id === commentId);
  if (comment) {
    const anchor = commentAnchorMeta(comment);
    selectPaperLines(anchor.start, anchor.end, anchor);
  }
  void renderPaperTexEditor().then(() => {
    if (scroll) scrollPaperToComment(commentId);
  });
}

async function loadPaperComments(projectId, slug) {
  try {
    const data = await KoiApi.getPaperComments(projectId, slug);
    paperState.comments = Array.isArray(data?.comments) ? data.comments : [];
  } catch {
    paperState.comments = [];
  }
  await renderPaperCommentMargin();
}

async function loadPaperTex(projectId, slug, { force = false } = {}) {
  const key = paperViewerKey(projectId, slug);
  if (!force && paperState.lastTexKey === key && paperEls().texInput && !paperState.texDirty) {
    await renderPaperTexEditor();
    return;
  }
  const text = await KoiApi.getPaperTex(projectId, slug);
  paperState.lastTexKey = key;
  setTexEditorContent(text, { markClean: true });
  await syncPaperTexRemoteMtime(projectId, slug);
  dismissPaperTexExternalChange();
}

async function loadPaperWorkspace(projectId, slug, { pdfExists = false, pdfStamp = "" } = {}) {
  const els = paperEls();
  let texLoaded = false;
  try {
    await loadPaperTex(projectId, slug);
    texLoaded = true;
  } catch {
    paperState.texText = "";
    paperState.texLines = [];
  }
  await loadPaperComments(projectId, slug);

  if (pdfExists) {
    paperState.lastRemotePdfMtime = pdfStamp || null;
    showPaperPdf(projectId, slug, pdfStamp);
    els.frame?.classList.remove("hidden");
    els.pdfMissing?.classList.add("hidden");
  } else {
    paperState.lastRemotePdfMtime = null;
    paperState.lastPdfStamp = null;
    if (els.frame) els.frame.src = "about:blank";
    els.frame?.classList.add("hidden");
    els.pdfMissing?.classList.toggle("hidden", false);
  }

  if (texLoaded || pdfExists) {
    setPaperViewerVisible({ split: true, empty: false });
  } else {
    setPaperViewerVisible({ split: false, empty: true });
  }

  if (paperState.pendingDeepLink?.commentId) {
    focusPaperComment(paperState.pendingDeepLink.commentId);
  } else if (paperState.activeCommentId) {
    focusPaperComment(paperState.activeCommentId);
  }
  paperState.pendingDeepLink = null;
}

async function copyPaperCommentLink(commentId, triggerBtn = null) {
  const entry = activePaperEntry();
  const comment = paperState.comments.find((item) => item.id === commentId);
  if (!entry || !comment) return false;
  const text = paperCommentClipboardText(entry.project_id, entry.slug, comment);
  try {
    await navigator.clipboard.writeText(text);
    showPaperToast("Скопировано — вставьте агенту в Cursor");
    markPaperCopyButton(triggerBtn, true);
    return true;
  } catch {
    showPaperToast("Не удалось скопировать", { variant: "error" });
    return false;
  }
}

function openPaperCommentCompose() {
  if (!paperState.selectedLineStart) return;
  paperState.composeOpen = true;
  paperState.activeCommentId = null;
  updatePaperSelectionUi();
  void renderPaperTexEditor().then(() => {
    const start = paperState.selectedLineStart;
    if (start) scrollPaperToLine(start);
    paperEls().commentMargin?.querySelector("[data-paper-compose-body]")?.focus();
  });
}

function scrollPaperToLine(lineNo) {
  const els = paperEls();
  if (!els.texScroll) return;
  const top = measurePaperLineTop(lineNo);
  els.texScroll.scrollTop = Math.max(0, top - 48);
}

function closePaperCommentCompose() {
  paperState.composeOpen = false;
  updatePaperSelectionUi();
  void renderPaperCommentMargin();
}

async function savePaperComment() {
  const entry = activePaperEntry();
  const els = paperEls();
  const body = els.commentMargin
    ?.querySelector("[data-paper-compose-body]")
    ?.value?.trim();
  if (!entry || !body || !paperState.selectedLineStart) return;
  try {
    const payload = {
      line_start: paperState.selectedLineStart,
      line_end: paperState.selectedLineEnd || paperState.selectedLineStart,
      body,
      author: "reviewer",
    };
    if (paperState.selectedCharStart != null) payload.char_start = paperState.selectedCharStart;
    if (paperState.selectedCharEnd != null) payload.char_end = paperState.selectedCharEnd;
    if (paperState.selectedText) payload.selected_text = paperState.selectedText;
    const res = await KoiApi.createPaperComment(entry.project_id, entry.slug, payload);
    if (res?.comment) {
      paperState.comments.push(res.comment);
      paperState.activeCommentId = res.comment.id;
    }
    paperState.composeOpen = false;
    await renderPaperTexEditor();
    void copyPaperCommentLink(paperState.activeCommentId);
  } catch (err) {
    if (els.status) els.status.textContent = `Не удалось сохранить комментарий: ${err.message}`;
  }
}

async function replyPaperComment(commentId) {
  const entry = activePaperEntry();
  const els = paperEls();
  const textarea = els.commentMargin?.querySelector(
    `[data-paper-thread-reply="${commentId}"]`
  );
  const body = textarea?.value?.trim();
  if (!entry || !body) return;
  try {
    const res = await KoiApi.replyPaperComment(entry.project_id, entry.slug, commentId, {
      body,
      author: "reviewer",
    });
    const comment = paperState.comments.find((item) => item.id === commentId);
    if (comment && res?.message) {
      comment.thread = [...(comment.thread || []), res.message];
    }
    if (textarea) textarea.value = "";
    await renderPaperCommentMargin();
  } catch (err) {
    if (els.status) els.status.textContent = `Не удалось отправить ответ: ${err.message}`;
  }
}

async function togglePaperCommentResolved(commentId, resolved) {
  const entry = activePaperEntry();
  try {
    const res = await KoiApi.resolvePaperComment(entry.project_id, entry.slug, commentId, resolved);
    const comment = paperState.comments.find((item) => item.id === commentId);
    if (comment && res?.comment) Object.assign(comment, res.comment);
    await renderPaperCommentMargin();
  } catch (err) {
    if (paperEls().status) paperEls().status.textContent = `Не удалось обновить комментарий: ${err.message}`;
  }
}

async function deletePaperComment(commentId) {
  const entry = activePaperEntry();
  if (!window.confirm("Удалить комментарий?")) return;
  try {
    await KoiApi.deletePaperComment(entry.project_id, entry.slug, commentId);
    paperState.comments = paperState.comments.filter((item) => item.id !== commentId);
    if (paperState.activeCommentId === commentId) paperState.activeCommentId = null;
    await renderPaperTexEditor();
  } catch (err) {
    if (paperEls().status) paperEls().status.textContent = `Не удалось удалить: ${err.message}`;
  }
}

function capturePaperDeepLinkFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get("paper");
  const commentId = params.get("paper_comment");
  if (!slug) return;
  paperState.pendingDeepLink = { slug, commentId: commentId || null };
}

function maybeOpenPaperFromDeepLink() {
  if (!paperState.pendingDeepLink || !state.project) return;
  const projectId = paperScopeProjectIds()[0];
  if (!projectId) return;
  const slug = paperState.pendingDeepLink.slug;
  paperState.activeKey = `${projectId}:${slug}`;
  openPaperModal();
}

function showPaperPdf(projectId, slug, stamp) {
  const els = paperEls();
  bindPaperFrameLoad();
  const url = `${KoiApi.paperPdfUrl(projectId, slug)}#view=FitH`;
  const cacheKey = `${projectId}:${slug}:${stamp || ""}`;
  const tabKey = paperTabKey({ project_id: projectId, slug });
  if (paperState.lastPdfStamp === cacheKey && paperState.lastPdfKey === tabKey && els.frame?.src && els.frame.src !== "about:blank") {
    els.frame.classList.remove("hidden");
    els.pdfMissing?.classList.add("hidden");
    els.pdfLink.href = url;
    els.pdfLink.classList.remove("hidden");
    els.texLink.href = KoiApi.paperTexUrl(projectId, slug);
    els.texLink.classList.remove("hidden");
    return;
  }
  showPaperLoader("Загрузка PDF…");
  els.frame?.classList.add("hidden");
  if (els.frame) els.frame.src = `${KoiApi.paperPdfUrl(projectId, slug)}?t=${encodeURIComponent(stamp || "")}#view=FitH`;
  paperState.lastPdfStamp = cacheKey;
  paperState.lastPdfKey = tabKey;
  els.pdfLink.href = url;
  els.pdfLink.classList.remove("hidden");
  els.texLink.href = KoiApi.paperTexUrl(projectId, slug);
  els.texLink.classList.remove("hidden");
}

function renderPaperState(st) {
  const els = paperEls();
  const entry = activePaperEntry();
  if (!entry || !els.modal) return;

  const projectId = entry.project_id;
  const slug = st.slug || entry.slug || "default";
  paperState.activeKey = paperTabKey({ ...entry, slug });
  if (els.title) els.title.textContent = entry.title || state.project.title;

  const running = st.state === "running";
  els.generate.disabled = running;
  els.regenerate.disabled = running;
  els.generate.classList.toggle("hidden", st.pdf_exists || running);
  els.regenerate.classList.toggle("hidden", !(st.pdf_exists || running));

  if (running) {
    const step = isInboxAgentMode()
      ? "Paper Inbox пишет статью…"
      : "Генерация статьи…";
    showPaperLoader(step);
    setPaperViewerVisible({ split: false, empty: false });
    els.status.textContent = "";
    if (st.tex_exists) {
      els.texLink.href = KoiApi.paperTexUrl(projectId, slug);
      els.texLink.classList.remove("hidden");
    }
  } else {
    hidePaperLoader();
    if (st.pdf_exists || st.tex_exists) {
      void loadPaperWorkspace(projectId, slug, {
        pdfExists: Boolean(st.pdf_exists),
        pdfStamp: st.pdf_mtime,
      });
    } else {
      setPaperViewerVisible({ split: false, empty: true });
      els.pdfLink.classList.add("hidden");
      els.texLink.classList.add("hidden");
    }
  }

  if (!running && st.state === "error") {
    const hint = st.log_tail ? ` · ${String(st.log_tail).split("\n")[0]}` : "";
    els.status.textContent = `Ошибка: ${st.error || "не удалось сгенерировать статью"}${hint}`;
    els.empty.textContent = "Статья не сгенерирована — попробуйте ещё раз.";
    setPaperViewerVisible({ split: false, empty: true });
  } else if (!running && st.state === "done" && st.pdf_exists) {
    const when = st.finished_at ? ` · ${new Date(st.finished_at).toLocaleString()}` : "";
    const how = st.mode === "agent" ? `агент (${st.backend || "LLM"})` : "автосборка из графа";
    els.status.textContent = `Готово: ${how}${when}`;
  } else if (!running) {
    els.status.textContent = "";
    if (st.tex_exists && !st.pdf_exists) {
      els.empty.textContent =
        entry.description ||
        "PDF не найден — откройте main.tex или положите paper.pdf в папку статьи.";
      els.texLink.href = KoiApi.paperTexUrl(projectId, slug);
      els.texLink.classList.remove("hidden");
    } else if (!st.pdf_exists && !st.tex_exists) {
      els.empty.textContent = entry.description || "Статья ещё не генерировалась.";
      setPaperViewerVisible({ split: false, empty: true });
    }
  }
}

async function refreshPaperStatus({ quiet = false } = {}) {
  const entry = activePaperEntry();
  if (!entry) return;
  if (!quiet) {
    const cached = paperState.papers.find((paper) => paperTabKey(paper) === paperTabKey(entry));
    if (cached) renderPaperFromEntry(cached);
  }
  try {
    const st = await KoiApi.getPaperStatus(entry.project_id, entry.slug);
    const idx = paperState.papers.findIndex((paper) => paperTabKey(paper) === paperTabKey(entry));
    if (idx >= 0) {
      paperState.papers[idx] = { ...paperState.papers[idx], ...st, project_id: entry.project_id };
    }
    renderPaperTabs();
    renderPaperState(st);
    renderPaperProgress(paperState.papers.find((paper) => paperTabKey(paper) === paperTabKey(entry)) || entry);
    const modalOpen = !paperEls().modal?.classList.contains("hidden");
    if (st.state === "running" && modalOpen) {
      if (!paperState.pollTimer) {
        paperState.pollTimer = setInterval(() => {
          void refreshPaperStatus({ quiet: true });
        }, 4000);
      }
    } else {
      stopPaperPolling();
    }
  } catch (err) {
    stopPaperPolling();
    hidePaperLoader();
    const els = paperEls();
    if (els.status) els.status.textContent = `Ошибка статуса: ${err.message}`;
  }
}

async function requestPaperGeneration() {
  const entry = activePaperEntry();
  const projectId = entry?.project_id || paperScopeProjectIds()[0];
  if (!projectId) return;
  const slug = entry?.slug || "default";
  const els = paperEls();
  els.generate.disabled = true;
  els.regenerate.disabled = true;
  els.status.textContent = "";
  showPaperLoader("Запуск генерации…");
  setPaperViewerVisible({ split: false, empty: false });
  try {
    const res = await KoiApi.generatePaper(projectId, slug);
    if (res?.inbox_message && isInboxAgentMode() && !isPaperInboxConfigured()) {
      lastPaperInboxMessage = res.inbox_message;
      paperInboxBootstrapCopied = false;
      updatePaperInboxNotice();
      void copyPaperInboxBootstrap(document.getElementById("paper-inbox-message-status"));
    }
    await loadProjectPapers();
    if (res?.slug) paperState.activeKey = `${projectId}:${res.slug}`;
    renderPaperTabs();
  } catch (err) {
    hidePaperLoader();
    setPaperViewerVisible({ split: false, empty: true });
    els.status.textContent = `Не удалось запустить генерацию: ${err.message}`;
    els.generate.disabled = false;
    els.regenerate.disabled = false;
    return;
  }
  void refreshPaperStatus();
}

function openPaperModal() {
  if (!state.project) return;
  const els = paperEls();
  bindPaperFrameLoad();
  paperState.lastPdfStamp = null;
  paperState.lastPdfKey = null;
  paperState.lastRemotePdfMtime = null;
  if (els.frame) els.frame.src = "about:blank";
  showPaperLoader("Загрузка статей…");
  void refreshAppSettings().then(() => {
    if (isInboxAgentMode() && !isPaperInboxConfigured() && appSettings.paper_inbox_bootstrap_prompt) {
      lastPaperInboxMessage = appSettings.paper_inbox_bootstrap_prompt;
    }
    updatePaperInboxNotice();
  });
  showModal("paper-modal");
  void loadProjectPapers()
    .then(() => {
      hidePaperLoader();
      renderPaperTabs();
      renderPaperFromEntry(activePaperEntry());
      return refreshPaperStatus({ quiet: true });
    })
    .catch((err) => {
      hidePaperLoader();
      const statusEl = paperEls().status;
      if (statusEl) statusEl.textContent = `Не удалось загрузить статьи: ${err.message}`;
    });
}

function initPaper() {
  capturePaperDeepLinkFromUrl();
  bindPaperTexEditor();
  document.getElementById("btn-paper")?.addEventListener("click", openPaperModal);
  document.getElementById("btn-paper-generate")?.addEventListener("click", () => {
    void requestPaperGeneration();
  });
  document.getElementById("btn-paper-regenerate")?.addEventListener("click", () => {
    void requestPaperGeneration();
  });
  document.getElementById("btn-paper-comment-add")?.addEventListener("click", () => {
    openPaperCommentCompose();
  });
  document.getElementById("btn-paper-tex-save")?.addEventListener("click", () => {
    void savePaperTex();
  });
  document.getElementById("btn-paper-tex-compile")?.addEventListener("click", () => {
    void compilePaperPdf();
  });
  document.getElementById("btn-paper-tex-reload")?.addEventListener("click", () => {
    void (async () => {
      if (paperState.pendingRemoteTexMtime != null) {
        paperState.lastRemoteTexMtime = paperState.pendingRemoteTexMtime;
      }
      await reloadPaperTexFromDisk();
    })();
  });
  document.getElementById("btn-paper-tex-keep-local")?.addEventListener("click", () => {
    if (paperState.pendingRemoteTexMtime != null) {
      paperState.lastRemoteTexMtime = paperState.pendingRemoteTexMtime;
    }
    dismissPaperTexExternalChange();
  });
  document.getElementById("paper-inbox-message-copy")?.addEventListener("click", () => {
    void copyPaperInboxBootstrap(document.getElementById("paper-inbox-message-status"));
  });
  document.getElementById("paper-inbox-mark-configured")?.addEventListener("click", () => {
    void markPaperInboxConfigured().then((ok) => {
      const status = document.getElementById("paper-inbox-message-status");
      if (ok && status) status.textContent = "Paper Inbox отмечен как настроенный.";
    });
  });
  paperEls().progressSettingsToggle?.addEventListener("click", () => {
    paperState.progressSettingsOpen = !paperState.progressSettingsOpen;
    renderPaperProgress(activePaperEntry());
  });
  paperEls().progressSettings?.addEventListener("submit", (event) => {
    void savePaperProgress(event);
  });
}

function initKnowledge() {
  document.getElementById("btn-knowledge")?.addEventListener("click", openKnowledgeModal);
  document.getElementById("knowledge-tab-index")?.addEventListener("click", () => {
    knowledgeState.tab = "index";
    knowledgeState.docPath = null;
    void loadKnowledgeTab();
  });
  document.getElementById("knowledge-tab-log")?.addEventListener("click", () => {
    knowledgeState.tab = "log";
    void loadKnowledgeTab();
  });
  document.getElementById("knowledge-back")?.addEventListener("click", () => {
    knowledgeState.docPath = null;
    void loadKnowledgeTab();
  });
}

async function init() {
  const hubMode = isHubMode();
  initImageLightbox();
  if (!hubMode) initCursorUsageWidget();
  if (!hubMode) {
    initKnowledge();
    initPaper();
  }
  initTheme();
  initTaglineRotation();
  if (!hubMode) {
    initSync();
    initProjectDiscoveryPoll();
    initSettings();
    initAgentChat();
  } else {
    applyHubReadonlyChrome();
  }
  initKanbanViewTabs();
  initKanbanModalChrome();
  if (!hubMode) bindCardLiveModal(cardLiveUi);
  document.querySelectorAll("[data-close]").forEach((el) => {
    el.addEventListener("click", () => {
      if (el.dataset.close === "card-report-modal") {
        void closeReportModal();
        return;
      }
      if (el.dataset.close === "paper-modal") {
        if (paperState.texDirty && !window.confirm("Есть несохранённые изменения в main.tex. Закрыть без сохранения?")) {
          return;
        }
        stopPaperPollingAll();
      }
      hideModal(el.dataset.close);
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (document.activeElement?.classList.contains("inline-edit-field")) return;
      const reportModal = document.getElementById("card-report-modal");
      if (!reportModal.classList.contains("hidden")) {
        void closeReportModal();
        return;
      }
      const paperModal = document.getElementById("paper-modal");
      if (paperModal && !paperModal.classList.contains("hidden")) {
        if (paperState.texDirty && !window.confirm("Есть несохранённые изменения в main.tex. Закрыть без сохранения?")) {
          return;
        }
        hideModal("paper-modal");
        stopPaperPollingAll();
        return;
      }
      hideModal("create-project-modal");
      hideModal("settings-modal");
      hideModal("node-modal");
      hideModal("kanban-modal");
      hideModal("method-questions-modal");
      hideModal("card-live-modal");
      hideModal("knowledge-modal");
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      const paperModal = document.getElementById("paper-modal");
      const paperOpen = paperModal && !paperModal.classList.contains("hidden");
      if (paperOpen && paperState.texDirty) {
        e.preventDefault();
        void savePaperTex();
        return;
      }
      if (document.activeElement?.id === "card-report-editor") {
        e.preventDefault();
        void saveCardReport();
      }
    }
  });
  document.getElementById("card-report-save").addEventListener("click", () => {
    void saveCardReport(true);
  });
  document
    .getElementById("card-report-mode-write")
    ?.addEventListener("click", () => setReportViewMode("write"));
  document
    .getElementById("card-report-mode-view")
    ?.addEventListener("click", () => setReportViewMode("view"));
  document.getElementById("card-report-editor").addEventListener("input", () => {
    state.reportDirty = true;
    scheduleReportPreview();
  });
  const reportEditor = document.getElementById("card-report-editor");
  reportEditor?.addEventListener("paste", (e) => {
    void onReportEditorPaste(e);
  });
  document.getElementById("card-report-modal")?.addEventListener(
    "paste",
    (e) => {
      if (e.target.id === "card-report-editor") return;
      void onReportEditorPaste(e);
    },
    true
  );

  if (!hubMode) setupInlineEdits();
  document.getElementById("add-child-form").addEventListener("submit", onAddChildSubmit);
  document.getElementById("btn-delete-node").addEventListener("click", onDeleteNode);
  document.getElementById("btn-add-method")?.addEventListener("click", (e) => {
    e.preventDefault();
    const node = state.project?.nodes?.find((n) => n.id === state.activeNodeId);
    if (node) openAddChildModal(node);
  });
  document.getElementById("btn-toggle-rq-edit")?.addEventListener("click", () => {
    toggleMethodQuestionsEdit();
  });
  document.getElementById("btn-save-rq")?.addEventListener("click", () => {
    void saveMethodQuestions();
  });
  initProjectsSidebar();
  initCreateProjectModal();
  initMindmapResizeObserver();
  initViewControls();

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(scheduleMindmapRender, 120);
  });

  try {
    state.meta = await KoiApi.meta();
    let requestedProjectId = new URLSearchParams(window.location.search).get("project");
    if (hubMode) {
      requestedProjectId = await resolveHubProjectId();
    }
    await loadLab();
    const preferred = resolvePreferredProjectId(
      requestedProjectId,
      state.lab.grouped,
      state.lab.projectsById
    );
    if (!preferred) {
      setStatus(
        hubMode
          ? "Не удалось загрузить снимок проекта"
          : "Нет обнаруженных проектов (ищем */koi-structure/)",
        true
      );
      return;
    }
    state.project = state.lab.projectsById[preferred];
    if (!state.project) {
      state.project = isCompositeVirtualId(preferred)
        ? await KoiApi.getComposite(preferred.slice("composite:".length))
        : await KoiApi.getProject(preferred);
      state.lab.projectsById[preferred] = state.project;
    }
    syncLabProject(state.project);
    const list = await loadProjectList(preferred);
    if (!list.length) {
      setStatus("Нет обнаруженных проектов (ищем */koi-structure/)", true);
      return;
    }
    setActiveProjectInList(preferred);
    const mode = getViewMode();
    renderLabMindmap({
      fitLab: mode === "chief",
      fitProgram: mode === "teamlead",
      flyToProjectId: mode === "researcher" ? preferred : null,
    });
    updatePaperReviewLink();
    updateAgentChatScope();
    void refreshAgentChat();
    maybeOpenPaperFromDeepLink();
  } catch (err) {
    console.error("ResearchOS init failed:", err);
    setStatus(
      hubMode
        ? `Hub: ${err.message}`
        : `Не удалось загрузить: ${err.message}. Проверьте API на ${KoiApi.baseUrl?.() ?? "порту 8010"} (scripts/koi-serve.sh start).`,
      true
    );
  }
}

init().catch((err) => {
  console.error(err);
  setStatus(`Ошибка UI: ${err.message}`, true);
});
