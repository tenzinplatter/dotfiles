---
name: "testing-local-package-builds"
description: "Use when testing a locally built GR pixi package (e.g. a platform_* package like topic_utils) inside a product (gama, missim, lookout) before releasing it — publish it to the local dev channel at /tmp/gr-dev-channel, relock the product workspaces that use it, confirm they resolve the local build, rebuild the containers, and revert afterwards."
styles:
  link: { color: "#60a5fa" }
  blockquote: { borderColor: "#60a5fa" }
# Comments: block "tag:n" = nth (0-indexed) <tag> in render order.
# block kind may carry block_text (first ~60 chars) as a survival hint when the index drifts.
# inline kind anchors via quote (+ optional prefix/suffix). resolved: true marks addressed.
comments:
  - id: "c1"
    kind: "block"
    block: "pre:5"
    block_text: "rm -f \"$CHAN\"/linux-64/*.conda\npixi exec rattler-index fs \"$"
    author: "user"
    color: "#ffbb00"
    at: "2026-10-14T04:22:00.303Z"
    text: "the channel can be deleted wholesale"
    resolved: true
---

# Testing a Local Package Build in a Product

## Overview

Product workspaces have a `dev` feature with a high-priority local channel:

```toml
[feature.dev]
channels = [{ channel = "file:///tmp/gr-dev-channel", priority = 1 }]
```

The channel is empty by default and doesn't affect any solve. A package published into it shadows the remote build for the `dev` environments only; `default`/prod environments keep resolving from the remote channel. The dev containers mount the channel at the same absolute path, so the lock resolves identically on host and in the container.

**Requires** a pixi-gr build with `pixi publish --allow-source-dependencies`, and pixi-plugins with `pixi publish-recurse`.

## Variables

- `PKG` — the package(s) you changed, e.g. `topic_utils`
- `CHAN` — `${GR_DEV_CHANNEL:-/tmp/gr-dev-channel}`
- `PRODUCT` — repo root of gama, missim or lookout

## 1. Seed the channel if it's missing

The product CLIs seed it automatically, but `/tmp` is cleared on reboot. Without `noarch/repodata.json` every solve fails with `could not find subdir 'noarch'`.

```bash
CHAN=${GR_DEV_CHANNEL:-/tmp/gr-dev-channel}
[ -f "$CHAN/noarch/repodata.json" ] || {
  mkdir -p "$CHAN/noarch"
  printf '{"repodata_version":2,"info":{"subdir":"noarch"},"packages":{},"packages.conda":{}}' \
    > "$CHAN/noarch/repodata.json"
}
```

## 2. Publish the package and its path-dependency chain

From the platform module root (e.g. `platform_toolbox`):

```bash
pixi publish-recurse PKG -- --to "file://$CHAN" --build-string-prefix dev --build-number <n>
```

This publishes `PKG` and every workspace it transitively path-depends on (e.g. `topic_utils` → `xtensor_vendor`), dependencies first, one at a time, each with `pixi publish --path . --allow-source-dependencies`. Publishing the whole chain means everything the product sees was built from the same checkout, so there's no ABI mismatch.

- **Stale siblings win.** Every package in the chain shadows its remote build in `dev` environments, whatever its version. Check `git status -sb` in the module first; if it's behind `origin`, pull (or rebase your work) so the siblings aren't older than their releases.
- `--build-string-prefix dev` — makes local builds obvious in `pixi where` output (`dev_h976c01b_1`).
- `--build-number <n>` — the build string hash doesn't change when the source does. Use an `n` higher than any `dev_` build already in `$CHAN/linux-64`, or the new artifact keeps the old filename and the cached one wins.
- The command's output lists every workspace it published. Those package names are the `PKG [DEPS...]` for the steps below.
- Only the host platform is built (`linux-64`). Leave `linux-aarch64` locks alone.

## 3. Relock the product workspaces

From `PRODUCT`:

```bash
pixi update-all --json PKG [DEPS...]
```

This touches only workspaces whose `pixi.lock` already pins one of the packages. Check `results[]`: every entry should have `"status": "ok"`. `failed` carries an `error`; `skipped` carries a `blocker` (a dependency workspace failed). Fix failures before continuing.

## 4. Confirm the local build is resolved

```bash
pixi where --json --verbose --platform linux-64 PKG [DEPS...]
```

Each row of `packages.<pkg>.rows[]` is one (workspace, channel, build) group with its `environments`. Pass when, for every workspace you care about, the row containing `dev` has:

- `"channel": "/tmp/gr-dev-channel"` (`where` prints the path without `file://`)
- `"build"` starting with `dev`

Rows for `default`/prod environments still showing the remote `az://...` channel are expected, not a failure. A `dev` row still on `az://` means the relock didn't take — rerun step 3 for that workspace and check its manifest's `dev` feature has the channel.

## 5. Rebuild the containers

Always use the product CLI, never `docker compose` directly. The dev image installs the env at build time, so a rebuild is required.

| Product | Command |
|---|---|
| gama vessel | `gama vessel up --pixi --build` (or `gama vessel build --pixi <services>`) |
| gama ground station | `gama gs up --pixi --build` |
| missim | `missim up --build` (or `missim build <services>`) |
| lookout | `lookout up --build` (or `lookout build <services>`) |

missim and lookout are pixi-only, so they don't take `--pixi`.

Then confirm each running container's `dev` env holds the local builds:

```bash
docker exec <container> sh -c 'ls /repo/projects/*/ws/.pixi/envs/dev/conda-meta /repo/projects/*/.pixi/envs/dev/conda-meta 2>/dev/null' | grep -E 'PKG|DEP'
```

Every package in the chain should show a `dev_` build, e.g. `topic_utils-1.28.0-dev_h976c01b_1.json` in `gama_vessel`.

## 6. Revert

The relocked `pixi.lock` files reference `file:///tmp/gr-dev-channel` and the local build. **Never commit them.**

The channel is scratch, so delete it wholesale, reseed it (step 1), and relock:

```bash
rm -rf "$CHAN"
# step 1 seed
cd PRODUCT && pixi update-all --json PKG [DEPS...]
```

Then check `pixi where` shows the remote channel again, and `git diff -- '*pixi.lock'` holds no leftover dev-channel references. The running containers still hold the local build until you rebuild them (step 5) or bring them down.

## Common mistakes

| Mistake | Fix |
|---|---|
| Plain `pixi publish` on a package with path deps | Error: `has source run dependencies (...)`. Use `publish-recurse` |
| Relocking/checking only `PKG` | Pass every package in the chain to `update-all` and `where` |
| Same version and build number republished | Bump `--build-number`, or the cached artifact wins |
| Reading `default` rows as a failure | Only `dev` environments see the local channel |
| Committing relocked lockfiles | Revert (step 6) before committing anything |
