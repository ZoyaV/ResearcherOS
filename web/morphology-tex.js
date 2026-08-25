/** Small TeX subset → MathML. Browser never evaluates the source string. */

const GREEK = {
  alpha: "α",
  beta: "β",
  gamma: "γ",
  delta: "δ",
  epsilon: "ε",
  varepsilon: "ε",
  zeta: "ζ",
  eta: "η",
  theta: "θ",
  iota: "ι",
  kappa: "κ",
  lambda: "λ",
  mu: "μ",
  nu: "ν",
  xi: "ξ",
  pi: "π",
  rho: "ρ",
  sigma: "σ",
  tau: "τ",
  phi: "φ",
  varphi: "φ",
  chi: "χ",
  psi: "ψ",
  omega: "ω",
  Gamma: "Γ",
  Delta: "Δ",
  Theta: "Θ",
  Lambda: "Λ",
  Xi: "Ξ",
  Pi: "Π",
  Sigma: "Σ",
  Phi: "Φ",
  Psi: "Ψ",
  Omega: "Ω",
};

const SYMBOLS = {
  times: "×",
  cdot: "⋅",
  circ: "∘",
  in: "∈",
  notin: "∉",
  subset: "⊂",
  subseteq: "⊆",
  geq: "≥",
  ge: "≥",
  leq: "≤",
  le: "≤",
  neq: "≠",
  ne: "≠",
  approx: "≈",
  sim: "∼",
  to: "→",
  rightarrow: "→",
  leftarrow: "←",
  Rightarrow: "⇒",
  mapsto: "↦",
  ldots: "…",
  cdots: "⋯",
  infty: "∞",
  partial: "∂",
  nabla: "∇",
  sum: "∑",
  prod: "∏",
  int: "∫",
  ell: "ℓ",
  top: "⊤",
  bot: "⊥",
  forall: "∀",
  exists: "∃",
  mid: "∣",
  vert: "|",
  Vert: "‖",
  lVert: "‖",
  rVert: "‖",
  langle: "⟨",
  rangle: "⟩",
  lfloor: "⌊",
  rfloor: "⌋",
  pm: "±",
  mp: "∓",
  ast: "∗",
  star: "⋆",
  bullet: "•",
  CIRCLE: "●",
  LEFTcircle: "◐",
  mathds: "𝟙",
};

const ACCENTS = {
  hat: "^",
  bar: "¯",
  overline: "¯",
  tilde: "~",
  vec: "→",
  dot: "˙",
  ddot: "¨",
};

const VARIANTS = {
  mathcal: "script",
  mathscr: "script",
  mathbb: "double-struck",
  mathbf: "bold",
  mathrm: "normal",
  mathit: "italic",
  mathds: "double-struck",
};

const SKIP = new Set(["displaystyle", "textstyle", "scriptstyle", "limits", "nolimits"]);

function escapeXml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tokenize(source) {
  const tokens = [];
  let index = 0;
  const text = String(source || "");
  while (index < text.length) {
    const char = text[index];
    if (/\s/.test(char)) {
      index += 1;
      continue;
    }
    if (char === "\\") {
      const next = text[index + 1] || "";
      if (/[A-Za-z]/.test(next)) {
        let end = index + 1;
        while (end < text.length && /[A-Za-z]/.test(text[end])) end += 1;
        tokens.push({ type: "cmd", value: text.slice(index + 1, end) });
        index = end;
        continue;
      }
      tokens.push({ type: "cmd", value: next });
      index += 2;
      continue;
    }
    if ("{}^_".includes(char)) {
      tokens.push({ type: char });
      index += 1;
      continue;
    }
    tokens.push({ type: "char", value: char });
    index += 1;
  }
  return tokens;
}

function tag(name, inner, attrs = "") {
  return `<${name}${attrs}>${inner}</${name}>`;
}

function operator(value) {
  return tag("mo", escapeXml(value));
}

function identifier(value, variant = "") {
  const attr = variant ? ` mathvariant="${variant}"` : "";
  return tag("mi", escapeXml(value), attr);
}

function number(value) {
  return tag("mn", escapeXml(value));
}

