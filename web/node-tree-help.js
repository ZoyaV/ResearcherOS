/** Explanations of project-tree node types and hints for adding nodes. */

export const NODE_TYPE_HELP = {
  problem: {
    title: "Problem",
    subtitle: "A problem situation in the domain",
    what:
      "What is wrong in the scientific or engineering task and how it manifests in practice. State only the observed failure, without explaining why.",
    content:
      "Use the title for the essence of the problem. In the description, provide context, reproduction conditions, metrics, and the observed failure.",
    example:
      "“On long episodes, the agent makes poor decisions because it does not remember earlier events”",
  },
  cause: {
    title: "Cause",
    subtitle: "Explanatory hypothesis",
    what:
      "A proposed mechanism for why the problem occurs. This is not a solution; it answers the question “why does this happen?”",
    content:
      "Title: “Cause: …”. In the description, identify which component, process, or constraint fails and under what conditions.",
    example: "“Cause: the agent lacks a memory module, so the context of earlier steps is lost”",
  },
  cause_evidence: {
    title: "Evidence",
    subtitle: "Empirical test of a cause",
    what:
      "Which observations or measurements will show whether the explanatory hypothesis is correct, before proposing a remediation.",
    content:
      "Title: “Evidence: …”. In the description, state exactly what you measure or compare. Put the experiment protocol in a method below.",
    example:
      "“Evidence: in episodes longer than 50 steps, the log contains no references to early events”",
  },
  remediation: {
    title: "Remediation hypothesis",
    subtitle: "Intervention hypothesis",
    what:
      "A proposal for weakening or bypassing the cause, or removing the problem entirely by reducing its impact or solving it directly.",
    content:
      "Title: “Remediation: …”. In the description, state what you will change, the expected effect, and the success metric.",
    example:
      "“Remediation: episodic memory that summarizes earlier steps before each action”",
  },
  method: {
    title: "Method",
    subtitle: "Test protocol",
    what:
      "A specific way to test evidence or a remediation hypothesis: what to do, what to measure, and how to interpret the result.",
    content:
      "Use the protocol name as the title. In the description, give steps, dataset, metrics, and supported/refuted criteria. Put run cards on the kanban board.",
    example:
      "“A/B: agent with memory vs. without on episodes longer than 50 steps; metric: success rate”",
  },
};

/** Explain why a child node should be added to a given parent. */
export const ADD_CHILD_WHY = {
  problem: {
    cause: "Formulate an explanatory hypothesis for why the problem occurs.",
  },
  cause: {
    cause_evidence:
      "Test the cause with data: what should be observed if the hypothesis is correct.",
    remediation:
      "Propose an intervention that weakens or bypasses this cause.",
  },
  cause_evidence: {
    method: "Plan an experiment that will collect these observations.",
  },
  remediation: {
    method: "Plan an experiment that will test the remediation hypothesis.",
  },
};

const TYPE_LABELS_FALLBACK = {
  problem: "Problem",
  cause: "Cause",
  cause_evidence: "Evidence",
  remediation: "Hypothesis",
  method: "Method",
};

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

export function typeLabel(nodeType, labels = TYPE_LABELS_FALLBACK) {
  return labels[nodeType] || TYPE_LABELS_FALLBACK[nodeType] || nodeType;
}

export function addChildWhy(parentType, childType) {
  return ADD_CHILD_WHY[parentType]?.[childType] || "";
}

export function addChildPreviewItems(parentType, allowedTypes, labels) {
  return allowedTypes.map((t) => ({
    type: t,
    label: typeLabel(t, labels),
    why: addChildWhy(parentType, t),
    help: NODE_TYPE_HELP[t],
  }));
}

export function formatAddChildFormatHint(nodeType) {
  const h = NODE_TYPE_HELP[nodeType];
  if (!h) return "";
  let html = `<strong>Block format:</strong> ${escapeHtml(h.content)}`;
  if (h.example) {
    html += `<br><span class="add-child-format-example">Example title: ${escapeHtml(h.example)}</span>`;
  }
  return html;
}

export function formatAddChildContextHint(parentType, childType) {
  const why = addChildWhy(parentType, childType);
  if (!why) return "";
  return why;
}

