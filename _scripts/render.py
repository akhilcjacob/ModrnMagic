#!/usr/bin/env python3
"""Render the static site from apps/index.json and apps/<id>/app.json.

Writes: index.html, apps/<id>/index.html, contact/index.html, mvp.html,
404.html, sitemap.xml, llms.txt, and the legal pages apps/<id>/privacy/,
apps/<id>/tos/, and apps/<id>/privacy/delete-account/ from their Markdown. Standard library only. The output is
committed, so GitHub Pages serves plain files with no build step.

    python3 _scripts/render.py          # write files
    python3 _scripts/render.py --check  # exit 1 if committed output is stale
    python3 _scripts/render.py --release  # the public build: no drafts anywhere,
                                          # and draft products' pages are deleted

The default build is the local one: drafts show on /work/ (marked) and on
their own pages. The release build leaves them out entirely.

Bump SITE_DATE when page content changes; it feeds sitemap lastmod.
"""
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://modrnmagic.app"
SITE_DATE = "2026-09-30"
EMAIL = "hello@modrnmagic.app"
ORG_ID = f"{SITE}/#org"
SITE_ID = f"{SITE}/#website"
PERSON_ID = "https://akhilcjacob.com/#akhil"   # same @id the personal site uses
FOUNDER = {
    "name": "Akhil Jacob",
    "url": "https://akhilcjacob.com/",
    "sameAs": [
        "https://akhilcjacob.com/",
        "https://engineering.akhilcjacob.com/",
        "https://github.com/akhilcjacob",
        "https://www.linkedin.com/in/akhilcjacob",
    ],
}
STATUS_LABEL = {"live": "Live", "lab": "Experiment", "archived": "Archived"}
GROUP_LABEL = {"live": "Live", "lab": "Experiments", "archived": "Archived"}   # /work/ filters
GROUP_ID = {"live": "live", "lab": "experiments", "archived": "archived"}
KIND_LABEL = {"app": "Apps", "game": "Games", "web": "Web", "tool": "Tools"}
KIND_ONE = {"app": "App", "game": "Game", "web": "Web", "tool": "Tool"}
RELEASE = "--release" in sys.argv
PLATFORM_LABEL = {"ios": "iPhone", "android": "Android", "web": "Web"}
OS_LABEL = {"ios": "iOS", "android": "Android", "web": "Web browser"}

e = html.escape


def icon(name, cls=""):
    with open(os.path.join(ROOT, "assets/icons", f"{name}.svg")) as f:
        svg = f.read().strip()
    attrs = ' aria-hidden="true" focusable="false"' + (f' class="{cls}"' if cls else "")
    return svg.replace("<svg ", f"<svg{attrs} ", 1)


OUTCOME_LABELS = ("Kept", "Paused", "Parked", "Archived")
NAME = "{name}"   # text fields say {name}, so a product's name lives only in its `name` field


def load_apps():
    """Every product in apps/index.json order, validated, with {name} filled in."""
    ids = json.load(open(os.path.join(ROOT, "apps/index.json")))
    apps = [json.load(open(os.path.join(ROOT, "apps", i, "app.json"))) for i in ids]
    problems = validate(ids, apps)
    if problems:
        raise SystemExit("app.json problems:\n  " + "\n  ".join(problems))
    apps = [fill(a, a["name"]) for a in apps]
    if RELEASE:   # the public build carries no unconfirmed text
        for a in apps:
            if a.get("outcome") and a["outcome"]["draft"]:
                a["outcome"] = None
            a["lessons"] = [x for x in a["lessons"] if not x["draft"]]
    return apps


def fill(value, name):
    if isinstance(value, str):
        return value.replace(NAME, name)
    if isinstance(value, list):
        return [fill(v, name) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, name) for k, v in value.items()}
    return value


def valid_date(value, day=False):
    for fmt in (("%Y-%m-%d",) if day else ("%Y-%m-%d", "%Y-%m")):
        try:
            dt.datetime.strptime(value, fmt)
            if len(value) == len(dt.datetime.now().strftime(fmt)):
                return True
        except (TypeError, ValueError):
            pass
    return False


def validate(ids, apps):
    """Schema checks for the fields render.py reads. Returns a list of problems."""
    template = json.load(open(os.path.join(ROOT, "_docs/app-template.json")))
    optional = {"draft", "price", "storeName", "tint", "stars"}
    known = set(template) | optional
    out = []
    for aid, a in zip(ids, apps):
        def bad(msg):
            out.append(f"apps/{aid}/app.json: {msg}")
        for key in known - set(a) - optional:
            bad(f"missing field `{key}`")
        for key in set(a) - known:
            bad(f"unknown field `{key}`")
        if a.get("id") != aid:
            bad("`id` must match the folder name")
        if a.get("status") not in STATUS_LABEL:
            bad(f"`status` must be one of {', '.join(STATUS_LABEL)}")
        if rgb(a.get("color")) is None:
            bad("`color` must be #rrggbb or rgb(r,g,b)")
        if "tint" in a and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(a["tint"])):
            bad("`tint` must be #rrggbb")
        if not isinstance(a.get("draft", False), bool):
            bad("`draft` must be true or false")
        if not isinstance(a.get("stars", False), bool):
            bad("`stars` must be true or false")
        elif a.get("stars") and rgb(a.get("color")) and not is_dark(a):
            bad("`stars` needs a near-black `color` (the night sky only shows on a dark cell)")
        if not isinstance(a.get("flagship"), bool):
            bad("`flagship` must be true or false")
        elif a["flagship"] and a.get("status") == "archived":
            bad("an archived product cannot be the flagship")
        o = a.get("outcome")
        if o is not None:
            if not isinstance(o, dict) or set(o) != {"label", "date", "line", "draft"}:
                bad("`outcome` must be null or {label, date, line, draft}")
            else:
                if o["label"] not in OUTCOME_LABELS:
                    bad(f"`outcome.label` must be one of {', '.join(OUTCOME_LABELS)}")
                if not valid_date(o["date"]):
                    bad("`outcome.date` must be YYYY-MM or YYYY-MM-DD")
                if not isinstance(o["line"], str) or not o["line"].strip():
                    bad("`outcome.line` must be one sentence")
                if not isinstance(o["draft"], bool):
                    bad("`outcome.draft` must be true or false")
        lessons = a.get("lessons")
        if not isinstance(lessons, list) or any(
                not isinstance(x, dict) or set(x) != {"text", "draft"} or not str(x["text"]).strip()
                or not isinstance(x["draft"], bool) for x in lessons):
            bad("`lessons` must be a list of {text, draft}")
        c = a.get("cycle")
        if c is not None:
            if not isinstance(c, dict) or set(c) != {"start", "end", "goal", "updates"}:
                bad("`cycle` must be null or {start, end, goal, updates}")
            else:
                if not (valid_date(c["start"], day=True) and valid_date(c["end"], day=True)) or c["start"] > c["end"]:
                    bad("`cycle.start` and `cycle.end` must be YYYY-MM-DD with start on or before end")
                if not isinstance(c["goal"], str) or not c["goal"].strip():
                    bad("`cycle.goal` must be one sentence")
                ups = c["updates"]
                if not isinstance(ups, list) or any(not isinstance(u, dict) or set(u) != {"date", "text"} for u in ups):
                    bad("`cycle.updates` must be a list of {date, text}")
                else:
                    dates = [u["date"] for u in ups]
                    if any(not valid_date(d, day=True) or d < c["start"] for d in dates):
                        bad("each `cycle.updates[].date` must be YYYY-MM-DD, on or after `cycle.start`")
                    if len(set(dates)) != len(dates):
                        bad("`cycle.updates` dates must be unique (each one is a link)")
    if sum(1 for a in apps if a.get("flagship") is True) > 1:
        out.append("apps/index.json: at most one product can set `flagship: true`")
    return out


def listed(apps):
    """Products shown on shared pages. Drafts get their own page only."""
    return [a for a in apps if not a.get("draft")]


def shown(apps):
    """Products this build renders at all: drafts only in the local build."""
    return [a for a in apps if not (RELEASE and a.get("draft"))]


def flagship(apps):
    """The one flagged product this build may show, or None."""
    return next((a for a in shown(apps) if a.get("flagship")), None)


def latest(app):
    d = app["dates"]
    return max(v for v in (d.get("updated"), d.get("ended"), d.get("shipped"), d.get("started"), "0000") if v)


def numbers(apps):
    """One line of counts, computed from the products given. Never typed."""
    count = {k: sum(1 for a in apps if a["status"] == k) for k in STATUS_LABEL}
    since = min((latest_start(a) for a in apps), default="")[:4]
    parts = [f"{count['live']} live", f"{count['lab']} experiment{'s' if count['lab'] != 1 else ''}", f"{count['archived']} archived"]
    return f"{len(apps)} product{'s' if len(apps) != 1 else ''} since {since}: " + ", ".join(parts[:-1]) + f", and {parts[-1]}."


