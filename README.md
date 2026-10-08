# modrnmagic.app

The studio site for Modrn Magic: a home page, a /work/ index, one page per product, contact, and the privacy and terms pages that app store listings link to. It is a static site. GitHub Pages serves `main` as committed at https://modrnmagic.app, so a merge to `main` publishes.

Product data lives in `apps/<id>/app.json`; `_scripts/render.py` generates the HTML, sitemap, and `llms.txt` from it. `_docs/APPS.md` is the full guide (fields, launch checklist) and `_docs/DESIGN.md` is the design system. `_config.yml` keeps this README and the Makefile off the published site and stops Jekyll from rendering Markdown into extra pages.

## Status

Checks and the click suite last run with Python 3.14.7 and Playwright 1.60.0.

### What works

- `check.py --release` prints READY, and `render.py --check` and `render.py --release --check` pass: the committed tree is the release build.
- The click suite `_tests/run.py` passes in Chromium, Firefox, and WebKit.

Checked on the live site on 2026-10-08:

- All 19 sitemap URLs answer 200.
- Every designed legal page (privacy, terms, and SkyWise's delete-account page) answers 200 with a slash and as `index.html`; the bare URL redirects once to the slash form. Its Markdown source answers 200 as raw `text/markdown` at its own `.md` URL.

### Known gaps

Each gap is a GitHub Issue; the issue list is the work queue.

- Real Safari is not tested. The suite runs Playwright's WebKit, not Safari.
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
make verify      # the full verify on a clean checkout, saved as a log
```

On a fresh Linux machine, Chromium also needs system libraries before `make test` can launch it: run `.venv/bin/python -m playwright install-deps chromium` once (it uses sudo to install packages). macOS needs nothing extra. CI does this with `playwright install --with-deps`.

`make test` runs `check.py --release`, `render.py --check`, `render.py --release --check`, and `_tests/run.py`. `ENGINE=firefox make e2e` or `ENGINE=webkit make e2e` runs the suite in another engine (install it first with `ENGINES="chromium firefox webkit" make bootstrap`). `python3 _tests/release.py` rehearses the full launch checklist.

`make verify` refuses to run on a working tree with uncommitted or untracked changes (ignored files such as `.venv` are fine). It runs `make bootstrap` if `.venv` is missing, then `make test`, and fails if `HEAD` or the working tree changed during the run. It writes everything to `_verify/verify-<time>-<commit>-pass.log` or `-fail.log` (gitignored). The log starts with the full commit hash and the UTC date, so it can be matched to the exact commit it tested. Set `VERIFY_DIR` to save it elsewhere. An old `.venv` is reused as is; `make clean` removes it.

If a `qa-run` lock wrapper is on `PATH` (or named by `QA_RUN`), the Makefile runs the checks and the click suite through it, with a wait and a time limit; otherwise they run directly.

CI (`.github/workflows/ci.yml`) runs the checks and the Chromium suite on every pull request. A pull request that changes only docs (this README, `LICENSE`, or `_docs/*.md`) runs the checks and skips the suite.

## Release

Follow the launch checklist in `_docs/APPS.md`. Merge with squash merge only.
