---
name: deslopify-comments
description: Use when writing, reviewing, or cleaning up code comments and docblocks — especially comments that name a rejected alternative ("rather than", "instead of"), name a consumer app (gama, lookout, missim), restate what the code says, or run longer than the code they describe
---

# Deslopify Comments

A comment earns its place by telling the reader something the code cannot. Everything
else is noise that rots.

## Scope — the modal is your first action

**The repo is always the one you are currently in** — the working directory this
session was launched with. Never ask which repo, never search for others.

**Open the modal before anything else.** `AskUserQuestion` is the first tool call of
the run: no `Read`, no `grep`, no `git`, no looking at whichever file is open in the
IDE. Every option below is static text, so there is nothing to compute first and no
reason to delay the prompt.

Counting files and lines happens in step 2, **after** the answers are in — computing it
up front stalls the modal.

Scope has two independent axes, and both are the user's call:

- **Inter-file** — which files may be modified at all.
- **Intra-file** — which lines inside those files may be modified.

### 1. Ask both questions in one modal

One `AskUserQuestion` call, so the user answers in a single pass:

```jsonc
[
  {
    "header": "Files",
    "question": "Which files may I modify?",
    "multiSelect": false,
    "options": [
      { "label": "Working tree only",
        "description": "Files with uncommitted, staged, or untracked changes." },
      { "label": "All files touched on the branch",
        "description": "Every file changed since the merge-base with origin/main, committed work included." }
    ]
  },
  {
    "header": "Lines",
    "question": "Inside those files, which comments may I modify?",
    "multiSelect": false,
    "options": [
      { "label": "Only comments on lines the diff touched",
        "description": "Comments the selected diff added or modified. Pre-existing comments elsewhere in the file are reported, not edited." },
      { "label": "Every comment in the file",
        "description": "Full sweep of each in-scope file, including comments the diff never touched." }
    ]
  }
]
```

State no preference on either axis and mark nothing recommended — which diff the user
wants is theirs to decide.

### 2. Resolve the answers

Only now touch git, in the current repo. The **Files** answer picks the base commit;
everything else is identical.

```bash
REPO=$(git rev-parse --show-toplevel)

# "Working tree only"               → BASE=HEAD
# "All files touched on the branch"  → BASE=$(git -C "$REPO" merge-base HEAD origin/main)
BASE=<per the Files answer>

# Inter-file: the files in scope
FILES=$({ git -C "$REPO" diff --name-only --diff-filter=d "$BASE"
          git -C "$REPO" ls-files --others --exclude-standard; } | sort -u)

# Intra-file: the lines in scope, per file — added or modified only
for FILE in $FILES; do
  echo "== $FILE"
  git -C "$REPO" diff -U0 "$BASE" -- "$FILE" |
    awk '/^@@/ { split($3, h, ","); s = substr(h[1], 2) + 0; n = (h[2] == "" ? 1 : h[2] + 0)
                 if (n > 0) print s "-" (s + n - 1) }'
done
```

Run the per-file line-range loop only when **Lines** = "only comments on lines the
diff touched"; "every comment in the file" makes the whole file fair game. Report the
file count before editing. If the scope resolves to zero files, say so and stop —
don't silently widen to fill it. An untracked file has no diff, so it is entirely in
scope under either Lines answer.

### 3. Applying the intra-file boundary

The line ranges are a permission boundary, not a hint. Same file, different **Files**
answers produce different ranges:

```
useHasNodeMatching.ts   working tree → 15-15    (one line: only the comment there)
useHasNodeMatching.ts   branch       → 1-26     (new file: all of it)
```

Rules when **Lines** = "only comments on lines the diff touched":

- A comment is in scope when **any** of its lines fall in a changed range. A three-line
  block with one edited line is yours entirely — fix or delete the whole block.
- A comment whose lines are all outside the ranges is out of scope **even when it sits
  directly above changed code**, and even when it is the worst comment in the file.
- Deleting an out-of-scope comment is an edit. The rule is not "don't rewrite" — it is
  don't touch.
- Moving code does not claim its comments. If the diff shows a block shifted lines
  without changing its text, it is untouched.

Editing beyond the ranges puts unrelated churn in someone's review and rewrites
decisions the branch never made.

### 4. Report what you can't touch

Whatever either axis excludes gets **reported, not edited** — file:line plus the
one-line fix, so the choice to widen stays with the user. A whole file, package, or
repo is an explicit request, never a default.

## The delete test

Before writing any comment, delete it and ask: **could a future reader of only this
file now make a wrong change?**

- No → don't write it.
- Yes → write the shortest sentence that prevents that wrong change.

Nothing else justifies a comment. Not "it took me a while to work out", not "the
reviewer will ask", not "it's good practice".

## Where comments belong — two places only

A comment may live in exactly two places:

