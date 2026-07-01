import { KoiApi } from "./api.js";
import {
  showKoiLoader,
  hideKoiLoader,
  attachRotatingHint,
  detachRotatingHint,
} from "./koi-loader.js";

const THEME_STORAGE_KEY = "koi-theme";
const RW_SETTINGS_KEY = "koi-rw-settings";

const BRAND_TAGLINES = [
  "Discovery through collaboration across minds",
  "Every experiment should make the next one smarter",
  "Creating a memory that grows with every question",
  "Organizing ideas for discovery",
  "Making research cumulative, not repetitive.",
];

const TAGLINE_ROTATE_MS = 60_000;
const TAGLINE_FADE_MS = 450;
const CONTEXT_APPEND_MARKER = "\n\nProject context:\n";

let literatureResults = [];
let selectedPaperUrls = new Set();
let latestPaperAnswerRun = null;
let selectedClusterKeys = new Set();
let activeClusterModal = null;
let activeSettingsModal = null;
let activeContextModal = null;
let projectContextItems = [];
let selectedProjectContextKeys = new Set();
let projectLiteratureKeywords = [];
let libraryExists = false;
let appSettings = {
  agent_chat_mode: "cursor_inbox",
  literature_inbox_configured: false,
  literature_inbox_watcher_running: false,
  literature_inbox_bootstrap_prompt: "",
  inbox_configured: false,
  inbox_pending_counts: { agent_chat: 0, related_work: 0 },
};
let literatureInboxStatusPollTimer = null;
let literatureInboxBootstrapCopied = false;

const LITERATURE_INBOX_CONFIGURED_KEY = "koi_literature_inbox_configured";

function isLiteratureInboxConfigured() {
  return Boolean(appSettings.literature_inbox_configured);
}

function isLiteratureInboxWatcherRunning() {
  return Boolean(appSettings.literature_inbox_watcher_running);
}

function isLiteratureInboxOperational() {
  return isLiteratureInboxConfigured() && isLiteratureInboxWatcherRunning();
}

function literatureInboxStatus() {
  if (!isInboxAgentMode()) return "not_inbox_mode";
  if (!isLiteratureInboxConfigured()) return "unconfigured";
  if (!isLiteratureInboxWatcherRunning()) return "no_watcher";
  return "ready";
}

function syncLiteratureInboxConfiguredCache() {
  try {
    if (isLiteratureInboxConfigured()) {
      localStorage.setItem(LITERATURE_INBOX_CONFIGURED_KEY, "1");
    } else {
      localStorage.removeItem(LITERATURE_INBOX_CONFIGURED_KEY);
      localStorage.removeItem("koi_inbox_configured");
      localStorage.removeItem("koi_inbox_hint_dismissed");
    }
  } catch {
    /* private mode */
  }
}

function ensureLiteratureInboxBootstrapCached() {
  const bootstrap =
    appSettings.literature_inbox_bootstrap_prompt ||
    appSettings.inbox_bootstrap_prompt ||
    "";
  if (bootstrap && !lastRelatedWorkInboxMessage) {
    lastRelatedWorkInboxMessage = bootstrap;
  }
}

function updateLiteratureInboxSetupNotice() {
  const box = document.getElementById("rw-inbox-message");
  if (!box) return;

  const split = document.getElementById("rw-workspace")?.classList.contains("is-split");
  const insights = document.getElementById("rw-insights-column");
  const insightsVisible = insights && !insights.classList.contains("hidden");

  if (!isInboxAgentMode() || isLiteratureInboxConfigured() || !split || !insightsVisible) {
    box.classList.add("hidden");
    stopLiteratureInboxStatusPoll();
    return;
  }

  const status = literatureInboxStatus();
  const markBtn = document.getElementById("rw-inbox-mark-configured");
  if (markBtn) {
    if (literatureInboxBootstrapCopied) {
      markBtn.removeAttribute("disabled");
    } else {
      markBtn.setAttribute("disabled", "disabled");
      markBtn.title = "Сначала скопируйте сообщение и вставьте в Cursor";
    }
  }
  const label = box.querySelector(".rw-inbox-message-label");
  const hint = box.querySelector(".rw-inbox-message-hint");
  const resetBtn = document.getElementById("rw-inbox-reset-configured");

  if (status === "no_watcher") {
    if (label) label.textContent = "Literature Inbox: watcher не запущен";
    if (hint) {
      hint.innerHTML =
        "Запустите сервер: <code>./scripts/koi-serve.sh start</code> — он поднимет watcher и будет писать RELATED_WORK_WAKE в лог. " +
        "Скопируйте bootstrap в чат Literature Inbox — агент сам поднимет мониторинг с автопробуждением.";
    }
    resetBtn?.classList.remove("hidden");
  } else {
    if (label) label.textContent = "Literature Inbox не настроен";
    if (hint) {
      hint.innerHTML =
        "Скопируйте bootstrap → чат <strong>ResearchOS Literature Inbox</strong> → дождитесь настройки мониторинга → «Inbox готов».";
    }
    resetBtn?.classList.add("hidden");
  }

  ensureLiteratureInboxBootstrapCached();
  box.classList.remove("hidden");
  startLiteratureInboxStatusPoll();
}

function startLiteratureInboxStatusPoll() {
  if (literatureInboxStatusPollTimer) return;
  literatureInboxStatusPollTimer = setInterval(() => {
    if (isLiteratureInboxConfigured()) {
      stopLiteratureInboxStatusPoll();
      return;
    }
    const split = document.getElementById("rw-workspace")?.classList.contains("is-split");
    if (!split || !isInboxAgentMode()) return;
    void refreshAppSettings();
  }, 10000);
}

function stopLiteratureInboxStatusPoll() {
  if (!literatureInboxStatusPollTimer) return;
  clearInterval(literatureInboxStatusPollTimer);
  literatureInboxStatusPollTimer = null;
}

function isInboxConfigured() {
  return isLiteratureInboxConfigured();
}

async function markInboxConfigured() {
  try {
    const data = await KoiApi.setInboxConfigured(true, "literature");
    appSettings = { ...appSettings, ...data };
  } catch {
    setRelatedWorksStatus("Не удалось сохранить настройку Inbox.", true);
    return;
  }
  await refreshAppSettings();
  syncLiteratureInboxConfiguredCache();
  updateInboxIndicator();
  updateLiteratureInboxSetupNotice();
  return isLiteratureInboxOperational();
}

async function resetLiteratureInboxConfigured() {
  try {
    const data = await KoiApi.setInboxConfigured(false, "literature");
    appSettings = { ...appSettings, ...data, literature_inbox_configured: false };
  } catch {
    setRelatedWorksStatus("Не удалось сбросить настройку Inbox.", true);
    return false;
  }
  syncLiteratureInboxConfiguredCache();
  literatureInboxBootstrapCopied = false;
  updateInboxIndicator();
  updateLiteratureInboxSetupNotice();
  updateInboxRestartButton();
  updateRelatedWorkWaitingActions();
  const status = document.getElementById("rw-inbox-message-status");
  if (status) status.textContent = "";
  return true;
}

async function restartLiteratureInboxSetup() {
  const savedItemId = activeRelatedWorkItemId;
  const ok = await resetLiteratureInboxConfigured();
  if (!ok) return;

  await refreshAppSettings();

  let message =
    appSettings.literature_inbox_bootstrap_prompt ||
    appSettings.inbox_bootstrap_prompt ||
    "";

  if (savedItemId) {
    try {
      const item = await KoiApi.getRelatedWorkItem(savedItemId);
      const taskMsg = composeRelatedWorkInboxMessage(item);
      if (taskMsg) message = taskMsg;
      else if (item.cursor_message) message = item.cursor_message;
    } catch {
      /* keep bootstrap */
    }
  }

  ensureLiteratureInboxBootstrapCached();
  if (message) {
    lastRelatedWorkInboxMessage = message;
    lastRelatedWorkCursorMessage = message;
  }

  showLiteratureInboxSetup();

  if (relatedWorkSubmitted && activeRelatedWorkPhase === "pending") {
    setRelatedWorkWaiting(true, "pending");
  }

  if (message) {
    showRelatedInboxModal(message);
  }

  setRelatedWorksStatus(
    "Inbox сброшен — скопируйте сообщение заново и нажмите «Inbox готов».",
    false
  );
}
let relatedWorkPollTimer = null;
let activeRelatedWorkItemId = null;
let activeRelatedWorkPhase = null;
let activeRelatedInboxModal = null;
let lastRelatedWorkCursorMessage = "";
let lastRelatedWorkInboxMessage = "";
let relatedWorkSubmitted = false;

const RELATED_WORK_POLL_MS = 15000;
const RW_PENDING_STORAGE_PREFIX = "koi-rw-pending-item";
let relatedWorkWaitStartedAt = null;
let relatedWorkWaitTimer = null;

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function defaultSettings() {
  return {
    searchMode: "internet",
    autoTranslate: true,
    limit: 10,
    overwriteAnswers: false,
    zoteroUserId: "",
    zoteroApiKey: "",
  };
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(RW_SETTINGS_KEY);
    if (!raw) return defaultSettings();
    return { ...defaultSettings(), ...JSON.parse(raw) };
  } catch {
    return defaultSettings();
  }
}

