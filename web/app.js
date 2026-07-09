import {
  bindCardLiveModal,
  bindLiveInspectButtons,
  cardHasLiveHints,
  cardHasLiveHintsFromSources,
  runningCardContextsFromProjects,
  setRunningSeedProvider,
} from "./card-live.js";
import { KoiApi } from "./api.js?v=20260701c";
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

const MAX_RESEARCH_QUESTIONS = 3;
const RQ_BADGE_HOLD_MS = 2500;
const RQ_BADGE_FADE_MS = 5_000;

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
  return {
    projectTitle: project?.title || pid || "",
    authors: pid ? runningAuthorsByProject.get(pid) || {} : {},
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
    const data = await KoiApi.getKanbanRunningActivity(projectId);
    const authors = Object.fromEntries(
      (data.items || []).map((item) => [item.card_id, item.author || "коллега"])
    );
    runningAuthorsByProject.set(projectId, authors);
    return authors;
  } catch {
    return runningAuthorsByProject.get(projectId) || {};
  }
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
  return items.filter((item) => scope.has(item.key.split(":")[0]));
}

function labCameraLayout() {
  return labWorldLayoutFull || labWorldLayout;
}

function refreshAllMethodActivityAuthors() {
  const ids = new Set(runningAuthorsByProject.keys());
  for (const item of collectAllRunningActivityItems()) {
    const pid = item.key.split(":")[0];
    if (pid) ids.add(pid);
  }
  for (const pid of ids) refreshMethodActivityAuthors(pid);
  syncLabActivityOverlay();
}

