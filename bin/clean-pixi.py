#!/usr/bin/env python3
"""Remove all project .pixi/ environment dirs under a root (default: $HOME).

Never touch ~/.pixi itself - that is the pixi installation (bin, global envs).
"""
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def dir_size(path: Path) -> int:
    total = 0
    for dirpath, _, files in os.walk(path):
        for f in files:
            fp = Path(dirpath) / f
            try:
                total += fp.lstat().st_size
            except OSError:
                pass  # ponytail: race with rm/broken symlink, just skip
    return total


def human(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PiB"


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home())
    installation = Path.home() / ".pixi"

    # fd --prune stops descending into matched .pixi dirs (their nested files aren't hits)
    out = subprocess.run(
        ["fd", "-HI", "-t", "d", "-a", "--prune", r"^\.pixi$", str(root)],
        capture_output=True, text=True, check=True,
    ).stdout

    targets = [
        (p, dir_size(p)) for line in out.splitlines()
        if (p := Path(line)) != installation
    ]

    for target, _ in targets:
        print(target)

    total_size = sum([size for _, size in targets])
    print(f"Size to be cleaned: {total_size}")
    cont = input("Continue? [Y/n]").strip()
    if cont.lower() not in ["y", ""]:
        return

    def clean(target: Path, size) -> int:
        shutil.rmtree(target, ignore_errors=True)
        return size

    total = len(targets)
    freed = 0
    with ThreadPoolExecutor() as pool:
        futures = [pool.submit(clean, *t) for t in targets]
        for done, fut in enumerate(as_completed(futures), 1):
            freed += fut.result()
            bar = "#" * (30 * done // total) if total else ""
            print(f"\r[{bar:<30}] {done}/{total} {human(freed)}", end="", flush=True)

    print(f"\n{total} env dir(s) removed, {human(freed)} freed")


if __name__ == "__main__":
    main()
