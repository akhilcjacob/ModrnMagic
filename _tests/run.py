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

It ends with interaction coverage: tested unique controls over all unique
controls found.
"""
import functools
import http.server
import os
import socket
import sys
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


def serve():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


# Collect every visible interactive control on a page with a stable key.
COLLECT = """() => {
  const out = [];
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !el.closest('[hidden]'); };
  document.querySelectorAll('a[href]').forEach((a, i) => {
    if (a.classList.contains('skip')) return;
    out.push({kind: 'link', i, href: a.getAttribute('href'), abs: a.href,
              name: (a.getAttribute('aria-label') || a.textContent).trim().replace(/\\s+/g, ' ').slice(0, 60),
              visible: visible(a)});
  });
  document.querySelectorAll('.theme-toggle').forEach((b, i) => out.push({kind: 'toggle', i, name: 'theme', visible: visible(b)}));
  document.querySelectorAll('.faq summary').forEach((s, i) => out.push({kind: 'faq', i, name: s.textContent.trim(), visible: visible(s)}));
  document.querySelectorAll('.rail-wrap').forEach((w, i) => out.push({kind: 'rail', i, name: w.getAttribute('aria-label'), visible: true}));
  return out;
}"""


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
