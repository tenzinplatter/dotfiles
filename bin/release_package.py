#!/usr/bin/env python3
"""Find which repo owns a package and dispatch its release.yml for that package.

Usage:
    release_package.py <package> [--root DIR] [--ref REF] [--yes]
    release_package.py --state | --clear
    release_package.py --selftest

Locates the package's source under --root (default ~/Repositories) via its
package.xml, falling back to a pixi.toml [package]. Then checks the repo's
release.yml takes a `package` workflow_dispatch input (the standard GR shape,
see platform_toolbox / platform_release_testing) and that the package is one of
its options, and asks before dispatching.

release.yml is read from the repo's DEFAULT BRANCH, not the working tree — a
clone parked on a feature branch would otherwise show a workflow that isn't the
one GitHub will run.

Dispatched runs are recorded in $XDG_STATE_HOME/release_package.json; --state
re-queries them via gh, --clear drops the finished ones.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

WORKFLOW = ".github/workflows/release.yml"
STATE = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "release_package.json"


def name_variants(pkg: str) -> list[str]:
    """conda names use `-`, ROS names use `_`; accept either spelling."""
    return list(dict.fromkeys([pkg, pkg.replace("-", "_"), pkg.replace("_", "-")]))


def git(repo: Path, *args: str) -> str | None:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def repo_root(path: Path) -> Path | None:
    out = git(path.parent, "rev-parse", "--show-toplevel")
    return Path(out) if out else None


def find_sources(pkg: str, root: Path) -> list[tuple[Path, Path]]:
    """[(repo_root, manifest_path)] for every GitHub repo whose source declares `pkg`.

    Deduped by remote slug, not by path: the same repo is commonly cloned several
    times under the search root (scratch clones, nested checkouts) and all of
    them dispatch to one place. The shallowest clone wins for display.
    """
    alts = "|".join(re.escape(v) for v in name_variants(pkg))
    probes = [
        (["-g", "package.xml"], rf"<name>\s*(?:{alts})\s*</name>"),
        (["-g", "pixi.toml"], rf'^name\s*=\s*"(?:{alts})"'),
    ]
    for globs, pattern in probes:
        r = subprocess.run(
            ["rg", "-l", "--no-messages", *globs, pattern, str(root)],
            capture_output=True, text=True,
        )
        hits: dict[str, tuple[Path, Path]] = {}
        for line in r.stdout.split("\n"):
            if not line:
                continue
            manifest = Path(line)
            root_dir = repo_root(manifest)
            if not root_dir:
                continue
            key = slug(root_dir) or str(root_dir)
            prev = hits.get(key)
            if prev is None or len(root_dir.parts) < len(prev[0].parts):
                hits[key] = (root_dir, manifest)
        if hits:
            # package.xml is authoritative; don't muddy it with pixi.toml
            return [hits[k] for k in sorted(hits)]
    return []


def default_branch(repo: Path) -> str:
    ref = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref:
        return ref.split("/", 1)[-1]
    for guess in ("main", "master"):
        if git(repo, "rev-parse", "--verify", f"refs/remotes/origin/{guess}"):
            return guess
    return "main"


def slug(repo: Path) -> str | None:
    url = git(repo, "remote", "get-url", "origin")
    if not url:
        return None
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def workflow_text(repo: Path, branch: str) -> str | None:
    return git(repo, "show", f"origin/{branch}:{WORKFLOW}")


def package_input(text: str) -> tuple[bool, list[str] | None]:
    """(takes a `package` input, its options if it is a choice)."""
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return False, None
    # `on` is parsed as the boolean True by YAML 1.1 unless quoted.
    trigger = doc.get("on", doc.get(True)) or {}
    if not isinstance(trigger, dict):
        return False, None
    dispatch = trigger.get("workflow_dispatch") or {}
    if not isinstance(dispatch, dict):
        return False, None
    spec = (dispatch.get("inputs") or {}).get("package")
    if spec is None:
        return False, None
    opts = spec.get("options") if isinstance(spec, dict) else None
    if opts is None:
        return True, None
    return True, [o for o in opts if o]


def show(text: str, title: str) -> None:
    """Print YAML through bat when it's around, else plain with a header."""
    for exe in ("bat", "batcat"):  # Debian ships it as batcat
        if shutil.which(exe):
            r = subprocess.run(
                [exe, "--language=yaml", "--paging=never", f"--file-name={title}"],
                input=text, text=True,
            )
            if r.returncode == 0:
                return
            break  # bat exists but failed — fall through rather than lose the file
    print(f"\n----- {title}\n{text}")


