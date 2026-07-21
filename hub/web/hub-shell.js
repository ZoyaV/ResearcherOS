(function () {
  var THEME_KEY = "koi-theme";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    var next = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
    syncThemeButton();
  }

  function syncThemeButton() {
    var btn = document.getElementById("btn-theme");
    if (!btn) return;
    var theme = currentTheme();
    btn.title = theme === "light" ? "Тёмная тема" : "Светлая тема";
    btn.setAttribute(
      "aria-label",
      theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"
    );
  }

  function initThemeButton() {
    var btn = document.getElementById("btn-theme");
    if (!btn) return;
    syncThemeButton();
    btn.addEventListener("click", function () {
      applyTheme(currentTheme() === "light" ? "dark" : "light");
    });
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function guestLoginHtml() {
    return '<a class="btn btn-primary hub-login-btn" href="/auth/github">Войти</a>';
  }

  function bindAccountMenu(root) {
    var trigger = root.querySelector("#hub-account-trigger");
    var menu = root.querySelector("#hub-account-menu");
    if (!trigger || !menu) return;

    function closeMenu() {
      menu.classList.add("hidden");
      trigger.setAttribute("aria-expanded", "false");
    }

    function openMenu() {
      menu.classList.remove("hidden");
      trigger.setAttribute("aria-expanded", "true");
    }

    trigger.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (menu.classList.contains("hidden")) openMenu();
      else closeMenu();
    });

    menu.addEventListener("click", function (ev) {
      ev.stopPropagation();
    });

    document.addEventListener("click", closeMenu);

    var logoutBtn = menu.querySelector('[data-action="logout"]');
    if (logoutBtn) {
      logoutBtn.addEventListener("click", function () {
        fetch("/auth/logout", { method: "POST", credentials: "same-origin" })
          .then(function () {
            location.href = "/";
          })
          .catch(function () {
            location.href = "/";
          });
      });
    }
  }

  function renderAuthToolbar() {
    var el = document.getElementById("auth-toolbar");
    if (!el) return Promise.resolve(null);
    return fetch("/api/me", { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (me) {
        if (!me.authenticated) {
          el.innerHTML = guestLoginHtml();
          return me;
        }
        var u = me.user || {};
        el.innerHTML =
          '<div class="hub-account">' +
          '<button type="button" class="user-chip hub-account__trigger" id="hub-account-trigger" aria-expanded="false" aria-haspopup="menu" aria-controls="hub-account-menu">' +
          '<img src="' +
          escapeHtml(u.avatar_url) +
          '" alt="" width="24" height="24" />' +
          "<span>@" +
          escapeHtml(u.login) +
          "</span>" +
          '<span class="hub-account__chevron" aria-hidden="true">▾</span>' +
          "</button>" +
          '<div class="hub-account__menu hidden" id="hub-account-menu" role="menu">' +
          '<a class="hub-account__item" href="/connect" role="menuitem">+ Подключить репозиторий</a>' +
          '<button type="button" class="hub-account__item hub-account__item--danger" data-action="logout" role="menuitem">Выйти</button>' +
          "</div>" +
          "</div>";
        bindAccountMenu(el);
        return me;
      })
      .catch(function (err) {
        el.innerHTML =
          '<span class="meta">Auth: ' + escapeHtml(err.message) + "</span>";
        return null;
      });
  }

  // Expose for hub.js so index/connect can reuse the same renderer.
  window.HubShell = {
    renderAuthToolbar: renderAuthToolbar,
    guestLoginHtml: guestLoginHtml,
  };

  function boot() {
    initThemeButton();
    renderAuthToolbar();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
