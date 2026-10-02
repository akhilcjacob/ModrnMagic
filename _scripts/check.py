"""Serve the site locally, or check that every internal link and asset resolves.

    python3 _scripts/check.py          # run the checks, exit 1 on any failure
    python3 _scripts/check.py serve    # serve at http://localhost:8000 (PORT=xxxx to change)
    python3 _scripts/check.py --release  # also fail while any draft remains in data or in published HTML

Python 3 standard library only. The checks cover the files GitHub Pages would
publish (everything outside `_`-prefixed and hidden folders):

- every href, src, srcset, and CSS url() that points inside the site resolves
  to a file, including absolute https://modrnmagic.app/ URLs in meta tags and
  JSON-LD
- every relative path in product JSON (app.json, flowmoro/home) resolves;
  app.json `icon` and screenshot `from` point at originals in _src/apps/<id>/
- every sitemap.xml <loc> maps to a file
- nothing still mentions the removed "00_Future App Template" folder
"""
import functools
import http.server
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://modrnmagic.app"
TEXT_EXT = {".html", ".css", ".js", ".json", ".xml", ".txt", ".md"}
ASSET_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".woff2", ".css", ".js", ".json", ".html"}
SKIP_SCHEMES = ("mailto:", "tel:", "data:", "javascript:", "#", "sms:")
ABS_URL = re.compile(r"https://modrnmagic\.app(/[^\s\"'<>)\\]*)?")
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
REMOVED = ("00_Future", "Future App Template", "Future%20App%20Template")


def published_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))]
        for name in filenames:
            if not name.startswith("."):
                yield os.path.join(dirpath, name)


def resolve(path):
    """Map a site path (already decoded, no query) to a file, like GitHub Pages does."""
    full = os.path.join(ROOT, path.lstrip("/"))
    if path.endswith("/"):
        return os.path.isfile(os.path.join(full, "index.html"))
    return os.path.isfile(full) or os.path.isfile(os.path.join(full, "index.html")) or os.path.isfile(full + ".html")


def target(ref, src_file):
    """Return the site path a reference points to, or None if it is external."""
    ref = ref.strip()
    if not ref or ref.startswith(SKIP_SCHEMES) or "${" in ref:
        return None
    if ref.startswith(SITE):
        ref = ref[len(SITE):] or "/"
    elif "://" in ref or ref.startswith("//"):
        return None
    path = unquote(urlsplit(ref).path)
    if not path:
        return None
    if not path.startswith("/"):
        base = "/" + os.path.relpath(os.path.dirname(src_file), ROOT).replace(os.sep, "/")
        path = os.path.normpath(os.path.join(base, path)).replace(os.sep, "/") + ("/" if path.endswith("/") else "")
    return path


class Refs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if v is None:
                continue
            if k in ("href", "src", "poster", "action"):
                self.refs.append(v)
            elif k in ("srcset", "imagesrcset"):
                self.refs += [part.split()[0] for part in v.split(",") if part.strip()]


SOURCE_KEYS = ("icon", "from")   # app.json keys that name originals in _src/apps/<id>/


def json_paths(data, key=None, skip=()):
    """Yield relative file paths in product JSON: strings with an asset extension or ending in /."""
    if isinstance(data, dict):
        for k, v in data.items():
            if k not in skip:
                yield from json_paths(v, k, skip)
    elif isinstance(data, list):
        for v in data:
            yield from json_paths(v, key, skip)
    elif isinstance(data, str) and "://" not in data and not data.startswith(SKIP_SCHEMES):
        is_file = os.path.splitext(data)[1].lower() in ASSET_EXT
        if ("/" in data or key == "icon") and (is_file or data.endswith("/")) and " " not in data:
            yield data


def source_paths(data):
    """Originals named by app.json: the icon and each screenshot's `from`."""
    if data.get("icon"):
        yield data["icon"]
    for shot in data.get("screenshots", []):
        yield shot["from"]


