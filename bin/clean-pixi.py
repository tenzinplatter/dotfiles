#!/usr/bin/env python3
"""Remove all project .pixi/ environment dirs under a root (default: $HOME).

Never touch ~/.pixi itself - that is the pixi installation (bin, global envs).
"""
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm


def dir_size(path: Path) -> int:
    out = subprocess.run(["du", "-sb", str(path)], capture_output=True, text=True)
    return int(out.stdout.split(maxsplit=1)[0]) if out.returncode == 0 else 0


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

    paths = [p for line in out.splitlines() if (p := Path(line)) != installation]
    with ThreadPoolExecutor() as pool:
        targets = list(zip(paths, pool.map(dir_size, paths)))

    for target, _ in targets:
        print(target)

    total_size = sum(size for _, size in targets)
    print(f"Size to be cleaned: {human(total_size)}")
    cont = input("Continue? [Y/n]").strip()
    if cont.lower() not in ["y", ""]:
        return

    def clean(target: Path, size: int) -> int:
        shutil.rmtree(target, ignore_errors=True)
        return size

    freed = 0
    with ThreadPoolExecutor() as pool, tqdm(
        total=total_size, unit="B", unit_scale=True, unit_divisor=1024
    ) as bar:
        futures = [pool.submit(clean, *t) for t in targets]
        for fut in as_completed(futures):
            size = fut.result()
            freed += size
            bar.update(size)

    print(f"{len(targets)} env dir(s) removed, {human(freed)} freed")


if __name__ == "__main__":
    main()
