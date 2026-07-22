/**
 * Interactive DAG editor for method kanban boards.
 * Tools: move, directed arrow linking, auto-layout, Q/A reveal.
 */

import { KoiApi } from "./api.js?v=20260721a";

const CARD_W = 184;
const CARD_MIN_H = 40;
const RQ_ZONE_H = 34;
const TAGS_ROW_H = 22;
const LAYER_GAP_X = 108;
const NODE_GAP_Y = 24;
const GRID_GAP = 28;
const STORAGE_PREFIX = "koi-dag-layout";
const LAYOUT_ANIM_MS = 420;
const TITLE_CHARS_PER_LINE = 24;

const COLUMN_COLORS = {
  backlog: "#8b5cf6",
  running: "#3b82f6",
  done: "#22c55e",
  successful: "#a855f7",
};

const CLOSED_COLUMNS = new Set(["done", "successful"]);

const DAG_PHASE = {
  backlog: "todo",
  running: "running",
  done: "done",
  successful: "done",
};

const DAG_PHASE_LABELS = {
  todo: "В очереди (TODO)",
  running: "Идёт",
  done: "Пройден",
};

function dagCardPhase(columnId) {
  return DAG_PHASE[columnId] || "todo";
}

function dagStatusHtml(phase) {
  const label = DAG_PHASE_LABELS[phase] || phase;
  if (phase === "done") {
    return `<div class="kanban-dag-card__status kanban-dag-card__status--check" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">✓</div>`;
  }
  return `<div class="kanban-dag-card__status" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"></div>`;
}

let activeEditor = null;

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function layoutKey(projectId, boardId) {
  return `${STORAGE_PREFIX}:${projectId || "p"}:${boardId || "b"}`;
}

function loadLayoutFromLocalStorage(projectId, boardId) {
  try {
    const raw = localStorage.getItem(layoutKey(projectId, boardId));
    return raw ? JSON.parse(raw) : { cards: {} };
  } catch {
    return { cards: {} };
  }
}

function clearLayoutFromLocalStorage(projectId, boardId) {
  try {
    localStorage.removeItem(layoutKey(projectId, boardId));
  } catch {
    /* ignore */
  }
}

function estimatedTitleLines(title) {
  return Math.max(1, Math.ceil(String(title || "").length / TITLE_CHARS_PER_LINE));
}

function cardBodyHeight(card) {
  return Math.max(CARD_MIN_H, 16 + estimatedTitleLines(card?.title) * 14);
}

function bundleHeight(card) {
  const hasTags = (card?.tags || []).length > 0;
  return RQ_ZONE_H + cardBodyHeight(card) + (hasTags ? TAGS_ROW_H : 0);
}

function defaultCardPositions(cards) {
  const positions = {};
  const cols = Math.max(1, Math.ceil(Math.sqrt(cards.length)));
  cards.forEach((card, i) => {
    const row = Math.floor(i / cols);
    const col = i % cols;
    positions[card.id] = {
      x: 72 + col * (CARD_W + GRID_GAP),
      y: 56 + row * (bundleHeight(card) + GRID_GAP),
    };
  });
  return positions;
}

function mergePositions(saved, defaults) {
  const merged = { ...defaults, ...saved };
  for (const [id, pos] of Object.entries(merged)) {
    if (!pos || !Number.isFinite(pos.x) || !Number.isFinite(pos.y)) {
      merged[id] = defaults[id] || { x: 72, y: 56 };
      continue;
    }
    if (pos.x < -240 || pos.y < -240 || pos.x > 8000 || pos.y > 8000) {
      merged[id] = defaults[id] || { x: 72, y: 56 };
    }
  }
  return merged;
}

function edgePath(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const bend = Math.max(40, Math.abs(dx) * 0.4, Math.abs(dy) * 0.16);

  if (dx >= 20) {
    const x1 = from.x + bend;
    const x2 = to.x - bend;
    return `M ${from.x} ${from.y} C ${x1} ${from.y}, ${x2} ${to.y}, ${to.x} ${to.y}`;
  }

  const arc = Math.max(52, Math.abs(dy) * 0.5);
  const yLift = Math.min(from.y, to.y) - arc;
  return `M ${from.x} ${from.y} C ${from.x + bend} ${yLift}, ${to.x - bend} ${yLift}, ${to.x} ${to.y}`;
}

function isCardClosed(card) {
  return CLOSED_COLUMNS.has(card?.column_id);
}

function questionsForCard(questions, cardId) {
  return (questions || []).filter((q) => q.card_id === cardId);
}

function buildTopologicalLayers(cards) {
  const cardIds = new Set(cards.map((c) => c.id));
  const inDegree = new Map();
  const adj = new Map();
  for (const card of cards) {
    inDegree.set(card.id, 0);
    adj.set(card.id, []);
  }
  for (const card of cards) {
    for (const depId of card.depends_on || []) {
      if (!cardIds.has(depId)) continue;
      adj.get(depId).push(card.id);
      inDegree.set(card.id, (inDegree.get(card.id) || 0) + 1);
    }
  }

  const layers = [];
  const assigned = new Set();
  let frontier = cards.filter((c) => inDegree.get(c.id) === 0).map((c) => c.id);

  while (frontier.length) {
    layers.push([...frontier]);
    const next = [];
    for (const id of frontier) {
      assigned.add(id);
      for (const childId of adj.get(id) || []) {
        inDegree.set(childId, inDegree.get(childId) - 1);
        if (inDegree.get(childId) === 0) next.push(childId);
      }
    }
    frontier = next;
  }

  const remaining = cards.filter((c) => !assigned.has(c.id)).map((c) => c.id);
  if (remaining.length) layers.push(remaining);
  return layers;
}

