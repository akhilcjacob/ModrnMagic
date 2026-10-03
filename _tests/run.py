#!/usr/bin/env python3
"""Click tests for the published site. Dev only; `_tests/` is not published.

    python3 _tests/run.py            # all pages, exit 1 on any failure
    python3 _tests/run.py -v         # also print every passing check
    python3 _tests/run.py --browser=firefox  # the same suite in firefox or webkit
    RUN_TIMEOUT=2400 python3 _tests/run.py   # whole-run limit in seconds (default 2400)

It never hangs: each section has its own time limit and the whole run has
one. Past a limit it prints TIMEOUT with the section and the last check,
closes the browsers, and exits 2.

Needs Python 3 and Playwright for Python with Chromium
(`pip install playwright && playwright install chromium`). It serves the repo
with the standard library on a free local port, opens every published HTML
page, and clicks every unique link, button, toggle, disclosure, and rail
control, asserting what each one should do:

- internal links navigate to a page that loads (status 200) and anchors land
  on their target; external and mailto links receive the click unobstructed
  with the right href (they are not followed)
- the theme toggle flips the theme, aria-pressed, and the stored choice
- FAQ items open and close
- rail buttons move the rail and update the position readout
- the skip link appears on Tab and moves to #main
- no page makes a request off the local server, logs an error, or scrolls
  sideways at 320 px
- every legal URL answers bare, with a trailing slash, as /index.html, and
  as its Markdown source
- every product in apps/index.json has a page; drafts stay off shared pages
- the /work/ filter pill's label copy sits exactly on the chips and is
  clipped to the pill on the active chip, at 1440 and 320 px and across
  groups, is aria-hidden with no controls, and no label color animates
- /work/ filters filter by mouse, keyboard, and with JavaScript off, keep
  aria-current and the live count right, never scroll, and skip the view
  transition under reduced motion; numbers lines match the data
- home shows a flagship panel only when one is flagged (checked with nothing
  flagged and with each push-cycle product flagged, in temp copies), and the
  experiments strip holds the three newest experiments
- home hides Products, and every link to it, when there is no live product
  and no flagship
- the home bento has one cell per live product, no empty grid area, and no
  cell more than 40% empty, at 1440, 800, 390, and 320 px, for every live set
  and flagship choice the reviews named (bento_cases); "N live" matches
- text on tinted surfaces reaches 4.5:1 against the pixels behind it, in both
  themes, at 320, 360, 390, 800, and 1440 px
- no test depends on which products are drafts: each sets the state it needs
  in a temp copy (_tests/release.py runs the suite with drafts cleared too)
- nav links and the theme toggle are at least 44 px at seven widths, and
  breadcrumb links at least 24 px tall
- a FAQ click during the close animation reopens it; Space and fast clicks
  on /work/ filters behave
- check.py --release fails on draft output in HTML, and render.py --release
  deletes draft pages
- held drafts (.drafts/, local and gitignored) are nowhere in the published
  tree; check.py --release fails on a held product in apps/, held text in a
  page, or a drafts folder committed to git; the preview shows each held
  product with its banner; promoting every held draft with drafts.py and
  rendering passes check.py --release. These use the fictional drafts in
  _tests/fixtures/drafts/, so they run the same in a fresh clone
- render.py rejects unsafe data: non-slug ids, paths that leave the product
  folder, non-https links, and the attribute-injection values from the review
- 404.html is noindex, follow with no canonical; legal pages for a product
  whose policy lives on its own domain point there (canonical, refresh, link)
- in a temporary copy of the repo: renaming a product in its one name field
  leaves the old name nowhere; a push cycle renders What's new with working
  update links; bad product data makes render.py fail; check.py --release
  fails while drafts remain

It waits on running animations and view transitions (settle()), not fixed
sleeps. It ends with interaction coverage: tested unique controls over all
unique controls found.
"""
import functools
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import signal
import urllib.request
from collections import deque
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_scripts"))
import drafts as held_drafts  # noqa: E402  the held drafts in .drafts/ (local, unpublished)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Fictional held drafts. Every temp copy gets these in place of the local .drafts/,
# so no test depends on which drafts (if any) exist on this machine.
FIXTURE = os.path.join(ROOT, "_tests/fixtures/drafts")
VERBOSE = "-v" in sys.argv
ENGINE = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--browser=")), "chromium")
# Safari, and so WebKit, moves Tab between form controls only by default;
# Option+Tab is its key for "every item", which is what these tests mean.
TAB = "Alt+Tab" if ENGINE == "webkit" else "Tab"

results = []   # (ok, name, detail)


def frames(page, n=2):
    """Wait for n animation frames, at most 3 s. A page that stops painting is logged, not waited on forever."""
    ok = page.evaluate("""n => new Promise(r => { setTimeout(() => r(false), 3000);
        const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(true); f(n); })""", n)
    if not ok:
        print(f"RAF STALL: no animation frame in 3 s on {page.url} in {ENGINE}", flush=True)
    return ok


def settle(page, timeout=15000):
    """Wait until no animation or view transition is running, then one more
    frame so animationend handlers have run. No fixed sleeps: steady on a slow
    machine, quick on a fast one."""
    frames(page)
    page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')", timeout=timeout, polling="raf")
    frames(page, 1)


def scroll_settle(locator, timeout=5000):
    """Wait until an element's smooth scroll has stopped (scrollLeft unchanged for 6 frames)."""
    locator.evaluate("""(el, timeout) => new Promise(r => { let last = -1, same = 0; const t0 = performance.now();
      (function tick() { same = el.scrollLeft === last ? same + 1 : 0; last = el.scrollLeft;
        if (same >= 6 || performance.now() - t0 > timeout) r(); else requestAnimationFrame(tick); })(); })""", timeout)


# Time limits. A watchdog thread sends SIGINT to the main thread when the current
# section or the whole run is over its limit; the interrupt unwinds through
# sync_playwright(), which closes every browser. If that does not finish in
# 30 s, the process exits hard (the Playwright driver then closes the browsers).
RUN_LIMIT = float(os.environ.get("RUN_TIMEOUT", "2400"))
STARTED = time.monotonic()
NOW = {"section": "start", "deadline": STARTED + RUN_LIMIT, "last": "none", "fired": None}


def watchdog():
    while True:
        time.sleep(2)
        t = time.monotonic()
        if NOW["fired"] is None and t > min(NOW["deadline"], STARTED + RUN_LIMIT):
            what = "the whole run" if t > STARTED + RUN_LIMIT else f"section '{NOW['section']}'"
            NOW["fired"] = t
            print(f"\nTIMEOUT: {what} is over its limit; last check: {NOW['last']}", flush=True)
            os.kill(os.getpid(), signal.SIGINT)   # a real signal also wakes a blocking wait
        elif NOW["fired"] is not None and t > NOW["fired"] + 30:
            print("TIMEOUT: browsers did not close within 30 s; exiting hard", flush=True)
            os._exit(2)


class Recycled:
    """A WebKit browser that is relaunched every `limit` contexts.

    One Playwright WebKit browser (Playwright 1.60, WebKit 26.4, macOS) stops
    responding after 50 to 64 contexts, with no site involved: a page set with
    set_content and no network hangs in ctx.close() by context 64, and a
    one-line page from a local server hangs in goto at context 64. Evidence in
    ~/Development/modrn/_attic/site-qa-2026-10-03/webkit-wedge.md. Earlier
    browsers stay open for the contexts they already hold."""

    def __init__(self, browser_type, limit):
        self.browser_type, self.limit = browser_type, limit
        self.browsers, self.count = [browser_type.launch()], 0

    def new_context(self, **kw):
        if self.count >= self.limit:
            self.browsers.append(self.browser_type.launch())
            self.count = 0
        self.count += 1
        return self.browsers[-1].new_context(**kw)

    def new_page(self, **kw):
        return self.new_context(**kw).new_page()

    def close(self):
        for b in self.browsers:
            b.close()


def begin(name, limit):
    """Start a section of checks with its own time limit in seconds."""
    if VERBOSE and NOW.get("t0"):
        print(f"section '{NOW['section']}': {time.monotonic() - NOW['t0']:.0f}s", flush=True)
    NOW.update(section=name, deadline=time.monotonic() + limit, t0=time.monotonic())


def record(ok, name, detail=""):
    NOW["last"] = name
    results.append((ok, name, detail))
    if VERBOSE or not ok:
        print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))


def pages():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith((".", "_")))
        for name in sorted(filenames):
            if name.endswith(".html"):
                rel = os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/")
                out.append("/" + rel[: -len("index.html")] if rel.endswith("index.html") else "/" + rel)
    return out


def published_text():
    """Every text file GitHub Pages would publish (outside `_` and dot folders)."""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))]
        for name in filenames:
            if os.path.splitext(name)[1] in (".html", ".css", ".js", ".json", ".xml", ".txt", ".md"):
                yield os.path.join(dirpath, name)


SERVED = deque(maxlen=200)   # recent requests, for diagnosing a stalled load


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        SERVED.append(f"{time.strftime('%H:%M:%S')} {self.client_address[1]} {fmt % args}")


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass   # the browser closing a connection early is not a test failure


def serve(directory=ROOT):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = Server(("127.0.0.1", port), functools.partial(Quiet, directory=directory))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


