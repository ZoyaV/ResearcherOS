(function () {
  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pathParts() {
    // /skills/{project_slug}/{skill_id}
    var parts = location.pathname.replace(/\/+$/, "").split("/");
    var i = parts.indexOf("skills");
    if (i < 0 || parts.length < i + 3) return null;
    return { projectSlug: decodeURIComponent(parts[i + 1]), skillId: decodeURIComponent(parts[i + 2]) };
  }

  async function load() {
    var article = document.getElementById("skill-article");
    var parts = pathParts();
    if (!parts) {
      article.innerHTML = '<p class="hub-status">Некорректный URL</p>';
      return;
    }
    try {
      var url =
        "/api/skills/" +
        encodeURIComponent(parts.projectSlug) +
        "/" +
        encodeURIComponent(parts.skillId);
      var skill = await fetch(url, { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error(r.status === 404 ? "Skill не найден" : r.statusText);
        return r.json();
      });
      document.title = (skill.title || skill.id) + " — ResearchOS Hub";
      var html = "";
      if (typeof marked !== "undefined" && marked.parse) {
        html = marked.parse(skill.readme_md || "");
      } else {
        html = "<pre>" + esc(skill.readme_md) + "</pre>";
      }
      article.innerHTML =
        '<header class="hub-skill-header">' +
        '<p class="hub-skill-header__id"><code>' +
        esc(skill.id) +
        "</code></p>" +
        '<h1 class="hub-skill-header__title">' +
        esc(skill.title) +
        "</h1>" +
        (skill.summary
          ? '<p class="hub-skill-header__summary">' + esc(skill.summary) + "</p>"
          : "") +
        '<p class="hub-skill-header__meta">' +
        'из проекта <a href="' +
        esc(skill.project_url) +
        '">' +
        esc(skill.project_title || skill.project_slug) +
        "</a>" +
        (skill.owner_login ? " · @" + esc(skill.owner_login) : "") +
        (skill.repo_full_name
          ? ' · <a href="https://github.com/' +
            esc(skill.repo_full_name) +
            '" rel="noopener">' +
            esc(skill.repo_full_name) +
            "</a>"
          : "") +
        "</p>" +
        "</header>" +
        '<div class="hub-skill-body prose">' +
        html +
        "</div>";
    } catch (err) {
      article.innerHTML =
        '<p class="hub-status">' + esc(err.message || String(err)) + "</p>";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