def latest_start(app):
    d = app["dates"]
    return min(v for v in (d.get("started"), d.get("shipped"), d.get("updated"), "9999") if v)


def draft_mark():
    return '<span class="draft-mark" title="Draft for Akhil to confirm">Draft</span>'


def fmt_date(value):
    if not value:
        return None
    if len(value) == 7:
        return dt.datetime.strptime(value, "%Y-%m").strftime("%b %Y")
    d = dt.datetime.strptime(value, "%Y-%m-%d")
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def years(app):
    d = app["dates"]
    start = (d.get("started") or d.get("shipped") or "")[:4]
    end = (d.get("ended") or d.get("updated") or "")[:4]
    if start and end and start != end:
        return f"{start} to {end}"
    return start or end or ""


def page_url(app):
    return f"{SITE}/apps/{app['id']}/"


def rgb(color):
    """'#rrggbb' or 'rgb(r,g,b)' as three ints, or None."""
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", color or "")
    if m:
        return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", color or "")
    if m and all(int(x) <= 255 for x in m.groups()):
        return tuple(int(x) for x in m.groups())
    return None


def oklch(color):
    """OKLCH lightness and chroma of a color (Ottosson's OKLab)."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    r, g, b = map(lin, rgb(color))
    l = (.4122214708 * r + .5363325363 * g + .0514459929 * b) ** (1 / 3)
    m = (.2119034982 * r + .6806995451 * g + .1073969566 * b) ** (1 / 3)
    s = (.0883024619 * r + .2817188376 * g + .6299787005 * b) ** (1 / 3)
    lightness = .2104542553 * l + .7936177850 * m - .0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + .4505937099 * s
    bb = .0259040371 * l + .7827717662 * m - .8086757660 * s
    return lightness, (a * a + bb * bb) ** .5


def glow(app):
    """The color for a product's card gradient, or None for no gradient.

    `tint` wins. Otherwise the icon tile `color`, unless it is near neutral or
    near black: those mix into a grey haze and pull meta text under AA."""
    if app.get("tint"):
        return app["tint"]
    lightness, chroma = oklch(app["color"])
    return app["color"] if chroma >= .04 and .3 <= lightness <= .9 else None


def is_dark(app):
    return oklch(app["color"])[0] < .3


def tint_style(app):
    """Inline custom properties for a product surface: --tint (icon tile) and --glow (gradient)."""
    g = glow(app)
    return f"--tint:{app['color']};" + (f"--glow:{g};" if g else "")


def icon_html(app, size_cls="", vt=True):
    style = f"--tint:{app['color']};"
    if vt:
        style += f"view-transition-name:icon-{app['id']};"
    if app.get("icon"):
        return (f'<span class="icon {size_cls}" style="{style}">'
                f'<img src="/apps/{app["id"]}/media/icon-256.webp" alt="" width="256" height="256" loading="lazy" decoding="async"></span>')
    return f'<span class="icon mono {size_cls}" style="{style}" aria-hidden="true">{e(app["name"][0])}</span>'


def jsonld(obj):
    text = json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{text}\n</script>'


def org_node():
    return {
        "@type": "Organization",
        "@id": ORG_ID,
        "name": "Modrn Magic",
        "alternateName": "Modrn Magic LLC",
        "url": f"{SITE}/",
        "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/img/icon-512.png", "width": 512, "height": 512},
        "email": EMAIL,
        "description": "Modrn Magic is an independent product studio founded by Akhil Jacob. It designs, builds, and runs its own apps for iPhone, Android, and the web.",
        "founder": {"@id": PERSON_ID},
        "location": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": "San Diego", "addressRegion": "CA", "addressCountry": "US"}},
        "contactPoint": {"@type": "ContactPoint", "email": EMAIL, "contactType": "customer support"},
    }


def person_node():
    return {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": FOUNDER["name"],
        "url": FOUNDER["url"],
        "sameAs": FOUNDER["sameAs"],
        "jobTitle": "Founder",
        "worksFor": {"@id": ORG_ID},
    }


def app_node(app):
    mobile = any(p in app["platforms"] for p in ("ios", "android"))
    kind = "MobileApplication" if mobile and app["status"] == "live" else (
        "WebApplication" if app["platforms"] == ["web"] else "SoftwareApplication")
    if app.get("kind") == "game" and app["status"] == "live":
        kind = ["MobileApplication", "VideoGame"]
    links = app["links"]
    node = {
        "@type": kind,
        "@id": page_url(app) + "#app",
        "name": app["name"],
        "description": app["summary"],
        "url": page_url(app),
        "applicationCategory": app["category"],
        "operatingSystem": ", ".join(OS_LABEL[p] for p in app["platforms"]),
        "publisher": {"@id": ORG_ID},
        "creator": {"@id": PERSON_ID},
        "creativeWorkStatus": {"live": "Published", "lab": "Prototype", "archived": "Archived"}[app["status"]],
    }
    if app.get("storeName"):
        node["alternateName"] = app["storeName"]
    if app.get("genre"):
        node["genre"] = app["genre"]
    if app.get("icon"):
        node["image"] = f"{SITE}/apps/{app['id']}/media/icon-256.webp"
    if app.get("screenshots"):
        node["screenshot"] = [f"{SITE}/apps/{app['id']}/{s['src']}" for s in app["screenshots"]]
    if app["dates"].get("shipped"):
        node["datePublished"] = app["dates"]["shipped"]
    if app["dates"].get("updated") and len(app["dates"]["updated"]) == 10:
        node["dateModified"] = app["dates"]["updated"]
    same = [u for u in (links.get("appStore"), links.get("googlePlay"), links.get("web")) if u]
    if same and app["status"] == "live":
        node["sameAs"] = same
        node["installUrl"] = same[0]
    if app["status"] == "live" and links.get("appStore") and app.get("price"):
        node["offers"] = {
            "@type": "Offer",
            "price": app["price"]["appStore"],
            "priceCurrency": app["price"]["currency"],
            "url": links["appStore"],
            "availability": "https://schema.org/InStock",
            "seller": {"@id": ORG_ID},
        }
    if app.get("stack"):
        node["keywords"] = ", ".join(app["stack"])
    return node


def inline_css():
    """The stylesheet, minified, for inlining. One less render-blocking request."""
    css = open(os.path.join(ROOT, "assets/css/site.css")).read()
    css = css.replace('url("../fonts/', 'url("/assets/fonts/')
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,>])\s*", r"\1", css)
    return css.replace(";}", "}").strip()


def head(title, description, path, og_image, graph, noindex=False, extra=""):
    canonical = SITE + path
    canonical_tag = "" if noindex else f'<link rel="canonical" href="{canonical}">\n'
    robots = '<meta name="robots" content="noindex">' if noindex else '<meta name="robots" content="index, follow, max-image-preview:large">'
    og = SITE + og_image
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
{canonical_tag}{robots}
<meta name="author" content="Akhil Jacob">
<meta name="theme-color" content="#eef0f4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0c0d10" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Modrn Magic">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(title)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{og}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/assets/img/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
<link rel="manifest" href="/manifest.json">
<link rel="alternate" type="text/plain" href="/llms.txt" title="llms.txt">
<link rel="preload" href="/assets/fonts/figtree-var.woff2" as="font" type="font/woff2" crossorigin>
<style>{inline_css()}</style>
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
<script src="/assets/js/site.js" defer></script>
{extra}{jsonld({"@context": "https://schema.org", "@graph": graph})}
</head>
"""


def nav(current=""):
    def link(href, label, key):
        cur = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="nav glass">
  <a class="brand" href="/" aria-label="Modrn Magic home"><img src="/assets/img/mark-96.webp" alt="" width="30" height="30"><span>Modrn Magic</span></a>
  <nav class="nav-links" aria-label="Main">
    {link("/#products", "Products", "products")}
    {link("/work/", "Work", "work")}
    {link("/contact/", "Contact", "contact")}
  </nav>
  <button class="theme-toggle" type="button" aria-label="Dark mode" aria-pressed="false">{icon("moon", "i-moon")}{icon("sun", "i-sun")}</button>