function computeAutoLayout(cards, heightFor = bundleHeight) {
  const layers = buildTopologicalLayers(cards);
  const positions = {};
  const startX = 64;
  const startY = 52;

  const layerHeights = layers.map((layer) =>
    layer.reduce((acc, id, idx) => {
      const card = cards.find((c) => c.id === id);
      return acc + heightFor(card) + (idx > 0 ? NODE_GAP_Y : 0);
    }, 0)
  );
  const maxLayerHeight = Math.max(CARD_MIN_H + RQ_ZONE_H, ...layerHeights);

  let x = startX;
  layers.forEach((layer, layerIdx) => {
    const colHeight = layerHeights[layerIdx];
    let y = startY + (maxLayerHeight - colHeight) / 2;
    layer.forEach((cardId) => {
      const card = cards.find((c) => c.id === cardId);
      positions[cardId] = { x, y };
      y += heightFor(card) + NODE_GAP_Y;
    });
    x += CARD_W + LAYER_GAP_X;
  });

  return positions;
}

class KanbanDagEditor {
  constructor(rootEl, board, node, ctx) {
    this.rootEl = rootEl;
    this.board = board;
    this.node = node;
    this.ctx = ctx;
    this.cards = board?.cards || [];
    this.questions = node?.research_questions || [];
    this.projectId = ctx.projectId || "";
    this.tool = "move";
    this.showQA = false;
    this.arrowDraft = null;
    this.selectedEdge = null;
    this.drag = null;
    this.camera = { x: 40, y: 40, scale: 1 };
    this.layoutAnim = null;
    this._layoutSaveTimer = null;
    this._layoutHydrated = false;
    this._linkMoveHandler = null;
    this._linkUpHandler = null;

    const cardDefaults = defaultCardPositions(this.cards);
    this.positions = {
      cards: { ...cardDefaults },
    };
    this._mount();
    void this._hydrateLayoutFromServer(cardDefaults);
  }

  destroy() {
    if (activeEditor === this) activeEditor = null;
    this._teardownLinkHandlers();
    this._cancelArrowDraft();
    if (this.layoutAnim) cancelAnimationFrame(this.layoutAnim);
    if (this._layoutSaveTimer) clearTimeout(this._layoutSaveTimer);
    if (this._edgeRenderRaf) cancelAnimationFrame(this._edgeRenderRaf);
    if (this._fitRaf) cancelAnimationFrame(this._fitRaf);
    if (this._resizeFitTimer) clearTimeout(this._resizeFitTimer);
    if (this._resizeObserver) this._resizeObserver.disconnect();
    if (this._onKeyDown) document.removeEventListener("keydown", this._onKeyDown);
    this.rootEl.innerHTML = "";
  }

  visibleCards() {
    const filters = this.ctx.tagFilters || [];
    const match = this.ctx.cardMatchesFilter;
    if (!filters.length || !match) return this.cards;
    return this.cards.filter((c) => match(c, filters));
  }

  isCardVisible(cardId) {
    return this.visibleCards().some((c) => c.id === cardId);
  }

  persistLayout() {
    if (this.ctx.readOnly || !this.projectId || !this.board?.id) return;
    if (this._layoutSaveTimer) clearTimeout(this._layoutSaveTimer);
    this._layoutSaveTimer = setTimeout(() => {
      this._layoutSaveTimer = null;
      void this._flushLayout();
    }, 400);
  }

  async _flushLayout() {
    if (this.ctx.readOnly || !this.projectId || !this.board?.id) return;
    try {
      await KoiApi.saveBoardDagLayout(this.projectId, this.board.id, {
        cards: this.positions.cards,
      });
    } catch (err) {
      this.ctx.onStatus?.(err?.message || "Не удалось сохранить раскладку DAG", true);
      console.error("DAG layout save failed", err);
    }
  }

  _applyPositionsToDom() {
    for (const card of this.visibleCards()) {
      const pos = this.positions.cards[card.id];
      if (!pos) continue;
      const el = this.nodesEl?.querySelector(`[data-bundle-id="${CSS.escape(card.id)}"]`);
      if (el) {
        el.style.left = `${pos.x}px`;
        el.style.top = `${pos.y}px`;
      }
    }
    this._resizeWorld();
    this._scheduleEdgeRender();
  }

  async _hydrateLayoutFromServer(cardDefaults = defaultCardPositions(this.cards)) {
    if (!this.projectId || !this.board?.id) {
      this._layoutHydrated = true;
      return;
    }
    try {
      const remote = await KoiApi.getBoardDagLayout(this.projectId, this.board.id);
      const remoteCards = remote?.cards || {};
      if (Object.keys(remoteCards).length > 0) {
        this.positions.cards = mergePositions(remoteCards, cardDefaults);
        this._applyPositionsToDom();
        this._layoutHydrated = true;
        return;
      }

      const local = loadLayoutFromLocalStorage(this.projectId, this.board.id);
      if (Object.keys(local.cards || {}).length > 0) {
        this.positions.cards = mergePositions(local.cards, cardDefaults);
        this._applyPositionsToDom();
        if (!this.ctx.readOnly) {
          await KoiApi.saveBoardDagLayout(this.projectId, this.board.id, {
            cards: this.positions.cards,
          });
          clearLayoutFromLocalStorage(this.projectId, this.board.id);
        }
      }
    } catch (err) {
      const local = loadLayoutFromLocalStorage(this.projectId, this.board.id);
      if (Object.keys(local.cards || {}).length > 0) {
        this.positions.cards = mergePositions(local.cards, cardDefaults);
        this._applyPositionsToDom();
      }
      console.error("DAG layout load failed", err);
    } finally {
      this._layoutHydrated = true;
    }
  }

