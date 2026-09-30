// Progressive polish only. Every page works without this file: content is
// visible by default, and only this script opts sections into the reveal.
(function () {
  var root = document.documentElement;
  var dark = matchMedia("(prefers-color-scheme: dark)");

  // Theme toggle. A stored choice is applied before paint by the inline head script.
  var toggle = document.querySelector(".theme-toggle");
  function currentTheme() {
    return root.getAttribute("data-theme") || (dark.matches ? "dark" : "light");
  }
  function syncToggle() {
    if (toggle) toggle.setAttribute("aria-pressed", String(currentTheme() === "dark"));
  }
  if (toggle) {
    syncToggle();
    if (dark.addEventListener) dark.addEventListener("change", syncToggle);
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      syncToggle();
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  // Reveal sections once as they enter the viewport. Anything already on
  // screen, or anything the observer cannot watch, stays visible.
  if (!("IntersectionObserver" in window)) return;
  var items = document.querySelectorAll(".reveal");
  // The huge top margin counts anything already scrolled past as seen, so an
  // anchor jump or the End key never leaves a hidden section behind.
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        io.unobserve(entry.target);
      }
    });
  }, { rootMargin: "100000px 0px -8% 0px", threshold: 0 });
  items.forEach(function (el) {
    if (el.getBoundingClientRect().top < innerHeight) el.classList.add("in");
    else io.observe(el);
  });
  root.classList.add("js");
})();