async function preloadAllRunningAuthors() {
  if (!state.lab?.projectsById) return;
  const ids = new Set();
  for (const item of collectAllRunningActivityItems()) {
    const pid = item.key.split(":")[0];
    if (pid) ids.add(pid);
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
  if (showOverlay && overlayRebuilt) {
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
  bindMethodLiveInspect(below, node, board, project);
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
    setDisplay: (v) =>
      renderInlineDisplay(
        document.getElementById("kanban-node-desc-display"),
        v,
        "Описание (двойной клик)"
      ),
    onCommit: async (description) => {
      const updated = await patchNodeFields(state.kanbanNodeId, {
        description,
      });
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
  const importance = formatImportance(q.importance);
  return `
    <article class="method-question-item">
      ${researchQuestionCardSourceHtml(q, node)}
      <p class="method-question-q">${escapeHtml(q.question)}</p>
      <p class="method-question-meta">Важность: ${importance}</p>
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

function renderMethodQuestionsBody(node) {
  const body = document.getElementById("method-questions-body");
  const questions = node.research_questions || [];
  if (!questions.length) {
    body.innerHTML =
      '<p class="method-questions-empty">Пока нет выводов по экспериментам этого метода.</p>';
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
  document.getElementById("btn-save-rq")?.classList.add("hidden");
  document
    .querySelector("#method-questions-modal .modal-panel--questions")
    ?.classList.remove("is-editing");
  const toggle = document.getElementById("btn-toggle-rq-edit");
  if (toggle) toggle.textContent = "Редактировать";
}

function updateAddResearchQuestionButton() {
  const addBtn = document.getElementById("btn-add-rq-row");
  const count = document.querySelectorAll(
    "#method-questions-edit .method-rq-edit-row"
  ).length;
  if (addBtn) addBtn.disabled = count >= MAX_RESEARCH_QUESTIONS;
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
    <p class="method-questions-edit-hint">До ${MAX_RESEARCH_QUESTIONS} вопросов · ▶ развернуть детали · двойной клик — редактировать поле</p>
    <div id="method-rq-edit-list" class="method-rq-edit-list"></div>
    <button type="button" id="btn-add-rq-row" class="btn">+ Вопрос</button>`;
  const list = edit.querySelector("#method-rq-edit-list");
  for (const q of node.research_questions || []) {
    list.appendChild(createResearchQuestionEditRow(q, node));
  }
  edit.querySelector("#btn-add-rq-row").addEventListener("click", () => {
    if (list.querySelectorAll(".method-rq-edit-row").length >= MAX_RESEARCH_QUESTIONS) return;
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
  if (questions.length > MAX_RESEARCH_QUESTIONS) {
    setStatus(`Не больше ${MAX_RESEARCH_QUESTIONS} вопросов на метод`, true);
    return;
  }
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

  document.getElementById("kanban-modal-type").textContent =
    TYPE_LABELS[node.node_type];
  fillKanbanNodeMeta(node);

  renderKanbanBoard(board);
  showModal("kanban-modal");
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
    await KoiApi.patchCard(boardWriteProjectId(board), board.id, cardId, fields);
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    setStatus("Сохранено в project.md");
    if (rerenderKanban) {
      const node = state.project.nodes.find((n) => n.id === state.kanbanNodeId);
      if (node?.board_id) {
        renderKanbanBoard(state.project.boards[node.board_id]);
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

function projectCardTagVocabulary(project) {
  const seen = new Map();
  const add = (tag) => {
    const norm = normalizeCardTagName(tag);
    if (!norm) return;
    const key = norm.toLowerCase();
    if (!seen.has(key)) seen.set(key, norm);
  };
  (project?.card_tags || []).forEach(add);
  Object.values(project?.boards || {}).forEach((board) => {
    (board.cards || []).forEach((card) => {
      (card.tags || []).forEach(add);
    });
  });
  return [...seen.values()].sort((a, b) => a.localeCompare(b, "ru"));
}

function cardTagsEqual(a, b) {
  const norm = (arr) => [...(arr || [])].map((t) => t.toLowerCase()).sort();
  const aa = norm(a);
  const bb = norm(b);
  return aa.length === bb.length && aa.every((v, i) => v === bb[i]);
}

function cardTagsRowHtml(tags, { kanban = false } = {}) {
  const list = tags || [];
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
  const vocabulary = projectCardTagVocabulary(state.project);
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
  const map = variant === "map";
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
            ${cardTagsRowHtml(c.tags, { kanban: true })}
            <div class="kanban-card-actions">
              ${copyBtn}
              <button type="button" class="card-expand-report card-action-btn" title="Открыть отчёт" aria-label="Открыть отчёт">
                <svg class="card-action-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M15 3h6v6M10 14L21 3M21 14v7h-7"/></svg>
              </button>
            </div>
          </div>
        </div>`;
}

function kanbanBoardHtml(board, variant = "modal") {
  return (board.columns || [])
    .map((col) => {
      const cards = board.cards.filter((c) => c.column_id === col.id);
      const cardsHtml = cards.map((c) => kanbanCardHtml(c, col, variant)).join("");
      return `
        <div class="kanban-col" data-col="${col.id}">
          <div class="kanban-col-head">
            <h3>
              <span class="col-title">${escapeHtml(col.title)}</span>
              <span class="col-count-inline">${cards.length}</span>
            </h3>
            <button type="button" class="col-add-btn" title="Добавить карточку" aria-label="Добавить карточку в ${escapeHtml(col.title)}">+</button>
          </div>
          <div class="kanban-col-body">
            ${cardsHtml || '<span class="col-empty">Перетащите сюда</span>'}
          </div>
        </div>`;
    })
    .join("");
}

function renderKanbanBoardInto(boardEl, board, { variant = "modal", node = null, project = null } = {}) {
  if (!boardEl || !board) return;
  boardEl.innerHTML = kanbanBoardHtml(board, variant);
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
  if (liveCtx) {
    bindLiveInspectButtons(boardEl, liveCtx, cardLiveUi);
  }
}

function renderKanbanBoard(board) {
  const boardEl = document.getElementById("kanban-board");
  if (!boardEl) return;
  renderKanbanBoardInto(boardEl, board, { variant: "modal" });
}

function bindKanbanColumnActions(boardEl, board, context = {}) {
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
  if (context.project) state.project = context.project;
  const node = context.node ||
    state.project.nodes.find((n) => n.id === state.kanbanNodeId);
  if (!node?.board_id) return;
  const beforeIds = new Set(board.cards.map((c) => c.id));
  setStatus("Добавление…");
  try {
    await KoiApi.addCard(boardWriteProjectId(board), node.board_id, {
      title: "Новый эксперимент",
      column_id: columnId,
      description: "",
    });
    state.project = await reloadProjectView();
    syncLabProject(state.project);
    setStatus("Сохранено в project.md");
    const updatedBoard = state.project.boards[node.board_id];
    renderKanbanBoard(updatedBoard);
    if (state.kanbanNodeId) refreshKanbanBelowForNode(state.kanbanNodeId);
    refreshMapKanbansForProject(state.project.id, node.id);
    const newCard = updatedBoard.cards.find(
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
    hint: "На экране — вся лаборатория · колёсико — масштаб до карточек метода · перетаскивание — панорама",
  },
  teamlead: {
    id: "teamlead",
    label: "Team lead researcher",
    hint: "На экране — программа выбранного проекта · список слева — полный",
  },
  researcher: {
    id: "researcher",
    label: "Researcher",
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
  if (!board || !isCompositeView()) return state.project?.id;
  if (board.source_project_id) return board.source_project_id;
  const owner = state.project?.nodes?.find((n) => n.id === board.owner_node_id);
  return nodeWriteProjectId(owner);
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
    "Загрузите настройки (обновите страницу) или выполните: python scripts/koi_agent_chat_inbox.py bootstrap";
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

/* --------------------- Статья по проекту (NeurIPS PDF) --------------------- */

const paperState = {
  pollTimer: null,
  lastPdfStamp: null,
  lastPdfKey: null,
  activeKey: null,
  papers: [],
};
const PAPER_INBOX_CONFIGURED_KEY = "koi_paper_inbox_configured";
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
    generate: document.getElementById("btn-paper-generate"),
    regenerate: document.getElementById("btn-paper-regenerate"),
    pdfLink: document.getElementById("paper-pdf-link"),
    texLink: document.getElementById("paper-tex-link"),
    status: document.getElementById("paper-status"),
    empty: document.getElementById("paper-empty"),
    frame: document.getElementById("paper-frame"),
  };
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
      paperState.activeKey = key;
      paperState.lastPdfStamp = null;
      paperState.lastPdfKey = null;
      if (paperEls().frame) paperEls().frame.src = "about:blank";
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
  });
  frame.addEventListener("error", () => {
    hidePaperLoader();
    const { status, empty } = paperEls();
    if (status) status.textContent = "Не удалось загрузить PDF в просмотрщике — откройте ссылку «Открыть PDF».";
    if (empty) empty.classList.remove("hidden");
  });
}

function stopPaperPolling() {
  if (paperState.pollTimer) {
    clearInterval(paperState.pollTimer);
    paperState.pollTimer = null;
  }
}

function showPaperLoader(step = "Генерация статьи…") {
  showKoiLoader("paper-loader", { step, pool: "paper" });
}

function hidePaperLoader() {
  hideKoiLoader("paper-loader");
}

function showPaperPdf(projectId, slug, stamp) {
  const els = paperEls();
  bindPaperFrameLoad();
  const url = `${KoiApi.paperPdfUrl(projectId, slug)}#view=FitH`;
  const cacheKey = `${projectId}:${slug}:${stamp || ""}`;
  const tabKey = paperTabKey({ project_id: projectId, slug });
  if (paperState.lastPdfStamp === cacheKey && paperState.lastPdfKey === tabKey && els.frame.src && els.frame.src !== "about:blank") {
    els.frame.classList.remove("hidden");
    els.empty.classList.add("hidden");
    els.pdfLink.href = url;
    els.pdfLink.classList.remove("hidden");
    els.texLink.href = KoiApi.paperTexUrl(projectId, slug);
    els.texLink.classList.remove("hidden");
    return;
  }
  showPaperLoader("Загрузка PDF…");
  els.frame.classList.add("hidden");
  els.frame.src = `${KoiApi.paperPdfUrl(projectId, slug)}?t=${encodeURIComponent(stamp || "")}#view=FitH`;
  paperState.lastPdfStamp = cacheKey;
  paperState.lastPdfKey = tabKey;
  els.empty.classList.add("hidden");
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
    els.frame.classList.add("hidden");
    els.empty.classList.add("hidden");
    els.status.textContent = "";
    if (st.tex_exists) {
      els.texLink.href = KoiApi.paperTexUrl(projectId, slug);
      els.texLink.classList.remove("hidden");
    }
  } else {
    hidePaperLoader();
    if (st.pdf_exists) {
      showPaperPdf(projectId, slug, st.pdf_mtime);
    } else {
      els.frame.classList.add("hidden");
      els.empty.classList.remove("hidden");
      els.pdfLink.classList.add("hidden");
      els.texLink.classList.toggle("hidden", !st.tex_exists);
      if (st.tex_exists) els.texLink.href = KoiApi.paperTexUrl(projectId, slug);
    }
  }

  if (!running && st.state === "error") {
    const hint = st.log_tail ? ` · ${String(st.log_tail).split("\n")[0]}` : "";
    els.status.textContent = `Ошибка: ${st.error || "не удалось сгенерировать статью"}${hint}`;
    els.empty.textContent = "Статья не сгенерирована — попробуйте ещё раз.";
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
    } else {
      els.empty.textContent = entry.description || "Статья ещё не генерировалась.";
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
  els.frame.classList.add("hidden");
  els.empty.classList.add("hidden");
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
    els.empty.classList.remove("hidden");
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
  document.getElementById("btn-paper")?.addEventListener("click", openPaperModal);
  document.getElementById("btn-paper-generate")?.addEventListener("click", () => {
    void requestPaperGeneration();
  });
  document.getElementById("btn-paper-regenerate")?.addEventListener("click", () => {
    void requestPaperGeneration();
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
  initImageLightbox();
  initKnowledge();
  initPaper();
  initTheme();
  initTaglineRotation();
  initSync();
  initProjectDiscoveryPoll();
  initSettings();
  initAgentChat();
  bindCardLiveModal(cardLiveUi);
  document.querySelectorAll("[data-close]").forEach((el) => {
    el.addEventListener("click", () => {
      if (el.dataset.close === "card-report-modal") {
        void closeReportModal();
        return;
      }
      if (el.dataset.close === "paper-modal") stopPaperPolling();
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
      hideModal("create-project-modal");
      hideModal("settings-modal");
      hideModal("node-modal");
      hideModal("kanban-modal");
      hideModal("method-questions-modal");
      hideModal("card-live-modal");
      hideModal("knowledge-modal");
      hideModal("paper-modal");
      stopPaperPolling();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
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

  setupInlineEdits();
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
    await loadLab();
    const requestedProjectId = new URLSearchParams(window.location.search).get("project");
    const preferred = resolvePreferredProjectId(
      requestedProjectId,
      state.lab.grouped,
      state.lab.projectsById
    );
    if (!preferred) {
      setStatus("Нет обнаруженных проектов (ищем */koi-structure/)", true);
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
  } catch (err) {
    console.error("ResearchOS init failed:", err);
    setStatus(
      `Не удалось загрузить: ${err.message}. Проверьте API на ${KoiApi.baseUrl?.() ?? "порту 8010"} (scripts/koi-serve.sh start).`,
      true
    );
  }
}

init().catch((err) => {
  console.error(err);
  setStatus(`Ошибка UI: ${err.message}`, true);
});
