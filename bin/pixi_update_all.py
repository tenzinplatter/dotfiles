#!/usr/bin/env python3
"""Run `pixi update` (or `pixi lock` with --lock) next to every pixi.toml under CWD."""
import asyncio
import sys
from pathlib import Path

command = "lock" if "--lock" in sys.argv else "update"
args = [a for a in sys.argv[1:] if not a.startswith("-")]
root = Path(args[0]) if args else Path.cwd()
manifests = [p for p in root.rglob("pixi.toml") if ".pixi" not in p.parts]


async def update(d):
    p = await asyncio.create_subprocess_exec(
        "pixi", command, cwd=d,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await p.communicate()
    return d, p.returncode, err.decode().strip()


# ponytail: unbounded fan-out, add a Semaphore if you have hundreds of manifests
async def main():
    return await asyncio.gather(*(update(m.parent) for m in manifests))


results = asyncio.run(main())

failed = [(d, err) for d, rc, err in results if rc != 0]
for d, rc, _ in results:
    print(f"{'✓' if rc == 0 else '✗'} {d}")

print(f"\n{len(results) - len(failed)} ok, {len(failed)} failed")
for d, err in failed:
    print(f"\n--- {d}\n{err}")

sys.exit(1 if failed else 0)
