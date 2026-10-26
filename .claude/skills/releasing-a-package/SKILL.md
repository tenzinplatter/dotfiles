---
name: releasing-a-package
description: Use when opening a PR to release/publish a GR package into ros-recipes by hand — bumping a package's rev/version so the buildfarm republishes it. This is the manual fallback for what `mise ci release` normally automates.
---

# Releasing a Package (manual PR)

Repo: `greenroom-robotics/ros-recipes` (locally `~/Repositories/ros-recipes`).

Normally the package repo's CI (`mise ci release` → `mise ci recipes-pr`) opens this PR
for you. Do it by hand only when that path is broken or unavailable.

## Pick the target file by package type

| Package type | File to edit | What to change |
|---|---|---|
| pixi-native (ships `pixi.toml`, no `package.xml`) | `pixi_native_packages.yaml` | bump the package's `rev` (40-char SHA) to the release commit |
| vinca / package.xml (in `packages_select_by_deps`) | `rosdistro_additional_recipes.yaml` | bump `tag` + `version` to the new release tag |
| hand-authored vendored (DeepStream-linked, etc.) | `vendor_recipes/<pkg>/recipe.yaml` | bump `version` (+ `source` url/tag/sha256) and `build: number` |

Not sure which? Grep the package name across all three. It lives in exactly one.

## The PR

1. Branch: `release/<repo>/<package>` (e.g. `release/platform_grit_interfaces/nmea0183_lib`)
2. Make the one-line edit above. Get the release SHA from the package repo's release tag.
3. Commit: `release: <repo>/<package> v<X.Y.Z>`
4. Push, open PR, enable squash automerge:
   ```
   gh pr create --title "release: <repo>/<package> v<X.Y.Z>" --body "Manual release PR."
   gh pr merge --squash --auto
   ```

## Notes

- For vendored recipes with an unchanged version, still bump `build: number` +1 —
  a rev/version no-op silently republishes nothing (see [[feedback_increment_build_number]]).
- To force a fleet-wide pixi-native rebuild without touching a package, bump
  top-level `rebuild_epoch` in `pixi_native_packages.yaml` instead.
- Never push to `main`; PR only. Automerge is squash.
