#!/usr/bin/env python3
"""Click tests for the published site. Dev only; `_tests/` is not published.

    python3 _tests/run.py            # all pages, exit 1 on any failure
    python3 _tests/run.py -v         # also print every passing check

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
- /work/ filters filter by mouse, keyboard, and with JavaScript off, keep
  aria-current and the live count right, never scroll, and skip the view
  transition under reduced motion; numbers lines match the data
- home shows a flagship panel only when one is flagged (checked with nothing
  flagged and with each push-cycle product flagged, in temp copies), and the
  experiments strip holds the three newest experiments
- in a temporary copy of the repo: renaming Ramble in its one name field
  leaves the old name nowhere; a push cycle renders What's new with working
  update links; bad product data makes render.py fail; check.py --release
  fails while drafts remain

It ends with interaction coverage: tested unique controls over all unique
controls found.
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
import urllib.request
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERBOSE = "-v" in sys.argv

results = []   # (ok, name, detail)


def record(ok, name, detail=""):
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


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


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


def temp_copy(edit=None):
    """Copy the repo (without .git) to a temp folder, apply edit(apps_dir), render it there."""
    tmp = tempfile.mkdtemp(prefix="modrn-site-test-")
    dest = os.path.join(tmp, "site")
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "_attic"))
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
PUSH_CYCLE = ("ramble", "nookly", "inboxhiiv", "hypebridge")


def load_all(root=ROOT):
    ids = json.load(open(os.path.join(root, "apps/index.json")))
    return [json.load(open(os.path.join(root, "apps", i, "app.json"))) for i in ids]


def expected_numbers(apps):
    """Recomputed here from app.json, independent of render.py."""
    n = {k: sum(1 for a in apps if a["status"] == k) for k in ("live", "lab", "archived")}
    starts = [v for a in apps for v in (a["dates"].get("started"), a["dates"].get("shipped"), a["dates"].get("updated")) if v]
    exp = f"{n['lab']} experiment" + ("s" if n["lab"] != 1 else "")
    return f"{len(apps)} products since {min(starts)[:4]}: {n['live']} live, {exp}, and {n['archived']} archived."


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
        page.wait_for_timeout(600)   # the view transition (--d-base) plus margin
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
    # Keyboard: chips in reading order, Enter activates, focus stays on the chip.
    page.goto(base + "/work/")
    page.locator(".fchip").first.focus()
    order = [page.evaluate("document.activeElement.dataset.filter")]
    for _ in range(len(chips) - 1):
        page.keyboard.press("Tab")
        order.append(page.evaluate("document.activeElement.dataset.filter"))
    page.keyboard.press("Enter")
    page.wait_for_timeout(450)
    after = page.evaluate("[document.activeElement.dataset.filter, location.hash]")
    record(order == chips and after == [chips[-1], "#" + chips[-1]], "/work/ filters: Tab order follows the chips, Enter filters, focus stays", f"{order} {after}")
    page.close()
    # JavaScript off: :target alone filters, and deep links work.
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, java_script_enabled=False)
    p2 = ctx.new_page()
    p2.goto(base + "/work/#archived")
    vis = p2.eval_on_selector_all(".work-item", "els => els.filter(e => getComputedStyle(e).display !== 'none').length")
    p2.locator('.fchip[data-filter="live"]').click()
    vis_live = p2.eval_on_selector_all(".work-item", "els => els.filter(e => getComputedStyle(e).display !== 'none').map(e => e.dataset.status)")
    want_arch = sum(1 for a in apps if a["status"] == "archived")
    record(vis == want_arch and vis_live and set(vis_live) == {"live"}, "/work/ filters work with JavaScript off, deep links included", f"{vis} {vis_live}")
    ctx.close()
    # Reduced motion: no view transition and no item animation, still filters.
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    p3 = ctx.new_page()
    p3.goto(base + "/work/")
    p3.evaluate("window.__vt = 0; const o = document.startViewTransition && document.startViewTransition.bind(document); if (o) document.startViewTransition = cb => { window.__vt++; return o(cb); }; 0")
    p3.locator('.fchip[data-filter="experiments"]').click()
    p3.wait_for_timeout(200)
    res = p3.evaluate("[window.__vt, [...document.querySelectorAll('.work-item')].filter(e => getComputedStyle(e).display !== 'none').length, document.getAnimations().filter(a => a.playState === 'running').length]")
    want = sum(1 for a in apps if a["status"] == "lab")
    record(res == [0, want, 0], "/work/ under reduced motion: no view transition or animation, still filters", str(res))
    ctx.close()
    # With motion, a filter change runs one view transition.
    p4 = browser.new_page(viewport={"width": 1440, "height": 900})
    p4.goto(base + "/work/")
    p4.evaluate("window.__vt = 0; const o = document.startViewTransition.bind(document); document.startViewTransition = cb => { window.__vt++; return o(cb); }; 0")
    p4.locator('.fchip[data-filter="archived"]').click()
    p4.wait_for_timeout(450)
    record(p4.evaluate("window.__vt") == 1, "/work/ filter change runs one view transition")
    p4.close()


def flagship_tests(browser):
    apps = {a["id"]: a for a in load_all()}
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
        page.keyboard.press("Tab")
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
    tmp, dest, r = temp_copy(lambda d: edit_app(d, "ramble", lambda a: a.update(flagship=True)))
    rel = subprocess.run([sys.executable, "_scripts/render.py", "--release"], cwd=dest, capture_output=True, text=True)
    work = open(os.path.join(dest, "work/index.html")).read()
    home = open(os.path.join(dest, "index.html")).read()
    drafts = [a for a in apps.values() if a.get("draft")]
    leak = [a["id"] for a in drafts if f"/apps/{a['id']}/" in work or f"/apps/{a['id']}/" in home]
    record(rel.returncode == 0 and not leak and 'class="draft-mark"' not in work and 'class="flagship' not in home,
           "release build: no drafts on /work/ or home, and a draft flagship falls back", ", ".join(leak) or rel.stderr[-120:])
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


def bento_check(browser, base, label, apps):
    """Home bento: one cell per live, listed, non-flagship product, no grid holes at any width, and the live count matches."""
    listed_apps = [a for a in apps if not a.get("draft")]
    flag = next((a for a in listed_apps if a.get("flagship")), None)
    want = [a["id"] for a in listed_apps if a["status"] == "live" and a is not flag]
    for w in (1440, 800, 390):
        ctx = browser.new_context(viewport={"width": w, "height": 900}, reduced_motion="reduce")
        page = ctx.new_page()
        page.goto(base + "/")
        cells = page.eval_on_selector_all(".bento .cell", "els => els.map(e => e.dataset.app)")
        holes = page.evaluate(BENTO_HOLES)
        live_n = int(re.search(r"(\d+) live", page.locator(".hero .numbers").inner_text()).group(1))
        shown_live = len(cells) + (1 if flag and flag["status"] == "live" else 0)
        record(cells == want and not holes and live_n == shown_live,
               f"bento {label} at {w}px: a cell per live product, no holes, '{live_n} live' matches",
               f"cells {cells} want {want} holes {holes}")
        ctx.close()


def bento_tests(browser):
    apps = load_all()
    server, base = serve()
    bento_check(browser, base, "nothing flagged", apps)
    server.shutdown()
    cases = [(f"{a['id']} flagged", lambda d, aid=a["id"]: edit_app(d, aid, lambda x: x.update(flagship=True)))
             for a in apps if a["status"] == "live" and not a.get("draft")]
    drafts = [a["id"] for a in apps if a.get("draft") and a["status"] == "live"]
    for aid in drafts:
        cases.append((f"{aid} draft cleared", lambda d, aid=aid: edit_app(d, aid, lambda x: x.pop("draft"))))
        cases.append((f"{aid} draft cleared and flagged", lambda d, aid=aid: edit_app(d, aid, lambda x: (x.pop("draft"), x.update(flagship=True)))))
    for label, edit in cases:
        tmp, dest, r = temp_copy(edit)
        if r.returncode:
            record(False, f"bento {label}: renders", r.stderr[-200:])
            continue
        server, base = serve(dest)
        bento_check(browser, base, label, load_all(dest))
        contrast_check(browser, base, "/", f"home with {label}")
        server.shutdown()
        shutil.rmtree(tmp)


# Text on product surfaces must reach WCAG AA (4.5:1) against what is actually
# painted behind it: glass, tint gradient, and wash. The text is hidden, the
# page is captured, and each text box is measured against its own pixels.
CARD_TEXT = ".cell, .card, .w-card, .flagship"
TEXT_SEL = ".meta, .status, .chip, .one, .w-outcome, .draft-mark, .name, .fl-news"


def luminance(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb[:3])
    return .2126 * r + .7152 * g + .0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + .05) / (lb + .05)


def contrast_check(browser, base, path, label, themes=("light", "dark")):
    from io import BytesIO
    from PIL import Image
    for theme in themes:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme=theme, reduced_motion="reduce")
        page = ctx.new_page()
        page.goto(base + path, wait_until="networkidle")
        page.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
        page.wait_for_function("[...document.images].every(i => i.complete)")
        page.wait_for_timeout(100)
        boxes = page.evaluate("""([cards, sel]) => [...document.querySelectorAll(cards)].flatMap(card =>
          [...card.querySelectorAll(sel)].filter(el => el.getBoundingClientRect().width > 0).map(el => {
            const r = el.getBoundingClientRect(); const c = getComputedStyle(el).color.match(/[\\d.]+/g).map(Number);
            return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, color: c,
                    what: (card.querySelector('.name') || card).textContent.trim().slice(0, 20) + ' ' + el.className + ' ' + el.textContent.trim().slice(0, 16)};
          }))""", [CARD_TEXT, TEXT_SEL])
        page.add_style_tag(content="* { color: transparent !important; text-shadow: none !important; -webkit-text-fill-color: transparent !important; border-color: transparent !important; }")
        page.wait_for_timeout(50)
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
        record(not leaks and 'content="noindex"' in page and "draft-banner" in page,
               f"draft {i}: own noindex page with a banner, not on shared pages", ", ".join(leaks))

    # Drafts block a release.
    r = subprocess.run([sys.executable, "_scripts/check.py", "--release"], cwd=ROOT, capture_output=True, text=True)
    pending = any((json.load(open(os.path.join(ROOT, "apps", i, "app.json"))).get("draft")) for i in ids)
    record((r.returncode == 1) == pending, "check.py --release fails while drafts remain", r.stdout.strip().splitlines()[-1])

    # Rename: the name lives in one field.
    old, new = "Ramble", "Zephyrnote"
    tmp, dest, r = temp_copy(lambda d: edit_app(d, "ramble", lambda a: a.update(name=new)))
    hits = []
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames[:] = [x for x in dirnames if x not in ("_tests", "_attic", "_docs")]
        for f in filenames:
            if os.path.splitext(f)[1] in (".html", ".xml", ".txt", ".json", ".py", ".js", ".css", ".md"):
                text = open(os.path.join(dirpath, f), encoding="utf-8", errors="replace").read()
                if re.search(rf"\b{old}\b", text):
                    hits.append(os.path.relpath(os.path.join(dirpath, f), dest))
    page = open(os.path.join(dest, "apps/ramble/index.html")).read()
    record(r.returncode == 0 and not hits and page.count(new) >= 5,
           f"renaming {old} in app.json leaves the old name nowhere", ", ".join(hits) or r.stderr[-200:])
    shutil.rmtree(tmp)

    # Bad data fails the build.
    cases = {
        "two flagships": lambda d: (edit_app(d, "flowmoro", lambda a: a.update(flagship=True)),
                                    edit_app(d, "skywise", lambda a: a.update(flagship=True))),
        "bad cycle date": lambda d: edit_app(d, "ramble", lambda a: a.update(cycle=dict(FIXTURE_CYCLE, start="Oct 5"))),
        "update before start": lambda d: edit_app(d, "ramble", lambda a: a.update(cycle=dict(FIXTURE_CYCLE, start="2026-10-20"))),
        "unknown outcome label": lambda d: edit_app(d, "quorum", lambda a: a["outcome"].update(label="Dead")),
        "unknown field": lambda d: edit_app(d, "triply", lambda a: a.update(flagshp=True)),
        "archived flagship": lambda d: edit_app(d, "quorum", lambda a: a.update(flagship=True)),
    }
    for name, edit in cases.items():
        tmp, dest, r = temp_copy(edit)
        record(r.returncode != 0 and "app.json problems" in (r.stderr + r.stdout), f"render.py rejects {name}", r.stderr.strip()[-120:])
        shutil.rmtree(tmp)

    # No drafts, release passes.
    def confirm_all(d):
        for i in ids:
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
    shutil.rmtree(tmp)

    # A push cycle renders What's new, newest first, and each date link lands on its row.
    tmp, dest, r = temp_copy(lambda d: edit_app(d, "ramble", lambda a: a.update(cycle=FIXTURE_CYCLE)))
    server, base = serve(dest)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(base + "/apps/ramble/")
    dates = page.eval_on_selector_all(".updates .update", "els => els.map(e => e.id)")
    want = ["update-" + u["date"] for u in sorted(FIXTURE_CYCLE["updates"], key=lambda u: u["date"], reverse=True)]
    record(dates == want, "What's new lists updates newest first", str(dates))
    ok = True
    for d in want:
        page.locator(f'a[href="#{d}"]').click()
        page.wait_for_timeout(350)
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


def main():
    server, base = serve()
    all_pages = [p for p in pages() if p not in REDIRECTS]
    seen = {}       # key -> page where first found
    tested = set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        off_site, errors = [], []
        page.on("request", lambda r: urlsplit(r.url).scheme in ("http", "https") and not r.url.startswith(base) and off_site.append(r.url))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))

        # Page-level checks and control inventory.
        inventory = []
        for path in all_pages:
            off_site.clear(); errors.clear()
            resp = page.goto(base + path, wait_until="load")
            page.wait_for_timeout(150)
            record(resp is not None and resp.ok, f"{path} loads", str(resp.status if resp else "no response"))
            record(not off_site, f"{path} third-party requests = 0", ", ".join(off_site))
            record(not errors, f"{path} no console errors", "; ".join(errors))
            for c in page.evaluate(COLLECT):
                key = link_key(path, c) if c["kind"] == "link" else (c["kind"], path, c["i"])
                if key not in seen:
                    seen[key] = (path, c)
            inventory.append(path)
        third_party = sum(1 for ok, n, _ in results if "third-party" in n and not ok)

        # Narrow-screen overflow.
        narrow = browser.new_context(viewport={"width": 320, "height": 800})
        np_ = narrow.new_page()
        for path in all_pages:
            np_.goto(base + path)
            sw = np_.evaluate("document.documentElement.scrollWidth")
            record(sw <= 320, f"{path} no sideways scroll at 320px", f"scrollWidth {sw}")
        narrow.close()

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
                page.wait_for_timeout(200)
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

        # Theme toggle, on every page template that has one (tested once per page).
        for key, (path, c) in seen.items():
            if key[0] != "toggle":
                continue
            page.goto(base + path)
            page.evaluate("localStorage.clear()")
            page.reload()
            before = page.evaluate("[getComputedStyle(document.body).backgroundColor, document.querySelector('.theme-toggle').getAttribute('aria-pressed')]")
            page.click(".theme-toggle")
            page.wait_for_timeout(700)
            after = page.evaluate("[getComputedStyle(document.body).backgroundColor, document.querySelector('.theme-toggle').getAttribute('aria-pressed'), document.documentElement.dataset.theme, localStorage.getItem('theme')]")
            ok = after[0] != before[0] and after[1] != before[1] and after[2] == after[3] == "dark"
            page.reload()
            kept = page.evaluate("document.documentElement.dataset.theme") == "dark"
            page.click(".theme-toggle")
            page.wait_for_timeout(700)
            back = page.evaluate("document.documentElement.dataset.theme") == "light"
            record(ok and kept and back, f"theme toggle on {path} switches, persists, and switches back", str(after))
            tested.add(key)

        # FAQ disclosures.
        for key, (path, c) in seen.items():
            if key[0] != "faq":
                continue
            page.goto(base + path)
            item = page.locator(".faq details").nth(c["i"])
            item.locator("summary").click()
            page.wait_for_timeout(350)
            opened = item.evaluate("d => d.open && getComputedStyle(d.querySelector('p')).opacity === '1'")
            item.locator("summary").click()
            page.wait_for_timeout(450)
            closed = item.evaluate("d => !d.open")
            record(opened and closed, f"FAQ '{c['name']}' on {path} opens and closes")
            tested.add(key)

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
                record(fits, f"rail on {path} hides controls only when it fits", f"{count} shots")
                tested.add(key)
                continue
            n = wrap.locator("figure").count()
            prev, nxt = ctl.locator('[data-step="-1"]'), ctl.locator('[data-step="1"]')
            start = rp.evaluate("() => 0")
            ok = prev.get_attribute("aria-disabled") == "true" and ctl.locator(".rail-now").inner_text() == "1"
            nxt.click(); rp.wait_for_timeout(700)
            moved = wrap.locator(".rail").evaluate("r => r.scrollLeft") > start
            ok = ok and moved and ctl.locator(".rail-now").inner_text() == "2" and prev.get_attribute("aria-disabled") == "false"
            nxt.focus(); rp.keyboard.press("Enter"); rp.wait_for_timeout(700)
            ok_kb = ctl.locator(".rail-now").inner_text() == str(min(3, n))
            for _ in range(n):
                if nxt.get_attribute("aria-disabled") == "true":
                    break
                nxt.click(); rp.wait_for_timeout(600)
            at_end = nxt.get_attribute("aria-disabled") == "true" and ctl.locator(".rail-now").inner_text() == str(n)
            prev.click(); rp.wait_for_timeout(700)
            back = int(ctl.locator(".rail-now").inner_text()) < n
            record(ok and ok_kb and at_end and back, f"rail '{c['name']}' on {path}: next, keyboard, end, previous",
                   f"start/next {ok} keyboard {ok_kb} end {at_end} back {back}")
            tested.add(key)
        phone.close()

        # Skip link on one page per template.
        for path in ("/", "/apps/flowmoro/", "/apps/flowmoro/privacy/", "/apps/flowmoro/home/"):
            page.goto(base + path)
            page.keyboard.press("Tab")
            page.wait_for_timeout(300)
            shown = page.evaluate("[document.activeElement.className, document.activeElement.getBoundingClientRect().top]")
            page.keyboard.press("Enter")
            page.wait_for_timeout(100)
            record(shown[0] == "skip" and shown[1] >= 0 and page.url.endswith("#main"),
                   f"skip link on {path} shows on Tab and jumps to #main", f"{shown} {page.url}")

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

        # The vision doc's open item: footer "Flowmoro privacy" from home, real mouse click.
        page.goto(base + "/")
        link = page.get_by_role("link", name="Flowmoro privacy")
        link.scroll_into_view_if_needed()
        with page.expect_navigation():
            link.click()
        h1 = page.locator("h1").inner_text()
        record(urlsplit(page.url).path == "/apps/flowmoro/privacy/" and "privacy" in h1.lower(),
               "footer 'Flowmoro privacy' link navigates from home", f"{page.url} h1={h1!r}")
        data_tests(browser)
        filter_tests(browser, base, seen, tested)
        flagship_tests(browser)
        for path in ("/", "/work/"):
            contrast_check(browser, base, path, path)
        bento_tests(browser)
        browser.close()

    # Legal URLs answer in every form a store listing might use.
    for dirpath, _, filenames in os.walk(os.path.join(ROOT, "apps")):
        rel = "/" + os.path.relpath(dirpath, ROOT).replace(os.sep, "/")
        if not any(seg in rel for seg in ("/privacy", "/tos")) or "index.html" not in filenames:
            continue
        for form in (rel, rel + "/", rel + "/index.html") + tuple(f"{rel}/{f}" for f in filenames if f.endswith(".md")):
            try:
                r = urllib.request.urlopen(base + form)
                body = r.read().decode("utf-8", "replace")
                ok = r.status == 200 and ("<h1>" in body if not form.endswith(".md") else True)
                record(ok, f"legal URL {form} answers", str(r.status))
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
