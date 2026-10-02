# Product data

Every product on modrnmagic.app comes from one file: `apps/<id>/app.json`. `apps/index.json` lists the ids in display order. Nothing about products is hardcoded in HTML or JS.

## Add or change a product

1. Create or edit `apps/<id>/app.json` (copy an existing one; `_docs/app-template.json` is a blank).
2. Put the source icon and screenshots in `_src/apps/<id>/` (not published) and list them under `icon` and `screenshots[].from`, relative to that folder. Only the WebP copies in `apps/<id>/media/` ship.
3. Run:

```
python3 _scripts/images.py   # web-sized WebP copies in apps/<id>/media/ (needs Pillow)
python3 _scripts/render.py   # pages, /work/, sitemap.xml, llms.txt, JSON-LD (local build: drafts marked)
python3 _scripts/og.py       # 1200x630 share cards in assets/og/ (needs Chrome)
python3 _scripts/check.py serve  # preview at http://localhost:8000
```

4. Commit the JSON and the generated files together. `python3 _scripts/render.py --check` fails if the committed HTML is stale.

## Serve and check

Both commands need only Python 3, no installs:

```
python3 _scripts/check.py serve   # serve the repo at http://localhost:8000 (PORT=xxxx to change)
python3 _scripts/check.py         # exit 1 if any internal link, asset, or sitemap URL is missing
python3 _scripts/check.py --release  # also exit 1 while any draft page, outcome, or lesson remains
```

Click tests (dev only, need Playwright for Python with Chromium: `pip install playwright && playwright install chromium`):

```
python3 _tests/run.py      # click every link, button, toggle, FAQ, and rail control on every page; exit 1 on failure
python3 _tests/run.py -v   # same, printing every passing check
```

It also fails on any request off the local server, any console error, sideways scroll at 320px, and any legal URL that stops answering bare, with a slash, as `/index.html`, or as its `.md` source. It checks that every product has a page and that drafts stay off shared pages. In a temporary copy of the repo (never the repo itself) it renames Ramble and greps for the old name, renders an example push cycle and clicks each update link, feeds `render.py` bad data, and confirms `check.py --release` passes once drafts are cleared. It ends with an interaction coverage line.

The check reads every published HTML, CSS, JS, JSON, XML, TXT, and MD file (anything outside `_` and dot folders). It resolves each internal `href`, `src`, `srcset`, CSS `url()`, `https://modrnmagic.app/` URL, and relative path in `apps/**/*.json`, confirms each `sitemap.xml` URL maps to a file, and fails on any mention of the removed `00_Future App Template` folder. Run it before every push.

GitHub Pages serves the committed files as they are. Its default Jekyll pass copies plain HTML untouched and skips `_`-prefixed folders, so `_docs/` and `_scripts/` are not published. Do not add a `.nojekyll` file unless those folders move out of the repo root.

## Fields

| Field | Notes |
|---|---|
| `id` | Folder name and URL slug. Never rename a live app's id: store listings link to `apps/<id>/privacy/`. |
| `name`, `storeName` | Display name; optional full store title. |
| `status` | `live`, `lab` (prototype or paused), or `archived`. Only `live` shows store buttons. |
| `kind` | `app`, `game`, `web`, `tool`. |
| `oneliner` | One sentence, used on cards, OG images, and titles. |
| `summary` | Two or three sentences. Used for the meta description, JSON-LD, and llms.txt. |
| `description` | Paragraphs for the product page. |
| `features`, `faq` | Optional. FAQ also becomes FAQPage JSON-LD. Only write what is true. |
| `category`, `genre` | schema.org `applicationCategory` and a plain genre label. |
| `stack` | Technologies, shown as "Built with". |
| `dates` | `started`, `shipped`, `updated`, `ended` as `YYYY-MM-DD` or `YYYY-MM`, or null. |
| `platforms` | Any of `ios`, `android`, `web`. |
| `links` | `appStore`, `googlePlay`, `web`, `home` (relative product site), `writing`, `source`. |
| `price` | App Store price from the store listing, for the Offer in JSON-LD. |
| `wasOn` | For archived apps: stores it used to be on, shown as text, never as links. |
| `icon`, `color` | Icon file in the folder (or null for a letter tile) and its tile color. |
| `screenshots` | `{from, src, w, h, alt, shape}`. `shape` is `phone` or `wide`. `src`, `w`, `h` are written by `images.py`. |
| `legal` | Relative paths to `privacy/`, `tos/`, and optional `deleteAccount`. |
| `draft` | Optional, default false. In the local build a draft product gets its own page (noindex, with a Draft banner) and a marked row on /work/, and nothing else: no home, footer, sitemap, or llms.txt entry. The release build (`render.py --release`) leaves drafts out entirely, along with draft outcome lines and lessons. Remove the flag once Akhil confirms. |
| `outcome` | `null`, or `{label, date, line, draft}` once a keep or archive decision exists. `label` is `Kept`, `Paused`, `Parked`, or `Archived`; `date` is `YYYY-MM`; `line` is one sentence with the reason. Outcome text comes from Akhil or the cycle report; a line an agent drafted keeps `draft: true` until he confirms it. |
| `lessons` | `[{text, draft}]`, shown as "What we learned". Same draft rule. |
| `cycle` | `null`, or `{start, end, goal, updates}` during a push cycle. Dates are `YYYY-MM-DD`; `updates` is `[{date, text}]` with unique dates on or after `start`. The page shows them newest first as "What's new", each with its own link. |
| `flagship` | `true` on at most one product, never an archived one. Home then shows that product in a full-width panel above the bento and drops it from the bento and the experiments strip. HQ picks it; with nothing flagged, home is complete without the panel. A draft flagship shows only in the local build. |

Text fields (`oneliner`, `summary`, `description`, `features`, `faq`, screenshot `alt`) may write `{name}`; `render.py` fills in `name`. Use it when a product may be renamed, so the name lives in one field. Ramble does this.

`render.py` validates all of the above, and rejects unknown keys, on every run, so `render.py --check` fails on bad data.

Rules: no invented metrics, ratings, or testimonials. Archived apps never link to a store.

## URLs that must keep working

Store listings and AdMob point at these. Do not move or delete them:

- `apps/<id>/privacy/` and `apps/<id>/tos/` for every app that was on a store, plus `apps/skywise/privacy/delete-account/`

Legal pages are generated: edit `apps/<id>/privacy/privacy-policy.md` or `apps/<id>/tos/terms_of_service.md` and run `render.py`. The text is reproduced verbatim inside the site chrome, and the `.md` files stay published at their paths. An empty Markdown file renders a page that says the policy is not published yet and gives the support address.
- `app-ads.txt`
- `apps/flowmoro/home/` (rendered from `home/descriptions.json`; its `icon.png` and `screenshots/*.png` stay at their old paths)
- `CNAME`