# Collect every visible interactive control on a page with a stable key.
COLLECT = """() => {
  const out = [];
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !el.closest('[hidden]'); };
  document.querySelectorAll('a[href]').forEach((a, i) => {
    if (a.classList.contains('skip') || a.classList.contains('fchip')) return;
    out.push({kind: 'link', i, href: a.getAttribute('href'), abs: a.href,
              name: (a.getAttribute('aria-label') || a.textContent).trim().replace(/\\s+/g, ' ').slice(0, 60),
              visible: visible(a)});
  });
  document.querySelectorAll('.theme-toggle').forEach((b, i) => out.push({kind: 'toggle', i, name: 'theme', visible: visible(b)}));
  document.querySelectorAll('.faq summary').forEach((s, i) => out.push({kind: 'faq', i, name: s.textContent.trim(), visible: visible(s)}));
  document.querySelectorAll('.fchip').forEach((a, i) => out.push({kind: 'filter', i, name: a.textContent.trim(), visible: visible(a)}));
  document.querySelectorAll('.rail-wrap').forEach((w, i) => out.push({kind: 'rail', i, name: w.getAttribute('aria-label'), visible: true}));
  return out;
}"""


# A fixture push cycle. Only ever written to a temporary copy, never to the repo.
FIXTURE_CYCLE = {
    "start": "2026-10-05", "end": "2026-11-01",
    "goal": "Example goal: five private testers use it on five of seven days.",
    "updates": [
        {"date": "2026-10-09", "text": "Example update: the first private test build went to five testers."},
        {"date": "2026-10-16", "text": "Example update: recordings now survive a phone restart mid-session."},
        {"date": "2026-10-23", "text": "Example update: a calmer first-run setup with one step per screen."},
    ],
}


def temp_copy(edit=None, merge=True):
    """Copy the repo (without .git) to a temp folder with the fixture drafts as its
    .drafts/, merge them into it (the preview state, so every product is there to
    edit), apply edit(apps_dir), and render it there."""
    tmp = tempfile.mkdtemp(prefix="modrn-site-test-")
    dest = os.path.join(tmp, "site")
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "_attic", "_preview", ".drafts"))
    shutil.copytree(FIXTURE, os.path.join(dest, held_drafts.DRAFTS))
    if merge:
        held_drafts.merge(dest)
    if edit:
        edit(os.path.join(dest, "apps"))
    r = subprocess.run([sys.executable, "_scripts/render.py"], cwd=dest, capture_output=True, text=True)
    return tmp, dest, r


def edit_app(apps_dir, aid, change):
    path = os.path.join(apps_dir, aid, "app.json")
    data = json.load(open(path))
    change(data)
    json.dump(data, open(path, "w"), indent=2)


STATUS_GROUP = {"live": "live", "lab": "experiments", "archived": "archived"}
PUSH_CYCLE = ("samplenote", "nookly", "inboxhiiv", "sampleboard")


def load_all(root=ROOT, held=False):
    """Products as published in `root`, or with the fixture drafts merged (held=True)."""
    if held:
        return held_drafts.merged_apps(root, FIXTURE)
    ids = json.load(open(os.path.join(root, "apps/index.json")))
    return [json.load(open(os.path.join(root, "apps", i, "app.json"))) for i in ids]


def expected_numbers(apps):
    """Recomputed here from app.json, independent of render.py."""
    n = {k: sum(1 for a in apps if a["status"] == k) for k in ("live", "lab", "archived")}
    starts = [v for a in apps for v in (a["dates"].get("started"), a["dates"].get("shipped"), a["dates"].get("updated")) if v]
    exp = f"{n['lab']} experiment" + ("s" if n["lab"] != 1 else "")
    return f"{len(apps)} product" + ("s" if len(apps) != 1 else "") + f" since {min(starts)[:4]}: {n['live']} live, {exp}, and {n['archived']} archived."


def filter_tests(browser, base, seen, tested):
    apps = load_all()
    def matches(fid, a):
        if fid == "all":
            return True
        if fid.startswith("kind-"):
            return a["kind"] == fid[5:]
        return STATUS_GROUP[a["status"]] == fid
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(base + "/work/")
    numbers = page.locator(".work .numbers").inner_text()
    record(numbers.startswith(expected_numbers(apps)), "/work/ numbers line matches app.json", numbers)
    chips = page.eval_on_selector_all(".fchip", "els => els.map(e => e.dataset.filter)")
    for fid in chips + ["all"]:
        page.evaluate("scrollTo(0, 0)")
        page.locator(f'.fchip[data-filter="{fid}"]').click()
        settle(page)
        shown = page.eval_on_selector_all(".work-item", "els => els.filter(e => getComputedStyle(e).display !== 'none').map(e => e.querySelector('.name').textContent)")
        want = [a["name"] for a in apps if matches(fid, a)]
        current = page.eval_on_selector_all(".fchip[aria-current]", "els => els.map(e => e.dataset.filter)")
        count = page.locator(f'.work-count [data-for="{fid}"]').inner_text()
        live = page.locator("#work-live").inner_text()
        state = page.evaluate("[location.hash, scrollY]")
        ok = (sorted(shown) == sorted(want) and current == [fid] and str(len(want)) in count
              and live == count and state[0] == "#" + fid and state[1] == 0)
        record(ok, f"/work/ filter '{fid}': {len(want)} shown, aria-current, live count, no scroll",
               f"shown {len(shown)} want {len(want)} current {current} live {live!r} state {state}")
        key = ("filter", "/work/", chips.index(fid))
        if ok and key in seen:
            tested.add(key)
    pill_tests(page, base)
    # Keyboard: chips in reading order, Enter activates, focus stays on the chip.
    page.goto(base + "/work/")
    page.locator(".fchip").first.focus()
    order = [page.evaluate("document.activeElement.dataset.filter")]
    for _ in range(len(chips) - 1):
        page.keyboard.press(TAB)
        order.append(page.evaluate("document.activeElement.dataset.filter"))
    page.keyboard.press("Enter")
    settle(page)
    after = page.evaluate("[document.activeElement.dataset.filter, location.hash]")
    record(order == chips and after == [chips[-1], "#" + chips[-1]], "/work/ filters: Tab order follows the chips, Enter filters, focus stays", f"{order} {after}")
    page.close()
    # JavaScript off: :target alone filters, and deep links work.
    # Reduced motion, so chip colors read their final values right after a click (no transition to wait for).
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, java_script_enabled=False, reduced_motion="reduce")
    p2 = ctx.new_page()
    p2.goto(base + "/work/#archived")
    vis = p2.eval_on_selector_all(".work-item", "els => els.filter(e => getComputedStyle(e).display !== 'none').length")
    p2.locator('.fchip[data-filter="live"]').click()
    vis_live = p2.eval_on_selector_all(".work-item", "els => els.filter(e => getComputedStyle(e).display !== 'none').map(e => e.dataset.status)")
    want_arch = sum(1 for a in apps if a["status"] == "archived")
    record(vis == want_arch and vis_live and set(vis_live) == {"live"}, "/work/ filters work with JavaScript off, deep links included", f"{vis} {vis_live}")
    nojs = p2.evaluate("""() => [[...document.querySelectorAll('.fpill')].every(p => getComputedStyle(p).display === 'none'),
        getComputedStyle(document.querySelector('.fchip[data-filter="live"]')).backgroundColor !== getComputedStyle(document.querySelector('.fchip[data-filter="all"]')).backgroundColor]""")
    record(nojs == [True, True], "/work/ with JavaScript off: no label copy shows, the active chip itself is the pill", str(nojs))
    ctx.close()
    # Reduced motion: no view transition and no item animation, still filters.
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    p3 = ctx.new_page()
    p3.goto(base + "/work/")
    p3.evaluate("window.__vt = 0; const o = document.startViewTransition && document.startViewTransition.bind(document); if (o) document.startViewTransition = cb => { window.__vt++; return o(cb); }; 0")
    p3.locator('.fchip[data-filter="experiments"]').click()
    frames(p3, 3)   # a reduced-motion change must not start any animation
    res = p3.evaluate("[window.__vt, [...document.querySelectorAll('.work-item')].filter(e => getComputedStyle(e).display !== 'none').length, document.getAnimations().filter(a => a.playState === 'running').length]")
    want = sum(1 for a in apps if a["status"] == "lab")
    record(res == [0, want, 0], "/work/ under reduced motion: no view transition or animation, still filters", str(res))
    ctx.close()
    # With motion, a filter change runs one view transition.
    p4 = browser.new_page(viewport={"width": 1440, "height": 900})
    p4.goto(base + "/work/")
    p4.evaluate("window.__vt = 0; const o = document.startViewTransition.bind(document); document.startViewTransition = cb => { window.__vt++; return o(cb); }; 0")
    p4.locator('.fchip[data-filter="archived"]').click()
    settle(p4)
    record(p4.evaluate("window.__vt") == 1, "/work/ filter change runs one view transition")
    # Two fast clicks: the aborted first transition must not drop the faster
    # timing (filter-vt) while the second still runs (review item 11).
    p4.goto(base + "/work/")
    settle(p4)
    # Sample every frame: any frame with view-transition animations running but no filter-vt is the bug.
    p4.evaluate("""() => { window.__frames = []; const t0 = performance.now(); (function tick() {
        const vt = document.getAnimations().some(a => (a.effect.pseudoElement || '').startsWith('::view-transition'));
        window.__frames.push([vt, document.documentElement.classList.contains('filter-vt')]);
        if (performance.now() - t0 < 1500) requestAnimationFrame(tick); else window.__sampled = true; })(); }""")
    p4.evaluate("""() => { document.querySelector('.fchip[data-filter="live"]').click();
        setTimeout(() => document.querySelector('.fchip[data-filter="experiments"]').click(), 60); }""")
    p4.wait_for_function("window.__frames.filter(f => f[0]).length > 0")
    settle(p4)
    p4.wait_for_function("window.__sampled")   # the sampler's window is over
    samples = p4.evaluate("window.__frames")
    vt_frames = [f for f in samples if f[0]]
    dropped = sum(1 for f in vt_frames if not f[1])
    end = p4.evaluate("[document.documentElement.classList.contains('filter-vt'), location.hash]")
    record(vt_frames and not dropped and end == [False, "#experiments"],
           "/work/ two fast filter clicks keep the faster timing until the last transition ends",
           f"{len(vt_frames)} transition frames, {dropped} without filter-vt, end {end}")
    # Space on a chip filters like Enter and never scrolls the page (review item 12).
    p4.set_viewport_size({"width": 390, "height": 600})
    p4.goto(base + "/work/")
    p4.evaluate("scrollTo(0, 120)")
    y0 = p4.evaluate("scrollY")
    p4.locator('.fchip[data-filter="archived"]').focus()
    p4.keyboard.press(" ")
    settle(p4)
    got = p4.evaluate("[location.hash, scrollY, document.activeElement.dataset.filter]")
    record(got == ["#archived", y0, "archived"], "/work/ Space on a filter chip filters, keeps focus, and does not scroll", str(got))
    p4.close()


