import { KoiApi } from "./api.js?v=20260811e";
import { renderMarkdown } from "./markdown.js";

const THEME_STORAGE_KEY = "koi-theme";
const MORPH_HANDOFF_KEY = "koi-morph-paper";
const POLL_MS = 4000;
const SVG_NS = "http://www.w3.org/2000/svg";

const NODE_W = 234;
const NODE_H = 104;
const GAP_X = 84;
const GAP_Y = 26;

const ROLE_LABELS = {
  problem: "проблема",
  origin: "откуда берётся",
  symptom: "доказательство проблемы",
  gap: "разрыв",
  thesis: "тезис",
  assumption: "допущение",
  method_step: "шаг метода",
  mechanism: "механизм",
  experiment: "эксперимент",
  result: "результат",
  comparison: "сравнение",
  limitation: "ограничение",
  implication: "следствие",
};

const RELATION_LABELS = {
  causes: "вызывает",
  evidences: "доказывает",
  motivates: "мотивирует",
  contrasts: "противопоставлено",
  solves: "решает",
  measures: "измеряет",
  generalizes: "обобщает",
  limits: "ограничивает",
  assumes: "опирается на",
  enables: "делает возможным",
};

const GROUNDING_LABELS = {
  quoted: "дословная цитата",
  paraphrased: "пересказ",
  inferred: "прочтение агента",
};

const COVERAGE_LABELS = {
  full_text: "полный текст",
  partial_text: "часть текста",
  abstract_only: "только абстракт",
};

/** Hues for chapter accents — readable on both themes at 72%/60%. */
const CHAPTER_HUES = [190, 320, 265, 30, 95, 350, 220, 160, 55, 285];
const LAYOUT_STORAGE_PREFIX = "koi-morph-layout";

let projectId = "";
let paperUrl = "";
let paper = null;
let currentRun = null;
let allRuns = [];
let pollTimer = null;
let selectedNodeId = "";
let activeTab = "graph";
let viewTransform = { x: 40, y: 40, k: 1 };

let graphData = null;
let nodePositions = new Map();
let nodeIndex = new Map();
let chapterColors = new Map();
let chapterFilter = "";
const nodeEls = new Map();
/** One entry per rendered edge — a Map would collapse parallel from→to pairs. */
const edgeEls = [];
let articleData = null;
let articleSplitOpen = true;
const ARTICLE_SPLIT_KEY = "koi-morph-article-split";

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function shortText(value, max) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

