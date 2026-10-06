# modrnmagic.app

The studio site for Modrn Magic: a home page, a /work/ index, one page per product, contact, and the privacy and terms pages that app store listings link to. It is a static site. GitHub Pages serves `main` as committed at https://modrnmagic.app, so a merge to `main` publishes.

Product data lives in `apps/<id>/app.json`; `_scripts/render.py` generates the HTML, sitemap, and `llms.txt` from it. `_docs/APPS.md` is the full guide (fields, held drafts, launch checklist) and `_docs/DESIGN.md` is the design system.

## Status

Verified on 2026-10-06 against `main` at `7415518`, Python 3.14.7, Playwright 1.60.0. Proof is in HQ `_attic/site-baseline-2026-10/`.

### What works

- The live site matches `main` byte for byte (home, /work/, sitemap, llms.txt), and the last GitHub Pages build of `main` succeeded.
- All 19 sitemap URLs answer 200 on the live site.
- Every legal URL answers 200 bare, with a slash, as `index.html`, and as its `.md` source: privacy and terms for Flowmoro, Astro Defender, SkyWise, InboxHiive, and Nookly, plus SkyWise's delete-account page. The other kept URLs (`app-ads.txt`, `/skywise`, `/mvp.html`, `/apps/flowmoro/home/`, `assets/og-image.png`) answer 200.
- `check.py --release` prints READY, and `render.py --check` and `render.py --release --check` pass: the committed tree is the release build.
- `render.py --release` on today's toolchain rewrites the tree with no diff.
- The click suite `_tests/run.py` passes in Chromium, Firefox, and WebKit.

### What is broken or not covered

Each item is a GitHub Issue; the issue list is the work queue.

- Real Safari is not tested. The suite runs Playwright's WebKit, not Safari. Safari needs Remote Automation turned on by hand.
- Ten held drafts (two products, and outcome lines or lessons for four others) wait on Akhil. They live in a local, gitignored `.drafts/` and are not on the site.
- GitHub Pages' Jekyll pass also publishes every Markdown file as an unstyled HTML page (for example `/apps/flowmoro/privacy/privacy-policy.html`) with its own canonical URL, alongside the designed legal pages.
- Not yet confirmed: that no store listing uses the eight legal URLs of the old app template folder, removed in PR #1.
- Share cards (`og.py`) need a local Chrome and are not checked in CI.

## Run

The site needs only Python 3 and its standard library; nothing to install.

```
python3 _scripts/check.py serve   # what Pages would publish, at http://localhost:8000
python3 _scripts/render.py        # after editing apps/*/app.json or a legal .md
```

## Test

From a fresh clone:

```
make bootstrap   # .venv with Playwright and Pillow, plus Playwright's Chromium
make test        # release checks, then the click suite in Chromium
```

`make test` runs `check.py --release`, `render.py --check`, `render.py --release --check`, and `_tests/run.py`. `ENGINE=firefox make e2e` or `ENGINE=webkit make e2e` runs the suite in another engine (install it first with `ENGINES="chromium firefox webkit" make bootstrap`). On the studio laptop, browser runs go through the HQ `qa-run` lock on their own. `python3 _tests/release.py` rehearses the full launch checklist, with drafts held and with every draft promoted.

CI (`.github/workflows/ci.yml`) runs the same checks and the Chromium suite on every pull request and on `main`.

## Release

Follow the launch checklist in `_docs/APPS.md`. Merge with squash merge only: the repository is public, and branch history can hold content later removed.