</header>
"""


def footer(apps):
    live = [a for a in listed(apps) if a["status"] == "live"]
    items = "\n".join(f'<li><a href="/apps/{a["id"]}/">{e(a["name"])}</a></li>' for a in live)
    legal = "\n".join(f'<li><a href="/apps/{a["id"]}/privacy/">{e(a["name"])} privacy</a></li>'
                      for a in live if a["legal"].get("privacy"))
    return f"""<footer class="footer wrap">
  <div class="footer-grid">
    <div>
      <a class="brand" href="/"><img src="/assets/img/mark-96.webp" alt="" width="30" height="30" loading="lazy"><span>Modrn Magic</span></a>
      <p style="margin-top:var(--s-3);max-width:34ch">An independent product studio founded by <a href="https://akhilcjacob.com/">Akhil Jacob</a>.</p>
    </div>
    <div><h2>Products</h2><ul>{items}</ul></div>
    <div><h2>Studio</h2><ul>
      <li><a href="/work/">All work</a></li>
      <li><a href="/#about">About</a></li>
      <li><a href="/contact/">Contact</a></li>
      <li><a href="https://akhilcjacob.com/">Akhil's portfolio</a></li>
    </ul></div>
    <div><h2>Legal</h2><ul>{legal}</ul></div>
  </div>
  <div class="fine"><span>&copy; {SITE_DATE[:4]} Modrn Magic LLC</span><span><a href="mailto:{EMAIL}">{EMAIL}</a></span></div>
</footer>
"""


def store_buttons(app, home=True):
    links = app["links"]
    out = []
    if app["status"] != "live":
        return ""
    if links.get("appStore"):
        out.append(f'<a class="btn btn-primary" href="{e(links["appStore"])}" rel="noopener">{icon("apple-logo")}<span class="two"><span class="sub">Download on the</span>App Store</span></a>')
    if links.get("googlePlay"):
        cls = "btn-primary" if not out else "btn-glass glass"
        out.append(f'<a class="btn {cls}" href="{e(links["googlePlay"])}" rel="noopener">{icon("google-play-logo")}<span class="two"><span class="sub">Get it on</span>Google Play</span></a>')
    if links.get("web"):
        host = links["web"].split("//", 1)[1].rstrip("/")
        cls = "btn-primary" if not out else "btn-glass glass"
        out.append(f'<a class="btn {cls}" href="{e(links["web"])}" rel="noopener">{icon("globe")}Visit {e(host)}</a>')
    if home and links.get("home"):
        out.append(f'<a class="btn btn-glass glass" href="/apps/{app["id"]}/{links["home"]}">Product site</a>')
    return f'<div class="btns">{"".join(out)}</div>'


def rail_html(figs, label, count, cls=""):
    """A scroll-snap rail. site.js reveals the previous, next, and position
    controls when the rail overflows; without JS it is a plain scroll row."""
    return f"""<section class="rail-wrap" aria-label="{e(label)}">
<div class="rail{(' ' + cls) if cls else ''}" tabindex="0" aria-label="{e(label)}, scroll sideways">
{figs}
</div>
<div class="wrap rail-ctl" hidden>
  <button class="rail-btn" type="button" data-step="-1" aria-label="Previous screenshot">{icon("caret-left")}</button>
  <span class="rail-pos meta tnum" aria-live="polite"><span class="rail-now">1</span> of {count}</span>
  <button class="rail-btn" type="button" data-step="1" aria-label="Next screenshot">{icon("caret-right")}</button>
</div>
</section>"""


def chips(app):
    return "".join(f'<span class="chip">{PLATFORM_LABEL[p]}</span>' for p in app["platforms"])


def status_html(app, outcome=None):
    label = STATUS_LABEL[app["status"]]
    if outcome and outcome["label"] == label:
        label += f' {fmt_date(outcome["date"])}'
    return f'<span class="status status-{app["status"]}">{label}</span>'


# ---------------------------------------------------------------- home

def framed_shot(app):
    """The first tour shot of the product site: a framed, uncropped device. None without a product site."""
    path = os.path.join(ROOT, "apps", app["id"], "home/descriptions.json")
    if not (app["links"].get("home") and os.path.exists(path)):
        return None
    tour = json.load(open(path))["tour"]
    return tour[0] if tour else None


def flagship_html(app):
    """Full-width panel for the flagged product: name, one-liner, latest update, one call to action."""
    aid = app["id"]
    links = app["links"]
    if app["status"] == "live" and links.get("web"):
        host = links["web"].split("//", 1)[1].rstrip("/")
        cta = f'<a class="btn btn-primary" href="{e(links["web"])}" rel="noopener">{icon("globe")}Visit {e(host)}</a>'
    elif app["status"] == "live" and links.get("appStore"):
        cta = f'<a class="btn btn-primary" href="{e(links["appStore"])}" rel="noopener">{icon("apple-logo")}Get it on the App Store</a>'
    elif app["status"] == "live" and links.get("googlePlay"):
        cta = f'<a class="btn btn-primary" href="{e(links["googlePlay"])}" rel="noopener">{icon("google-play-logo")}Get it on Google Play</a>'
    else:
        cta = f'<a class="btn btn-primary" href="/apps/{aid}/">See {e(app["name"])}</a>'
    news = ""
    c = app.get("cycle")
    if c and c["updates"]:
        u = max(c["updates"], key=lambda x: x["date"])
        news = (f'<p class="fl-news"><a href="/apps/{aid}/#update-{u["date"]}"><span class="meta">What\'s new, '
                f'<time datetime="{u["date"]}">{fmt_date(u["date"])}</time></span> {e(u["text"])}</a></p>')
    art = ""
    framed = framed_shot(app)
    if framed:   # a whole device, never a marketing image that crops it
        art = (f'<div class="fl-art phone framed" aria-hidden="true"><img src="/apps/{aid}/home/{framed["src"]}" alt="" '
               f'width="{framed["w"]}" height="{framed["h"]}" loading="lazy" decoding="async"></div>')
    elif app["screenshots"]:
        s0 = app["screenshots"][0]
        art = (f'<div class="fl-art {s0["shape"]}" aria-hidden="true"><img src="/apps/{aid}/{s0["src"]}" alt="" '
               f'width="{s0["w"]}" height="{s0["h"]}" loading="lazy" decoding="async"></div>')
    return f"""<section class="flagship glass reveal{' has-art' if art else ''}" aria-labelledby="flagship-title" style="{tint_style(app)}">
  <div class="fl-copy">
    <p class="meta fl-eyebrow">Flagship{" " + draft_mark() if app.get("draft") else ""}</p>
    <div class="fl-head">{icon_html(app, vt=False)}<div><h2 class="h2" id="flagship-title"><a href="/apps/{aid}/">{e(app['name'])}</a></h2>{status_html(app, app.get("outcome"))}</div></div>
    <p class="lead">{e(app['oneliner'])}</p>
    {news}
    <div class="btns">{cta}</div>
  </div>
  {art}
</section>"""


def strip_card(app, i=0):
    """A compact product card for the experiments strip and /work/."""
    o = app.get("outcome")
    tag = f'<span class="chip outcome-tag">{e(o["label"])} {fmt_date(o["date"])}</span>' if o and o["label"] != STATUS_LABEL[app["status"]] else ""
    return f"""<a class="card glass reveal" style="--i:{i};{tint_style(app)}" href="/apps/{app['id']}/">
  <div class="card-top">{icon_html(app, vt=False)}<div><h3 class="name">{e(app['name'])}</h3><div class="card-status">{status_html(app, o)}{tag}{draft_mark() if app.get("draft") else ""}</div></div></div>
  <p class="one">{e(app['oneliner'])}</p>
  <div class="foot">{f'<span class="meta tnum">{years(app)}</span>' if years(app) else ""}{chips(app)}</div>