def ask(prompt: str, choices: str) -> str:
    while True:
        try:
            got = input(f"{prompt} [{choices}] ").strip().lower()
        except EOFError:
            sys.exit("\nno input available; pass --yes to run unattended")
        if got and got[0] in choices:
            return got[0]


def load_state() -> list[dict]:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):  # missing or hand-mangled — start over
        return []


def save_state(runs: list[dict]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(runs, indent=2) + "\n")


def gh_json(*args: str):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout or "null")
    except ValueError:
        return None


FIELDS = "databaseId,status,conclusion,url,createdAt"


def latest_run(repo: str) -> dict | None:
    runs = gh_json("run", "list", "-R", repo, "-w", "release.yml", "-L", "1", "--json", FIELDS)
    return runs[0] if runs else None


def wait_for_run(repo: str, before: int | None) -> dict | None:
    """The run our dispatch just created — poll until a newer id than `before` shows up."""
    for _ in range(15):
        run = latest_run(repo)
        if run and run["databaseId"] != before:
            return run
        time.sleep(1)
    return None


def refresh(entry: dict) -> dict:
    got = gh_json("run", "view", str(entry["id"]), "-R", entry["repo"], "--json",
                  "status,conclusion,url")
    return {**entry, **(got or {"status": "?", "conclusion": "?"})}


def report(clear: bool) -> int:
    runs = load_state()
    if not runs:
        print("no recorded runs")
        return 0
    live = [refresh(e) for e in runs]
    for e in live:
        state = e["conclusion"] or e["status"]
        print(f"{state:<12} {e['package']:<24} {e['repo']:<40} {e['url']}")
    if clear:
        keep = [{k: v for k, v in e.items() if k in ("package", "repo", "ref", "id", "createdAt")}
                for e in live if e["status"] != "completed"]
        save_state(keep)
        print(f"\ncleared {len(live) - len(keep)}, {len(keep)} still running")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package", nargs="?")
    ap.add_argument("--root", type=Path, default=Path.home() / "Repositories")
    ap.add_argument("--ref", help="ref to dispatch on (default: the repo's default branch)")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--state", action="store_true", help="status of every dispatched run")
    ap.add_argument("--clear", action="store_true", help="as --state, then forget finished runs")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return 0
    if args.state or args.clear:
        return report(args.clear)
    if not args.package:
        ap.error("package is required")

    pkg = args.package
    found = find_sources(pkg, args.root)
    if not found:
        print(f"no source for {pkg!r} under {args.root}", file=sys.stderr)
        return 1
    if len(found) > 1:
        print(f"{pkg!r} declared in {len(found)} repos:")
        for i, (repo, manifest) in enumerate(found, 1):
            print(f"  {i}) {slug(repo) or repo}  ({manifest.relative_to(repo)})")
            print(f"     {repo}")
        pick = ask("which?", "".join(str(i) for i in range(1, len(found) + 1)))
        found = [found[int(pick) - 1]]

    repo, manifest = found[0]
    branch = default_branch(repo)
    ref = args.ref or branch
    name = slug(repo)
    print(f"package  {pkg}")
    print(f"source   {manifest.relative_to(repo)}")
    print(f"repo     {name or repo}  (default branch {branch})")

    text = workflow_text(repo, branch)
    if text is None:
        print(f"\n{repo.name} has no {WORKFLOW} on origin/{branch}", file=sys.stderr)
        return 1
    takes_input, options = package_input(text)
    if not takes_input:
        print(f"\n{WORKFLOW} has no `package` workflow_dispatch input — "
              f"not the standard releasable shape", file=sys.stderr)
        return 1
    if options is not None and pkg not in options:
        print(f"\n{pkg!r} is not among release.yml's package options:", file=sys.stderr)
        print(f"  {', '.join(options) or '(none listed)'}", file=sys.stderr)
        return 1
    print(f"workflow {WORKFLOW}  (package input ok"
          f"{f', {len(options)} options' if options is not None else ''})")

    cmd = ["gh", "workflow", "run", "release.yml", "-R", name or str(repo),
           "--ref", ref, "-f", f"package={pkg}"]
    print(f"\nwould run:\n  {shlex.join(cmd)}")

    if not args.yes:
        if not sys.stdin.isatty():
            print("\nnot a tty; pass --yes to dispatch unattended", file=sys.stderr)
            return 1
        while True:
            got = ask(f"\nrelease {pkg} from {name} @ {ref}?", "ynv")
            if got == "v":
                show(text, f"origin/{branch}:{WORKFLOW}")
                continue
            if got == "n":
                print("cancelled")
                return 1
            break

    target = name or str(repo)
    before = latest_run(target)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        return r.returncode

    run = wait_for_run(target, before["databaseId"] if before else None)
    if not run:
        print("dispatched, but the run didn't appear in time — not recorded", file=sys.stderr)
        return 0
    save_state(load_state() + [{"package": pkg, "repo": target, "ref": ref,
                                "id": run["databaseId"], "createdAt": run["createdAt"]}])
    print(f"\nrun {run['databaseId']}  {run['url']}")
    if not args.no_open:
        subprocess.run(["xdg-open", run["url"]])
    return 0


