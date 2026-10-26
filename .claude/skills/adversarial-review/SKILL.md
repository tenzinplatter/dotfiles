---
name: adversarial-review
description: Adversarial code review run by a single orchestrator subagent that dispatches three parallel review agents — one auditing implementation details, one auditing typestates, patterns, and general code quality, one auditing comments for fluff and staleness — then consolidates their findings itself and returns one merged report. All reviewers are told to assume the code is entirely wrong and must prove how and why. Use when the user asks for a code review, an adversarial review, a "tear it apart" review, or invokes /adversarial-review.
---

# Adversarial Review

Review the target code (the working diff by default, or whatever the user names) by spawning **one orchestrator subagent** (a single `Agent` tool call, `run_in_background: false`). The orchestrator runs the three review agents and consolidates their reports itself; its return value is the finished, merged review. When it comes back, relay that report — do not re-synthesize the findings yourself.

## Orchestrator prompt

Give the orchestrator the concrete target (file paths, diff, or `git diff` scope — resolve this before dispatching, don't make it guess) and these instructions:

> Dispatch **three subagents in parallel** — a single message with three `Agent` tool calls — against the target below. Give all three the same target and this framing:
>
> **Assume the code is entirely incorrect. It is your job to tell us how and why it is wrong.** Do not confirm that anything works. Every claim of a defect must name a file:line, a concrete failure scenario (inputs/state → wrong result), and the fix. If you cannot find fault in something, say so explicitly rather than praising it.
>
> ### Agent 1 — Implementation
> Focus: correctness of the logic itself. Off-by-one, boundary and null/empty cases, error handling and silent failures, concurrency/ordering, resource leaks, incorrect algorithms, mishandled return values, broken assumptions about inputs.
>
> ### Agent 2 — Types, patterns & quality
> Focus: whether invalid states are representable (they shouldn't be), type-safety holes, leaky abstractions, misapplied or missing patterns, coupling, naming, dead flexibility, over-engineering, and violations of the codebase's own conventions.
>
> ### Agent 3 — Comments
> Focus: comments that shouldn't exist or no longer tell the truth. Fluff and mechanical restatement of the line below (`// increment i`), commented-out code, TODOs with no owner or context, docstrings/comments that contradict the current code (wrong param names, removed behaviour, stale invariants), and section-header noise. For each: quote the comment, say delete or rewrite, and give the replacement text if rewriting. A comment explaining *why* — a non-obvious constraint, a workaround, a `ponytail:` ceiling — stays; only flag it if it's wrong.
>
> ### Consolidate
> When all three return: merge the reports, deduplicate, rank most-severe first, and drop anything no agent could tie to a concrete failure. Return the consolidated report as your final output, findings formatted as: `file:line — defect → consequence → fix`. Your output goes straight back to the caller — make it the complete review, not a summary of your process.

ponytail: one orchestrator, three reviewers, not a configurable pool. Add a fourth lens only if the user asks.
