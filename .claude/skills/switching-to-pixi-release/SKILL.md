---
name: switching-to-pixi-release
description: Use when a GR ROS repo has the platform_toolbox CI shape (a standard release.yml using ros_semantic_release_action, a disabled release-pixi.yml.disabled, and a tag-triggered publish-pixi.yml) and you need to make the pixi (mise) release the canonical version/tag/recipe path — enable release-pixi, delete the duplicate publish-pixi, and stop the standard release from tagging.
---

# Switching a Repo to the Pixi Release

## Overview

These repos run **two** release systems against the same packages, and both tag
`<pkg>@<ver>`:

- **Standard release** (`release.yml` → `ros_semantic_release_action`): builds debs,
  tags, GitHub release.
- **Pixi release** (`release-pixi.yml.disabled` → `mise/.github/actions/release`):
  bumps `pixi.toml` → commits → tags `<pkg>@<ver>` → GitHub release → opens the
  ros-recipes PR **inline**. Currently disabled.

Plus `publish-pixi.yml` triggers on `push: tags: '*@*'` and *also* opens a ros-recipes
PR. So once the pixi release is enabled and pushes a tag, you get a **duplicate** recipe
PR, and the two release systems **collide** on the `<pkg>@<ver>` tag.

This conversion makes the **pixi release the sole owner of tagging + recipe publishing**
(manually dispatched), retires the duplicate publisher, and demotes the standard release
to deb-build/publish only.

## When to use

- A repo whose `.github/workflows/` contains all of: `release.yml`,
  `release-pixi.yml.disabled`, `publish-pixi.yml`, `test-pixi.yml` (the platform_toolbox
  shape).

**When NOT to use:**
- No `release-pixi.yml.disabled` present (repo isn't on this shape yet).
- `publish-pixi.yml` already deleted and `release-pixi.yml` already enabled (already done).

## End state (what "done" looks like)

- `release-pixi.yml` exists (no `.disabled`), still `workflow_dispatch`, its `package`
  dropdown matching the repo's actual pixi packages.
- `publish-pixi.yml` deleted.
- `release.yml` still runs (debs) but its **release job no longer tags** and creates no
  GitHub release.

## Procedure

### 1. Enable the pixi release

```bash
cd packages/<repo>
git mv .github/workflows/release-pixi.yml.disabled .github/workflows/release-pixi.yml
```

Reconcile its `workflow_dispatch` `package` choice list against the repo's actual pixi
packages. The disabled file's list drifts from reality — e.g. it may list `pfs` where the
package is `pfs_vendor`, or omit newer packages. The source of truth is which dirs hold a
`pixi.toml`:

```bash
# pixi packages = dirs (at any depth under packages/) with a pixi.toml
find packages -name pixi.toml -not -path '*/.pixi/*' -printf '%h\n' | sed 's@.*/@@' | sort -u
```

Cross-check against `release.yml`'s list. Two cases need judgment, not a silent edit:
- **Container dir with no manifest of its own** (e.g. `adnav-ros2-beta/` holding nested
  `adnav_driver`, `adnav_interfaces`, …). The `find` above lists the *nested* package
  names; the container name itself is not a pixi package — don't list it. If `release.yml`
  releases the nested names individually, list those instead.
- **A name in `release.yml` with no `pixi.toml` anywhere.** It isn't pixi-released — leave
  it out, but flag it to the human rather than assuming.

### 2. Delete the duplicate publisher

```bash
git rm .github/workflows/publish-pixi.yml
```

The pixi release opens the ros-recipes PR inline, so `publish-pixi`'s tag-triggered PR is
a duplicate. Note the one thing lost: `publish-pixi` built the package before publishing
(a build gate); the inline mise path does **not** build first. `test-pixi.yml` on PRs is
the remaining build safety net — that's an accepted trade.

### 3. Stop the standard release tagging

First detect which shape `release.yml` is:

```bash
grep -q 'workflows/release.yml@' packages/<repo>/.github/workflows/release.yml \
  && echo REUSABLE-WORKFLOW || echo INLINE-ACTION
```

**INLINE-ACTION** (own `build` + `release` jobs calling the action directly) — edit the
`release` job's `with:`:

```yaml
          github_release: false   # was true — a release needs a tag
          skip_tag: true          # was false
```

(Leave the `build` job alone; it already has `skip_tag: true`.) Self-contained, no
external dependency.

**REUSABLE-WORKFLOW** (`uses: Greenroom-Robotics/ros_semantic_release_action/.github/workflows/release.yml@main`)
— add one input under `with:`:

```yaml
    with:
      ...
      skip_tag: true
```

The reusable workflow gates `github_release` off `skip_tag` itself, so no other change is
needed. **Prerequisite:** the `skip_tag` input must exist in
`ros_semantic_release_action`'s reusable `release.yml` on `main` (the workflow is pulled
via `@main`). If a `skip_tag` input isn't there yet, that change must be merged to that
repo first.

### 4. Commit

Semantic, one-line, no co-author lines:

```bash
git add -A
git commit -m "ci: switch to pixi release as canonical tag/recipe path"
```

## Common mistakes

- **Forgetting the reusable-workflow prerequisite.** Setting `skip_tag: true` on a
  reusable-workflow repo does nothing (and may error) until the `skip_tag` input exists on
  `ros_semantic_release_action@main`. Verify before committing.
- **Setting `skip_tag` but leaving `github_release: true` in the inline shape.** A GitHub
  release needs a tag; you must set `github_release: false` too. (The reusable workflow
  does this for you — only the inline shape needs it spelled out.)
- **Leaving `publish-pixi.yml` in place "just in case".** It re-fires on every tag the
  pixi release pushes → duplicate ros-recipes PRs. Delete it.
- **Shipping the stale `package` dropdown.** The disabled file's list is usually wrong;
  reconcile it to the dirs that actually have a `pixi.toml`.
- **Disabling the standard release entirely.** Only its *tagging* is being removed; it
  still builds/publishes debs. Don't rename it to `.disabled` unless debs are being
  retired too.

## Reference

- `mise` release action: `greenroom-robotics/mise` → `.github/actions/release` and
  `src/commands/ci/release.rs` (writes a per-package `.releaserc`: `bump-pixi` in prepare,
  `recipes-pr` in publish, tag format `<pkg>@<ver>`).
- Standard release: `Greenroom-Robotics/ros_semantic_release_action` — reusable
  `.github/workflows/release.yml` and the root `action.yml` (`skip_tag` input).