function normalizePaperTitle(value) {
  return String(value || "")
    .normalize("NFKC")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function normalizePaperUrl(value) {
  return String(value || "")
    .trim()
    .replace(/^https?:\/\//i, "")
    .replace(/\/+$/, "")
    .toLowerCase();
}

/** Same paper can be staged from Zotero one day and arXiv the next — match URL or title. */
function runMatchesCurrentPaper(row) {
  if (!row || typeof row !== "object") return false;
  const currentUrl = normalizePaperUrl(paperUrl || paper?.url || "");
  const rowUrl = normalizePaperUrl(row.paper_url);
  if (currentUrl && rowUrl && currentUrl === rowUrl) return true;
  const currentTitle = normalizePaperTitle(paper?.title || "");
  const rowTitle = normalizePaperTitle(row.paper_title);
  if (currentTitle && rowTitle && currentTitle === rowTitle) return true;
  return false;
}

function runsForCurrentPaper() {
  if (!paperUrl && !paper?.title) return allRuns;
  return allRuns.filter(runMatchesCurrentPaper);
}

function roleLabel(role) {
  return ROLE_LABELS[role] || String(role || "узел").replace(/_/g, " ");
}

function relationLabel(relation) {
  return RELATION_LABELS[relation] || String(relation || "").replace(/_/g, " ");
}

/* ------------------------------------------------------------------ sections */

/** Split "3.1 Hindsight Proposer" into chapter 3, number 3.1, title. */
function parseSection(raw) {
  const text = String(raw || "").trim();
  if (!text) return { chapter: "", number: "", title: "", label: "" };
  const match = text.match(/^([0-9]+(?:\.[0-9]+)*|[A-Z](?:\.[0-9]+)*)[.)]?\s+(.+)$/);
  if (!match) return { chapter: text, number: "", title: text, label: text };
  const number = match[1];
  return { chapter: number.split(".")[0], number, title: match[2], label: text };
}

/** Section of a node = section of its first anchored quote. */
function nodeSection(node) {
  const anchored = (node.evidence || []).find((item) => item.section);
  return parseSection(anchored?.section);
}

function chapterRank(chapter) {
  if (/^\d+$/.test(chapter)) return [1, Number(chapter), ""];
  if (/^[A-Z]$/.test(chapter)) return [3, 0, chapter];
  return [/^abstract$/i.test(chapter) ? 0 : 2, 0, chapter.toLowerCase()];
}

function compareChapters(a, b) {
  const [ka, na, sa] = chapterRank(a);
  const [kb, nb, sb] = chapterRank(b);
  return ka - kb || na - nb || sa.localeCompare(sb);
}

function assignChapterColors(nodes) {
  const chapters = [...new Set(nodes.map((node) => nodeSection(node).chapter).filter(Boolean))];
  chapters.sort(compareChapters);
  chapterColors = new Map(
    chapters.map((chapter, index) => [
      chapter,
      `hsl(${CHAPTER_HUES[index % CHAPTER_HUES.length]} 72% 60%)`,
    ])
  );
  return chapters;
}

function chapterColor(chapter) {
  return chapterColors.get(chapter) || "var(--muted)";
}

function setStatus(message, kind = "") {
  const el = document.getElementById("morph-status");
  if (!el) return;
  el.textContent = message || "";
  el.className = `morph-status${kind ? ` is-${kind}` : ""}`;
}

/* ---------------------------------------------------------------- bootstrap */

function readHandoffPaper() {
  try {
    const raw = sessionStorage.getItem(MORPH_HANDOFF_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

async function resolvePaper() {
  const handoff = readHandoffPaper();
  if (handoff?.url && (!paperUrl || handoff.url === paperUrl)) return handoff;

  // Direct link without a handoff: recover the record from the shared library.
  if (!paperUrl) return null;
  try {
    const data = await KoiApi.listLibraryPapers();
    const found = (data.papers || []).find((row) => row.arxiv_url === paperUrl);
    if (!found) return null;
    return {
      title: found.title,
      url: found.arxiv_url,
      authors: found.authors,
      year: found.year,
      abstract: found.abstract || found.abstract_preview || "",
    };
  } catch {
    return null;
  }
}

function renderPaperCard() {
  const metaEl = document.getElementById("morph-paper-meta");
  const titleEl = document.getElementById("morph-paper-title");
  const abstractEl = document.getElementById("morph-paper-abstract");
  if (!paper) {
    if (titleEl) titleEl.textContent = "Статья не выбрана";
    return;
  }
  if (metaEl) {
    const year = paper.year ? String(paper.year) : "—";
    metaEl.textContent = `${year} · ${paper.authors || "авторы не указаны"}`;
  }
  if (titleEl) {
    titleEl.textContent = paper.title || "(без названия)";
    titleEl.href = paper.url || "#";
  }
  if (abstractEl) abstractEl.textContent = shortText(paper.abstract, 420);
}

/* --------------------------------------------------------------------- runs */

function renderRuns() {
  const list = document.getElementById("morph-runs-list");
  if (!list) return;
  const showAll = Boolean(document.getElementById("morph-runs-all")?.checked);
  const matched = runsForCurrentPaper();
  const rows = showAll ? allRuns : matched;

  if (!rows.length) {
    const orphanHint =
      !showAll && allRuns.length
        ? `<p class="morph-runs-empty">Для этой ссылки прогонов нет, но в проекте есть ${allRuns.length} — включите «все статьи».</p>`
        : '<p class="morph-runs-empty">Пока нет прогонов.</p>';
    list.innerHTML = orphanHint;
    return;
  }

  list.innerHTML = rows
    .map((row) => {
      const active = currentRun?.run_id === row.run_id ? " is-active" : "";
      const ready = row.status === "ready";
      const when = String(row.created_at || "").replace("T", " ").replace("Z", "");
      const title = showAll ? shortText(row.paper_title, 60) : when;
      const sub = showAll ? when : ready ? "готово" : "ждёт агента";
      return `
        <div class="morph-run-item${active}">
          <button type="button" class="morph-run-row" data-run-id="${escapeHtml(row.run_id)}">
            <span class="morph-run-dot${ready ? " is-ready" : ""}" aria-hidden="true"></span>
            <span class="morph-run-copy">
              <span class="morph-run-title">${escapeHtml(title)}</span>
              <span class="morph-run-sub">${escapeHtml(sub)}</span>
            </span>
          </button>
          <button type="button" class="morph-run-delete" data-run-id="${escapeHtml(row.run_id)}"
                  title="Удалить прогон" aria-label="Удалить прогон">×</button>
        </div>`;
    })
    .join("");

  list.querySelectorAll(".morph-run-row").forEach((btn) => {
    btn.addEventListener("click", () => {
      const runId = btn.dataset.runId;
      if (runId) void openRun(runId);
    });
  });

  list.querySelectorAll(".morph-run-delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const runId = btn.dataset.runId;
      if (!runId || !window.confirm("Удалить этот прогон морфологии?")) return;
      try {
        await KoiApi.deleteMorphologyRun(projectId, runId);
      } catch (err) {
        setStatus(err.message, "error");
        return;
      }
      if (currentRun?.run_id === runId) {
        stopPolling();
        currentRun = null;
        renderRun();
      }
      await loadRuns();
    });
  });
}

async function loadRuns() {
  if (!projectId) return;
  try {
    const data = await KoiApi.listMorphologyRuns(projectId);
    allRuns = data.runs || [];
  } catch {
    allRuns = [];
  }
  renderRuns();
}

async function openRun(runId) {
  stopPolling();
  try {
    currentRun = await KoiApi.getMorphologyRun(projectId, runId);
  } catch (err) {
    setStatus(err.message, "error");
    return;
  }
  if (currentRun?.paper?.title) {
    paper = { ...paper, ...currentRun.paper };
    paperUrl = currentRun.paper.url || paperUrl;
    renderPaperCard();
  }
  renderRun();
  void loadArticle(runId);
  if (currentRun?.status !== "ready") startPolling(runId);
}

async function loadArticle(runId) {
  articleData = null;
  if (!projectId || !runId) {
    renderArticle();
    return;
  }
  try {
    articleData = await KoiApi.getMorphologyArticle(projectId, runId);
  } catch (err) {
    articleData = { available: false, reason: err.message || "error" };
  }
  renderArticle();
  syncArticleSelection();
}

function injectHtmlMarks(root, marks) {
  if (!root || !marks?.length) return 0;
  let hit = 0;
  for (const mark of marks) {
    if (!mark.quote || mark.found === false) continue;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const index = node.nodeValue.indexOf(mark.quote);
      if (index < 0) {
        node = walker.nextNode();
        continue;
      }
      const range = document.createRange();
      range.setStart(node, index);
      range.setEnd(node, index + mark.quote.length);
      const wrap = document.createElement("mark");
      wrap.className = `morph-art-mark role-${mark.role || ""}`;
      wrap.id = `mark-${mark.mark_id}`;
      wrap.dataset.nodeId = mark.node_id;
      wrap.dataset.markId = mark.mark_id;
      wrap.dataset.section = mark.section || "";
      wrap.tabIndex = 0;
      wrap.setAttribute("role", "button");
      try {
        range.surroundContents(wrap);
        hit += 1;
      } catch {
        /* overlapping / partial DOM — skip */
      }
      break;
    }
  }
  return hit;
}

function bindArticleMarks(root) {
  root?.querySelectorAll(".morph-art-mark").forEach((el) => {
    const activate = (event) => {
      event.preventDefault();
      const nodeId = el.dataset.nodeId;
      if (nodeId) selectNode(nodeId, { scrollArticle: false });
    };
    el.addEventListener("click", activate);
    el.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") activate(event);
    });
  });
}

