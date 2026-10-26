# Building Greenroom ROS packages with `pixi-build-ros-gr`

This guide describes how to set up a Greenroom Robotics ROS workspace so its packages build into conda packages via the `pixi-build-ros-gr` backend (pixi-native mode), publish to the GR conda channel, and remain reproducible across rebuilds.

It also covers running this alongside the legacy deb release pipeline during the transition window where both must produce artifacts.

**Reference repos**:
- Backend source: `~/Repositories/pixi-gr/crates/pixi_build_ros/`
- Buildfarm: `~/Repositories/ros-recipes/`
- Worked example: `~/Repositories/platform/packages/platform_toolbox/` (16-package workspace)

---

## Architecture

Each package is **independent**. It happens to live in a shared repo for organizational convenience, but as far as pixi and the buildfarm are concerned, each `packages/<pkg>/pixi.toml` is a standalone workspace + package manifest. Sibling deps are versioned matchspecs resolved from the channel, identical in shape to external deps. Cross-package version bumps are explicit and coordinated.

The repo also has an **optional, dev-only top-level `pixi.toml`** that source-builds every package via path deps so developers can edit one package and have dependents rebuild in a single `pixi install`. The buildfarm never reads it.

```
<repo>/
├── pixi.toml                # dev-only workspace; never read by buildfarm
└── packages/
    ├── <pkg_a>/
    │   ├── pixi.toml        # standalone workspace + package
    │   ├── package.xml      # kept while deb pipeline still ships
    │   ├── CMakeLists.txt   # or setup.py + setup.cfg for ament_python
    │   └── …
    └── <pkg_b>/…
```

**Why per-package independence?** Reproducibility. Checking out an old commit of `ros-recipes` and rebuilding produces the same artifacts because each package's `pixi.toml` records exact-version sibling pins (`==X.Y.Z`), which resolve from the channel's append-only history. Path deps would point at moving source and break this.

---

## TL;DR — execution order

1. **Audit** every `package.xml`. Note custom content the new shape can't represent.
2. **Determine versions.** `apt show ros-<distro>-<pkg>` is the source of truth.
3. **Write each package's `pixi.toml`** as a self-contained workspace + package. Sibling deps are versioned channel pins.
4. **Write the dev-only top-level `pixi.toml`** with path deps to all packages.
5. **Patch `CMakeLists.txt`** for any package that uses `ament_cmake_auto` / `ament_auto_find_build_dependencies()`.
6. **Wire each package into the buildfarm** by adding entries to `ros-recipes/pixi_native_packages.yaml`.
7. **Verify** with `pixi install` from the dev workspace, and with `pixi publish --path packages/<pkg>/pixi.toml --to file://…` for a single package.

> **Dual-publish window**: while the deb release pipeline is still active, every package also keeps its `package.xml`, and Python packages keep `setup.py` (+ `setup.cfg` if present). Don't introduce `pyproject.toml` alongside `setup.py`. See "Coexisting with the deb pipeline" below.

---

## Step 1 — Audit `package.xml`

For each package, capture from its `package.xml`:

- **Name** and **version** (cross-check version against `apt show`).
- **buildtool_depend** — what ament flavor this package uses (`ament_cmake`, `ament_python`, `ament_cmake_auto`, etc.).
- **depend / build_depend / exec_depend** — these become host/run dependencies.
- **test_depend** — these aggregate into the dev workspace's `[feature.tests.dependencies]`.
- **member_of_group** — `<member_of_group>rosidl_interface_packages</member_of_group>` is the marker for an `ament_idl` (msg/srv/action) package.
- **`<export>` block** — `<build_type>` tells you the `[package.build.config].build-type` value.
- **Sibling dependencies** — deps on packages in the same workspace. You'll convert these to `==X.Y.Z` channel pins.
- **Anything else**: `condition=` attrs, `<group_depend>`, `<replace>`, `<conflict>`, custom `<export>` children. The new shape doesn't represent these — flag and discuss before proceeding.

---

