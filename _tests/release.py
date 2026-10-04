#!/usr/bin/env python3
"""Rehearse the launch checklist (_docs/APPS.md) with drafts held and with drafts promoted.

    python3 _tests/release.py            # all three runs below, exit 1 on any failure
    python3 _tests/release.py --cleared  # only the promoted-drafts rehearsal

1. As committed (drafts held in the local, gitignored .drafts/, if any): `check.py --release` must print
   READY, `render.py --check` is clean, and `_tests/run.py` passes.
2. Draft preview: in a temporary copy (never the repo), the held drafts are
   merged as `drafts.py preview` does, the local build runs, and
   `_tests/run.py` passes there, so the review copy keeps working.
3. Drafts promoted: in another temporary copy, `drafts.py promote` runs on
   every held draft, as if Akhil said yes to all of them. Then checklist steps
   run in order: `render.py --release`, `check.py --release` (READY with
   nothing held), `render.py --release --check`, and `_tests/run.py`.

So the suite cannot depend on which products are drafts today, and the
checklist cannot break on the day the drafts are confirmed.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
import drafts  # noqa: E402


def step(name, cmd, cwd, want=None):
    print(f"--- {name}: {' '.join(cmd[1:])}", flush=True)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    lines = (r.stdout + r.stderr).strip().splitlines()
    tail = lines[-4:]
    # Every failing check by name, not only the summary, so a failure in a
    # long child run says which test it was.
    fails = [x for x in lines[:-4] if x.startswith("FAIL")]
    ok = r.returncode == 0 and (want is None or want in r.stdout)
    print(("ok " if ok else "FAIL ") + "\n    ".join(fails + tail), flush=True)
    return ok


def copy():
    tmp = tempfile.mkdtemp(prefix="modrn-site-release-")
    dest = os.path.join(tmp, "site")
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "_attic", "_preview"))
    return tmp, dest


def run_steps(results, label, steps, cwd):
    for name, cmd, want in steps:
        ok = step(f"{label}, {name}", cmd, cwd, want)
        results.append((f"{label}: {name}", ok))
        if not ok:
            return


def main():
    py = sys.executable
    results = []
    expected = 0
    if "--cleared" not in sys.argv:
        expected += 3 + 2
        run_steps(results, "as committed", (
            ("check.py --release", [py, "_scripts/check.py", "--release"], "READY: 0 draft(s)"),
            ("render.py --check", [py, "_scripts/render.py", "--check"], None),
            ("run.py", [py, "_tests/run.py"], None),
        ), ROOT)
        tmp, dest = copy()
        try:
            drafts.merge(dest)
            run_steps(results, "draft preview", (
                ("render.py", [py, "_scripts/render.py"], None),
                ("run.py", [py, "_tests/run.py"], None),
            ), dest)
        finally:
            shutil.rmtree(tmp)
    expected += 1 + 4
    tmp, dest = copy()
    try:
        data, products = drafts.held(dest)
        ids = products + list(data["lines"])
        ok = all(subprocess.run([py, "_scripts/drafts.py", "promote", i], cwd=dest, capture_output=True).returncode == 0 for i in ids)
        print(f"--- drafts promoted: drafts.py promote {' '.join(ids) or '(nothing held)'}\n{'ok' if ok else 'FAIL'}", flush=True)
        results.append(("drafts promoted: drafts.py promote", ok))
        if ok:
            run_steps(results, "drafts promoted", (
                ("step 2", [py, "_scripts/render.py", "--release"], None),
                ("step 3", [py, "_scripts/check.py", "--release"], "0 draft(s) held"),
                ("step 4", [py, "_scripts/render.py", "--release", "--check"], None),
                ("step 5", [py, "_tests/run.py"], None),
            ), dest)
    finally:
        shutil.rmtree(tmp)
    print()
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    return 0 if len(results) == expected and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
