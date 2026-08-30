(function () {
  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function card(skill) {
    return (
      '<a class="hub-skill-card" href="' +
      esc(skill.view_url) +
      '">' +
      '<h2 class="hub-skill-card__title">' +
      esc(skill.title) +
      "</h2>" +
      (skill.summary
        ? '<p class="hub-skill-card__summary">' + esc(skill.summary) + "</p>"
        : "") +
      '<p class="hub-skill-card__meta">' +
      '<span>' +
      esc(skill.owner_login || "—") +
      "</span>" +
      '<span>·</span>' +
      '<span>' +
      esc(skill.project_title || skill.project_slug) +
      "</span>" +
      "</p>" +
      "</a>"
    );
  }

  async function load() {
    var root = document.getElementById("skills-catalog");
    var status = document.getElementById("hub-status");
    try {
      var data = await fetch("/api/catalog/skills", { credentials: "same-origin" }).then(
        function (r) {
          if (!r.ok) throw new Error(r.statusText);
          return r.json();
        }
      );
      var skills = data.skills || [];
      if (!skills.length) {
        root.innerHTML =
          '<p class="hub-empty">Nothing here yet. When authors of public projects ' +
          "share skills, they will appear in this catalog.</p>";
        return;
      }
      root.innerHTML = skills.map(card).join("");
      if (status) status.textContent = skills.length + " skills";
    } catch (err) {
      if (status) status.textContent = "Could not load: " + (err.message || err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
