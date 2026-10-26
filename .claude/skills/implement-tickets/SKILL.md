---
name: implement-tickets
description: Implement a project's local tickets from `.scratch/<project>/issues/` end to end — parallel Sonnet implementers in isolated worktrees following the `Blocked by:` graph, an Opus review of every ticket diff, an Opus integration review wherever parallel work is combined, all merged onto an `impl/<project>` branch, worktrees cleaned up afterwards. Use when the user invokes /implement-tickets <project> or asks to implement/orchestrate the tickets of a .scratch project.
---

# Implement Tickets

The main session is the orchestrator. It never writes ticket code itself: implementers implement, reviewers review, the orchestrator plans, merges, relays findings and cleans up.

Argument: the project name. Tickets are `.scratch/<project>/issues/NN-*.md`; `.scratch/<project>/spec.md` is context when present. If the project or its issues don't exist, stop and say so.

## 1. Plan

- Read every ticket. Each has a `Blocked by: none` or `Blocked by: 01, 02` line naming ticket numbers. Build the graph; a cycle or an unknown number is a stop-and-ask.
- Show the user the graph and which tickets can run at once, then proceed without waiting.

## 2. Set up

Let `REPO` be the repo root and `WT=$REPO/../$(basename $REPO).wt`. Never touch the main checkout's working tree — it may be dirty.

```bash
git worktree add -b impl/<project> $WT/<project>-integration main
```

If `impl/<project>` already exists, stop and ask (resume or recreate) rather than overwriting it.

## 3. Run tickets

A ticket is **ready** when every blocker is merged into `impl/<project>`. Whenever tickets become ready — at the start and after every merge — launch all of them at once, one message with one `Agent` call each.

For each ready ticket `NN`:

```bash
git worktree add -b impl/<project>-NN $WT/<project>-NN impl/<project>
```

then dispatch an implementer (`model: "sonnet"`, `run_in_background: true`, no `isolation` — the worktree above is its isolation). Prompt it with:

> Implement the ticket at `<abs path to ticket>` (spec for context: `<abs path to spec.md, if any>`). Work only in `<abs worktree path>` on branch `impl/<project>-NN`; never cd into or edit another checkout.
> - Read the repo's CLAUDE.md, CONTEXT.md and docs/adr/ first, and follow the user's global instructions in ~/.claude/CLAUDE.md (types make invalid state unrepresentable, minimal comments). If the repo has a pixi.toml, read ~/Repositories/platform/website/docs_base/development/index.md and the pages it links.
> - The ticket's **Done when** is the acceptance bar. Run the repo's tests, type checker and linter and make them pass.
> - Commit as you go: one-line conventional commits under 72 chars, no body, no trailers.
> - Reply with: the commits made, the commands you ran to verify and their results, and anything in the ticket you could not satisfy.

## 4. Review each ticket

When an implementer returns, dispatch a reviewer (`model: "opus"`) on `git -C <worktree> diff impl/<project>...HEAD`:

> Review this diff for ticket `<abs path to ticket>`. Assume it is wrong and prove how. Check: every **Done when** item is actually met and tested; correctness (edge cases, error paths, silent failures); invalid states representable in the types; the repo's conventions (CLAUDE.md, CONTEXT.md, docs/adr/); comments that are fluff or stale. Run the tests yourself in `<abs worktree path>`; do not edit anything. Each finding: `file:line — defect → consequence → fix`. End with `VERDICT: PASS` or `VERDICT: FAIL`. PASS means no finding that must be fixed.

- **FAIL**: send the findings to the same implementer with `SendMessage`, then re-review. At most 2 fix rounds; still failing means the ticket is **stuck** — don't merge it, don't launch anything it blocks, keep going with everything else.
- **PASS**: merge it.

## 5. Merge and integration review

```bash
git -C $WT/<project>-integration merge --no-ff impl/<project>-NN -m "chore: merge ticket NN"
```

- Conflicts: resolve trivial ones yourself; otherwise dispatch a `sonnet` agent in the integration worktree using the `mattpocock-skills:resolving-merge-conflicts` skill. A conflict always triggers an integration review.
- If `impl/<project>` moved since this ticket branched (other tickets merged meanwhile), dispatch an integration reviewer (`model: "opus"`) before launching newly ready tickets:

  > The branch in `<integration worktree>` just combined work developed in parallel: tickets `<NN list>` (ticket files: `<paths>`). Review `git diff <pre-merge sha>..HEAD` and the code it touches for seams: conflicting assumptions between the tickets, duplicated helpers or types, one ticket breaking another's behaviour, broken tests. Run the full test suite. Do not edit. Findings as `file:line — defect → consequence → fix`, then `VERDICT: PASS` or `VERDICT: FAIL`.

  On FAIL, dispatch a `sonnet` fixer in the integration worktree with the findings (same commit rules), then re-review; same 2-round cap, after which stop launching new tickets and report.
- After merging, remove that ticket's worktree and branch:
  ```bash
  git worktree remove $WT/<project>-NN && git branch -d impl/<project>-NN
  ```

## 6. Finish

Once no ticket is running or ready:

1. If more than one ticket merged, run one final integration reviewer over `git diff main...impl/<project>` with every ticket file, same prompt and fix loop as above.
2. Clean up every worktree this run created, stuck ones included (report their branch names first, then remove them only if they're clean and fully committed — otherwise leave them and say so):
   ```bash
   git worktree remove $WT/<project>-integration
   git worktree prune
   rmdir $WT 2>/dev/null
   ```
   Keep the `impl/<project>` branch. Don't merge to main, don't push, don't edit the ticket files.
3. Report: merged tickets with their commits, stuck tickets with their unresolved findings and branches, tickets never started because a blocker got stuck, and the final integration verdict.