## Step 2 — Determine versions

The `<version>` field in `package.xml` and in any old `pixi.toml` is commonly stale. The shipped/published artifact version is what consumers expect.

```bash
apt show ros-<distro>-<package-name-with-dashes> 2>/dev/null | grep ^Version:
```

Underscores in package names become dashes in the apt name: `topic_utils` → `ros-kilted-topic-utils`.

Strip the suffix to get clean semver: `1.25.5-0noble` → `1.25.5`. Build a `name → version` table — you'll use it for both `[package].version` fields and for sibling pins in consumers.

If a package isn't in apt (newly added, not yet released), use the latest git tag in its source repo, or coordinate with the user.

---

## Step 3 — Write each package's `pixi.toml`

Each per-package `pixi.toml` is a complete unit: it has its own `[workspace]` block (so pixi can build/install/publish it standalone) plus the `[package]` block describing the artifact.

### Target shape

```toml
[workspace]
name = "<pkg>"
channels = [
  "http://localhost:8000",                  # GR Azure blob proxy
  "https://prefix.dev/robostack-<distro>",  # e.g. robostack-kilted
  "https://prefix.dev/conda-forge",
]
platforms = ["linux-64", "linux-aarch64"]
preview = ["pixi-build"]

[dependencies]
<pkg> = { path = "." }                      # self-as-workspace-member idiom

[package]
name        = "<pkg>"
version     = "<from apt>"
description = "<short, one line>"
license     = "<SPDX expression>"
authors     = ["First Last <first.last@example.com>"]

[package.build.backend]
name    = "pixi-build-ros-gr"
version = "*"

[package.build.config]
mode       = "pixi-native"
build-type = "<ament_cmake | ament_python | ament_idl | ament_cargo>"
distro     = "<kilted | jazzy | humble | …>"

[package.host-dependencies]
# Build/configure-time deps. For ament_cmake: every find_package(X) target
# in CMakeLists.txt MUST be here.

[package.run-dependencies]
# Runtime deps of the installed package.
```

### Sibling deps: versioned channel pins

```toml
# In topic_utils/pixi.toml, depending on xtensor_vendor 1.14.3:
[package.host-dependencies]
xtensor_vendor = "==1.14.3"

[package.run-dependencies]
xtensor_vendor = "==1.14.3"
```

The pixi manifest format does not allow combining `path` with `version` (the deserializer rejects it explicitly). Even if it did, a path dep produces an unversioned matchspec in the published `.conda` — anyone could pick up any version of the sibling, breaking reproducibility. Path deps are reserved for the dev-only top-level workspace (Step 4).

When sibling versions change, every consumer that pins to that sibling must be updated in the same diff. The dev workspace catches mismatches by failing to solve.

### License must be a valid SPDX expression

The solver enforces this.

| Old free text                                       | New SPDX expression       |
|-----------------------------------------------------|---------------------------|
| `"Proprietary"`                                     | `"LicenseRef-Proprietary"`|
| `"Copyright (c) 2025 Greenroom Robotics Pty Ltd"`   | `"LicenseRef-Proprietary"`|
| `"Mozilla Public License Version 2.0"`              | `"MPL-2.0"`               |
| `"BSD-3"`                                           | `"BSD-3-Clause"`          |

### Auto-injected build essentials — do NOT list these

The backend injects these per build-type. Listing them in `[package.host-dependencies]` is redundant at best, conflicting at worst.

