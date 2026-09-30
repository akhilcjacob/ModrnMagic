# Product data

Every product on modrnmagic.app comes from one file: `apps/<id>/app.json`. `apps/index.json` lists the ids in display order. Nothing about products is hardcoded in HTML or JS.

## Add or change a product

1. Create or edit `apps/<id>/app.json` (copy an existing one; `docs/app-template.json` is a blank).
2. Put source screenshots in `apps/<id>/screenshots/` or `marketing/` and list them under `screenshots` with a `from` path.
3. Run:

```
python3 scripts/images.py   # web-sized WebP copies in apps/<id>/media/ (needs Pillow)
python3 scripts/render.py   # pages, sitemap.xml, llms.txt, JSON-LD
python3 scripts/og.py       # 1200x630 share cards in assets/og/ (needs Chrome)
python3 -m http.server      # preview at http://localhost:8000
```

4. Commit the JSON and the generated files together. `python3 scripts/render.py --check` fails if the committed HTML is stale.

GitHub Pages serves the committed files as they are. There is no build step on deploy.

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

Rules: no invented metrics, ratings, or testimonials. Archived apps never link to a store.

## URLs that must keep working

Store listings and AdMob point at these. Do not move or delete them:

- `apps/<id>/privacy/` and `apps/<id>/tos/` for every app that was on a store, plus `apps/skywise/privacy/delete-account/`
- `app-ads.txt`
- `apps/flowmoro/home/`
- `CNAME`
