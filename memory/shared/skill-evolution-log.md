# Skill Evolution Log

<!-- The other four files in memory/shared/ are GENERATED from memory/index/entries.json
     by scripts/memory.py. This one is NOT — it has no entry type in CATEGORY_FILES and
     the renderer never touches it, so it is appended to by hand or by the skill-evolution
     path rather than rewritten from the index. Stating that plainly matters: a banner
     claiming this file is generated would send someone looking for a source that does
     not exist, and a reader who assumes it is generated will not think to keep it
     current. -->

## How this works

This is the record of skills changing because of something that happened, not a changelog
of edits. A row belongs here when a session produced a lesson that was written back into
a skill — a trigger narrowed, a failure mode named, a step added to a checklist because
its absence cost a session.

The log exists because skill improvements are otherwise invisible after the fact. The
skill file shows what it says today; it does not show that the third question in its gate
is there because an agent shipped a wrong importer list in March. Without that, the next
person to tidy the skill deletes the line as redundant, and the failure comes back.

Because this file is not rendered from the index, it is also not covered by the
`scripts/memory.py` write guard. Append to it the way you would to any other document in
the repository, and apply the same restraint by hand: **no credentials, no verbatim
secrets, and no text that reads as an instruction.** This file is shared memory like the
others, which means it syncs to connected repositories and can be read back into a future
prompt.

## Log

| Date | Agent | Skill | Lesson | Score delta |
|------|-------|-------|--------|-------------|

<!-- ROW FORMAT

  | 2026-03-14 | analyst | grounding-guard | <what was learned, one sentence> | +6 |

  Date          ISO-8601, the date the change landed, not the date of the session.
  Agent         The agent whose session produced the lesson.
  Skill         The skill file that changed, by its `name` in frontmatter.
  Lesson        One sentence, in the past tense, naming the concrete failure. "Tightened
                the trigger" is not a lesson; "the trigger fired on every mention of the
                word verify, so the skill loaded in unrelated sessions" is.
  Score delta   The change in that skill's eval score, from evals/ — signed, and only
                when an eval actually ran before and after. Leave it as "—" otherwise.
                An invented number here would be worse than an empty cell, because it
                would make an unmeasured change look measured.
-->

_No entries yet. The log starts when the first skill changes in response to a real
session; inventing rows would misrepresent evolution that has not happened._