export function formatAddParentIntro(parentType, allowedTypes, labels) {
  const items = addChildPreviewItems(parentType, allowedTypes, labels);
  if (!items.length) return "";
  if (items.length === 1) {
    return `A “${items[0].label}” node will be added under “${typeLabel(parentType, labels)}”.`;
  }
  const names = items.map((i) => `“${i.label}”`).join(" or ");
  return `Under “${typeLabel(parentType, labels)}”, you can add ${names}; select a type below.`;
}

let helpOverlay = null;
let helpOverlayKeyHandler = null;

function buildHelpPanelHtml(help) {
  return `
    <p class="node-type-help-popover-title">${escapeHtml(help.title)}</p>
    ${help.subtitle ? `<p class="node-type-help-popover-subtitle">${escapeHtml(help.subtitle)}</p>` : ""}
    <p class="node-type-help-popover-what">${escapeHtml(help.what)}</p>
    <p class="node-type-help-popover-content"><span class="node-type-help-popover-label">What to write:</span> ${escapeHtml(help.content)}</p>
    ${help.example ? `<p class="node-type-help-popover-example"><span class="node-type-help-popover-label">Example:</span> ${escapeHtml(help.example)}</p>` : ""}`;
}

function ensureHelpOverlay() {
  if (helpOverlay) return helpOverlay;

  helpOverlay = document.createElement("div");
  helpOverlay.id = "node-type-help-overlay";
  helpOverlay.className = "node-type-help-overlay hidden";
  helpOverlay.innerHTML = `
    <div class="node-type-help-backdrop" data-close="node-type-help"></div>
    <div class="node-type-help-panel" role="dialog" aria-modal="true" aria-labelledby="node-type-help-title">
      <button type="button" class="node-type-help-close" aria-label="Close">×</button>
      <div class="node-type-help-panel-body"></div>
    </div>`;

  helpOverlay.querySelector(".node-type-help-backdrop")?.addEventListener("click", closeNodeTypeHelp);
  helpOverlay.querySelector(".node-type-help-close")?.addEventListener("click", closeNodeTypeHelp);

  document.body.appendChild(helpOverlay);
  return helpOverlay;
}

export function closeNodeTypeHelp() {
  if (!helpOverlay || helpOverlay.classList.contains("hidden")) return;
  helpOverlay.classList.add("hidden");
  document.body.classList.remove("node-type-help-open");
  if (helpOverlayKeyHandler) {
    document.removeEventListener("keydown", helpOverlayKeyHandler);
    helpOverlayKeyHandler = null;
  }
}

export function openNodeTypeHelp(nodeType) {
  const help = NODE_TYPE_HELP[nodeType];
  if (!help) return;

  const overlay = ensureHelpOverlay();
  const body = overlay.querySelector(".node-type-help-panel-body");
  const panel = overlay.querySelector(".node-type-help-panel");
  if (!body || !panel) return;

  body.innerHTML = buildHelpPanelHtml(help);
  const titleEl = body.querySelector(".node-type-help-popover-title");
  if (titleEl) titleEl.id = "node-type-help-title";

  overlay.classList.remove("hidden");
  document.body.classList.add("node-type-help-open");

  if (!helpOverlayKeyHandler) {
    helpOverlayKeyHandler = (e) => {
      if (e.key === "Escape") closeNodeTypeHelp();
    };
    document.addEventListener("keydown", helpOverlayKeyHandler);
  }

  overlay.querySelector(".node-type-help-close")?.focus();
}

/**
 * The “?” in a node card corner opens full-screen help.
 */
export function mountNodeTypeHelp(wrap, nodeType) {
  const help = NODE_TYPE_HELP[nodeType];
  if (!help || !wrap) return;

  const mapEl = wrap.querySelector(".map-node");
  if (!mapEl || mapEl.querySelector(".node-type-help-trigger")) return;

  mapEl.classList.add("has-type-help");

  const trigger = document.createElement("span");
  trigger.className = "node-type-help-trigger";
  trigger.title = help.title;
  trigger.innerHTML = `<span class="node-type-help-q" aria-hidden="true">?</span>`;

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();
    openNodeTypeHelp(nodeType);
  });
  trigger.addEventListener("mousedown", (e) => e.stopPropagation());

  mapEl.appendChild(trigger);
}

