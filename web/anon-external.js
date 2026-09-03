/** Block off-site navigation in anonymous builds; show a short modal instead. */
(function () {
  function isBlockedExternal(href) {
    if (!href) return false;
    var raw = String(href).trim();
    if (!raw || raw === "#" || raw.indexOf("javascript:") === 0 || raw.indexOf("mailto:") === 0) {
      return false;
    }
    try {
      var u = new URL(raw, location.href);
      if (u.protocol !== "http:" && u.protocol !== "https:") return false;
      if (u.hostname === "127.0.0.1" || u.hostname === "localhost") return false;
      if (u.origin === location.origin) return false;
      return true;
    } catch (e) {
      return false;
    }
  }

  function ensureModal() {
    var el = document.getElementById("anon-external-modal");
    if (el) return el;
    el = document.createElement("div");
    el.id = "anon-external-modal";
    el.className = "anon-modal";
    el.setAttribute("hidden", "");
    el.innerHTML =
      '<div class="anon-modal__backdrop" data-anon-close></div>' +
      '<div class="anon-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="anon-external-title">' +
      '<h2 id="anon-external-title" class="anon-modal__title">External link unavailable</h2>' +
      '<p class="anon-modal__body">This is anonymous code. You cannot connect to an external resource.</p>' +
      '<button type="button" class="anon-modal__ok" data-anon-close>OK</button>' +
      "</div>";
    document.body.appendChild(el);
    if (!document.getElementById("anon-external-style")) {
      var style = document.createElement("style");
      style.id = "anon-external-style";
      style.textContent =
        "html.anon-modal-open{overflow:hidden}" +
        ".anon-modal[hidden]{display:none!important}" +
        ".anon-modal{position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;padding:1.25rem}" +
        ".anon-modal__backdrop{position:absolute;inset:0;background:rgba(10,10,18,.55)}" +
        ".anon-modal__dialog{position:relative;z-index:1;width:min(100%,26rem);padding:1.5rem 1.4rem 1.25rem;border-radius:.9rem;border:1px solid rgba(255,255,255,.12);background:#12121a;color:#f4f4ff;box-shadow:0 18px 48px rgba(0,0,0,.35)}" +
        ".anon-modal__title{margin:0 0 .65rem;font-size:1.15rem;font-weight:700}" +
        ".anon-modal__body{margin:0 0 1.25rem;color:#a8a8bc;line-height:1.5}" +
        ".anon-modal__ok{min-width:5.5rem;padding:.55rem 1rem;border:none;border-radius:.55rem;background:#6b42d4;color:#fff;font:inherit;font-weight:600;cursor:pointer}";
      document.head.appendChild(style);
    }
    return el;
  }

  function openModal() {
    var el = ensureModal();
    el.removeAttribute("hidden");
    document.documentElement.classList.add("anon-modal-open");
    var ok = el.querySelector(".anon-modal__ok");
    if (ok) ok.focus();
  }

  function closeModal() {
    var el = document.getElementById("anon-external-modal");
    if (!el) return;
    el.setAttribute("hidden", "");
    document.documentElement.classList.remove("anon-modal-open");
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-anon-close]")) {
      closeModal();
      return;
    }
    var a = e.target.closest("a");
    if (!a) return;
    var blocked =
      a.hasAttribute("data-anon-external") || isBlockedExternal(a.getAttribute("href"));
    if (!blocked) return;
    e.preventDefault();
    openModal();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeModal();
  });
})();
