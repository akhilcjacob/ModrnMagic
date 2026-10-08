# One command to set up, one to verify. See README.md.
#
#   make bootstrap   # .venv with Playwright and Pillow, plus the Chromium build Playwright uses
#   make test        # check.py --release, render.py --check (both builds), then the click suite in Chromium
#   make verify      # on a clean checkout: bootstrap if needed, then make test, logged to _verify/
#
# ENGINES="chromium firefox webkit" make bootstrap installs more engines; ENGINE=webkit make e2e runs one.
# QA_RUN names an optional lock wrapper (default: qa-run on PATH, if any). With one, checks run under
# its build lock and the click suite under browser-qa plus build, each with a wait and a time limit.
# Stop such a run with `qa-run cancel`, never kill -9.

SHELL := /bin/bash
PY ?= .venv/bin/python
ENGINES ?= chromium
ENGINE ?= chromium
VERIFY_DIR ?= _verify
QA_RUN ?= $(shell command -v qa-run 2>/dev/null)
BUILD_JOB := $(if $(QA_RUN),$(QA_RUN) build --wait 30 --timeout 10 --,)
BROWSER_JOB := $(if $(QA_RUN),$(QA_RUN) browser-qa --build --wait 30 --timeout 20 --,)

.PHONY: bootstrap test check e2e verify verify-steps serve clean

bootstrap:
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r _tests/requirements.txt
	$(PY) -m playwright install $(ENGINES)
	@echo "bootstrap ok: $$($(PY) --version), engines: $(ENGINES)"

check:
	$(BUILD_JOB) bash -exc '$(PY) _scripts/check.py --release; $(PY) _scripts/render.py --check; $(PY) _scripts/render.py --release --check'

e2e:
	$(BROWSER_JOB) $(PY) _tests/run.py --browser=$(ENGINE)

test: check e2e
	@echo "test ok"

# The log starts with the commit and the date, so it can be matched to a PR head. The tree must be
# clean (tracked and untracked; ignored files such as .venv and _verify are fine) and on the same
# commit at the start and at the end, or verify fails. The log name ends in -pass or -fail.
verify:
	@if [ -n "$$(git status --porcelain)" ]; then git status --short; echo "verify: the working tree is not clean; commit or stash first"; exit 1; fi
	@mkdir -p $(VERIFY_DIR)
	@sha=$$(git rev-parse HEAD); \
	log="$(VERIFY_DIR)/verify-$$(date -u +%Y%m%dT%H%M%SZ)-$$(git rev-parse --short HEAD)"; \
	{ echo "commit: $$sha"; echo "date: $$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "qa-run: $(if $(QA_RUN),yes,no)"; echo; } > "$$log.log"; \
	$(MAKE) --no-print-directory verify-steps 2>&1 | tee -a "$$log.log"; status=$${PIPESTATUS[0]}; \
	{ now=$$(git rev-parse HEAD); dirty=$$(git status --porcelain); \
	  if [ "$$now" != "$$sha" ]; then echo "verify: HEAD moved during the run ($$sha -> $$now)"; status=1; fi; \
	  if [ -n "$$dirty" ]; then echo "verify: the working tree changed during the run:"; echo "$$dirty"; status=1; fi; \
	  echo "verify exit $$status"; } 2>&1 | tee -a "$$log.log"; \
	status=$$(tail -1 "$$log.log" | sed 's/^verify exit //'); \
	if [ "$$status" = 0 ]; then out="$$log-pass.log"; else out="$$log-fail.log"; fi; \
	mv "$$log.log" "$$out"; echo "log: $$out"; exit $$status

verify-steps:
	@if [ ! -x "$(PY)" ]; then $(MAKE) --no-print-directory bootstrap; fi
	@echo "python: $$($(PY) --version 2>&1) ($(PY)), playwright: $$($(PY) -m pip show playwright 2>/dev/null | sed -n 's/^Version: //p'), pillow: $$($(PY) -m pip show pillow 2>/dev/null | sed -n 's/^Version: //p')"
	@$(MAKE) --no-print-directory test

serve:
	$(PY) _scripts/check.py serve

clean:
	rm -rf .venv _preview
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