1. **The docblock directly above an exported function, hook, or component** — and only
   when the name and signature leave a question unanswered. A docblock is not owed to
   an export just for being exported.
2. **On a field inside an interface, props type, or options object** — and only when
   the contract isn't already in the field name and its type.

**Everywhere else, delete by default.** Inside a function body, between statements,
above a `const`, inside JSX, at the top of a file: on a deslopify pass these come out
unless the comment survives the delete test. Not "consider trimming" — remove it, and
justify each one you keep.

### The exception bar

A body comment survives only when deleting it lets a reader of *only this file* make a
wrong change. In a real pass over six files, one of six inline comments survived.

```ts
// ✅ SURVIVES — cpaNm's instability is invisible here, so a reader would "fix"
//    the gate to use it
// `rangeM` is stable; `cpaNm` comes and goes as the orientation gate resolves.
const showAlert = view.alert.severity !== "none" || …

// ❌ DELETED — the identifier already says it
// The pause control acts on an avoidance contact. A goal behaviour
// (waypoint / station-keep) has no contact, so it has no pause control.
const pausable = behavior.kind === "avoid";
```

The test is never "is this true?" or "was this hard to work out?" — both were true of
the deleted one. It is only: **does the file mislead without it?**

### This pass is subtractive

**Deslopifying never adds a comment to a file that didn't have one.** Net comment
lines go down, always. An undocumented export is not a finding — leave it alone.

The failure this prevents: reading "docblocks on exports" as a quota and authoring
filler for every export in the file.

```ts
// ❌ The ROS names a PTZ driver is reachable on. Mirrors the driver's launch
//    remappings, which are not introspectable on the graph — the two change together.
// ✅ The ROS names a PTZ driver is reachable on.
export const getPtzEndpoints = (…): IPtzEndpoints => {
```

Everything after the first sentence fails the delete test three ways: the reader
cannot see the launch file, cannot act on "not introspectable", and cannot be helped
by "the two change together" — the coupling is real but nothing in this file enforces
it, so the note rots the day the driver is remapped.

Apply the same test to a docblock as to any comment. `getCameraTiltFrame(namespaceVessel,
cameraName)` answers itself. It gets nothing.

## Principles

### 1. Say what the code IS, never what it is not

```ts
// ❌ Throttle state is a timestamp, not a scheduled timer: StrictMode mounts,
//    cleans up and remounts, and a timer cancelled by that first cleanup never
//    fires again. A timestamp survives the cycle — the next tick re-reads it.
// ✅ Timestamp throttle — survives StrictMode's mount/cleanup/remount cycle.
const lastSample = useRef(0);
```

The negative frame drags the absent design into the reader's head and then spends
three lines dismissing it.

### 2. Never justify a choice against an alternative the reader can't see

The reader has the present code, nothing else. A rejected approach is a dead
pointer — it raises "what was the other way?" and the file can't answer.

```ts
// ❌ Mutates the default client (rather than creating a new one) because the
//    generated tanstack `queryKey` helpers bake its `baseUrl` into the key.
// ✅ The generated tanstack `queryKey` helpers bake the default client's `baseUrl`
//    into every key, so the default client is the one that must carry LAUNCHER_URL.
```

Same fact, but the subject is now the constraint rather than your decision. If ruling
out an alternative genuinely helps, name it concretely as a present-tense property
(`cpaNm comes and goes as the orientation gate resolves`), never as a story about
what you tried.

### 3. Never justify what the library already requires

```ts
// ❌ MapboxDraw keys features by top-level `Feature.id`, falling back to the array
//    index. Selection is UUID-keyed throughout, so the UUID has to sit here as
//    well as in `properties`.
// ✅ MapboxDraw keys features by top-level `Feature.id`, falling back to the
//    array index.
id: geofence.id,
```

Stop at the fact that makes the line necessary. The trailing "so I had to…" is
addressed to a reviewer, and the reviewer leaves when the PR merges.

### 4. Never reach outside the module's boundary

A library documents its own contract. It never names its consumers or the systems
upstream of it — those change without touching the file, so the comment rots while
asserting a coupling the module cannot enforce.

```ts
// ❌ /** Accent for the class tile. Defaults to the class colour;
//        GAMA passes a priority-derived red, Lookout the alert-severity colour. */
// ✅ /** Accent for the class tile. Defaults to the class colour. */

// ❌ ...the avoidance strip shows when `view.avoidance` is set (GAMA), the alert
//    strip when there's an alert or an FE CPA (Lookout)
// ✅ ...the avoidance strip by `view.avoidance`, the alert strip by an alert or
//    an un-avoided range
```

Replace the consumer's name with the **condition** that made it relevant. Same for
sibling components, page names, a consumer's state shape, and another repo's launch
files or config.

**Example values count.** A consumer's name inside a sample string, `@example`, or
placeholder is still this module knowing who calls it — and it is the easiest one to
miss, because it reads as illustration rather than assertion. Fix the sample; never
delete the example itself.