</a>"""


def bento_sizes(n, lead_art=True):
    """Cell sizes by position, so any number of cells tiles the grid with no hole.

    On the 6-column grid a lead cell is 3 wide and 2 tall, a half is 3 wide,
    and a wide is 6. Three or more cells: a lead, two halves beside it, then
    halves in pairs, and a lone last cell goes wide. The 2-column tablet grid
    maps lead and wide to 2 and half to 1, so the same pairs fill it too.
    A lead is two rows tall, so it needs art: when the first product has no
    screenshots, every cell is a half in pairs instead, with a lone last wide."""
    if n < 3 or not lead_art:
        return ["half"] * (n - n % 2) + ["wide"] * (n % 2)
    rest = n - 3
    return ["lead", "half", "half"] + ["half"] * (rest - rest % 2) + ["wide"] * (rest % 2)


def bento_cell(app, size, shot):
    """One home bento cell. The art comes from the product's own screenshots."""
    phones = [s for s in app["screenshots"] if s["shape"] == "phone"]
    wides = [s for s in app["screenshots"] if s["shape"] == "wide"]
    art = ""
    if size == "lead" and len(phones) >= 2:
        pair = (phones[0], phones[2] if len(phones) > 2 else phones[1])
        art = f'<div class="cell-shots pair">{"".join(shot(app, s) for s in pair)}</div>'
    elif size != "half" and wides:
        art = f'<div class="cell-shots">{shot(app, wides[0])}</div>'
    elif phones:
        art = f'<div class="peek-clip" aria-hidden="true"><div class="peek">{shot(app, phones[-1])}</div></div>'
    elif wides:   # a half: the top of the wide shot peeks in, clipped, so it never sets the row height
        art = f'<div class="peek-clip" aria-hidden="true"><div class="peek wide">{shot(app, wides[0])}</div></div>'
    cls = f"cell cell-{size} glass reveal" + (" dark" if is_dark(app) else "") + (" stars" if app.get("stars") else "") + (" has-peek" if "peek" in art else "")
    return f"""<a class="{cls}" href="/apps/{app['id']}/" data-app="{app['id']}" style="{tint_style(app)}">
  {icon("arrow-up-right", "arrow")}
  <div class="top">{icon_html(app)}<div><h3 class="name">{e(app['name'])}</h3>{status_html(app)}</div></div>
  <p class="one">{e(app['oneliner'])}</p>
  {art}
  <div class="foot">{chips(app)}</div>
</a>"""


