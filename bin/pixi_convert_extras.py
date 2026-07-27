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
import shutil
import subprocess
import sys

OLD_CHANNEL = "http://localhost:12222/general"
NEW_CHANNEL = "az://stgrcondachannel.blob.core.windows.net/general"
BRANCH = "refactor/pixi-test-extras"
TITLE = "refactor: pixi test extras, az:// channels, mise @v8"
BODY = """Mechanical conversion (scripted, `pixi_convert_extras.py`):

- test deps move from a `tests` environment to a `test` extra, so they fold into
  the `default` env — no separate environment to resolve or solve for
- GR conda channel -> `az://stgrcondachannel.blob.core.windows.net/general`
- mise action/workflow refs -> `@v8`
- `pixi.lock` regenerated for every package

[sc-23514] [sc-21396]
"""

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


def dep_names(blocks, *tables: str) -> set[str]:
    """Names declared in the given dep tables, matched by FULL header path (e.g.
    'dependencies', 'package.host-dependencies').

    Full-path matching matters: a suffix match on 'dependencies' also hits
    '[feature.tests.dependencies]', which would make every test-only dep look
    like it was declared somewhere else and silently droppable.
    """
    names: set[str] = set()
    for header, body in blocks:
        if header is None:
            continue
        if header in tables:
            for line in body:
                m = DEP_RE.match(line)
                if m and not line.lstrip().startswith("#"):
                    names.add(m.group("name"))
        # table form: [dependencies.foo]
        for s in tables:
            if header.startswith(s + "."):
                names.add(header[len(s) + 1:])
    return names


def check_flags(blocks) -> None:
    for header, body in blocks:
        if header is None:
            continue
        if header.startswith("feature.tests.target") and not header.endswith(".dependencies"):
            raise Flag(f"unhandled arch-conditional table ([{header}]) — review by hand")
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
            or re.fullmatch(r"feature\.tests\.target\.[^.]+\.dependencies", header)
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
    # A sibling path dep in the tests feature was installed into the WORKSPACE env,
    # which is where `colcon build`/`colcon test` run. Only two tables put a name
    # in that env: [dependencies] directly, and [package.run-dependencies] via the
    # self dep's run closure. [package.host-dependencies] does NOT — those go to
    # the build backend's isolated env, so a dep that lives only there is invisible
    # to find_package() during the test build.
    in_env = dep_names(blocks, "dependencies", "package.run-dependencies")
    # Sibling path deps that need re-homing into [dependencies] to stay in the env.
    rehome: list[str] = []

    # Arch-conditional test deps: [package.extra-dependencies.<group>] has no
    # target subtable, so [feature.tests.target.<plat>.dependencies] becomes an
    # inline-conditional extras block instead. The deprecated
    # [package.target.<plat>.extra-dependencies] form is not used.
    target_re = re.compile(r"feature\.tests\.target\.(?P<plat>[^.]+)\.dependencies")
    cond_blocks: list[tuple[str, list[str]]] = []
    for header, body in blocks:
        m = header and target_re.fullmatch(header)
        if m:
            cond_blocks.append((
                f"""package.extra-dependencies.test."if(host_platform == '{m.group("plat")}')\"""",
                body,
            ))

    out = []
    for header, body in blocks:
        if header and target_re.fullmatch(header):
            changed = True
            continue  # folded into the extras block below
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
                        if name not in in_env:
                            # Move it to [dependencies] — same workspace env the
                            # tests feature put it in, and a table that takes path
                            # deps (unlike package.extra-dependencies).
                            rehome.append(line)
                        continue  # never keep a path dep in the extras block
                kept.append(line)
            out.append(("package.extra-dependencies.test", kept))
            out += cond_blocks
            changed = True
        elif header == "feature.tests.tasks":
            out.append(("tasks", body))
            changed = True
        elif header and header.startswith("feature.tests.tasks."):
            out.append(("tasks." + header[len("feature.tests.tasks."):], body))
            changed = True
        else:
            out.append((header, body))

    if rehome:
        for i, (header, body) in enumerate(out):
            if header == "dependencies":
                at = max((j for j, l in enumerate(body) if DEP_RE.match(l)), default=len(body) - 1)
                out[i] = (header, body[: at + 1] + rehome + body[at + 1 :])
                changed = True
                break
        else:
            raise Flag(
                "test-only sibling path deps "
                f"({', '.join(DEP_RE.match(l).group('name') for l in rehome)}) "
                "but no [dependencies] table to re-home them into — convert by hand"
            )
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
    # Extras are a *package* concept. A manifest with no [package] table is a
    # dev-only workspace (the repo-root ones that source-build siblings via path
    # deps); its `tests` env is local build tooling that CI never runs, so leave
    # the envs alone and only swap the channel.
    is_package = any(h and (h == "package" or h.startswith("package.")) for h, _ in blocks)

    if has_tests_feature and is_package:
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


