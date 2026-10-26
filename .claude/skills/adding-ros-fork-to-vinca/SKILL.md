---
name: adding-ros-fork-to-vinca
description: Use when adding a Greenroom fork of a ROS package we don't own (e.g. Integration-Service, adnav-ros2-driver) to the vinca build pipeline in greenroom-robotics/ros-recipes — wiring each package into rosdistro_additional_recipes.yaml and vinca.yaml's packages_select_by_deps, then opening an automerge PR.
---

# Adding a ROS Fork to the Vinca Pipeline

## Overview

Greenroom forks of third-party ROS repos are built by vinca from the fork's git
tag. Wiring one in means editing two files in `ros-recipes` and opening a PR:

- `rosdistro_additional_recipes.yaml` — one entry **per ROS package** (the recipe source).
- `vinca.yaml` `packages_select_by_deps` — the package **name** so vinca emits a recipe.
- `vinca.yaml` `force_build` — **only** if the package already exists on robostack
  (forking to patch an upstream package, like `generate_parameter_library`).

Canonical example: PRs #146/#147 added `is-core`/`is-ros2` from
`greenroom-robotics/Integration-Service` and `ROS2-SH`.

## Inputs (read from the local clone under ~/Repositories)

Do not curl GitHub — work from the cloned fork. If it isn't cloned, ask for it.

| Input | How to get it |
|-------|---------------|
| `url` | `git remote get-url origin`, normalized to `https://github.com/<org>/<repo>.git` |
| `tag` | latest release tag (`git tag --sort=-creatordate \| head`). Forks tag as `<pkg>@<version>` |
| package list | every non-build `package.xml`: `find . -name package.xml -not -path '*/build/*' -not -path '*/install/*' -not -path '*/.pixi/*'` |
| `<name>` | the `<name>` in each package.xml (recipe key + select_by_deps entry) |
| `additional_folder` | the package's subfolder relative to repo root (omit if package.xml is at root) |
| `version` | the version embedded in the tag (`is-core@1.1.3` → `1.1.3`) |

**The tag is the source of truth for the version.** Vinca uses the recipe's
`version:` field (taken from the tag) for the conda package version;
`manifest_file: package.xml` is read only for *dependencies*, not the version.
Forks routinely leave package.xml out of sync with their release tags — that's
expected and fine (e.g. is-core shipped as `1.1.3` while package.xml said
`3.1.0`). Do NOT gate on package.xml matching the tag; if it disagrees, note it
as a one-line warning and proceed using the tag version.

**Halt only when there is no usable tag version:** the package has no release
tag at all (can't pin a reproducible `version:`), or the tag carries no version
(bare moving ref). Report it and skip that package — don't invent a version.

## Steps

0. **Work in a dedicated git worktree** so parallel runs don't clobber each
   other's branch or working tree in the shared `ros-recipes` checkout:
   ```
   git -C ~/Repositories/ros-recipes worktree add -b add-<pkg> \
     ~/Repositories/ros-recipes-wt/add-<pkg> main
   ```
   Run all edits, commits, and `gh` commands from that worktree dir. Remove it
   after the PR merges: `git -C ~/Repositories/ros-recipes worktree remove <path>`.
1. Locate the clone; read `url`, `tag`, and auto-detect every package.
   **Present the package list and confirm it** before editing.
2. For each package, classify against robostack (kilted distro):
   ```
   pixi search -c robostack-kilted ros-kilted-<name-with-dashes>
   ```
   (ROS name `foo_bar` → `ros-kilted-foo-bar`.)
   - **No result → new package:** add to `additional_recipes` + `packages_select_by_deps`.
   - **Found → upstream fork:** ALSO add to `force_build` (forces a local rebuild
     from the fork over the published robostack build).
3. Edit both YAMLs (entry shape below).
4. Branch, then commit — oneline semantic, no co-author lines:
   `feat: publish <pkg> via vinca` (or list the repo for multi-package).
5. `gh pr create --fill --base main` then `gh pr merge --auto --squash` so it
   merges when CI passes. One PR targeting `main` — never stack PRs.
6. Watch the PR's CI until it resolves:
   ```
   gh pr checks --watch --fail-fast
   ```
   Blocks until all checks finish; exits non-zero if any fail. On failure,
   report which check failed (the command prints it) — do NOT declare success.
   On success the automerge from step 5 lands the PR.

## Recipe entry shape

One block per ROS package in `rosdistro_additional_recipes.yaml`:

```yaml
<ros-pkg-name>:
  url: https://github.com/greenroom-robotics/<Repo>.git
  tag: <pkg>@<version>          # use `branch: <name>` only if there is no release tag
  version: <version>
  additional_folder: <subfolder>  # OMIT this line if package.xml is at repo root
  manifest_file: package.xml
```

Then add `<ros-pkg-name>` to `packages_select_by_deps` in `vinca.yaml` (and to
`force_build` if step 2 found it on robostack).

## Common mistakes

- **Editing only one file.** A package needs BOTH an `additional_recipes` entry
  and a `packages_select_by_deps` entry, or vinca skips it.
- **Wrong key.** The recipe key and the select_by_deps entry are the ROS
  `<name>`, not the repo name (e.g. `is-core`, not `Integration-Service`).
- **Adding `additional_folder` for a root package.** Omit it when package.xml is
  at the repo root.
- **Forgetting force_build for an upstream fork.** Without it, vinca's
  `skip_existing` skips the package because robostack already publishes it.
- **Stacked PRs.** Target every PR at `main`; a stacked base auto-merges
  instantly with no CI.
