// Applies the saved theme before first paint (an external file: the CSP forbids inline scripts).
// Must match src/stores/theme.ts.
(function () {
  try {
    var pref = localStorage.getItem("hike.theme");
    var dark =
      pref === "dark" ||
      ((pref === null || pref === "system") &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (dark) document.documentElement.classList.add("dark");
  } catch (e) {
    /* storage unavailable: keep the light theme */
  }
})();