PILL_GEO = """() => [...document.querySelectorAll('.fgroup')].map(g => {
  const chips = [...g.querySelectorAll('.fchip')], copies = [...g.querySelectorAll('.flabels > span')];
  const off = Math.max(...chips.map((c, i) => { const a = c.getBoundingClientRect(), b = copies[i] ? copies[i].getBoundingClientRect() : {};
    return Math.max(Math.abs(a.left - b.left), Math.abs(a.top - b.top), Math.abs(a.width - b.width), Math.abs(a.height - b.height)); }));
  const pill = g.querySelector('.fpill'), cur = g.querySelector('.fchip[aria-current]');
  let pe = 0;
  if (cur) { const a = cur.getBoundingClientRect(), r = pill.getBoundingClientRect(), v = k => +pill.style.getPropertyValue(k);
    pe = Math.max(Math.abs(r.left + v('--x') - a.left), Math.abs(r.left + v('--x') + v('--w') - a.right), Math.abs(r.top + v('--y') - a.top), Math.abs(v('--h') - a.height)); }
  return [copies.length === chips.length && copies.every((c, i) => c.textContent === chips[i].textContent), +off.toFixed(2), +pe.toFixed(2),
    !!cur === (getComputedStyle(pill).opacity === '1'), pill.getAttribute('aria-hidden'), pill.querySelectorAll('a, button, [tabindex]').length];
})"""


def pill_tests(page, base):
    """The pill is a copy of the labels clipped to the pill's shape (review
    fix 3, item 1): copies sit exactly on the chips, the pill sits on the
    active chip, the copy is hidden from assistive tech and holds no controls,
    and no label color animates on a selection change."""
    for w in (1440, 320):
        page.set_viewport_size({"width": w, "height": 900})
        page.goto(base + "/work/")
        page.mouse.move(1, 1)
        for fid in ("live", "archived", "kind-web", "kind-game", "all"):
            settle(page)
            # Record any color or background animation on a chip or copy while the pill moves.
            page.evaluate("""() => { window.__color = []; const t0 = performance.now(); (function tick() {
                document.getAnimations().forEach(a => { const p = a.transitionProperty || '', t = a.effect && a.effect.target;
                  if (t && t.closest && t.closest('.fgroup') && /color/.test(p)) window.__color.push(p); });
                if (performance.now() - t0 < 600) requestAnimationFrame(tick); else window.__colorDone = true; })(); }""")
            # Keyboard, so no hover color (allowed on hover) muddies the check.
            page.locator(f'.fchip[data-filter="{fid}"]').focus()
            page.keyboard.press("Enter")
            page.wait_for_function("window.__colorDone")
            settle(page)
            geo = page.evaluate(PILL_GEO)
            colors = page.evaluate("window.__color")
            same = page.evaluate("""() => new Set([...document.querySelectorAll('.fchip')].map(c => getComputedStyle(c).color)).size""")
            ok = all(g[0] and g[1] <= 0.5 and g[2] <= 1 and g[3] and g[4] == "true" and g[5] == 0 for g in geo) and not colors and same == 1
            record(ok, f"/work/ pill at {w}px on '{fid}': copies on the chips, pill on the active chip, aria-hidden, no color animation",
                   f"{geo} color animations {colors} label colors {same}")

def flagship_tests(browser):
    apps = {a["id"]: a for a in load_all(held=True)}
    listed_apps = [a for a in apps.values() if not a.get("draft")]
    # Nothing flagged (the real data): home is complete without the panel.
    server, base = serve()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(base + "/")
    got = page.evaluate("[document.querySelectorAll('.flagship').length, document.querySelectorAll('.bento .cell').length, [...document.querySelectorAll('.strip .card .name')].map(e => e.textContent)]")
    labs = sorted((a for a in listed_apps if a["status"] == "lab"),
                  key=lambda a: max(v for v in (a["dates"].get("updated"), a["dates"].get("ended"), a["dates"].get("shipped"), a["dates"].get("started")) if v), reverse=True)
    record(not any(a.get("flagship") for a in apps.values()), "no product is flagged in the real data (HQ picks)")
    n_live = sum(1 for a in listed_apps if a["status"] == "live")
    record(got[0] == 0 and got[1] == n_live and got[2] == [a["name"] for a in labs[:3]],
           "home with nothing flagged: no panel, full bento, three newest experiments", str(got))
    numbers = page.locator(".hero .numbers").inner_text()
    record(numbers == expected_numbers(listed_apps), "home numbers line matches app.json", numbers)
    page.close()
    server.shutdown()
    # Each push-cycle product flagged in turn.
    for aid in PUSH_CYCLE:
        tmp, dest, r = temp_copy(lambda d, aid=aid: edit_app(d, aid, lambda a: a.update(flagship=True)))
        if r.returncode:
            record(False, f"flagship {aid}: renders", r.stderr[-200:])
            continue
        server, base = serve(dest)
        a = apps[aid]
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(base + "/")
        panel = page.locator(".flagship")
        name = panel.locator("#flagship-title").inner_text() if panel.count() else ""
        cta = panel.locator(".btn").get_attribute("href") if panel.count() else ""
        want_cta = (a["links"].get("web") or a["links"].get("appStore") or a["links"].get("googlePlay")) if a["status"] == "live" else f"/apps/{aid}/"
        in_bento = page.locator(f'.bento [data-app="{aid}"]').count()
        in_strip = page.locator(".strip .card", has_text=a["name"]).count()
        labelled = page.evaluate("document.querySelector('.flagship').getAttribute('aria-labelledby')") == "flagship-title"
        draft_ok = (panel.locator(".draft-mark").count() > 0) == bool(a.get("draft"))
        record(panel.count() == 1 and name == a["name"] and cta == want_cta and not in_bento and not in_strip and labelled and draft_ok,
               f"flagship {aid}: one panel, labelled, right call to action, not repeated below", f"{name} {cta} bento {in_bento} strip {in_strip}")
        # Keyboard: the name link, then the call to action.
        panel.locator("#flagship-title a").focus()
        page.keyboard.press(TAB)
        focus_ok = page.evaluate("document.activeElement.closest('.flagship') && document.activeElement.classList.contains('btn')")
        record(bool(focus_ok), f"flagship {aid}: Tab goes from the name to the call to action")
        # Click the call to action.
        if cta.startswith("/"):
            with page.expect_navigation():
                panel.locator(".btn").click()
            record(urlsplit(page.url).path == cta, f"flagship {aid}: call to action opens {cta}")
        else:
            page.evaluate("""() => { window.__clicked = null; document.addEventListener('click', e => { const a = e.target.closest('a');
                window.__clicked = a && a.href; e.preventDefault(); }, {once: true}); }""")
            panel.locator(".btn").click()
            record(page.evaluate("window.__clicked") == page.evaluate("u => new URL(u).href", cta), f"flagship {aid}: call to action receives the click for {cta}")
        page.close()
        for w in (320,):
            ctx = browser.new_context(viewport={"width": w, "height": 800}, reduced_motion="reduce")
            p2 = ctx.new_page()
            p2.goto(base + "/")
            res = p2.evaluate("[document.documentElement.scrollWidth, getComputedStyle(document.querySelector('.flagship')).opacity]")
            record(res[0] <= w and res[1] == "1", f"flagship {aid}: fits 320px and is visible at once under reduced motion", str(res))
            ctx.close()
        server.shutdown()
        shutil.rmtree(tmp)

    # Release build: no drafts on /work/ or home, even when a draft is flagged.
    # The test makes its own draft (a live product with art), so it holds
    # whether or not the real data still has any.
    pick = next(a["id"] for a in apps.values() if a["status"] == "live" and a["screenshots"])
    tmp, dest, r = temp_copy(lambda d: edit_app(d, pick, lambda a: a.update(draft=True, flagship=True)))
    rel = subprocess.run([sys.executable, "_scripts/render.py", "--release"], cwd=dest, capture_output=True, text=True)
    work = open(os.path.join(dest, "work/index.html")).read()
    home = open(os.path.join(dest, "index.html")).read()
    drafts = [a for a in load_all(dest) if a.get("draft")]
    leak = [a["id"] for a in drafts if f"/apps/{a['id']}/" in work or f"/apps/{a['id']}/" in home]
    record(rel.returncode == 0 and pick in [a["id"] for a in drafts] and not leak and 'class="draft-mark"' not in work
           and 'class="flagship' not in home,
           f"release build: no drafts on /work/ or home, and a draft flagship ({pick}) falls back", ", ".join(leak) or rel.stderr[-120:])
    shutil.rmtree(tmp)
    # /work/ is in the sitemap and llms.txt.
    sm, llms = open(os.path.join(ROOT, "sitemap.xml")).read(), open(os.path.join(ROOT, "llms.txt")).read()
    record("https://modrnmagic.app/work/" in sm and "https://modrnmagic.app/work/" in llms, "/work/ is in sitemap.xml and llms.txt")


