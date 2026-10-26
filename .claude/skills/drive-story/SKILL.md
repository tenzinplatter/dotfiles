---
name: drive-story
description: Drive one of the user's Shortcut stories to a PR — pick the story from the active iterations, locate its repo, investigate, grill a solution, write local tickets, run implement-tickets, then open a ready-for-review PR. Use when the user invokes /drive-story or asks to take a Shortcut story/ticket to completion.
---

# Drive Story

The main session is the orchestrator. It talks to the user (picking, grilling, approvals) and delegates legwork to subagents. Read `~/.claude/agents-config/issue-tracker.md` for Shortcut ids and workflow states.

## 1. Pick the story

1. `users-get-current`, then `iterations-get-active` and `iterations-get-stories` for each. Keep stories the user owns that are not Completed or Closed.
2. Print the full list (id, state, name) as text. Then one `AskUserQuestion` with at most 4 options: In Progress stories first, then Unstarted, then the rest. Never split the list across several questions. The built-in "Other" takes a story id or name; resolve a name with `stories-search` and confirm if more than one matches.
3. `stories-get-by-id` (includes comments). Assign the user if not already the owner, and move the story to In Progress.

## 2. Locate the repo

Gather clues from the story, its epic, comments, links and any package names. Search, in order:

- Local checkouts: `~/Repositories/*` and `~/Repositories/platform/packages/*` (e.g. `grep -rl --include=package.xml "<name>PKG</name>"`, plus `pixi.toml` / `pyproject.toml` / `Cargo.toml`).
- GitHub org when a package name is known but its repo is not: `gh search code "PKG" --owner greenroom-robotics --filename package.xml` (repeat for the other manifests).

One clear match: use it. Otherwise ask with the top candidates as options. A repo found only on GitHub is cloned into `~/Repositories` (`platform_*` into `~/Repositories/platform/packages/`).

Let `REPO` be its root and `PROJECT` be `sc-<id>-<short-kebab-slug>`.

## 3. Investigate

`arc current_story` / `get_story_note` (pass `cwd`) for prior notes. Dispatch an `Explore` agent (`model: "sonnet"`) with the story text and `REPO`: map the code the story touches, existing patterns, tests, constraints and open unknowns, plus the repo's CLAUDE.md, CONTEXT.md and docs/adr/. If the repo has a `pixi.toml`, it also reads `~/Repositories/platform/website/docs_base/development/index.md`.

## 4. Grill the solution

Summarise the findings to the user, then call the Skill tool with `mattpocock-skills:grilling` and with `mattpocock-skills:domain-modeling` (this is `grill-with-docs`, which cannot be invoked from a skill). Run it in this session, in `REPO`, until the solution is agreed.

## 5. Write tickets

Write `REPO/.scratch/PROJECT/spec.md` (the agreed solution) and one file per vertical slice at `REPO/.scratch/PROJECT/issues/NN-<slug>.md`:

```markdown
# NN: <title>

Blocked by: none | 01, 02

## What
<the change, with the files and types involved>

## Done when
- <observable, testable criterion>
```

Show the tickets and their graph to the user and **wait for an explicit OK**. Never commit `.scratch/`.

## 6. Implement

Call the Skill tool with `implement-tickets` and argument `PROJECT`. It builds `impl/PROJECT`. If it reports stuck tickets, stop and ask before going further.

Domain docs changed during grilling (GLOSSARY.md, CONTEXT.md, docs/adr/) live only in the main checkout. Carry them onto the branch:

```bash
git -C $REPO status --porcelain -- GLOSSARY.md CONTEXT.md docs/adr
git worktree add $REPO/../PROJECT-docs impl/PROJECT
# cp each listed path into the worktree, then:
git -C $REPO/../PROJECT-docs commit -am "docs: <summary>"   # git add new files first
git worktree remove $REPO/../PROJECT-docs
```

## 7. Open the PR

1. `git -C $REPO push -u origin impl/PROJECT`.
2. Write the body with the `mattpocock-skills:pr` skill and include the story URL. `gh pr create --base main --head impl/PROJECT --title "<conventional one-line title>" --body-file <file>` (ready for review, not draft). A hook checks the body links the Shortcut story.
3. Move the story to PR Review and `arc log_session` (with `cwd`).
4. Report the PR URL, any stuck tickets, and the domain-doc copies left uncommitted in the main checkout.
