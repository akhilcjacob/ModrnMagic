#!/usr/bin/env python3
"""Held drafts: content Akhil has not confirmed, kept out of git and the published tree.

They live in .drafts/, a local folder that .gitignore keeps out of the public
repository (GitHub Pages skips hidden folders too):

    .drafts/drafts.json          {"order": [every id, drafts included], "lines": {id: {outcome?, lessons?}}}
    .drafts/apps/<id>/           a draft product: app.json (with "draft": true) and media/
    .drafts/assets/og/<id>.jpg   its share card
    .drafts/src/apps/<id>/       its originals (icon, screenshots), _src/apps/<id>/ once promoted

A fresh clone has no .drafts/, which reads as "nothing held".

The committed tree is the release build. The preview merges the drafts into a
copy of the site, so they can be reviewed with their Draft marks.

    python3 _scripts/drafts.py           # list held drafts
    python3 _scripts/drafts.py preview   # build _preview/ (gitignored) with drafts merged
    python3 _scripts/drafts.py promote <id>  # Akhil said yes: publish that product or its lines

`promote` moves a draft product into apps/ (at its place in `order`) with the
flag cleared, or moves a product's draft outcome and lessons into its
apps/<id>/app.json as confirmed. Then run render.py and commit. Standard
library only.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS = ".drafts"   # relative to the site root; gitignored


def _write(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def held(root=ROOT, folder=None):
    """(drafts.json data, draft product ids) for a tree, or for another drafts
    `folder` (the test fixture); empty when nothing is held."""
    folder = folder or os.path.join(root, DRAFTS)
    path = os.path.join(folder, "drafts.json")
    if not os.path.exists(path):
        return {"order": [], "lines": {}}, []
    data = json.load(open(path))
    apps_dir = os.path.join(folder, "apps")
    products = sorted(os.listdir(apps_dir)) if os.path.isdir(apps_dir) else []
    return data, [p for p in products if os.path.isfile(os.path.join(apps_dir, p, "app.json"))]


def merged_order(root, data, products):
    """Published ids plus draft products, in drafts.json order (unknown ids keep their place at the end)."""
    ids = json.load(open(os.path.join(root, "apps/index.json")))
    want = set(ids) | set(products)
    order = [i for i in data.get("order", []) if i in want]
    return order + [i for i in ids + products if i not in order]


def merge_app(app, line):
    """One product's data with its held lines added as drafts."""
    if line.get("outcome"):
        app["outcome"] = dict(line["outcome"], draft=True)
    app["lessons"] = app.get("lessons", []) + [dict(x, draft=True) for x in line.get("lessons", [])]
    return app


def merge(root):
    """Merge .drafts/ into apps/ of a copy of the site and remove .drafts/. Never call on the repo."""
    if os.path.abspath(root) == ROOT:
        raise SystemExit("merge() rewrites apps/; run it on a copy, not the repo")
    if not os.path.isdir(os.path.join(root, DRAFTS)):
        return
    data, products = held(root)
    order = merged_order(root, data, products)
    for aid in products:
        shutil.move(os.path.join(root, DRAFTS, "apps", aid), os.path.join(root, "apps", aid))
        move_src(root, aid)
    og = os.path.join(root, DRAFTS, "assets/og")
    if os.path.isdir(og):
        for name in os.listdir(og):
            shutil.move(os.path.join(og, name), os.path.join(root, "assets/og", name))
    for aid, line in data["lines"].items():
        path = os.path.join(root, "apps", aid, "app.json")
        _write(path, merge_app(json.load(open(path)), line))
    _write(os.path.join(root, "apps/index.json"), order)
    shutil.rmtree(os.path.join(root, DRAFTS))


def move_src(root, aid):
    """A held product's originals go to _src/apps/<id>/, where images.py and check.py expect them."""
    src = os.path.join(root, DRAFTS, "src/apps", aid)
    if os.path.isdir(src):
        dst = os.path.join(root, "_src/apps", aid)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.move(src, dst)


def merged_apps(root=ROOT, folder=None):
    """Every product with the held drafts merged, in memory, in preview order."""
    folder = folder or os.path.join(root, DRAFTS)
    data, products = held(root, folder)
    out = []
    for aid in merged_order(root, data, products):
        base = os.path.join(folder, "apps") if aid in products else os.path.join(root, "apps")
        app = json.load(open(os.path.join(base, aid, "app.json")))
        out.append(merge_app(app, data["lines"][aid]) if aid in data["lines"] else app)
    return out


def listing(root=ROOT):
    data, products = held(root)
    out = [f"{DRAFTS}/apps/{p}: the product is a draft" for p in products]
    for aid, line in data["lines"].items():
        if line.get("outcome"):
            out.append(f"{DRAFTS}/drafts.json {aid}: outcome line is a draft")
        out += [f"{DRAFTS}/drafts.json {aid}: lesson is a draft: {x['text'][:50]}" for x in line.get("lessons", [])]
    return out


def preview():
    """Copy the site to _preview/, merge the drafts, and run the local build there."""
    dest = os.path.join(ROOT, "_preview")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "_attic", "_preview"))
    # merge() refuses ROOT; _preview is a separate tree.
    merge(dest)
    r = subprocess.run([sys.executable, "_scripts/render.py"], cwd=dest, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stdout + r.stderr)
    return dest


def promote(aid):
    data, products = held()
    if aid in products:
        order = merged_order(ROOT, data, products)
        ids = json.load(open(os.path.join(ROOT, "apps/index.json")))
        src, dst = os.path.join(ROOT, DRAFTS, "apps", aid), os.path.join(ROOT, "apps", aid)
        shutil.move(src, dst)
        move_src(ROOT, aid)
        og = os.path.join(ROOT, DRAFTS, "assets/og", f"{aid}.jpg")
        if os.path.exists(og):
            shutil.move(og, os.path.join(ROOT, "assets/og", f"{aid}.jpg"))
        path = os.path.join(dst, "app.json")
        app = json.load(open(path))
        app.pop("draft", None)
        _write(path, app)
        _write(os.path.join(ROOT, "apps/index.json"), [i for i in order if i in ids or i == aid])
        print(f"promoted product {aid}")
    elif aid in data["lines"]:
        path = os.path.join(ROOT, "apps", aid, "app.json")
        app = merge_app(json.load(open(path)), data["lines"].pop(aid))
        if app.get("outcome"):
            app["outcome"]["draft"] = False
        for x in app["lessons"]:
            x["draft"] = False
        _write(path, app)
        _write(os.path.join(ROOT, DRAFTS, "drafts.json"), data)
        print(f"promoted the outcome and lessons of {aid}")
    else:
        raise SystemExit(f"nothing held for {aid}")
    print("next: python3 _scripts/render.py, then the launch checklist in _docs/APPS.md")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        lines = listing()
        print("\n".join(lines) if lines else "nothing held")
        print(f"{len(lines)} held draft(s)")
    elif args == ["preview"]:
        print("built", os.path.relpath(preview(), ROOT) + "/; serve it with: python3 _scripts/check.py serve --drafts")
    elif len(args) == 2 and args[0] == "promote":
        promote(args[1])
    else:
        sys.exit(__doc__)