def taplo_format(paths: list[pathlib.Path], root: pathlib.Path) -> str | None:
    """Re-align the manifests we rewrote. Our line edits don't pad `=` to match
    taplo's alignment, so without this every converted file shows up as dirty
    under the repo's taplo-format pre-commit hook."""
    if not paths:
        return None
    taplo = shutil.which("taplo")
    if not taplo:
        return "taplo not on PATH — run the repo's pre-commit to format"
    # cwd=root so taplo picks up the repo's .taplo.toml (align_entries etc.);
    # formatting with defaults leaves every file dirty under the pre-commit hook.
    r = subprocess.run(
        [taplo, "format", *map(str, paths)],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if r.returncode != 0:
        return f"taplo format failed: {(r.stderr or r.stdout).strip()}"
    return None


def git(root: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=check
    )


def preflight(root: pathlib.Path, expect: str = "main") -> str | None:
    """Refuse to touch anything unless we're on a clean `expect` branch. Returns
    the reason to hand back to the human, or None when good to go."""
    try:
        branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        # Untracked files are fine — the commit stages explicit paths, so a stray
        # artifact can't ride along. Tracked modifications are not: they'd land in
        # this PR (or get clobbered by the relock).
        dirty = "\n".join(
            l for l in git(root, "status", "--porcelain").stdout.splitlines()
            if not l.startswith("??")
        ).strip()
    except subprocess.CalledProcessError as e:
        return f"git failed: {(e.stderr or e.stdout).strip()}"
    if branch != expect:
        return f"on branch '{branch}', not {expect} — switch to it (or handle this repo manually)"
    if dirty:
        return "worktree is dirty — commit/stash first:\n    " + dirty.replace("\n", "\n    ")
    # A freshly created local branch has no upstream to pull from; that's normal,
    # not an error. Only pull when there is something to pull.
    has_upstream = git(
        root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False
    ).returncode == 0
    if has_upstream:
        try:
            git(root, "pull", "--ff-only")
        except subprocess.CalledProcessError as e:
            return f"git pull failed: {(e.stderr or e.stdout).strip()}"
    return None


def relock(root: pathlib.Path) -> str | None:
    """Regenerate every pixi.lock via the user's pixi_update_all.py."""
    script = shutil.which("pixi_update_all.py") or str(pathlib.Path.home() / "bin" / "pixi_update_all.py")
    if not pathlib.Path(script).exists():
        return "pixi_update_all.py not found — relock manually"
    r = subprocess.run([sys.executable, script, str(root)], cwd=root)
    return None if r.returncode == 0 else "pixi_update_all.py reported failures (see output above)"


def make_pr(root: pathlib.Path, branch: str, paths: list[pathlib.Path]) -> str | None:
    """Branch, stage only what we touched, push, PR (reuse if it exists), open it."""
    try:
        git(root, "checkout", "-B", branch)
        # Stage the lock beside each manifest we rewrote, by exact path. A
        # `*pixi.lock` pathspec would also sweep up locks under build/ or other
        # ignored dirs and make `git add` fail for the whole command.
        locks = [p.parent / "pixi.lock" for p in paths if p.name == "pixi.toml"]
        git(root, "add", "--", *(str(p) for p in paths + [l for l in locks if l.exists()]))
        if git(root, "diff", "--cached", "--name-only").stdout.strip():
            git(root, "commit", "-m", TITLE)
        elif not git(root, "rev-list", "origin/main..HEAD").stdout.strip():
            return "nothing to commit and nothing ahead of main — no PR created"
        git(root, "push", "-u", "origin", branch, "--force-with-lease")
    except subprocess.CalledProcessError as e:
        return f"git failed: {(e.stderr or e.stdout).strip()}"

    view = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "url", "-q", ".url"],
        cwd=root, capture_output=True, text=True,
    )
    url = view.stdout.strip()
    if not url:
        create = subprocess.run(
            ["gh", "pr", "create", "--title", TITLE, "--body", BODY,
             "--head", branch, "--base", "main"],
            cwd=root, capture_output=True, text=True,
        )
        url = create.stdout.strip().splitlines()[-1] if create.returncode == 0 else ""
        if not url:
            return f"gh pr create failed: {(create.stderr or create.stdout).strip()}"
    print(f"\nPR: {url}")
    subprocess.run(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=pathlib.Path)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--branch", default=BRANCH, help="branch/PR name")
    ap.add_argument("--no-pr", action="store_true", help="stop after relock; no branch/commit/PR")
    ap.add_argument(
        "--onto-current",
        action="store_true",
        help="commit onto the branch already checked out (folds into its existing PR) "
             "instead of branching off main",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    if args.onto_current:
        args.branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if args.apply and not args.no_pr:
        why = preflight(root, args.branch)
        if why:
            print(f"⚠ {root}: {why}", file=sys.stderr)
            return 1
    manifests = discover(root)
    if not manifests:
        print(f"no pixi.toml found under {root}", file=sys.stderr)
        return 1

    converted, skipped, flagged = [], [], []
    written: list[pathlib.Path] = []
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
                written.append(m)
            converted.append((rel, notes))

    wf_notes = bump_workflows(root, args.apply)
    taplo_warning = taplo_format(written, root) if args.apply else None

    for rel, notes in converted:
        print(f"✓ {rel}  ({', '.join(notes)})")
    for note in wf_notes:
        print(f"✓ {note}")
    for m, why in flagged:
        print(f"⚠ {m.relative_to(root)}\n    {why}")
    if taplo_warning:
        print(f"⚠ {taplo_warning}")

    print(
        f"\n{len(converted)} converted, {len(skipped)} already current, "
        f"{len(flagged)} need review"
        + ("" if args.apply else "   [DRY RUN — re-run with --apply]")
    )
    if not args.apply or not (converted or wf_notes):
        return 2 if flagged else 0

    # A flagged manifest keeps the localhost channel while CI moves to @v8/fork
    # — PRing that is a guaranteed-red build. Human resolves those first.
    if flagged:
        print("\nStopping before relock/PR — resolve the flagged manifests above, then re-run.")
        return 2

    print("\nRelocking...")
    if warn := relock(root):
        print(f"⚠ {warn}\nStopping before commit/PR.", file=sys.stderr)
        return 1

    if args.no_pr:
        print("\nRelocked. --no-pr: commit and PR yourself.")
        return 0

    touched = written + [root / n.split(":")[0] for n in wf_notes]
    if warn := make_pr(root, args.branch, touched):
        print(f"⚠ {warn}", file=sys.stderr)
        return 1
    return 0


def _selfcheck() -> None:
    """python3 pixi_convert_extras.py --selfcheck — smallest thing that fails if
    the transform breaks. No framework, no fixtures."""
    import tempfile

    before = '''[workspace]
name = "demo"
channels = ["http://localhost:12222/general"]

[dependencies]
demo = { path = "." }
sibling = { path = "../sibling" }

[package.host-dependencies]
sibling = { path = "../sibling" }

[feature.tests.dependencies]
ros-dev-tools-meta = "*"
sibling = { path = "../sibling" }

[feature.tests.tasks]
build = "colcon build"

[feature.tests.tasks.test]
cmd = "colcon test-result"

[environments]
tests = { features = ["tests"] }
prod = { features = ["vessel"] }
'''
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "pixi.toml"
        p.write_text(before)
        out, notes = convert_manifest(p)
        assert out is not None, "expected a conversion"
        assert "[package.extra-dependencies.test]" in out, "extras table missing"
        assert "feature.tests" not in out, "feature.tests survived"
        assert 'extras = ["test"]' in out, "self dep did not gain extras"
        assert NEW_CHANNEL in out and OLD_CHANNEL not in out, "channel not swapped"
        # sibling path dep never stays in extras; it is in [dependencies] already
        extras_body = out.split("[package.extra-dependencies.test]")[1].split("\n[")[0]
        assert "sibling" not in extras_body, "sibling path dep should be dropped from extras"
        assert "[package.host-dependencies]" in out, "host-deps clobbered"
        # other environments must survive; the tests env must not
        assert 'prod = { features = ["vessel"] }' in out, "unrelated env was dropped"
        assert not re.search(r"^\s*tests\s*=", out, re.M), "tests env survived"
        assert "[tasks]" in out and "[tasks.test]" in out, "tasks not promoted"

        # idempotent: converting the result again is a no-op
        p.write_text(out)
        again, _ = convert_manifest(p)
        assert again is None, "second pass should be a no-op"

        # arch-conditional deps fold into the single extras block (extras carry no
        # target selector); the target table itself must not survive
        p.write_text(before.replace(
            "[feature.tests.dependencies]",
            '[feature.tests.target.linux-64.dependencies]\npyds = "*"\n\n[feature.tests.dependencies]',
        ))
        out, _ = convert_manifest(p)
        assert 'pyds = "*"' in out, "arch-conditional dep was dropped"
        assert "target.linux-64" not in out, "target table survived"
        assert out.index('pyds = "*"') > out.index("[package.extra-dependencies.test]"), \
            "arch-conditional dep landed outside the extras block"

        # a sibling path dep that lives ONLY in host-dependencies is not in the
        # workspace env, so it must be re-homed into [dependencies], not dropped
        p.write_text(before.replace(
            "[feature.tests.dependencies]",
            '[package.host-dependencies]\nsib = { path = "../sib" }\n\n'
            '[feature.tests.dependencies]\nsib = { path = "../sib" }',
        ))
        out, _ = convert_manifest(p)
        dep_block = out.split("\n[dependencies]")[1].split("\n[", 1)[0]
        assert 'sib = { path = "../sib" }' in dep_block, "host-only sibling path dep was dropped"
        extras_block = out.split("[package.extra-dependencies.test]")[1].split("\n[", 1)[0]
        assert "sib " not in extras_block and "sib=" not in extras_block, "path dep left in extras block"

        # flags: no-default-feature changes semantics
        p.write_text(before.replace(
            'tests = { features = ["tests"] }',
            'tests = { features = ["tests"], no-default-feature = true }',
        ))
        try:
            convert_manifest(p)
        except Flag:
            pass
        else:
            raise AssertionError("no-default-feature should have been flagged")
    print("selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    sys.exit(main())
