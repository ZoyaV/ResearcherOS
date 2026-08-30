/**
 * Method milestones timeline under the kanban board.
 * Backed by reports/<method>/milestones.md — sorted chronologically by date.
 */

import { KoiApi } from "./api.js?v=20260723b";

const COLUMN_LABELS = {
  backlog: "Backlog",
  running: "Running",
  done: "Done",
  successful: "Successful",
};

let state = {
  projectId: null,
  nodeId: null,
  board: null,
  readOnly: false,
  exists: false,
  milestones: [],
  relativePath: "",
  /** Milestone open in editor (double-click). */
  editingId: null,
  /** Milestone applied as board card filter (single-click). */
  filterId: null,
  onStatus: null,
  onBoardFilterChange: null,
  loadSeq: 0,
  filterQuery: "",
  _clickTimer: null,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function rootEl() {
  return document.getElementById("kanban-milestones");
}

function todayLabel() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yy = String(d.getFullYear()).slice(-2);
  return `${dd}.${mm}.${yy}`;
}

function parseMilestoneDate(raw) {
  const s = String(raw || "").trim();
  if (!s) return null;
  let m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{2})$/);
  if (m) {
    const y = 2000 + Number(m[3]);
    const dt = new Date(y, Number(m[2]) - 1, Number(m[1]));
    return Number.isNaN(dt.getTime()) ? null : dt;
  }
  m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (m) {
    const dt = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
    return Number.isNaN(dt.getTime()) ? null : dt;
  }
  m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) {
    const dt = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return Number.isNaN(dt.getTime()) ? null : dt;
  }
  return null;
}

function sortMilestones(list) {
  return [...(list || [])].sort((a, b) => {
    const da = parseMilestoneDate(a.date);
    const db = parseMilestoneDate(b.date);
    if (da && db) {
      const diff = da - db;
      if (diff !== 0) return diff;
    } else if (da && !db) return -1;
    else if (!da && db) return 1;
    const t = String(a.title || "").localeCompare(String(b.title || ""), "ru");
    if (t !== 0) return t;
    return String(a.id || "").localeCompare(String(b.id || ""));
  });
}

function boardCards(board) {
  return Array.isArray(board?.cards) ? board.cards : [];
}

function cardById(board, cardId) {
  return boardCards(board).find((c) => c.id === cardId) || null;
}

function newLocalId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `ms-${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`;
  }
  return `ms-${Math.random().toString(16).slice(2, 10)}`;
}

async function persist(milestones) {
  if (!state.projectId || !state.nodeId || state.readOnly) return null;
  const ordered = sortMilestones(milestones);
  const data = await KoiApi.saveMilestones(state.projectId, state.nodeId, ordered);
  state.exists = true;
  state.milestones = sortMilestones(data.milestones || ordered);
  state.relativePath = data.relative_path || state.relativePath;
  return data;
}

function setStatus(msg, isError = false) {
  if (typeof state.onStatus === "function") state.onStatus(msg, isError);
}

function notifyBoardFilter() {
  if (typeof state.onBoardFilterChange !== "function") return;
  if (!state.filterId) {
    state.onBoardFilterChange(null);
    return;
  }
  const ms = state.milestones.find((m) => m.id === state.filterId);
  if (!ms) {
    state.filterId = null;
    state.onBoardFilterChange(null);
    return;
  }
  state.onBoardFilterChange({
    milestoneId: ms.id,
    title: ms.title || "Milestone",
    cardIds: [...(ms.card_ids || [])],
  });
}

function clearClickTimer() {
  if (state._clickTimer) {
    clearTimeout(state._clickTimer);
    state._clickTimer = null;
  }
}

function applyFilterToggle(id) {
  state.filterId = state.filterId === id ? null : id;
  // Filtering does not open the editor.
  notifyBoardFilter();
  render();
}

function openEditor(id) {
  clearClickTimer();
  state.editingId = id;
  state.filterQuery = "";
  // While editing, clear board filter so backlog/running cards stay visible to attach.
  if (state.filterId) {
    state.filterId = null;
    notifyBoardFilter();
  }
  render();
  bindBoardCardAttachClicks();
}

function closeEditor() {
  state.editingId = null;
  state.filterQuery = "";
  unbindBoardCardAttachClicks();
  render();
}


const COLUMN_ORDER = ["backlog", "running", "done", "successful"];

