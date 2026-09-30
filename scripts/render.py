#!/usr/bin/env python3
"""Render the static site from apps/index.json and apps/<id>/app.json.

Writes: index.html, apps/<id>/index.html, contact/index.html, mvp.html,
404.html, sitemap.xml, llms.txt. Standard library only. The output is
committed, so GitHub Pages serves plain files with no build step.

    python3 scripts/render.py          # write files
    python3 scripts/render.py --check  # exit 1 if committed output is stale

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
    robots = '<meta name="robots" content="noindex">' if noindex else '<meta name="robots" content="index, follow, max-image-preview:large">'
    og = SITE + og_image
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{canonical}">
{robots}
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
<script>(function(){{var d=document.documentElement;d.classList.add("js");try{{var t=localStorage.getItem("theme");if(t)d.setAttribute("data-theme",t)}}catch(e){{}}}})();</script>
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
  <button class="theme-toggle" type="button" aria-label="Toggle dark mode">{icon("moon", "i-moon")}{icon("sun", "i-sun")}</button>
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


def store_buttons(app, primary_first=True):
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
    if links.get("home"):
        out.append(f'<a class="btn btn-glass glass" href="/apps/{app["id"]}/{links["home"]}">Product site</a>')
    return f'<div class="btns">{"".join(out)}</div>'


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
        cell(live["flowmoro"], f'<div class="cell-shots">{shot("flowmoro", 2)}{shot("flowmoro", 3)}</div>'),
        cell(live["skywise"]),
        cell(live["astrodefender"], dark=True),
        cell(live["inboxhiiv"], f'<div class="cell-shots">{shot("inboxhiiv", 1)}</div>'),
        cell(live["nookly"], f'<div class="cell-shots">{shot("nookly", 1)}</div>'),
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
  <div class="phone p0">{shot("flowmoro", 0, eager=True)}</div>
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
    <p class="meta">Email the studio. A person reads every message.</p>
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
        rail = f'<section aria-label="Screenshots"><div class="rail" tabindex="0">\n{figs}\n</div></section>'

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
    <div class="btns"><a class="btn btn-accent" href="mailto:{EMAIL}">{icon("envelope-simple")}{EMAIL}</a></div>
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
    for name, text in files.items():
        if "\u2014" in text or "\u2013" in text:
            raise SystemExit(f"{name}: contains an em or en dash")
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
