#!/usr/bin/env python3
"""Release every engine_control_* package in platform_control, one at a time.

Each dispatch must finish before the next starts: the release bumps HEAD, and a
second run started against the old HEAD silently skips its release.

Usage: release_engine_controls.py [--repo SLUG] [--only PKG ...] [--dry-run]
"""

import argparse
import re
import subprocess
import sys

REPO = "greenroom-robotics/platform_control"


def packages(repo: str) -> list[str]:
    text = subprocess.run(["gh", "workflow", "view", "release.yml", "-R", repo, "--yaml"],
                          capture_output=True, text=True, check=True).stdout
    return re.findall(r"^\s+- (engine_control_\S+)$", text, re.M)


def release(pkg: str, repo: str) -> bool:
    out = subprocess.run(["release_package.py", pkg, "--yes", "--no-open"],
                         capture_output=True, text=True)
    print(out.stdout, out.stderr, sep="", end="")
    m = re.search(r"^run (\d+)", out.stdout, re.M)
    if out.returncode != 0 or not m:
        return False
    return subprocess.run(["gh", "run", "watch", m.group(1), "-R", repo,
                           "--exit-status", "-i", "15"]).returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--only", nargs="+", metavar="PKG")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pkgs = args.only or packages(args.repo)
    print("\n".join(f"  {p}" for p in pkgs))
    if args.dry_run:
        return 0

    failed = []
    for i, pkg in enumerate(pkgs):
        print(f"\n===== [{i + 1}/{len(pkgs)}] {pkg}")
        if not release(pkg, args.repo):
            failed.append(pkg)
            print(f"{pkg} failed, continuing", file=sys.stderr)
    print(f"\nreleased {len(pkgs) - len(failed)}/{len(pkgs)}")
    if failed:
        print(f"failed: {' '.join(failed)}", file=sys.stderr)
        print(f"retry:  release_engine_controls.py --only {' '.join(failed)}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
