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

<!-- sdocs-agent-block:start v=13 -->
## SmallDocs

The `sdoc` CLI (`sdoc path/to/file.md`) is installed globally and renders local Markdown files securely in the browser (at https://smalldocs.org) in a way that's comfortable for your user to read and share. Nothing hits a server unless the user explicitly saves the file to the SmallDocs cloud or runs `sdoc share`.

When the user says "sdoc it", "sdoc me the plan", or asks for a smalldoc, they mean this: write (or locate) the `.md` file and open it with `sdoc`.

Use it (or offer it) when the user wants to read, share, or export a `.md` file, or when a styled / interactive artifact will land harder than chat prose. Skip it for quick Q&A that already fits in a reply - SmallDocs adds friction without value when there's no document, no rendering opportunity, and nothing to share.

### Basic `sdoc` usage

- `sdoc file.md` - the default way to open a file, for comfortable reading or quick sharing.
- `sdoc bridge file.md` - open a live editing session while you iterate on a file with the user: edits in the browser autosave to the file on disk, and your edits to the file push to the open page. It parks the terminal until the tab closes, so run it in the background when you want to keep working. The first time the page connects, the browser asks to reach a local process (Chrome calls this "Apps on device" / Local Network Access) - the user has to accept, or the page stays read-only. Reach for this when you and the user are working a file back and forth, not for a one-off open.
- `sdoc library` - opens a library view in the browser. SmallDocs automatically indexes every `.md` under the user's home directory; filter by directory, date, or tags (the index doesn't search file content - fall back to `grep` for that). Opt out per-directory with `.sdocsignore` or per-file with `sdocs-library: false` in front matter. (`sdoc library --help` for the full reference.)
- `sdoc file.md +tag1 +tag2` - open the file and inject tags into its YAML front matter which persist. The `+` prefix is shell-safe. Tag files when they're worth rediscovering - the library filters by tag, not by content.
- `sdoc library ls --tags` - print the tags (tag - count) for the current project directory. If you think you might tag the file, run this first so you reuse the project's existing tag vocabulary instead of inventing parallel ones.
- `sdoc share file.md` - copy an encrypted short URL to the clipboard for sending to someone else. The link decrypts in the recipient's browser; the server only sees ciphertext. The agent can't actually deliver - paste the link into wherever the user talks to that person.
- `sdoc --help` - full reference.

### SmallDocs expands what you can create with Markdown

SmallDocs uses the browser to extend what Markdown can be: a styled doc, a chart, a diagram, a slide deck, or an interactive form whose answers come back to you. Reach for one of these when a visual or interactive artifact will land harder than prose - not as a default for every reply. To create something new, write the `.md` file first, then `sdoc path/to/file.md`.

Each command below prints its reference when run with no arguments - run it before writing the matching fenced block. The JSON / DSL shapes are specific and easy to get wrong from memory.

- `sdoc charts` - rendering inline charts (```chart blocks)
- `sdoc diagrams` - rendering inline Mermaid diagrams (```mermaid blocks; has full-screen mode for zoom). Reach for this when drawing system or architectural diagrams (sequence, flow, component layout) - a diagram often communicates the shape of something faster than the equivalent prose.
- `sdoc slides` - inline slide decks (```slide / ~~~slide blocks; has full-screen presentation mode). Slides can be standalone exported as `.pdf` or `.pptx`. `sdoc present file.md` - open file directly in fullscreen presentation mode.
- `sdoc cells` - rendering spreadsheets (```cells blocks): CSV rows where plain values and =formulas (SUM, AVERAGE, IF, ROUND...) sit in the same grid and compute live. The reader can sort, select ranges for quick stats, edit a scratch copy fullscreen, and download the sheet as Excel (.xlsx) with the formulas still working. Name a block (```cells Expenses) to build a workbook of several tabs whose formulas reference each other across sheets (`=Expenses!B4`); run `sdoc cells verify file.md` to compute the whole workbook headlessly and read the values back. Reach for this when handing the user numbers they will want to check or play with - totals, budgets, projections. `sdoc report.csv` opens a CSV file directly as a sheet.
- `sdoc code` - opening a source file or a fenced code block as a syntax-highlighted listing: a light code viewer for reading code with the user away from the IDE. `sdoc app.rb` (or `.js`, `.py`, `.go`, `.rs`, `.ts`...) opens a file as a highlighted listing; a ```lang fenced block is highlighted inline. Comments in the source get a prominent lane so the code reads clearly top to bottom. The fullscreen view adds a line-number gutter and language-aware folding (collapse a whole method or class); a comment mode lets the user annotate a line or method with review notes, kept in the browser rather than the file. You can also pin your own explanations to lines as you open a file - `sdoc app.py 22:"the bug is here" 25-28:"wrong comparison"` - and the file opens as a guided walkthrough: each note is a markdown callout below its line with a Prev / Next stepper, walked in the order you pass the notes (not line order). Name several files to narrate across them - `sdoc app.py 5:"entry point" util.py 12:"it calls into here" app.py 9:"back here"` - and each becomes a tab the walkthrough hops between. When the user asks you to walk them through code, an MR, a diff, or the current changes, build one of these. The file rides in the URL like any document; nothing is uploaded. Reach for it when reading or reviewing code with the user, not for prose.
- `sdoc schema` - styling Markdown (fonts, colors, spacing). The default styles are already comfortable to read; reach for this only when they aren't enough - client-facing polish or a bit of fun.
- `sdoc feedback` - rendering interactive elements (```form blocks) to receive structured input from the user. Run `sdoc feedback file.md` and the user's submission lands as a JSON line on stdout. Good for eliciting complex/subtle feedback. All standard interactive HTML elements with prefilled (but editable) content of your choosing.
<!-- sdocs-agent-block:end -->

## Agent skills

### Issue tracker

Shortcut (Platform team, Engineering workflow, epics), with arc for local notes/todos. See `~/.claude/agents-config/issue-tracker.md`.

### Domain docs

Single-context: the current repo's root `CONTEXT.md` + `docs/adr/`. See `~/.claude/agents-config/domain.md`.
