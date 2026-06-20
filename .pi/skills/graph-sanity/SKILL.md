---
name: graph-sanity
description: Sanity-check generated charts before sharing them. Use whenever creating, updating, or saving plots/figures in notebooks, reports, or data analysis work; catches sorted-x bugs, duplicate timestamps, overlapping labels, misleading axes, missing event markers, and visual artifacts.
---

# Graph Sanity

After generating any figure that will be shown to the user or referenced in a report:

1. **Data checks before plotting**
   - Sort line plots by x within each series.
   - For time-bucketed multi-series plots, deduplicate to one row per `(series, timestamp bucket)`.
   - Drop or explicitly mark settlement/post-event tails if they are not part of the analysis window.
   - Check for incomplete groups before summing across outcomes.

2. **Visual checks after saving**
   - Open/read the saved image.
   - Look for zigzags from unsorted x, vertical cliffs from duplicate/incomplete buckets, clipped text, legend overlap, label collisions, unreadable ticks, and misleading y-limits.
   - If event lines exist, label only key events or stagger labels. Do not label every line if it turns into barcode soup.

3. **Context markers**
   - Mark actual start/end windows when sourced.
   - If start/end are inferred or missing, say so in the caption/report and add a todo to source them.

4. **Done means**
   - Re-run the notebook/script.
   - Re-open at least the changed figures.
   - Fix obvious artifacts before reporting completion.

Lazy rule: no fancy plotting framework. Sort, dedupe, annotate less, and save the corrected PNG.
