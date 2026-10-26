---
name: explain-diff
description: Create a rich, self-contained interactive HTML explanation of a code change, diff, branch, or pull request. Use when the user wants to understand the background, intuition, implementation, data flow, diagrams, or quiz-based reinforcement for a software change, with the result saved as a dated HTML file outside the repository.
---

# Explain Diff HTML

Produce a single long-form HTML page that teaches a reader how a specified code change works. Investigate the surrounding system before explaining the diff: the page should make sense to a beginner while still giving an experienced engineer a concise path to the changed behavior.

## Workflow

1. Identify the change and its scope. Use the current checkout, diff, branch, PR metadata, or user-supplied files as the source of truth. If the target is ambiguous, infer the most likely change from the available context and state the assumption in the page.
2. Explore relevant surrounding code, tests, configuration, callers, data models, and documentation. Trace the old and new paths far enough to explain behavior, not merely file-by-file edits. Prefer checked-in examples and tests over speculation.
3. Build a narrative before writing HTML:
   - what problem or constraint motivated the change;
   - how the old system behaved;
   - the smallest useful mental model of the new behavior;
   - how the implementation realizes that model;
   - edge cases, trade-offs, and observable consequences.
4. Write the output as one self-contained HTML file with inline CSS and JavaScript. Do not depend on external fonts, CDNs, images, JavaScript packages, or network access. Save it outside the repository, preferably at `/tmp/YYYY-MM-DD-explanation-<slug>.html`, using the current date in `YYYY-MM-DD` format.
5. Validate the artifact before handing it off: confirm it exists, is a complete HTML document, contains no external asset dependencies, has working quiz interactions, and satisfies the code-block and quiz checks below. If practical, open it in a browser or use a local HTML inspection tool to catch layout or JavaScript errors.

## Required page structure

Include a clear title, a short summary, and a table of contents linking to these sections in this order:

1. **Background** — Explain only the system needed for the change. Start with an optional beginner-friendly mental model, then narrow to the exact components, contracts, and prior behavior involved.
2. **Intuition** — Explain the core idea before implementation detail. Use small concrete toy inputs and outputs. Show the old and new behavior when comparison makes the change clearer.
3. **Code** — Walk through the changes in conceptual groups, ordered by execution or dependency flow rather than arbitrary file order. Include precise file and line references when available, but do not dump the whole diff.
4. **Quiz** — Include exactly five medium-difficulty, interactive multiple-choice questions. Clicking an option must immediately show whether it is correct and explain why, including the relevant behavior or code path.

Use smooth transitions, plain language, and precise systems-oriented prose. Explain jargon on first use. Use callouts for definitions, invariants, important edge cases, and practical consequences. Keep the page readable on phones with responsive CSS. Do not use top-level tabs; make it one continuous page.

## Diagrams and examples

Use a small, reusable set of HTML/CSS diagram patterns rather than ornamental graphics:

- flow diagrams for requests, data, or control flow;
- before/after panels for changed behavior;
- labeled component cards for system boundaries;
- compact tables for mappings, invariants, and toy data.

Never use ASCII diagrams. Build diagrams with semantic HTML elements and CSS. Label arrows and include example values whenever the diagram describes data movement. Add accessible text or a caption so the explanation does not depend on visual inspection alone.

## Quiz quality rules

Treat quiz design as part of the explanation, not decoration. Before emitting the page, inspect all five questions as a set.

- Randomize the option order independently for each question. Do not always place the correct answer first, second, or in any fixed position. A deterministic shuffle with a per-page seed is acceptable; the visible order must vary across questions.
- Balance correct-answer positions across the five questions as evenly as possible. Never let position, letter, punctuation, or a repeated pattern reveal the answer.
- Keep options comparable in length, grammar, specificity, and confidence. Do not make the correct option conspicuously longer, more qualified, or more technically precise than distractors. Shorten or enrich distractors as needed.
- Make every distractor plausible and tied to a real misunderstanding of the change. Avoid joke answers, obviously impossible claims, “all/none of the above,” and trivia that cannot be inferred from the page.
- Ask about behavior, causality, contracts, edge cases, or trade-offs. Avoid questions whose answer can be guessed from a single copied phrase.
- Keep the correct answer and explanation in the page’s JavaScript data or DOM so the interaction works offline. Reveal feedback only after selection. Mark the selected option and explain both the right reasoning and, when useful, the misconception behind the distractors.
- Ensure the UI does not expose the answer through styling before selection, DOM labels, `title` attributes, source ordering, or accessibility text. Accessibility labels should describe the option, not its correctness.

## HTML and code-block constraints

- Escape user/code-derived text for HTML and JavaScript contexts. Preserve meaningful whitespace in code examples.
- Use `<pre><code>...</code></pre>` for code blocks. The CSS for `pre` must explicitly include `white-space: pre` or `white-space: pre-wrap`; verify every code block in the saved source before delivery.
- Keep JavaScript small, namespaced, and dependency-free. Use event listeners rather than inline handlers when convenient, and handle repeated quiz cards without relying on fragile global selectors.
- Include visible focus states and sufficient color contrast. Do not make correctness depend on color alone.
- Avoid claiming behavior that the inspected source does not support. Distinguish observed facts from reasonable interpretation.

## Final handoff

Return the exact absolute path to the generated HTML file as a clickable local-file link. Briefly state what was inspected and any assumptions or validation limitations. Do not place the deliverable inside the code repository unless the user explicitly requests that.
