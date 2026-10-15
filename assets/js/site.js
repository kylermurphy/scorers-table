/* scorers-table: the theme button, and nothing else. Every page works without this file.
   The head has already applied a saved choice (localStorage "st-theme") before the first paint.
   The button is in the page with the `hidden` attribute; this shows it, keeps its icon and label for the page's
   current theme, and on a press sets data-theme on <html> and saves the choice. */
(function () {
  var root = document.documentElement;
  var button = document.querySelector(".st-theme-toggle");
  if (!button) return;
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var SVG = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
  var MOON = SVG + '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>';
  var SUN = SVG + '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2' +
    'M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';

  function current() {
    var chosen = root.getAttribute("data-theme");
    if (chosen === "light" || chosen === "dark") return chosen;
    return media && media.matches ? "dark" : "light";
  }

  // The button names what a press does: on a dark page it offers the light theme, with the sun.
  function show() {
    var dark = current() === "dark";
    button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    button.innerHTML = dark ? SUN : MOON;
  }

  button.addEventListener("click", function () {
    var next = current() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("st-theme", next); } catch (e) {}
    show();
  });
  if (media && media.addEventListener) media.addEventListener("change", show);

  button.hidden = false;
  show();
})();