function saveSettingsToStorage(settings) {
  localStorage.setItem(RW_SETTINGS_KEY, JSON.stringify(settings));
}

function readSettingsFromDom() {
  const mode =
    document.querySelector('input[name="rw-search-mode"]:checked')?.value || "internet";
  return {
    searchMode: mode,
    autoTranslate: Boolean(document.getElementById("literature-auto-translate")?.checked),
    limit: selectedLiteratureLimit(),
    overwriteAnswers: Boolean(document.getElementById("literature-overwrite-answers")?.checked),
    zoteroUserId: document.getElementById("rw-zotero-user-id")?.value?.trim() || "",
    zoteroApiKey: document.getElementById("rw-zotero-api-key")?.value?.trim() || "",
  };
}

function applySettingsToDom(settings = loadSettings()) {
  const modeInput = document.querySelector(
    `input[name="rw-search-mode"][value="${settings.searchMode}"]`
  );
  if (modeInput) modeInput.checked = true;
  else {
    const fallback = document.querySelector('input[name="rw-search-mode"][value="internet"]');
    if (fallback) fallback.checked = true;
  }
  const autoTranslate = document.getElementById("literature-auto-translate");
  if (autoTranslate) autoTranslate.checked = settings.autoTranslate;
  const overwrite = document.getElementById("literature-overwrite-answers");
  if (overwrite) overwrite.checked = settings.overwriteAnswers;
  const limit = document.getElementById("literature-limit");
  if (limit) limit.value = String(settings.limit || 10);
  const zoteroUser = document.getElementById("rw-zotero-user-id");
  if (zoteroUser) zoteroUser.value = settings.zoteroUserId || "";
  const zoteroKey = document.getElementById("rw-zotero-api-key");
  if (zoteroKey) zoteroKey.value = settings.zoteroApiKey || "";
}

function getSearchMode() {
  return loadSettings().searchMode || "internet";
}

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
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function updateThemeButton(theme) {
  const btn = document.getElementById("btn-theme");
  if (!btn) return;
  const isLight = theme === "light";
  btn.title = isLight ? "Тёмная тема" : "Светлая тема";
  btn.setAttribute("aria-label", btn.title);
}

function setTheme(theme) {
  const next = theme === "light" ? "light" : "dark";
  if (next === "light") document.documentElement.setAttribute("data-theme", "light");
  else document.documentElement.removeAttribute("data-theme");
  localStorage.setItem(THEME_STORAGE_KEY, next);
  updateThemeButton(next);
}

function initTheme() {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  const theme = stored === "light" ? "light" : "dark";
  if (theme === "light") document.documentElement.setAttribute("data-theme", "light");
  updateThemeButton(theme);
  document.getElementById("btn-theme")?.addEventListener("click", () => {
    setTheme(getTheme() === "light" ? "dark" : "light");
  });
}

function setLiteratureStatus(msg, isError = false) {
  const el = document.getElementById("literature-search-status");
  if (!el) return;
  if (!isError || !msg) {
    el.textContent = "";
    el.className = "rw-search-status hidden";
    return;
  }
  el.textContent = msg;
  el.className = "rw-search-status error";
}

function setProjectContextStatus(msg, isError = false) {
  const el = document.getElementById("literature-context-status");
  if (!el) return;
  el.textContent = msg;
  el.className = "literature-context-status" + (isError ? " error" : msg ? " ok" : "");
}

function setRelatedWorksStatus(msg, isError = false) {
  const el = document.getElementById("related-works-status");
  if (!el) return;
  el.textContent = msg;
  el.className = "rw-pane-meta rw-related-status" + (isError ? " error" : msg ? " ok" : "");
  el.classList.toggle("hidden", !msg);
}

function showLoader(step = "Подготовка…") {
  showKoiLoader("rw-loader", { step, pool: "literature" });
}

function hideLoader() {
  hideKoiLoader("rw-loader");
}

function showRelatedLoader(step = "Генерация Related Work…") {
  showKoiLoader("rw-related-loader", { step, pool: "related" });
}

function hideRelatedLoader() {
  hideKoiLoader("rw-related-loader");
}

function setWorkspaceSplit(enabled) {
  const workspace = document.getElementById("rw-workspace");
  const page = document.getElementById("rw-page");
  const divider = document.getElementById("rw-split-divider");
  const insights = document.getElementById("rw-insights-column");
  const resultsWrap = document.getElementById("literature-results-wrap");
  workspace?.classList.toggle("is-split", enabled);
  page?.classList.toggle("is-split", enabled);
  divider?.classList.toggle("hidden", !enabled);
  insights?.classList.toggle("hidden", !enabled);
  resultsWrap?.classList.toggle("hidden", !enabled);
  if (enabled) {
    updateInboxIndicator();
    updateLiteratureInboxSetupNotice();
  }
}

