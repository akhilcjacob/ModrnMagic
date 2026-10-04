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
    var t = root.getAttribute("data-theme");
    return t === "light" || t === "dark" ? t : (dark.matches ? "dark" : "light");
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
  // that close runs it backwards from where it is, so the item stays open
  // without the answer blinking out and fading in again.
  document.querySelectorAll(".faq details").forEach(function (d) {
    var summary = d.querySelector("summary");
    var answer = d.querySelector("p");
    if (!summary || !answer) return;
    var pending = null;   // the close in flight
    var back = null;      // a close running backwards
    function stop() {
      if (!pending) return;
      answer.removeEventListener("animationend", pending);
      clearTimeout(pending.timer);
      pending = null;
    }
    function close() {
      pending = function () { stop(); d.classList.remove("closing"); d.open = false; };
      pending.timer = setTimeout(pending, 400);
      answer.addEventListener("animationend", pending, { once: true });
    }
    summary.addEventListener("click", function (ev) {
      if (!d.open || still.matches) return;
      ev.preventDefault();
      var anim = answer.getAnimations ? answer.getAnimations()[0] : null;
      if (pending) {   // reopen: reverse the close from its current point
        stop();
        if (!anim) { d.classList.remove("closing"); return; }
        back = anim;
        anim.playbackRate = -1;   // takes effect this frame; reverse() would wait a frame and dip first
        anim.finished.then(function () {
          if (back !== anim) return;
          back = null;
          d.classList.add("reopened");
          d.classList.remove("closing");
        }, function () {});
        return;
      }
      if (back) {   // close again while reversing: run forward again
        back.playbackRate = 1;
        back = null;
        close();
        return;
      }
      d.classList.remove("reopened");
      d.classList.add("closing");
      close();
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
      ctl.hidden = max() <= 2 || figs.length < 2;   // one shot: native scroll only, no dead "1 of 1"
      now.textContent = String(index() + 1);
      prev.setAttribute("aria-disabled", String(rail.scrollLeft <= 2));
      next.setAttribute("aria-disabled", String(rail.scrollLeft >= max() - 2));
    }
    // Step from where the rail is, not from the shot it reads as: at the end,
    // the shot before the last can sit past the furthest scroll, so stepping
    // back by index would not move at all.
    function go(step) {
      var x = rail.scrollLeft, left = 0;
      if (step > 0) {
        left = max();
        for (var i = 0; i < figs.length; i++) {
          if (figs[i].offsetLeft - start() > x + 2) { left = figs[i].offsetLeft - start(); break; }
        }
      } else {
        for (var j = figs.length - 1; j >= 0; j--) {
          if (figs[j].offsetLeft - start() < x - 2) { left = figs[j].offsetLeft - start(); break; }
        }
      }
      rail.scrollTo({ left: Math.max(0, Math.min(max(), left)), behavior: still.matches ? "auto" : "smooth" });
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
    // Lazy shots can load after the page does; each one can change what overflows.
    rail.querySelectorAll("img").forEach(function (img) { img.addEventListener("load", update); });
    update();
  });

  // /work/ filters. CSS (:target) does the filtering, so they work with
  // JavaScript off. This adds aria-current on the active chip, a polite
  // live count for screen readers, and a view transition between states.
  var filters = document.querySelector(".filters");
  if (filters) {
    var chipsEls = filters.querySelectorAll(".fchip");
    var live = document.getElementById("work-live");
    var running = 0;   // filter view transitions in flight
    // One pill per group, over the labels: CSS clips an inverted copy of them
    // to the pill's box from these numbers. It slides within a row; it fades
    // in when it changes group or row, since a diagonal slide reads as a glitch.
    var place = function (pill, chip, slide) {
      if (!chip) { pill.classList.remove("on"); return; }
      var y = chip.offsetTop;
      var glide = slide && pill.classList.contains("on") && pill.getAttribute("data-y") === String(y);
      if (!glide) {
        pill.classList.add("still");
        if (slide) pill.classList.remove("on");
      }
      pill.style.setProperty("--x", chip.offsetLeft);
      pill.style.setProperty("--y", y);
      pill.style.setProperty("--w", chip.offsetWidth);
      pill.style.setProperty("--h", chip.offsetHeight);
      pill.setAttribute("data-y", y);
      if (!slide) pill.classList.add("on");
      if (!glide) {
        void pill.offsetWidth;   // commit the jump before transitions come back
        pill.classList.remove("still");
      }
      pill.classList.add("on");
    };
    var placePills = function (slide) {
      filters.querySelectorAll(".fgroup").forEach(function (g) {
        var pill = g.querySelector(".fpill");
        if (pill) place(pill, g.querySelector('.fchip[aria-current="true"]'), slide);
      });
    };
    var syncFilters = function (announce) {
      var id = location.hash.slice(1);
      if (!document.querySelector('.filters [data-filter="' + id + '"]')) id = "all";
      chipsEls.forEach(function (c) {
        if (c.getAttribute("data-filter") === id) c.setAttribute("aria-current", "true");
        else c.removeAttribute("aria-current");
      });
      placePills(announce);
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
        // A second click aborts the running transition, whose done() still
        // fires: count them, so the faster timing holds until the last ends.
        running++;
        root.classList.add("filter-vt");
        document.startViewTransition(go).finished.then(done, done);
      } else {
        go();
      }
      function done() { if (--running === 0) root.classList.remove("filter-vt"); }
    });
    // Chips are links (so they work without JavaScript) but read as a
    // segmented control: Space selects, like Enter, instead of scrolling.
    filters.addEventListener("keydown", function (ev) {
      var chip = ev.target.closest(".fchip");
      if (!chip || (ev.key !== " " && ev.key !== "Spacebar")) return;
      ev.preventDefault();
      chip.click();
    });
    addEventListener("hashchange", function () { syncFilters(true); });
    if (document.startViewTransition) root.classList.add("vt-filters");
    filters.classList.add("pill");
    syncFilters(false);
    // Chips change size when the font loads or the bar wraps: follow without sliding.
    if ("ResizeObserver" in window) {
      var ro = new ResizeObserver(function () { placePills(false); });
      chipsEls.forEach(function (c) { ro.observe(c); });
      ro.observe(filters);
    }
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
