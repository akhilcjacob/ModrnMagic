#!/usr/bin/env python3
"""Render 1200x630 OpenGraph cards to assets/og/*.jpg with headless Chrome.

Held draft products (.drafts/apps/<id>/, gitignored) get their card in .drafts/assets/og/,
so it stays unpublished until the draft is promoted. Needs Google Chrome and Pillow. Rerun when a product's name, one-liner, icon,
or color changes; the output is committed.

    python3 _scripts/og.py                    # every card
    python3 _scripts/og.py ramble hypebridge  # only these products (no home card)
    python3 _scripts/og.py --check            # exit 1 if a published card is stale (no Chrome or Pillow needed)

Each render records, in _scripts/og.json, a hash of the card's inputs (its HTML, which holds the
product's name, one-liner, color, tint, status, and platforms, plus the bytes of every file the HTML
loads: icon, mark, font) and a hash of the JPEG it wrote. --check rebuilds the HTML from the current
data and fails when an input hash differs (the card needs a rerender), when a file the card loads is
missing, when a JPEG no longer matches its recorded hash, or when a published product has no card or a
card has no product. The render settings (SHOT: Chrome flags, crop, JPEG options) are part of the input
hash too. It compares inputs, not pixels, so it gives the same answer on any OS and Chrome version; a
new Chrome that draws the same HTML differently is not caught.
"""
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import fill, glow, listed, load_apps  # noqa: E402  validated data with {name} filled in, and the site's tint rule

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
e = html.escape

BASE_CSS = f"""
@font-face {{ font-family: F; src: url("file://{ROOT}/assets/fonts/figtree-var.woff2"); font-weight: 300 900; }}
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ width: 1200px; height: 630px; overflow: hidden; }}
body {{ font-family: F, sans-serif; color: #14161b; background: #eef0f4; position: relative; }}
.wash {{ position: absolute; inset: 0; background:
  radial-gradient(520px 420px at 6% 0%, rgb(255 122 89 / .30), transparent 70%),
  radial-gradient(560px 460px at 100% 10%, rgb(80 170 255 / .26), transparent 70%),
  radial-gradient(620px 420px at 60% 110%, rgb(120 220 160 / .24), transparent 70%); }}
.card {{ position: absolute; inset: 48px; border-radius: 40px; background: rgb(255 255 255 / .62);
  border: 1px solid rgb(20 24 34 / .08); box-shadow: inset 0 1px 0 #fff, 0 24px 60px rgb(20 24 34 / .10);
  padding: 64px 72px; display: flex; flex-direction: column; }}
.brand {{ display: flex; align-items: center; gap: 14px; font-size: 28px; font-weight: 650; letter-spacing: -.01em; }}
.brand img {{ width: 44px; height: 44px; }}
.foot {{ margin-top: auto; display: flex; justify-content: space-between; align-items: center; font-size: 24px; color: #5f6674; font-weight: 550; }}
.icon {{ border-radius: 22.5%; overflow: hidden; box-shadow: 0 0 0 1px rgb(20 24 34 / .08), 0 16px 40px rgb(20 24 34 / .18); flex: none; }}
.icon img {{ width: 100%; height: 100%; display: block; }}
.mono {{ display: grid; place-items: center; font-weight: 700; color: #14161b; }}
"""


MANIFEST = "_scripts/og.json"
FILE_REF = re.compile(r"file://" + re.escape(ROOT) + r"/([^\"')\s]+)")


# How a card's HTML becomes a JPEG. Part of every card's input hash, so changing one marks every card stale.
SHOT = {"chrome_flags": ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                         "--allow-file-access-from-files", "--virtual-time-budget=1500", "--window-size=1200,630"],
        "crop": [0, 0, 1200, 630], "jpeg": {"quality": 86, "optimize": True, "progressive": True}}


class MissingInput(Exception):
    """A file the card HTML loads (icon, mark, font) does not exist."""


