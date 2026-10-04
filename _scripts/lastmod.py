"""Sitemap lastmod from page content, never from git or from the day a check runs.

`_scripts/lastmod.json` maps each sitemap URL to the file its date follows and
a hash of that file:

    {"/work/": {"src": "work/index.html", "sha": "...", "date": "2026-10-03"}}

`render.py` keeps an entry's date while the hash still matches and sets it to
today when the content changed (`SOURCE_DATE_EPOCH` overrides today). So a
merge or a re-check on a later day changes nothing, and `check.py --release`
only tests that the sitemap, this file, and the files on disk agree.

Legal pages follow their Markdown source, so a change to the site chrome does
not move a policy's date. Every other page follows its rendered HTML, with the
footer's copyright year masked (the year comes from these dates).
"""
import datetime as dt
import hashlib
import json
import os
import re

FILE = "_scripts/lastmod.json"
YEAR = re.compile(r"&copy; \d{4} ")


def digest(text):
    return hashlib.sha256(YEAR.sub("&copy; YEAR ", text).encode("utf-8")).hexdigest()[:16]


def today():
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).date().isoformat()
    return dt.date.today().isoformat()


def load(root):
    try:
        with open(os.path.join(root, FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def dump(data):
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def problems(root, sitemap_text):
    """Every way the sitemap, lastmod.json, and the files on disk disagree."""
    data = load(root)
    out = []
    locs = re.findall(r"<loc>https://[^/<]+(/[^<]*)</loc><lastmod>([^<]+)</lastmod>", sitemap_text)
    for url, lastmod in locs:
        entry = data.get(url)
        if not entry:
            out.append(f"sitemap.xml: {url} has no entry in {FILE} (run render.py)")
            continue
        if entry["date"] != lastmod:
            out.append(f"sitemap.xml: {url} says {lastmod}, {FILE} says {entry['date']} (run render.py)")
        try:
            with open(os.path.join(root, entry["src"]), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            out.append(f"{FILE}: {url} follows {entry['src']}, which is missing")
            continue
        if digest(text) != entry["sha"]:
            out.append(f"{entry['src']}: changed since its lastmod {entry['date']} was set (run render.py)")
    extra = sorted(set(data) - {u for u, _ in locs})
    for url in extra:
        out.append(f"{FILE}: {url} is not in sitemap.xml (run render.py)")
    return out
