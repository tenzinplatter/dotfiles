#!/usr/bin/env python3
"""Bump every exact (`==X.Y.Z`) conda pin in every pixi.toml to the channel's latest.

Usage:
    pixi_bump_pins.py [root] [--apply] [--jobs N]

Discovers manifests with `rg --files -g pixi.toml`, so .gitignore/.ignore are
respected for free. Dry-run by default; --apply writes (matching
pixi_convert_extras.py). Versions come from `pixi search` against each
manifest's own [workspace] channels.

Only exact pins are touched. Ranges (">=1,<2"), wildcards ("*"), path deps and
[pypi-dependencies] are left alone, as is [package] version.

    pixi_bump_pins.py --selftest    # run the rewrite self-check
"""

import argparse
import asyncio
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# A pin line: `name = "==1.2.3"  # trailing comment`. Captured in pieces so the
# rewrite preserves the manifests' column alignment and comments.
PIN = re.compile(
    r'^(?P<pre>\s*(?P<name>[A-Za-z0-9_.\-]+)\s*=\s*")==(?P<ver>[^"]+)(?P<post>".*)$'
)
TABLE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
# `Version    4.18.2` — pixi search prints the newest first.
VERSION = re.compile(r"^\s*Version\s+(\S+)")


def is_conda_deps_table(table: str | None) -> bool:
    """True for conda dependency tables, false for pypi ones and everything else."""
    if table is None:
        return False
    last = table.split(".")[-1]
    return last.endswith("dependencies") and last != "pypi-dependencies"


def find_pins(text: str) -> list[tuple[int, str, str]]:
    """Return (line_index, package, version) for each exact conda pin."""
    out = []
    table = None
    for i, line in enumerate(text.splitlines()):
        if m := TABLE.match(line):
            table = m.group("name")
            continue
        if not is_conda_deps_table(table):
            continue
        if m := PIN.match(line):
            out.append((i, m.group("name"), m.group("ver")))
    return out


def apply_bumps(text: str, bumps: dict[int, str]) -> str:
    """Replace the version on each given line index, preserving layout."""
    lines = text.splitlines(keepends=True)
    for i, new in bumps.items():
        m = PIN.match(lines[i].rstrip("\n"))
        assert m, f"line {i} is no longer a pin"
        nl = "\n" if lines[i].endswith("\n") else ""
        lines[i] = f'{m.group("pre")}=={new}{m.group("post")}{nl}'
    return "".join(lines)


def manifest_context(path: Path) -> tuple[tuple[str, ...], str] | None:
    """(channels, platform) from [workspace], or None if it has no channels."""
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        print(f"! {path}: unparseable ({e})", file=sys.stderr)
        return None
    ws = data.get("workspace") or data.get("project") or {}
    channels = [c for c in ws.get("channels", []) if isinstance(c, str)]
    if not channels:
        return None
    platforms = ws.get("platforms") or ["linux-64"]
    return tuple(channels), platforms[0]


async def latest(pkg: str, channels: tuple[str, ...], platform: str, sem) -> str | None:
    args = ["pixi", "search"]
    for c in channels:
        args += ["--channel", c]
    args += ["--platform", platform, pkg]
    async with sem:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        out, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    for line in out.decode(errors="replace").splitlines():
        if m := VERSION.match(line):
            return m.group(1)
    return None


def discover(root: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["rg", "--files", "-g", "pixi.toml", str(root)],
            capture_output=True, text=True, check=True,
        ).stdout
    except FileNotFoundError:
        sys.exit("pixi_bump_pins: needs ripgrep (rg) on PATH")
    except subprocess.CalledProcessError:
        return []  # rg exits 1 when it matches nothing
    return sorted(Path(p) for p in out.split("\n") if p)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", type=Path)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--jobs", type=int, default=8, help="concurrent pixi searches")
    ap.add_argument("--selftest", action="store_true", help="run the rewrite self-check")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return 0

    manifests = discover(args.root)
    if not manifests:
        print("no pixi.toml found")
        return 0

    # One search per (package, channels, platform) no matter how many manifests
    # share it — the same pin repeats across dozens of variant manifests.
    work: dict[tuple, list[tuple[Path, int, str]]] = {}
    texts: dict[Path, str] = {}
    for path in manifests:
        ctx = manifest_context(path)
        if ctx is None:
            continue
        channels, platform = ctx
        text = texts[path] = path.read_text()
        for idx, pkg, ver in find_pins(text):
            work.setdefault((pkg, channels, platform), []).append((path, idx, ver))

    if not work:
        print(f"{len(manifests)} manifests, no exact pins")
        return 0

    sem = asyncio.Semaphore(args.jobs)
    keys = list(work)
    results = await asyncio.gather(
        *(latest(pkg, ch, plat, sem) for pkg, ch, plat in keys)
    )

    bumps: dict[Path, dict[int, str]] = {}
    unresolved: list[str] = []
    for key, newest in zip(keys, results):
        pkg = key[0]
        if newest is None:
            unresolved.append(pkg)
            continue
        for path, idx, current in work[key]:
            if current != newest:
                bumps.setdefault(path, {})[idx] = newest
                print(f"  {path}: {pkg} {current} -> {newest}")

    if unresolved:
        print(f"\nnot found on channel ({len(set(unresolved))}): "
              f"{', '.join(sorted(set(unresolved)))}", file=sys.stderr)

    if not bumps:
        print("all pins already at latest")
        return 0

    total = sum(len(v) for v in bumps.values())
    if not args.apply:
        print(f"\n{total} pins in {len(bumps)} manifests would change (--apply to write)")
        return 0

    for path, changes in bumps.items():
        path.write_text(apply_bumps(texts[path], changes))
    print(f"\nwrote {total} pins across {len(bumps)} manifests")
    print("run `pixi lock` in the affected workspaces")
    return 0


SAMPLE = '''\
[workspace]
channels = ["az://example/general"]

[dependencies]
autopilot                        = "==3.5.4"
geofence                         = "==1.6.2"   # channel behind
ranged                           = ">=1,<2"
wild                             = "*"
local                            = { path = "." }

[pypi-dependencies]
fluxconf = "==0.0.4"

[package]
version = "==9.9.9"

[package.run-dependencies]
python = "==3.12"
'''


def selftest() -> None:
    pins = find_pins(SAMPLE)
    names = [p[1] for p in pins]
    assert names == ["autopilot", "geofence", "python"], names
    assert [p[2] for p in pins] == ["3.5.4", "1.6.2", "3.12"]

    out = apply_bumps(SAMPLE, {pins[0][0]: "3.5.5", pins[1][0]: "2.0.0"})
    # Alignment and trailing comments survive.
    assert 'autopilot                        = "==3.5.5"' in out
    assert 'geofence                         = "==2.0.0"   # channel behind' in out
    # Everything else is untouched.
    assert '[package]\nversion = "==9.9.9"' in out
    assert 'fluxconf = "==0.0.4"' in out
    assert 'ranged                           = ">=1,<2"' in out
    assert out.count("\n") == SAMPLE.count("\n")

    assert is_conda_deps_table("dependencies")
    assert is_conda_deps_table("package.run-dependencies")
    assert is_conda_deps_table("target.linux-64.build-dependencies")
    assert not is_conda_deps_table("pypi-dependencies")
    assert not is_conda_deps_table("package")
    assert not is_conda_deps_table(None)

    print("selftest ok")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