function renderArticle() {
  const pane = document.getElementById("morph-article-pane");
  const toggle = document.getElementById("morph-article-toggle");
  const empty = document.getElementById("morph-article-empty");
  const full = document.getElementById("morph-article-full");
  const bodySplit = document.getElementById("morph-article-body");
  const bodyFull = document.getElementById("morph-article-body-full");
  const metaSplit = document.getElementById("morph-article-meta");
  const metaFull = document.getElementById("morph-article-meta-full");
  const wrap = document.getElementById("morph-canvas-wrap");

  const available = Boolean(articleData?.available && articleData.html);
  toggle?.classList.toggle("hidden", !available || activeTab !== "graph");
  toggle?.classList.toggle("is-active", available && articleSplitOpen);
  if (toggle) {
    toggle.textContent = articleSplitOpen ? "текст ✓" : "текст";
  }

  const meta = available
    ? `${articleData.source_name || "источник"} · ${articleData.marked_count || 0}/${
        articleData.mark_total || 0
      } цитат размечено`
    : "";
  if (metaSplit) metaSplit.textContent = meta;
  if (metaFull) metaFull.textContent = meta;

  empty?.classList.toggle("hidden", available);
  full?.classList.toggle("hidden", !available);

  const html = available ? articleData.html : "";
  if (bodySplit) bodySplit.innerHTML = html;
  if (bodyFull) {
    bodyFull.innerHTML = html;
    if (available && articleData.kind === "html") {
      injectHtmlMarks(bodyFull, articleData.marks || []);
      if (bodySplit) injectHtmlMarks(bodySplit, articleData.marks || []);
    }
  }

  bindArticleMarks(bodySplit);
  bindArticleMarks(bodyFull);

  const showSplit = available && articleSplitOpen && activeTab === "graph";
  pane?.classList.toggle("hidden", !showSplit);
  wrap?.classList.toggle("has-article", showSplit);
}

