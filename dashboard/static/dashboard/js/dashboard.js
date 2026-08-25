(function () {
  // Auto-refresh: full reload; the theme survives via localStorage plus the
  // pre-paint script in <head>.
  var seconds = parseInt(document.body.getAttribute("data-refresh-seconds"), 10) || 30;
  window.setTimeout(function () {
    window.location.reload();
  }, seconds * 1000);

  // Light/dark toggle. The <head> script already applied the initial theme.
  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var root = document.documentElement;
      var dark = root.getAttribute("data-theme") === "dark";
      if (dark) {
        root.removeAttribute("data-theme");
      } else {
        root.setAttribute("data-theme", "dark");
      }
      try {
        localStorage.setItem("dashboard-theme", dark ? "light" : "dark");
      } catch (e) { /* storage unavailable; theme just won't persist */ }
    });
  }
})();
