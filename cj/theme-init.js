/* C&J theme bootstrap — no-flash. Runs before first paint.
   Reads localStorage 'cj-theme' (light|dark|field); default follows
   prefers-color-scheme (dark -> dark, else light).
   Paper palettes (light-theme variants, mockup): ?paper=limestone|sandstone|
   kraft|sage persists to localStorage 'cj-paper'; ?paper=none clears. */
(function () {
  try {
    var t = localStorage.getItem("cj-theme");
    if (t !== "light" && t !== "dark" && t !== "field") {
      t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.dataset.theme = t;
  } catch {
    document.documentElement.dataset.theme = "light";
  }
  try {
    var q = new URLSearchParams(location.search).get("paper");
    if (q === "none") localStorage.removeItem("cj-paper");
    else if (q) localStorage.setItem("cj-paper", q);
    var p = localStorage.getItem("cj-paper");
    if (p === "limestone" || p === "sandstone" || p === "kraft" || p === "sage") {
      document.documentElement.dataset.paper = p;
    }
  } catch {}
})();