function syncArticleSelection() {
  const nodeId = selectedNodeId;
  document.querySelectorAll(".morph-art-mark").forEach((el) => {
    const on = Boolean(nodeId) && el.dataset.nodeId === nodeId;
    el.classList.toggle("is-active", on);
  });
  if (!nodeId) return;
  const visibleRoots = [];
  const pane = document.getElementById("morph-article-pane");
  const full = document.getElementById("morph-panel-article");
  if (pane && !pane.classList.contains("hidden")) {
    visibleRoots.push(document.getElementById("morph-article-body"));
  }
  if (full && !full.classList.contains("hidden")) {
    visibleRoots.push(document.getElementById("morph-article-body-full"));
  }
  for (const root of visibleRoots) {
    const target = root?.querySelector(`.morph-art-mark[data-node-id="${CSS.escape(nodeId)}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function setArticleSplit(open) {
  articleSplitOpen = Boolean(open);
  try {
    localStorage.setItem(ARTICLE_SPLIT_KEY, articleSplitOpen ? "1" : "0");
  } catch {
    /* private mode */
  }
  renderArticle();
  syncArticleSelection();
}

/* -------------------------------------------------------------------- stage */

async function stageRun() {
  if (!projectId) {
    setStatus("Не выбран проект.", "error");
    return;
  }
  if (!paper?.title && !paper?.url) {
    setStatus("Нет данных статьи — вернитесь в RelatedWork и нажмите морф ещё раз.", "error");
    return;
  }
  setStatus("Готовлю промпт…");
  let staged;
  try {
    staged = await KoiApi.stagePaperMorphology(projectId, paper);
  } catch (err) {
    setStatus(err.message, "error");
    return;
  }
  currentRun = { ...staged, status: "staged" };
  await copyPrompt(staged.cursor_message || staged.prompt || "");
  renderRun();
  await loadRuns();
  startPolling(staged.run_id);
}

async function copyPrompt(text, okMessage = "Промпт в буфере обмена.") {
  const hint = document.getElementById("morph-prompt-hint");
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    if (hint) {
      hint.textContent =
        "Скопировано — вставьте в чат Cursor. Страница подхватит результат сама.";
    }
    setStatus(okMessage, "ok");
  } catch {
    if (hint) hint.textContent = "Не удалось скопировать автоматически — скопируйте текст ниже.";
    setStatus("Скопируйте промпт вручную.", "warn");
  }
}

/** Visible subgraph: focus + ancestors + descendants, optionally clipped to a chapter. */
function currentSubgraph() {
  if (!graphData || !selectedNodeId) return null;
  const upstream = reachable(selectedNodeId, "up");
  const downstream = reachable(selectedNodeId, "down");
  const ids = new Set([selectedNodeId, ...upstream, ...downstream]);
  if (chapterFilter) {
    for (const id of [...ids]) {
      const chapter = nodeSection(nodeIndex.get(id) || {}).chapter;
      if (chapter !== chapterFilter) ids.delete(id);
    }
  }
  if (!ids.size) return null;
  const nodes = (graphData.nodes || []).filter((node) => ids.has(node.id));
  const edges = (graphData.edges || []).filter(
    (edge) => ids.has(edge.from) && ids.has(edge.to)
  );
  return { focusId: selectedNodeId, nodes, edges, upstream, downstream };
}

function composeSubgraphExplainPrompt(subgraph) {
  const title = paper?.title || graphData?.paper_title || "статья";
  const url = paper?.url || paperUrl || "";
  const focus = nodeIndex.get(subgraph.focusId);
  const focusLine = focus
    ? `${focus.id} · ${roleLabel(focus.role)} · ${focus.statement}`
    : subgraph.focusId;

  const nodeLines = subgraph.nodes
    .map((node) => {
      const section = nodeSection(node);
      const mark =
        node.id === subgraph.focusId
          ? "★"
          : subgraph.upstream.has(node.id)
            ? "↑"
            : subgraph.downstream.has(node.id)
              ? "↓"
              : "·";
      const where = section.number || section.chapter || "—";
      return `${mark} ${node.id} [${roleLabel(node.role)} · ${where}] ${node.statement}`;
    })
    .join("\n");

  const edgeLines = subgraph.edges
    .map((edge) => {
      const cue = edge.cue ? ` «${edge.cue}»` : "";
      return `${edge.from} --${edge.relation}--> ${edge.to}${cue}`;
    })
    .join("\n");

  return `Поясни связку в морфологии статьи максимально коротко.

Статья: ${title}
${url ? `${url}\n` : ""}
Фокус: ${focusLine}
Подграф: ${subgraph.nodes.length} узлов, ${subgraph.edges.length} переходов
(★ фокус, ↑ предки, ↓ потомки)

## Узлы
${nodeLines || "(пусто)"}

## Переходы
${edgeLines || "(нет рёбер внутри подграфа)"}

## Задача
Дай сжатое пояснение связки **по содержанию статьи**, а не по меткам графа.

Форма ответа — 3–6 коротких предложений **или** одна цепочка «A → B → C» с глаголами
переходов. Пиши в ритме:
«Авторы утверждают, что (A); показывают это через (B); предлагают решение через (C).»

Запрещено: пересказ всей статьи; утверждения вне узлов выше; списки цитат;
мета-слова вроде «данный подграф», «в рамках морфологии».
Если в графе есть цикл — одна фраза об этом в конце.`.trim();
}

async function copySubgraphExplainPrompt() {
  const subgraph = currentSubgraph();
  if (!subgraph) {
    setStatus("Сначала выберите узел — подсветится подграф.", "warn");
    return;
  }
  await copyPrompt(
    composeSubgraphExplainPrompt(subgraph),
    `Промпт по связке (${subgraph.nodes.length} узлов) в буфере.`
  );
}

function startPolling(runId) {
  stopPolling();
  if (!runId) return;
  pollTimer = window.setInterval(async () => {
    try {
      const run = await KoiApi.getMorphologyRun(projectId, runId);
      if (run?.status === "ready") {
        currentRun = run;
        stopPolling();
        setStatus("Морфология готова.", "ok");
        renderRun();
        void loadArticle(runId);
        void loadRuns();
      }
    } catch {
      /* keep polling — the agent may still be writing */
    }
  }, POLL_MS);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

/* ------------------------------------------------------------------ render */

function renderRun() {
  const empty = document.getElementById("morph-empty");
  const promptBlock = document.getElementById("morph-prompt-block");
  const canvasWrap = document.getElementById("morph-canvas-wrap");
  const runBtn = document.getElementById("morph-run");
  const graph = currentRun?.morphology;

  const staged = Boolean(currentRun) && !graph;
  empty?.classList.toggle("hidden", Boolean(currentRun));
  promptBlock?.classList.toggle("hidden", !staged);
  canvasWrap?.classList.toggle("hidden", !graph);

  if (staged) {
    const promptEl = document.getElementById("morph-prompt");
    if (promptEl) promptEl.textContent = currentRun.prompt || currentRun.cursor_message || "";
  }
  if (runBtn) runBtn.textContent = graph ? "Пересобрать" : "Собрать морфологию";

  renderRuns();
  renderShape();
  renderReport();
  clearInspector();

  if (graph) {
    renderGraph(graph);
    setStatus(
      `${(graph.nodes || []).length} узлов · ${(graph.edges || []).length} переходов · ${
        COVERAGE_LABELS[graph.source_coverage] || graph.source_coverage || "источник не указан"
      }`
    );
  }
}

function layoutGraph(nodes, edges) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const incoming = new Map(nodes.map((node) => [node.id, []]));
  const outgoing = new Map(nodes.map((node) => [node.id, []]));
  const valid = edges.filter((edge) => byId.has(edge.from) && byId.has(edge.to));
  for (const edge of valid) {
    outgoing.get(edge.from).push(edge);
    incoming.get(edge.to).push(edge);
  }

  // Longest-path layering over a topological order; nodes left in cycles land last.
  const indegree = new Map(nodes.map((node) => [node.id, incoming.get(node.id).length]));
  const queue = nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id);
  const order = [];
  while (queue.length) {
    const id = queue.shift();
    order.push(id);
    for (const edge of outgoing.get(id)) {
      indegree.set(edge.to, indegree.get(edge.to) - 1);
      if (indegree.get(edge.to) === 0) queue.push(edge.to);
    }
  }
  for (const node of nodes) if (!order.includes(node.id)) order.push(node.id);

  const layer = new Map(nodes.map((node) => [node.id, 0]));
  for (const id of order) {
    for (const edge of outgoing.get(id)) {
      layer.set(edge.to, Math.max(layer.get(edge.to) || 0, (layer.get(id) || 0) + 1));
    }
  }

  const columns = new Map();
  for (const node of nodes) {
    const index = layer.get(node.id) || 0;
    if (!columns.has(index)) columns.set(index, []);
    columns.get(index).push(node.id);
  }

  const positions = new Map();
  const tallest = Math.max(...[...columns.values()].map((column) => column.length), 1);
  const columnHeight = tallest * (NODE_H + GAP_Y);
  for (const [index, column] of columns) {
    const height = column.length * (NODE_H + GAP_Y);
    const offset = (columnHeight - height) / 2;
    column.forEach((id, row) => {
      positions.set(id, {
        x: index * (NODE_W + GAP_X),
        y: offset + row * (NODE_H + GAP_Y),
      });
    });
  }

  return {
    positions,
    edges: valid,
    width: columns.size * (NODE_W + GAP_X),
    height: columnHeight,
  };
}

function layoutStorageKey() {
  return `${LAYOUT_STORAGE_PREFIX}:${currentRun?.run_id || ""}`;
}

function loadSavedLayout() {
  try {
    const raw = localStorage.getItem(layoutStorageKey());
    const data = raw ? JSON.parse(raw) : null;
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

function saveLayout() {
  const payload = {};
  for (const [id, position] of nodePositions) payload[id] = [position.x, position.y];
  try {
    localStorage.setItem(layoutStorageKey(), JSON.stringify(payload));
  } catch {
    /* private mode — the layout just will not survive a reload */
  }
}

function resetLayout() {
  try {
    localStorage.removeItem(layoutStorageKey());
  } catch {
    /* nothing to clear */
  }
  if (graphData) renderGraph(graphData);
}

function edgeGeometry(edge) {
  const from = nodePositions.get(edge.from);
  const to = nodePositions.get(edge.to);
  if (!from || !to) return null;
  // Leave from whichever side faces the target so dragged nodes keep readable arrows.
  const forward = to.x + NODE_W / 2 >= from.x + NODE_W / 2;
  const x1 = from.x + (forward ? NODE_W : 0);
  const y1 = from.y + NODE_H / 2;
  const x2 = to.x + (forward ? 0 : NODE_W);
  const y2 = to.y + NODE_H / 2;
  const dx = Math.max(40, Math.abs(x2 - x1) / 2) * (forward ? 1 : -1);
  return {
    d: `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`,
    mx: (x1 + x2) / 2,
    my: (y1 + y2) / 2,
  };
}

function updateEdgeGeometry() {
  for (const { path, label, cue, edge } of edgeEls) {
    const geometry = edgeGeometry(edge);
    if (!geometry) continue;
    path.setAttribute("d", geometry.d);
    label.setAttribute("x", String(geometry.mx));
    label.setAttribute("y", String(geometry.my - 8));
    if (cue) {
      cue.setAttribute("x", String(geometry.mx));
      cue.setAttribute("y", String(geometry.my + 10));
    }
  }
}

function renderGraph(graph) {
  const svg = document.getElementById("morph-canvas");
  if (!svg) return;
  svg.innerHTML = "";
  nodeEls.clear();
  edgeEls.length = 0;

  graphData = graph;
  const nodes = graph.nodes || [];
  nodeIndex = new Map(nodes.map((node) => [node.id, node]));
  assignChapterColors(nodes);

  const { positions, edges, width, height } = layoutGraph(nodes, graph.edges || []);
  const saved = loadSavedLayout();
  nodePositions = new Map();
  for (const node of nodes) {
    const fallback = positions.get(node.id) || { x: 0, y: 0 };
    const stored = saved?.[node.id];
    nodePositions.set(
      node.id,
      Array.isArray(stored) ? { x: Number(stored[0]), y: Number(stored[1]) } : fallback
    );
  }

  const defs = document.createElementNS(SVG_NS, "defs");
  defs.innerHTML = `
    <marker id="morph-arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
    </marker>`;
  svg.appendChild(defs);

  const root = document.createElementNS(SVG_NS, "g");
  root.setAttribute("id", "morph-viewport");
  svg.appendChild(root);

  const edgeLayer = document.createElementNS(SVG_NS, "g");
  edgeLayer.setAttribute("class", "morph-edges");
  root.appendChild(edgeLayer);

  for (const edge of edges) {
    const geometry = edgeGeometry(edge);
    if (!geometry) continue;

    const group = document.createElementNS(SVG_NS, "g");
    group.setAttribute("class", `morph-edge is-${edge.grounding || "quoted"}`);

    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", geometry.d);
    path.setAttribute("marker-end", "url(#morph-arrow)");
    group.appendChild(path);

    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("class", "morph-edge-label");
    label.setAttribute("x", String(geometry.mx));
    label.setAttribute("y", String(geometry.my - 8));
    label.setAttribute("text-anchor", "middle");
    label.textContent = relationLabel(edge.relation);
    group.appendChild(label);

    let cue = null;
    if (edge.cue) {
      cue = document.createElementNS(SVG_NS, "text");
      cue.setAttribute("class", "morph-edge-cue");
      cue.setAttribute("x", String(geometry.mx));
      cue.setAttribute("y", String(geometry.my + 10));
      cue.setAttribute("text-anchor", "middle");
      cue.textContent = `«${shortText(edge.cue, 28)}»`;
      group.appendChild(cue);
    }

    const tooltip = document.createElementNS(SVG_NS, "title");
    tooltip.textContent = edge.rationale || relationLabel(edge.relation);
    group.appendChild(tooltip);

    edgeLayer.appendChild(group);
    edgeEls.push({ group, path, label, cue, edge });
  }

  const nodeLayer = document.createElementNS(SVG_NS, "g");
  nodeLayer.setAttribute("class", "morph-nodes");
  root.appendChild(nodeLayer);

  for (const node of nodes) {
    const position = nodePositions.get(node.id);
    if (!position) continue;
    const section = nodeSection(node);
    const holder = document.createElementNS(SVG_NS, "foreignObject");
    holder.setAttribute("x", String(position.x));
    holder.setAttribute("y", String(position.y));
    holder.setAttribute("width", String(NODE_W));
    holder.setAttribute("height", String(NODE_H));
    holder.innerHTML = `
      <div xmlns="http://www.w3.org/1999/xhtml"
           class="morph-node is-${escapeHtml(node.grounding || "quoted")} role-${escapeHtml(node.role || "")}"
           style="--morph-chapter: ${escapeHtml(chapterColor(section.chapter))}"
           data-node-id="${escapeHtml(node.id)}" data-chapter="${escapeHtml(section.chapter)}"
           tabindex="0" role="button">
        <span class="morph-node-head">
          <span class="morph-node-role">${escapeHtml(roleLabel(node.role))}</span>
          ${
            section.number
              ? `<span class="morph-node-section" title="${escapeHtml(section.label)}">${escapeHtml(section.number)}</span>`
              : ""
          }
        </span>
        <span class="morph-node-text">${escapeHtml(shortText(node.statement, 118))}</span>
        <span class="morph-node-where">${escapeHtml(shortText(section.title || "без якоря", 34))}</span>
      </div>`;
    nodeLayer.appendChild(holder);
    nodeEls.set(node.id, { holder, div: holder.firstElementChild });
    attachNodeInteractions(node.id, holder);
  }

  svg.setAttribute("viewBox", `0 0 ${width + 80} ${height + 80}`);
  viewTransform = { x: 40, y: 40, k: 1 };
  applyTransform();
  attachCanvasInteractions(svg);
  renderLegend(nodes);
  updateHighlight();
}

/** Client coords → canvas coords inside the zoom/pan group. */
function toCanvasPoint(event) {
  const root = document.getElementById("morph-viewport");
  const ctm = root?.getScreenCTM();
  if (!ctm) return { x: event.clientX, y: event.clientY };
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(ctm.inverse());
  return { x: point.x, y: point.y };
}

function attachNodeInteractions(nodeId, holder) {
  const el = holder.firstElementChild;
  if (!el) return;
  let pointerId = null;
  let moved = false;
  let offsetX = 0;
  let offsetY = 0;

  el.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
    const point = toCanvasPoint(event);
    const position = nodePositions.get(nodeId);
    offsetX = point.x - position.x;
    offsetY = point.y - position.y;
    pointerId = event.pointerId;
    moved = false;
    el.setPointerCapture(pointerId);
    el.classList.add("is-dragging");
  });

  el.addEventListener("pointermove", (event) => {
    if (pointerId === null) return;
    const point = toCanvasPoint(event);
    const next = { x: point.x - offsetX, y: point.y - offsetY };
    const previous = nodePositions.get(nodeId);
    if (!moved && Math.hypot(next.x - previous.x, next.y - previous.y) < 3) return;
    moved = true;
    nodePositions.set(nodeId, next);
    holder.setAttribute("x", String(next.x));
    holder.setAttribute("y", String(next.y));
    updateEdgeGeometry();
  });

  const finish = (event) => {
    if (pointerId === null) return;
    el.releasePointerCapture?.(pointerId);
    pointerId = null;
    el.classList.remove("is-dragging");
    if (moved) saveLayout();
    else selectNode(nodeId);
    event.stopPropagation();
  };
  el.addEventListener("pointerup", finish);
  el.addEventListener("pointercancel", finish);

  el.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectNode(nodeId);
    }
  });
}

/* ------------------------------------------------------- subgraph highlight */

/** Nodes reachable from `startId` following edges in one direction. */
function reachable(startId, direction) {
  const key = direction === "up" ? "to" : "from";
  const step = direction === "up" ? "from" : "to";
  const seen = new Set();
  const queue = [startId];
  while (queue.length) {
    const current = queue.shift();
    for (const { edge } of edgeEls) {
      if (edge[key] !== current || seen.has(edge[step])) continue;
      seen.add(edge[step]);
      queue.push(edge[step]);
    }
  }
  seen.delete(startId);
  return seen;
}

function updateHighlight() {
  const upstream = selectedNodeId ? reachable(selectedNodeId, "up") : new Set();
  const downstream = selectedNodeId ? reachable(selectedNodeId, "down") : new Set();

  const inSubgraph = (id) =>
    !selectedNodeId || id === selectedNodeId || upstream.has(id) || downstream.has(id);
  const inChapter = (el) => !chapterFilter || el.dataset.chapter === chapterFilter;

  for (const [id, { div }] of nodeEls) {
    div.classList.toggle("is-selected", id === selectedNodeId);
    div.classList.toggle("is-upstream", upstream.has(id));
    div.classList.toggle("is-downstream", downstream.has(id));
    div.classList.toggle("is-faded", !(inSubgraph(id) && inChapter(div)));
  }

  for (const { group, edge } of edgeEls) {
    const leadsIn =
      upstream.has(edge.from) && (upstream.has(edge.to) || edge.to === selectedNodeId);
    const leadsOut =
      (downstream.has(edge.from) || edge.from === selectedNodeId) && downstream.has(edge.to);
    group.classList.toggle("is-upstream", leadsIn && !leadsOut);
    group.classList.toggle("is-downstream", leadsOut);
    group.classList.toggle("is-faded", Boolean(selectedNodeId) && !(leadsIn || leadsOut));
  }

  const clearBtn = document.getElementById("morph-clear-focus");
  clearBtn?.classList.toggle("hidden", !selectedNodeId && !chapterFilter);
  const explainBtn = document.getElementById("morph-explain-subgraph");
  explainBtn?.classList.toggle("hidden", !selectedNodeId);
}

function applyTransform() {
  document
    .getElementById("morph-viewport")
    ?.setAttribute(
      "transform",
      `translate(${viewTransform.x} ${viewTransform.y}) scale(${viewTransform.k})`
    );
}

/** Listeners live on the <svg>, which survives re-renders — attach them once. */
function attachCanvasInteractions(svg) {
  if (svg.dataset.interactive === "1") return;
  svg.dataset.interactive = "1";

  let dragging = false;
  let panned = false;
  let originX = 0;
  let originY = 0;

  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    viewTransform.k = Math.min(2.2, Math.max(0.3, viewTransform.k * factor));
    applyTransform();
  });

  svg.addEventListener("pointerdown", (event) => {
    if (event.target.closest?.(".morph-node")) return;
    dragging = true;
    panned = false;
    originX = event.clientX - viewTransform.x;
    originY = event.clientY - viewTransform.y;
    svg.classList.add("is-panning");
    svg.setPointerCapture(event.pointerId);
  });

  svg.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const x = event.clientX - originX;
    const y = event.clientY - originY;
    if (Math.hypot(x - viewTransform.x, y - viewTransform.y) > 2) panned = true;
    viewTransform.x = x;
    viewTransform.y = y;
    applyTransform();
  });

  const endDrag = () => {
    if (dragging && !panned && selectedNodeId) clearInspector();
    dragging = false;
    svg.classList.remove("is-panning");
  };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointerleave", endDrag);
}

function renderLegend(nodes) {
  const legend = document.getElementById("morph-legend");
  if (!legend) return;

  const counts = new Map();
  const titles = new Map();
  for (const node of nodes) {
    const section = nodeSection(node);
    if (!section.chapter) continue;
    counts.set(section.chapter, (counts.get(section.chapter) || 0) + 1);
    if (!titles.has(section.chapter)) titles.set(section.chapter, section.title);
  }
  const chapters = [...counts.keys()].sort(compareChapters);

  const chapterChips = chapters
    .map(
      (chapter) => `
        <button type="button" class="morph-chapter-chip${
          chapterFilter === chapter ? " is-active" : ""
        }" data-chapter="${escapeHtml(chapter)}"
                style="--morph-chapter: ${escapeHtml(chapterColor(chapter))}"
                title="${escapeHtml(titles.get(chapter) || chapter)}">
          <span class="morph-chapter-dot" aria-hidden="true"></span>
          <span>${escapeHtml(chapter)}</span>
          <span class="morph-chapter-count">${counts.get(chapter)}</span>
        </button>`
    )
    .join("");

  const groundings = [...new Set(nodes.map((node) => node.grounding || "quoted"))];
  const groundingChips = groundings
    .map(
      (grounding) =>
        `<span class="morph-legend-item is-${escapeHtml(grounding)}">${escapeHtml(
          GROUNDING_LABELS[grounding] || grounding
        )}</span>`
    )
    .join("");

  legend.innerHTML = `
    <div class="morph-legend-row">
      <span class="morph-legend-caption">Разделы</span>
      ${chapterChips || '<span class="morph-legend-item">без якорей</span>'}
    </div>
    <div class="morph-legend-row">
      ${groundingChips}
      <button type="button" class="morph-legend-btn morph-legend-btn-accent hidden" id="morph-explain-subgraph" title="Скопировать промпт: пояснить выделенную связку">пояснить связку</button>
      <button type="button" class="morph-legend-btn hidden" id="morph-clear-focus">сбросить фокус</button>
      <button type="button" class="morph-legend-btn" id="morph-reset-layout">раскладка ↺</button>
    </div>`;

  legend.querySelectorAll(".morph-chapter-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const chapter = btn.dataset.chapter || "";
      chapterFilter = chapterFilter === chapter ? "" : chapter;
      legend.querySelectorAll(".morph-chapter-chip").forEach((chip) => {
        chip.classList.toggle("is-active", chip.dataset.chapter === chapterFilter);
      });
      updateHighlight();
    });
  });

  document.getElementById("morph-reset-layout")?.addEventListener("click", resetLayout);
  document.getElementById("morph-clear-focus")?.addEventListener("click", () => {
    chapterFilter = "";
    clearInspector();
    renderLegend(nodes);
    updateHighlight();
  });
  document
    .getElementById("morph-explain-subgraph")
    ?.addEventListener("click", () => void copySubgraphExplainPrompt());
  updateHighlight();
}

/* --------------------------------------------------------------- inspector */

function clearInspector() {
  selectedNodeId = "";
  document.getElementById("morph-inspector-empty")?.classList.remove("hidden");
  const body = document.getElementById("morph-inspector-body");
  if (body) {
    body.classList.add("hidden");
    body.innerHTML = "";
  }
  if (nodeEls.size) updateHighlight();
  syncArticleSelection();
}

function selectNode(nodeId, { scrollArticle = true } = {}) {
  const graph = graphData;
  const node = nodeIndex.get(nodeId);
  if (!graph || !node) return;
  selectedNodeId = nodeId;
  updateHighlight();
  if (scrollArticle) syncArticleSelection();

  const section = nodeSection(node);
  const incoming = (graph.edges || []).filter((edge) => edge.to === nodeId);
  const outgoing = (graph.edges || []).filter((edge) => edge.from === nodeId);
  const nameOf = (id) => {
    const other = nodeIndex.get(id);
    return other ? shortText(other.statement, 70) : id;
  };

  const evidence = (node.evidence || [])
    .map(
      (item) => `
        <figure class="morph-quote">
          <blockquote>${escapeHtml(item.quote)}</blockquote>
          <figcaption>${escapeHtml(
            [item.section, item.locator].filter(Boolean).join(" · ") || "без якоря"
          )}</figcaption>
        </figure>`
    )
    .join("");

  const transitions = (list, direction) =>
    list
      .map(
        (edge) => `
        <li class="morph-transition">
          <span class="morph-transition-rel">${escapeHtml(relationLabel(edge.relation))}</span>
          <span class="morph-transition-dir">${direction === "in" ? "←" : "→"}</span>
          <span class="morph-transition-node">${escapeHtml(
            nameOf(direction === "in" ? edge.from : edge.to)
          )}</span>
          ${edge.cue ? `<span class="morph-transition-cue">«${escapeHtml(edge.cue)}»</span>` : ""}
        </li>`
      )
      .join("");

  const body = document.getElementById("morph-inspector-body");
  if (!body) return;
  body.innerHTML = `
    <header class="morph-inspector-head">
      <span class="morph-node-role role-${escapeHtml(node.role || "")}">${escapeHtml(
        roleLabel(node.role)
      )}</span>
      <span class="morph-grounding is-${escapeHtml(node.grounding || "quoted")}">${escapeHtml(
        GROUNDING_LABELS[node.grounding] || node.grounding || ""
      )}</span>
    </header>
    ${
      section.label
        ? `<p class="morph-inspector-section" style="--morph-chapter: ${escapeHtml(
            chapterColor(section.chapter)
          )}">${escapeHtml(section.label)}</p>`
        : ""
    }
    <p class="morph-inspector-statement">${escapeHtml(node.statement)}</p>
    ${evidence ? `<h4 class="morph-inspector-title">Цитаты</h4>${evidence}` : ""}
    ${
      incoming.length
        ? `<h4 class="morph-inspector-title">Входящие переходы</h4><ul class="morph-transitions">${transitions(
            incoming,
            "in"
          )}</ul>`
        : ""
    }
    ${
      outgoing.length
        ? `<h4 class="morph-inspector-title">Исходящие переходы</h4><ul class="morph-transitions">${transitions(
            outgoing,
            "out"
          )}</ul>`
        : ""
    }
    <button type="button" class="btn btn-small morph-explain-btn" id="morph-explain-inspector">
      Пояснить связку — скопировать промпт
    </button>`;
  body.classList.remove("hidden");
  document.getElementById("morph-inspector-empty")?.classList.add("hidden");
  document
    .getElementById("morph-explain-inspector")
    ?.addEventListener("click", () => void copySubgraphExplainPrompt());
}

/* ------------------------------------------------------------------- shape */

function renderShape() {
  const root = document.getElementById("morph-shape-body");
  if (!root) return;
  const graph = currentRun?.morphology;
  if (!graph) {
    root.innerHTML = '<p class="morph-runs-empty">Форма появится после разбора.</p>';
    return;
  }

  const fits = [...(graph.template_fit || [])].sort(
    (a, b) => Number(b.score || 0) - Number(a.score || 0)
  );
  const fitRows = fits
    .map((fit) => {
      const percent = Math.round(Number(fit.score || 0) * 100);
      const missing = (fit.missing_slots || []).join(", ") || "—";
      return `
        <tr>
          <td>${escapeHtml(fit.template)}</td>
          <td>
            <span class="morph-score"><span class="morph-score-fill" style="width:${percent}%"></span></span>
            <span class="morph-score-value">${percent}%</span>
          </td>
          <td class="morph-missing">${escapeHtml(missing)}</td>
          <td>${escapeHtml(fit.note || "")}</td>
        </tr>`;
    })
    .join("");

  const style = graph.style || {};
  const cues = (style.transition_cues || []).map((cue) => `<code>${escapeHtml(cue)}</code>`).join(" ");
  const gaps = (graph.coverage_gaps || [])
    .map((gap) => `<li>${escapeHtml(gap)}</li>`)
    .join("");
  const extensions = (graph.vocabulary_extensions || [])
    .map(
      (item) =>
        `<li><code>${escapeHtml(item.key)}</code> (${escapeHtml(item.kind)}) — ${escapeHtml(
          item.definition
        )}</li>`
    )
    .join("");

  root.innerHTML = `
    <section class="morph-shape-section">
      <h3>Шаблоны аргументации</h3>
      <p class="morph-shape-hint">
        Шаблон подбирается после разбора. Пустой слот остаётся пустым — он не заполняется
        придуманным узлом.
      </p>
      ${
        fitRows
          ? `<table class="morph-table">
               <thead><tr><th>Шаблон</th><th>Совпадение</th><th>Пустые слоты</th><th>Замечание</th></tr></thead>
               <tbody>${fitRows}</tbody>
             </table>`
          : '<p class="morph-runs-empty">Агент не сопоставил шаблоны.</p>'
      }
    </section>
    <section class="morph-shape-section">
      <h3>Стиль</h3>
      <dl class="morph-style">
        <dt>Голос</dt><dd>${escapeHtml(style.voice || "—")}</dd>
        <dt>Хеджирование</dt><dd>${escapeHtml(style.hedging || "—")}</dd>
        <dt>Связки</dt><dd>${cues || "—"}</dd>
        <dt>Заметки</dt><dd>${escapeHtml(style.notes || "—")}</dd>
      </dl>
    </section>
    ${
      gaps
        ? `<section class="morph-shape-section"><h3>Пробелы источника</h3><ul class="morph-list">${gaps}</ul></section>`
        : ""
    }
    ${
      extensions
        ? `<section class="morph-shape-section"><h3>Новые роли и связи</h3><ul class="morph-list">${extensions}</ul></section>`
        : ""
    }`;
}

function renderReport() {
  const root = document.getElementById("morph-report-body");
  if (!root) return;
  const markdown = currentRun?.report_markdown;
  if (!markdown) {
    root.innerHTML = '<p class="morph-runs-empty">Отчёт появится после разбора.</p>';
    return;
  }
  root.innerHTML = renderMarkdown(markdown);
}

/* --------------------------------------------------------------------- tabs */

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll(".morph-tab").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.tab === tab);
  });
  for (const name of ["graph", "article", "shape", "report"]) {
    document.getElementById(`morph-panel-${name}`)?.classList.toggle("hidden", name !== tab);
  }
  renderArticle();
  if (tab === "article") syncArticleSelection();
}

/* --------------------------------------------------------------------- init */

function initTheme() {
  const button = document.getElementById("btn-theme");
  button?.addEventListener("click", () => {
    const next =
      document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* private mode */
    }
  });
}

async function init() {
  initTheme();
  try {
    const saved = localStorage.getItem(ARTICLE_SPLIT_KEY);
    if (saved === "0") articleSplitOpen = false;
    if (saved === "1") articleSplitOpen = true;
  } catch {
    /* private mode */
  }
  const params = new URLSearchParams(window.location.search);
  projectId = params.get("project") || "";
  paperUrl = params.get("paper") || "";

  const backLibrary = document.getElementById("morph-back-library");
  const backProject = document.getElementById("morph-back-project");
  if (projectId) {
    const suffix = `?project=${encodeURIComponent(projectId)}`;
    if (backLibrary) backLibrary.href = `literature.html${suffix}`;
    if (backProject) backProject.href = `index.html${suffix}`;
  }

  paper = await resolvePaper();
  renderPaperCard();
  if (!paper) {
    setStatus("Статья не найдена — откройте её из списка литературы.", "error");
  }

  document.getElementById("morph-run")?.addEventListener("click", () => void stageRun());
  document.getElementById("morph-copy-again")?.addEventListener("click", () => {
    void copyPrompt(currentRun?.prompt || currentRun?.cursor_message || "");
  });
  document.getElementById("morph-runs-all")?.addEventListener("change", renderRuns);
  document.querySelectorAll(".morph-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab || "graph"));
  });
  document.getElementById("morph-article-toggle")?.addEventListener("click", () => {
    setArticleSplit(!articleSplitOpen);
  });
  document.getElementById("morph-article-close")?.addEventListener("click", () => {
    setArticleSplit(false);
  });

  await loadRuns();

  const requestedRun = params.get("run");
  const latestForPaper = runsForCurrentPaper().find((row) => row.status === "ready")
    || runsForCurrentPaper()[0];
  if (requestedRun) await openRun(requestedRun);
  else if (latestForPaper) await openRun(latestForPaper.run_id);
  else switchTab(activeTab);
}

window.addEventListener("beforeunload", stopPolling);
void init();
