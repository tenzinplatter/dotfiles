---
name: publishing-pixi-packages
description: Use when a GR pixi-converted ROS repo has per-package pixi.toml manifests whose version is behind the latest `<pkg>@<ver>` release tag — sync each stale pixi.toml version up to its newest tag, commit, push, then release each package either by dispatching the repo's pixi release workflow OR (when that workflow isn't on the default branch yet) by opening a ros-recipes PR that points the package's recipe rev at the bump commit.
---

# Publishing Pixi Packages

## Overview

After the pixi conversion, each package's release version lives in
`packages/<pkg>/pixi.toml` (`[package] version = "..."`). The repo still carries the
old `<pkg>@<ver>` git release tags. When a package's `pixi.toml` version trails its
newest tag, you bump the manifest up to that tag's version, push the bump commit, then
release the package so a recipe lands in `greenroom-robotics/ros-recipes`.

**There are two release paths, decided per repo by whether the pixi release workflow is
on the default branch (see step 3):**
- **A — dispatch the workflow** (`publish-pixi.yml`, or `release-pixi.yml` in newer repos)
  when it exists on `main`. The workflow builds the package and opens the recipe PR.
- **B — open the ros-recipes PR yourself** when the release workflow is NOT on `main`
  (still on a conversion feature branch). You can't dispatch a workflow that isn't on the
  default branch, so you edit the package's `rev` in `ros-recipes` to the bump commit and
  open the PR by hand.

**Direction is one-way: only ever bump UP.** If `pixi.toml` is already at or ahead of
the latest tag, leave it alone. Never downgrade a manifest to match an older tag.

## When to use

- A GR pixi-converted ROS repo (per-package `packages/<pkg>/pixi.toml`) that has a pixi
  release workflow (`publish-pixi.yml` or `release-pixi.yml`) and `<pkg>@<ver>` git tags.
- You want to release the packages whose manifest version is behind their latest tag.

**When NOT to use:**
- Repo not pixi-converted, or no pixi release workflow at all.
- A package's `pixi.toml` is already at/ahead of its newest tag (nothing to release).
- A package has no `<pkg>@<ver>` tag at all (no release line — skip it).

## Procedure

### 1. List the candidate packages and compare versions

For every package manifest, read its current version and find the newest release tag.
**Ignore platform-suffixed tags** (`<pkg>@<ver>-amd64` / `-arm64`) when picking the
latest — use the plain `<pkg>@<ver>` line. Sort with version ordering (`sort -V`), not
lexically.

```bash
git fetch --tags -q
for f in packages/*/pixi.toml; do
  pkg=$(grep -m1 '^name' "$f" | sed 's/.*=\s*//; s/"//g; s/ //g')
  cur=$(grep -m1 '^version' "$f" | sed 's/.*=\s*//; s/"//g; s/ //g')
  latest=$(git tag -l "${pkg}@*" | grep -vE '\-(amd64|arm64)$' \
           | sed "s/^${pkg}@//" | sort -V | tail -1)
  [ -z "$latest" ] && { echo "$pkg: no tag (skip)"; continue; }
  if [ "$cur" = "$latest" ]; then echo "$pkg: $cur up-to-date";
  else echo "$pkg: $cur -> $latest  (CHECK: only bump if $latest > $cur)"; fi
done
```

A package needs releasing only when `latest > cur`. If `cur > latest` (manifest ahead of
tags), skip it — do not downgrade.

### 2. Bump each stale manifest, one commit per package

Edit only the `[package] version` line. Commit each package on its own so each release
gets a distinct bump-commit SHA (the publish dispatch keys off it).

```
chore: bump <pkg> pixi.toml
```

A pure version bump does not change `pixi.lock` — don't re-lock or touch the lockfile.
Let the taplo pre-commit hook reformat; don't hand-align.

### 3. Push the bump commit, and decide the release path

Push the bump commit(s) to the remote. The recipe build needs the bump SHA reachable on
the remote — on `origin/main` if the repo releases via the workflow, or on whatever branch
the conversion lives on (e.g. `tenzinplatter/pixi-conversion`) if you'll open the
ros-recipes PR yourself. The harness may block direct pushes to `main`; if denied, ask the
user to push (`! git push ...`).

```bash
git push origin <branch>      # main, or the conversion feature branch
git fetch origin -q
git merge-base --is-ancestor <bump-sha> origin/<branch> && echo "on remote"
```

**Now decide the path by checking whether the release workflow is on the default branch.**
`gh run list` returns a 404 (`workflow ... not found on the default branch`) when it isn't:

```bash
gh run list --workflow=release-pixi.yml -L 1   # or publish-pixi.yml
```

