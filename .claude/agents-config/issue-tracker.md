# Issue tracker: Shortcut + arc

Work is tracked in Shortcut via the Shortcut MCP (`mcp__shortcut__*`). Local working state lives in arc via the arc MCP (`mcp__arc__*`).

## Shortcut

- **Team**: Platform (`@platform`, id `60f0edff-0026-4e05-9477-d69fa3ef523e`). Internal dev-facing work: infrastructure, packaging, CI, tooling.
- **Other teams**: product-specific work belongs to Robotics (gama, and missim via the Robotics iteration) or Perception (lookout). Ask before filing outside Platform.
- **Workflow**: Engineering (`500000005`): Backlog → Unstarted → In Progress → PR Review → Completed. Also On Hold, Externally Blocked, Closed.
- **Epics**: every story should belong to an epic. Find one with `epics-search`. A story without an epic is an error: raise it with the user so an epic can be created. Don't create epics yourself.
- **No triage labels.** Use workflow states only.

### Operations

- **Create**: `stories-create` with the Platform team, the Engineering workflow, Backlog state and the epic.
- **Read**: `stories-get-by-id` (includes comments).
- **Search**: `stories-search` / `epics-search`.
- **Comment**: `stories-create-comment`.
- **Move state**: `stories-update` with `workflow_state_id`.
- **Close**: move to Completed (done) or Closed (won't do), with a comment explaining why.

### Branches

Name every branch for a story with the Shortcut branch name from `stories-get-branch-name`. Shortcut and arc link the branch to the story by this name. Don't invent branch names for story work.

## When a skill says "publish to the issue tracker"

Create a Shortcut story under the relevant Platform epic.

## When a skill says "fetch the relevant ticket"

`stories-get-by-id`, or `mcp__arc__current_story` (with `cwd`) to resolve the story from the git branch.

## arc (local tracking)

Keep arc up to date during every session:

- **Start of session**: `current_story` with `cwd` to load the story note, recent handoffs and open todos.
- **During work**: `append_note` for context worth keeping, `add_todo` for follow-ups (scoped to the repo via `cwd`, or `global: true`).
- **At milestones and before ending**: `log_session` with done / state / next / open questions.
- New story-linked context goes in `create_story_note`, not a free-floating note.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a Shortcut epic and the **child** tickets are its stories.

- **Map**: the epic. Its description holds Notes / Decisions-so-far / Fog. Update with `epics-update`.
- **Child ticket**: a story in the epic, named `[research]`, `[prototype]`, `[grilling]` or `[task]` by its title prefix.
- **Blocking**: `stories-add-relation` with type `blocks`. A ticket is unblocked when every blocker is Completed or Closed.
- **Frontier query**: the epic's stories that are not done, have no open blocker and have no owner. Take the first in epic order.
- **Claim**: `stories-assign-current-user`, then move to In Progress. This is the session's first write.
- **Resolve**: `stories-create-comment` with the answer, move to Completed, then append a gist and link to the epic's Decisions-so-far.
