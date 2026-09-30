#!/usr/bin/env python3
"""Render 1200x630 OpenGraph cards to assets/og/*.jpg with headless Chrome.

Needs Google Chrome and Pillow. Rerun when a product's name, one-liner, icon,
or color changes; the output is committed.

    python3 _scripts/og.py
"""
import html
import json
import os
import subprocess
import tempfile

from PIL import Image

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


def shoot(markup, out_jpg):
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "og.html")
        png = os.path.join(tmp, "og.png")
        with open(page, "w") as f:
            f.write(markup)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--allow-file-access-from-files", "--virtual-time-budget=1500",
                        "--window-size=1200,630", f"--screenshot={png}", f"file://{page}"],
                       check=True, capture_output=True)
        Image.open(png).convert("RGB").crop((0, 0, 1200, 630)).save(out_jpg, "JPEG", quality=86, optimize=True, progressive=True)


def icon_markup(app, size):
    if app.get("icon"):
        return (f'<div class="icon" style="width:{size}px;height:{size}px;background:{app["color"]}">'
                f'<img src="file://{ROOT}/apps/{app["id"]}/media/icon-256.webp"></div>')
    return (f'<div class="icon mono" style="width:{size}px;height:{size}px;background:{app["color"]};font-size:{size * .42}px">'
            f'{e(app["name"][0])}</div>')


def main():
    out_dir = os.path.join(ROOT, "assets/og")
    os.makedirs(out_dir, exist_ok=True)
    ids = json.load(open(os.path.join(ROOT, "apps/index.json")))
    apps = [json.load(open(os.path.join(ROOT, "apps", i, "app.json"))) for i in ids]
    mark = f"file://{ROOT}/assets/img/mark-96.webp"

    live_icons = "".join(icon_markup(a, 92) for a in apps if a["status"] == "live")
    home = f"""<!doctype html><html><head><style>{BASE_CSS}
h1 {{ font-size: 76px; line-height: 1.02; letter-spacing: -.035em; font-weight: 650; margin-top: 44px; max-width: 15ch; }}
h1 span {{ color: #5f6674; }}
.row {{ display: flex; gap: 18px; }}
</style></head><body><div class="wash"></div><div class="card">
<div class="brand"><img src="{mark}">Modrn Magic</div>
<h1>Independent apps for <span>everyday things.</span></h1>
<div class="foot"><div class="row">{live_icons}</div><span>modrnmagic.app</span></div>
</div></body></html>"""
    shoot(home, os.path.join(out_dir, "home.jpg"))
    print("ok home")

    status = {"live": "", "lab": "In the lab", "archived": "Archived"}
    for app in apps:
        badge = f'<span style="margin-left:16px;font-size:24px;color:#875700;font-weight:650">{status[app["status"]]}</span>' if status[app["status"]] else ""
        markup = f"""<!doctype html><html><head><style>{BASE_CSS}
.wash::after {{ content: ""; position: absolute; inset: 0; background: radial-gradient(640px 520px at 100% 0%, {app["color"]}, transparent 70%); opacity: .7; }}
.main {{ display: flex; gap: 48px; align-items: center; margin-top: 52px; }}
h1 {{ font-size: 84px; line-height: 1; letter-spacing: -.035em; font-weight: 650; display: flex; align-items: baseline; }}
p {{ font-size: 36px; line-height: 1.25; color: #474d59; margin-top: 18px; max-width: 22ch; letter-spacing: -.01em; }}
</style></head><body><div class="wash"></div><div class="card">
<div class="brand"><img src="{mark}">Modrn Magic</div>
<div class="main">{icon_markup(app, 200)}<div><h1>{e(app["name"])}{badge}</h1><p>{e(app["oneliner"])}</p></div></div>
<div class="foot"><span>{e(", ".join({"ios": "iPhone", "android": "Android", "web": "Web"}[p] for p in app["platforms"]))}</span><span>modrnmagic.app/apps/{app["id"]}</span></div>
</div></body></html>"""
        shoot(markup, os.path.join(out_dir, f"{app['id']}.jpg"))
        print("ok", app["id"])


if __name__ == "__main__":
    main()