- **No 404 → Path A** (workflow on `main`): dispatch it (step 4A).
- **404 → Path B** (workflow only on a feature branch): open the ros-recipes PR yourself
  (step 4B). You cannot `gh workflow run` a workflow that isn't on the default branch.

### 4A. Dispatch the release workflow per package (workflow on `main`)

One dispatch per bumped package. For `publish-pixi.yml`, pass the package, a **blank**
version (resolves to the most recent `<pkg>@*` tag), and the bump-commit SHA:

```bash
gh workflow run publish-pixi.yml --ref main \
  -f package=<pkg> -f version= -f sha=<bump-commit-sha>
```

(`release-pixi.yml` takes a `package` input and a `changelog` boolean — no `sha`.) Confirm
the runs started:

```bash
gh run list --workflow=publish-pixi.yml -L 10
```

Each run builds the package as a gate, then opens a recipe PR to
`greenroom-robotics/ros-recipes`.

### 4B. Open the ros-recipes PR per package (workflow not on `main`)

Work in the local `ros-recipes` checkout (`~/Repositories/ros-recipes`). Each package has
an entry in `pixi_native_packages.yaml`; point its `rev` at the **full 40-char** bump SHA
and open a PR. One branch + PR per package.

```bash
cd ~/Repositories/ros-recipes && git fetch origin -q
git checkout -b release-<pkg-hyphenated> origin/main
```

Edit only the package's `rev` (leave `url`, `subdir`, `runner-size` alone):

```yaml
  - name: <pkg>
    url: https://github.com/greenroom-robotics/<repo>.git
    rev: <full-40-char-bump-sha>          # was the previous release SHA
    subdir: packages/<pkg>
    runner-size: 16cpu
```

```bash
git commit -am "bump <pkg readable>"
git push -u origin release-<pkg-hyphenated>
gh -R greenroom-robotics/ros-recipes pr create --base main \
  --head release-<pkg-hyphenated> --title "bump <pkg>" \
  --body "Release <pkg> <ver>; points recipe rev at the version-bump commit."
```

Opening this PR is the outward-facing publish — only do it for packages you intentionally
bumped. (Match the existing repo convention: copy the branch/commit/title style of the most
recent recipe bump.)

The `rev` pins a commit that lives on the conversion feature branch, not `main`. That's fine
for the build, but the SHA could be orphaned if that branch is later squash-merged or
force-pushed — so get the recipe PR merged (the build runs at merge) before the conversion
branch is rewritten.

## How publish-pixi.yml resolves inputs

`workflow_dispatch` inputs are `package`, `version`, `sha`:
- **package** — required; the package to publish.
- **version** — blank → resolves to the most recent `<pkg>@*` tag (`--sort=-version:refname`).
  Set it only to pin a specific older tag.
- **sha** — blank → falls back to the resolved tag's commit. Pass the **bump commit** SHA
  so the recipe builds from the manifest you just bumped.

## Common mistakes

- **Downgrading.** Only bump when the latest tag is *greater* than the manifest version.
  Some manifests (e.g. vendor packages) sit ahead of their tags — leave them.
- **Counting `-amd64`/`-arm64` tags as the latest.** Filter them out; they mirror a plain
  `<pkg>@<ver>` tag and can skew the sort.
- **Lexical version sort.** Use `sort -V` so `1.12.0` beats `1.2.0`.
- **One squashed commit for all bumps.** Each package needs its own bump commit so its
  dispatch can reference a distinct SHA.
- **Releasing before the bump commit is on the remote.** Neither path can build a SHA that
  isn't pushed. Verify with `git merge-base --is-ancestor`.
- **Trying to `gh workflow run` a workflow that isn't on `main`.** It 404s. That's the Path B
  signal — open the ros-recipes PR yourself instead.
- **Using a short SHA for the recipe `rev`.** Use the full 40-char SHA to match convention.
- **Editing more than `rev` in `pixi_native_packages.yaml`.** Only the rev changes.
- **Re-locking on a version-only bump.** `pixi.lock` doesn't change; don't churn it.
- **Releasing a package with no `<pkg>@<ver>` tag.** No tag = no release line; skip it.

## Reference

- `.github/workflows/publish-pixi.yml` / `release-pixi.yml` — the release workflow (when on
  `main`); inputs and resolve logic.
- `ros-recipes/pixi_native_packages.yaml` — per-package recipe entries (`name`, `url`, `rev`,
  `subdir`, `runner-size`); the `rev` you bump in Path B.
- `[[finishing-pixi-conversion]]` — the manifest-cleanup pass that precedes releasing.
- `[[switching-to-pixi-release]]` — makes `release-pixi.yml` canonical; once that lands on
  `main`, releasing moves from Path B back to Path A.