  measuredBundleHeight(cardId) {
    const el = this.nodesEl?.querySelector(`[data-bundle-id="${CSS.escape(cardId)}"]`);
    if (el?.offsetHeight) return el.offsetHeight;
    const card = this.cards.find((c) => c.id === cardId);
    return card ? bundleHeight(card) : CARD_MIN_H + RQ_ZONE_H;
  }

  worldSize() {
    let maxX = 480;
    let maxY = 360;
    for (const card of this.visibleCards()) {
      const pos = this.positions.cards[card.id];
      if (!pos) continue;
      maxX = Math.max(maxX, pos.x + CARD_W + 88);
      maxY = Math.max(maxY, pos.y + this.measuredBundleHeight(card.id) + 88);
    }
    return { width: maxX, height: maxY };
  }

  _cardAnchor(cardId, side) {
    const pos = this.positions.cards[cardId];
    if (!pos) return null;
    const bundleEl = this.nodesEl?.querySelector(`[data-bundle-id="${CSS.escape(cardId)}"]`);
    const rqEl = bundleEl?.querySelector(".kanban-dag-rq-stack");
    const cardEl = bundleEl?.querySelector(".kanban-dag-card");
    const card = this.cards.find((c) => c.id === cardId);
    const rqH = rqEl?.offsetHeight ?? (card ? RQ_ZONE_H : 0);
    const cardH = cardEl?.offsetHeight ?? (card ? cardBodyHeight(card) : CARD_MIN_H);
    const y = pos.y + rqH + cardH / 2;
    const x = side === "right" ? pos.x + CARD_W : pos.x;
    return { x, y };
  }

  collectEdges() {
    const edges = [];
    for (const card of this.visibleCards()) {
      for (const depId of card.depends_on || []) {
        if (!this.isCardVisible(depId)) continue;
        const from = this._cardAnchor(depId, "right");
        const to = this._cardAnchor(card.id, "left");
        if (!from || !to) continue;
        edges.push({
          kind: "depends",
          from: depId,
          to: card.id,
          path: edgePath(from, to),
        });
      }
    }
    return edges;
  }

  _mount() {
    const size = this.worldSize();
    this.rootEl.innerHTML = `
      <div class="kanban-dag-viewport" data-dag-viewport>
        <div class="kanban-dag-floatbar" role="toolbar" aria-label="Инструменты графа">
          <div class="kanban-dag-toolbar__tools">
            <button type="button" class="kanban-dag-tool is-active" data-dag-tool="move" aria-pressed="true" title="Перемещение">✥</button>
            <button type="button" class="kanban-dag-tool" data-dag-tool="arrow" aria-pressed="false" title="Направленная связь">→</button>
            <button type="button" class="kanban-dag-tool" data-dag-action="layout" title="Упорядочить по связям">⫴</button>
            <button type="button" class="kanban-dag-tool kanban-dag-tool--wide" data-dag-action="toggle-qa" aria-pressed="false" title="Показать Q/A">Q/A</button>
          </div>
          <div class="kanban-dag-toolbar__actions">
            <button type="button" class="kanban-dag-tool" data-dag-action="zoom-out" title="Уменьшить" aria-label="Уменьшить">−</button>
            <button type="button" class="kanban-dag-tool" data-dag-action="zoom-in" title="Увеличить" aria-label="Увеличить">+</button>
            <button type="button" class="kanban-dag-tool" data-dag-action="suggest" title="Предложить DAG">✦</button>
            <button type="button" class="kanban-dag-tool" data-dag-action="reset-view" title="Все карточки в вид" aria-label="Все карточки в вид">⌂</button>
          </div>
        </div>
        <div class="kanban-dag-link-hint hidden" data-dag-link-hint aria-live="polite"></div>
        <div class="kanban-dag-world" data-dag-world style="width:${size.width}px;height:${size.height}px">
          <svg class="kanban-dag-edges" width="${size.width}" height="${size.height}" aria-hidden="true">
            <defs>
              <marker id="kanban-dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
                <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor"></path>
              </marker>
            </defs>
            <g data-dag-edges></g>
          </svg>
          <div class="kanban-dag-nodes" data-dag-nodes></div>
          <svg class="kanban-dag-edge-hits" width="${size.width}" height="${size.height}" aria-hidden="true">
            <g data-dag-edge-hits></g>
          </svg>
        </div>
      </div>
      <div id="kanban-dag-suggest-panel" class="kanban-dag-suggest kanban-dag-suggest--dock hidden" aria-live="polite"></div>
    `;

    this.viewportEl = this.rootEl.querySelector("[data-dag-viewport]");
    this.worldEl = this.rootEl.querySelector("[data-dag-world]");
    this.edgesEl = this.rootEl.querySelector("[data-dag-edges]");
    this.edgeHitsSvgEl = this.rootEl.querySelector("svg.kanban-dag-edge-hits");
    this.edgeHitsEl = this.edgeHitsSvgEl?.querySelector("[data-dag-edge-hits]");
    this.nodesEl = this.rootEl.querySelector("[data-dag-nodes]");
    this.linkHintEl = this.rootEl.querySelector("[data-dag-link-hint]");

    this._renderNodes();
    this._scheduleEdgeRender();
    this._applyCamera();
    this._bindToolbar();
    this._bindViewport();
    this._bindViewportResize();
    this._bindEdgeInteraction();
    this._bindEscape();
    this._bindNodeDelegation();
    this._syncToolCursors();
    this._scheduleFitView();
  }

