#!/usr/bin/env python3
"""Make web-sized copies of product images and the site icons.

Reads each apps/<id>/app.json and writes apps/<id>/media/*.webp from the
`from` path of every screenshot, plus a small icon. Also writes favicons and
the nav mark from favicon.ico. Needs Pillow (with WebP support). Only rerun
when source images change; the output is committed.

    python3 _scripts/images.py
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHONE_W = 640   # phone shots display at ~300px wide; 2x plus a little
WIDE_W = 1600   # wide shots display at up to ~760px wide


def save_webp(im, path, width, quality=80):
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "WEBP", quality=quality, method=6)
    return im.size


def main():
    ids = json.load(open(os.path.join(ROOT, "apps/index.json")))
    for app_id in ids:
        folder = os.path.join(ROOT, "apps", app_id)
        path = os.path.join(folder, "app.json")
        app = json.load(open(path))
        for shot in app.get("screenshots", []):
            im = Image.open(os.path.join(folder, shot["from"])).convert("RGB")
            width = WIDE_W if shot.get("shape") == "wide" else PHONE_W
            shot["w"], shot["h"] = save_webp(im, os.path.join(folder, shot["src"]), width)
        if app.get("icon"):
            icon = Image.open(os.path.join(folder, app["icon"])).convert("RGBA")
            for size in (96, 256):
                out = os.path.join(folder, "media", f"icon-{size}.webp")
                icon.resize((size, size), Image.LANCZOS).save(out, "WEBP", quality=88, method=6)
        with open(path, "w") as f:
            json.dump(app, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("ok", app_id)

    mark = Image.open(os.path.join(ROOT, "favicon.ico")).convert("RGBA")
    out = os.path.join(ROOT, "assets/img")
    os.makedirs(out, exist_ok=True)
    mark.resize((96, 96), Image.LANCZOS).save(os.path.join(out, "mark-96.webp"), "WEBP", quality=90, method=6)
    mark.resize((32, 32), Image.LANCZOS).save(os.path.join(out, "favicon-32.png"))
    for size in (180, 192, 512):
        tile = Image.new("RGBA", (size, size), (250, 251, 252, 255))
        inner = round(size * 0.78)
        m = mark.resize((inner, inner), Image.LANCZOS)
        tile.paste(m, ((size - inner) // 2, (size - inner) // 2), m)
        name = "apple-touch-icon.png" if size == 180 else f"icon-{size}.png"
        tile.convert("RGB").save(os.path.join(out, name), optimize=True)
    print("ok icons")


if __name__ == "__main__":
    main()