| build-type     | Auto-injected (don't list)                                |
|----------------|-----------------------------------------------------------|
| `ament_cmake`  | `cmake`, `ninja`, `compilers` (c, cxx), `python`, `setuptools`, `pip` |
| `ament_python` | `python`, `setuptools`, `pip`                             |
| `ament_idl`    | `cmake`, `ninja`, `compilers`, all rosidl generators/runtimes |

`pkg-config` is NOT auto-injected — keep it explicit if your `CMakeLists.txt` uses it.

### Build-type specifics

#### `ament_cmake`

Every `find_package(X REQUIRED)` in `CMakeLists.txt` needs `X` in `[package.host-dependencies]` (in `ros-<distro>-x` form for ROS packages, or the conda-forge name).

Common mappings:
- `find_package(ament_cmake REQUIRED)` → `ros-<distro>-ament-cmake = "*"`
- `find_package(rclcpp REQUIRED)` → `ros-<distro>-rclcpp = "*"`
- `find_package(Boost REQUIRED COMPONENTS system)` → `libboost-devel = "*"` (host) + `libboost = "*"` (run)
- `find_package(yaml-cpp REQUIRED)` → `yaml-cpp = "*"`
- `find_package(Qt5 ...)` → `qt-main = "*"`

If `CMakeLists.txt` calls `find_package(rclpy REQUIRED)`, `rclpy` must be in **host-deps** (configure time), not just run-deps. CMake doesn't care that `rclpy` is a Python package.

#### `ament_python`

```toml
[package.build.config]
mode       = "pixi-native"
build-type = "ament_python"
distro     = "<distro>"

[package.host-dependencies]
# Empty unless something is needed at build time beyond auto-injected python+setuptools.

[package.run-dependencies]
ros-<distro>-rclpy = "*"
# … any runtime ROS or pip deps your code imports
```

The package needs either `setup.py` (+ `setup.cfg` for `install_scripts` redirection) or a `pyproject.toml`. See "Python packaging" below.

#### `ament_idl` (pure msg/srv/action packages)

```toml
[package.build.config]
mode       = "pixi-native"
build-type = "ament_idl"
distro     = "<distro>"

[package.host-dependencies]
ros-<distro>-ament-cmake = "*"
ros-<distro>-std-msgs    = "*"   # any msg dependencies
# rosidl_default_generators / runtime / pydantic / mypy / etc. are auto-injected.

[package.run-dependencies]
ros-<distro>-std-msgs    = "*"   # same msg dependencies
```

`CMakeLists.txt` must use **explicit `find_package` calls**, not `ament_cmake_auto`. The backend's synthesized `package.xml` carries no `<depend>` tags, so `ament_auto_find_build_dependencies()` finds nothing. See Step 5.

---

## Step 4 — Write the dev-only top-level `pixi.toml`

This is a developer convenience. It source-builds every package via path deps so cross-package edits rebuild dependents in one `pixi install`. The buildfarm never reads this file.

### How discovery separates dev vs buildfarm

When the buildfarm runs `pixi publish --path packages/<pkg>/pixi.toml`, pixi finds the per-package `[workspace]` block first and stops there — it does not walk up to the top-level workspace. When a developer runs `pixi install` from the repo root, pixi finds the top-level workspace and uses its path deps to source-build everything. Verified behavior; same pattern as `launch_ext/pixi.toml` in the GR ecosystem.

### Target shape

```toml
# Dev-only workspace. Source-builds every package via path deps. The buildfarm
# never reads this file; it consumes per-package pixi.toml files in isolation.

[workspace]
name = "<repo_name>"
channels = [
  "http://localhost:8000",
  "https://prefix.dev/robostack-<distro>",
  "https://prefix.dev/conda-forge",
]
platforms = ["linux-64", "linux-aarch64"]
preview = ["pixi-build"]

[dependencies]
pkg_a = { path = "./packages/pkg_a" }
pkg_b = { path = "./packages/pkg_b" }
# … alphabetized, one per package, with `./` prefix.
# Use the package's logical name ([package].name) on the LEFT, even if the
# directory name differs (e.g. pfs_vendor lives at ./packages/pfs).

[feature.tests.dependencies]
# Aggregate of every per-package test_depend across the workspace.
ros-<distro>-ament-cmake-pytest = "*"
ros-<distro>-ament-cmake-gtest  = "*"
ros-<distro>-ament-lint-auto    = "*"
ros-<distro>-ament-lint-common  = "*"
ros-<distro>-integration-test   = "*"
# … etc
nlohmann_json                   = "*"
catch2                          = "*"
pytest                          = "*"
# libboost-devel intentionally unpinned: ros2-distro-mutex constrains it
# per-platform, and a single workspace-level pin can't satisfy both targets
# in the same lockfile.
libboost-devel                  = "*"

[environments]
tests = ["tests"]
```

**No `[package]` block.** The top-level isn't a buildable artifact — it's a workspace shell.

### Drift detection

The dev workspace solves consumer pins (`topic_utils = "==1.25.5"` from each consumer's per-package pixi.toml) against the source-built version (the producer's `[package].version`). If they don't match, the solver fails:

> package 'topic_utils' is required by 'ros2gr' with version '==1.25.5' but the workspace builds 'topic_utils 1.26.0'

That's the forcing function: bumping a producer requires bumping every consumer's pin in the same change. Drift is a build-time error, not a silent mismatch in published artifacts.

### Day-to-day workflows

- `cd <repo_root> && pixi install` — full source-build via the dev workspace.
- `cd <repo_root> && pixi run -e tests <cmd>` — run a command in the tests environment.
- `cd packages/<pkg> && pixi install` — single-package mode; siblings come from the channel.
- `pixi publish --path packages/<pkg>/pixi.toml --to <channel>` — buildfarm-equivalent single-package publish.

---

## Step 5 — Patch `ament_cmake_auto` users

The backend's synthesized `package.xml` contains only:
- `<name>`, `<version>`, `<description>`, `<maintainer>`, `<license>`
- One `<buildtool_depend>` (the ament flavor)
- For `ament_idl`: an extra `rosidl_default_generators` buildtool_depend and the `rosidl_interface_packages` group membership
- The matching `<export><build_type>`

It explicitly does NOT emit `<depend>`, `<build_depend>`, or `<exec_depend>` — see the comment in `pixi-gr/crates/pixi_build_ros/src/pixi_native.rs` near `synthesize_package_xml`.

So `ament_auto_find_build_dependencies()` (which scans `<depend>` tags) finds nothing. Any package whose `CMakeLists.txt` calls that function will fail to configure.

**Fix:** rewrite the CMake to use explicit `find_package` calls. Example for an `ament_idl` package:

```cmake
# Before
find_package(ament_cmake_auto REQUIRED)
ament_auto_find_build_dependencies()

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Foo.msg"
  DEPENDENCIES "std_msgs"
  ADD_LINTER_TESTS
)
ament_auto_package()

# After
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Foo.msg"
  DEPENDENCIES "std_msgs"
  ADD_LINTER_TESTS
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
```

Add explicit `find_package` for every dep that was implicit via `ament_auto_*`.

---

## Step 6 — Wire each package into the buildfarm

Add one entry per package to `ros-recipes/pixi_native_packages.yaml`:

```yaml
packages:
  - name: <pkg>
    url: https://github.com/Greenroom-Robotics/<repo>.git
    rev: <40-char SHA>          # exactly one of rev/ref required
    subdir: packages/<pkg>      # path within the repo to the dir holding pixi.toml
```

`rev` (a 40-char commit SHA) is preferred for reproducibility. `ref` (branch or tag) is accepted as an alternative when CI publishes pre-release tags. Setting both is rejected.

The buildfarm script (`ros-recipes/.scripts/build_pixi_native.py`) clones each entry's repo at the pinned `rev`, then runs `pixi publish --path <subdir>/pixi.toml --to file://<output>`. The whole repo is in the clone, so any path references resolve — but with sibling deps as versioned channel pins, no sibling source paths are needed at build time.

### Cross-package version bump cadence

Bumping `topic_utils` from `1.25.5` → `1.26.0`:

1. PR in the source repo: edit `packages/topic_utils/pixi.toml` (`version = "1.26.0"`) AND every consumer's `topic_utils = "==1.26.0"` pin in the same diff. Merge.
2. Release CI publishes both `topic_utils 1.26.0` and the bumped consumers to the channel.
3. PR in `ros-recipes`: bump SHAs in `pixi_native_packages.yaml` for each affected package.

The dev workspace solver fails immediately if you bump a producer without updating consumers (or vice versa), so this stays in sync.

> **Buildfarm caveat**: when a single CI run rebuilds multiple packages with cross-pins to each other's new versions, packages built later need the earlier ones to already be in a channel. A robust buildfarm indexes its `output_dir` after each build and adds it as an extra channel for subsequent builds; otherwise the order in `pixi_native_packages.yaml` matters. This is a `ros-recipes` concern, not a per-package concern.

---

## Coexisting with the deb pipeline

While the deb release pipeline still ships, every package keeps `package.xml` (and every Python package keeps `setup.py` plus `setup.cfg` if it had one). The pixi-build-ros-gr backend ignores these in `pixi-native` mode (it synthesizes its own `package.xml`), so they're harmless on the conda side.

| File          | Why keep it during dual-publish                                                |
|---------------|--------------------------------------------------------------------------------|
| `package.xml` | Deb pipeline reads it. Conda backend ignores it (synthesizes its own).         |
| `setup.py`    | Deb `ament_python` flow runs `python3 setup.py install`. Conda's `ament_python` build script also uses it (via `setup.py install` when `setup.cfg` is present, or via `pip install .` otherwise). |
| `setup.cfg`   | `install_scripts=$base/lib/<pkg>/` is what positions console scripts where `ros2 run <pkg> <node>` finds them in the deb build. Without it, scripts go to `/usr/bin/` and `ros2 run` breaks. |

**Do NOT introduce `pyproject.toml` alongside `setup.py` during dual-publish.** With both present, setuptools ≥64 errors on metadata conflicts (e.g. `name was already specified in pyproject.toml — name should not be specified in setup()`), and you risk silent version/dep drift between the two.

When the deb pipeline is fully retired:
- Delete `package.xml` from every package.
- Optionally migrate Python packages to `pyproject.toml` (delete `setup.py` + `setup.cfg`). The conda `ament_python` build falls into the `pip install .` path; console scripts go to `$PREFIX/bin/` instead of `$PREFIX/lib/<pkg>/`. Verify `ros2 run <pkg> <node>` still works for each Python package after the switch.

> **Drift warning while both flows coexist**: `package.xml`, `pixi.toml`, and `setup.py`/`setup.cfg` each declare versions, deps, console scripts, data files. The deb pipeline trusts `package.xml` + `setup.py` + `setup.cfg`; the conda pipeline trusts `pixi.toml` (for solver inputs) + `setup.py` + `setup.cfg` (for the actual install). When you bump a version, add a dep, or add a data file during the dual-publishing window, update **every** relevant file. The dual-publish window should be short — once conda is verified for dev use, retire debs and consolidate.

---

## Verification

From the dev workspace:
```bash
pixi info       # parses every manifest; should not error
pixi install    # solves and source-builds every package via path deps
pixi run -e tests <cmd>  # runs in the tests env
```

From a single package (mirrors what the buildfarm does):
```bash
cd packages/<pkg>
pixi info       # should resolve as a standalone workspace
pixi install    # siblings pull from the channel via ==X.Y.Z pins
pixi publish --path . --to file:///tmp/local-channel --target-platform linux-64
ls /tmp/local-channel/linux-64/   # should contain <pkg>-*.conda
```

If a sibling pin is to a version that doesn't exist in the channel yet, the per-package `pixi install` fails until that sibling has been published at least once. Bootstrapping order: leaves first (vendors, then leaf libraries, then consumers).

---

## Failure mode catalogue

In the order you'll likely hit them:

1. **`'license' is not a valid SPDX expression`** — fix licenses to SPDX form (Step 3 table).
2. **`could not find a package configuration file provided by "<dep>"`** during CMake configure — that dep is missing from `[package.host-dependencies]`. Find where `find_package(<dep>)` is in `CMakeLists.txt` and add the corresponding `ros-<distro>-<dep>` (or conda-forge name) to host-deps.
3. **`rosidl_generate_interfaces() the passed dependency 'X' has not been found before using find_package()`** — `ament_cmake_auto` issue. Convert to explicit `find_package` calls (Step 5).
4. **`No candidates were found for <sibling> ==X.Y.Z`** when running `cd packages/<pkg> && pixi install` — that sibling hasn't been published to the channel at version `X.Y.Z` yet. Either publish it first, or use the dev top-level workspace which source-builds it.
5. **Solver mismatch in dev workspace**: *"package 'X' is required by 'Y' with version '==A.B.C' but the workspace builds 'X D.E.F'"* — a producer bump wasn't matched by a consumer pin update (or vice versa). Fix the pin.
6. **`'version' cannot be used with 'path'`** when parsing a manifest — you tried to combine path and version on one entry. Pick one: path dep (no version, dev-only top-level) or versioned channel pin (per-package).
7. **`License classifiers have been superseded by license expressions (PEP 639)`** — only relevant after deb retirement when migrating to pyproject.toml. Remove `License :: …` from `classifiers` if you also have an SPDX `license` field.
8. **`ros2-distro-mutex … which conflicts with libboost-devel X.Y.*`** — your `libboost*` pin conflicts with what robostack's mutex chose for that platform. Drop the pin to `*`; ros2-distro-mutex governs.
9. **304 from localhost:8000** — transient pixi/rattler cache bug with Azure-Blob-style 304 responses. Clear `~/.cache/rattler/cache/repodata/*.shards-cache-v1` and retry.

---

## Things to watch out for when porting test deps

- **Aggregate, don't drop.** Every `<test_depend>` in each package's `package.xml` lands in the dev workspace's `[feature.tests.dependencies]` — even if you can't tell which test package consumes it.
- **Names sometimes don't translate 1:1.** `nlohmann-json-dev` (apt) → `nlohmann_json` (conda-forge). `python3-pytest` → `pytest`. `python3-pydantic` → `pydantic`. Resolve case-by-case.
- **GR-internal apt packages map to `ros-<distro>-*` on conda.** `ros-kilted-integration-test`, `ros-kilted-launch-ext`, etc. — same kebab-case rule from Step 2.

---

## Checklist before declaring done

- [ ] Every per-package `pixi.toml` has both `[workspace]` and `[package]` blocks.
- [ ] Every per-package `pixi.toml` has `[dependencies] <pkg> = { path = "." }`.
- [ ] Every per-package `[package.build.backend]` is `pixi-build-ros-gr`, with `[package.build.config]` declaring `mode = "pixi-native"`, `build-type`, and `distro`.
- [ ] No `cmake/ninja/compilers/python/setuptools/pip` lines in any `[package.host-dependencies]`.
- [ ] All sibling references are versioned channel pins (`==X.Y.Z`) — no path deps in any per-package file.
- [ ] All licenses are valid SPDX expressions.
- [ ] Every `find_package(X)` in every `CMakeLists.txt` has a corresponding `[package.host-dependencies]` entry.
- [ ] No `ament_cmake_auto` / `ament_auto_find_build_dependencies()` references in any `CMakeLists.txt`.
- [ ] Dev-only top-level `pixi.toml` has `[workspace]` + `[dependencies]` (path entries) + `[feature.tests.dependencies]` + `[environments] tests = ["tests"]`. **No `[package]` block.**
- [ ] `pixi info` and `pixi install` succeed from both the repo root and from each package directory.
- [ ] `pixi publish --path packages/<pkg>/pixi.toml --to file://…` produces a `.conda` for at least one package.
- [ ] One entry per package added to `ros-recipes/pixi_native_packages.yaml`, each pinned to a 40-char SHA.
- [ ] If aarch64 is supported, `pixi install --platform linux-aarch64` resolves (or the lockfile contains aarch64 entries).
- [ ] During dual-publish: `package.xml` retained for every package; `setup.py`/`setup.cfg` retained for every Python package; no `pyproject.toml` introduced alongside `setup.py`.