  _bindNodeDelegation() {
    if (this._delegationBound) return;
    this._delegationBound = true;

    this.nodesEl.addEventListener("click", (e) => {
      const reportBtn = e.target.closest('[data-action="report"]');
      if (!reportBtn) return;
      const bundle = reportBtn.closest("[data-bundle-id]");
      if (!bundle) return;
      e.stopPropagation();
      const card = this.cards.find((c) => c.id === bundle.dataset.bundleId);
      if (card) this.ctx.onOpenReport?.(card);
    });

    this.nodesEl.addEventListener("pointerdown", (e) => {
      const bundle = e.target.closest("[data-bundle-id]");
      if (!bundle || e.button !== 0) return;
      const cardId = bundle.dataset.bundleId;
      const cardEl = bundle.querySelector("[data-node-kind='card']");

      if (this.tool === "arrow") {
        if (e.target.closest('[data-action="report"]')) return;
        e.preventDefault();
        e.stopPropagation();
        this._beginLinkDrag(cardId, bundle, e.clientX, e.clientY);
        return;
      }

      if (!cardEl?.contains(e.target) || e.target.closest("button")) return;
      e.stopPropagation();
      cardEl.setPointerCapture(e.pointerId);
      const pos = this.positions.cards[cardId];
      this.drag = {
        cardId,
        bundleEl: bundle,
        cardEl,
        startX: e.clientX,
        startY: e.clientY,
        originX: pos.x,
        originY: pos.y,
      };
      bundle.classList.add("is-dragging");
    });

    this.nodesEl.addEventListener("pointermove", (e) => {
      if (!this.drag) return;
      const { cardId, bundleEl, startX, startY, originX, originY } = this.drag;
      const dx = (e.clientX - startX) / this.camera.scale;
      const dy = (e.clientY - startY) / this.camera.scale;
      const nx = originX + dx;
      const ny = originY + dy;
      this.positions.cards[cardId] = { x: nx, y: ny };
      bundleEl.style.left = `${nx}px`;
      bundleEl.style.top = `${ny}px`;
      this._renderEdges();
    });

    const endDrag = (e) => {
      if (!this.drag) return;
      const { bundleEl, cardEl } = this.drag;
      this.drag = null;
      bundleEl.classList.remove("is-dragging");
      this.persistLayout();
      try {
        cardEl?.releasePointerCapture(e.pointerId);
      } catch {
        /* */
      }
    };
    this.nodesEl.addEventListener("pointerup", endDrag);
    this.nodesEl.addEventListener("pointercancel", endDrag);
  }

  _syncToolCursors() {
    this.viewportEl?.classList.toggle("is-arrow-tool", this.tool === "arrow");
    this.rootEl.classList.toggle("kanban-dag--arrow-tool", this.tool === "arrow");
    this.rootEl.classList.toggle("kanban-dag--show-qa", this.showQA);
    this._updateLinkHint();
    this._renderEdgeHits();
  }

  _updateLinkHint() {
    if (!this.linkHintEl) return;
    if (this.tool === "move" && this.selectedEdge) {
      this.linkHintEl.textContent = "Delete / Backspace — удалить · двойной клик — тоже удалить";
      this.linkHintEl.classList.remove("hidden");
      return;
    }
    if (this.tool === "arrow" && this.arrowDraft) {
      this.linkHintEl.textContent = "Отпустите на целевой карточке (prerequisite → зависимый)";
      this.linkHintEl.classList.remove("hidden");
      return;
    }
    if (this.tool === "arrow") {
      this.linkHintEl.textContent = "Зажмите на источнике и отпустите на целевой карточке";
      this.linkHintEl.classList.remove("hidden");
      return;
    }
    this.linkHintEl.classList.add("hidden");
  }