def render_home(apps):
    flag = flagship(apps)
    apps = listed(apps)
    live = [a for a in apps if a["status"] == "live"]
    experiments = sorted((a for a in apps if a["status"] == "lab" and a is not flag and (not flag or a["id"] != flag["id"])),
                         key=latest, reverse=True)[:3]

    def shot(app, s, eager=False):
        load = 'decoding="async"' if eager else 'loading="lazy" decoding="async"'
        return (f'<img src="/apps/{app["id"]}/{s["src"]}" alt="{e(s["alt"])}" '
                f'width="{s["w"]}" height="{s["h"]}" {load}>')

    # The flagship gets the panel above, so it leaves the bento. Every other
    # live product gets a cell, in apps/index.json order.
    bento_apps = [a for a in live if not (flag and flag["id"] == a["id"])]
    sizes = bento_sizes(len(bento_apps), bool(bento_apps and bento_apps[0]["screenshots"]))
    bento = "\n".join(bento_cell(a, size, shot) for a, size in zip(bento_apps, sizes))
    strip = "\n".join(strip_card(a, i) for i, a in enumerate(experiments))

    names = [a["name"] for a in live]
    makes = (names[0] if len(names) == 1 else " and ".join(names) if len(names) == 2
             else ", ".join(names[:-1]) + f", and {names[-1]}" if names else "apps")
    description = f"Modrn Magic is an independent product studio founded by Akhil Jacob. It makes {makes} for iPhone, Android, and the web."

    graph = [
        org_node(),
        person_node(),
        {"@type": "WebSite", "@id": SITE_ID, "url": f"{SITE}/", "name": "Modrn Magic", "publisher": {"@id": ORG_ID}, "inLanguage": "en-US"},
        {"@type": "WebPage", "@id": f"{SITE}/#page", "url": f"{SITE}/", "name": "Modrn Magic", "isPartOf": {"@id": SITE_ID},
         "about": {"@id": ORG_ID}, "description": description, "inLanguage": "en-US",
         "primaryImageOfPage": f"{SITE}/assets/og/home.jpg"},
        {"@type": "ItemList", "name": "Modrn Magic products", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": page_url(a), "name": a["name"]} for i, a in enumerate(apps)]},
    ]

    # Hero: one phone shot from each of the first three live products that have one.
    phones = [(a, [s for s in a["screenshots"] if s["shape"] == "phone"]) for a in live]
    trio = [(a, ps[1] if len(ps) > 1 else ps[0]) for a, ps in phones if ps][:3]
    hero_art = ""
    if trio:
        places = ("p0", "p1", "p2")
        hero_art = '<div class="hero-art" aria-hidden="true">\n' + "\n".join(
            f'  <div class="phone {p}">{shot(a, s, eager=p == "p0")}</div>'
            for p, (a, s) in reversed(list(zip(places, trio)))) + "\n</div>"

    body = f"""<body>
{nav()}
<main id="main">
<section class="wrap hero">
  <div>
    <h1>Independent apps for <em>everyday things.</em></h1>
    <p class="lead">Modrn Magic is a product studio founded by Akhil Jacob. We design, build, and run our own apps.</p>
    <div class="btns">
      <a class="btn btn-primary" href="#products">See the products</a>
      <a class="btn btn-glass glass" href="#about">Meet the founder</a>
    </div>
    <p class="meta numbers tnum"><a href="/work/">{numbers(apps)}</a></p>
  </div>
  {hero_art}
</section>

<section class="wrap section" id="products" aria-labelledby="products-title" style="padding-top:var(--s-7)">
  <div class="section-head">
    <h2 class="h2" id="products-title">Products</h2>
    <p class="lead">Live on the App Store, Google Play, and the web.</p>
  </div>
  {flagship_html(flag) if flag else ""}
  {f'<div class="bento">{chr(10)}{bento}{chr(10)}  </div>' if bento else ""}
</section>

<section class="wrap section" id="experiments" aria-labelledby="exp-title">
  <div class="section-head">
    <h2 class="h2" id="exp-title">Experiments</h2>
    <p class="lead">Small products in progress, newest first. Every product, archived ones included, is on the work page.</p>
  </div>
  <div class="strip">
{strip}
  </div>
  <div class="btns strip-more">
    <a class="btn btn-glass glass" href="/work/">See all work</a>
    <a class="btn btn-glass glass" href="/work/#archived">Archive</a>
  </div>
</section>

<section class="wrap section" id="about" aria-labelledby="about-title">
  <div class="about">
    <div>
      <h2 class="h2" id="about-title">About the studio</h2>
      <div class="prose reveal" style="margin-top:var(--s-5)">
        <p>Modrn Magic is an independent product studio founded by Akhil Jacob, a software engineer in San Diego. The studio makes its own products: mobile apps and games built with Flutter, and web products built on Next.js and Firebase.</p>
        <p>Each product starts small and ships to real people. Some stay live, some stay experiments, and some are retired. This site lists all of them.</p>
      </div>
      <div class="facts-inline"><span class="chip">Founded by Akhil Jacob</span><span class="chip">San Diego, California</span><span class="chip">iPhone, Android, and web</span></div>
    </div>
    <aside class="founder glass reveal" aria-label="Founder">
      <div class="who"><span class="avatar" aria-hidden="true">AJ</span><div><div class="h3">Akhil Jacob</div><div class="meta">Founder, Modrn Magic</div></div></div>
      <p style="color:var(--ink-2);font-size:var(--t-small)">Akhil designs and builds every Modrn Magic product. His portfolio covers his engineering work beyond the studio.</p>
      <div class="links">
        <a href="https://akhilcjacob.com/">Portfolio <span>akhilcjacob.com</span></a>
        <a href="https://engineering.akhilcjacob.com/">Engineering notes <span>engineering.akhilcjacob.com</span></a>
        <a href="https://github.com/akhilcjacob">GitHub <span>@akhilcjacob</span></a>
        <a href="https://www.linkedin.com/in/akhilcjacob">LinkedIn <span>in/akhilcjacob</span></a>
      </div>
    </aside>
  </div>
</section>

<section class="wrap section" style="padding-top:0">
  <div class="contact-band glass reveal">
    <h2 class="h2">Questions, feedback, or press?</h2>
    <a class="mail" href="mailto:{EMAIL}">{EMAIL}</a>
  </div>
</section>
</main>
{footer(apps)}</body>
</html>
"""
    return head("Modrn Magic: independent app studio by Akhil Jacob", description, "/", "/assets/og/home.jpg", graph) + body


# ---------------------------------------------------------------- product

def render_product(app, apps):
    aid = app["id"]
    live = app["status"] == "live"
    links = app["links"]

    rail = ""
    if app["screenshots"]:
        figs = "\n".join(
            f'<figure class="{s["shape"]}"><img src="/apps/{aid}/{s["src"]}" alt="{e(s["alt"])}" width="{s["w"]}" height="{s["h"]}" '
            + ('fetchpriority="high"' if i == 0 else 'loading="lazy" decoding="async"') + "></figure>"
            for i, s in enumerate(app["screenshots"]))
        rail = rail_html(figs, f"{app['name']} screenshots", len(app["screenshots"]))

    facts = [("Status", status_html(app)), ("Made by", '<a href="/">Modrn Magic</a>'),
             ("Platforms", e(", ".join(PLATFORM_LABEL[p] for p in app["platforms"])))]
    if app.get("genre"):
        facts.append(("Category", e(app["genre"])))
    if live and app.get("price") and links.get("appStore"):
        p = app["price"]["appStore"]
        facts.append(("Price", "Free" if p == "0" else f"${p} on the App Store (US)"))
    d = app["dates"]
    if d.get("shipped"):
        facts.append(("Released", f'<time datetime="{d["shipped"]}">{fmt_date(d["shipped"])}</time>'))
    if live and d.get("updated") and d.get("updated") != d.get("shipped"):
        facts.append(("Last update", f'<time datetime="{d["updated"]}">{fmt_date(d["updated"])}</time>'))
    if not live and years(app):
        facts.append(("Active", e(years(app))))
    if app.get("stack"):
        facts.append(("Built with", e(", ".join(app["stack"]))))
    if links.get("writing"):
        facts.append(("Write-up", f'<a href="{e(links["writing"])}">Building {e(app["name"])}</a>'))
    legal = []
    if app["legal"].get("privacy"):
        legal.append(f'<a href="/apps/{aid}/{app["legal"]["privacy"]}">Privacy policy</a>')
    if app["legal"].get("terms"):
        legal.append(f'<a href="/apps/{aid}/{app["legal"]["terms"]}">Terms of service</a>')
    if app["legal"].get("deleteAccount"):
        legal.append(f'<a href="/apps/{aid}/{app["legal"]["deleteAccount"]}">Delete account</a>')
    if legal:
        facts.append(("Legal", ", ".join(legal)))
    facts.append(("Support", f'<a href="mailto:{EMAIL}?subject={e(app["name"])}">{EMAIL}</a>'))
    facts_html = "\n".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)

    notice = ""
    if app["status"] == "lab":
        notice = f'<p class="notice glass">{e(app["name"])} is an experiment. It has not been released and is not available to download.</p>'
    elif app["status"] == "archived":
        was = f' It was on {", ".join(app["wasOn"])}.' if app.get("wasOn") else ""
        notice = f'<p class="notice glass">{e(app["name"])} is archived and no longer in development.{was}</p>'

    features = ""
    if app.get("features"):
        n = len(app["features"])
        items = "\n".join(f'<div class="feature glass reveal" style="--i:{i}"><h3 class="h3">{e(f["title"])}</h3><p>{e(f["body"])}</p></div>'
                          for i, f in enumerate(app["features"]))
        features = f"""<section class="wrap section" style="padding-top:0" aria-labelledby="f-title">
  <h2 class="h2" id="f-title" style="margin-bottom:var(--s-6)">What it does</h2>
  <div class="features n{n}" style="{tint_style(app)}">
{items}
  </div>
</section>"""

    faq = ""
    if app.get("faq"):
        qs = "\n".join(f'<details class="glass"><summary>{e(q["q"])}</summary><p>{e(q["a"])}</p></details>' for q in app["faq"])
        faq = f"""<section class="wrap section" style="padding-top:0" aria-labelledby="q-title">
  <h2 class="h2" id="q-title" style="margin-bottom:var(--s-6)">Questions</h2>
  <div class="faq">
{qs}
  </div>
</section>"""

    others = [a for a in listed(apps) if a["id"] != aid and (a["status"] == "live" or not live)][:5]
    more = "\n".join(f'<a href="/apps/{a["id"]}/">{icon_html(a, vt=False)}<div><div style="font-weight:600">{e(a["name"])}</div><div class="one">{e(a["oneliner"])}</div></div></a>' for a in others)

    prose = "\n".join(f"<p>{e(p)}</p>" for p in app["description"])

    o = app.get("outcome")
    outcome_tag = ""
    if o:
        outcome_tag = (f'<span class="chip outcome-tag">{e(o["label"])} {fmt_date(o["date"])}</span>'
                       + (draft_mark() if o["draft"] else ""))
        if o["label"] == STATUS_LABEL[app["status"]]:   # "Archived" twice reads as a stutter: date the status instead
            outcome_tag = ""
        notice = ""   # the outcome line says the same thing, with a reason
    record = ""
    if o or app["lessons"]:
        parts = []
        if o:
            parts.append(f'<p class="outcome-line"><strong>{e(o["label"])}, {fmt_date(o["date"])}.</strong> {e(o["line"])}'
                         f'{" " + draft_mark() if o["draft"] else ""}</p>')
        if app["lessons"]:
            items = "".join(f'<li>{e(x["text"])}{" " + draft_mark() if x["draft"] else ""}</li>' for x in app["lessons"])
            parts.append(f'<h3 class="h3">What we learned</h3><ul class="lessons">{items}</ul>')
        record = f'<div class="record glass" aria-label="Outcome">{"".join(parts)}</div>'

    whats_new = ""
    c = app.get("cycle")
    if c and c["updates"]:
        ups = sorted(c["updates"], key=lambda u: u["date"], reverse=True)
        items = "\n".join(
            f'<li class="update glass reveal" id="update-{u["date"]}" style="--i:{i}">'
            f'<a class="update-date meta tnum" href="#update-{u["date"]}"><time datetime="{u["date"]}">{fmt_date(u["date"])}</time></a>'
            f'<p>{e(u["text"])}</p></li>' for i, u in enumerate(ups))
        whats_new = f"""<section class="wrap section" style="padding-top:0" aria-labelledby="new-title">
  <div class="section-head">
    <h2 class="h2" id="new-title">What's new</h2>
    <p class="lead">{e(c["goal"])}</p>
    <p class="meta tnum">Push cycle, <time datetime="{c["start"]}">{fmt_date(c["start"])}</time> to <time datetime="{c["end"]}">{fmt_date(c["end"])}</time></p>
  </div>
  <ol class="updates">
{items}
  </ol>
</section>"""

    banner = ""
    if app.get("draft"):
        banner = (f'<p class="draft-banner glass">{draft_mark()} This page is a draft for Akhil to confirm. '
                  'It is not linked from the rest of the site, the sitemap, or llms.txt.</p>')
    crumb_mid = ("Products", "/#products") if live else (
        (GROUP_LABEL["lab"], "/work/#experiments") if app["status"] == "lab" else ("Archive", "/work/#archived"))

    graph = [
        app_node(app),
        {"@type": "WebPage", "@id": page_url(app), "url": page_url(app), "name": f"{app['name']} by Modrn Magic",
         "isPartOf": {"@id": SITE_ID}, "about": {"@id": page_url(app) + "#app"}, "inLanguage": "en-US",
         "primaryImageOfPage": f"{SITE}/assets/og/{aid}.jpg",
         "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
             {"@type": "ListItem", "position": 1, "name": "Modrn Magic", "item": f"{SITE}/"},
             {"@type": "ListItem", "position": 2, "name": crumb_mid[0], "item": f"{SITE}{crumb_mid[1]}"},
             {"@type": "ListItem", "position": 3, "name": app["name"], "item": page_url(app)}]}},
        org_node(),
        person_node(),
    ]
    if app.get("faq"):
        graph.append({"@type": "FAQPage", "@id": page_url(app) + "#faq", "mainEntity": [
            {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in app["faq"]]})

    if live:
        where = " and ".join(PLATFORM_LABEL[p] for p in app["platforms"])
        title = f"{app['name']}: {app['oneliner'].rstrip('.')} | Modrn Magic"
        if len(title) > 70:
            title = f"{app['name']} for {where} | Modrn Magic"
    else:
        title = f"{app['name']} ({STATUS_LABEL[app['status']].lower()}) | Modrn Magic"
    description = app["summary"]
    if len(description) > 230:
        description = description[:description.rfind(".", 0, 230) + 1]

    body = f"""<body>
{nav("products" if live else "work")}
<main id="main">
<div class="wrap">
  {banner}
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Modrn Magic</a> / <a href="{crumb_mid[1]}">{crumb_mid[0]}</a> / <span aria-current="page">{e(app['name'])}</span></nav>
  <section class="p-hero">
    {icon_html(app)}
    <div>
      <h1>{e(app['name'])}</h1>
      <p class="lead">{e(app['oneliner'])}</p>
      <div class="row">{status_html(app, o)}{outcome_tag}{chips(app)}</div>
      {store_buttons(app)}
    </div>
  </section>
</div>
{rail}
<section class="wrap section" aria-labelledby="about-title">
  <div class="p-body">
    <div>
      <h2 class="h2" id="about-title" style="margin-bottom:var(--s-5)">About {e(app['name'])}</h2>
      <div class="prose">
{prose}
      </div>
      {f'<div style="margin-top:var(--s-5)">{notice}</div>' if notice else ''}
      {record}
    </div>
    <aside class="facts glass" aria-label="Facts"><dl>
{facts_html}
    </dl></aside>
  </div>
</section>
{whats_new}
{features}
{faq}
<section class="wrap section" style="padding-top:0" aria-labelledby="more-title">
  <h2 class="h3" id="more-title" style="margin-bottom:var(--s-4)">More from Modrn Magic</h2>
  <div class="more">
{more}
  </div>
</section>
</main>
{footer(apps)}</body>
</html>
"""
    return head(title, description, f"/apps/{aid}/", f"/assets/og/{aid}.jpg", graph, noindex=bool(app.get("draft"))) + body


# ---------------------------------------------------------------- product site (apps/<id>/home/)

def render_product_site(app, apps):
    """The marketing page a store listing can point to, from home/descriptions.json."""
    aid = app["id"]
    data = json.load(open(os.path.join(ROOT, "apps", aid, "home/descriptions.json")))
    base = f"/apps/{aid}/home/"
    tour = data["tour"]

    def img(s, eager=False):
        load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
        return f'<img src="{base}{s["src"]}" alt="{e(s["alt"])}" width="{s["w"]}" height="{s["h"]}" {load}>'

    left, right, center = (tour[i] for i in data["hero"])
    hero_art = f"""<div class="hero-art framed" aria-hidden="true">
  <div class="phone p1">{img(left)}</div>
  <div class="phone p2">{img(right)}</div>
  <div class="phone p0">{img(center, eager=True)}</div>
</div>"""
    figs = "\n".join(f'<figure class="phone">{img(s)}<figcaption><span class="h3">{e(s["title"])}</span>'
                     f'<span>{e(s["text"])}</span></figcaption></figure>' for s in tour)
    features = ""
    if app.get("features"):
        items = "\n".join(f'<div class="feature glass reveal" style="--i:{i}"><h3 class="h3">{e(f["title"])}</h3><p>{e(f["body"])}</p></div>'
                          for i, f in enumerate(app["features"]))
        features = f"""<section class="wrap section" style="padding-top:0" aria-labelledby="f-title">
  <h2 class="h2" id="f-title" style="margin-bottom:var(--s-6)">Why it works</h2>
  <div class="features n{len(app['features'])}" style="{tint_style(app)}">
{items}
  </div>
</section>"""
    legal = [f'<a class="btn btn-glass glass" href="/apps/{aid}/{app["legal"][k]}">{label}</a>'
             for k, label in (("privacy", "Privacy policy"), ("terms", "Terms of service")) if app["legal"].get(k)]
    price = ""
    if app.get("price") and app["links"].get("appStore"):
        p = app["price"]["appStore"]
        price = f'<p class="meta ps-price">{"Free on the App Store" if p == "0" else f"${p} on the App Store (US)"}</p>'

    title = f"{data['title']}: {app['oneliner'].rstrip('.')}"
    description = app["summary"]
    graph = [
        {"@type": "WebPage", "@id": SITE + base, "url": SITE + base, "name": title, "isPartOf": {"@id": SITE_ID},
         "about": {"@id": page_url(app) + "#app"}, "inLanguage": "en-US"},
        app_node(app), org_node(), person_node(),
    ]
    body = f"""<body>
{nav("products")}
<main id="main" style="{tint_style(app)}">
<div class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Modrn Magic</a> / <a href="/apps/{aid}/">{e(app['name'])}</a> / <span aria-current="page">Product site</span></nav>
  <section class="hero ps-hero">
    <div>
      <div class="ps-brand">{icon_html(app)}<span class="h3">{e(data['title'])}</span></div>
      <h1>{e(data['headline'])}</h1>
      <p class="lead">{e(data['lead'])}</p>
      {store_buttons(app, home=False)}
      {price}
    </div>
    {hero_art}
  </section>
</div>
<div class="wrap section-head" style="margin-bottom:var(--s-5)"><h2 class="h2" id="tour-title">A quick tour</h2></div>
{rail_html(figs, f"{data['title']} tour", len(tour), "framed")}
{features}
<section class="wrap section" style="padding-top:0">
  <div class="contact-band glass reveal">
    <h2 class="h2">{e(data['closing']['title'])}</h2>
    <p class="lead">{e(data['closing']['text'])}</p>
    <div class="btns" style="justify-content:center">{''.join(legal)}<a class="btn btn-glass glass" href="/apps/{aid}/">More about {e(app['name'])}</a></div>
  </div>
</section>
</main>
{footer(apps)}</body>
</html>
"""
    return head(f"{title} | Modrn Magic", description, base, f"/assets/og/{aid}.jpg", graph) + body


# ---------------------------------------------------------------- /work/

def render_work(apps):
    """Every product, newest first, filterable by status and kind.

    Filters are links to #<filter>. Each target is an empty fixed-position
    span before the list, so :target filters the list with CSS alone (no
    scroll jump, works with JavaScript off). site.js adds aria-current, a live
    count for screen readers, and a view transition between filter states.
    """
    items = sorted(shown(apps), key=latest, reverse=True)
    statuses = [k for k in STATUS_LABEL if any(a["status"] == k for a in items)]
    kinds = [k for k in KIND_LABEL if any(a["kind"] == k for a in items)]
    filters = [("all", "All", lambda a: True, "products")]
    filters += [(GROUP_ID[k], GROUP_LABEL[k], (lambda k: lambda a: a["status"] == k)(k), "status") for k in statuses]
    filters += [(f"kind-{k}", KIND_LABEL[k], (lambda k: lambda a: a["kind"] == k)(k), "kind") for k in kinds]

    def count_text(fid, label, test):
        n = sum(1 for a in items if test(a))
        noun = "product" if n == 1 else "products"
        if fid == "all":
            return f"Showing all {n} {noun}."
        return f"Showing {n} {noun}: {label}."

    targets = "".join(f'<span class="ftarget" id="{fid}"></span>' for fid, *_ in filters)
    # The active pill: a left cap, a 1px middle scaled to length, and a right cap,
    # so site.js can slide and stretch it with transforms alone, behind static labels.
    pill = '<span class="fpill" aria-hidden="true"><i></i><i></i><i></i></span>'
    chip_link = lambda fid, label: f'<a class="fchip" href="#{fid}" data-filter="{fid}">{label}</a>'
    status_chips = "".join(chip_link(fid, label) for fid, label, _, group in filters if group in ("products", "status"))
    kind_chips = "".join(chip_link(fid, label) for fid, label, _, group in filters if group == "kind")
    counts = "".join(f'<span data-for="{fid}">{count_text(fid, label, test)}</span>' for fid, label, test, _ in filters)

    def row(a, i):
        o = a.get("outcome")
        tag = f'<span class="chip outcome-tag">{e(o["label"])} {fmt_date(o["date"])}</span>' if o and o["label"] != STATUS_LABEL[a["status"]] else ""
        line = f'<p class="w-outcome">{e(o["line"])}{" " + draft_mark() if o["draft"] else ""}</p>' if o else ""
        return f"""<li class="work-item" data-status="{GROUP_ID[a['status']]}" data-kind="kind-{a['kind']}" style="--i:{i};view-transition-name:work-{a['id']}">
  <a class="w-card glass" href="/apps/{a['id']}/" style="{tint_style(a)}">
    {icon_html(a, vt=False)}
    <div class="w-main">
      <div class="w-head"><h2 class="name">{e(a['name'])}</h2>{status_html(a, o)}{tag}{draft_mark() if a.get("draft") else ""}</div>
      <p class="one">{e(a['oneliner'])}</p>
      {line}
    </div>
    <div class="w-meta">{f'<span class="meta tnum">{years(a)}</span>' if years(a) else ""}<span class="chip">{KIND_ONE[a['kind']]}</span></div>
  </a>
</li>"""

    rows = "\n".join(row(a, i) for i, a in enumerate(items))
    css = "".join(
        f'#{fid}:target~.work-list .work-item:not([data-{"status" if group == "status" else "kind"}="{fid}"]){{display:none}}'
        f'#{fid}:target~.work-count [data-for="{fid}"]{{display:inline}}'
        f'#{fid}:target~.work-count [data-for="all"]{{display:none}}'
        f'#{fid}:target~.filters [data-filter="{fid}"]{{color:var(--bg)}}'
        f'#{fid}:target~.filters:not(.pill) [data-filter="{fid}"]{{background:var(--ink)}}'
        f'#{fid}:target~.filters [data-filter="all"]{{background:transparent;color:var(--ink-2)}}'
        for fid, label, _, group in filters if fid != "all")
    drafts = sum(1 for a in items if a.get("draft"))
    draft_note = f' <span class="meta">Includes {drafts} draft{"s" if drafts != 1 else ""} {draft_mark()}</span>' if drafts else ""
    graph = [
        {"@type": "CollectionPage", "@id": f"{SITE}/work/", "url": f"{SITE}/work/", "name": "All work by Modrn Magic",
         "isPartOf": {"@id": SITE_ID}, "about": {"@id": ORG_ID}, "inLanguage": "en-US",
         "mainEntity": {"@type": "ItemList", "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": page_url(a), "name": a["name"]}
             for i, a in enumerate(x for x in items if not x.get("draft"))]}},
        org_node(), person_node(),
    ]
    body = f"""<body>
{nav("work")}
<main id="main" class="wrap work">
  <header class="page-hero">
    <h1>Work</h1>
    <p class="lead">Every Modrn Magic product, newest first: what is live, what is still an experiment, and what was archived, with the outcome where there is one.</p>
    <p class="meta numbers tnum">{numbers(items)}{draft_note}</p>
  </header>
  {targets}
  <nav class="filters" aria-label="Filter products">
    <div class="fgroup" role="group" aria-label="Status">{pill}{status_chips}</div>
    <div class="fgroup" role="group" aria-label="Kind">{pill}{kind_chips}</div>
  </nav>
  <p class="work-count meta" id="work-count">{counts}</p>
  <p class="sr-only" aria-live="polite" id="work-live"></p>
  <ul class="work-list" aria-label="Products">
{rows}
  </ul>
</main>
{footer(apps)}</body>
</html>
"""
    extra = f"<style>{css}</style>\n"
    description = "Every Modrn Magic product: live apps, experiments, and archived work, with outcomes."
    return head("Work | Modrn Magic", description, "/work/", "/assets/og/home.jpg", graph, extra=extra) + body