function unbindBoardCardAttachClicks() {
  const boardEl = document.getElementById("kanban-board");
  if (!boardEl || !boardEl._msAttachHandler) return;
  boardEl.removeEventListener("click", boardEl._msAttachHandler, true);
  boardEl._msAttachHandler = null;
  boardEl.classList.remove("is-ms-attach-mode");
}

function bindBoardCardAttachClicks() {
  unbindBoardCardAttachClicks();
  if (state.readOnly || !state.editingId) return;
  const boardEl = document.getElementById("kanban-board");
  if (!boardEl) return;
  boardEl.classList.add("is-ms-attach-mode");
  const handler = (ev) => {
    const cardEl = ev.target.closest?.(".kanban-card");
    if (!cardEl || !boardEl.contains(cardEl)) return;
    // Don't steal report / drag / inline-edit controls.
    if (ev.target.closest(".card-expand-report, .card-drag-handle, .card-delete, .inline-edit-field, a, button")) {
      return;
    }
    const cardId = cardEl.getAttribute("data-card-id");
    if (!cardId || !state.editingId) return;
    ev.preventDefault();
    ev.stopPropagation();
    const ms = state.milestones.find((m) => m.id === state.editingId);
    if (!ms) return;
    const set = new Set(ms.card_ids || []);
    if (set.has(cardId)) set.delete(cardId);
    else set.add(cardId);
    state.milestones = state.milestones.map((m) =>
      m.id === state.editingId ? { ...m, card_ids: [...set] } : m
    );
    // Optimistic UI; persist on Save. Mark editor dirty via class.
    rootEl()?.querySelector(".ms-editor")?.classList.add("is-dirty");
    syncBoardAttachHighlights();
    // Refresh linked list + checkboxes without closing editor.
    render();
    bindBoardCardAttachClicks();
  };
  boardEl._msAttachHandler = handler;
  boardEl.addEventListener("click", handler, true);
  syncBoardAttachHighlights();
}

function syncBoardAttachHighlights() {
  const boardEl = document.getElementById("kanban-board");
  if (!boardEl) return;
  const ms = state.milestones.find((m) => m.id === state.editingId);
  const linked = new Set(ms?.card_ids || []);
  boardEl.querySelectorAll(".kanban-card").forEach((el) => {
    const id = el.getAttribute("data-card-id");
    el.classList.toggle("is-ms-attached", Boolean(id && linked.has(id)));
  });
}

function timelineHtml() {
  const items = sortMilestones(state.milestones);
  if (!items.length) {
    return `<div class="ms-empty">No milestones yet — add the first one to the timeline</div>`;
  }
  const nodes = items
    .map((ms, idx) => {
      const filtering = state.filterId === ms.id ? " is-filtering" : "";
      const editing = state.editingId === ms.id ? " is-editing" : "";
      const date = escapeHtml(ms.date || "??.??.??");
      const title = escapeHtml(ms.title || "Milestone");
      const n = (ms.card_ids || []).length;
      const step = `${idx + 1}/${items.length}`;
      const tip = `${title} · click to filter board · double-click to edit`;
      return `
      <li class="ms-node-wrap">
        <button type="button" class="ms-node${filtering}${editing}" data-ms-id="${escapeHtml(ms.id)}" aria-pressed="${
        state.filterId === ms.id ? "true" : "false"
      }" title="${escapeHtml(tip)}">
          <span class="ms-date">${date}</span>
          <span class="ms-dot" aria-hidden="true"></span>
          <span class="ms-name">${title}</span>
          <span class="ms-meta">
            <span class="ms-step">${step}</span>
            <span class="ms-count${n ? "" : " is-empty"}" data-ms-count="${escapeHtml(ms.id)}" title="${
        n ? "Show cards" : "No linked cards"
      }">${n ? `${n} cards` : "no cards"}</span>
          </span>
        </button>
      </li>`;
    })
    .join("");
  return `<ol class="ms-track" aria-label="Milestones by date">${nodes}</ol>`;
}