# Every grid track of the bento, sampled at its center, must fall inside a cell.
BENTO_HOLES = """() => {
  const g = document.querySelector('.bento'); if (!g) return [];
  const cs = getComputedStyle(g), r = g.getBoundingClientRect();
  const cols = cs.gridTemplateColumns.split(' ').map(parseFloat), rows = cs.gridTemplateRows.split(' ').map(parseFloat);
  const cells = [...g.children].map(c => c.getBoundingClientRect());
  const holes = []; let y = r.top;
  rows.forEach((h, j) => { let x = r.left;
    cols.forEach((w, i) => { const cx = x + w / 2, cy = y + h / 2;
      if (!cells.some(c => cx >= c.left && cx <= c.right && cy >= c.top && cy <= c.bottom)) holes.push([i, j]);
      x += w + parseFloat(cs.columnGap); });
    y += h + parseFloat(cs.rowGap); });
  return holes;
}"""


# Each bento cell's largest empty vertical stretch, as a share of its height.
# Content is every child box (arrow aside) plus the visible part of a peek, so
# a cell stretched by its row neighbour shows up even when the grid has no hole.
BENTO_GAPS = """() => [...document.querySelectorAll('.bento .cell')].map(c => {
  const r = c.getBoundingClientRect(), pad = parseFloat(getComputedStyle(c).paddingTop);
  const boxes = [...c.children].filter(k => !k.classList.contains('arrow') && !k.classList.contains('peek-clip'))
    .map(k => k.getBoundingClientRect()).filter(k => k.height > 0);
  const clip = c.querySelector('.peek-clip'), peek = c.querySelector('.peek');
  if (clip && peek && getComputedStyle(clip).display !== 'none') {
    const p = peek.getBoundingClientRect(); boxes.push({top: Math.max(p.top, r.top), bottom: Math.min(p.bottom, r.bottom)}); }
  boxes.sort((a, b) => a.top - b.top);
  let gap = 0, prev = r.top + pad;
  boxes.forEach(k => { gap = Math.max(gap, k.top - prev); prev = Math.max(prev, k.bottom); });
  gap = Math.max(gap, r.bottom - pad - prev);
  return [c.dataset.app, c.className.match(/cell-(\\w+)/)[1], Math.round(r.height), Math.round(gap)];
})"""
MAX_GAP = .4    # no cell may be more than 40% empty space
MIN_GAP = 64    # gaps under this many px are air, not a broken row


def bento_check(browser, base, label, apps):
    """Home bento: one cell per live, listed, non-flagship product, no grid holes
    and no mostly empty cell at any width, and the live count matches."""
    listed_apps = [a for a in apps if not a.get("draft")]
    flag = next((a for a in listed_apps if a.get("flagship")), None)
    want = [a["id"] for a in listed_apps if a["status"] == "live" and a is not flag]
    for w in (1440, 800, 390, 320):
        ctx = browser.new_context(viewport={"width": w, "height": 900}, reduced_motion="reduce")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "/")
        page.evaluate("document.querySelectorAll('.bento img[loading=lazy]').forEach(i => i.loading = 'eager')")
        page.wait_for_function("[...document.querySelectorAll('.bento img')].every(i => i.complete)")
        cells = page.eval_on_selector_all(".bento .cell", "els => els.map(e => e.dataset.app)")
        holes = page.evaluate(BENTO_HOLES)
        empty = [c for c in page.evaluate(BENTO_GAPS) if c[3] > MIN_GAP and c[3] > MAX_GAP * c[2]]
        live_n = int(re.search(r"(\d+) live", page.locator(".hero .numbers").inner_text()).group(1))
        shown_live = len(cells) + (1 if flag and flag["status"] == "live" else 0)
        sw = page.evaluate("document.documentElement.scrollWidth")
        record(cells == want and not holes and not empty and live_n == shown_live and sw <= w and not errors,
               f"bento {label} at {w}px: a cell per live product, no holes, no cell over {MAX_GAP:.0%} empty, '{live_n} live' matches",
               f"cells {cells} want {want} holes {holes} empty [id, size, height, gap] {empty} scrollWidth {sw} {errors}")
        if w == 1440:
            # Products shows only with a flagship panel or a bento cell, and no
            # link anywhere points at /#products when it is gone (review item 6).
            has = bool(want or flag)
            got = page.evaluate("""() => [!!document.getElementById('products'),
                [...document.querySelectorAll('h2')].some(h => h.textContent.trim() === 'Products'),
                [...document.querySelectorAll('footer h2')].filter(h => !h.nextElementSibling || !h.nextElementSibling.children.length).length,
                [...document.querySelectorAll('a[href$="#products"]')].length,
                document.querySelector('.hero .btn-primary').getAttribute('href')]""")
            page.goto(base + "/work/")
            nav_link = page.evaluate("document.querySelectorAll('a[href=\"/#products\"]').length")
            want_got = [True, True, 0, got[3] or -1, "#products"] if has else [False, False, 0, 0, "/work/"]
            record(got == want_got and (nav_link > 0) == has,
                   f"bento {label}: Products section {'shown' if has else 'hidden, no links to it'}",
                   f"[section, heading, empty footer columns, #products links, hero button] {got} want {want_got}, /work/ links {nav_link}")
        ctx.close()


def set_live(ids):
    """An edit that makes exactly these products live and listed, in this order at the top of apps/index.json."""
    def edit(d):
        order = json.load(open(os.path.join(d, "index.json")))
        for aid in order:
            def change(a, on=aid in ids):
                if on:
                    a.pop("draft", None)
                    a.update(status="live", outcome=None)
                elif a["status"] == "live":
                    a["status"] = "lab"
                a["flagship"] = False
            edit_app(d, aid, change)
        json.dump(list(ids) + [i for i in order if i not in ids], open(os.path.join(d, "index.json"), "w"), indent=2)
    return edit


def flag(aid, live=False):
    """An edit that flags one product, first making it live and listed when asked."""
    def edit(d):
        edit_app(d, aid, lambda a: (a.pop("draft", None), a.update(status="live", outcome=None)) if live else a.pop("draft", None))
        edit_app(d, aid, lambda a: a.update(flagship=True))
    return edit


def bento_cases(apps):
    """Every live set and flagship choice the reviews named. Each edit states the
    state it needs, so no case depends on which products are drafts today."""
    live_now = [a["id"] for a in apps if a["status"] == "live"]
    with_art = [a["id"] for a in apps if a["screenshots"] and a["status"] != "archived"]
    no_art = next((a["id"] for a in apps if not a["screenshots"] and a["status"] != "archived"), None)
    wide_first = next((a["id"] for a in apps if a["screenshots"] and all(s["shape"] == "wide" for s in a["screenshots"][:2])), None)
    mixed_first = next((a["id"] for a in apps if any(s["shape"] == "wide" for s in a["screenshots"])
                        and sum(s["shape"] == "phone" for s in a["screenshots"]) < 2), None)
    cases = [("nothing flagged", None)]
    cases += [(f"{aid} flagged", flag(aid)) for aid in live_now]
    cases += [("sampleboard live", set_live(live_now + ["sampleboard"] if "sampleboard" not in live_now else live_now)),
              ("sampleboard live and flagged", flag("sampleboard", live=True)),
              ("samplenote live", set_live([i for i in live_now if i != "samplenote"] + ["samplenote"])),
              ("samplenote live and flagged", flag("samplenote", live=True)),
              ("quietdesk flagged", flag("quietdesk")),
              ("nookly flagged", flag("nookly"))]
    pool = with_art + [a["id"] for a in apps if a["id"] not in with_art and a["status"] != "archived"]
    cases += [(f"{n} cells", set_live(pool[:n])) for n in (0, 1, 2, 3, 4, 5, 6, 7)]
    if wide_first:
        cases.append((f"wide-shot lead ({wide_first})", set_live([wide_first] + [i for i in pool if i != wide_first][:4])))
    if mixed_first:
        cases.append((f"one-phone lead ({mixed_first})", set_live([mixed_first] + [i for i in pool if i != mixed_first][:4])))
    if no_art:
        cases.append((f"no-art lead ({no_art})", set_live([no_art] + [i for i in pool if i != no_art][:4])))
        cases.append((f"no-art half ({no_art})", set_live(pool[:2] + [no_art] + pool[2:4])))
    return cases


def bento_tests(browser):
    for label, edit in bento_cases(load_all(held=True)):
        if edit is None:
            server, base = serve()
            bento_check(browser, base, label, load_all())
            server.shutdown()
            continue
        tmp, dest, r = temp_copy(lambda d, edit=edit: edit(d))
        if r.returncode:
            record(False, f"bento {label}: renders", r.stderr[-200:])
            shutil.rmtree(tmp)
            continue
        server, base = serve(dest)
        bento_check(browser, base, label, load_all(dest))
        contrast_check(browser, base, "/", f"home with {label}", widths=(390, 1440))
        server.shutdown()
        shutil.rmtree(tmp)


# Text on product surfaces must reach WCAG AA (4.5:1) against what is actually
# painted behind it: glass, tint gradient, and wash. The text is hidden, the
# page is captured, and each text box is measured against its own pixels.
CARD_TEXT = ".cell, .card, .w-card, .flagship, .feature"
TEXT_SEL = ".meta, .status, .chip, .one, .w-outcome, .draft-mark, .name, .fl-news, .h3, p"
CONTRAST_WIDTHS = (320, 360, 390, 800, 1440)   # text moves under the tint gradient on narrow cards


def luminance(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb[:3])
    return .2126 * r + .7152 * g + .0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + .05) / (lb + .05)


def contrast_check(browser, base, path, label, themes=("light", "dark"), widths=CONTRAST_WIDTHS):
    for w in widths:
        for theme in themes:
            contrast_one(browser, base, path, f"{label} at {w}px", theme, w)


