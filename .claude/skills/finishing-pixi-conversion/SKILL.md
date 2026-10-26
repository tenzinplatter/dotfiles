---
name: finishing-pixi-conversion
description: Use when a GR ROS repo has already been pixi-converted in the older style (root dev-only pixi.toml workspace + per-package dev AND tests environments) and you need the final cleanup — collapse dev into tests via ros-dev-tools-meta and delete the root workspace.
---

# Finishing the Pixi Conversion

## Overview

The first pass of the pixi conversion gave every package **two** environments — a
`dev` env (build toolchain + build/link deps) and a `tests` env layered on top
(`features = ["dev", "tests"]`) — plus a **root** dev-only `pixi.toml`/`pixi.lock`
workspace that path-deps every package for cross-package source builds.

This final pass removes both:

1. **Collapse `dev` into `tests`.** Delete the `dev` feature/environment; the build
   toolchain now comes from a single `ros-dev-tools-meta` dep inside the `tests`
   feature. `tests` becomes `features = ["tests"]`.
2. **Delete the root workspace.** Remove the repo-root `pixi.toml` and `pixi.lock`
   entirely. Each per-package manifest is already a standalone workspace; cross-package
   source dev uses `path =` sibling deps in individual manifests, not a root workspace.

End state: no root `pixi.toml`/`pixi.lock`; every package has exactly one
`[environments.tests]` and no `dev` feature.

## When to use

- A repo already converted to pixi-native **in the older style**: per-package manifests
  have `[feature.dev.dependencies]`, `[environments.dev]`, and
  `[environments.tests] features = ["dev", "tests"]`; the repo root has a dev-only
  `pixi.toml` + `pixi.lock`.

**When NOT to use:**
- Repo not yet pixi-converted (do the base conversion first — see `website/docs_base/development/`).
- Repo already has no `dev` feature and no root workspace (already finished).

## The end state (what "done" looks like)

Per package `pixi.toml`:
- No `[feature.dev.dependencies]`, no `[environments.dev]`.
- `[environments.tests]` → `features = ["tests"]`.
- `[feature.tests.dependencies]` starts with `ros-dev-tools-meta = "*"`, followed by the
  package's real build/link deps and the original test-only deps.
- Everything else (`[package]`, host/run deps, build config, tasks, target tables) unchanged.

Repo root: `pixi.toml` and `pixi.lock` deleted.

## What `ros-dev-tools-meta` provides

It is the build-toolchain bundle. As of 0.2.0 it pulls in:
`colcon-common-extensions`, `c-compiler`, `cxx-compiler`, `cmake`, `ninja`,
`pkg-config`, `pytest`, and `ros-kilted-ros-base` (which carries `ament-cmake`,
`ament-index-cpp`, `rclcpp`, the rosidl stack, etc.).

So when merging `dev` into `tests`, **drop** these now-redundant deps and replace them
with the single `ros-dev-tools-meta`:
`cxx-compiler`, `c-compiler`, `cmake`, `make`, `ninja`, `pkg-config`,
`colcon-common-extensions`, `ros-kilted-ament-cmake`, `ros-kilted-ament-cmake-python`,
`ros-kilted-ament-index-cpp`.

**Keep** every other `dev` dep — those are the package's actual build/link deps
(`rclcpp`, message packages, vendor libs, `xtensor_vendor`, `libboost-devel`, etc.) and
they must survive the merge. Then union with the existing `[feature.tests.dependencies]`,
de-duplicating. Redundant keeps (e.g. listing `rclcpp` even though `ros-base` provides it)
are harmless — when unsure, keep it. The verification build is the safety net.

`ament_idl` packages: keep `ros-kilted-rosidl-default-generators` and
`ros-kilted-rosidl-default-runtime` in tests deps even though `ros-base` exists — colcon
needs them explicit at source-build time.

## Procedure

Do this once per package, then handle the root.

1. **Per package `pixi.toml`:**
   - Delete the `[environments.dev]` table.
   - Change `[environments.tests]` to `features = ["tests"]`.
   - Compute the merged tests deps: `ros-dev-tools-meta = "*"` (first) + (`dev` deps minus
     the redundant toolchain/ament list above) + (existing `tests` deps). De-dup.
   - Delete `[feature.dev.dependencies]`; write the merged set into
     `[feature.tests.dependencies]`.
   - Leave `[feature.tests.target.<plat>.dependencies]`, tasks, and everything else as-is.

2. **Regenerate that package's lockfile** — the dep set changed, so the lock is stale:
   ```bash
   cd packages/<pkg>
   pixi lock
   ```
   (Requires the conda-channel proxy running locally, e.g. `http://localhost:12222`.)

3. **Delete the root workspace** (once, at repo root):
   ```bash
   git rm pixi.toml pixi.lock
   ```

4. **Verify** each changed package mirrors the buildfarm:
   ```bash
   cd packages/<pkg>
   pixi install --locked
   pixi run -e tests test     # colcon build -> colcon test -> test-result
   ```
   If a `colcon build` fails on a missing header/package, a real build dep was dropped —
   add it back to `[feature.tests.dependencies]`, re-`pixi lock`, re-run.

## Canonical example (`type_adapters`, ament_cmake)

Before:

```toml
[environments.dev]
features = ["dev"]

[environments.tests]
features = ["dev", "tests"]

[feature.dev.dependencies]
cxx-compiler             = "*"
cmake                    = "*"
make                     = "*"
pkg-config               = "*"
colcon-common-extensions = "*"
ros-kilted-ament-cmake     = "*"
ros-kilted-message-filters = "*"
ros-kilted-rclcpp          = "*"

[feature.tests.dependencies]
catch2                       = "*"
ros-kilted-ament-lint-auto   = "*"
ros-kilted-ament-lint-common = "*"
ros-kilted-geometry-msgs     = "*"
```

After (note: toolchain + `ament-cmake` dropped, `message-filters`/`rclcpp` kept):

```toml
[environments.tests]
features = ["tests"]

[feature.tests.dependencies]
ros-dev-tools-meta           = "*"
ros-kilted-message-filters   = "*"
ros-kilted-rclcpp            = "*"
catch2                       = "*"
ros-kilted-ament-lint-auto   = "*"
ros-kilted-ament-lint-common = "*"
ros-kilted-geometry-msgs     = "*"
```

## Common mistakes

- **Dropping a real build dep.** Only the toolchain/ament list is redundant. Keep
  `rclcpp`, message packages, vendor libs, `xtensor_vendor`, `libboost-devel`, etc.
- **Forgetting to re-lock.** Adding `ros-dev-tools-meta` and removing `dev` changes the
  solve — stale locks fail `pixi install --locked`. Re-run `pixi lock` per changed package.
- **Refreshing locks that didn't need it.** `pixi lock` re-solves to *latest*. Only re-lock
  packages you actually edited; don't churn untouched ones.
- **Leaving the root workspace.** The root `pixi.toml`/`pixi.lock` must be deleted, not
  trimmed. Cross-package source dev uses per-manifest `path =` deps (see `website/docs_base/development/`).
- **Stripping `rosidl-default-generators` from `ament_idl` packages.** Keep them explicit.
- **Hand-aligning the TOML.** Let the taplo pre-commit hook reformat; don't fight it.

## Reference

`website/docs_base/development/` in the platform repo — per-package manifest structure, the tests task chain,
and developing against a neighboring source package via `path =`.
