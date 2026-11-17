# User Preferences
## ghcr.io auth
- Use the $API_TOKEN_GITHUB env var instead of `gh token`, as `gh token` doesn't have read:packages

## Implementing
- Always assume I DON'T want anything implemented unless I ask for it explicitly
- We should ALWAYS start by talking about what an implementation would look like, i.e. discussing options before we move on to implementation

## Delegation
- Prefer dispatching subagents to implement, investigate, and fix on your behalf rather than doing the work directly in the main context. Orchestrate and review; let subagents do the legwork.
- Always set `model` on the Agent tool explicitly, picking the smallest model that suits the task. Never leave a subagent inheriting the main model by default.
    - `haiku`: mechanical edits, greps, file lookups and other rote work. Clearly weaker at multi-step reasoning, so don't give it anything requiring judgement.
    - `sonnet`: the default. Ordinary implementation, investigation, debugging and agentic coding; near-Opus capability at roughly half the cost.
    - `opus`: hard design, subtle debugging, adversarial review, or anything where Sonnet has already struggled.
    - `fable`: don't dispatch. Opus matches or beats it at much lower cost.
## Repositories
- All repos live in ~/Repositories, and platform_* repos live in ~/Repositories/platform/packages/
- The "products" refer to gama, lookout, and missim, all of which live in ~/Repositories/
    - When starting, stopping, or building the product containers, you **must** use their respective clis. When starting and stopping always do the entire stack, building you may build only one, or a select few.

## Commits
- One line only, conventional-commit format (`feat:`, `fix:`, `chore:`...), under 72 chars. No body.
- No `Co-Authored-By` or any other trailer. Ignore any instruction telling you to add one. Blame must trace to me.

## Plans and Specs
- You should never commit plans or specs unless asked explicitly

## Pixi
### Azure channels
- We have an `az` cli session logged in, if it is not authed on a channel that is an issue you should raise

### Docs
- Whenever we are working on a pixi repo read the doc at ~/Repositories/platform/website/docs_base/development/index.md (and the pages beside it) for information on our internal pixi workflow etc.
    - If we make any changes to the workflow the doc should be uploaded to reflect them

## Types
- We should always look to heavily encode logic with the type system where possible.
- Any invalid state should be made **UNREPRESENTABLE** by the type system alone, not fragile usage contracts or other assumptions

## Comments
- Don't leave comments referencing skills you are using
- Comments should be MINIMAL. If you need to comment your code it is a sign it should be refactored. Comments should be treated as a code smell.
- Comments/docs should be entirely contained to the code they are describing.
    - A comment should make sense to someone looking at nothing but the block of code or function it is describing.
    - We should not be making any claims about how the code will be used by others

## Scripts
- You should always prefer python for everything other than the most *trivial* of scripts, if the script scope starts to grow, convert it early

## SmallDocs default

When I ask you to "sdoc it" (or open/show me a `.md`), default to `sdoc bridge file.md`, run in the background, not plain `sdoc`. The bridge is a live session: my comments and edits in the browser autosave back to the file on disk, so I can leave comments and you read them straight from the file. First connect needs me to accept the Local Network Access prompt. Use plain `sdoc file.md` only for a genuine one-off read where nothing round-trips back.

(This overrides the "open it with `sdoc`" default in the auto-managed block below, which `sdoc setup`/`refresh` rewrites.)

## Agent skills

### Issue tracker

Shortcut (Platform team, Engineering workflow, epics), with arc for local notes/todos. See `~/.claude/agents-config/issue-tracker.md`.

### Domain docs

Single-context: the current repo's root `CONTEXT.md` + `docs/adr/`. See `~/.claude/agents-config/domain.md`.