def contrast_one(browser, base, path, label, theme, width, diagnose=False):
    from io import BytesIO
    from PIL import Image
    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=theme, reduced_motion="reduce")
    page = ctx.new_page()
    pending, done = {}, []
    page.on("request", lambda r: pending.__setitem__(r.url, r.resource_type))
    page.on("requestfinished", lambda r: (pending.pop(r.url, None), done.append(r.url.replace(base, ""))))
    page.on("requestfailed", lambda r: (pending.pop(r.url, None), done.append(f"FAILED {r.url.replace(base, '')} {r.failure}")))
    try:
        page.goto(base + path, wait_until="load", timeout=20000)
    except Exception as err:
        # A load that never finishes is a failure, never retried into a pass. The
        # evidence says where it stuck: what the page requested and never got,
        # what the server saw, and whether a fresh browser loads the same page.
        state = "unknown"
        try:
            page.wait_for_function("true", timeout=3000)
            state = page.evaluate("document.readyState")
        except Exception:
            state = "page not responding"
        seen_by_server = [x for x in SERVED if path.rstrip("/") in x][-4:]
        ctx.close()
        detail = (f"{str(err).splitlines()[0]}; readyState {state}; pending {dict(list(pending.items())[:8])}; "
                  f"finished {len(done)}: {done[-6:]}; server saw {seen_by_server or 'nothing for this path'}")
        print(f"STALL {path} at {width}px ({theme}) in {ENGINE}: {detail}", flush=True)
        if diagnose:
            record(False, f"STALL DIAGNOSIS fresh {ENGINE} also fails to load {path} at {width}px ({theme})", detail)
            return
        record(False, f"card text contrast on {label} ({theme}): page loads in {ENGINE}", detail)
        fresh = browser.browser_type.launch()   # evidence only: the failure above stands
        try:
            contrast_one(fresh, base, path, label + " (fresh browser, diagnosis)", theme, width, diagnose=True)
        finally:
            fresh.close()
        return
    page.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
    try:
        page.wait_for_function("[...document.images].every(i => i.complete)", timeout=15000)
    except Exception:
        stuck = page.evaluate("[...document.images].filter(i => !i.complete).map(i => i.currentSrc || i.src)")
        record(False, f"card text contrast on {label} ({theme}): images load", f"incomplete {stuck}")
        ctx.close()
        return
    settle(page)
    boxes = page.evaluate("""([cards, sel]) => [...document.querySelectorAll(cards)].flatMap(card =>
      [...card.querySelectorAll(sel)].filter(el => el.getBoundingClientRect().width > 0).map(el => {
        const r = el.getBoundingClientRect(); const c = getComputedStyle(el).color.match(/[\\d.]+/g).map(Number);
        return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, color: c,
                what: (card.querySelector('.name') || card).textContent.trim().slice(0, 20) + ' ' + el.className + ' ' + el.textContent.trim().slice(0, 16)};
      }))""", [CARD_TEXT, TEXT_SEL])
    page.add_style_tag(content="* { color: transparent !important; text-shadow: none !important; -webkit-text-fill-color: transparent !important; border-color: transparent !important; }")
    settle(page)
    shot = Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")
    worst = []
    for b in boxes:
        crop = shot.crop((int(b["x"]), int(b["y"]), int(b["x"] + b["w"]), int(b["y"] + b["h"])))
        px = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())
        if not px:
            continue
        ratios = sorted(contrast(b["color"], p) for p in px)
        low = ratios[len(ratios) // 50]   # 2nd percentile: one stray edge pixel does not decide
        if low < 4.5:
            worst.append(f"{b['what']} {low:.2f}")
    record(not worst and bool(boxes), f"card text contrast >= 4.5 on {label} ({theme}), {len(boxes)} text boxes", "; ".join(worst[:6]))
    ctx.close()


def tinted_pages():
    """Product pages and product sites whose own surfaces carry the product tint."""
    out = []
    for path in pages():
        if path.startswith("/apps/") and path.count("/") <= 4 and not any(x in path for x in ("/privacy", "/tos")):
            html = open(os.path.join(ROOT, path.lstrip("/"), "index.html")).read()
            if re.search(r'class="features n3" style="[^"]*--glow', html) or re.search(r'<main id="main" style="[^"]*--glow', html):
                out.append(path)
    return tuple(out)


def data_tests(browser):
    # 10 of 10: every product has a page, and drafts stay off shared pages.
    ids = json.load(open(os.path.join(ROOT, "apps/index.json")))
    have = [i for i in ids if os.path.isfile(os.path.join(ROOT, "apps", i, "index.html"))]
    record(len(have) == len(ids), f"product pages: {len(have)} of {len(ids)}", ", ".join(sorted(set(ids) - set(have))))
    shared = {f: open(os.path.join(ROOT, f)).read() for f in ("index.html", "sitemap.xml", "llms.txt", "contact/index.html", "apps/flowmoro/index.html")}
    for i in ids:
        app = json.load(open(os.path.join(ROOT, "apps", i, "app.json")))
        if not app.get("draft"):
            continue
        page = open(os.path.join(ROOT, "apps", i, "index.html")).read()
        leaks = [f for f, text in shared.items() if f"/apps/{i}/" in text]
        record(not leaks and 'name="robots" content="noindex' in page and "draft-banner" in page,
               f"draft {i}: own noindex page with a banner, not on shared pages", ", ".join(leaks))

    # Drafts block a release: the gate agrees with the real data, and fails on a draft the test makes itself.
    r = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=ROOT, capture_output=True, text=True)
    pending = any(a.get("draft") or (a.get("outcome") or {}).get("draft") or any(x["draft"] for x in a["lessons"]) for a in load_all())
    record((r.returncode == 1) == pending, "check.py --release agrees with the drafts in the real data", r.stdout.strip().splitlines()[-1])
    tmp, dest, _ = temp_copy(lambda d: edit_app(d, ids[0], lambda a: a.update(draft=True)))
    r = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
    record(r.returncode == 1 and f"DRAFT apps/{ids[0]}" in r.stdout, "check.py --release fails while a draft remains", r.stdout.strip()[-120:])
    shutil.rmtree(tmp)

    # Held drafts: the committed tree carries none of them, the gate catches a
    # leak, the preview shows them marked, and promoting all of them is a release.
    # The real local drafts, when this machine has any (a fresh clone has none).
    data, products = held_drafts.held(ROOT)
    published = "\n".join(open(f, encoding="utf-8", errors="replace").read() for f in published_text())
    leaks = [p for p in products if f"/apps/{p}/" in published or os.path.exists(os.path.join(ROOT, "apps", p))]
    leaks += [aid for aid, line in data["lines"].items()
              if (line.get("outcome") and line["outcome"]["line"] in published) or any(x["text"] in published for x in line.get("lessons", []))]
    record(not leaks, f"held drafts ({len(held_drafts.listing())}) are nowhere in the published tree", ", ".join(leaks))
    tracked = subprocess.run(["git", "ls-files", "--", ".drafts", "_drafts"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    record(not tracked, "no held drafts are committed to git (the repository is public)", ", ".join(tracked[:5]))
    ignored = subprocess.run(["git", "check-ignore", "-q", ".drafts/drafts.json"], cwd=ROOT).returncode == 0
    record(ignored or not os.path.isdir(os.path.join(ROOT, ".git")), ".drafts/ is gitignored")
    # The gate itself, against the fixture drafts installed in temp copies.
    data, products = held_drafts.held(ROOT, FIXTURE)
    if products:
        def leak(d):
            shutil.copytree(os.path.join(FIXTURE, "apps", products[0]), os.path.join(d, products[0]))
        tmp, dest, _ = temp_copy(leak, merge=False)
        r = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
        record(r.returncode == 1 and f"DRAFT LEAK apps/{products[0]}" in r.stdout,
               "check.py --release fails when a held draft product lands in apps/", r.stdout.strip()[-160:])
        shutil.rmtree(tmp)
    if data["lines"]:
        aid, line = next(iter(data["lines"].items()))
        text = line["outcome"]["line"] if line.get("outcome") else line["lessons"][0]["text"]
        tmp, dest, _ = temp_copy(merge=False)
        open(os.path.join(dest, "work/index.html"), "a").write(f"<p>{text}</p>")
        r = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
        record(r.returncode == 1 and "DRAFT LEAK work/index.html" in r.stdout,
               "check.py --release fails when held draft text lands in a published page", r.stdout.strip()[-160:])
        shutil.rmtree(tmp)
    tmp, dest, r = temp_copy()
    # Every draft product in the merged copy: the ones held here, plus any already in apps/
    # (in the preview copy release.py tests, they were merged before this suite ran).
    draft_ids = sorted(a["id"] for a in load_all(dest) if a.get("draft"))
    marked = [i for i in draft_ids if "draft-banner" in open(os.path.join(dest, "apps", i, "index.html")).read()]
    record(r.returncode == 0 and set(products) <= set(draft_ids) and marked == draft_ids and not os.path.exists(os.path.join(dest, held_drafts.DRAFTS)),
           "the preview merges every held draft product, each with its Draft banner", f"{marked} {r.stderr[-120:]}")
    shutil.rmtree(tmp)
    # Only where apps/ is the release build (in release.py's preview copy the drafts are already in apps/).
    clean = not any(a.get("draft") or (a.get("outcome") or {}).get("draft") or any(x["draft"] for x in a["lessons"]) for a in load_all())
    tmp, dest, _ = temp_copy(merge=False) if clean else (None, None, None)
    steps = [] if not clean else [subprocess.run([sys.executable, "_scripts/drafts.py", "promote", i], cwd=dest, capture_output=True, text=True)
             for i in products + list(data["lines"])]
    if clean:
        steps.append(subprocess.run([sys.executable, "_scripts/render.py"], cwd=dest, capture_output=True, text=True))
        gate = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
        pages_ok = all(os.path.isfile(os.path.join(dest, "apps", p, "index.html")) for p in products)
        record(all(x.returncode == 0 for x in steps) and gate.returncode == 0 and "0 draft(s) held" in gate.stdout and pages_ok,
               "drafts.py promote on every held draft, then render.py, passes check.py --release",
               " ".join(x.stderr.strip()[-80:] for x in steps) + gate.stdout.strip()[-160:])
        shutil.rmtree(tmp)

    # Rename: the name lives in one field.
    old, new = "Samplenote", "Zephyrnote"
    tmp, dest, r = temp_copy(lambda d: edit_app(d, "samplenote", lambda a: a.update(name=new)))
    hits = []
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames[:] = [x for x in dirnames if x not in ("_tests", "_attic", "_docs")]
        for f in filenames:
            if os.path.splitext(f)[1] in (".html", ".xml", ".txt", ".json", ".py", ".js", ".css", ".md"):
                text = open(os.path.join(dirpath, f), encoding="utf-8", errors="replace").read()
                if re.search(rf"\b{old}\b", text):
                    hits.append(os.path.relpath(os.path.join(dirpath, f), dest))
    page = open(os.path.join(dest, "apps/samplenote/index.html")).read()
    record(r.returncode == 0 and not hits and page.count(new) >= 5,
           f"renaming {old} in app.json leaves the old name nowhere", ", ".join(hits) or r.stderr[-200:])
    shutil.rmtree(tmp)

    # Bad data fails the build.
    cases = {
        "two flagships": lambda d: (edit_app(d, "flowmoro", lambda a: a.update(flagship=True)),
                                    edit_app(d, "skywise", lambda a: a.update(flagship=True))),
        "bad cycle date": lambda d: edit_app(d, "samplenote", lambda a: a.update(cycle=dict(FIXTURE_CYCLE, start="Oct 5"))),
        "update before start": lambda d: edit_app(d, "samplenote", lambda a: a.update(cycle=dict(FIXTURE_CYCLE, start="2026-10-20"))),
        "unknown outcome label": lambda d: edit_app(d, "quorum", lambda a: a["outcome"].update(label="Dead")),
        "unknown field": lambda d: edit_app(d, "triply", lambda a: a.update(flagshp=True)),
        "archived flagship": lambda d: edit_app(d, "quorum", lambda a: a.update(flagship=True)),
        "a tint that is not #rrggbb": lambda d: edit_app(d, "samplenote", lambda a: a.update(tint="amber")),
        "an unreadable color": lambda d: edit_app(d, "triply", lambda a: a.update(color="teal")),
        # The adversarial review's repro values, then the rest of the schema they point at.
        "an id that injects attributes": lambda d: edit_app(d, "flowmoro", lambda a: a.update(id='x" autofocus onfocus=alert(1) x="')),
        "a home path that injects attributes": lambda d: edit_app(d, "flowmoro", lambda a: a["links"].update(home='home/" onmouseover=alert(1) x="')),
        "an id that is not its folder": lambda d: edit_app(d, "flowmoro", lambda a: a.update(id="skywise")),
        "a home path outside the folder": lambda d: edit_app(d, "flowmoro", lambda a: a["links"].update(home="../skywise/")),
        "an absolute home path": lambda d: edit_app(d, "flowmoro", lambda a: a["links"].update(home="/home/")),
        "a screenshot src outside the folder": lambda d: edit_app(d, "skywise", lambda a: a["screenshots"][0].update(src="../../index.html")),
        "a screenshot from with a quote": lambda d: edit_app(d, "skywise", lambda a: a["screenshots"][0].update({"from": 'a".webp'})),
        "an icon outside _src": lambda d: edit_app(d, "skywise", lambda a: a.update(icon="../../CNAME")),
        "a legal path outside the folder": lambda d: edit_app(d, "skywise", lambda a: a["legal"].update(privacy="../flowmoro/privacy/")),
        "a legal path that is a javascript URL": lambda d: edit_app(d, "skywise", lambda a: a["legal"].update(terms="javascript:alert(1)")),
        "an http store link": lambda d: edit_app(d, "skywise", lambda a: a["links"].update(appStore="http://apps.apple.com/app/id1")),
        "a javascript web link": lambda d: edit_app(d, "inboxhiiv", lambda a: a["links"].update(web="javascript:alert(1)")),
        "a writing link with a quote": lambda d: edit_app(d, "inboxhiiv", lambda a: a["links"].update(writing='https://example.com/" onclick="x')),
        "a store link without a host": lambda d: edit_app(d, "skywise", lambda a: a["links"].update(googlePlay="https:///x")),
        "an unknown screenshot shape": lambda d: edit_app(d, "skywise", lambda a: a["screenshots"][0].update(shape='phone" x="')),
        "an unknown kind": lambda d: edit_app(d, "skywise", lambda a: a.update(kind='app" x="')),
        "an unknown platform": lambda d: edit_app(d, "skywise", lambda a: a.update(platforms=["ios", "beos"])),
    }
    for name, edit in cases.items():
        tmp, dest, r = temp_copy(edit)
        record(r.returncode != 0 and "app.json problems" in (r.stderr + r.stdout), f"render.py rejects {name}", r.stderr.strip()[-120:])
        shutil.rmtree(tmp)

    # The review's repro values, straight through validate(): no build needed to see them rejected.
    sys.path.insert(0, os.path.join(ROOT, "_scripts"))
    import render   # noqa: E402
    base_app = json.load(open(os.path.join(ROOT, "apps/flowmoro/app.json")))
    for label, change in (("id", lambda a: a.update(id='x" autofocus onfocus=alert(1) x="')),
                          ("links.home", lambda a: a["links"].update(home='home/" onmouseover=alert(1) x="'))):
        a = json.loads(json.dumps(base_app))
        change(a)
        record(bool(render.validate(["flowmoro"], [a])), f"validate() rejects the review's {label} injection value")
    record(not render.validate(["flowmoro"], [base_app]), "validate() accepts the real Flowmoro data")

    # 404.html: not indexable at its direct URL, and no self-canonical.
    page = open(os.path.join(ROOT, "404.html")).read()
    record('<meta name="robots" content="noindex, follow">' in page and 'rel="canonical"' not in page,
           "404.html is noindex, follow with no canonical")

    # Files kept on purpose (outside links may use them): check.py fails if one goes missing.
    sys.path.insert(0, os.path.join(ROOT, "_scripts"))
    import check as site_check   # noqa: E402
    record(all(os.path.isfile(os.path.join(ROOT, f)) for f in site_check.RETAINED), "retained legacy files exist: " + ", ".join(site_check.RETAINED))
    tmp, dest, _ = temp_copy(merge=False)
    os.remove(os.path.join(dest, "assets/og-image.png"))
    r = subprocess.run([sys.executable, "_scripts/check.py"], cwd=dest, capture_output=True, text=True)
    record(r.returncode == 1 and "assets/og-image.png: missing, but it is kept on purpose" in r.stdout,
           "check.py fails when a retained legacy file is deleted", r.stdout.strip()[-160:])
    shutil.rmtree(tmp)

    # In a git checkout, the release gate fails on committed drafts and on a sitemap date older than a page commit.
    tmp, dest, _ = temp_copy(merge=False)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
               GIT_AUTHOR_DATE="2000-01-01T12:00:00", GIT_COMMITTER_DATE="2000-01-01T12:00:00")
    git = lambda *a: subprocess.run(["git", *a], cwd=dest, capture_output=True, text=True, env=env)
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    r = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
    record(r.returncode == 0 and "STALE" not in r.stdout and "committed to git" not in r.stdout,
           "check.py --release passes in a fresh git checkout of the tree", r.stdout.strip()[-160:])
    open(os.path.join(dest, "work/index.html"), "a").write("\n")
    env.update(GIT_COMMITTER_DATE="2099-01-01T12:00:00")
    git("add", "-A")
    git("add", "-f", ".drafts/drafts.json")
    git("commit", "-q", "-m", "later")
    r = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
    record(r.returncode == 1 and "STALE sitemap.xml: https://modrnmagic.app/work/" in r.stdout
           and "DRAFT LEAK .drafts/drafts.json: held draft content is committed to git" in r.stdout,
           "check.py --release fails on a stale sitemap date and on drafts committed to git", r.stdout.strip()[-200:])
    shutil.rmtree(tmp)

    # No drafts, release passes.
    def confirm_all(d):
        for i in json.load(open(os.path.join(d, "index.json"))):
            def clear(a):
                a.pop("draft", None)
                if a.get("outcome"):
                    a["outcome"]["draft"] = False
                for x in a["lessons"]:
                    x["draft"] = False
            edit_app(d, i, clear)
    tmp, dest, r = temp_copy(confirm_all)
    rel = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
    record(r.returncode == 0 and rel.returncode == 0, "with every draft confirmed, check.py --release passes", rel.stdout.strip()[-160:])
    # The gate reads the output too: a stray local-build page fails it even when the data is clean.
    work = os.path.join(dest, "work/index.html")
    open(work, "a").write('<span class="draft-mark">Draft</span>')
    rel = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
    record(rel.returncode == 1 and "DRAFT OUTPUT work/index.html" in rel.stdout,
           "check.py --release fails on a draft marker in published HTML", rel.stdout.strip()[-160:])
    shutil.rmtree(tmp)

    # The release build deletes draft products' pages, leaves no draft output, and is then not stale.
    # One product is made a draft here, so the deletion is tested even once the real drafts are gone.
    tmp, dest, r = temp_copy(lambda d: edit_app(d, ids[-1], lambda a: a.update(draft=True)))
    rel = subprocess.run([sys.executable, "_scripts/render.py", "--release"], cwd=dest, capture_output=True, text=True)
    gone = [i for i in ids if json.load(open(os.path.join(dest, "apps", i, "app.json"))).get("draft")
            and os.path.exists(os.path.join(dest, "apps", i, "index.html"))]
    again = subprocess.run([sys.executable, "_scripts/render.py", "--release", "--check"], cwd=dest, capture_output=True, text=True)
    gate = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=dest, capture_output=True, text=True)
    record(rel.returncode == 0 and not gone and not os.path.exists(os.path.join(dest, "apps", ids[-1], "index.html"))
           and again.returncode == 0 and "DRAFT OUTPUT" not in gate.stdout
           and " 0 published page(s) carry draft output" in gate.stdout,
           "render.py --release deletes draft pages and leaves no draft output", f"left {gone} {gate.stdout.strip()[-120:]}")
    shutil.rmtree(tmp)

    # A push cycle renders What's new, newest first, and each date link lands on its row.
    tmp, dest, r = temp_copy(lambda d: edit_app(d, "samplenote", lambda a: a.update(cycle=FIXTURE_CYCLE)))
    server, base = serve(dest)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(base + "/apps/samplenote/")
    dates = page.eval_on_selector_all(".updates .update", "els => els.map(e => e.id)")
    want = ["update-" + u["date"] for u in sorted(FIXTURE_CYCLE["updates"], key=lambda u: u["date"], reverse=True)]
    record(dates == want, "What's new lists updates newest first", str(dates))
    ok = True
    for d in want:
        page.locator(f'a[href="#{d}"]').click()
        settle(page)
        ring = page.evaluate(f"getComputedStyle(document.getElementById('{d}'), '::after').opacity")
        ok = ok and page.url.endswith("#" + d) and ring == "1"
    record(ok, "each What's new date links to its own row and rings it")
    page.close()
    server.shutdown()
    shutil.rmtree(tmp)


