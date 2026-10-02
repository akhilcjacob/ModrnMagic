#!/usr/bin/env python3
"""Render the static site from apps/index.json and apps/<id>/app.json.

Writes: index.html, apps/<id>/index.html, contact/index.html, mvp.html,
404.html, sitemap.xml, llms.txt, and the legal pages apps/<id>/privacy/,
apps/<id>/tos/, and apps/<id>/privacy/delete-account/ from their Markdown. Standard library only. The output is
committed, so GitHub Pages serves plain files with no build step.

    python3 _scripts/render.py          # write files
    python3 _scripts/render.py --check  # exit 1 if committed output is stale

Bump SITE_DATE when page content changes; it feeds sitemap lastmod.
"""
import datetime as dt
import html
import json
import os
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
STATUS_LABEL = {"live": "Live", "lab": "In the lab", "archived": "Archived"}
PLATFORM_LABEL = {"ios": "iPhone", "android": "Android", "web": "Web"}
OS_LABEL = {"ios": "iOS", "android": "Android", "web": "Web browser"}

e = html.escape


def icon(name, cls=""):
    with open(os.path.join(ROOT, "assets/icons", f"{name}.svg")) as f:
        svg = f.read().strip()
    attrs = ' aria-hidden="true" focusable="false"' + (f' class="{cls}"' if cls else "")
    return svg.replace("<svg ", f"<svg{attrs} ", 1)


def load_apps():
    ids = json.load(open(os.path.join(ROOT, "apps/index.json")))
    return [json.load(open(os.path.join(ROOT, "apps", i, "app.json"))) for i in ids]


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
    import re
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
    {link("/#lab", "Lab", "lab")}
    {link("/contact/", "Contact", "contact")}
  </nav>
  <button class="theme-toggle" type="button" aria-label="Dark mode" aria-pressed="false">{icon("moon", "i-moon")}{icon("sun", "i-sun")}</button>
</header>
"""


def footer(apps):
    live = [a for a in apps if a["status"] == "live"]
    items = "\n".join(f'<li><a href="/apps/{a["id"]}/">{e(a["name"])}</a></li>' for a in live)
    legal = "\n".join(f'<li><a href="/apps/{a["id"]}/privacy/">{e(a["name"])} privacy</a></li>'
                      for a in live if a["legal"].get("privacy"))
    return f"""<footer class="footer wrap">
  <div class="footer-grid">
    <div>
      <a class="brand" href="/"><img src="/assets/img/mark-96.webp" alt="" width="30" height="30" loading="lazy"><span>Modrn Magic</span></a>
      <p style="margin-top:12px;max-width:34ch">An independent product studio founded by <a href="https://akhilcjacob.com/">Akhil Jacob</a>.</p>
    </div>
    <div><h2>Products</h2><ul>{items}</ul></div>
    <div><h2>Studio</h2><ul>
      <li><a href="/#lab">Lab and archive</a></li>
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


def status_html(app):
    return f'<span class="status status-{app["status"]}">{STATUS_LABEL[app["status"]]}</span>'


# ---------------------------------------------------------------- home

def render_home(apps):
    live = {a["id"]: a for a in apps if a["status"] == "live"}
    shelf_apps = [a for a in apps if a["status"] != "live"]

    def shot(app_id, n, cls="", eager=False, width=None):
        s = live[app_id]["screenshots"][n]
        load = 'decoding="async"' if eager else 'loading="lazy" decoding="async"'
        return f'<img class="{cls}" src="/apps/{app_id}/{s["src"]}" alt="{e(s["alt"])}" width="{s["w"]}" height="{s["h"]}" {load}>'

    def cell(app, inner="", dark=False):
        cls = f"cell glass reveal c-{app['id']}" + (" dark" if dark else "")
        return f"""<a class="{cls}" href="/apps/{app['id']}/" style="--tint:{app['color']}">
  {icon("arrow-up-right", "arrow")}
  <div class="top">{icon_html(app)}<div><h3 class="name">{e(app['name'])}</h3>{status_html(app)}</div></div>
  <p class="one">{e(app['oneliner'])}</p>
  {inner}
  <div class="foot">{chips(app)}</div>
</a>"""

    bento = "\n".join([
        cell(live["flowmoro"], f'<div class="cell-shots">{shot("flowmoro", 0)}{shot("flowmoro", 2)}</div>'),
        cell(live["skywise"], f'<div class="peek" aria-hidden="true">{shot("skywise", 0)}</div>'),
        cell(live["astrodefender"], f'<div class="peek" aria-hidden="true">{shot("astrodefender", 2)}</div>', dark=True),
        cell(live["inboxhiiv"], f'<div class="cell-shots">{shot("inboxhiiv", 0)}</div>'),
    ])

    shelf = "\n".join(f"""<a class="shelf-row reveal" style="--i:{i}" href="/apps/{a['id']}/">
  {icon_html(a)}
  <div><div class="name">{e(a['name'])}</div><p class="one">{e(a['oneliner'])}</p></div>
  <div class="right">{status_html(a)}<span class="meta tnum">{years(a)}</span></div>
</a>""" for i, a in enumerate(shelf_apps))

    live_list = [a for a in apps if a["status"] == "live"]
    names = ", ".join(a["name"] for a in live_list[:-1]) + f", and {live_list[-1]['name']}"
    description = f"Modrn Magic is an independent product studio founded by Akhil Jacob. It makes {names} for iPhone, Android, and the web."

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

    hero_art = f"""<div class="hero-art" aria-hidden="true">
  <div class="phone p1">{shot("skywise", 1)}</div>
  <div class="phone p2">{shot("astrodefender", 0)}</div>
  <div class="phone p0">{shot("flowmoro", 1, eager=True)}</div>
</div>"""

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
  </div>
  {hero_art}