  _setTool(tool) {
    this.tool = tool;
    this._cancelArrowDraft();
    this._clearEdgeSelection();
    this.rootEl.querySelectorAll("[data-dag-tool]").forEach((btn) => {
      const active = btn.dataset.dagTool === tool;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    this._syncToolCursors();
  }

  _rqStackHtml(card) {
    const linked = questionsForCard(this.questions, card.id);
    if (!linked.length) return '<div class="kanban-dag-rq-stack is-empty"></div>';

    const closed = isCardClosed(card);
    const pills = linked
      .map((q) => {
        const answer = (q.narrative || q.answer || "").trim();
        const shortQ = q.question.length > 42 ? `${q.question.slice(0, 42)}…` : q.question;
        const showAnswer = closed && answer;
        return `<div class="kanban-dag-rq-pill${showAnswer ? " is-answered" : ""}" data-rq-id="${escapeHtml(q.id)}">
          <button type="button" class="kanban-dag-rq-pill__trigger" aria-label="Исследовательский вопрос">?</button>
          <div class="kanban-dag-rq-pill__flyout" role="tooltip">
            <p class="kanban-dag-rq-pill__q">${escapeHtml(q.question)}</p>
            ${showAnswer ? `<p class="kanban-dag-rq-pill__a">${escapeHtml(answer)}</p>` : ""}
          </div>
          <span class="kanban-dag-rq-pill__label">${escapeHtml(shortQ)}</span>
        </div>`;
      })
      .join("");

    return `<div class="kanban-dag-rq-stack">${pills}</div>`;
  }

  _scheduleEdgeRender() {
    if (this._edgeRenderRaf) cancelAnimationFrame(this._edgeRenderRaf);
    this._edgeRenderRaf = requestAnimationFrame(() => {
      this._edgeRenderRaf = null;
      this._renderEdges();
    });
  }

  _renderNodes() {
    const cards = this.visibleCards();
    const hiddenCount = this.cards.length - cards.length;

    const bundles = cards
      .map((card) => {
        const pos = this.positions.cards[card.id] || { x: 0, y: 0 };
        const phase = dagCardPhase(card.column_id);
        const tagsHtml = this.ctx.cardTagsHtml?.(card) || "";
        return `<div class="kanban-dag-bundle" data-bundle-id="${escapeHtml(card.id)}" style="left:${pos.x}px;top:${pos.y}px;width:${CARD_W}px">
          ${this._rqStackHtml(card)}
          <article class="kanban-dag-card kanban-dag-card--${phase}" data-node-kind="card" data-node-id="${escapeHtml(card.id)}" data-dag-phase="${phase}">
            <div class="kanban-dag-card__head">
              ${dagStatusHtml(phase)}
              <h3 class="kanban-dag-card__title">${escapeHtml(card.title)}</h3>
            </div>
            <button type="button" class="kanban-dag-link-handle" data-action="link" title="Тянуть связь" aria-label="Тянуть связь">⤓</button>
            <button type="button" class="kanban-dag-card__btn" data-action="report" title="Отчёт" aria-label="Отчёт">↗</button>
          </article>
          ${tagsHtml ? `<div class="kanban-dag-card__tags">${tagsHtml}</div>` : ""}
        </div>`;
      })
      .join("");

    const filterNote =
      hiddenCount > 0
        ? `<div class="kanban-dag-filter-note" aria-live="polite">Скрыто ${hiddenCount} по фильтру тегов</div>`
        : "";

    this.nodesEl.innerHTML = bundles + filterNote;
  }

  _renderEdges() {
    const edges = this.collectEdges();
    const draft = this.arrowDraft;
    const draftPath = draft
      ? edgePath(draft.anchor, this._clientToWorld(draft.cursorX, draft.cursorY))
      : "";

    this.edgesEl.innerHTML =
      edges
        .map(
          (e) =>
            `<path class="kanban-dag-edge kanban-dag-edge--depends" data-edge-from="${escapeHtml(e.from)}" data-edge-to="${escapeHtml(e.to)}" d="${e.path}" marker-end="url(#kanban-dag-arrow)"></path>`
        )
        .join("") +
      (draftPath
        ? `<path class="kanban-dag-edge kanban-dag-edge--draft" data-dag-draft d="${draftPath}" marker-end="url(#kanban-dag-arrow)"></path>`
        : "");

    this._renderEdgeHits(edges);
  }

  _renderEdgeHits(edges = null) {
    if (!this.edgeHitsEl) return;
    if (this.tool === "arrow") {
      this.edgeHitsEl.innerHTML = "";
      return;
    }
    const list = edges || this.collectEdges();
    this.edgeHitsEl.innerHTML = list
      .map(
        (e) =>
          `<g class="kanban-dag-edge-group" data-edge-from="${escapeHtml(e.from)}" data-edge-to="${escapeHtml(e.to)}" data-edge-kind="depends" title="Двойной клик — удалить связь">
            <path class="kanban-dag-edge-hit" d="${e.path}" vector-effect="non-scaling-stroke" />
          </g>`
      )
      .join("");

    if (this.selectedEdge) {
      const { edgeFrom, edgeTo } = this.selectedEdge.dataset;
      const stillThere = this.edgeHitsEl.querySelector(
        `[data-edge-from="${CSS.escape(edgeFrom || "")}"][data-edge-to="${CSS.escape(edgeTo || "")}"]`
      );
      if (stillThere) this._selectEdge(stillThere);
      else this._clearEdgeSelection();
    }
  }

  _bindEdgeInteraction() {
    if (this._edgeInteractionBound || !this.viewportEl) return;
    this._edgeInteractionBound = true;

    this.viewportEl.addEventListener(
      "click",
      (e) => {
        if (this.tool === "arrow") return;
        const group = e.target.closest(".kanban-dag-edge-group");
        if (!group) return;
        e.preventDefault();
        e.stopPropagation();
        this._selectEdge(group);
      },
      true
    );

    this.viewportEl.addEventListener(
      "dblclick",
      (e) => {
        if (this.tool === "arrow") return;
        const group = e.target.closest(".kanban-dag-edge-group");
        if (!group) return;
        e.preventDefault();
        e.stopPropagation();
        void this._removeEdge(group);
      },
      true
    );
  }

  _selectEdge(groupEl) {
    this.edgeHitsEl?.querySelectorAll(".kanban-dag-edge-group.is-selected").forEach((el) => {
      el.classList.remove("is-selected");
    });
    this.selectedEdge = groupEl;
    groupEl.classList.add("is-selected");
    this.edgesEl?.querySelectorAll(".kanban-dag-edge--depends").forEach((pathEl) => {
      const selected =
        pathEl.dataset.edgeFrom === groupEl.dataset.edgeFrom &&
        pathEl.dataset.edgeTo === groupEl.dataset.edgeTo;
      pathEl.classList.toggle("is-selected", selected);
    });
    this._updateLinkHint();
  }

  _clearEdgeSelection() {
    this.selectedEdge = null;
    this.edgeHitsEl?.querySelectorAll(".kanban-dag-edge-group.is-selected").forEach((el) => {
      el.classList.remove("is-selected");
    });
    this.edgesEl?.querySelectorAll(".kanban-dag-edge--depends.is-selected").forEach((el) => {
      el.classList.remove("is-selected");
    });
    this._updateLinkHint();
  }

  _clientToWorld(clientX, clientY) {
    const rect = this.viewportEl.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    return {
      x: (mx - this.camera.x) / this.camera.scale,
      y: (my - this.camera.y) / this.camera.scale,
    };
  }

  _applyCamera() {
    this.worldEl.style.transform = `translate(${this.camera.x}px, ${this.camera.y}px) scale(${this.camera.scale})`;
    this.worldEl.style.transformOrigin = "0 0";
  }

  _contentBounds() {
    const cards = this.visibleCards();
    if (!cards.length) return null;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const card of cards) {
      const pos = this.positions.cards[card.id];
      if (!pos) continue;
      const h = this.measuredBundleHeight(card.id);
      minX = Math.min(minX, pos.x);
      minY = Math.min(minY, pos.y);
      maxX = Math.max(maxX, pos.x + CARD_W);
      maxY = Math.max(maxY, pos.y + h);
    }
    if (!Number.isFinite(minX)) return null;
    return { minX, minY, maxX, maxY };
  }

  _scheduleFitView() {
    if (this._fitRaf) cancelAnimationFrame(this._fitRaf);
    this._fitRaf = requestAnimationFrame(() => {
      this._fitRaf = requestAnimationFrame(() => {
        this._fitRaf = null;
        this._fitViewToContent();
      });
    });
  }

  _fitViewToContent(padding = 56) {
    const bounds = this._contentBounds();
    if (!bounds || !this.viewportEl) return;
    const vpW = this.viewportEl.clientWidth;
    const vpH = this.viewportEl.clientHeight;
    if (vpW < 40 || vpH < 40) return;

    const contentW = bounds.maxX - bounds.minX + padding * 2;
    const contentH = bounds.maxY - bounds.minY + padding * 2;
    const scale = Math.min(1.6, Math.max(0.35, Math.min(vpW / contentW, vpH / contentH)));
    this.camera.scale = scale;
    this.camera.x = (vpW - contentW * scale) / 2 - (bounds.minX - padding) * scale;
    this.camera.y = (vpH - contentH * scale) / 2 - (bounds.minY - padding) * scale;
    this._applyCamera();
    this._scheduleEdgeRender();
  }

  _bindViewportResize() {
    if (this._resizeObserver || !this.viewportEl) return;
    this._resizeObserver = new ResizeObserver(() => {
      if (this.viewportEl.clientWidth < 40 || this.viewportEl.clientHeight < 40) return;
      clearTimeout(this._resizeFitTimer);
      this._resizeFitTimer = setTimeout(() => this._scheduleFitView(), 80);
    });
    this._resizeObserver.observe(this.viewportEl);
  }

  _bindToolbar() {
    this.rootEl.querySelectorAll("[data-dag-tool]").forEach((btn) => {
      btn.addEventListener("click", () => this._setTool(btn.dataset.dagTool));
    });

    this.rootEl.querySelector('[data-dag-action="toggle-qa"]')?.addEventListener("click", () => {
      this.showQA = !this.showQA;
      const btn = this.rootEl.querySelector('[data-dag-action="toggle-qa"]');
      btn?.classList.toggle("is-active", this.showQA);
      btn?.setAttribute("aria-pressed", this.showQA ? "true" : "false");
      this._syncToolCursors();
      this._renderNodes();
      this._scheduleEdgeRender();
    });

    this.rootEl.querySelector('[data-dag-action="layout"]')?.addEventListener("click", () => {
      void this._applyAutoLayout();
    });

    this.rootEl.querySelector('[data-dag-action="zoom-in"]')?.addEventListener("click", () => {
      this.camera.scale = Math.min(2, this.camera.scale * 1.12);
      this._applyCamera();
      this._renderEdges();
    });
    this.rootEl.querySelector('[data-dag-action="zoom-out"]')?.addEventListener("click", () => {
      this.camera.scale = Math.max(0.35, this.camera.scale / 1.12);
      this._applyCamera();
      this._renderEdges();
    });

    this.rootEl.querySelector('[data-dag-action="suggest"]')?.addEventListener("click", async () => {
      const btn = this.rootEl.querySelector('[data-dag-action="suggest"]');
      if (btn) btn.disabled = true;
      try {
        const result = await this.ctx.onSuggestDag?.();
        this._renderSuggestPanel(result?.suggestions || []);
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    this.rootEl.querySelector('[data-dag-action="reset-view"]')?.addEventListener("click", () => {
      this._scheduleFitView();
    });
  }

  async _applyAutoLayout() {
    const cards = this.visibleCards();
    if (!cards.length) return;
    const heightFor = (card) => this.measuredBundleHeight(card.id);
    const target = computeAutoLayout(cards, heightFor);
    await this._animatePositions(target);
    this.persistLayout();
    this._resizeWorld();
    this._renderEdges();
    this._scheduleFitView();
  }

  _resizeWorld() {
    const size = this.worldSize();
    this.worldEl.style.width = `${size.width}px`;
    this.worldEl.style.height = `${size.height}px`;
    for (const svg of [this.rootEl.querySelector("svg.kanban-dag-edges"), this.edgeHitsSvgEl]) {
      svg?.setAttribute("width", size.width);
      svg?.setAttribute("height", size.height);
    }
  }

  _animatePositions(target) {
    const start = performance.now();
    const from = { ...this.positions.cards };
    if (this.layoutAnim) cancelAnimationFrame(this.layoutAnim);

    return new Promise((resolve) => {
      const tick = (now) => {
        const t = Math.min(1, (now - start) / LAYOUT_ANIM_MS);
        const ease = 1 - (1 - t) ** 3;
        for (const card of this.visibleCards()) {
          const a = from[card.id] || target[card.id] || { x: 0, y: 0 };
          const b = target[card.id] || a;
          this.positions.cards[card.id] = {
            x: a.x + (b.x - a.x) * ease,
            y: a.y + (b.y - a.y) * ease,
          };
          const el = this.nodesEl.querySelector(`[data-bundle-id="${CSS.escape(card.id)}"]`);
          if (el) {
            el.style.left = `${this.positions.cards[card.id].x}px`;
            el.style.top = `${this.positions.cards[card.id].y}px`;
          }
        }
        this._renderEdges();
        if (t < 1) {
          this.layoutAnim = requestAnimationFrame(tick);
        } else {
          this.layoutAnim = null;
          resolve();
        }
      };
      this.layoutAnim = requestAnimationFrame(tick);
    });
  }

  _renderSuggestPanel(suggestions) {
    const panel = this.rootEl.querySelector("#kanban-dag-suggest-panel");
    if (!panel) return;
    if (!suggestions.length) {
      panel.classList.remove("hidden");
      panel.innerHTML = '<p class="kanban-dag-suggest__empty">Новых связей не найдено.</p>';
      return;
    }
    panel.classList.remove("hidden");
    panel.innerHTML = `
      <div class="kanban-dag-suggest__head">
        <h3>Предложенные связи (${suggestions.length})</h3>
        <button type="button" class="btn btn-sm btn-primary" data-suggest-action="apply">Применить</button>
      </div>
      <ul class="kanban-dag-suggest__list">${suggestions
        .map(
          (s, i) => `<li><label><input type="checkbox" data-suggest-index="${i}" checked />
            <span><strong>${escapeHtml(s.from_title)}</strong> → <strong>${escapeHtml(s.to_title)}</strong></span>
            <span class="kanban-dag-suggest__reason">${escapeHtml(s.reason || "")}</span></label></li>`
        )
        .join("")}</ul>`;
    panel.querySelector("[data-suggest-action='apply']")?.addEventListener("click", async () => {
      const selected = suggestions.filter((_, i) => panel.querySelector(`input[data-suggest-index="${i}"]`)?.checked);
      await this.ctx.onApplySuggestions?.(selected);
      panel.classList.add("hidden");
      await this.ctx.onRefresh?.();
    });
  }

  _bindViewport() {
    let pan = null;

    this.viewportEl.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        const rect = this.viewportEl.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const factor = e.deltaY < 0 ? 1.08 : 1 / 1.08;
        const next = Math.min(2, Math.max(0.35, this.camera.scale * factor));
        const wx = (mx - this.camera.x) / this.camera.scale;
        const wy = (my - this.camera.y) / this.camera.scale;
        this.camera.scale = next;
        this.camera.x = mx - wx * next;
        this.camera.y = my - wy * next;
        this._applyCamera();
        this._renderEdges();
      },
      { passive: false }
    );

    this.viewportEl.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || e.target.closest(".kanban-dag-floatbar")) return;
      if (this.tool === "arrow") return;
      if (e.target.closest(".kanban-dag-edge-hit, .kanban-dag-edge-group")) return;

      this._clearEdgeSelection();

      if (e.target.closest(".kanban-dag-rq-pill__trigger, [data-bundle-id]")) return;

      this.viewportEl.setPointerCapture(e.pointerId);
      pan = { x: e.clientX, y: e.clientY, cx: this.camera.x, cy: this.camera.y };
      this.viewportEl.classList.add("is-panning");
    });

