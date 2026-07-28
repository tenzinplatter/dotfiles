#!/usr/bin/env python3
"""Bump every exact (`==X.Y.Z`) conda pin in every pixi.toml to the channel's latest.

Usage:
    pixi_bump_pins.py [root] [--apply] [-i PKG]... [--jobs N]

Some pins are held back deliberately (an incompatible transitive dep, a stale
channel build); -i/--ignore keeps those out of the run, and repeats:

    pixi_bump_pins.py -i ivp_manager -i launch_ext --apply

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
import json
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


def find_pins(text: str, ignore=frozenset()) -> list[tuple[int, str, str]]:
    """Return (line_index, package, version) for each exact conda pin."""
    out = []
    table = None
    for i, line in enumerate(text.splitlines()):
        if m := TABLE.match(line):
            table = m.group("name")
            continue
        if not is_conda_deps_table(table):
            continue
        if (m := PIN.match(line)) and m.group("name") not in ignore:
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


async def run_search(args: list[str], sem) -> bytes | None:
    async with sem:
        proc = await asyncio.create_subprocess_exec(
            "pixi", "search", *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
    return out if proc.returncode == 0 else None


def vkey(v: str) -> tuple:
    """Sort key for a version string. Numeric segments compare numerically."""
    # ponytail: not full conda version ordering (no epochs, no `dev`/`post`
    # ranking). Fine for the X.Y.Z pins this bumps; swap in rattler's ordering
    # if a pin ever needs prerelease semantics.
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"[._\-+]", v))


async def sweep(channel: str, platform: str, sem) -> dict[str, str]:
    """name -> newest version for a whole channel, in ONE pixi search.

    `pixi search` takes a per-channel lock on the repodata cache, so N searches
    against one channel cost N * one-search no matter the concurrency. Sweeping
    the channel once and filtering locally collapses that to a single lock hold.
    Only worth it for small private channels -- a `*` glob over conda-forge or
    robostack expands to ~34k names and takes minutes.
    """
    out = await run_search(["--channel", channel, "--platform", platform, "--json", "*"], sem)
    if out is None:
        return {}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    best: dict[str, str] = {}
    for records in data.values():
        for r in records:
            name, ver = r["name"], r["version"]
            if name not in best or vkey(ver) > vkey(best[name]):
                best[name] = ver
    return best


async def latest(pkg: str, channels: tuple[str, ...], platform: str, sem) -> str | None:
    args = []
    for c in channels:
        args += ["--channel", c]
    args += ["--platform", platform, pkg]
    out = await run_search(args, sem)
    if out is None:
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
    ap.add_argument("-i", "--ignore", action="append", default=[], metavar="PKG",
                    help="leave this package's pin alone; repeatable")
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

    ignore = frozenset(args.ignore)
    if ignore:
        print(f"ignoring: {', '.join(sorted(ignore))}\n")

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
        for idx, pkg, ver in find_pins(text, ignore):
            work.setdefault((pkg, channels, platform), []).append((path, idx, ver))

    if not work:
        print(f"{len(manifests)} manifests, no exact pins")
        return 0

    sem = asyncio.Semaphore(args.jobs)

    # Sweep each manifest's primary channel wholesale -- that's where the
    # first-party pins live, and it turns ~one search per pin into one search
    # per channel. Anything the sweep misses falls back to a full multi-channel
    # search below.
    primaries = sorted({(ch[0], plat) for _, ch, plat in work})
    swept = dict(zip(primaries, await asyncio.gather(
        *(sweep(c, p, sem) for c, p in primaries)
    )))
    print(f"swept {len(primaries)} channels, "
          f"{sum(len(s) for s in swept.values())} packages")

    keys = list(work)
    hits = {k: swept[(k[1][0], k[2])].get(k[0]) for k in keys}
    misses = [k for k in keys if hits[k] is None]
    if misses:
        print(f"{len(misses)} pins not on the primary channel, searching individually")
        for key, found in zip(misses, await asyncio.gather(
            *(latest(pkg, ch, plat, sem) for pkg, ch, plat in misses)
        )):
            hits[key] = found
    results = [hits[k] for k in keys]

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

    kept = find_pins(SAMPLE, {"geofence", "python"})
    assert [p[1] for p in kept] == ["autopilot"], kept
    assert find_pins(SAMPLE, {"autopilot", "geofence", "python"}) == []

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

    # Numeric segments must not compare as strings ("10" > "9").
    assert vkey("1.10.0") > vkey("1.9.0")
    assert vkey("2.0.1") > vkey("1.26.3")
    assert max(["1.4.0", "1.10.0", "1.9.2"], key=vkey) == "1.10.0"
    assert vkey("3.5.5") > vkey("3.5.4")
    assert vkey("1.2.3-1") > vkey("1.2.3")

    print("selftest ok")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
