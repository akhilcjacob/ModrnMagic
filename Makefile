# One command to set up, one to verify. See README.md, Status.
#
#   make bootstrap   # .venv with Playwright and Pillow, plus the Chromium build Playwright uses
#   make test        # check.py --release, render.py --check (both builds), then the click suite in Chromium
#
# ENGINES="chromium firefox webkit" make bootstrap installs more engines; ENGINE=webkit make e2e runs one.
# On the studio laptop browser runs go through the HQ qa-run lock automatically when it exists.

PY ?= .venv/bin/python
ENGINES ?= chromium
ENGINE ?= chromium
QA_RUN := $(wildcard $(HOME)/Development/modrn/hq/scripts/qa-run)
BROWSER_JOB := $(if $(QA_RUN),$(QA_RUN) browser-qa --wait 30 --timeout 20 --,)

.PHONY: bootstrap test check e2e serve clean

bootstrap:
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r _tests/requirements.txt
	$(PY) -m playwright install $(ENGINES)
	@echo "bootstrap ok: $$($(PY) --version), engines: $(ENGINES)"

check:
	$(PY) _scripts/check.py --release
	$(PY) _scripts/render.py --check
	$(PY) _scripts/render.py --release --check

e2e:
	$(BROWSER_JOB) $(PY) _tests/run.py --browser=$(ENGINE)

test: check e2e
	@echo "test ok"

serve:
	$(PY) _scripts/check.py serve

clean:
	rm -rf .venv _preview
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
