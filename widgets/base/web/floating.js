/**
 * Shared helpers for floating ResearchOS widgets (drag + position persistence).
 */

export function bindFloatingDrag(root, { storageKey, handle, onTap } = {}) {
  const dragHandle = handle || root;
  let dragging = false;
  let moved = false;
  let offsetX = 0;
  let offsetY = 0;

  const save = () => {
    if (!storageKey) return;
    try {
      const rect = root.getBoundingClientRect();
      localStorage.setItem(
        storageKey,
        JSON.stringify({ x: Math.round(rect.left), y: Math.round(rect.top) })
      );
    } catch {
      /* ignore */
    }
  };

  const load = () => {
    if (!storageKey) return false;
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return false;
      const data = JSON.parse(raw);
      if (!Number.isFinite(data?.x) || !Number.isFinite(data?.y)) return false;
      root.style.left = `${data.x}px`;
      root.style.top = `${data.y}px`;
      root.style.right = "auto";
      return true;
    } catch {
      return false;
    }
  };

  const defaultTopRight = (margin = 18) => {
    const size = root.offsetWidth || 76;
    root.style.top = `${margin}px`;
    root.style.left = `${window.innerWidth - size - margin}px`;
    root.style.right = "auto";
  };

  if (!load()) defaultTopRight();

  dragHandle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    dragging = true;
    moved = false;
    const rect = root.getBoundingClientRect();
    offsetX = event.clientX - rect.left;
    offsetY = event.clientY - rect.top;
    dragHandle.setPointerCapture?.(event.pointerId);
    root.classList.add("koi-widget--dragging");
    event.preventDefault();
  });

  dragHandle.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const x = event.clientX - offsetX;
    const y = event.clientY - offsetY;
    if (Math.abs(x - root.offsetLeft) > 2 || Math.abs(y - root.offsetTop) > 2) {
      moved = true;
    }
    const maxX = Math.max(0, window.innerWidth - root.offsetWidth);
    const maxY = Math.max(0, window.innerHeight - root.offsetHeight);
    root.style.left = `${Math.min(maxX, Math.max(0, x))}px`;
    root.style.top = `${Math.min(maxY, Math.max(0, y))}px`;
    root.style.right = "auto";
  });

  const endDrag = (event) => {
    if (!dragging) return;
    dragging = false;
    root.classList.remove("koi-widget--dragging");
    dragHandle.releasePointerCapture?.(event.pointerId);
    save();
    if (!moved && typeof onTap === "function") {
      onTap(event);
    }
  };

  dragHandle.addEventListener("pointerup", endDrag);
  dragHandle.addEventListener("pointercancel", endDrag);

  window.addEventListener("resize", () => {
    const rect = root.getBoundingClientRect();
    const maxX = Math.max(0, window.innerWidth - root.offsetWidth);
    const maxY = Math.max(0, window.innerHeight - root.offsetHeight);
    if (rect.left > maxX || rect.top > maxY) {
      root.style.left = `${Math.min(rect.left, maxX)}px`;
      root.style.top = `${Math.min(rect.top, maxY)}px`;
      save();
    }
  });

  return {
    endDrag,
    wasMoved: () => moved,
    save,
  };
}

export function injectStylesheet(href) {
  const existing = document.querySelector(`link[data-koi-widget-css="${href}"]`);
  if (existing) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.dataset.koiWidgetCss = href;
  document.head.appendChild(link);
}