function editorHtml(ms) {
  if (!ms) return "";
  const cards = boardCards(state.board);
  const linked = new Set(ms.card_ids || []);
  const q = (state.filterQuery || "").trim().toLowerCase();
  const byCol = new Map(COLUMN_ORDER.map((id) => [id, []]));
  for (const c of cards) {
    const col = COLUMN_ORDER.includes(c.column_id) ? c.column_id : "backlog";
    if (!byCol.has(col)) byCol.set(col, []);
    byCol.get(col).push(c);
  }
  const options = COLUMN_ORDER.map((col) => {
    const group = (byCol.get(col) || [])
      .slice()
      .sort((a, b) => String(a.title).localeCompare(String(b.title), "ru"));
    if (!group.length) return "";
    const rows = group
      .map((c) => {
        const checked = linked.has(c.id) ? "checked" : "";
        const title = c.title || c.id;
        const hidden = q && !String(title).toLowerCase().includes(q) ? " hidden" : "";
        const colLabel = COLUMN_LABELS[col] || col;
        return `<label class="ms-card-opt${hidden}" data-title="${escapeHtml(
          String(title).toLowerCase()
        )}" data-col="${escapeHtml(col)}">
        <input type="checkbox" value="${escapeHtml(c.id)}" ${checked} ${
          state.readOnly ? "disabled" : ""
        } />
        <span class="ms-card-opt__body">
          <span class="ms-card-opt__title">${escapeHtml(title)}</span>
          <span class="ms-card-opt__col" data-col="${escapeHtml(col)}">${escapeHtml(
          colLabel
        )}</span>
        </span>
      </label>`;
      })
      .join("");
    const visibleCount = group.filter((c) => {
      if (!q) return true;
      return String(c.title || "").toLowerCase().includes(q);
    }).length;
    if (!visibleCount) return "";
    return `<div class="ms-card-group" data-col="${escapeHtml(col)}">
      <div class="ms-card-group__title">${escapeHtml(COLUMN_LABELS[col] || col)} · ${visibleCount}</div>
      ${rows}
    </div>`;
  }).join("");

  return `
    <div class="ms-editor" data-edit-id="${escapeHtml(ms.id)}" role="region" aria-label="Edit milestone">
      <div class="ms-editor__row">
        <label class="ms-field">
          <span>Date</span>
          <input type="text" class="ms-input" data-field="date" value="${escapeHtml(
            ms.date || ""
          )}" placeholder="MM/DD/YY" inputmode="numeric" ${state.readOnly ? "disabled" : ""} />
        </label>
        <label class="ms-field ms-field--grow">
          <span>Title</span>
          <input type="text" class="ms-input" data-field="title" value="${escapeHtml(
            ms.title || ""
          )}" placeholder="Short milestone name" ${state.readOnly ? "disabled" : ""} />
        </label>
      </div>
      <div class="ms-attach">
        ${
          (ms.card_ids || []).length
            ? `<ul class="ms-linked-list" aria-label="Linked cards">${(ms.card_ids || [])
                .map((id) => {
                  const card = cardById(state.board, id);
                  const title = card?.title || id;
                  const col = card?.column_id || "";
                  const colLabel = COLUMN_LABELS[col] || col || "";
                  return `<li class="ms-linked-item"><span class="ms-linked-title">${escapeHtml(
                    title
                  )}</span>${
                    colLabel
                      ? `<span class="ms-card-opt__col" data-col="${escapeHtml(col)}">${escapeHtml(
                          colLabel
                        )}</span>`
                      : ""
                  }</li>`;
                })
                .join("")}</ul>`
            : `<p class="ms-attach-empty">No linked cards yet</p>`
        }
        ${
          state.readOnly
            ? ""
            : `<p class="ms-attach-tip">Click a board card to link or unlink it, or select it below</p>
        <div class="ms-attach__head">
          <span class="ms-attach__label">All columns</span>
          <input type="search" class="ms-input ms-input--search" data-ms-filter value="${escapeHtml(
            state.filterQuery || ""
          )}" placeholder="Filter by name…" autocomplete="off" />
        </div>
        <div class="ms-card-list">${
          options || '<p class="ms-attach-empty">There are no cards on the board yet</p>'
        }</div>`
        }
      </div>
      <div class="ms-editor__actions">
        ${
          state.readOnly
            ? ""
            : `<button type="button" class="btn btn-primary btn-small" data-ms-save>Save</button>
               <button type="button" class="btn btn-small ms-btn-danger" data-ms-delete>Delete</button>`
        }
        <button type="button" class="btn btn-small" data-ms-close>Close</button>
      </div>
    </div>
  `;
}