def shoot(markup, out_jpg):
    from PIL import Image   # only rendering needs Pillow; --check runs on the standard library
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "og.html")
        png = os.path.join(tmp, "og.png")
        with open(page, "w") as f:
            f.write(markup)
        subprocess.run([CHROME, *SHOT["chrome_flags"], f"--screenshot={png}", f"file://{page}"], check=True, capture_output=True)
        Image.open(png).convert("RGB").crop(tuple(SHOT["crop"])).save(out_jpg, "JPEG", **SHOT["jpeg"])


def icon_markup(app, size, base="apps"):
    if app.get("icon"):
        return (f'<div class="icon" style="width:{size}px;height:{size}px;background:{app["color"]}">'
                f'<img src="file://{ROOT}/{base}/{app["id"]}/media/icon-256.webp"></div>')
    return (f'<div class="icon mono" style="width:{size}px;height:{size}px;background:{app["color"]};font-size:{size * .42}px">'
            f'{e(app["name"][0])}</div>')


def cards(only=(), drafts=True):
    """(card path relative to ROOT, HTML) for each card: home first, then each product.
    Held drafts' cards go to .drafts/assets/og/, as rendering puts them; drafts=False
    leaves them out (the published cards only). A .drafts/apps/ entry that is not a
    folder with an app.json (a .DS_Store, a half-made draft) is skipped."""
    out_dir = "assets/og"
    apps = load_apps()
    mark = f"file://{ROOT}/assets/img/mark-96.webp"
    out = []

    live_icons = "".join(icon_markup(a, 92) for a in listed(apps) if a["status"] == "live")
    home = f"""<!doctype html><html><head><style>{BASE_CSS}
h1 {{ font-size: 76px; line-height: 1.02; letter-spacing: -.035em; font-weight: 650; margin-top: 44px; max-width: 15ch; }}
h1 span {{ color: #5f6674; }}
.row {{ display: flex; gap: 18px; }}
</style></head><body><div class="wash"></div><div class="card">
<div class="brand"><img src="{mark}">Modrn Magic</div>
<h1>Independent apps for <span>everyday things.</span></h1>
<div class="foot"><div class="row">{live_icons}</div><span>modrnmagic.app</span></div>
</div></body></html>"""
    if not only:
        out.append((f"{out_dir}/home.jpg", home))

    status = {"live": "", "lab": "Experiment", "archived": "Archived"}
    held = os.path.join(ROOT, ".drafts/apps")
    jobs = [(a, "apps", out_dir) for a in apps]
    if drafts and os.path.isdir(held):
        for aid in sorted(os.listdir(held)):
            if not os.path.isfile(os.path.join(held, aid, "app.json")):
                continue
            a = json.load(open(os.path.join(held, aid, "app.json")))
            jobs.append((fill(a, a["name"]), ".drafts/apps", ".drafts/assets/og"))
    for app, base, card_dir in jobs:
        if only and app["id"] not in only:
            continue
        badge = f'<span style="margin-left:16px;font-size:24px;letter-spacing:0;color:#875700;font-weight:650">{status[app["status"]]}</span>' if status[app["status"]] else ""
        # The same tint rule as the site (render.glow): `tint` wins, and a near-neutral or near-black
        # color gets no wash, since it would only smudge the corner grey.
        g = glow(app)
        wash = (f'.wash::after {{ content: ""; position: absolute; inset: 0; background: radial-gradient(640px 520px at 100% 0%, {g}, transparent 70%); opacity: .7; }}'
                if g else "")
        markup = f"""<!doctype html><html><head><style>{BASE_CSS}
{wash}
.main {{ display: flex; gap: 48px; align-items: center; margin-top: 52px; }}
h1 {{ font-size: 84px; line-height: 1; letter-spacing: -.035em; font-weight: 650; display: flex; align-items: baseline; }}
p {{ font-size: 36px; line-height: 1.25; color: #474d59; margin-top: 18px; max-width: 22ch; letter-spacing: -.01em; }}
</style></head><body><div class="wash"></div><div class="card">
<div class="brand"><img src="{mark}">Modrn Magic</div>
<div class="main">{icon_markup(app, 200, base)}<div><h1>{e(app["name"])}{badge}</h1><p>{e(app["oneliner"])}</p></div></div>
<div class="foot"><span>{e(", ".join({"ios": "iPhone", "android": "Android", "web": "Web"}[p] for p in app["platforms"]))}</span><span>modrnmagic.app/apps/{app["id"]}</span></div>
</div></body></html>"""
        out.append((f"{card_dir}/{app['id']}.jpg", markup))
    return out


