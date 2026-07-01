/** HTML overlays synced to scroll: kanban, knowledge base, literature. */

/**
 * @param {number} edge0
 * @param {number} edge1
 * @param {number} x
 */
function smoothstep(edge0, edge1, x) {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

/**
 * Opacity 0..1 for an overlay pinned to a scroll zone (1 inside, fade at edges only).
 * @param {string} startStep
 * @param {string} endStep
 */
function zoneVisibility(startStep, endStep) {
  const startEl = document.querySelector(`[data-step="${startStep}"]`);
  const endEl = document.querySelector(`[data-step="${endStep}"]`);
  if (!startEl || !endEl) return 0;

  const vh = window.innerHeight;
  const viewY = window.scrollY + vh * 0.42;
  const zoneStart = startEl.offsetTop - vh * 0.08;
  const zoneEnd = endEl.offsetTop + endEl.offsetHeight - vh * 0.12;
  const fade = vh * 0.22;

  if (viewY < zoneStart) {
    return smoothstep(zoneStart - fade, zoneStart, viewY);
  }
  if (viewY > zoneEnd) {
    return 1 - smoothstep(zoneEnd, zoneEnd + fade, viewY);
  }
  return 1;
}

/** @param {string} step @param {number} localT */
function revealItems(root, localT, itemSelector, stepSize) {
  if (!root) return;
  root.querySelectorAll(itemSelector).forEach((el, i) => {
    el.classList.toggle("is-visible", localT >= (Number(el.getAttribute("data-reveal")) || 0.15 + i * stepSize));
  });
}

/** @returns {number} */
export function kanbanStageVisibility() {
  return zoneVisibility("kanban", "verdict");
}

/** @returns {number} */
export function knowledgeStageVisibility() {
  return zoneVisibility("knowledge", "knowledge");
}

/** @returns {number} */
export function literatureSearchVisibility() {
  return zoneVisibility("literature-search", "literature-search");
}

/** @returns {number} */
export function literatureReviewVisibility() {
  return zoneVisibility("literature-review", "literature-review");
}

/** Progress 0..1 across kanban + verdict sections. */
function kanbanStageProgress() {
  const kanban = document.querySelector('[data-step="kanban"]');
  const verdict = document.querySelector('[data-step="verdict"]');
  if (!kanban || !verdict) return 0;
  const vh = window.innerHeight;
  const start = kanban.offsetTop - vh * 0.12;
  const end = verdict.offsetTop + verdict.offsetHeight - vh * 0.3;
  const range = Math.max(1, end - start);
  return Math.min(1, Math.max(0, (window.scrollY - start) / range));
}

/** @param {string} step */
function stepLocalProgress(step) {
  const el = document.querySelector(`[data-step="${step}"]`);
  if (!el) return 0;
  const vh = window.innerHeight;
  const start = el.offsetTop - vh * 0.15;
  const end = el.offsetTop + el.offsetHeight - vh * 0.25;
  const range = Math.max(1, end - start);
  return Math.min(1, Math.max(0, (window.scrollY - start) / range));
}

/**
 * @param {HTMLElement | null} el
 * @param {number} vis
 */
function setStageVisible(el, vis) {
  if (!el) return;
  el.hidden = vis < 0.03;
  el.style.opacity = String(vis);
  el.setAttribute("aria-hidden", vis < 0.03 ? "true" : "false");
}

/** @param {number} scrollProgress */
export function updateStageUI(scrollProgress) {
  const stage = document.getElementById("tour-stage");
  const flowCard = document.getElementById("tour-flow-card");
  const colBacklog = document.getElementById("tour-col-backlog");
  const colRunning = document.getElementById("tour-col-running");
  const colDone = document.getElementById("tour-col-done");
  const agent = document.getElementById("tour-stage-agent");
  const report = document.getElementById("tour-stage-report");

  if (stage && flowCard && colBacklog && colRunning && colDone && agent && report) {
    setStageVisible(stage, kanbanStageVisibility());

    const p = kanbanStageProgress();
    const toRunning = p >= 0.22;
    const agentOn = p >= 0.32 && p < 0.88;
    const writing = p >= 0.38 && p < 0.72;
    const toDone = p >= 0.58;

    if (toDone) {
      colDone.appendChild(flowCard);
      flowCard.classList.remove("is-running");
      flowCard.classList.add("is-done");
    } else if (toRunning) {
      colRunning.appendChild(flowCard);
      flowCard.classList.add("is-running");
      flowCard.classList.remove("is-done");
    } else {
      colBacklog.appendChild(flowCard);
      flowCard.classList.remove("is-running", "is-done");
    }

    agent.classList.toggle("is-visible", agentOn);
    agent.classList.toggle("is-writing", writing);
    report.classList.toggle("is-visible", p >= 0.36);

    report.querySelectorAll(".tour-stage-report__lines li").forEach((li, i) => {
      li.classList.toggle("is-visible", p >= 0.42 + i * 0.08);
    });
  }

  const kbStage = document.getElementById("tour-stage-knowledge");
  const kbVis = knowledgeStageVisibility();
  setStageVisible(kbStage, kbVis);
  const kbPanel = document.getElementById("tour-kb-panel");
  if (kbPanel) {
    kbPanel.classList.toggle("is-active", kbVis > 0.35);
    revealItems(kbPanel, stepLocalProgress("knowledge"), ".tour-kb-insights li", 0.2);
  }

  const litSearchStage = document.getElementById("tour-stage-lit-search");
  const litSearchVis = literatureSearchVisibility();
  setStageVisible(litSearchStage, litSearchVis);
  const litSearch = document.getElementById("tour-lit-search");
  if (litSearch) {
    litSearch.classList.toggle("is-active", litSearchVis > 0.35);
    revealItems(litSearch, stepLocalProgress("literature-search"), ".tour-lit-results li", 0.22);
  }

  const litClustersStage = document.getElementById("tour-stage-lit-clusters");
  const litClustersVis = literatureReviewVisibility();
  setStageVisible(litClustersStage, litClustersVis);
  const litClusters = document.getElementById("tour-lit-clusters");
  if (litClusters) {
    litClusters.classList.toggle("is-active", litClustersVis > 0.35);
    litClusters.querySelectorAll(".tour-lit-cluster").forEach((el, i) => {
      el.classList.toggle("is-visible", stepLocalProgress("literature-review") >= 0.25 + i * 0.3);
    });
  }

  void scrollProgress;
}

/** @param {number} scrollProgress @returns {number} 0..1 focus amount for dimming 3D tree */
export function stageTreeDim(scrollProgress) {
  return Math.max(
    kanbanStageVisibility(),
    knowledgeStageVisibility(),
    literatureSearchVisibility(),
    literatureReviewVisibility()
  );
}