function render() {
  const el = rootEl();
  if (!el) return;
  state.milestones = sortMilestones(state.milestones);

  if (!state.exists) {
    if (state.readOnly) {
      el.classList.add("hidden");
      el.innerHTML = "";
      /* board filter owned by app.js */
      return;
    }
    el.classList.remove("hidden");
    el.innerHTML = `
      <div class="ms-create-bar">
        <div class="ms-create-copy">
          <h3 class="ms-title">Milestones</h3>
          <p class="ms-create-hint">Optional method milestone timeline · milestones.md</p>
        </div>
        <button type="button" class="btn btn-primary btn-small" data-ms-create>+ Add</button>
      </div>
    `;
    /* board filter owned by app.js */
    wire();
    return;
  }

  el.classList.remove("hidden");
  if (state.filterId && !state.milestones.some((m) => m.id === state.filterId)) {
    state.filterId = null;
    notifyBoardFilter();
  }
  if (state.editingId && !state.milestones.some((m) => m.id === state.editingId)) {
    state.editingId = null;
  }
  const editing = state.milestones.find((m) => m.id === state.editingId) || null;
  const filtering = state.milestones.find((m) => m.id === state.filterId) || null;

  const fileName = (state.relativePath || "milestones.md").split("/").pop();
  const filterHint = filtering
    ? `Filter: ${escapeHtml(filtering.title || "milestone")} · click again to reset`
    : "Click to filter board · double-click to edit";

  el.innerHTML = `
    <div class="ms-shell">
      <div class="ms-head">
        <div class="ms-head__left">
          <h3 class="ms-title">Milestones</h3>
          <span class="ms-sort-hint" title="Timeline order is based on date">by date →</span>
        </div>
        <span class="ms-path" title="${escapeHtml(state.relativePath)}">${escapeHtml(fileName)}</span>
        ${
          state.readOnly
            ? ""
            : `<button type="button" class="btn btn-small" data-ms-add>+ Milestone</button>`
        }
      </div>
      ${timelineHtml()}
      ${
        editing
          ? editorHtml(editing)
          : `<p class="ms-hint">${filterHint}</p>`
      }
    </div>
  `;
  rootEl()?.classList.toggle("is-editing", Boolean(editing));
  wire();
  if (editing) bindBoardCardAttachClicks();
  else unbindBoardCardAttachClicks();
}

function wire() {
  const el = rootEl();
  if (!el) return;

  el.querySelector("[data-ms-create]")?.addEventListener("click", async () => {
    try {
      const data = await KoiApi.createMilestones(state.projectId, state.nodeId);
      state.exists = true;
      state.milestones = sortMilestones(data.milestones || []);
      state.relativePath = data.relative_path || "";
      setStatus("Created milestones.md");
      render();
    } catch (err) {
      setStatus(err.message || "Could not create milestones.md", true);
    }
  });

  el.querySelector("[data-ms-add]")?.addEventListener("click", async () => {
    const created = {
      id: newLocalId(),
      date: todayLabel(),
      title: "New milestone",
      card_ids: [],
    };
    try {
      await persist([...state.milestones, created]);
      openEditor(created.id);
      setStatus("Milestone added");
    } catch (err) {
      setStatus(err.message || "Could not save the milestone", true);
    }
  });

  el.querySelectorAll(".ms-node").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      const id = btn.getAttribute("data-ms-id");
      if (!id) return;
      // Ignore synthetic click that follows dblclick in some browsers after timeout path.
      clearClickTimer();
      state._clickTimer = setTimeout(() => {
        state._clickTimer = null;
        // Single click: filter board; close editor if another milestone.
        if (state.editingId && state.editingId !== id) {
          state.editingId = null;
          state.filterQuery = "";
        }
        applyFilterToggle(id);
      }, 250);
    });
    btn.addEventListener("dblclick", (ev) => {
      ev.preventDefault();
      const id = btn.getAttribute("data-ms-id");
      if (!id) return;
      if (state.readOnly) {
        applyFilterToggle(id);
        return;
      }
      openEditor(id);
    });
  });

  const editor = el.querySelector(".ms-editor");
  if (!editor) return;

  editor.querySelector("[data-ms-close]")?.addEventListener("click", () => {
    closeEditor();
  });

  editor.querySelectorAll('.ms-card-opt input[type="checkbox"]').forEach((input) => {
    input.addEventListener("change", () => {
      const id = editor.getAttribute("data-edit-id");
      if (!id) return;
      const cardIds = [
        ...editor.querySelectorAll('.ms-card-opt input[type="checkbox"]:checked'),
      ].map((el) => el.value);
      state.milestones = state.milestones.map((m) =>
        m.id === id ? { ...m, card_ids: cardIds } : m
      );
      editor.classList.add("is-dirty");
      // Refresh linked list titles without losing scroll where possible
      syncBoardAttachHighlights();
    });
  });

  editor.querySelector("[data-ms-filter]")?.addEventListener("input", (ev) => {
    state.filterQuery = String(ev.target.value || "");
    const q = state.filterQuery.trim().toLowerCase();
    editor.querySelectorAll(".ms-card-opt").forEach((row) => {
      const title = row.getAttribute("data-title") || "";
      row.classList.toggle("hidden", Boolean(q) && !title.includes(q));
    });
  });

  editor.querySelector("[data-ms-save]")?.addEventListener("click", async () => {
    const id = editor.getAttribute("data-edit-id");
    const date = editor.querySelector('[data-field="date"]')?.value?.trim() || "";
    const title =
      editor.querySelector('[data-field="title"]')?.value?.trim() || "Milestone";
    const cardIds = [
      ...editor.querySelectorAll('.ms-card-opt input[type="checkbox"]:checked'),
    ].map((input) => input.value);
    const next = state.milestones.map((m) =>
      m.id === id ? { ...m, date, title, card_ids: cardIds } : m
    );
    try {
      await persist(next);
      if (state.filterId === id) notifyBoardFilter();
      setStatus("Milestone saved");
      render();
    } catch (err) {
      setStatus(err.message || "Save error", true);
    }
  });

  editor.querySelector("[data-ms-delete]")?.addEventListener("click", async () => {
    const id = editor.getAttribute("data-edit-id");
    if (!id) return;
    if (!window.confirm("Delete this milestone?")) return;
    try {
      await persist(state.milestones.filter((m) => m.id !== id));
      if (state.filterId === id) {
        state.filterId = null;
        notifyBoardFilter();
      }
      state.editingId = null;
      state.filterQuery = "";
      setStatus("Milestone deleted");
      render();
    } catch (err) {
      setStatus(err.message || "Could not delete the milestone", true);
    }
  });
}