function wrapRow(parts) {
  if (!parts.length) return tag("mrow", "");
  if (parts.length === 1) return parts[0];
  return tag("mrow", parts.join(""));
}

function parse(tokens) {
  let cursor = 0;
  const peek = () => tokens[cursor] || null;
  const take = () => tokens[cursor++] || null;

  function parseGroup() {
    if (peek()?.type !== "{") return parseAtom();
    take();
    const inner = parseExpr("}");
    if (peek()?.type === "}") take();
    return inner;
  }

  function parseAtom() {
    const token = peek();
    if (!token) return tag("mrow", "");
    if (token.type === "{") return parseGroup();
    if (token.type === "cmd") {
      take();
      return parseCommand(token.value);
    }
    if (token.type === "char") {
      take();
      if (/[0-9]/.test(token.value)) {
        let digits = token.value;
        while (peek()?.type === "char" && /[0-9.]/.test(peek().value)) {
          digits += take().value;
        }
        return number(digits);
      }
      if (/[A-Za-z]/.test(token.value)) return identifier(token.value);
      if (token.value === "'") return tag("mo", "′");
      return operator(token.value);
    }
    return tag("mrow", "");
  }

  function parseCommand(name) {
    if (SKIP.has(name)) return parseAtom();
    if (name === "frac") return tag("mfrac", parseGroup() + parseGroup());
    if (name === "sqrt") return tag("msqrt", parseGroup());
    if (name === "text" || name === "textrm" || name === "mbox") {
      return tag("mtext", escapeXml(collectText(parseGroup())));
    }
    if (name in ACCENTS) {
      return tag("mover", parseGroup() + operator(ACCENTS[name]), ' accent="true"');
    }
    if (name in VARIANTS) {
      return applyVariant(parseGroup(), VARIANTS[name]);
    }
    if (name === "left" || name === "right") {
      const fence = take();
      const value =
        fence?.type === "cmd"
          ? SYMBOLS[fence.value] || fence.value
          : fence?.value || "";
      return operator(value === "." ? "" : value);
    }
    if (name === "quad") return '<mspace width="1em"></mspace>';
    if (name === "qquad") return '<mspace width="2em"></mspace>';
    if (name === "," || name === ":" || name === ";") return '<mspace width="0.2em"></mspace>';
    if (name === "!") return '<mspace width="-0.15em"></mspace>';
    if (name === "mathbb" || name === "mathds") {
      const inner = collectText(parseGroup());
      if (inner === "1") return identifier("𝟙");
      return applyVariant(identifier(inner), "double-struck");
    }
    if (GREEK[name]) return identifier(GREEK[name]);
    if (SYMBOLS[name]) return /[A-Za-zΑ-ω]/.test(SYMBOLS[name]) ? identifier(SYMBOLS[name]) : operator(SYMBOLS[name]);
    if (name.length === 1) return operator(name);
    return identifier(name);
  }

  function parseScripted() {
    let atom = parseAtom();
    let sub = "";
    let sup = "";
    while (peek()?.type === "^" || peek()?.type === "_") {
      const kind = take().type;
      const script = parseAtom();
      if (kind === "^") sup = script;
      else sub = script;
    }
    if (sub && sup) return tag("msubsup", atom + sub + sup);
    if (sub) return tag("msub", atom + sub);
    if (sup) return tag("msup", atom + sup);
    return atom;
  }

  function parseExpr(stop) {
    const parts = [];
    while (peek() && peek().type !== stop) {
      if (peek().type === "}") break;
      parts.push(parseScripted());
    }
    return wrapRow(parts);
  }

  function collectText(mathml) {
    return String(mathml || "")
      .replace(/<[^>]+>/g, "")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&");
  }

  function applyVariant(mathml, variant) {
    const text = collectText(mathml);
    if (text && text.length <= 8 && !/[+\-=]/.test(text)) return identifier(text, variant);
    return mathml.replace("<mi", `<mi mathvariant="${variant}"`);
  }

  return parseExpr();
}

export function latexToMathML(source, display = "inline") {
  const body = parse(tokenize(source));
  return `<math xmlns="http://www.w3.org/1998/Math/MathML" display="${display}">${body}</math>`;
}
