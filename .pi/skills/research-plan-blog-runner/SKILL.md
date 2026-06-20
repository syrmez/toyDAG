---
name: research-plan-blog-runner
description: Iteratively execute a research plan into a notebook and blog post. Use when the user asks to work through an EDA/research plan, keep todos current, update notebook/report artifacts as new issues arise, and continue until the blog post is evidence-backed and finished.
---

# Research Plan Blog Runner

Use for notebook + blog research projects.

## Loop

Repeat until the report is honestly complete:

1. **Read the plan**
   - Extract explicit deliverables, caveats, and open questions.
   - Maintain a checklist in the plan file. Add todos as soon as gaps appear.

2. **Build the smallest next artifact**
   - Prefer one notebook cell/helper over new modules unless reuse is real.
   - Use local data first. Web/source external facts only when needed.
   - Do not invent facts, timestamps, causes, or match events.

3. **Run it**
   - Execute the notebook or smallest reproducible script.
   - Leave a smoke check/assert for non-trivial normalization, joins, labels, or targets.

4. **Sanity-check outputs**
   - For plots, apply the `graph-sanity` checklist.
   - For tables, check row counts, missing groups, leakage windows, and suspicious NaNs/zeros.

5. **Update all surfaces together**
   - Plan checklist: mark done/add discovered todos.
   - Notebook: executable source of truth.
   - Blog/report: only claims supported by notebook outputs/sources.
   - Figures/data outputs: regenerate deterministically.

6. **Completion audit**
   - Map every plan requirement to evidence: file path, executed notebook, table, figure, source URL, or explicit caveat.
   - If anything is missing, keep going or leave a clear todo; do not call it finished.

## Blog standard

A finished blog post has:

- Motivation and data description.
- Reproducible normalization/target definitions.
- Main charts/tables with caveats.
- No fabricated context.
- Clear takeaways: what looks promising, what failed, what to collect next.

Lazy rule: no complex ML or scraper until the manual/source-backed version proves useful.