# ---------------------------------------------------------------- contact, 404, mvp

def render_contact(apps):
    live = [a for a in listed(apps) if a["status"] == "live"]
    support = "\n".join(f'<a href="mailto:{EMAIL}?subject={e(a["name"])}">{icon_html(a, vt=False)}<div><div style="font-weight:600">{e(a["name"])}</div><div class="one">Email about {e(a["name"])}</div></div></a>' for a in live)
    description = f"Contact Modrn Magic at {EMAIL} for app support, feedback, or press."
    graph = [
        {"@type": "ContactPage", "@id": f"{SITE}/contact/", "url": f"{SITE}/contact/", "name": "Contact Modrn Magic",
         "isPartOf": {"@id": SITE_ID}, "about": {"@id": ORG_ID}, "inLanguage": "en-US"},
        org_node(), person_node(),
    ]
    body = f"""<body>
{nav("contact")}
<main id="main" class="wrap">
  <section class="page-hero">
    <h1>Contact</h1>
    <p class="lead">For app support, feedback, or press, email the studio. Include the app name if it is about a specific product.</p>
    <div class="btns"><a class="btn btn-primary" href="mailto:{EMAIL}">{icon("envelope-simple")}{EMAIL}</a></div>
  </section>
  <section class="section" style="padding-top:var(--s-6)" aria-labelledby="s-title">
    <h2 class="h3" id="s-title" style="margin-bottom:var(--s-4)">Support for a specific app</h2>
    <div class="more">
{support}
    </div>
  </section>
  <section class="section" style="padding-top:0">
    <p class="prose">Looking for the founder? Akhil Jacob's portfolio is at <a href="https://akhilcjacob.com/">akhilcjacob.com</a>.</p>
  </section>
</main>
{footer(apps)}</body>
</html>
"""
    return head("Contact | Modrn Magic", description, "/contact/", "/assets/og/home.jpg", graph) + body


