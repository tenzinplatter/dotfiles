---
name: unifying-deb-pixi-release
description: Use when a GR ROS repo still has the split release setup (a deb-tagging release.yml + a separate release-pixi.yml using mise release@v2 or @v4) and you need to collapse them into ONE coordinator release.yml where the deb path owns tagging/GitHub-release AND triggers the pixi recipe PR in the same dispatch. This is the newer unified shape that REPLACES switching-to-pixi-release.
---

# Unifying the Deb + Pixi Release

## Overview

The older repos run **two** dispatchable release workflows against the same packages:

- `release.yml` — inline `build` + `release` jobs calling `ros_semantic_release_action`.
  Builds debs per arch, then `release` job tags `<pkg>@<ver>` and cuts a GitHub release.
- `release-pixi.yml` — a separate `workflow_dispatch` using `mise/.../actions/release@v2`
  (older repos) or `@v4` (the platform_* DONE cohort were already on `@v4`) that bumps
  `pixi.toml`, tags, and opens the ros-recipes PR. Tags collide with the deb release; you
  must remember to dispatch the right one.

This conversion collapses both into a **single coordinator `release.yml`** with two jobs:

1. **`deb`** — calls the `ros_semantic_release_action` *reusable workflow* (`@main`). It
   builds debs per arch, **owns tagging** (`skip_tag: false`), cuts the GitHub release, and
   in the central Create-Release job bumps `pixi.toml` to the new version and commits it via
   semantic-release's git plugin. The tag lands on that bump commit.
2. **`pixi`** — `needs: deb`; an inline job using `mise/.github/actions/recipes-pr@v4`. It
   reads the tag the deb job just created and opens the ros-recipes PR, pointing the recipe
   `rev` at the bumped-pixi.toml commit.

One dispatch → debs + tag + GitHub release + pixi.toml bump commit + ros-recipes PR.

## Prerequisites (must be on `main`/released before converting any repo)

Verify all three or the coordinator silently no-ops or errors:

1. **platform_cli** has the pixi-bump-in-release fix on `main` (commands `deb-prepare`,
   `deb-publish`, `set-pixi-version`; `get_releaserc` gates the pixi.toml bump + git plugin
   on `skip_build` so only the Create-Release job commits). `ros_semantic_release_action`
   installs platform_cli from `main` by default.
2. **mise** `recipes-pr` composite action is released as `@v4` (bundles
   `mise/setup@v4` + `git fetch --tags` + tag-discovery + `mise ci recipes-pr` +
   conda-channel-proxy teardown).
3. **ros_semantic_release_action** reusable `release.yml@main` has the `skip_tag` input
   (it gates `github_release` off it). It does.

(During testing these lived on branches: `ros_semantic_release_action@…/cli-branch-input`
with a `cli_branch:` input, and `mise/.../recipes-pr@…/recipes-pr-action`. The skill targets
the merged `@main`/`@v4` forms — drop the `cli_branch:` input and branch refs.)

## When to use

- A repo whose `.github/workflows/` contains both `release.yml` (inline deb build+release)
  and `release-pixi.yml` (a `mise .../release@v2` dispatch).

**When NOT to use:**
- `release-pixi.yml` already deleted and `release.yml` already the two-job coordinator
  (already done).
- The repo uses the `switching-to-pixi-release` shape (`release-pixi.yml.disabled` +
  `publish-pixi.yml`). That skill made pixi the *sole* tagger and demoted deb. This one is
  the opposite direction — deb owns tagging again. Don't run both.

## End state (what "done" looks like)

- `release-pixi.yml` **deleted**.
- `release.yml` is the coordinator below: `deb` (reusable workflow, `skip_tag: false`) +
  `pixi` (`needs: deb`, `recipes-pr@v4`).
- Same `workflow_dispatch` `package` dropdown and distro flags the repo had before.
- `changelog` is **hardcoded** (no longer a dispatch input), matching the repo's prior
  deb `release.yml` value (the deb path now owns CHANGELOG.md). Most repos: `false`.

## The coordinator (template)

Fill the `<…>` placeholders from the repo's current `release.yml`.

