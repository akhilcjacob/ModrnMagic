// Progressive polish only. Every page works without this file: content is
// visible by default, and only this script opts sections into the reveal.
(function () {
  var root = document.documentElement;
  var dark = matchMedia("(prefers-color-scheme: dark)");
  var still = matchMedia("(prefers-reduced-motion: reduce)");

  // Theme toggle. A stored choice is applied before paint by the inline head
  // script. The switch cross-fades the whole page instead of repainting it in
  // one frame, where the View Transitions API exists and motion is allowed.
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
      function apply() {
        root.setAttribute("data-theme", next);
        syncToggle();
      }
      toggle.classList.add("swapped");
      if (document.startViewTransition && !still.matches) {
        root.classList.add("theme-vt");
        document.startViewTransition(apply).finished.then(done, done);
      } else {
        apply();
      }
      function done() { root.classList.remove("theme-vt"); }
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  // FAQ: the answer fades in on open (CSS). Closing plays the reverse before
  // the <details> closes, so both directions read the same way. A click during
  // that close cancels it, so the item stays open instead of eating the click.
  document.querySelectorAll(".faq details").forEach(function (d) {
    var summary = d.querySelector("summary");
    var answer = d.querySelector("p");
    if (!summary || !answer) return;
    var pending = null;
    function settle() {
      answer.removeEventListener("animationend", pending);
      clearTimeout(pending && pending.timer);
      pending = null;
      d.classList.remove("closing");
    }
    summary.addEventListener("click", function (ev) {
      if (!d.open || still.matches) return;
      ev.preventDefault();
      if (pending) { settle(); return; }   // reopen: cancel the close in flight
      d.classList.add("closing");
      pending = function () { settle(); d.open = false; };
      pending.timer = setTimeout(pending, 400);
      answer.addEventListener("animationend", pending, { once: true });
    });
  });

  // Screenshot rails: previous and next buttons plus a position readout for
  // mouse and keyboard users. Hidden while the rail fits without scrolling.
  document.querySelectorAll(".rail-wrap").forEach(function (wrap) {
    var rail = wrap.querySelector(".rail");
    var ctl = wrap.querySelector(".rail-ctl");
    var figs = rail ? rail.querySelectorAll("figure") : [];
    if (!ctl || !figs.length) return;
    var now = ctl.querySelector(".rail-now");
    var prev = ctl.querySelector('[data-step="-1"]');
    var next = ctl.querySelector('[data-step="1"]');
    var frame = 0;

    function max() { return rail.scrollWidth - rail.clientWidth; }
    function start() { return parseFloat(getComputedStyle(rail).paddingLeft) || 0; }
    function index() {
      if (rail.scrollLeft >= max() - 2) return figs.length - 1;
      var x = rail.scrollLeft + start();
      var best = 0;
      for (var i = 1; i < figs.length; i++) {
        if (Math.abs(figs[i].offsetLeft - x) < Math.abs(figs[best].offsetLeft - x)) best = i;
      }
      return best;
    }
    function update() {
      frame = 0;
      ctl.hidden = max() <= 2;
      now.textContent = String(index() + 1);
      prev.setAttribute("aria-disabled", String(rail.scrollLeft <= 2));
      next.setAttribute("aria-disabled", String(rail.scrollLeft >= max() - 2));
    }
    function go(step) {
      var target = Math.max(0, Math.min(figs.length - 1, index() + step));
      rail.scrollTo({ left: figs[target].offsetLeft - start(), behavior: still.matches ? "auto" : "smooth" });
    }
    [prev, next].forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (btn.getAttribute("aria-disabled") !== "true") go(Number(btn.getAttribute("data-step")));
      });
    });
    rail.addEventListener("scroll", function () {
      if (!frame) frame = requestAnimationFrame(update);
    }, { passive: true });
    if ("ResizeObserver" in window) new ResizeObserver(update).observe(rail);
    addEventListener("load", update);
    update();
  });

  // /work/ filters. CSS (:target) does the filtering, so they work with
  // JavaScript off. This adds aria-current on the active chip, a polite
  // live count for screen readers, and a view transition between states.
  var filters = document.querySelector(".filters");
  if (filters) {
    var chipsEls = filters.querySelectorAll(".fchip");
    var live = document.getElementById("work-live");
    var syncFilters = function (announce) {
      var id = location.hash.slice(1);
      if (!document.querySelector('.filters [data-filter="' + id + '"]')) id = "all";
      chipsEls.forEach(function (c) {
        if (c.getAttribute("data-filter") === id) c.setAttribute("aria-current", "true");
        else c.removeAttribute("aria-current");
      });
      var msg = document.querySelector('.work-count [data-for="' + id + '"]');
      if (announce && live && msg) live.textContent = msg.textContent;
    };
    filters.addEventListener("click", function (ev) {
      var chip = ev.target.closest(".fchip");
      if (!chip) return;
      // Handle the jump here so focus stays on the chip (a fragment jump drops it).
      ev.preventDefault();
      var y = scrollY;
      function go() {
        if (location.hash !== chip.hash) location.hash = chip.hash;
        if (scrollY !== y) scrollTo(scrollX, y);   // a fragment jump inside a view transition can scroll; filters never should
        syncFilters(true);
        chip.focus({ preventScroll: true });
      }
      if (location.hash !== chip.hash && document.startViewTransition && !still.matches) {
        root.classList.add("filter-vt");
        document.startViewTransition(go).finished.then(done, done);
      } else {
        go();
      }
      function done() { root.classList.remove("filter-vt"); }
    });
    addEventListener("hashchange", function () { syncFilters(true); });
    if (document.startViewTransition) root.classList.add("vt-filters");
    syncFilters(false);
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