def render_404(apps):
    body = f"""<body>
{nav()}
<main id="main" class="wrap">
  <section class="page-hero" style="min-height:50dvh;align-content:center">
    <h1>Page not found</h1>
    <p class="lead">That page does not exist or has moved. The products are all listed on the home page.</p>
    <div class="btns"><a class="btn btn-primary" href="/">Go to the home page</a></div>
  </section>
</main>
{footer(apps)}</body>
</html>
"""
    return head("Page not found | Modrn Magic", "This page does not exist.", "/404.html", "/assets/og/home.jpg", [org_node()], noindex=True) + body


def render_mvp():
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contact | Modrn Magic</title>
<meta name="robots" content="noindex, follow">
<link rel="canonical" href="{SITE}/contact/">
<meta http-equiv="refresh" content="0; url=/contact/">
<link rel="stylesheet" href="/assets/css/site.css">
</head>
<body>
<main class="wrap page-hero">
  <h1>This page moved</h1>
  <p class="lead">Reach the studio at <a href="mailto:{EMAIL}">{EMAIL}</a>, or go to the <a href="/contact/">contact page</a>.</p>
</main>
</body>
</html>
"""


# ---------------------------------------------------------------- legal pages

# Store listings link to these URLs. The Markdown next to each page is the
# source and stays published; the page is plain HTML so it reads with
# JavaScript off and never depends on a CDN.
LEGAL = {"privacy": ("privacy-policy.md", "Privacy policy"), "tos": ("terms_of_service.md", "Terms of service")}
SUPPORT = "support@modrnmagic.app"   # the address the legal text itself names


def md_inline(text):
    out = e(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" rel="noopener">\1</a>', out)
    out = re.sub(r"(?<![\w.@/])([\w.+-]+@[\w-]+\.[\w.]+\w)", r'<a href="mailto:\1">\1</a>', out)
    return out


def md_to_html(md, title_words):
    """The small Markdown subset the legal files use: headings, bold-only
    lines used as headings, bullet lists, links, bold, and hard breaks.
    The first line is dropped when it is the document title."""
    md = re.sub(r"(?m)^(#{1,6} .*)$", r"\n\1\n", md)   # a heading is its own block
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", md.strip()) if b.strip()]
    if blocks:
        first = re.sub(r"[#*\s]+", " ", blocks[0].split("\n")[0]).strip().lower()
        if any(w in first for w in title_words) and len(first) < 60 and "\n" not in blocks[0].strip():
            blocks = blocks[1:]
    html_out = []
    used = set()

    def heading(level, text):
        slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"\*\*", "", text).lower()).strip("-") or "section"
        base, n = slug, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        return f'<h{level} id="{slug}">{md_inline(text)}</h{level}>'

    for b in blocks:
        lines = b.split("\n")
        m = re.match(r"^(#{1,6})\s+(.*)$", lines[0])
        if m and len(lines) == 1:
            html_out.append(heading(3 if len(m.group(1)) >= 3 else 2, m.group(2).strip()))
        elif re.fullmatch(r"\*\*[^*]+\*\*\s*", b):
            html_out.append(heading(2, b.strip()[2:-2].strip()))
        elif all(re.match(r"^\s*[*+-]\s+", ln) for ln in lines):
            items = "".join("<li>" + md_inline(re.sub(r"^\s*[*+-]\s+", "", ln)) + "</li>" for ln in lines)
            html_out.append(f"<ul>{items}</ul>")
        else:
            parts = [md_inline(ln.rstrip()) + ("<br>" if ln.endswith("  ") and i < len(lines) - 1 else "")
                     for i, ln in enumerate(lines)]
            html_out.append("<p>" + "\n".join(parts) + "</p>")
    return "\n".join(html_out)


def legal_shell(app_name, aid, path, title, description, crumb, inner, apps, side=""):
    graph = [{"@type": "WebPage", "@id": SITE + path, "url": SITE + path, "name": title,
              "isPartOf": {"@id": SITE_ID}, "inLanguage": "en-US",
              "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
                  {"@type": "ListItem", "position": 1, "name": "Modrn Magic", "item": f"{SITE}/"},
                  {"@type": "ListItem", "position": 2, "name": app_name, "item": f"{SITE}/apps/{aid}/"},
                  {"@type": "ListItem", "position": 3, "name": crumb, "item": SITE + path}]}},
              org_node()]
    body = f"""<body>
{nav()}
<main id="main" class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Modrn Magic</a> / <a href="/apps/{aid}/">{e(app_name)}</a> / <span aria-current="page">{e(crumb)}</span></nav>
  <div class="legal">
{inner}
    <aside class="legal-side" aria-label="About this page">
      <div class="facts glass">
        <p class="meta">Questions about this page</p>
        <p><a href="mailto:{SUPPORT}?subject={e(app_name)}">{SUPPORT}</a></p>
{side}
      </div>
    </aside>
  </div>