def sha(data):
    return hashlib.sha256(data).hexdigest()[:16]


def inputs(markup):
    """A hash of everything that decides how a card looks: its HTML (with this checkout's
    path taken out), the render settings (SHOT), and the bytes of each file it loads.
    Raises MissingInput when one of those files does not exist."""
    h = hashlib.sha256(markup.replace(ROOT, "ROOT").encode("utf-8"))
    h.update(json.dumps(SHOT, sort_keys=True).encode())
    for rel in sorted(set(FILE_REF.findall(markup))):
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            raise MissingInput(rel)
        h.update(f"\0{rel}\0".encode() + open(path, "rb").read())
    return h.hexdigest()[:16]


def load_manifest():
    path = os.path.join(ROOT, MANIFEST)
    return json.load(open(path)) if os.path.isfile(path) else {}


def main(only):
    manifest = load_manifest()
    jobs = cards(only)
    unknown = sorted(set(only) - {os.path.basename(rel)[:-4] for rel, _ in jobs})
    if unknown:
        sys.exit(f"og.py: no product with id {', '.join(unknown)}")
    for rel, markup in jobs:
        try:
            inputs(markup)
        except MissingInput as err:
            sys.exit(f"og.py: {rel} needs {err}, which does not exist; nothing was rendered")
    for rel, markup in jobs:
        out = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shoot(markup, out)
        if rel.startswith("assets/og/"):   # held drafts' cards stay out of the published record
            manifest[rel] = {"inputs": inputs(markup), "card": sha(open(out, "rb").read())}
        print("ok", rel)
    published = {rel for rel, _ in cards(drafts=False)}
    manifest = {k: v for k, v in sorted(manifest.items()) if k in published}
    with open(os.path.join(ROOT, MANIFEST), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def check():
    """Problems with the published cards, as lines; empty when every card is current."""
    manifest = load_manifest()
    want = dict(cards(drafts=False))
    out = []
    for rel, markup in want.items():
        path = os.path.join(ROOT, rel)
        entry = manifest.get(rel)
        redo = "run python3 _scripts/og.py" + ("" if rel.endswith("/home.jpg") else f" {os.path.basename(rel)[:-4]}")
        try:
            current = inputs(markup)
        except MissingInput as err:
            out.append(f"{rel}: missing input {err} (restore it, then check again)")
            continue
        if not os.path.isfile(path):
            out.append(f"{rel}: missing; {redo}")
        elif not entry:
            out.append(f"{rel}: not in {MANIFEST}; {redo}")
        elif entry["inputs"] != current:
            out.append(f"{rel}: stale (its name, one-liner, color, status, platforms, icon, template, or render settings changed); {redo}")
        elif entry["card"] != sha(open(path, "rb").read()):
            out.append(f"{rel}: the JPEG changed outside og.py; {redo}")
    for rel in sorted(set(manifest) - set(want)):
        out.append(f"{rel}: in {MANIFEST} but no published product uses it; run python3 _scripts/og.py")
    published_dir = os.path.join(ROOT, "assets/og")
    for name in sorted(os.listdir(published_dir)) if os.path.isdir(published_dir) else ():
        if name.endswith(".jpg") and f"assets/og/{name}" not in want:
            out.append(f"assets/og/{name}: a card for no published product")
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        problems = check()
        for line in problems:
            print("STALE CARD", line)
        print(f"{'FAILED' if problems else 'OK'}: {len(problems)} share card problem(s)")
        sys.exit(1 if problems else 0)
    main(sys.argv[1:])