export function clearKanbanMilestones() {
  clearClickTimer();
  unbindBoardCardAttachClicks();
  const hadFilter = Boolean(state.filterId);
  const onBoardFilterChange = state.onBoardFilterChange;
  state = {
    projectId: null,
    nodeId: null,
    board: null,
    readOnly: false,
    exists: false,
    milestones: [],
    relativePath: "",
    editingId: null,
    filterId: null,
    onStatus: null,
    onBoardFilterChange,
    loadSeq: state.loadSeq + 1,
    filterQuery: "",
    _clickTimer: null,
  };
  if (hadFilter && typeof onBoardFilterChange === "function") {
    onBoardFilterChange(null);
  }
  const el = rootEl();
  if (el) {
    el.classList.add("hidden");
    el.innerHTML = "";
  }
}

export async function refreshKanbanMilestones({
  projectId,
  node,
  board,
  readOnly = false,
  onStatus = null,
  onBoardFilterChange = null,
} = {}) {
  const el = rootEl();
  if (!el || !projectId || !node?.id) {
    clearKanbanMilestones();
    return;
  }

  const seq = ++state.loadSeq;
  state.projectId = projectId;
  state.nodeId = node.id;
  state.board = board;
  state.readOnly = Boolean(readOnly);
  state.onStatus = onStatus;
  state.onBoardFilterChange = onBoardFilterChange;

  try {
    const data = await KoiApi.getMilestones(projectId, node.id);
    if (seq !== state.loadSeq) return;
    state.exists = Boolean(data.exists);
    state.milestones = sortMilestones(data.milestones || []);
    state.relativePath = data.relative_path || "";
    if (state.editingId && !state.milestones.some((m) => m.id === state.editingId)) {
      state.editingId = null;
    }
    if (state.filterId && !state.milestones.some((m) => m.id === state.filterId)) {
      state.filterId = null;
      notifyBoardFilter();
    } else if (state.filterId) {
      notifyBoardFilter();
    }
    render();
  } catch (err) {
    if (seq !== state.loadSeq) return;
    el.classList.add("hidden");
    el.innerHTML = "";
    setStatus(err.message || "Milestones are unavailable", true);
  }
}

/** Clear the milestone board filter externally (for example, from Reset filters). */
export function clearMilestoneBoardFilter() {
  if (!state.filterId && !state.editingId) {
    notifyBoardFilter();
    return;
  }
  clearClickTimer();
  state.filterId = null;
  state.editingId = null;
  state.filterQuery = "";
  notifyBoardFilter();
  if (rootEl()) render();
}