</section>

<section class="wrap section" id="products" aria-labelledby="products-title" style="padding-top:var(--s-7)">
  <div class="section-head">
    <h2 class="h2" id="products-title">Products</h2>
    <p class="lead">Live on the App Store, Google Play, and the web.</p>
  </div>
  <div class="bento">
{bento}
  </div>
</section>

<section class="wrap section" id="lab" aria-labelledby="lab-title">
  <div class="section-head">
    <h2 class="h2" id="lab-title">Lab and archive</h2>
    <p class="lead">Prototypes still in progress, and ideas that were retired. They stay listed so the full record is here.</p>
  </div>
  <div class="shelf glass">
{shelf}
  </div>
</section>

<section class="wrap section" id="about" aria-labelledby="about-title">
  <div class="about">
    <div>
      <h2 class="h2" id="about-title">About the studio</h2>
      <div class="prose reveal" style="margin-top:var(--s-5)">
        <p>Modrn Magic is an independent product studio founded by Akhil Jacob, a software engineer in San Diego. The studio makes its own products: mobile apps and games built with Flutter, and web products built on Next.js and Firebase.</p>
        <p>Each product starts small and ships to real people. Some stay live, some go back to the lab, and some are retired. This site lists all of them.</p>
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
        notice = f'<p class="notice glass">{e(app["name"])} is a prototype in the lab. It has not been released and is not available to download.</p>'
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
  <div class="features n{n}" style="--tint:{app['color']}">
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

    others = [a for a in apps if a["id"] != aid and (a["status"] == "live" or not live)][:5]
    more = "\n".join(f'<a href="/apps/{a["id"]}/">{icon_html(a, vt=False)}<div><div style="font-weight:600">{e(a["name"])}</div><div class="one">{e(a["oneliner"])}</div></div></a>' for a in others)

    prose = "\n".join(f"<p>{e(p)}</p>" for p in app["description"])
    crumb_mid = ("Products", "/#products") if live else ("Lab and archive", "/#lab")

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
{nav("products" if live else "lab")}
<main id="main">
<div class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Modrn Magic</a> / <a href="{crumb_mid[1]}">{crumb_mid[0]}</a> / <span aria-current="page">{e(app['name'])}</span></nav>
  <section class="p-hero">
    {icon_html(app)}
    <div>
      <h1>{e(app['name'])}</h1>
      <p class="lead">{e(app['oneliner'])}</p>
      <div class="row">{status_html(app)}{chips(app)}</div>
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
    </div>
    <aside class="facts glass" aria-label="Facts"><dl>
{facts_html}
    </dl></aside>
  </div>
</section>
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
    return head(title, description, f"/apps/{aid}/", f"/assets/og/{aid}.jpg", graph) + body


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
  <div class="features n{len(app['features'])}" style="--tint:{app['color']}">
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
<main id="main" style="--tint:{app['color']}">
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


# ---------------------------------------------------------------- contact, 404, mvp

def render_contact(apps):
    live = [a for a in apps if a["status"] == "live"]
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
    import re
    out = e(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" rel="noopener">\1</a>', out)
    out = re.sub(r"(?<![\w.@/])([\w.+-]+@[\w-]+\.[\w.]+\w)", r'<a href="mailto:\1">\1</a>', out)
    return out


def md_to_html(md, title_words):
    """The small Markdown subset the legal files use: headings, bold-only
    lines used as headings, bullet lists, links, bold, and hard breaks.
    The first line is dropped when it is the document title."""
    import re
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
    urls = [("/", SITE_DATE, "1.0"), ("/contact/", SITE_DATE, "0.5")]
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

## Lab and archive

{other}

## Founder

- [Akhil Jacob](https://akhilcjacob.com/): founder of Modrn Magic. Engineering notes at https://engineering.akhilcjacob.com/, code at https://github.com/akhilcjacob.

## Optional

- [Contact]({SITE}/contact/)
- [Sitemap]({SITE}/sitemap.xml)
"""


# ---------------------------------------------------------------- main

def outputs():
    apps = load_apps()
    files = {
        "index.html": render_home(apps),
        "contact/index.html": render_contact(apps),
        "404.html": render_404(apps),
        "mvp.html": render_mvp(),
        "sitemap.xml": render_sitemap(apps),
        "llms.txt": render_llms(apps),
    }
    for a in apps:
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


def main():
    check = "--check" in sys.argv
    stale = []
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
