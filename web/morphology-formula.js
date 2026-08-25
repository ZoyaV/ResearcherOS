import { latexToMathML } from "./morphology-tex.js?v=20260821h";

const COPY = {
  ru: {
    language: "Язык урока",
    symbols: "Обозначения",
    domain: "Область определения",
    meaning: "Смысл выражения",
    parts: "Как читать выражение",
    example: "Пример",
    result: "Результат",
    plot: "Как переменные влияют на результат",
    fixed: "Не меняются:",
    nodes: "Связанные утверждения",
    occurrences: (count) => `Сколько раз встречается в статье: ${count}`,
    previous: "Предыдущая формула",
    next: "Следующая формула",
    open: "Открыть урок об этой формуле",
    empty: "В статье нет математических выражений.",
  },
  en: {
    language: "Lesson language",
    symbols: "Symbols",
    domain: "Domain",
    meaning: "What the expression means",
    parts: "How to read the expression",
    example: "Example",
    result: "Result",
    plot: "How variables affect the result",
    fixed: "Kept unchanged:",
    nodes: "Related claims",
    occurrences: (count) => `Times found in the article: ${count}`,
    previous: "Previous formula",
    next: "Next formula",
    open: "Open lesson about this formula",
    empty: "The article has no mathematical expressions.",
  },
};

const LANGUAGE_KEY = "koi-morph-formula-language";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function localized(value, language) {
  if (!value || typeof value !== "object") return "";
  return String(value[language] || value.en || value.ru || "");
}

function sourceMath(anchor) {
  if (!anchor) return null;
  for (const root of document.querySelectorAll(".morph-article-body")) {
    const math = root.querySelector(`#${CSS.escape(anchor)}`);
    if (math) return math;
  }
  return null;
}

function sourceMathForLatex(latex) {
  const wanted = normalizedLatex(latex);
  if (!wanted) return null;
  for (const root of document.querySelectorAll(".morph-article-body")) {
    for (const math of root.querySelectorAll("math[alttext]")) {
      if (normalizedLatex(math.getAttribute("alttext")) === wanted) return math;
    }
  }
  return null;
}

function clonedMath(original, className) {
  const clone = original.cloneNode(true);
  clone.removeAttribute("id");
  clone.querySelectorAll("[id]").forEach((element) => element.removeAttribute("id"));
  const presentation = clone.querySelector("semantics > :not(annotation):not(annotation-xml)") || clone;
  presentation.querySelectorAll("annotation, annotation-xml").forEach((node) => node.remove());
  if (presentation !== clone) {
    clone.replaceChildren(presentation.cloneNode(true));
  }
  const host = document.createElement("div");
  host.className = className;
  host.append(clone);
  return host.outerHTML;
}

function renderedMath(mathml, className) {
  if (!mathml) return "";
  const parsed = new DOMParser().parseFromString(String(mathml), "application/xml");
  const root = parsed.documentElement;
  if (!root || root.localName !== "math" || parsed.querySelector("parsererror")) return "";
  return clonedMath(document.importNode(root, true), className);
}

function renderFromLatex(latex, className, display = "inline") {
  const plainText = String(latex || "").match(/^\\text\{([^{}]*)\}$/);
  if (plainText) {
    return `<span class="morph-formula-snippet-text">${escapeHtml(plainText[1])}</span>`;
  }
  return renderedMath(latexToMathML(latex, display), className);
}

function normalizedLatex(value) {
  return String(value || "")
    .replaceAll("\\displaystyle", "")
    .replace(/\\(?:,|;|!|quad|qquad)/g, "")
    .replace(/\s+/g, "")
    .replace(/[,.]+$/, "");
}

function renderMath(expression, className = "morph-formula-math") {
  const occurrence = expression?.occurrences?.[0];
  const original = sourceMath(occurrence?.source_anchor);
  if (original) return clonedMath(original, className);
  const fromStored = renderedMath(expression?._mathml, className);
  if (fromStored) return fromStored;
  return renderFromLatex(expression?.latex, className, occurrence?.display || "block");
}