function shortText(text, max = 180) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max - 1).trimEnd()}…`;
}

function contextTypeLabel(type) {
  return (
    { problem: "Problem", cause: "Cause", hypothesis: "Hypothesis", task: "Kanban task" }[
      type
    ] || "Context"
  );
}

function buildProjectContextItems(project) {
  if (!project) return [];
  const nodes = Array.isArray(project.nodes) ? project.nodes : [];
  const boards = Array.isArray(project.boards) ? project.boards : [];
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const items = [];

  for (const node of nodes) {
    if (node.node_type === "problem") {
      items.push({
        key: `node:${node.id}`,
        type: "problem",
        title: node.title,
        subtitle: shortText(node.description, 180) || "Root problem from the project map.",
        snippet: `Problem: ${node.title}${node.description ? `. ${shortText(node.description, 260)}` : ""}`,
      });
    }
    if (node.node_type === "cause") {
      items.push({
        key: `node:${node.id}`,
        type: "cause",
        title: node.title,
        subtitle: shortText(node.description, 180) || "Cause node from the project tree.",
        snippet: `Cause: ${node.title}${node.description ? `. ${shortText(node.description, 260)}` : ""}`,
      });
    }
    if (node.node_type === "cause_evidence" || node.node_type === "remediation") {
      const parent = nodeById.get(node.parent_id);
      items.push({
        key: `node:${node.id}`,
        type: "hypothesis",
        title: node.title,
        subtitle: shortText(node.description, 180) || "Hypothesis branch from the project tree.",
        meta: parent?.title ? `Under cause: ${parent.title}` : "",
        snippet:
          `Hypothesis: ${node.title}` +
          `${parent?.title ? ` (under cause: ${parent.title})` : ""}` +
          `${node.description ? `. ${shortText(node.description, 260)}` : ""}`,
      });
    }
  }

  for (const board of boards) {
    const owner = nodeById.get(board.owner_node_id);
    const ownerTitle = owner?.title || "method";
    for (const card of board.cards || []) {
      items.push({
        key: `card:${board.id}:${card.id}`,
        type: "task",
        title: card.title,
        subtitle: shortText(card.description, 180) || "Kanban task without a separate description.",
        meta: `Method: ${ownerTitle}`,
        snippet:
          `Kanban task: ${card.title}` +
          ` (method: ${ownerTitle})` +
          `${card.description ? `. ${shortText(card.description, 260)}` : ""}`,
      });
    }
  }

  const order = { problem: 0, cause: 1, hypothesis: 2, task: 3 };
  return items.sort((a, b) => {
    const oa = order[a.type] ?? 99;
    const ob = order[b.type] ?? 99;
    if (oa !== ob) return oa - ob;
    return a.title.localeCompare(b.title);
  });
}

function selectedContextItems() {
  return projectContextItems.filter((item) => selectedProjectContextKeys.has(item.key));
}

function manualQueryValue() {
  return document.getElementById("literature-query")?.value?.trim() || "";
}

function composeClusterQuestion() {
  const manual = manualQueryValue();
  const picked = selectedContextItems();
  if (!picked.length) return manual;
  const contextBlock = picked.map((item) => `- ${item.snippet}`).join("\n");
  if (!manual) return `Project context for literature search:\n${contextBlock}`;
  return `${manual}${CONTEXT_APPEND_MARKER}${contextBlock}`;
}

/** @deprecated use composeClusterQuestion */
function composeLiteratureQuery() {
  return composeClusterQuestion();
}

function composeProjectSearchQuery() {
  if (!projectLiteratureKeywords.length) return "";
  return projectLiteratureKeywords.join(" ");
}

function displaySearchLabel(searchQuery = composeProjectSearchQuery()) {
  if (!searchQuery) return "";
  return shortText(searchQuery, 120);
}

function displayQueryLabel() {
  const manual = manualQueryValue();
  if (manual) return shortText(manual, 140);
  const titles = selectedContextItems().map((item) => item.title);
  if (!titles.length) return "";
  return shortText(titles.join("; "), 140);
}

function displayResultsHeader(searchQuery, questionLabel) {
  const search = shortText(searchQuery || "", 100);
  const question = questionLabel || displayQueryLabel();
  if (search && question) return `Поиск: ${search} · Вопрос: ${question}`;
  return search || question || "";
}

function selectedLiteratureLimit() {
  const input = document.getElementById("literature-limit");
  const raw = Number(input?.value || loadSettings().limit || 10);
  const limit = Math.max(1, Math.min(50, Number.isFinite(raw) ? Math.round(raw) : 10));
  if (input) input.value = String(limit);
  return limit;
}

function selectedProjectId() {
  return document.getElementById("literature-project-select")?.value || "";
}

function shouldOverwritePaperAnswers() {
  return Boolean(document.getElementById("literature-overwrite-answers")?.checked);
}

function shouldAutoTranslateQuestion() {
  return Boolean(document.getElementById("literature-auto-translate")?.checked);
}

function getSelectedResults() {
  if (!literatureResults.length) return [];
  return literatureResults.filter((paper) => selectedPaperUrls.has(paper.arxiv_url));
}

function updateSelectionSummary() {
  const el = document.getElementById("literature-selection-summary");
  if (!el) return;
  const count = getSelectedResults().length;
  if (!literatureResults.length) {
    el.textContent = "Нет статей.";
    return;
  }
  el.textContent = `${count} из ${literatureResults.length} выбрано.`;
}

function updateActionButtons() {
  updateSelectionSummary();
}

function selectedClustersFromRun(run = latestPaperAnswerRun) {
  if (!run?.clusters?.length) return [];
  return run.clusters.filter((cluster) => selectedClusterKeys.has(cluster.key));
}

function updateClusterStats(run = latestPaperAnswerRun) {
  const statsEl = document.getElementById("rw-cluster-stats");
  const articlesEl = document.getElementById("rw-stat-articles");
  const clustersEl = document.getElementById("rw-stat-clusters");
  if (!statsEl) return;

  const paperCount = run?.papers?.length || literatureResults.length || 0;
  const clusterCount = run?.clusters?.length || 0;

  if (!clusterCount) {
    statsEl.classList.add("hidden");
    if (articlesEl) articlesEl.textContent = "0";
    if (clustersEl) clustersEl.textContent = "0";
    return;
  }

  statsEl.classList.remove("hidden");
  if (articlesEl) articlesEl.textContent = String(paperCount);
  if (clustersEl) clustersEl.textContent = String(clusterCount);
}

function updateRelatedWorksSummary() {
  const button = document.getElementById("related-works-generate");
  const chosen = selectedClustersFromRun();
  updateClusterStats();
  if (button) button.disabled = chosen.length === 0 || !selectedProjectId();
  updateInboxIndicator();
  updateLiteratureInboxSetupNotice();
}

function defaultRelatedWorksProblem() {
  return manualQueryValue() || String(latestPaperAnswerRun?.question || "").trim() || "";
}

function toggleClusterSelection(key) {
  if (!key) return;
  if (selectedClusterKeys.has(key)) selectedClusterKeys.delete(key);
  else selectedClusterKeys.add(key);
  renderClusterResults(latestPaperAnswerRun);
  updateRelatedWorksSummary();
}

function selectAllResults() {
  selectedPaperUrls = new Set(literatureResults.map((paper) => paper.arxiv_url));
  renderLiteratureResults(literatureResults, displayQueryLabel());
}

function clearSelectedResults() {
  selectedPaperUrls = new Set();
  renderLiteratureResults(literatureResults, displayQueryLabel());
}

function mapDiscoverPaperToResult(paper, index) {
  return {
    title: paper.title,
    arxiv_url: paper.arxiv_url,
    authors: paper.authors,
    abstract_preview: shortText(paper.abstract, 280),
    score: Math.max(0.61, 1 - index * 0.02),
    matched_terms: [],
  };
}

function mergePaperResults(primary, secondary, limit) {
  const seen = new Set(primary.map((p) => p.arxiv_url));
  const merged = [...primary];
  for (const paper of secondary) {
    if (seen.has(paper.arxiv_url)) continue;
    merged.push(paper);
    seen.add(paper.arxiv_url);
    if (merged.length >= limit) break;
  }
  return merged.slice(0, limit);
}

async function searchPapers(query, limit) {
  const mode = getSearchMode();
  let localResults = [];
  let internetResults = [];

  if (mode === "local" || mode === "both") {
    if (!libraryExists) {
      if (mode === "local") {
        throw new Error(
          "Локальная база не найдена. Загрузите CSV в настройках или выберите поиск в интернете."
        );
      }
    } else {
      showLoader("Поиск в локальной базе…");
      const data = await KoiApi.searchLibrary(query, limit);
      localResults = data.results || [];
    }
  }

  if (mode === "internet" || (mode === "both" && localResults.length < limit)) {
    showLoader("Поиск статей на arXiv…");
    const data = await KoiApi.searchInternet(query, limit);
    internetResults = data.results || (data.papers || []).map(mapDiscoverPaperToResult);
    if (internetResults.length) {
      libraryExists = true;
      updateLibraryStatusHint();
    }
  }

  if (mode === "both") {
    return mergePaperResults(localResults, internetResults, limit);
  }
  if (mode === "internet") return internetResults.slice(0, limit);
  return localResults.slice(0, limit);
}

function updateProjectBanner(title, projectId = selectedProjectId()) {
  const banner = document.getElementById("rw-project-banner");
  const titleEl = document.getElementById("rw-project-banner-title");
  const backEl = document.getElementById("rw-project-banner-back");
  if (!banner || !titleEl) return;
  const label = String(title || "").trim();
  if (!projectId || !label) {
    banner.classList.add("hidden");
    titleEl.textContent = "";
    return;
  }
  titleEl.textContent = label;
  if (backEl) backEl.href = `index.html?project=${encodeURIComponent(projectId)}`;
  banner.classList.remove("hidden");
}

async function loadProjectOptions() {
  const select = document.getElementById("literature-project-select");
  if (!select) return;
  const list = await KoiApi.listProjects();
  const requested = new URLSearchParams(window.location.search).get("project");
  select.innerHTML = list
    .map((p) => `<option value="${p.id}">${escapeHtml(p.title)}</option>`)
    .join("");
  const preferred =
    (requested && list.find((p) => p.id === requested)?.id) || list[0]?.id || "";
  if (preferred) select.value = preferred;
  const active = list.find((p) => p.id === preferred);
  updateProjectBanner(active?.title, preferred);
}

function updateProjectKeywordsHint() {
  const el = document.getElementById("rw-project-keywords-hint");
  if (!el) return;
  if (!projectLiteratureKeywords.length) {
    el.textContent =
      "В project.md нет literature_keywords — добавьте ключевые слова для поиска статей.";
    el.className = "rw-settings-hint error";
    return;
  }
  el.textContent = `Поиск статей: ${projectLiteratureKeywords.join(", ")}`;
  el.className = "rw-settings-hint ok";
}

async function loadProjectContext(projectId) {
  selectedProjectContextKeys = new Set();
  projectContextItems = [];
  projectLiteratureKeywords = [];
  renderProjectContextSummary();
  renderProjectContext();
  updateProjectKeywordsHint();
  if (!projectId) {
    updateProjectBanner("", "");
    setProjectContextStatus("Выберите проект в настройках.");
    return;
  }
  setProjectContextStatus("Загрузка контекста…");
  try {
    const project = await KoiApi.getProject(projectId);
    updateProjectBanner(project.title, projectId);
    projectLiteratureKeywords = Array.isArray(project.literature_keywords)
      ? project.literature_keywords.map((item) => String(item).trim()).filter(Boolean)
      : [];
    projectContextItems = buildProjectContextItems(project);
    renderProjectContextSummary();
    renderProjectContext();
    updateProjectKeywordsHint();
    if (!projectContextItems.length) {
      setProjectContextStatus("В проекте пока нет узлов или kanban-задач.");
    } else {
      setProjectContextStatus(`Загружено ${projectContextItems.length} элементов.`);
    }
  } catch (err) {
    projectContextItems = [];
    projectLiteratureKeywords = [];
    renderProjectContextSummary();
    renderProjectContext();
    updateProjectKeywordsHint();
    setProjectContextStatus(`Ошибка: ${err.message}`, true);
  }
}

function toggleProjectContextItem(key) {
  if (selectedProjectContextKeys.has(key)) selectedProjectContextKeys.delete(key);
  else selectedProjectContextKeys.add(key);
  renderProjectContextSummary();
  renderProjectContext();
}

function clearProjectContextSelection() {
  selectedProjectContextKeys = new Set();
  renderProjectContextSummary();
  renderProjectContext();
}

async function translateQueryToEnglish(text, { silent = false } = {}) {
  const sourceText = String(text || composeClusterQuestion() || "").trim();
  if (!sourceText) {
    if (!silent) setLiteratureStatus("Введите вопрос или добавьте контекст.", true);
    return "";
  }
  if (!silent) showLoader("Перевод вопроса на английский…");
  try {
    const data = await KoiApi.translateToEnglish(sourceText);
    let translatedText = String(data.translated_text || "").trim();
    translatedText = translatedText
      .replace(/^Project context for literature search:\n/i, "")
      .replace(/\n\nProject context:\n/g, "\n\n")
      .trim();
    if (!text) {
      clearProjectContextSelection();
      const input = document.getElementById("literature-query");
      if (input) input.value = translatedText.split("\n")[0].trim();
    }
    if (!silent) setLiteratureStatus(`Переведено (${data.backend || "agent"}).`);
    return translatedText;
  } catch (err) {
    if (!silent) setLiteratureStatus(err.message, true);
    throw err;
  }
}

function renderProjectContext() {
  const root = document.getElementById("literature-context-groups");
  if (!root) return;
  if (!projectContextItems.length) {
    root.innerHTML = `<p class="literature-empty">Нет доступного контекста для выбранного проекта.</p>`;
    return;
  }
  const groupLabels = { problem: "Problem", cause: "Causes", hypothesis: "Hypotheses", task: "Kanban Tasks" };
  const order = ["problem", "cause", "hypothesis", "task"];
  const groups = new Map();
  for (const type of order) groups.set(type, []);
  for (const item of projectContextItems) groups.get(item.type)?.push(item);

  root.innerHTML = order
    .filter((type) => groups.get(type)?.length)
    .map((type) => {
      const items = groups.get(type) || [];
      return `
        <section class="literature-context-group">
          <h4 class="literature-context-group-title">${escapeHtml(groupLabels[type] || contextTypeLabel(type))}</h4>
          <div class="literature-context-items">
            ${items
              .map((item) => {
                const selected = selectedProjectContextKeys.has(item.key);
                return `
                  <article class="literature-context-item${selected ? " is-selected" : ""}">
                    <div class="literature-context-item-main">
                      <strong>${escapeHtml(item.title)}</strong>
                      ${item.meta ? `<span>${escapeHtml(item.meta)}</span>` : ""}
                      <p>${escapeHtml(item.subtitle || "")}</p>
                    </div>
                    <button type="button" class="btn btn-small literature-context-toggle" data-context-key="${escapeHtml(item.key)}">${selected ? "Убрать" : "Добавить"}</button>
                  </article>`;
              })
              .join("")}
          </div>
        </section>`;
    })
    .join("");

  root.querySelectorAll(".literature-context-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.getAttribute("data-context-key");
      if (key) toggleProjectContextItem(key);
    });
  });
}

function renderProjectContextSummary() {
  const root = document.getElementById("literature-context-summary-list");
  if (!root) return;
  const picked = selectedContextItems();
  if (!picked.length) {
    root.innerHTML = `<p class="literature-empty">Контекст не выбран.</p>`;
    return;
  }
  root.innerHTML = picked
    .map(
      (item) => `
        <article class="literature-context-pill">
          <div class="literature-context-pill-main">
            <strong>${escapeHtml(item.title)}</strong>
            <span>${escapeHtml(contextTypeLabel(item.type))}</span>
          </div>
          <button type="button" class="btn btn-small literature-context-pill-remove" data-context-key="${escapeHtml(item.key)}">Убрать</button>
        </article>`
    )
    .join("");

  root.querySelectorAll(".literature-context-pill-remove").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.getAttribute("data-context-key");
      if (key) toggleProjectContextItem(key);
    });
  });
}

async function loadLatestPaperAnswerRun(projectId) {
  if (!projectId) {
    latestPaperAnswerRun = null;
    selectedClusterKeys = new Set();
    return;
  }
  try {
    latestPaperAnswerRun = await KoiApi.getLatestPaperQuestionAgentRun(projectId);
    selectedClusterKeys = new Set((latestPaperAnswerRun.clusters || []).map((c) => c.key));
  } catch {
    latestPaperAnswerRun = null;
    selectedClusterKeys = new Set();
  }
}

function showClusterModal(cluster, members, run) {
  const modal = document.getElementById("cluster-modal");
  const title = document.getElementById("cluster-modal-title");
  const content = document.getElementById("cluster-modal-content");
  if (!modal || !title || !content) return;

  const papersHtml = members.length
    ? members
        .map((paper) => {
          const year = paper.year ? ` (${paper.year})` : "";
          const queryAnswer = paper.query_answer || paper.short_answer || "";
          const fit = paper.assignment_rationale || paper.cluster_rationale || "";
          return `
            <article class="cluster-modal-paper">
              <h3>${escapeHtml(`${paper.title}${year}`)}</h3>
              ${queryAnswer ? `<p><strong>Paper answer:</strong> ${escapeHtml(queryAnswer)}</p>` : ""}
              ${fit ? `<p><strong>Why in this cluster:</strong> ${escapeHtml(fit)}</p>` : ""}
            </article>`;
        })
        .join("")
    : "<p>No papers found for this cluster.</p>";

  title.textContent = cluster.label || "Cluster details";
  content.innerHTML = `
    <div class="cluster-modal-meta">
      <p><strong>Question:</strong> ${escapeHtml(run.question || "n/a")}</p>
      <p><strong>Shared answer:</strong> ${escapeHtml(cluster.answer || "n/a")}</p>
    </div>
    <section class="cluster-modal-section">
      <h3>Why this cluster</h3>
      <p>${escapeHtml(cluster.rationale || "n/a")}</p>
    </section>
    ${cluster.distinguishing_features ? `<section class="cluster-modal-section"><h3>How it differs</h3><p>${escapeHtml(cluster.distinguishing_features)}</p></section>` : ""}
    <section class="cluster-modal-section">
      <h3>Signature terms</h3>
      <p>${escapeHtml((cluster.signature_terms || []).join(", ") || "n/a")}</p>
    </section>
    <section class="cluster-modal-section">
      <h3>Papers in this cluster</h3>
      <div class="cluster-modal-paper-grid">${papersHtml}</div>
    </section>`;

  activeClusterModal = modal;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function hideClusterModal() {
  if (!activeClusterModal) return;
  activeClusterModal.classList.add("hidden");
  activeClusterModal.setAttribute("aria-hidden", "true");
  activeClusterModal = null;
  document.body.classList.remove("modal-open");
}

function setLibraryUploadStatus(msg, isError = false) {
  const el = document.getElementById("library-upload-status");
  if (!el) return;
  el.textContent = msg;
  el.className = "library-upload-status" + (isError ? " error" : msg ? " ok" : "");
}

function setLibraryBootstrapStatus(msg, isError = false) {
  const el = document.getElementById("library-agent-bootstrap-status");
  if (!el) return;
  el.textContent = msg;
  el.className = "library-upload-status" + (isError ? " error" : msg ? " ok" : "");
}

function updateLibraryUploadFilename() {
  const input = document.getElementById("library-upload-input");
  const label = document.getElementById("library-upload-filename");
  if (!label) return;
  const file = input?.files?.[0];
  label.textContent = file ? file.name : "Выберите CSV с компьютера";
}

function updateLibraryStatusHint() {
  const el = document.getElementById("rw-library-status");
  if (!el) return;
  if (libraryExists) {
    el.textContent = "Локальная база найдена — можно искать по своей библиотеке.";
    el.className = "rw-settings-hint ok";
  } else {
    el.textContent =
      "Локальная база не найдена. Загрузите CSV или используйте поиск в интернете.";
    el.className = "rw-settings-hint";
  }
}

async function refreshLibraryStatus() {
  try {
    const status = await KoiApi.libraryStatus();
    libraryExists = Boolean(status.exists);
    updateLibraryStatusHint();
    if (!libraryExists && getSearchMode() === "local") {
      const settings = loadSettings();
      settings.searchMode = "internet";
      saveSettingsToStorage(settings);
      applySettingsToDom(settings);
    }
  } catch {
    libraryExists = false;
    updateLibraryStatusHint();
  }
}

function showSettingsModal() {
  const modal = document.getElementById("rw-settings-modal");
  if (!modal) return;
  applySettingsToDom();
  activeSettingsModal = modal;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  void refreshLibraryStatus();
}

function hideSettingsModal() {
  if (!activeSettingsModal) return;
  activeSettingsModal.classList.add("hidden");
  activeSettingsModal.setAttribute("aria-hidden", "true");
  activeSettingsModal = null;
  if (!activeContextModal && !activeClusterModal) {
    document.body.classList.remove("modal-open");
  }
}

function showContextModal() {
  const modal = document.getElementById("literature-context-modal");
  if (!modal) return;
  activeContextModal = modal;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function hideContextModal() {
  if (!activeContextModal) return;
  activeContextModal.classList.add("hidden");
  activeContextModal.setAttribute("aria-hidden", "true");
  activeContextModal = null;
  if (!activeSettingsModal && !activeClusterModal) {
    document.body.classList.remove("modal-open");
  }
}

async function uploadLibraryFile() {
  const input = document.getElementById("library-upload-input");
  const button = document.getElementById("library-upload-submit");
  const file = input?.files?.[0];
  if (!file) {
    setLibraryUploadStatus("Сначала выберите CSV.", true);
    return;
  }
  button?.setAttribute("disabled", "disabled");
  setLibraryUploadStatus("Загрузка…");
  try {
    const data = await KoiApi.uploadLibrary(file);
    libraryExists = true;
    updateLibraryStatusHint();
    setLibraryUploadStatus(`Загружено ${data.count} статей в ${data.csv_path}.`);
    setLiteratureStatus(`База обновлена: ${data.filename}.`);
  } catch (err) {
    setLibraryUploadStatus(err.message, true);
  } finally {
    button?.removeAttribute("disabled");
  }
}

async function bootstrapLibraryFromAgent() {
  const button = document.getElementById("library-agent-bootstrap-submit");
  const limit = selectedLiteratureLimit();
  let query = composeProjectSearchQuery();
  if (!query) {
    setLibraryBootstrapStatus(
      "В project.md нет literature_keywords — добавьте ключевые слова проекта.",
      true
    );
    return;
  }
  if (shouldAutoTranslateQuestion()) {
    try {
      query = await translateQueryToEnglish(query, { silent: true });
    } catch {
      setLibraryBootstrapStatus("Не удалось перевести ключевые слова.", true);
      return;
    }
  }
  button?.setAttribute("disabled", "disabled");
  setLibraryBootstrapStatus("Обновление базы через arXiv…");
  try {
    const data = await KoiApi.discoverLibrary(query, limit);
    libraryExists = true;
    updateLibraryStatusHint();
    setLibraryBootstrapStatus(`База обновлена: ${data.count} статей.`);
  } catch (err) {
    setLibraryBootstrapStatus(err.message, true);
  } finally {
    button?.removeAttribute("disabled");
  }
}

function isInboxAgentMode() {
  return appSettings.agent_chat_mode === "cursor_inbox";
}

async function refreshAppSettings() {
  try {
    const data = await KoiApi.getSettings();
    appSettings = {
      ...appSettings,
      ...data,
      literature_inbox_configured: Boolean(data.literature_inbox_configured),
      literature_inbox_watcher_running: Boolean(data.literature_inbox_watcher_running),
    };
    syncLiteratureInboxConfiguredCache();
    ensureLiteratureInboxBootstrapCached();
    updateInboxIndicator();
    updateLiteratureInboxSetupNotice();
    if (inboxIsReady()) stopLiteratureInboxStatusPoll();
  } catch {
    /* API may be restarting */
  }
}

/** Cursor-чат инициализирован (пользователь нажал «Inbox готов» после bootstrap). */
function inboxIsReady() {
  return isInboxAgentMode() && isLiteratureInboxConfigured();
}

function updateInboxRestartButton() {
  const btn = document.getElementById("rw-inbox-restart");
  if (!btn) return;
  const split = document.getElementById("rw-workspace")?.classList.contains("is-split");
  const show =
    split &&
    isInboxAgentMode() &&
    isLiteratureInboxConfigured() &&
    activeRelatedWorkPhase !== "processing";
  btn.classList.toggle("hidden", !show);
}

function updateRelatedWorkWaitingActions() {
  const actions = document.getElementById("rw-related-waiting-actions");
  const waiting = document.getElementById("rw-related-waiting");
  if (!actions || !waiting) return;

  const hasMessage = Boolean(
    lastRelatedWorkInboxMessage ||
      lastRelatedWorkCursorMessage ||
      appSettings.literature_inbox_bootstrap_prompt
  );
  const visible =
    !waiting.classList.contains("hidden") &&
    isInboxAgentMode() &&
    activeRelatedWorkPhase === "pending" &&
    !isLiteratureInboxOperational() &&
    hasMessage;

  actions.classList.toggle("hidden", !visible);
}

function updateInboxIndicator() {
  const box = document.getElementById("rw-inbox-indicator");
  const textEl = document.getElementById("rw-inbox-indicator-text");
  const dot = document.getElementById("rw-inbox-dot");
  if (!box || !textEl) return;

  const split = document.getElementById("rw-workspace")?.classList.contains("is-split");
  if (!split || !isInboxAgentMode()) {
    box.classList.add("hidden");
    return;
  }

  box.classList.remove("hidden");
  dot?.classList.remove("is-ok", "is-warn");
  box.classList.remove("rw-inbox-indicator--action");

  const status = literatureInboxStatus();
  if (status === "ready" && isLiteratureInboxOperational()) {
    dot?.classList.add("is-ok");
    if (activeRelatedWorkPhase === "processing") {
      textEl.textContent = "Literature Inbox · агент пишет Related Work";
    } else if (activeRelatedWorkItemId && relatedWorkSubmitted) {
      textEl.textContent = "Literature Inbox · задача в очереди";
    } else {
      textEl.textContent = "Literature Inbox · ждёт запросов из UI";
    }
  } else if (status === "no_watcher") {
    dot?.classList.add("is-warn");
    textEl.textContent = "Cursor настроен, но watcher не запущен — ./scripts/koi-serve.sh start";
    box.classList.add("rw-inbox-indicator--action");
  } else {
    dot?.classList.add("is-warn");
    textEl.textContent = isInboxAgentMode()
      ? "Literature Inbox не настроен — нажмите, чтобы показать инструкцию"
      : "Режим не Inbox — см. настройки агента";
    box.classList.add("rw-inbox-indicator--action");
  }
  updateInboxRestartButton();
}

function showLiteratureInboxSetup() {
  ensureLiteratureInboxBootstrapCached();
  updateLiteratureInboxSetupNotice();
  const box = document.getElementById("rw-inbox-message");
  box?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function formatRelatedWorkElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function startRelatedWorkWaitTimer() {
  stopRelatedWorkWaitTimer();
  relatedWorkWaitStartedAt = Date.now();
  const tick = () => {
    if (!relatedWorkWaitStartedAt) return;
    const sec = Math.floor((Date.now() - relatedWorkWaitStartedAt) / 1000);
    const label = formatRelatedWorkElapsed(sec);
    const timerEl = document.getElementById("rw-related-waiting-timer");
    if (timerEl) timerEl.textContent = label;
  };
  tick();
  relatedWorkWaitTimer = setInterval(tick, 1000);
}

function stopRelatedWorkWaitTimer() {
  if (relatedWorkWaitTimer) {
    clearInterval(relatedWorkWaitTimer);
    relatedWorkWaitTimer = null;
  }
  relatedWorkWaitStartedAt = null;
  const timerEl = document.getElementById("rw-related-waiting-timer");
  if (timerEl) timerEl.textContent = "00:00";
}

function composeRelatedWorkInboxMessage(data = {}) {
  if (!isLiteratureInboxConfigured() && isInboxAgentMode()) {
    if (data.inbox_message) return data.inbox_message;
    if (appSettings.literature_inbox_bootstrap_prompt) {
      return appSettings.literature_inbox_bootstrap_prompt;
    }
  }
  if (data.inbox_message && isInboxAgentMode()) return data.inbox_message;
  if (inboxIsReady()) return "";
  return data.cursor_message || lastRelatedWorkCursorMessage || "";
}

function updateRelatedWorkInboxMessage(message) {
  const trimmed = String(message || "").trim();
  if (trimmed) lastRelatedWorkInboxMessage = trimmed;
  if (!isLiteratureInboxConfigured() && isInboxAgentMode()) {
    updateLiteratureInboxSetupNotice();
  }
}

async function copyRelatedWorkInboxMessage(statusEl) {
  const text =
    lastRelatedWorkInboxMessage ||
    appSettings.literature_inbox_bootstrap_prompt ||
    "";
  const ok = await copyRelatedWorkCursorMessage(text, statusEl);
  if (ok) {
    literatureInboxBootstrapCopied = true;
    updateLiteratureInboxSetupNotice();
  }
  return ok;
}

function setRelatedWorkWaiting(isWaiting, phase = "pending") {
  const waiting = document.getElementById("rw-related-waiting");
  const relatedPane = document.getElementById("rw-related-pane");
  const lead = document.getElementById("rw-related-waiting-lead");
  const hint = document.getElementById("rw-related-waiting-hint");
  const timerRow = document.querySelector(".rw-related-waiting-timer-row");
  if (!waiting) return;

  if (isWaiting) {
    relatedPane?.classList.remove("hidden");
    waiting.classList.remove("hidden");
    timerRow?.classList.remove("hidden");
    activeRelatedWorkPhase = phase;
    startRelatedWorkWaitTimer();
    if (phase === "processing") {
      waiting.classList.add("is-processing");
      waiting.classList.remove("is-pending-queue");
      hideRelatedWorkQueuePanel();
      hideRelatedWorkSetupText();
      updateRelatedWorkInboxMessage("");
      hideRelatedInboxModal();
      showRelatedWorkAgentPanel();
    } else {
      waiting.classList.remove("is-processing");
      hideRelatedWorkAgentPanel();
      const needsSetup = isInboxAgentMode() && !isLiteratureInboxOperational();
      if (needsSetup) {
        waiting.classList.remove("is-pending-queue");
        hideRelatedWorkQueuePanel();
        if (isLiteratureInboxConfigured()) {
          showRelatedWorkSetupText(
            "Watcher не запущен",
            "Запустите ./scripts/koi-serve.sh start — затем задача уйдёт в очередь автоматически."
          );
        } else {
          showRelatedWorkSetupText(
            "Настройте Literature Inbox один раз",
            "Скопируйте сообщение кнопкой ниже → вставьте в чат ResearchOS Literature Inbox → tail -f related-work-watch.log → «Inbox готов»."
          );
        }
        updateRelatedWorkInboxMessage(lastRelatedWorkInboxMessage);
      } else {
        waiting.classList.add("is-pending-queue");
        hideRelatedWorkSetupText();
        showRelatedWorkQueuePanel();
        updateRelatedWorkInboxMessage("");
      }
    }
    setRelatedWorksStatus("");
  } else {
    waiting.classList.add("hidden");
    waiting.classList.remove("is-processing", "is-pending-queue");
    timerRow?.classList.add("hidden");
    activeRelatedWorkPhase = null;
    stopRelatedWorkWaitTimer();
    updateRelatedWorkInboxMessage("");
    hideRelatedWorkQueuePanel();
    hideRelatedWorkAgentPanel();
    hideRelatedWorkSetupText();
  }
  updateInboxIndicator();
  updateLiteratureInboxSetupNotice();
  updateRelatedWorkWaitingActions();
}

function showRelatedWorkSetupText(leadText, hintText) {
  const lead = document.getElementById("rw-related-waiting-lead");
  const hint = document.getElementById("rw-related-waiting-hint");
  if (lead) {
    lead.textContent = leadText;
    lead.classList.remove("hidden");
  }
  if (hint) {
    hint.textContent = hintText;
    hint.classList.remove("hidden");
  }
}

function hideRelatedWorkSetupText() {
  document.getElementById("rw-related-waiting-lead")?.classList.add("hidden");
  document.getElementById("rw-related-waiting-hint")?.classList.add("hidden");
}

function showRelatedWorkQueuePanel() {
  const panel = document.getElementById("rw-related-queue-panel");
  panel?.classList.remove("hidden");
  attachRotatingHint(document.getElementById("rw-related-queue-hint"), "relatedQueue");
}

function hideRelatedWorkQueuePanel() {
  detachRotatingHint(document.getElementById("rw-related-queue-hint"));
  document.getElementById("rw-related-queue-panel")?.classList.add("hidden");
}

function showRelatedWorkAgentPanel() {
  const panel = document.getElementById("rw-related-agent-panel");
  panel?.classList.remove("hidden");
  attachRotatingHint(document.getElementById("rw-related-agent-hint"), "related");
}

function hideRelatedWorkAgentPanel() {
  detachRotatingHint(document.getElementById("rw-related-agent-hint"));
  document.getElementById("rw-related-agent-panel")?.classList.add("hidden");
}

function applyRelatedWorkProcessing(item = {}) {
  activeRelatedWorkItemId = item.id || activeRelatedWorkItemId;
  if (item.project_id || selectedProjectId()) {
    saveRelatedWorkPending(item.project_id || selectedProjectId(), activeRelatedWorkItemId);
  }
  setRelatedWorkWaiting(true, "processing");
  syncRelatedWorkPolling();
}

function hideRelatedCursorPanel() {
  /* inline panel removed — message lives in modal only */
}

function showRelatedCursorPanel() {
  /* inline panel removed — message lives in modal only */
}

function showRelatedInboxModal(cursorMessage) {
  const message = String(cursorMessage || lastRelatedWorkInboxMessage || "").trim();
  lastRelatedWorkCursorMessage = message;
  lastRelatedWorkInboxMessage = message;
  const modal = document.getElementById("rw-related-inbox-modal");
  if (!modal) return;
  const watcherEl = document.getElementById("rw-related-inbox-watcher-status");
  if (watcherEl) {
    watcherEl.classList.remove("is-ok", "is-warn");
    if (!isInboxAgentMode()) {
      watcherEl.textContent = "Режим не Inbox — используйте hooks или API-агента.";
    } else if (isLiteratureInboxOperational()) {
      watcherEl.textContent =
        "Literature Inbox работает — watcher пишет RELATED_WORK_WAKE в .run/logs/related-work-watch.log.";
      watcherEl.classList.add("is-ok");
    } else if (isLiteratureInboxConfigured()) {
      watcherEl.textContent =
        "Inbox отмечен, но watcher не запущен. Выполните ./scripts/koi-serve.sh start и настройте loop в Cursor.";
      watcherEl.classList.add("is-warn");
    } else {
      watcherEl.textContent =
        "Literature Inbox ещё не настроен. Скопируйте bootstrap и вставьте в чат ResearchOS Literature Inbox.";
      watcherEl.classList.add("is-warn");
    }
  }
  activeRelatedInboxModal = modal;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  void copyRelatedWorkCursorMessage(
    lastRelatedWorkCursorMessage,
    document.getElementById("rw-related-inbox-copy-status")
  );
}

function hideRelatedInboxModal() {
  const modal = activeRelatedInboxModal || document.getElementById("rw-related-inbox-modal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  if (activeRelatedInboxModal === modal) activeRelatedInboxModal = null;
  if (!activeClusterModal && !activeSettingsModal && !activeContextModal) {
    document.body.classList.remove("modal-open");
  }
}

async function copyRelatedWorkCursorMessage(message, statusEl) {
  const text = String(message || "").trim();
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    if (statusEl) {
      statusEl.textContent = "Скопировано — вставьте в чат Cursor.";
      setTimeout(() => {
        if (statusEl.textContent.startsWith("Скопировано")) statusEl.textContent = "";
      }, 5000);
    }
    return true;
  } catch {
    if (statusEl) statusEl.textContent = "Не удалось скопировать — скопируйте из блока ниже.";
    return false;
  }
}

function relatedWorkPendingKey(projectId) {
  return `${RW_PENDING_STORAGE_PREFIX}:${projectId || ""}`;
}

function saveRelatedWorkPending(projectId, itemId) {
  if (!projectId || !itemId) return;
  try {
    sessionStorage.setItem(relatedWorkPendingKey(projectId), itemId);
  } catch {
    /* private mode */
  }
}

function loadRelatedWorkPending(projectId) {
  if (!projectId) return null;
  try {
    return sessionStorage.getItem(relatedWorkPendingKey(projectId));
  } catch {
    return null;
  }
}

function clearRelatedWorkPending(projectId) {
  if (!projectId) return;
  try {
    sessionStorage.removeItem(relatedWorkPendingKey(projectId));
  } catch {
    /* ignore */
  }
}

async function restoreRelatedWorkOnLoad() {
  stopRelatedWorkPollTimer();
  relatedWorkSubmitted = false;
  activeRelatedWorkItemId = null;
  activeRelatedWorkPhase = null;
  updateRelatedWorkInboxMessage("");
  hideRelatedInboxModal();

  const projectId = selectedProjectId();
  const savedId = loadRelatedWorkPending(projectId);

  if (!savedId) {
    document.getElementById("rw-related-pane")?.classList.add("hidden");
    document.getElementById("related-works-output")?.classList.remove("has-content");
    const output = document.getElementById("related-works-output");
    if (output) output.textContent = "";
    setRelatedWorksStatus("");
    updateInboxIndicator();
    return;
  }

  try {
    const item = await KoiApi.getRelatedWorkItem(savedId);
    document.getElementById("rw-workspace")?.classList.add("is-split");
    document.getElementById("rw-related-pane")?.classList.remove("hidden");

    if (item.status === "answered" && item.markdown) {
      applyRelatedWorkResult(item.markdown, item);
      clearRelatedWorkPending(projectId);
      updateInboxIndicator();
      return;
    }

    relatedWorkSubmitted = true;
    activeRelatedWorkItemId = savedId;

    if (item.status === "processing") {
      applyRelatedWorkProcessing(item);
    } else {
      setRelatedWorkWaiting(true, "pending");
      const msg = composeRelatedWorkInboxMessage(item);
      if (msg) updateRelatedWorkInboxMessage(msg);
    }
    startRelatedWorkPolling(savedId);
  } catch {
    clearRelatedWorkPending(projectId);
    document.getElementById("rw-related-pane")?.classList.add("hidden");
  }
  updateInboxIndicator();
  updateLiteratureInboxSetupNotice();
}

function stopRelatedWorkPollTimer() {
  if (relatedWorkPollTimer) {
    clearInterval(relatedWorkPollTimer);
    relatedWorkPollTimer = null;
  }
}

function stopRelatedWorkPolling() {
  stopRelatedWorkPollTimer();
  activeRelatedWorkItemId = null;
  activeRelatedWorkPhase = null;
  updateInboxIndicator();
  updateLiteratureInboxSetupNotice();
}

function syncRelatedWorkPolling() {
  if (activeRelatedWorkItemId && !relatedWorkPollTimer) {
    relatedWorkPollTimer = setInterval(() => {
      void pollRelatedWorkItem(activeRelatedWorkItemId);
    }, RELATED_WORK_POLL_MS);
  } else if (!activeRelatedWorkItemId && relatedWorkPollTimer) {
    stopRelatedWorkPolling();
  }
}

async function pollRelatedWorkItem(itemId) {
  if (!itemId || !relatedWorkSubmitted) return;
  try {
    const item = await KoiApi.getRelatedWorkItem(itemId);
    if (item.status === "answered" && item.markdown) {
      applyRelatedWorkResult(item.markdown, item);
      clearRelatedWorkPending(item.project_id || selectedProjectId());
      stopRelatedWorkPolling();
      hideRelatedInboxModal();
      return;
    }
    if (item.status === "processing") {
      applyRelatedWorkProcessing(item);
      return;
    }
    if (item.status === "pending") {
      activeRelatedWorkItemId = itemId;
      setRelatedWorkWaiting(true, "pending");
    }
    syncRelatedWorkPolling();
  } catch (err) {
    setRelatedWorksStatus(`Ожидание ответа: ${err.message}`, true);
  }
}

function startRelatedWorkPolling(itemId) {
  stopRelatedWorkPolling();
  if (!itemId || !relatedWorkSubmitted) return;
  activeRelatedWorkItemId = itemId;
  saveRelatedWorkPending(selectedProjectId(), itemId);
  void pollRelatedWorkItem(itemId);
  syncRelatedWorkPolling();
}

function showRelatedWorkAnswer(markdown, data = {}) {
  const output = document.getElementById("related-works-output");
  const relatedPane = document.getElementById("rw-related-pane");
  setRelatedWorkWaiting(false);
  const text = String(markdown || "").trim();
  if (output) {
    output.textContent = text;
    output.classList.toggle("has-content", Boolean(text));
  }
  relatedPane?.classList.remove("hidden");
  setRelatedWorksStatus("");
}

function applyRelatedWorkResult(markdown, data = {}) {
  showRelatedWorkAnswer(markdown, data);
  hideRelatedInboxModal();
  stopRelatedWorkPolling();
  relatedWorkSubmitted = false;
  clearRelatedWorkPending(data.project_id || selectedProjectId());
  updateInboxIndicator();
  updateLiteratureInboxSetupNotice();
}

async function generateRelatedWorks() {
  const btn = document.getElementById("related-works-generate");
  const relatedPane = document.getElementById("rw-related-pane");
  const problem = defaultRelatedWorksProblem();
  const projectId = selectedProjectId();
  const clusters = selectedClustersFromRun();

  if (!projectId) {
    setRelatedWorksStatus("Выберите проект в настройках.", true);
    return;
  }
  if (!clusters.length) {
    setRelatedWorksStatus("Выберите хотя бы один кластер.", true);
    return;
  }
  if (!problem) {
    setRelatedWorksStatus("Введите вопрос в строке поиска.", true);
    return;
  }

  btn?.setAttribute("disabled", "disabled");
  relatedPane?.classList.remove("hidden");
  showRelatedLoader();
  setRelatedWorksStatus("");
  stopRelatedWorkPolling();
  relatedWorkSubmitted = false;
  hideRelatedInboxModal();

  try {
    await refreshAppSettings();
    const data = await KoiApi.generateRelatedWorks(projectId, {
      problem,
      cluster_keys: clusters.map((c) => c.key),
    });

    if (data.status === "answered" && data.markdown) {
      applyRelatedWorkResult(data.markdown, data);
      return;
    }

    const itemId = data.item_id || data.item?.id;
    const cursorMessage = data.cursor_message || "";
    if (!itemId) {
      throw new Error("Не удалось поставить Related Work в очередь.");
    }

    lastRelatedWorkCursorMessage = cursorMessage;
    const inboxMessage = composeRelatedWorkInboxMessage(data);
    relatedWorkSubmitted = true;
    saveRelatedWorkPending(projectId, itemId);
    setRelatedWorkWaiting(true, "pending");
    startRelatedWorkPolling(itemId);

    if (isInboxAgentMode()) {
      if (!isLiteratureInboxConfigured()) {
        const bootstrap =
          inboxMessage ||
          appSettings.literature_inbox_bootstrap_prompt ||
          "";
        if (bootstrap) lastRelatedWorkInboxMessage = bootstrap;
        showLiteratureInboxSetup();
        showRelatedInboxModal(bootstrap);
        setRelatedWorksStatus(
          "Скопируйте сообщение в ResearchOS Literature Inbox, затем нажмите «Inbox готов».",
          true
        );
      } else if (!isLiteratureInboxOperational()) {
        showLiteratureInboxSetup();
        setRelatedWorksStatus("Запустите watcher: ./scripts/koi-serve.sh start", true);
      } else {
        updateRelatedWorkInboxMessage("");
      }
    } else {
      showRelatedInboxModal(cursorMessage);
    }
  } catch (err) {
    relatedWorkSubmitted = false;
    setRelatedWorksStatus(err.message || "Не удалось отправить Related Work.", true);
    setRelatedWorkWaiting(false);
  } finally {
    hideRelatedLoader();
    btn?.removeAttribute("disabled");
    updateRelatedWorksSummary();
  }
}

function renderClusterResults(run) {
  const root = document.getElementById("literature-agent-results");
  if (!root) return;
  if (!run?.clusters?.length) {
    selectedClusterKeys = new Set();
    updateRelatedWorksSummary();
    root.innerHTML = `<p class="literature-empty">Кластеры появятся после генерации.</p>`;
    return;
  }

  root.innerHTML = `
    <div class="cluster-grid cluster-grid--tiles">
      ${run.clusters
        .map((cluster, index) => {
          const members = (run.papers || []).filter((p) => p.cluster_key === cluster.key);
          const checked = selectedClusterKeys.has(cluster.key) ? "checked" : "";
          const selectedClass = selectedClusterKeys.has(cluster.key) ? " is-selected" : "";
          return `
            <article class="cluster-card cluster-card--tile${selectedClass}">
              <label class="cluster-tile-select" title="Выбрать кластер">
                <input type="checkbox" class="cluster-select-checkbox" data-cluster-key="${escapeHtml(cluster.key)}" ${checked} />
              </label>
              <button type="button" class="cluster-tile-body cluster-tile-open" data-cluster-index="${index}">
                <h3 class="cluster-tile-title">${escapeHtml(cluster.label)}</h3>
                <p class="cluster-tile-meta">${members.length} статей</p>
                <p class="cluster-tile-preview">${escapeHtml(shortText(cluster.answer || "—", 110))}</p>
              </button>
            </article>`;
        })
        .join("")}
    </div>`;

  root.querySelectorAll(".cluster-tile-open").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.getAttribute("data-cluster-index"));
      const cluster = run.clusters?.[index];
      if (!cluster) return;
      const members = (run.papers || []).filter((p) => p.cluster_key === cluster.key);
      showClusterModal(cluster, members, run);
    });
  });
  root.querySelectorAll(".cluster-select-checkbox").forEach((input) => {
    input.addEventListener("change", () => {
      toggleClusterSelection(input.getAttribute("data-cluster-key"));
    });
  });
  updateRelatedWorksSummary();
}

function renderLiteratureResults(results = [], query = "") {
  const root = document.getElementById("literature-results");
  if (!root) return;

  if (!results.length) {
    const text = query
      ? `Ничего не найдено по запросу «${query}». Попробуйте другие ключевые слова или режим «Интернет».`
      : "Введите вопрос и нажмите «Сгенерировать».";
    root.innerHTML = `<p class="literature-empty">${escapeHtml(text)}</p>`;
    updateActionButtons();
    return;
  }

  root.innerHTML = results
    .map((paper, index) => {
      const checked = selectedPaperUrls.has(paper.arxiv_url) ? "checked" : "";
      return `
        <article class="literature-result-card">
          <label class="literature-select-toggle">
            <input type="checkbox" class="literature-result-checkbox" data-paper-url="${escapeHtml(paper.arxiv_url)}" ${checked} />
            <span>Выбрать</span>
          </label>
          <div class="literature-result-rank">${index + 1}</div>
          <div class="literature-result-body">
            <a class="literature-result-title" href="${escapeHtml(paper.arxiv_url)}" target="_blank" rel="noreferrer">${escapeHtml(paper.title)}</a>
            <p class="literature-result-meta">
              <span>score ${(paper.score ?? 0).toFixed(3)}</span>
              ${paper.matched_terms?.length ? `<span>matched: ${escapeHtml(paper.matched_terms.join(", "))}</span>` : ""}
            </p>
            ${paper.abstract_preview ? `<p class="literature-result-abstract">${escapeHtml(paper.abstract_preview)}</p>` : ""}
          </div>
        </article>`;
    })
    .join("");

  root.querySelectorAll(".literature-result-checkbox").forEach((input) => {
    input.addEventListener("change", (event) => {
      const url = event.currentTarget?.dataset?.paperUrl;
      if (!url) return;
      if (event.currentTarget.checked) selectedPaperUrls.add(url);
      else selectedPaperUrls.delete(url);
      updateActionButtons();
    });
  });
  updateActionButtons();
}

async function onLiteratureSearchSubmit(e) {
  e.preventDefault();
  const button = document.getElementById("literature-search-button");
  const limit = selectedLiteratureLimit();
  const projectId = selectedProjectId();
  let searchQuery = composeProjectSearchQuery();
  let clusterQuestion = composeClusterQuestion();
  let questionLabel = displayQueryLabel();
  let resultsHeader = displayResultsHeader(searchQuery, questionLabel);
  let searchCompleted = false;

  if (!clusterQuestion) {
    setLiteratureStatus("Введите исследовательный вопрос — по нему сгруппируем статьи.", true);
    return;
  }
  if (!searchQuery) {
    setLiteratureStatus(
      "В project.md нет literature_keywords — добавьте ключевые слова для поиска статей.",
      true
    );
    showSettingsModal();
    return;
  }
  if (!projectId) {
    setLiteratureStatus("Выберите проект в настройках (иконка шестерёнки).", true);
    showSettingsModal();
    return;
  }

  button?.setAttribute("disabled", "disabled");
  showLoader("Подготовка…");
  setLiteratureStatus("");

  try {
    if (shouldAutoTranslateQuestion()) {
      showLoader("Перевод на английский…");
      clusterQuestion = await translateQueryToEnglish(clusterQuestion, { silent: true });
      searchQuery = await translateQueryToEnglish(searchQuery, { silent: true });
      questionLabel = shortText(clusterQuestion.split("\n")[0], 140);
      resultsHeader = displayResultsHeader(searchQuery, questionLabel);
    }

    showLoader("Поиск релевантных статей по ключевым словам проекта…");
    literatureResults = await searchPapers(searchQuery, limit);
    searchCompleted = true;

    if (!literatureResults.length) {
      setWorkspaceSplit(false);
      renderLiteratureResults([], resultsHeader);
      const mode = getSearchMode();
      setLiteratureStatus(
        mode === "internet" || mode === "both"
          ? `По ключевым словам проекта ничего не найдено на arXiv. Проверьте literature_keywords в project.md.`
          : "Статьи не найдены. В настройках выберите режим «Интернет (arXiv)» или загрузите CSV.",
        true
      );
      return;
    }

    selectedPaperUrls = new Set(literatureResults.map((p) => p.arxiv_url));
    setWorkspaceSplit(true);
    renderLiteratureResults(literatureResults, resultsHeader);
    setLiteratureStatus(`Найдено ${literatureResults.length} статей по ключевым словам проекта.`);

    showLoader("Анализ статей и группировка по вашему вопросу…");
    latestPaperAnswerRun = await KoiApi.runPaperQuestionAgent(projectId, {
      question: clusterQuestion,
      limit,
      refresh: shouldOverwritePaperAnswers(),
      download_pdfs: true,
      papers: literatureResults,
    });
    selectedClusterKeys = new Set((latestPaperAnswerRun.clusters || []).map((c) => c.key));
    renderClusterResults(latestPaperAnswerRun);

    const clusterCount = latestPaperAnswerRun.clusters?.length || 0;
    const clusterBackend = latestPaperAnswerRun.cluster_backend || "";
    const heuristicNote =
      clusterBackend === "abstract_heuristic"
        ? " (эвристика по абстрактам, без агента)"
        : "";
    setLiteratureStatus(
      clusterCount
        ? `Готово${heuristicNote}.`
        : "Готово."
    );
  } catch (err) {
    if (searchCompleted && literatureResults.length) {
      setWorkspaceSplit(true);
      renderLiteratureResults(literatureResults, resultsHeader);
      const clusterRoot = document.getElementById("literature-agent-results");
      if (clusterRoot) {
        clusterRoot.innerHTML = `<p class="literature-empty">Группировка не выполнена: ${escapeHtml(err.message)}</p>`;
      }
      setLiteratureStatus(
        `Найдено ${literatureResults.length} статей. Группировка не удалась: ${err.message}`,
        true
      );
    } else {
      literatureResults = [];
      selectedPaperUrls = new Set();
      setWorkspaceSplit(false);
      renderLiteratureResults([], resultsHeader);
      setLiteratureStatus(err.message, true);
    }
  } finally {
    hideLoader();
    button?.removeAttribute("disabled");
  }
}

function saveSettingsFromModal() {
  const settings = readSettingsFromDom();
  saveSettingsToStorage(settings);
  hideSettingsModal();
  setLiteratureStatus("Настройки сохранены.");
}

async function init() {
  initTheme();
  initTaglineRotation();
  applySettingsToDom();

  try {
    await loadProjectOptions();
    await refreshLibraryStatus();
    await refreshAppSettings();
    await loadProjectContext(selectedProjectId());
    await restoreRelatedWorkOnLoad();
  } catch (err) {
    setLiteratureStatus(`Ошибка загрузки: ${err.message}`, true);
  }

  document.getElementById("btn-rw-settings")?.addEventListener("click", showSettingsModal);
  document.getElementById("rw-settings-save")?.addEventListener("click", saveSettingsFromModal);
  document.getElementById("literature-search-form")?.addEventListener("submit", onLiteratureSearchSubmit);
  document.getElementById("literature-project-select")?.addEventListener("change", (event) => {
    const select = event.target;
    const title = select.selectedOptions?.[0]?.textContent?.trim() || "";
    updateProjectBanner(title, select.value);
    void loadProjectContext(select.value);
    void restoreRelatedWorkOnLoad();
  });
  document.getElementById("literature-open-context-modal")?.addEventListener("click", showContextModal);
  document.getElementById("literature-clear-context")?.addEventListener("click", clearProjectContextSelection);
  document.getElementById("literature-context-modal-clear")?.addEventListener("click", clearProjectContextSelection);
  document.getElementById("literature-select-all")?.addEventListener("click", selectAllResults);
  document.getElementById("literature-clear-selection")?.addEventListener("click", clearSelectedResults);
  document.getElementById("library-upload-input")?.addEventListener("change", () => {
    updateLibraryUploadFilename();
    const file = document.getElementById("library-upload-input")?.files?.[0];
    setLibraryUploadStatus(file ? "Готово к загрузке." : "Файл не выбран.");
  });
  document.getElementById("library-upload-submit")?.addEventListener("click", () => void uploadLibraryFile());
  document.getElementById("library-agent-bootstrap-submit")?.addEventListener("click", () => void bootstrapLibraryFromAgent());
  document.getElementById("rw-inbox-indicator")?.addEventListener("click", () => {
    if (!inboxIsReady()) showLiteratureInboxSetup();
  });
  document.getElementById("rw-inbox-indicator")?.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && !inboxIsReady()) {
      e.preventDefault();
      showLiteratureInboxSetup();
    }
  });
  document.getElementById("related-works-generate")?.addEventListener("click", () => void generateRelatedWorks());
  document.getElementById("rw-related-show-message")?.addEventListener("click", () => {
    const message = lastRelatedWorkInboxMessage || lastRelatedWorkCursorMessage;
    if (message) {
      showRelatedInboxModal(message);
      return;
    }
    const itemId = activeRelatedWorkItemId;
    if (itemId) {
      void KoiApi.getRelatedWorkItem(itemId).then((item) => {
        showRelatedInboxModal(composeRelatedWorkInboxMessage(item));
      });
    }
  });
  document.getElementById("rw-inbox-message-copy")?.addEventListener("click", () => {
    void copyRelatedWorkInboxMessage(document.getElementById("rw-inbox-message-status"));
  });
  document.getElementById("rw-inbox-mark-configured")?.addEventListener("click", () => {
    void markInboxConfigured().then((operational) => {
      updateRelatedWorkInboxMessage("");
      const status = document.getElementById("rw-inbox-message-status");
      if (operational) {
        setRelatedWorksStatus("Literature Inbox готов — watcher запущен.", false);
        if (status) status.textContent = "Готово. Related Work идёт в очередь автоматически.";
      } else {
        setRelatedWorksStatus("Inbox отмечен, но watcher не запущен — см. инструкцию выше.", true);
        if (status) {
          status.textContent =
            "Сохранено. Запустите ./scripts/koi-serve.sh start и loop в Cursor — зелёный индикатор появится сам.";
        }
      }
    });
  });
  document.getElementById("rw-inbox-reset-configured")?.addEventListener("click", () => {
    void restartLiteratureInboxSetup();
  });
  document.getElementById("rw-inbox-restart")?.addEventListener("click", () => {
    void restartLiteratureInboxSetup();
  });
  document.getElementById("rw-related-waiting-copy")?.addEventListener("click", () => {
    const message = lastRelatedWorkInboxMessage || lastRelatedWorkCursorMessage;
    if (message) {
      showRelatedInboxModal(message);
      return;
    }
    void copyRelatedWorkInboxMessage(document.getElementById("rw-inbox-message-status"));
  });
  document.getElementById("rw-related-inbox-copy")?.addEventListener("click", () => {
    void copyRelatedWorkCursorMessage(
      lastRelatedWorkCursorMessage || lastRelatedWorkInboxMessage,
      document.getElementById("rw-related-inbox-copy-status")
    );
  });
  document.querySelectorAll("[data-close='rw-related-inbox-modal']").forEach((el) => {
    el.addEventListener("click", hideRelatedInboxModal);
  });

  document.querySelectorAll("[data-close='cluster-modal']").forEach((el) => {
    el.addEventListener("click", hideClusterModal);
  });
  document.querySelectorAll("[data-close='rw-settings-modal']").forEach((el) => {
    el.addEventListener("click", hideSettingsModal);
  });
  document.querySelectorAll("[data-close='literature-context-modal']").forEach((el) => {
    el.addEventListener("click", hideContextModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    hideClusterModal();
    hideSettingsModal();
    hideContextModal();
    hideRelatedInboxModal();
  });

  updateLibraryUploadFilename();
  renderProjectContextSummary();
  updateRelatedWorksSummary();
}

init().catch((err) => {
  console.error(err);
  setLiteratureStatus(`Ошибка: ${err.message}`, true);
});
