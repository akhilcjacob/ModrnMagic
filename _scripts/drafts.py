#!/usr/bin/env python3
"""Held drafts: content Akhil has not confirmed, kept out of the published tree.

GitHub Pages skips `_` folders, so everything here is unpublished:

    _drafts/drafts.json          {"order": [every id, drafts included], "lines": {id: {outcome?, lessons?}}}
    _drafts/apps/<id>/           a draft product: app.json (with "draft": true) and media/
    _drafts/assets/og/<id>.jpg   its share card

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


def _write(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def held(root=ROOT):
    """(drafts.json data, draft product ids) for a tree; empty when nothing is held."""
    path = os.path.join(root, "_drafts/drafts.json")
    if not os.path.exists(path):
        return {"order": [], "lines": {}}, []
    data = json.load(open(path))
    apps_dir = os.path.join(root, "_drafts/apps")
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
    """Merge _drafts/ into apps/ of a copy of the site and remove _drafts/. Never call on the repo."""
    if os.path.abspath(root) == ROOT:
        raise SystemExit("merge() rewrites apps/; run it on a copy, not the repo")
    data, products = held(root)
    if not products and not data["lines"]:
        return
    order = merged_order(root, data, products)
    for aid in products:
        shutil.move(os.path.join(root, "_drafts/apps", aid), os.path.join(root, "apps", aid))
    og = os.path.join(root, "_drafts/assets/og")
    if os.path.isdir(og):
        for name in os.listdir(og):
            shutil.move(os.path.join(og, name), os.path.join(root, "assets/og", name))
    for aid, line in data["lines"].items():
        path = os.path.join(root, "apps", aid, "app.json")
        _write(path, merge_app(json.load(open(path)), line))
    _write(os.path.join(root, "apps/index.json"), order)
    shutil.rmtree(os.path.join(root, "_drafts"))


def merged_apps(root=ROOT):
    """Every product with the held drafts merged, in memory, in preview order."""
    data, products = held(root)
    out = []
    for aid in merged_order(root, data, products):
        base = "_drafts/apps" if aid in products else "apps"
        app = json.load(open(os.path.join(root, base, aid, "app.json")))
        out.append(merge_app(app, data["lines"][aid]) if aid in data["lines"] else app)
    return out


def listing(root=ROOT):
    data, products = held(root)
    out = [f"_drafts/apps/{p}: the product is a draft" for p in products]
    for aid, line in data["lines"].items():
        if line.get("outcome"):
            out.append(f"_drafts/drafts.json {aid}: outcome line is a draft")
        out += [f"_drafts/drafts.json {aid}: lesson is a draft: {x['text'][:50]}" for x in line.get("lessons", [])]
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
        src, dst = os.path.join(ROOT, "_drafts/apps", aid), os.path.join(ROOT, "apps", aid)
        shutil.move(src, dst)
        og = os.path.join(ROOT, "_drafts/assets/og", f"{aid}.jpg")
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
        _write(os.path.join(ROOT, "_drafts/drafts.json"), data)
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