</main>
{footer(apps)}</body>
</html>
"""
    og = f"/assets/og/{aid}.jpg" if os.path.exists(os.path.join(ROOT, f"assets/og/{aid}.jpg")) else "/assets/og/home.jpg"
    return head(title, description, path, og, graph) + body


def render_legal(aid, apps):
    """Pages for every apps/<id>/privacy/ and apps/<id>/tos/ folder with a Markdown source."""
    meta = json.load(open(os.path.join(ROOT, "apps", aid, "app.json")))
    name = meta["name"]
    files = {}
    present = [k for k, (src, _) in LEGAL.items() if os.path.exists(os.path.join(ROOT, "apps", aid, k, src))]
    for key in present:
        src, label = LEGAL[key]
        md = open(os.path.join(ROOT, "apps", aid, key, src), encoding="utf-8").read()
        path = f"/apps/{aid}/{key}/"
        words = ("privacy",) if key == "privacy" else ("terms",)
        if md.strip():
            doc = md_to_html(md, words)
        else:
            doc = (f'<p>The {label.lower()} for {e(name)} is not published on this page yet. '
                   f'For a copy, or with any question about it, email <a href="mailto:{SUPPORT}?subject={e(name)}%20{e(label)}">{SUPPORT}</a>.</p>')
        inner = f"""    <article class="legal-doc">
      <header class="page-hero"><h1>{e(name)} {label.lower()}</h1><p class="lead">{e(name)} is made by Modrn Magic LLC.</p></header>
      <div class="legal-body glass">
{doc}
      </div>
    </article>"""
        others = [f'<li><a href="/apps/{aid}/{k}/">{LEGAL[k][1]}</a></li>' for k in present if k != key]
        if key == "privacy" and os.path.exists(os.path.join(ROOT, "apps", aid, "privacy/delete-account/index.html")):
            others.append(f'<li><a href="/apps/{aid}/privacy/delete-account/">Delete your account</a></li>')
        others.append(f'<li><a href="/apps/{aid}/">About {e(name)}</a></li>')
        side = f'        <p class="meta">Related</p>\n        <ul class="legal-links">{"".join(others)}</ul>'
        files[f"apps/{aid}/{key}/index.html"] = legal_shell(
            name, aid, path, f"{name} {label.lower()} | Modrn Magic",
            f"The {label.lower()} for {name}, an app by Modrn Magic.", label, inner, apps, side)
    if os.path.exists(os.path.join(ROOT, "apps", aid, "privacy/delete-account/index.html")):
        path = f"/apps/{aid}/privacy/delete-account/"
        subject = "Account%20Deletion%20Request"
        inner = f"""    <article class="legal-doc">
      <header class="page-hero"><h1>Delete your {e(name)} account</h1>
        <p class="lead">To delete your account, email the support team with the request.</p>
        <div class="btns"><a class="btn btn-primary" href="mailto:{SUPPORT}?subject={subject}">{icon("envelope-simple")}Request account deletion</a></div>
      </header>
    </article>"""
        side = (f'        <p class="meta">Related</p>\n        <ul class="legal-links"><li><a href="/apps/{aid}/privacy/">Privacy policy</a></li>'
                f'<li><a href="/apps/{aid}/">About {e(name)}</a></li></ul>')
        files[f"apps/{aid}/privacy/delete-account/index.html"] = legal_shell(
            name, aid, path, f"Delete your {name} account | Modrn Magic",
            f"How to delete your {name} account and its data.", "Delete account", inner, apps, side)
    return files


def legal_ids():
    apps_dir = os.path.join(ROOT, "apps")
    return sorted(d for d in os.listdir(apps_dir)
                  if any(os.path.exists(os.path.join(apps_dir, d, k, src)) for k, (src, _) in LEGAL.items()))


# ---------------------------------------------------------------- sitemap, llms.txt

def git_date(rel):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return out or SITE_DATE
    except OSError:
        return SITE_DATE


def render_sitemap(apps):
    apps = listed(apps)
    urls = [("/", SITE_DATE, "1.0"), ("/work/", SITE_DATE, "0.8"), ("/contact/", SITE_DATE, "0.5")]
    for a in apps:
        urls.append((f"/apps/{a['id']}/", SITE_DATE, "0.9" if a["status"] == "live" else "0.5"))
    for a in apps:
        if a["links"].get("home"):
            urls.append((f"/apps/{a['id']}/{a['links']['home']}", git_date(f"apps/{a['id']}/{a['links']['home']}index.html"), "0.7"))
        for key in ("privacy", "terms", "deleteAccount"):
            rel = a["legal"].get(key)
            if rel:
                src = "privacy-policy.md" if key == "privacy" else ("terms_of_service.md" if key == "terms" else "index.html")
                urls.append((f"/apps/{a['id']}/{rel}", git_date(f"apps/{a['id']}/{rel}{src}"), "0.3"))
    rows = "\n".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{d}</lastmod><priority>{p}</priority></url>" for u, d, p in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n'


def render_llms(apps):
    apps = listed(apps)

    def line(a):
        bits = [f"- [{a['name']}]({page_url(a)}): {a['summary']}"]
        where = []
        if a["status"] == "live":
            for key, label in (("appStore", "App Store"), ("googlePlay", "Google Play"), ("web", "Website")):
                if a["links"].get(key):
                    where.append(f"[{label}]({a['links'][key]})")
        if where:
            bits.append(" Available: " + ", ".join(where) + ".")
        if a["status"] == "live" and a.get("price") and a["links"].get("appStore"):
            p = a["price"]["appStore"]
            bits.append(" Price on the US App Store: " + ("free." if p == "0" else f"${p}."))
        if a["dates"].get("shipped"):
            bits.append(f" First released {fmt_date(a['dates']['shipped'])}.")
        if a["status"] != "live":
            bits.append(f" Status: {STATUS_LABEL[a['status']].lower()}, {years(a)}.")
        return "".join(bits)

    live = "\n".join(line(a) for a in apps if a["status"] == "live")
    other = "\n".join(line(a) for a in apps if a["status"] != "live")
    return f"""# Modrn Magic

> Modrn Magic (modrnmagic.app) is an independent product studio founded by Akhil Jacob in San Diego, California. It designs, builds, and runs its own apps for iPhone, Android, and the web. It does not publish client work on this site.

Key facts:

- Founder: Akhil Jacob, software engineer. Portfolio: https://akhilcjacob.com/
- Legal name: Modrn Magic LLC
- Contact: {EMAIL}
- Mobile apps are built with Flutter. Web products use Next.js and Firebase.
- Store listings name the seller as Akhil Jacob.

## Products

{live}

## Experiments and archive

{other}

## Founder

- [Akhil Jacob](https://akhilcjacob.com/): founder of Modrn Magic. Engineering notes at https://engineering.akhilcjacob.com/, code at https://github.com/akhilcjacob.

## Optional

- [All work]({SITE}/work/): every product with its status and outcome. {numbers(apps)}
- [Contact]({SITE}/contact/)
- [Sitemap]({SITE}/sitemap.xml)
"""


# ---------------------------------------------------------------- main

def outputs():
    apps = load_apps()
    files = {
        "index.html": render_home(apps),
        "contact/index.html": render_contact(apps),
        "work/index.html": render_work(apps),
        "404.html": render_404(apps),
        "mvp.html": render_mvp(),
        "sitemap.xml": render_sitemap(apps),
        "llms.txt": render_llms(apps),
    }
    for a in shown(apps):
        files[f"apps/{a['id']}/index.html"] = render_product(a, apps)
        if a["links"].get("home") and os.path.exists(os.path.join(ROOT, "apps", a["id"], "home/descriptions.json")):
            files[f"apps/{a['id']}/home/index.html"] = render_product_site(a, apps)
    for name, text in files.items():
        if "\u2014" in text or "\u2013" in text:
            raise SystemExit(f"{name}: contains an em or en dash")
    # Legal text is reproduced verbatim, dashes included.
    for aid in legal_ids():
        files.update(render_legal(aid, apps))
    return files


def orphans():
    """Generated pages of products this build does not render (drafts, in the
    release build). They must not stay on disk, or a merge would publish them."""
    apps = load_apps()
    keep = {a["id"] for a in shown(apps)}
    out = []
    for a in apps:
        if a["id"] in keep:
            continue
        for rel in (f"apps/{a['id']}/index.html", f"apps/{a['id']}/home/index.html"):
            if os.path.exists(os.path.join(ROOT, rel)):
                out.append(rel)
    return out


def main():
    check = "--check" in sys.argv
    stale = []
    for rel in orphans():
        if check:
            stale.append(rel)
        else:
            os.remove(os.path.join(ROOT, rel))
            print("removed", rel)
    for rel, text in outputs().items():
        path = os.path.join(ROOT, rel)
        if check:
            if not os.path.exists(path) or open(path).read() != text:
                stale.append(rel)
            continue
        os.makedirs(os.path.dirname(path) or ROOT, exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        print("wrote", rel)
    if stale:
        print("stale:", ", ".join(stale))
        sys.exit(1)


if __name__ == "__main__":
    main()
