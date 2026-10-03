# Product data

Every product on modrnmagic.app comes from one file: `apps/<id>/app.json`. `apps/index.json` lists the ids in display order. Nothing about products is hardcoded in HTML or JS. Content Akhil has not confirmed is held in `_drafts/`, which is not published (see Held drafts).

## Add or change a product

1. Create or edit `apps/<id>/app.json` (copy an existing one; `_docs/app-template.json` is a blank).
2. Put the source icon and screenshots in `_src/apps/<id>/` (not published) and list them under `icon` and `screenshots[].from`, relative to that folder. Only the WebP copies in `apps/<id>/media/` ship.
3. Run:

```
python3 _scripts/images.py   # web-sized WebP copies in apps/<id>/media/ (needs Pillow)
python3 _scripts/render.py   # pages, /work/, sitemap.xml, llms.txt, JSON-LD
python3 _scripts/og.py       # 1200x630 share cards in assets/og/ (needs Chrome)
python3 _scripts/check.py serve  # preview at http://localhost:8000
```

4. Commit the JSON and the generated files together. `python3 _scripts/render.py --check` fails if the committed HTML is stale.

## Serve and check

Both commands need only Python 3, no installs:

```
python3 _scripts/check.py serve   # serve the repo at http://localhost:8000 (PORT=xxxx to change)
python3 _scripts/check.py         # exit 1 if any internal link, asset, or sitemap URL is missing
python3 _scripts/check.py --release  # also exit 1 on any draft in published data or HTML, or any leak of held drafts (see Launch checklist)
python3 _scripts/check.py serve --drafts  # build _preview/ with the held drafts merged and serve that
```

Click tests (dev only, need Playwright for Python with Chromium: `pip install playwright && playwright install chromium`):

```
python3 _tests/run.py      # click every link, button, toggle, FAQ, and rail control on every page; exit 1 on failure
python3 _tests/run.py -v   # same, printing every passing check
python3 _tests/release.py  # the committed tree, then the draft preview, then the launch checklist with every held draft promoted (temp copies)
```

On the studio laptop, run every browser job through the HQ lock wrapper, one engine at a time, with a time bound:

```
~/Development/modrn/hq/scripts/qa-run browser-qa --wait 30 --timeout 20 -- python3 _tests/run.py --browser=webkit
~/Development/modrn/hq/scripts/qa-locks-status   # who holds which slot
```

`qa-run` takes a free `browser-qa` slot, stops the whole job and releases the slot on exit, failure, or timeout. `run.py` also bounds itself: each section and the whole run (`RUN_TIMEOUT`, default 2400 seconds) have time limits, and past one it prints `TIMEOUT` with the section and the last check, closes the browsers, and exits 2. `--browser=firefox` or `--browser=webkit` runs the same suite in that engine (WebKit tabs with Option+Tab, like Safari).

It also fails on any request off the local server, any console error, sideways scroll at 320px, and any legal URL that stops answering bare, with a slash, as `/index.html`, or as its `.md` source. It checks that every product has a page and that drafts stay off shared pages. In a temporary copy of the repo (never the repo itself) it renames Ramble and greps for the old name, renders an example push cycle and clicks each update link, feeds `render.py` bad data, confirms `check.py --release` passes once drafts are cleared, fails on a draft it adds itself and on a stray draft mark in HTML, and runs `render.py --release` on a product it marks as a draft to confirm the page is deleted. No test relies on which products are drafts today: each temp copy starts from the preview state (held drafts merged) and sets the state it needs, so the suite passes on the committed tree, on the preview, and with every draft promoted (`_tests/release.py` runs all three). It also checks that no held draft appears in the published tree, that `check.py --release` fails on a held product in `apps/` or held text in a page, and that promoting every held draft passes the gate. It renders home for every live set and flagship choice the reviews named (nothing flagged, each live product flagged, HypeBridge and Ramble live and flagged, QuietDesk and Nookly flagged, 0 to 7 cells, a wide-shot, one-phone, and no-art lead, a no-art half) and checks at 1440, 800, 390, and 320px for one bento cell per live product, no empty grid area, no cell more than 40% empty space (a cell stretched by its row neighbour), and a matching "N live" count. It measures the contrast of every text box on tinted surfaces (home, /work/, each product page and product site with a tinted surface, and each bento variant) against the pixels behind it, in both themes, at 320, 360, 390, 800, and 1440px, and fails under 4.5:1. It checks nav links and the theme toggle are at least 44px at seven widths from 320 up. It ends with an interaction coverage line.

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
| `icon`, `color` | Icon file in the folder (or null for a letter tile) and its tile color, as `#rrggbb` or `rgb(r,g,b)`. A near-black `color` makes the product's home bento cell dark. |
| `stars` | Optional, default false. A faint night sky in the product's dark bento cell. Only for products where it fits (Astro Defender, a space game); needs a near-black `color`. |
| `tint` | Optional `#rrggbb`. The hue of the soft gradient in the product's cards, bento cell, and flagship panel. Without it the gradient uses `color`, unless `color` is near neutral or near black (OKLCH chroma under 0.04, or lightness outside 0.3 to 0.9): those turn into grey haze and pull meta text under AA, so the card gets no gradient. Take it from the product's own icon or UI; leave it out until the product has a brand hue (open choices are in `_docs/DRAFTS.md`). `og.py` uses the same rule for the share card wash. `_tests/run.py` measures card text contrast in both themes. |
| `screenshots` | `{from, src, w, h, alt, shape}`. `shape` is `phone` or `wide`. `src`, `w`, `h` are written by `images.py`. |
| `legal` | Relative paths to `privacy/`, `tos/`, and optional `deleteAccount`. |
| `draft` | Optional, default false. Only held draft products in `_drafts/apps/<id>/app.json` carry it. In the preview a draft product gets its own page (noindex, with a Draft banner) and a marked row on /work/, and nothing else: no home, footer, sitemap, or llms.txt entry. `drafts.py promote` clears it. |
| `outcome` | `null`, or `{label, date, line, draft}` once a keep or archive decision exists. `label` is `Kept`, `Paused`, `Parked`, or `Archived`; `date` is `YYYY-MM`; `line` is one sentence with the reason. Outcome text comes from Akhil or the cycle report; a line an agent drafted is held in `_drafts/drafts.json` until he confirms it. |
| `lessons` | `[{text, draft}]`, shown as "What we learned". Same draft rule: published lessons have `draft: false`. |
| `cycle` | `null`, or `{start, end, goal, updates}` during a push cycle. Dates are `YYYY-MM-DD`; `updates` is `[{date, text}]` with unique dates on or after `start`. The page shows them newest first as "What's new", each with its own link. |
| `flagship` | `true` on at most one product, never an archived one. Home then shows that product in a full-width panel above the bento and drops it from the bento and the experiments strip. HQ picks it; with nothing flagged, home is complete without the panel. A draft flagship shows only in the preview. |

