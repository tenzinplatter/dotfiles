#!/usr/bin/env python3
"""Convert per-package pixi.toml from a `tests` environment to a `test` extra,
point the GR channel at az://, and bump the CI workflow to mise @v8.

Usage:
    pixi_convert_extras.py <repo-root> [--apply]

Discovers pixi.toml files itself (rglob). Dry-run by default; --apply writes.
Each transform is independent and idempotent, so a repo that is already
half-converted (e.g. extras done, channel not) converts the rest cleanly.

Anything that cannot be converted *faithfully* is reported and the file is left
alone -- this never guesses at semantics. Flagged cases are a human's call:
  * [feature.tests.target.*]        arch-conditional deps: flat vs if(...) form
  * [feature.tests.activation*]     extras cannot carry activation env vars
  * no-default-feature = true       extras fold into the default env; converting
                                    would silently change what's installed
  * test-only sibling path deps     would be dropped with nowhere else declared
  * no self path dep                nothing to hang extras = ["test"] on
"""

import argparse
import pathlib
import re
import sys

OLD_CHANNEL = "http://localhost:12222/general"
NEW_CHANNEL = "az://stgrcondachannel.blob.core.windows.net/general"
SKIP_DIRS = (".pixi", "_ci_fix", "node_modules", "build", "install", "log", ".git")

# A dep line: `name = "spec"` or `name = { ... }`, keeping alignment whitespace.
DEP_RE = re.compile(r'^(?P<indent>\s*)(?P<name>[A-Za-z0-9_.-]+)(?P<pad>\s*)=(?P<rest>.*)$')
# `{ path = "..." }` — a path dep. path = "." is the self dep.
PATH_DEP_RE = re.compile(r'path\s*=\s*"(?P<path>[^"]*)"')


class Flag(Exception):
    """Raised when a manifest needs a human decision rather than a transform."""


