/* C&J theme bootstrap — no-flash. Runs before first paint.
   Reads localStorage 'cj-theme' (light|dark|field); default follows
   prefers-color-scheme (dark -> dark, else light). */
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
})();
