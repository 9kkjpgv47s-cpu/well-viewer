/* C&J theme toggle — vanilla JS for static surfaces (Well Viewer).
   Any [data-cj-theme-toggle] button cycles light -> dark -> field, persists to
   localStorage 'cj-theme', and keeps its aria-label honest. The glyph morph
   itself is pure CSS (.tt-* rules in components.css). */
(function () {
  var KEY = "cj-theme";
  var ORDER = ["light", "dark", "field"];
  var NEXT = { light: "dark", dark: "field", field: "light" };

  function current() {
    var t = document.documentElement.dataset.theme;
    return ORDER.indexOf(t) >= 0 ? t : "light";
  }

  function label(t) {
    return "Theme: " + t + " — switch to " + NEXT[t];
  }

  function paint(btn) {
    btn.setAttribute("aria-label", label(current()));
    btn.setAttribute("title", label(current()));
  }

  function apply(t) {
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem(KEY, t);
    } catch {}
    document
      .querySelectorAll("[data-cj-theme-toggle]")
      .forEach(paint);
  }

  function bind(btn) {
    paint(btn);
    btn.addEventListener("click", function () {
      apply(NEXT[current()]);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      document.querySelectorAll("[data-cj-theme-toggle]").forEach(bind);
    });
  } else {
    document.querySelectorAll("[data-cj-theme-toggle]").forEach(bind);
  }

  window.cjTheme = { apply: apply, current: current };
})();