def check():
    errors = []

    def need(path, src, ref):
        if path is not None and not resolve(path):
            errors.append(f"{os.path.relpath(src, ROOT)}: missing {ref}")

    for f in published_files():
        ext = os.path.splitext(f)[1].lower()
        if ext not in TEXT_EXT:
            continue
        with open(f, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for word in REMOVED:
            if word in text:
                errors.append(f"{os.path.relpath(f, ROOT)}: still mentions {word}")
        refs = [m.group(0) for m in ABS_URL.finditer(text)]
        if ext == ".html":
            p = Refs()
            p.feed(text)
            refs += p.refs
            refs += CSS_URL.findall(text)
        elif ext == ".css":
            refs += CSS_URL.findall(text)
        elif ext == ".md":
            refs += MD_LINK.findall(text)
        elif ext == ".json" and f.startswith(os.path.join(ROOT, "apps") + os.sep):
            try:
                data = json.loads(text)
            except ValueError as err:
                errors.append(f"{os.path.relpath(f, ROOT)}: bad JSON ({err})")
                data = None
            if os.path.basename(f) == "app.json" and isinstance(data, dict):
                refs += list(json_paths(data, skip=SOURCE_KEYS))
                src = os.path.join(ROOT, "_src", os.path.relpath(os.path.dirname(f), ROOT))
                for rel in source_paths(data):
                    if not os.path.isfile(os.path.join(src, rel)):
                        errors.append(f"{os.path.relpath(f, ROOT)}: missing original _src/{os.path.relpath(os.path.join(src, rel), os.path.join(ROOT, '_src'))}")
            elif data is not None:
                refs += list(json_paths(data))
        for ref in dict.fromkeys(refs):
            need(target(ref, f), f, ref)

    sitemap = os.path.join(ROOT, "sitemap.xml")
    locs = re.findall(r"<loc>([^<]+)</loc>", open(sitemap, encoding="utf-8").read())
    if not locs:
        errors.append("sitemap.xml: no <loc> entries")
    for loc in locs:
        if not loc.startswith(SITE + "/"):
            errors.append(f"sitemap.xml: off-site URL {loc}")
        else:
            need(target(loc, sitemap), sitemap, loc)

    errors = list(dict.fromkeys(errors))
    for line in errors:
        print("FAIL", line)
    print(f"{'FAILED' if errors else 'OK'}: {len(errors)} problem(s), {len(locs)} sitemap URLs checked")
    return 1 if errors else 0


def drafts():
    """Every draft in product data: draft pages, outcome lines, and lessons."""
    out = []
    for name in json.load(open(os.path.join(ROOT, "apps/index.json"))):
        app = json.load(open(os.path.join(ROOT, "apps", name, "app.json")))
        if app.get("draft"):
            out.append(f"apps/{name}: the page is a draft")
        if (app.get("outcome") or {}).get("draft"):
            out.append(f"apps/{name}: outcome line is a draft")
        out += [f"apps/{name}: lesson is a draft: {x['text'][:50]}" for x in app.get("lessons", []) if x.get("draft")]
    return out


DRAFT_MARKERS = ('class="draft-mark"', 'class="draft-banner')


def draft_output():
    """Published HTML that still carries a draft marker: a local build a merge would publish."""
    out = []
    for f in sorted(published_files()):
        if f.endswith(".html"):
            text = open(f, encoding="utf-8", errors="replace").read()
            if any(m in text for m in DRAFT_MARKERS):
                out.append(os.path.relpath(f, ROOT))
    return out


def release():
    status = check()
    pending = drafts()
    for line in pending:
        print("DRAFT", line)
    leaked = draft_output()
    for rel in leaked:
        print("DRAFT OUTPUT", f"{rel}: draft marker in published HTML (run render.py --release)")
    print(f"{'NOT READY' if pending or leaked else 'READY'}: {len(pending)} draft(s) need Akhil's confirmation, "
          f"{len(leaked)} published page(s) carry draft output")
    return 1 if status or pending or leaked else 0


def serve():
    port = int(os.environ.get("PORT", "8000"))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    print(f"Serving {ROOT} at http://localhost:{port}/ (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    if sys.argv[1:] == ["serve"]:
        serve()
    elif sys.argv[1:] == ["--release"]:
        sys.exit(release())
    elif not sys.argv[1:]:
        sys.exit(check())
    else:
        sys.exit(__doc__)