function renderSymbol(symbol) {
  const latex = symbol?.latex;
  const original = sourceMathForLatex(latex);
  if (original) return clonedMath(original, "morph-formula-symbol-math");
  const fromStored = renderedMath(symbol?._mathml, "morph-formula-symbol-math");
  if (fromStored) return fromStored;
  return renderFromLatex(latex, "morph-formula-symbol-math");
}

function renderSnippet(latex, mathml, expression) {
  if (normalizedLatex(latex) === normalizedLatex(expression?.latex)) {
    return renderMath(expression, "morph-formula-snippet-math");
  }
  const original = sourceMathForLatex(latex);
  if (original) return clonedMath(original, "morph-formula-snippet-math");
  const fromStored = renderedMath(mathml, "morph-formula-snippet-math");
  if (fromStored) return fromStored;
  return renderFromLatex(latex, "morph-formula-snippet-math");
}

function renderPlot(plot, language, index) {
  const xValues = Array.isArray(plot?.x?.values)
    ? plot.x.values.map(Number).filter(Number.isFinite)
    : [];
  const series = (Array.isArray(plot?.series) ? plot.series : []).filter(
    (row) =>
      Array.isArray(row?.values) &&
      row.values.length === xValues.length &&
      row.values.every((value) => Number.isFinite(Number(value)))
  );
  if (xValues.length < 2 || !series.length) return "";

  const yValues = series.flatMap((row) => row.values.map(Number));
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  const left = 44;
  const right = 616;
  const top = 20;
  const bottom = 220;
  const px = (value) => left + ((Number(value) - minX) / xSpan) * (right - left);
  const py = (value) => bottom - ((Number(value) - minY) / ySpan) * (bottom - top);

  const lines = series
    .map((row, seriesIndex) => {
      const points = xValues
        .map((x, pointIndex) => `${px(x).toFixed(2)},${py(row.values[pointIndex]).toFixed(2)}`)
        .join(" ");
      return `<polyline class="morph-formula-series series-${seriesIndex % 6}" points="${points}" />`;
    })
    .join("");
  const legend = series
    .map(
      (row, seriesIndex) =>
        `<span class="morph-formula-legend-item series-${seriesIndex % 6}">${escapeHtml(
          localized(row.label, language)
        )}</span>`
    )
    .join("");

  return `
    <section class="morph-formula-plot">
      <h4>${escapeHtml(localized(plot.title, language))}</h4>
      <svg viewBox="0 0 640 260" role="img" aria-label="${escapeHtml(
        localized(plot.title, language)
      )}">
        <line class="morph-formula-axis" x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}" />
        <line class="morph-formula-axis" x1="${left}" y1="${top}" x2="${left}" y2="${bottom}" />
        ${lines}
        <text class="morph-formula-axis-label" x="330" y="252">${escapeHtml(
          localized(plot.x.label, language)
        )}</text>
        <text class="morph-formula-axis-label" x="10" y="14">${escapeHtml(
          localized(plot.y_label, language)
        )}</text>
        <text class="morph-formula-tick" x="${left}" y="${bottom + 16}">${escapeHtml(minX)}</text>
        <text class="morph-formula-tick" x="${right}" y="${bottom + 16}" text-anchor="end">${escapeHtml(
          maxX
        )}</text>
        <text class="morph-formula-tick" x="${left - 6}" y="${bottom}" text-anchor="end">${escapeHtml(
          minY
        )}</text>
        <text class="morph-formula-tick" x="${left - 6}" y="${top + 4}" text-anchor="end">${escapeHtml(
          maxY
        )}</text>
      </svg>
      <div class="morph-formula-legend">${legend}</div>
      <p>${escapeHtml(localized(plot.explanation, language))}</p>
      <p class="morph-formula-fixed"><strong>${COPY[language].fixed}</strong> ${escapeHtml(
        localized(plot.fixed_parameters, language)
      )}</p>
    </section>`;
}