Text fields (`oneliner`, `summary`, `description`, `features`, `faq`, screenshot `alt`) may write `{name}`; `render.py` fills in `name`. Use it when a product may be renamed, so the name lives in one field. Ramble does this.

`render.py` validates all of the above, and rejects unknown keys, on every run, so `render.py --check` fails on bad data.

Rules: no invented metrics, ratings, or testimonials. Archived apps never link to a store.

## Held drafts

GitHub Pages publishes every file outside `_` folders, so anything in `apps/`, `assets/`, or a page is public the moment it lands on `main`. Content Akhil has not confirmed therefore lives in `_drafts/`, which Jekyll skips:

| Path | What |
|---|---|
| `_drafts/apps/<id>/` | A draft product: `app.json` with `"draft": true`, and its `media/` |
| `_drafts/assets/og/<id>.jpg` | Its share card (`og.py` writes it there) |
| `_drafts/drafts.json` | `order`: every id, drafts included, in display order. `lines`: per product, a held `outcome` and `lessons` |

The committed tree is the release build: no draft product, page, row, line, mark, data, or media. `images.py` and `og.py` write a held product's media and card inside `_drafts/`. Originals stay in `_src/apps/<id>/` as for any product.

```
python3 _scripts/drafts.py            # list held drafts
python3 _scripts/check.py serve --drafts  # preview with drafts merged and marked, at http://localhost:8000
python3 _scripts/drafts.py preview    # only build that preview, in _preview/ (gitignored)
```

The preview is a copy of the site with the drafts merged and the default build run, so draft pages, Draft marks, and the draft row on /work/ look as they did before drafts were held. It never touches the repo.

**Promote a draft** once Akhil says yes (or after he rewrites it in `_drafts/`):

```
python3 _scripts/drafts.py promote ramble   # a product: moves _drafts/apps/ramble/ and its card into place, clears draft, adds it to apps/index.json at its place in order
python3 _scripts/drafts.py promote nookly   # lines: moves nookly's held outcome and lessons into apps/nookly/app.json as confirmed
python3 _scripts/render.py
```

Then run the launch checklist and commit. To drop a draft instead, delete its folder or its entry under `lines`. Record the decision in `_docs/DRAFTS.md`.

## Launch checklist

GitHub Pages publishes whatever lands on `main`, and there is no CI, so a merge publishes exactly what is committed. Before any merge to `main`:

Rehearse first: `python3 _tests/release.py` checks the committed tree, the draft preview, and steps 2 to 5 below in a temp copy with every held draft promoted.

1. Promote only what Akhil confirmed (`drafts.py promote <id>`). Everything else stays held.
2. Build the public site: `python3 _scripts/render.py --release`. It leaves out any `draft` product or line still in `apps/` and deletes its page.
3. `python3 _scripts/check.py --release` must print `READY`. It fails on any draft in published data (`DRAFT`), on published HTML that still carries a draft mark or banner (`DRAFT OUTPUT`), and on held draft content in the published tree (`DRAFT LEAK`: a held product's folder, page, card, or URL, or the text of a held line). Held drafts in `_drafts/` are listed but do not block.
4. `python3 _scripts/render.py --check` and `python3 _scripts/render.py --release --check` pass (the committed output is the release build).
5. `python3 _tests/run.py` passes, then commit and open the PR.

## URLs that must keep working

Store listings and AdMob point at these. Do not move or delete them:

- `apps/<id>/privacy/` and `apps/<id>/tos/` for every app that was on a store, plus `apps/skywise/privacy/delete-account/`

Legal pages are generated: edit `apps/<id>/privacy/privacy-policy.md` or `apps/<id>/tos/terms_of_service.md` and run `render.py`. The text is reproduced verbatim inside the site chrome, and the `.md` files stay published at their paths. An empty Markdown file renders a page that says the policy is not published yet and gives the support address.
- `app-ads.txt`
- `apps/flowmoro/home/` (rendered from `home/descriptions.json`; its `icon.png` and `screenshots/*.png` stay at their old paths)
- `CNAME`
