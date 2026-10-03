#!/usr/bin/env python3
"""Rehearse the launch checklist (_docs/APPS.md) before Akhil clears the drafts.

    python3 _tests/release.py          # both runs below, exit 1 on any failure
    python3 _tests/release.py --cleared  # only the cleared-drafts rehearsal

1. Drafts present: `_tests/run.py` on the repo as it is.
2. Drafts cleared: in a temporary copy (never the repo), every draft flag,
   draft outcome, and draft lesson is confirmed, as if Akhil said yes to all
   of them. Then checklist steps 2 to 5 run in order: `render.py --release`,
   `check.py --release` (must print READY), `render.py --release --check`,
   and `_tests/run.py`. Steps 1 and 6 are people, not scripts.

So the suite cannot depend on which products are drafts today, and the
checklist cannot break on the day the drafts are confirmed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def step(name, cmd, cwd, want=None):
    print(f"--- {name}: {' '.join(cmd[1:])}", flush=True)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-4:])
    ok = r.returncode == 0 and (want is None or want in r.stdout)
    print(("ok " if ok else "FAIL ") + tail.replace("\n", "\n    "), flush=True)
    return ok


def confirm_all(apps_dir):
    for aid in json.load(open(os.path.join(apps_dir, "index.json"))):
        path = os.path.join(apps_dir, aid, "app.json")
        a = json.load(open(path))
        a.pop("draft", None)
        if a.get("outcome"):
            a["outcome"]["draft"] = False
        for x in a["lessons"]:
            x["draft"] = False
        json.dump(a, open(path, "w"), indent=2)


def main():
    py = sys.executable
    results = []
    if "--cleared" not in sys.argv:
        results.append(("drafts present: run.py", step("drafts present", [py, "_tests/run.py"], ROOT)))
    tmp = tempfile.mkdtemp(prefix="modrn-site-release-")
    dest = os.path.join(tmp, "site")
    try:
        shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "_attic"))
        confirm_all(os.path.join(dest, "apps"))
        for name, cmd, want in (
            ("step 2", [py, "_scripts/render.py", "--release"], None),
            ("step 3", [py, "_scripts/check.py", "--release"], "READY: 0 draft(s)"),
            ("step 4", [py, "_scripts/render.py", "--release", "--check"], None),
            ("step 5", [py, "_tests/run.py"], None),
        ):
            ok = step(f"drafts cleared, {name}", cmd, dest, want)
            results.append((f"drafts cleared: {name}", ok))
            if not ok:
                break
    finally:
        shutil.rmtree(tmp)
    print()
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    return 0 if results and all(ok for _, ok in results) and len(results) == (4 if "--cleared" in sys.argv else 5) else 1


if __name__ == "__main__":
    sys.exit(main())