export function initFormulaLessons({ onSelectNode } = {}) {
  const nodeTab = document.getElementById("morph-inspector-node-tab");
  const formulaTab = document.getElementById("morph-inspector-formula-tab");
  const nodePanel = document.getElementById("morph-inspector-node");
  const formulaPanel = document.getElementById("morph-formula-panel");
  let analysis = null;
  let expressions = [];
  let selectedId = "";
  let language = "ru";
  try {
    const saved = localStorage.getItem(LANGUAGE_KEY);
    if (saved === "en" || saved === "ru") language = saved;
  } catch {
    /* private mode */
  }

  function setMode(mode) {
    const formulaMode = mode === "formula" && expressions.length > 0;
    nodePanel?.classList.toggle("hidden", formulaMode);
    formulaPanel?.classList.toggle("hidden", !formulaMode);
    nodeTab?.classList.toggle("is-active", !formulaMode);
    formulaTab?.classList.toggle("is-active", formulaMode);
    nodeTab?.setAttribute("aria-selected", formulaMode ? "false" : "true");
    formulaTab?.setAttribute("aria-selected", formulaMode ? "true" : "false");
  }

  function selectedExpression() {
    return expressions.find((expression) => expression.id === selectedId) || expressions[0] || null;
  }

  function syncSourceSelection() {
    document.querySelectorAll(".morph-formula-note").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.expressionId === selectedId);
    });
  }

  function render() {
    if (!formulaPanel) return;
    const expression = selectedExpression();
    if (!expression) {
      formulaPanel.innerHTML = `<p class="morph-formula-empty">${escapeHtml(COPY[language].empty)}</p>`;
      return;
    }
    selectedId = expression.id;
    const copy = COPY[language];
    const index = expressions.indexOf(expression);
    const symbols = (expression.symbols || [])
      .map(
        (symbol) => `
          <article class="morph-formula-symbol">
            ${renderSymbol(symbol)}
            <p>${escapeHtml(localized(symbol.meaning, language))}</p>
            <p class="morph-formula-domain"><strong>${copy.domain}:</strong> ${escapeHtml(
              localized(symbol.domain, language)
            )}</p>
          </article>`
      )
      .join("");
    const expressionParts = expression.parts || [];
    const parts = expressionParts
      .filter(
        (part) =>
          expressionParts.length === 1 ||
          normalizedLatex(part.latex) !== normalizedLatex(expression.latex)
      )
      .map(
        (part) => `
          <li>
            ${renderSnippet(part.latex, part._mathml, expression)}
            <p>${escapeHtml(localized(part.explanation, language))}</p>
          </li>`
      )
      .join("");
    const example = expression.worked_example || {};
    const steps = (example.steps || [])
      .map(
        (step, stepIndex) => `
          <li>
            <span>${stepIndex + 1}</span>
            <div>
              ${renderSnippet(step.latex, step._mathml, expression)}
              <p>${escapeHtml(localized(step.explanation, language))}</p>
            </div>
          </li>`
      )
      .join("");
    const plots = (expression.plots || [])
      .map((plot, plotIndex) => renderPlot(plot, language, plotIndex))
      .join("");
    const nodes = (expression.node_ids || [])
      .map(
        (nodeId) =>
          `<button type="button" class="morph-formula-node" data-node-id="${escapeHtml(
            nodeId
          )}">${escapeHtml(nodeId)}</button>`
      )
      .join("");

    formulaPanel.innerHTML = `
      <header class="morph-formula-head">
        <div class="morph-formula-position">
          <strong>${expression.note_number}</strong>
          <span>${escapeHtml(copy.occurrences(expression.occurrences?.length || 0))}</span>
        </div>
        <label class="morph-formula-language">
          <span>${escapeHtml(copy.language)}</span>
          <select id="morph-formula-language">
            <option value="ru"${language === "ru" ? " selected" : ""}>Русский</option>
            <option value="en"${language === "en" ? " selected" : ""}>English</option>
          </select>
        </label>
      </header>
      ${renderMath(expression)}
      <section class="morph-formula-section">
        <h4>${escapeHtml(copy.meaning)}</h4>
        <p>${escapeHtml(localized(expression.meaning, language))}</p>
      </section>
      ${
        symbols
          ? `<section class="morph-formula-section"><h4>${escapeHtml(
              copy.symbols
            )}</h4><div class="morph-formula-symbols">${symbols}</div></section>`
          : ""
      }
      ${
        parts
          ? `<section class="morph-formula-section"><h4>${escapeHtml(
              copy.parts
            )}</h4><ul class="morph-formula-parts">${parts}</ul></section>`
          : ""
      }
      <section class="morph-formula-section">
        <h4>${escapeHtml(copy.example)}</h4>
        <h5>${escapeHtml(localized(example.title, language))}</h5>
        <p>${escapeHtml(localized(example.setup, language))}</p>
        <ol class="morph-formula-steps">${steps}</ol>
        <p class="morph-formula-result"><strong>${escapeHtml(copy.result)}:</strong> ${escapeHtml(
          localized(example.result, language)
        )}</p>
      </section>
      ${
        plots
          ? `<section class="morph-formula-section"><h4>${escapeHtml(copy.plot)}</h4>${plots}</section>`
          : ""
      }
      ${
        nodes
          ? `<section class="morph-formula-section"><h4>${escapeHtml(
              copy.nodes
            )}</h4><div class="morph-formula-nodes">${nodes}</div></section>`
          : ""
      }
      <nav class="morph-formula-nav">
        <button type="button" class="btn btn-small" id="morph-formula-prev" ${
          index <= 0 ? "disabled" : ""
        }>← ${escapeHtml(copy.previous)}</button>
        <button type="button" class="btn btn-small" id="morph-formula-next" ${
          index >= expressions.length - 1 ? "disabled" : ""
        }>${escapeHtml(copy.next)} →</button>
      </nav>`;

    formulaPanel.querySelector("#morph-formula-language")?.addEventListener("change", (event) => {
      language = event.target.value === "en" ? "en" : "ru";
      try {
        localStorage.setItem(LANGUAGE_KEY, language);
      } catch {
        /* private mode */
      }
      render();
    });
    formulaPanel.querySelector("#morph-formula-prev")?.addEventListener("click", () => {
      select(expressions[index - 1]?.id);
    });
    formulaPanel.querySelector("#morph-formula-next")?.addEventListener("click", () => {
      select(expressions[index + 1]?.id);
    });
    formulaPanel.querySelectorAll(".morph-formula-node").forEach((button) => {
      button.addEventListener("click", () => onSelectNode?.(button.dataset.nodeId));
    });
    syncSourceSelection();
  }

  function select(expressionId) {
    if (!expressions.some((expression) => expression.id === expressionId)) return;
    selectedId = expressionId;
    setMode("formula");
    render();
  }

  function decorate(root) {
    if (!root) return;
    root.querySelectorAll(".morph-formula-note").forEach((button) => button.remove());
    for (const expression of expressions) {
      for (const occurrence of expression.occurrences || []) {
        const anchor = String(occurrence.source_anchor || "");
        if (!anchor) continue;
        const math = root.querySelector(`#${CSS.escape(anchor)}`);
        if (!math) continue;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "morph-formula-note";
        button.dataset.expressionId = expression.id;
        button.textContent = String(expression.note_number);
        button.title = COPY[language].open;
        button.setAttribute("aria-label", `${COPY[language].open} ${expression.note_number}`);
        button.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          select(expression.id);
        });
        math.insertAdjacentElement("afterend", button);
      }
    }
    syncSourceSelection();
  }

  function setAnalysis(nextAnalysis) {
    analysis = nextAnalysis && typeof nextAnalysis === "object" ? nextAnalysis : null;
    expressions = Array.isArray(analysis?.expressions) ? analysis.expressions : [];
    formulaTab?.classList.toggle("hidden", expressions.length === 0);
    if (!expressions.some((expression) => expression.id === selectedId)) {
      selectedId = expressions[0]?.id || "";
      setMode("node");
    }
    render();
  }

  nodeTab?.addEventListener("click", () => setMode("node"));
  formulaTab?.addEventListener("click", () => {
    if (!selectedId) selectedId = expressions[0]?.id || "";
    setMode("formula");
    render();
  });

  return {
    decorate,
    select,
    setAnalysis,
    showNode: () => setMode("node"),
  };
}