    this.viewportEl.addEventListener("pointermove", (e) => {
      if (!pan) return;
      this.camera.x = pan.cx + (e.clientX - pan.x);
      this.camera.y = pan.cy + (e.clientY - pan.y);
      this._applyCamera();
      this._renderEdges();
    });

    const endPan = (e) => {
      if (!pan) return;
      pan = null;
      this.viewportEl.classList.remove("is-panning");
      try {
        this.viewportEl.releasePointerCapture(e.pointerId);
      } catch {
        /* */
      }
    };
    this.viewportEl.addEventListener("pointerup", endPan);
    this.viewportEl.addEventListener("pointercancel", endPan);
  }

  _bindEscape() {
    this._onKeyDown = (e) => {
      if (e.key === "Escape") {
        this._cancelArrowDraft();
        this._clearEdgeSelection();
        return;
      }
      if ((e.key === "Delete" || e.key === "Backspace") && this.selectedEdge) {
        e.preventDefault();
        void this._removeEdge(this.selectedEdge);
      }
    };
    document.addEventListener("keydown", this._onKeyDown);
  }

  _teardownLinkHandlers() {
    if (this._linkMoveHandler) {
      document.removeEventListener("pointermove", this._linkMoveHandler);
      this._linkMoveHandler = null;
    }
    if (this._linkUpHandler) {
      document.removeEventListener("pointerup", this._linkUpHandler);
      document.removeEventListener("pointercancel", this._linkUpHandler);
      this._linkUpHandler = null;
    }
  }

  _bundleUnderPoint(clientX, clientY) {
    const layers = [this.edgeHitsSvgEl, this.rootEl.querySelector("svg.kanban-dag-edges")];
    const prev = layers.map((el) => {
      const p = el?.style.pointerEvents;
      if (el) el.style.pointerEvents = "none";
      return [el, p];
    });
    const bundle = document.elementFromPoint(clientX, clientY)?.closest("[data-bundle-id]");
    for (const [el, p] of prev) {
      if (el) el.style.pointerEvents = p || "";
    }
    return bundle;
  }

  _cancelArrowDraft() {
    this._teardownLinkHandlers();
    if (!this.arrowDraft) {
      this._updateLinkHint();
      return;
    }
    this.arrowDraft = null;
    this.nodesEl?.querySelectorAll(".is-arrow-source, .is-link-target").forEach((el) => {
      el.classList.remove("is-arrow-source", "is-link-target");
    });
    this._renderEdges();
    this._updateLinkHint();
  }

  _beginLinkDrag(cardId, bundleEl, clientX, clientY) {
    const anchor = this._cardAnchor(cardId, "right");
    if (!anchor) return;
    this._cancelArrowDraft();
    this.arrowDraft = {
      fromCardId: cardId,
      anchor,
      cursorX: clientX,
      cursorY: clientY,
    };
    bundleEl.classList.add("is-arrow-source");
    this._renderEdges();
    this._updateLinkHint();

    this._linkMoveHandler = (ev) => {
      if (!this.arrowDraft) return;
      this.arrowDraft.cursorX = ev.clientX;
      this.arrowDraft.cursorY = ev.clientY;
      this.nodesEl?.querySelectorAll(".is-link-target").forEach((el) => el.classList.remove("is-link-target"));
      const hover = this._bundleUnderPoint(ev.clientX, ev.clientY);
      if (hover && hover.dataset.bundleId !== this.arrowDraft.fromCardId) {
        hover.classList.add("is-link-target");
      }
      this._renderEdges();
    };
    this._linkUpHandler = (ev) => {
      void this._finishLinkDrag(ev);
    };
    document.addEventListener("pointermove", this._linkMoveHandler);
    document.addEventListener("pointerup", this._linkUpHandler);
    document.addEventListener("pointercancel", this._linkUpHandler);
  }

  async _finishLinkDrag(ev) {
    this._teardownLinkHandlers();
    const fromId = this.arrowDraft?.fromCardId;
    if (!fromId) {
      this._cancelArrowDraft();
      return;
    }
    const target = this._bundleUnderPoint(ev.clientX, ev.clientY);
    const toId = target?.dataset?.bundleId;
    if (toId && toId !== fromId) {
      await this._completeArrowDraft(toId);
      return;
    }
    this._cancelArrowDraft();
    this.ctx.onStatus?.("Отпустите на другой карточке", true);
  }

  async _completeArrowDraft(toCardId) {
    const fromId = this.arrowDraft?.fromCardId;
    if (!fromId || fromId === toCardId) {
      this._cancelArrowDraft();
      return;
    }

    const toCard = this.cards.find((c) => c.id === toCardId);
    if (toCard && !(toCard.depends_on || []).includes(fromId)) {
      toCard.depends_on = [...(toCard.depends_on || []), fromId];
    }
    this._cancelArrowDraft();
    this._renderEdges();

    try {
      await this.ctx.onAddEdge?.(toCardId, fromId);
      this.ctx.onStatus?.("Связь сохранена");
    } catch (err) {
      if (toCard) {
        toCard.depends_on = (toCard.depends_on || []).filter((d) => d !== fromId);
      }
      this._renderEdges();
      this.ctx.onStatus?.(err?.message || "Не удалось сохранить связь", true);
      console.error("DAG link failed", err);
    }
  }

  async _removeEdge(edgeEl) {
    const fromId = edgeEl.dataset.edgeFrom || "";
    const toId = edgeEl.dataset.edgeTo || "";
    if (!fromId || !toId) return;
    this._clearEdgeSelection();

    const toCard = this.cards.find((c) => c.id === toId);
    const prevDeps = toCard ? [...(toCard.depends_on || [])] : [];
    if (toCard) {
      toCard.depends_on = prevDeps.filter((d) => d !== fromId);
    }
    this._scheduleEdgeRender();

    try {
      await this.ctx.onRemoveEdge?.(toId, fromId);
      this.ctx.onStatus?.("Связь удалена");
    } catch (err) {
      if (toCard) toCard.depends_on = prevDeps;
      this._scheduleEdgeRender();
      this.ctx.onStatus?.(err?.message || "Не удалось удалить связь", true);
      console.error("DAG unlink failed", err);
    }
  }

  refresh(board, node, ctx = {}) {
    this.board = board;
    this.node = node;
    this.ctx = { ...this.ctx, ...ctx, node };
    this.cards = board?.cards || [];
    this.questions = node?.research_questions || [];
    const cardDefaults = defaultCardPositions(this.cards);
    void this._hydrateLayoutFromServer(cardDefaults);
    this._renderNodes();
    this._scheduleEdgeRender();
    this._syncToolCursors();
    this._scheduleFitView();
  }
}

export function destroyKanbanDagView() {
  if (activeEditor) {
    activeEditor.destroy();
    activeEditor = null;
  }
}

export function fitKanbanDagView() {
  if (activeEditor) activeEditor._scheduleFitView();
}

export function renderKanbanDagView(rootEl, board, ctx = {}) {
  if (!rootEl || !board) return;
  if (activeEditor) {
    activeEditor.destroy();
    activeEditor = null;
  }
  activeEditor = new KanbanDagEditor(rootEl, board, ctx.node, ctx);
}

export function refreshKanbanDagView(rootEl, board, ctx) {
  if (activeEditor && activeEditor.rootEl === rootEl) {
    activeEditor.refresh(board, ctx.node, ctx);
    return;
  }
  renderKanbanDagView(rootEl, board, ctx);
  fitKanbanDagView();
}