def link_key(page, c):
    # Shared chrome (nav, footer) is the same control on every page; product
    # content is keyed by page so each product's own links are covered.
    return ("link", c["name"], c["abs"].split("#")[0] if not c["href"].startswith("#") else page + c["href"])


REDIRECTS = {"/mvp.html": "/contact/"}   # meta-refresh pages: tested for where they land


def pointers():
    """Legal pages for products whose policy lives on their own domain: the page
    path, and the https URL it must point at (from app.json `legal`)."""
    out = {}
    for a in load_all():
        for key, folder in (("privacy", "privacy"), ("terms", "tos")):
            url = a["legal"].get(key) or ""
            if url.startswith("https://"):
                out[f"/apps/{a['id']}/{folder}/"] = url
    return out


def main():
    threading.Thread(target=watchdog, daemon=True).start()
    try:
        return run_all()
    except KeyboardInterrupt:
        print(f"TIMEOUT: stopped in section '{NOW['section']}' after {time.monotonic() - STARTED:.0f}s; "
              f"last check: {NOW['last']}; {sum(1 for r in results if r[0])} passed before it", flush=True)
        return 2


def run_all():
    server, base = serve()
    # Pointer pages refresh to another domain, so they are checked over HTTP below, not loaded.
    all_pages = [p for p in pages() if p not in REDIRECTS and p not in pointers()]
    seen = {}       # key -> page where first found
    tested = set()
    with sync_playwright() as pw:
        browser = getattr(pw, ENGINE).launch() if ENGINE != "webkit" else Recycled(pw.webkit, 40)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        off_site, errors = [], []
        page.on("request", lambda r: urlsplit(r.url).scheme in ("http", "https") and not r.url.startswith(base) and off_site.append(r.url))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))

        begin("page loads", 300)
        # Page-level checks and control inventory.
        inventory = []
        for path in all_pages:
            off_site.clear(); errors.clear()
            resp = page.goto(base + path, wait_until="load")
            settle(page)
            record(resp is not None and resp.ok, f"{path} loads", str(resp.status if resp else "no response"))
            record(not off_site, f"{path} third-party requests = 0", ", ".join(off_site))
            record(not errors, f"{path} no console errors", "; ".join(errors))
            for c in page.evaluate(COLLECT):
                key = link_key(path, c) if c["kind"] == "link" else (c["kind"], path, c["i"])
                if key not in seen:
                    seen[key] = (path, c)
            inventory.append(path)
        third_party = sum(1 for ok, n, _ in results if "third-party" in n and not ok)

        begin("narrow overflow", 180)
        # Narrow-screen overflow.
        narrow = browser.new_context(viewport={"width": 320, "height": 800})
        np_ = narrow.new_page()
        for path in all_pages:
            np_.goto(base + path)
            sw = np_.evaluate("document.documentElement.scrollWidth")
            record(sw <= 320, f"{path} no sideways scroll at 320px", f"scrollWidth {sw}")
        narrow.close()

        begin("touch targets", 180)
        # Nav links and the theme toggle meet the 44px touch floor at every width.
        for w in (320, 360, 390, 560, 768, 1024, 1440):
            ctx = browser.new_context(viewport={"width": w, "height": 800})
            tp = ctx.new_page()
            for path in ("/", "/work/", "/apps/flowmoro/", "/apps/flowmoro/privacy/"):
                tp.goto(base + path)
                small = tp.evaluate("""[...document.querySelectorAll('.nav-links a, .theme-toggle')].map(e => {
                    const r = e.getBoundingClientRect(); return [e.textContent.trim() || 'theme', r.width, r.height, r.right]; })
                    .filter(([n, w, h, right]) => w < 44 || h < 44 || right > innerWidth)""")
                record(not small, f"{path} nav targets are at least 44px and on screen at {w}px", str(small))
            ctx.close()

        begin("breadcrumbs", 60)
        # Breadcrumb links reach 24px tall (WCAG 2.5.8) from padding alone.
        for path in ("/apps/flowmoro/", "/apps/flowmoro/home/", "/apps/flowmoro/privacy/"):
            page.goto(base + path)
            crumbs = page.evaluate("[...document.querySelectorAll('.crumbs a')].map(a => a.getBoundingClientRect().height)")
            record(bool(crumbs) and min(crumbs) >= 24, f"{path} breadcrumb links are at least 24px tall", str(crumbs))

        begin("links", 600)
        # Links.
        for key, (path, c) in seen.items():
            if key[0] != "link":
                continue
            page.goto(base + path)
            loc = page.locator("a[href]").nth(c["i"])
            if not c["visible"]:
                record(False, f"link '{c['name']}' on {path} is visible", "hidden at 1440px")
                continue
            href = c["href"]
            target = urlsplit(c["abs"])
            internal = c["abs"].startswith(base)
            name = f"link '{c['name']}' ({href}) on {path}"
            if internal and href.startswith("#"):
                loc.click()
                settle(page)
                ok = page.evaluate("""h => { const el = document.getElementById(h.slice(1));
                    if (!el) return false; const r = el.getBoundingClientRect(); return location.hash === h && r.top < innerHeight && r.bottom > 0; }""", href)
                record(ok, name + " scrolls to its anchor")
            elif internal:
                with page.expect_navigation():
                    loc.click()
                resp_ok = page.evaluate("document.readyState") and True
                now = urlsplit(page.url)
                want = target.path
                same = now.path == want or now.path == want + "/" or (want.endswith("/") and now.path == want + "index.html")
                status = urllib.request.urlopen(page.url).status
                if target.fragment:
                    same = same and now.fragment == target.fragment
                record(same and status == 200 and resp_ok, name + " navigates", f"landed on {page.url} ({status})")
            else:
                page.evaluate("""() => { window.__clicked = null;
                    document.addEventListener('click', e => { const a = e.target.closest('a');
                      window.__clicked = {href: a && a.href, prevented: e.defaultPrevented}; e.preventDefault(); }, {once: true}); }""")
                loc.click()
                got = page.evaluate("window.__clicked")
                ok = bool(got) and got["href"] == c["abs"] and not got["prevented"]
                record(ok, name + " receives the click", str(got))
            tested.add(key)

        begin("theme toggle", 300)
        # Theme toggle, on every page template that has one (tested once per page).
        for key, (path, c) in seen.items():
            if key[0] != "toggle":
                continue
            page.goto(base + path)
            page.evaluate("localStorage.clear()")
            page.reload()
            before = page.evaluate("[getComputedStyle(document.body).backgroundColor, document.querySelector('.theme-toggle').getAttribute('aria-pressed')]")
            page.click(".theme-toggle")
            settle(page)
            after = page.evaluate("[getComputedStyle(document.body).backgroundColor, document.querySelector('.theme-toggle').getAttribute('aria-pressed'), document.documentElement.dataset.theme, localStorage.getItem('theme')]")
            ok = after[0] != before[0] and after[1] != before[1] and after[2] == after[3] == "dark"
            page.reload()
            kept = page.evaluate("document.documentElement.dataset.theme") == "dark"
            page.click(".theme-toggle")
            settle(page)
            back = page.evaluate("document.documentElement.dataset.theme") == "light"
            record(ok and kept and back, f"theme toggle on {path} switches, persists, and switches back", str(after))
            tested.add(key)

        begin("faq", 180)
        # FAQ disclosures.
        for key, (path, c) in seen.items():
            if key[0] != "faq":
                continue
            page.goto(base + path)
            item = page.locator(".faq details").nth(c["i"])
            item.locator("summary").click()
            settle(page)
            opened = item.evaluate("d => d.open && getComputedStyle(d.querySelector('p')).opacity === '1'")
            item.locator("summary").click()
            settle(page)
            closed = item.evaluate("d => !d.open")
            record(opened and closed, f"FAQ '{c['name']}' on {path} opens and closes")
            tested.add(key)

        # A click while an answer is still closing reopens it (review item 3).
        faq_pages = sorted({path for key, (path, c) in seen.items() if key[0] == "faq"})
        for path in faq_pages[:2]:
            page.goto(base + path)
            item = page.locator(".faq details").first
            item.locator("summary").click()
            settle(page)
            # Close, put the close animation part way (10% of the time, about 0.6 opacity
            # with --ease-out), and reopen, all in one task: the
            # click lands mid-close however slow the machine is. (Waiting a few frames
            # instead let a loaded run finish the 140ms close first, then reopen from 0.)
            # Then sample the answer's opacity every frame: it must climb back from
            # where the close left it, never restart at 0.
            mid, dip = item.evaluate("""d => new Promise(r => { const s = d.querySelector('summary'), p = d.querySelector('p');
              s.click();
              const a = p.getAnimations()[0], mid = d.classList.contains('closing') && !!a && d.open;
              if (a) a.currentTime = a.effect.getComputedTiming().duration * .1;
              const from = +getComputedStyle(p).opacity;
              s.click(); let low = 1, n = 0;
              (function tick() { low = Math.min(low, +getComputedStyle(p).opacity); if (++n < 20) requestAnimationFrame(tick); else r([mid, [from, low]]); })(); })""")
            settle(page)
            state = item.evaluate("d => [d.open, d.classList.contains('closing'), getComputedStyle(d.querySelector('p')).opacity]")
            item.locator("summary").click()
            settle(page)
            closed = item.evaluate("d => !d.open")
            record(mid and .2 < dip[0] < .9 and state == [True, False, "1"] and closed and dip[1] >= dip[0] - .05,
                   f"FAQ on {path}: a click during the close reverses it from where it is, the next click closes it",
                   f"mid {mid} opacity at click {dip[0]:.2f}, lowest after {dip[1]:.2f}, state {state} closed {closed}")

        begin("rails", 180)
        # Rails, at phone width where they overflow.
        phone = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=False)
        rp = phone.new_page()
        for key, (path, c) in seen.items():
            if key[0] != "rail":
                continue
            rp.goto(base + path, wait_until="load")
            wrap = rp.locator(".rail-wrap").nth(c["i"])
            ctl = wrap.locator(".rail-ctl")
            if not ctl.is_visible():
                count = wrap.locator("figure").count()
                fits = wrap.locator(".rail").evaluate("r => r.scrollWidth <= r.clientWidth + 2")
                record(fits, f"rail on {path} hides controls only when it fits (a lone shot too: nothing runs off the page)", f"{count} shots")
                tested.add(key)
                continue
            n = wrap.locator("figure").count()
            prev, nxt = ctl.locator('[data-step="-1"]'), ctl.locator('[data-step="1"]')
            start = rp.evaluate("() => 0")
            ok = prev.get_attribute("aria-disabled") == "true" and ctl.locator(".rail-now").inner_text() == "1"
            nxt.click(); scroll_settle(wrap.locator('.rail')); settle(rp)
            moved = wrap.locator(".rail").evaluate("r => r.scrollLeft") > start
            ok = ok and moved and ctl.locator(".rail-now").inner_text() == "2" and prev.get_attribute("aria-disabled") == "false"
            nxt.focus(); rp.keyboard.press("Enter"); scroll_settle(wrap.locator('.rail')); settle(rp)
            ok_kb = ctl.locator(".rail-now").inner_text() == str(min(3, n))
            for _ in range(n):
                if nxt.get_attribute("aria-disabled") == "true":
                    break
                nxt.click(); scroll_settle(wrap.locator('.rail')); settle(rp)
            at_end = nxt.get_attribute("aria-disabled") == "true" and ctl.locator(".rail-now").inner_text() == str(n)
            prev.click(); scroll_settle(wrap.locator('.rail')); settle(rp)
            back = int(ctl.locator(".rail-now").inner_text()) < n
            record(ok and ok_kb and at_end and back, f"rail '{c['name']}' on {path}: next, keyboard, end, previous",
                   f"start/next {ok} keyboard {ok_kb} end {at_end} back {back}")
            tested.add(key)
        phone.close()
        # Wide screens: where a rail still overflows, previous steps back from the end.
        # (The shot before the last can sit past the furthest scroll; stepping back by
        # index once left the rail where it was.)
        for w in (800, 1440):
            wide = browser.new_context(viewport={"width": w, "height": 900})
            wp = wide.new_page()
            for key, (path, c) in seen.items():
                if key[0] != "rail":
                    continue
                wp.goto(base + path, wait_until="load")
                wrap = wp.locator(".rail-wrap").nth(c["i"])
                ctl = wrap.locator(".rail-ctl")
                if not ctl.is_visible():
                    fits = wrap.locator(".rail").evaluate("r => r.scrollWidth <= r.clientWidth + 2")
                    record(fits, f"rail '{c['name']}' on {path} at {w}px: no buttons, and nothing runs off the page")
                    continue
                rail = wrap.locator(".rail")
                nxt, prev = ctl.locator('[data-step="1"]'), ctl.locator('[data-step="-1"]')
                for _ in range(wrap.locator("figure").count()):
                    if nxt.get_attribute("aria-disabled") == "true":
                        break
                    nxt.click(); scroll_settle(rail); settle(wp)
                end = rail.evaluate("r => r.scrollLeft")
                at_end = nxt.get_attribute("aria-disabled") == "true"
                prev.click(); scroll_settle(rail); settle(wp)
                back = rail.evaluate("r => r.scrollLeft")
                record(at_end and back < end - 2,
                       f"rail '{c['name']}' on {path} at {w}px: previous steps back from the end", f"{end} -> {back}")
            wide.close()

        begin("skip link", 60)
        # Skip link on one page per template.
        for path in ("/", "/apps/flowmoro/", "/apps/flowmoro/privacy/", "/apps/flowmoro/home/"):
            page.goto(base + path)
            page.keyboard.press(TAB)
            settle(page)
            shown = page.evaluate("[document.activeElement.className, document.activeElement.getBoundingClientRect().top]")
            page.keyboard.press("Enter")
            settle(page)
            record(shown[0] == "skip" and shown[1] >= 0 and page.url.endswith("#main"),
                   f"skip link on {path} shows on Tab and jumps to #main", f"{shown} {page.url}")

        begin("reduced motion", 60)
        # Reduced motion: transitions off, FAQ still works.
        still = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        sp = still.new_page()
        sp.goto(base + "/apps/flowmoro/")
        dur = sp.evaluate("getComputedStyle(document.querySelector('.btn')).transitionDuration")
        sp.locator(".faq summary").first.click()
        sp.locator(".faq summary").first.click()
        closed = sp.evaluate("!document.querySelector('.faq details').open")
        record(all(float(x.strip()[:-1] or 0) == 0 for x in dur.split(",")) and closed, "reduced motion turns transitions off and FAQ still toggles", dur)
        still.close()

        for src, dest in REDIRECTS.items():
            page.goto(base + src)
            page.wait_for_url(base + dest, timeout=5000)
            record(True, f"{src} redirects to {dest}")

        begin("footer link", 60)
        # The vision doc's open item: footer "Flowmoro privacy" from home, real mouse click.
        page.goto(base + "/")
        link = page.get_by_role("link", name="Flowmoro privacy")
        link.scroll_into_view_if_needed()
        with page.expect_navigation():
            link.click()
        h1 = page.locator("h1").inner_text()
        record(urlsplit(page.url).path == "/apps/flowmoro/privacy/" and "privacy" in h1.lower(),
               "footer 'Flowmoro privacy' link navigates from home", f"{page.url} h1={h1!r}")
        begin("data and drafts", 600)
        data_tests(browser)
        begin("filters", 300)
        filter_tests(browser, base, seen, tested)
        begin("flagship", 600)
        flagship_tests(browser)
        begin("contrast", 900)
        for path in ("/", "/work/") + tinted_pages():
            contrast_check(browser, base, path, path)
        begin("bento", 1500)
        bento_tests(browser)
        browser.close()
    begin("legal URLs", 120)

    # Legal URLs answer in every form a store listing might use.
    for dirpath, _, filenames in os.walk(os.path.join(ROOT, "apps")):
        rel = "/" + os.path.relpath(dirpath, ROOT).replace(os.sep, "/")
        if not any(seg in rel for seg in ("/privacy", "/tos")) or "index.html" not in filenames:
            continue
        url = pointers().get(rel + "/")
        for form in (rel, rel + "/", rel + "/index.html") + tuple(f"{rel}/{f}" for f in filenames if f.endswith(".md")):
            try:
                r = urllib.request.urlopen(base + form)
                body = r.read().decode("utf-8", "replace")
                ok = r.status == 200 and ("<h1>" in body if not form.endswith(".md") else True)
                record(ok, f"legal URL {form} answers", str(r.status))
                if url and form.endswith(".md"):
                    record(f"<{url}>" in body, f"legal URL {form} points at {url}", body[:120])
                elif url:
                    want = (f'<link rel="canonical" href="{url}">', f'<meta http-equiv="refresh" content="0; url={url}">',
                            '<meta name="robots" content="noindex, follow">', f'class="btn btn-primary" href="{url}"')
                    missing = [w for w in want if w not in body]
                    record(not missing, f"legal URL {form} points at {url} (canonical, refresh, visible link, noindex)", str(missing))
            except Exception as err:   # noqa: BLE001
                record(False, f"legal URL {form} answers", str(err))
    server.shutdown()

    failed = [r for r in results if not r[0]]
    total = len(seen)
    covered = len(tested)
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    print(f"third-party requests: {third_party} page(s) with any")
    print(f"interaction coverage: {covered}/{total} unique controls ({100 * covered // max(total, 1)}%)")
    by_kind = {}
    for k in seen:
        by_kind.setdefault(k[0], [0, 0])
        by_kind[k[0]][0] += k in tested
        by_kind[k[0]][1] += 1
    print("  " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in sorted(by_kind.items())))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