function parentWrapSelector(parent, projectId) {
  const pid = projectId ? `[data-project-id="${projectId}"]` : "";
  return `.node-wrap[data-node-id="${parent.id}"]${pid}`;
}

function setAddParentHighlight(parent, projectId, on) {
  const sel = parentWrapSelector(parent, projectId);
  document.querySelectorAll(sel).forEach((w) => {
    w.classList.toggle("is-add-parent-highlight", on);
  });
}

function buildAddPreviewGhosts(items) {
  const ghosts = document.createElement("div");
  ghosts.className = "add-preview-ghosts";
  ghosts.setAttribute("aria-hidden", "true");
  ghosts.innerHTML = items
    .map(
      (item) => `
    <div class="add-preview-ghost add-preview-ghost--${item.type}">
      <span class="add-preview-ghost-label">${escapeHtml(item.label)}</span>
      ${item.why ? `<span class="add-preview-ghost-why">${escapeHtml(item.why)}</span>` : ""}
    </div>`
    )
    .join("");
  return ghosts;
}

/**
 * “+” button with parent highlighting and a preview of the node types to add.
 * @param {{ readOnly?: boolean }} opts
 */
export function mountAddNodeButton({
  pos,
  parent,
  projectId,
  labels,
  allowedTypes,
  onOpen,
  mount,
  readOnly = false,
}) {
  const size = { w: 80, h: 80, round: "50%" };
  const items = addChildPreviewItems(parent.node_type, allowedTypes, labels);
  const singleLabel = items.length === 1 ? items[0].label : null;
  const hubHint = "Nodes cannot be added in Hub; it is read-only";

  const el = document.createElement("button");
  el.type = "button";
  el.className = "map-node add-node" + (readOnly ? " add-node--readonly" : "");
  el.dataset.parentId = parent.id;
  if (readOnly) {
    el.disabled = true;
    el.setAttribute("aria-disabled", "true");
    el.title = hubHint;
    el.setAttribute("aria-label", hubHint);
  } else {
    const ariaLabel =
      items.length === 1
        ? `Add ${items[0].label.toLowerCase()}`
        : `Add: ${items.map((i) => i.label.toLowerCase()).join(" or ")}`;
    el.setAttribute("aria-label", ariaLabel);
  }
  el.innerHTML = `
    <span class="node-label add-node-dynamic-label">${singleLabel ? `+ ${singleLabel}` : "Add"}</span>
    <span class="add-plus">+</span>`;

  const addWrap = document.createElement("div");
  addWrap.className =
    "node-wrap add-slot-wrap" + (readOnly ? " add-slot-wrap--readonly" : "");
  if (projectId) addWrap.dataset.projectId = projectId;
  addWrap.dataset.parentId = parent.id;
  addWrap.style.left = `${pos.x}px`;
  addWrap.style.top = `${pos.y}px`;
  addWrap.style.transform = "translate(-50%, -50%)";
  if (readOnly) addWrap.title = hubHint;

  addWrap.appendChild(buildAddPreviewGhosts(items));

  el.style.width = `${size.w}px`;
  el.style.height = `${size.h}px`;
  el.style.borderRadius = size.round;

  const showPreview = () => {
    if (readOnly) return;
    addWrap.classList.add("is-add-preview-active");
    setAddParentHighlight(parent, projectId, true);
  };
  const hidePreview = () => {
    addWrap.classList.remove("is-add-preview-active");
    setAddParentHighlight(parent, projectId, false);
  };

  addWrap.addEventListener("mouseenter", showPreview);
  addWrap.addEventListener("mouseleave", hidePreview);
  addWrap.addEventListener("focusin", showPreview);
  addWrap.addEventListener("focusout", (e) => {
    if (!addWrap.contains(e.relatedTarget)) hidePreview();
  });

  el.addEventListener("click", (e) => {
    e.stopPropagation();
    if (readOnly) return;
    hidePreview();
    onOpen(parent);
  });

  addWrap.appendChild(el);
  if (mount) {
    mount(addWrap);
  }
  return addWrap;
}