**Make examples dummy, not domain-shaped.** Swapping one real path for another real-looking
path only moves the problem: it still dates, still implies a deployment that may not exist,
and still invites the reader to match it literally. An example exists to show the *shape* of
the argument, so use obvious placeholders — `foo`, `test`, `/this/is/a/test/node`.

```ts
// ❌ e.g. `radar` for `/vessel_1/gama/furuno_radar`   — names a consumer
// ❌ e.g. `radar` for `/vessel_1/sensors/furuno_radar` — no consumer, still a real-looking path
// ✅ e.g. `test` for `/this/is/a/test/node`            — unmistakably an illustration
```

```ts
export interface IUseHasNodeMatchingOptions {
  /** Part of the node's name, e.g. `test` for `/this/is/a/test/node`. */
  contains: string | undefined;
  /**
   * Node-name prefix to search within. e.g. `/foo/` will only search nodes
   * that begin with `/foo/`. Omit to search the whole graph.
   */
  prefix?: string;
}
```

Field docs are one of the two allowed places for a comment, and this is what a good one
looks like: it says what the field is, shows the shape with a throwaway value, and states
what omitting it does. Nothing in it can rot.

Scan every backtick, string literal, and `@example` in a comment for `gama`,
`lookout`, `missim`, `launchpad`, `gama_ui`, `lookout_ui` — case-insensitively, and
including the middle of a path. Grepping only for prose like "GAMA passes" misses these.

### 5. Delete comments that restate the code

```ts
// ❌ The pause control acts on an avoidance contact. A goal behaviour
//    (waypoint / station-keep) has no contact, so it has no pause control.
const pausable = behavior.kind === "avoid";
// ✅
const pausable = behavior.kind === "avoid";
```

### 6. Brevity is part of correctness

A long comment is skimmed, so it stops working. Fold the qualifier into the summary
line and cut the mechanism nobody needs.

```ts
// ❌ Presence is derived from the node's advertised parameter services, so it
//    reflects a live node rather than a configured one — a node that has crashed
//    or not yet started reads as absent.
// ✅ Reflects live nodes only — a crashed or unstarted node is absent.
```

Ask of every clause: does the reader act differently knowing this? Cut it if not.

## Red flags — grep for these

```bash
# defect phrases
grep -rnE "(//|#|\*).*(rather than|instead of|as opposed to|not a |we no longer|used to|previously|Without this)" src/
# consumer names anywhere in a comment, prose or example value (run in alpha)
grep -rniE "(//|#|\*).*(gama|lookout|missim|launchpad)" src/
```

| Phrase found | What it usually means |
|---|---|
| "rather than" / "instead of" | Defending against an invisible alternative → state the constraint |
| "not a…" / "doesn't…" | Saying what the code is not → say what it is |
| "Without this…" / "so it has to…" | Justifying a library requirement → stop after the requirement |
| "GAMA passes…" / "used in gama_ui" | Encapsulation break → name the condition, not the consumer |
| `gama` / `lookout` inside an example path or string | Encapsulation break hiding as illustration → genericise the sample |
| A real-looking path or ID in an `e.g.` | Domain-shaped example → replace with `foo` / `test` placeholders |
| "Mirrors the launch file / the backend config" | Coupling to another repo this file can't enforce → cut it |
| "previously" / "no longer" / "legacy" | Temporal dead pointer → describe the present |
| "Tying it to X made it flash" | Reviewer-facing defence → present-tense property of X |

## Rationalizations

| Excuse | Reality |
|---|---|
| "The next person will ask why I didn't use X" | They won't — they don't know X was on the table. You just put it there. |
| "It's context that took me hours to find" | Then it's a constraint. State the constraint, not your search. |
| "Naming GAMA makes the prop concrete" | It makes it wrong the day GAMA changes. Name the condition. |
| "It's only three extra lines" | Three lines nobody reads, in every file, forever. |
| "The code is complex, it needs explaining" | Complex code needs better names first. Comment only what naming can't reach. |
| "This export has no docblock, I should add one" | Out of scope. This pass removes; it does not document. |
| "This body comment is accurate, so it stays" | Accuracy isn't the bar. Delete unless the file misleads without it. |
| "It explains a tricky bit of logic" | Tricky logic needs a named intermediate, not a comment above it. |
| "It's only an example, not a claim about the consumer" | The example still names who calls you, and it rots the same way. Genericise it. |
| "I'm already in the file, might as well fix the rest" | Out-of-scope lines are someone else's diff. Report them. |
| "This comment is right next to my change" | Adjacency isn't authorship. Check the line ranges. |
| "Deleting a bad comment isn't really an edit" | It is a diff line either way. Don't touch. |
| "A realistic example is more helpful" | The reader needs the shape, not a real path. Realistic examples date, and get copied literally. |