def discover(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(
        p for p in root.rglob("pixi.toml")
        if not any(seg in p.parts for seg in SKIP_DIRS)
    )


def split_blocks(text: str) -> list[tuple[str | None, list[str]]]:
    """Split TOML into [(header_or_None, body_lines)]. Preamble gets header None.

    Comments and blank lines stay attached to the block they follow, so
    formatting survives the round-trip.
    """
    blocks: list[tuple[str | None, list[str]]] = []
    header: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\[([^\[\]]+)\]\s*$", line)
        if m:
            blocks.append((header, body))
            header, body = m.group(1), []
        else:
            body.append(line)
    blocks.append((header, body))
    return blocks


def join_blocks(blocks: list[tuple[str | None, list[str]]]) -> str:
    out: list[str] = []
    for header, body in blocks:
        if header is not None:
            out.append(f"[{header}]")
        out.extend(body)
    return "\n".join(out).rstrip("\n") + "\n"


def dep_names(blocks, *table_suffixes: str) -> set[str]:
    """Names declared in the given dep tables (e.g. 'host-dependencies')."""
    names: set[str] = set()
    for header, body in blocks:
        if header is None:
            continue
        # [package.host-dependencies], [dependencies], [package.run-dependencies]...
        if any(header == s or header.endswith("." + s) for s in table_suffixes):
            for line in body:
                m = DEP_RE.match(line)
                if m and not line.lstrip().startswith("#"):
                    names.add(m.group("name"))
        # table form: [dependencies.foo]
        for s in table_suffixes:
            if header.startswith(s + "."):
                names.add(header[len(s) + 1:])
    return names


def check_flags(blocks) -> None:
    for header, body in blocks:
        if header is None:
            continue
        if header.startswith("feature.tests.target"):
            raise Flag(f"arch-conditional test deps ([{header}]) — needs flat vs if(...) decision")
        if header.startswith("feature.tests.activation"):
            raise Flag(f"[{header}] — extras cannot carry activation env vars")
        if header == "feature.tests":
            # bare table with inline keys (system-requirements, pypi-deps, ...)
            if any(DEP_RE.match(l) for l in body if not l.lstrip().startswith("#")):
                raise Flag("[feature.tests] carries inline keys — review by hand")
        if header.startswith("feature.tests.") and not (
            header == "feature.tests.dependencies"
            or header == "feature.tests.tasks"
            or header.startswith("feature.tests.tasks.")
        ):
            raise Flag(f"unhandled [{header}] — review by hand")
        if header == "environments" or header == "environments.tests":
            for line in body:
                if "no-default-feature" in line and re.match(r"\s*tests\s*=", line):
                    raise Flag("tests env sets no-default-feature — extras change what's installed")
            if header == "environments.tests" and any(
                "no-default-feature" in l for l in body
            ):
                raise Flag("tests env sets no-default-feature — extras change what's installed")


def convert_tests_feature(blocks, path: pathlib.Path) -> tuple[list, bool]:
    """feature.tests.dependencies -> package.extra-dependencies.test, tasks -> tasks."""
    changed = False
    # Names safe to drop from the extras block: sibling path deps that are also
    # declared in a real dep table (so the artifact still gets them).
    declared = dep_names(blocks, "dependencies", "host-dependencies", "run-dependencies")

    out = []
    for header, body in blocks:
        if header == "feature.tests.dependencies":
            kept = []
            for line in body:
                m = DEP_RE.match(line)
                if m and not line.lstrip().startswith("#"):
                    pm = PATH_DEP_RE.search(m.group("rest"))
                    if pm:
                        name = m.group("name")
                        if pm.group("path") == ".":
                            continue  # self dep; extras handles it
                        if name not in declared:
                            raise Flag(
                                f"test-only sibling path dep '{name}' — declare it in a real "
                                "dep table first, or convert this file by hand"
                            )
                        continue  # already declared elsewhere; drop from extras
                kept.append(line)
            out.append(("package.extra-dependencies.test", kept))
            changed = True
        elif header == "feature.tests.tasks":
            out.append(("tasks", body))
            changed = True
        elif header and header.startswith("feature.tests.tasks."):
            out.append(("tasks." + header[len("feature.tests.tasks."):], body))
            changed = True
        else:
            out.append((header, body))
    return out, changed


def drop_tests_env(blocks) -> tuple[list, bool]:
    """Remove the tests environment, preserving every other environment."""
    changed = False
    out = []
    for header, body in blocks:
        if header == "environments.tests":
            changed = True
            continue  # drop the whole table
        if header == "environments":
            kept = [l for l in body if not re.match(r"\s*tests\s*=", l)]
            if len(kept) != len(body):
                changed = True
            # Drop the table entirely if nothing but blanks/comments remain.
            if not any(DEP_RE.match(l) for l in kept if not l.lstrip().startswith("#")):
                continue
            out.append((header, kept))
            continue
        out.append((header, body))
    return out, changed


def add_self_extras(blocks) -> tuple[list, bool]:
    """Add extras = ["test"] to the self path dep (table or inline form)."""
    for i, (header, body) in enumerate(blocks):
        # table form: [dependencies.<pkg>] with path = "."
        if header and header.startswith("dependencies."):
            if any(PATH_DEP_RE.search(l) and PATH_DEP_RE.search(l).group("path") == "."
                   for l in body):
                if any(re.match(r"\s*extras\s*=", l) for l in body):
                    return blocks, False  # already has extras
                new_body = list(body)
                idx = max(j for j, l in enumerate(new_body) if PATH_DEP_RE.search(l))
                new_body.insert(idx + 1, 'extras = ["test"]')
                blocks[i] = (header, new_body)
                return blocks, True
        # inline form: [dependencies] with <pkg> = { path = "." }
        if header == "dependencies":
            for j, line in enumerate(body):
                m = DEP_RE.match(line)
                if not m or line.lstrip().startswith("#"):
                    continue
                pm = PATH_DEP_RE.search(m.group("rest"))
                if pm and pm.group("path") == ".":
                    if "extras" in line:
                        return blocks, False
                    # inject extras into the inline table
                    new = re.sub(r"\}\s*$", ', extras = ["test"] }', line.rstrip())
                    if new == line.rstrip():
                        raise Flag("could not add extras to inline self dep — convert by hand")
                    body = list(body)
                    body[j] = new
                    blocks[i] = (header, body)
                    return blocks, True
    raise Flag('no self path dep (path = ".") — nothing to attach extras = ["test"] to')


def convert_manifest(path: pathlib.Path) -> tuple[str | None, list[str]]:
    """Return (new_text_or_None, notes). None means no change needed."""
    original = path.read_text()
    blocks = split_blocks(original)
    notes: list[str] = []

    has_tests_feature = any(
        h and (h == "feature.tests" or h.startswith("feature.tests."))
        for h, _ in blocks
    )

    if has_tests_feature:
        check_flags(blocks)
        blocks, c1 = convert_tests_feature(blocks, path)
        blocks, c2 = drop_tests_env(blocks)
        blocks, c3 = add_self_extras(blocks)
        if c1 or c2 or c3:
            notes.append("tests env -> test extra")

    text = join_blocks(blocks)
    if OLD_CHANNEL in text:
        text = text.replace(OLD_CHANNEL, NEW_CHANNEL)
        notes.append("channel -> az://")

    return (text if text != original else None), notes


def bump_workflows(root: pathlib.Path, apply: bool) -> list[str]:
    """Point mise reusable-workflow/action refs at @v8."""
    notes = []
    wf_dir = root / ".github" / "workflows"
    targets = list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")) if wf_dir.is_dir() else []
    for wf in targets:
        text = wf.read_text()
        new = re.sub(
            r"(greenroom-robotics/mise/\.github/(?:actions|workflows)/[A-Za-z.-]+)@v[0-7]\b",
            r"\1@v8",
            text,
        )
        if new != text:
            if apply:
                wf.write_text(new)
            notes.append(f"{wf.relative_to(root)}: mise refs -> @v8")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=pathlib.Path)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    root = args.root.resolve()
    manifests = discover(root)
    if not manifests:
        print(f"no pixi.toml found under {root}", file=sys.stderr)
        return 1

    converted, skipped, flagged = [], [], []
    for m in manifests:
        try:
            new_text, notes = convert_manifest(m)
        except Flag as f:
            flagged.append((m, str(f)))
            continue
        rel = m.relative_to(root)
        if new_text is None:
            skipped.append(rel)
        else:
            if args.apply:
                m.write_text(new_text)
            converted.append((rel, notes))

    wf_notes = bump_workflows(root, args.apply)

    for rel, notes in converted:
        print(f"✓ {rel}  ({', '.join(notes)})")
    for note in wf_notes:
        print(f"✓ {note}")
    for m, why in flagged:
        print(f"⚠ {m.relative_to(root)}\n    {why}")

    print(
        f"\n{len(converted)} converted, {len(skipped)} already current, "
        f"{len(flagged)} need review"
        + ("" if args.apply else "   [DRY RUN — re-run with --apply]")
    )
    if args.apply and (converted or wf_notes):
        print("\nNext: relock and commit\n  pixi_update_all.py .")
    return 2 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