SAMPLE_OK = """\
name: Tag & Release
on:
  workflow_dispatch:
    inputs:
      package:
        type: choice
        description: 'If not specified, all packages will be released.'
        options:
          - ""
          - topic_utils
          - vessel_offsets
jobs:
  release:
    runs-on: ubuntu-latest
"""

SAMPLE_NO_INPUT = """\
name: Tag & Release
on:
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
"""

SAMPLE_FREEFORM = """\
on:
  workflow_dispatch:
    inputs:
      package:
        type: string
"""


def selftest() -> None:
    # The real platform_toolbox / platform_release_testing shape.
    takes, opts = package_input(SAMPLE_OK)
    assert takes and opts == ["topic_utils", "vessel_offsets"], opts

    # platform_analysis: bare workflow_dispatch, nothing to dispatch per-package.
    assert package_input(SAMPLE_NO_INPUT) == (False, None)

    # A `package` input that isn't a choice: accept, can't validate the name.
    assert package_input(SAMPLE_FREEFORM) == (True, None)

    # platform_calibration lists only the empty option -> no real packages.
    takes, opts = package_input(SAMPLE_OK.replace('          - topic_utils\n'
                                                  '          - vessel_offsets\n', ''))
    assert takes and opts == [], opts

    assert package_input("{{ not yaml") == (False, None)

    # YAML 1.1 turns an unquoted `on:` key into True; both must work.
    assert package_input(SAMPLE_OK.replace("on:", '"on":'))[0]

    assert name_variants("is-nmea0183") == ["is-nmea0183", "is_nmea0183"]
    assert name_variants("topic_utils") == ["topic_utils", "topic-utils"]
    assert name_variants("cip") == ["cip"]

    global STATE
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        STATE = Path(d) / "runs.json"
        assert load_state() == []          # missing file
        save_state([{"id": 1}])
        assert load_state() == [{"id": 1}]
        STATE.write_text("{ not json")
        assert load_state() == []

    print("selftest ok")


if __name__ == "__main__":
    sys.exit(main())