```yaml
name: Tag & Release
on:
  workflow_dispatch:
    inputs:
      package:
        type: choice
        description: 'If not specified, all packages will be released.'
        options:
          - ""
          # <one line per package, copied from the old release.yml dropdown>
      build_kilted:
        type: boolean
        default: true
        description: "Release for Kilted"
      # <build_iron / build_jazzy ONLY if the old release.yml had them, same defaults>

permissions:
  contents: write
  pull-requests: write
  id-token: write

jobs:
  deb:
    uses: Greenroom-Robotics/ros_semantic_release_action/.github/workflows/release.yml@main
    with:
      package: ${{ inputs.package }}
      package_dir: packages
      build_kilted: ${{ inputs.build_kilted }}
      # <build_iron / build_jazzy passthroughs ONLY for the flags you declared above>
      changelog: false        # hardcode to the repo's PRIOR deb release.yml value
      skip_tag: false
    secrets:
      token: ${{ secrets.API_TOKEN_GITHUB }}

  pixi:
    needs: deb
    runs-on: runs-on=${{ github.run_id }}/runner=2cpu-linux-x64   # RunsOn, not a GH-hosted runner
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
          persist-credentials: false   # checkout is read-only here (recipes-pr uses the GH App token)
      - uses: greenroom-robotics/mise/.github/actions/recipes-pr@v4
        with:
          dispatch-sha: ${{ github.sha }}
          package: ${{ inputs.package }}
          ros-distro: kilted        # the pixi recipe distro; see note below
          gh-app-client-id: ${{ secrets.GH_APP_CLIENT_ID }}
          gh-app-private-key: ${{ secrets.GH_APP_PRIVATE_KEY }}
          azure-client-id: ${{ secrets.AZURE_CLIENT_ID }}
          azure-tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          azure-subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

## Procedure

Work on the repo's `tenzinplatter/pixi-conversion` branch (the conversion lives there).

### 1. Read the four per-repo values out of the old `release.yml`

- **package dropdown** — copy the `options:` list verbatim (keep the leading `""`).
- **distro flags** — which of `build_kilted` / `build_iron` / `build_jazzy` it declares,
  and their `default:` values (e.g. platform_recorder declares kilted+iron, both `true`;
  platform_health uses iron). Declare exactly those, pass through exactly those.
- **changelog** — the value on the `release` job's `changelog:` (the deb tagging path).
  Hardcode it in the coordinator. Most are `false`.
- **package_dir** — almost always `packages`; confirm.

### 2. Confirm the pixi secrets exist in the repo (GOTCHA — only for `@v2`-era repos)

**This step only matters if the old `release-pixi.yml` used `release@v2`.** Check the
`uses:` line first:

- **`@v4`** (the platform_* DONE cohort): it already references `GH_APP_CLIENT_ID` and
  `AZURE_*` as **secrets** — the same names the coordinator needs. No rename, no
  reconciliation; skip to step 3.
- **`@v2`** (older repos): the names differ and you must verify the new ones exist:

| coordinator (recipes-pr@v4)        | old release@v2 release-pixi.yml        |
|------------------------------------|---------------------------------------|
| `secrets.GH_APP_CLIENT_ID`         | `secrets.GH_APP_ID`                   |
| `secrets.GH_APP_PRIVATE_KEY`       | `secrets.GH_APP_PRIVATE_KEY` (same)   |
| `secrets.AZURE_CLIENT_ID`          | `vars.AZURE_READER_CLIENT_ID`         |
| `secrets.AZURE_TENANT_ID`          | `vars.AZURE_TENANT_ID`                |
| `secrets.AZURE_SUBSCRIPTION_ID`    | `vars.AZURE_SUBSCRIPTION_ID`          |

The newer mise action authenticates via an OIDC app **client id** (not the old app id) and
reads Azure creds from **secrets**, not `vars`. Check the repo actually has
`GH_APP_CLIENT_ID` + `AZURE_*` as **secrets**:

```bash
gh -R greenroom-robotics/<repo> secret list
```

If they're missing (only the old `vars`/`GH_APP_ID` exist), the pixi job fails at auth.
Don't silently rewrite the template to the old names — flag it to the human; the org may
need the secrets added (platform_release_testing has them as secrets, which is why the
validated run worked). Note: org-level secrets don't show in repo-level `secret list`
(it returns `[]`) and require `admin:org` to enumerate — absence there isn't proof
they're missing.

### 3. Write the coordinator and delete the duplicate

```bash
cd <repo>
# overwrite release.yml with the filled-in coordinator template, then:
git rm .github/workflows/release-pixi.yml
```

### 4. Commit

Semantic, one-line, no co-author lines:

```bash
git add .github/workflows/release.yml
git commit -m "ci: unify deb + pixi into one release workflow"
```

## Validation (on the test-bed; do once, not per rollout repo)

A clean dispatch from a quiescent `main` should produce, for the chosen package:
- a new `<pkg>@<ver>` tag pointing at a `chore(release): <ver>` bump commit (NOT an
  ancestor of the dispatch sha — it's created this run);
- that commit bumps only `packages/<pkg>/pixi.toml` `[package].version`;
- a GitHub release `<pkg>@<ver>`;
- the pixi job logs the recipe PR at the **bump commit's** sha (`mise` must receive that
  sha as `--sha`, else the recipe builds the wrong tree);
- a ros-recipes PR for `<pkg> v<ver>`.

## Common mistakes

- **Partial publish is pre-existing, not a regression — don't "fix" it.** The deb matrix
  is `fail-fast: true`, but if one arch's apt push fails after another succeeded, that arch
  is published alone. Standard repos behave identically; mimic, don't refactor.
- **Build legs must NOT commit.** Only the central Create-Release job (`skip_build: true`)
  bumps pixi.toml and runs the git plugin. If the per-arch build legs push pixi.toml to
  `main`, the release job (checked out at the original sha) sees "local branch main is
  behind the remote" → "Released 0 packages" → no tag. This is gated in platform_cli's
  `get_releaserc` (prerequisite #1) — don't reintroduce a bump in the build path.
- **Concurrent pushes desync the run.** If `main` advances mid-run (a teammate pushes),
  the release job refuses to publish. Dispatch from a quiescent `main`.
- **Copying the old secret/var names.** See step 2 — the action wants `GH_APP_CLIENT_ID`
  and `AZURE_*` *secrets*, not `GH_APP_ID` / `vars.AZURE_READER_CLIENT_ID`.
- **Hiding `changelog` but flipping its value.** Hardcode the repo's *prior* deb value
  (mostly `false`); don't default it to `true`.
- **Re-adding `release_testing_msgs` to the ros-recipes pipeline.** The test-bed's recipe
  PR is a throwaway — close it, don't merge.
- **Leaving the test-bed branch refs.** Target merged `@main`/`@v4`; drop the `cli_branch:`
  input and any `@tenzinplatter/*` action refs.

## Reference

- Validated coordinator: `platform_release_testing/.github/workflows/release.yml`.
- `ros_semantic_release_action` reusable `.github/workflows/release.yml` (`skip_tag`,
  `package_dir`, build matrix) + root `action.yml`.
- `platform_cli` `groups/release.py` — `get_releaserc` (skip_build gating), `deb-prepare`,
  `deb-publish`, `set-pixi-version`.
- `mise/.github/actions/recipes-pr/action.yml` — dispatch-sha → tag discovery → recipe PR.
- `[[switching-to-pixi-release]]` — the *opposite*, older direction (pixi sole tagger);
  superseded by this skill.
- `[[publishing-pixi-packages]]` — one-off manifest version-bump + release of stale packages.
- `[[finishing-pixi-conversion]]` — the per-package manifest cleanup that precedes releasing.

## Rollout (DONE repos)

Apply per repo on its `tenzinplatter/pixi-conversion` branch: platform_health (iron),
platform_toolbox, platform_testing, platform_peripherals, platform_geographic,
platform_recorder (kilted+iron), platform_planning. Patch the package dropdown, distro
flags, and `changelog` per repo; verify secrets (step 2) before committing.

Note for multi-distro repos: the pixi recipe path is kilted-native (ros-recipes
`pixi_native_packages.yaml`), so `ros-distro: kilted` even when the deb job also builds
iron. If a repo's recipes target a different distro, set it accordingly.
```
