## Confidence Taxonomy

One vocabulary, used identically by every agent, skill, hook, and context in this
system — so a finding moves between components without translation.

| Marker | Meaning | Requirement |
|--------|---------|-------------|
| 🟢 Verified | You read it in this session | A `file:line` the reader can open |
| 🟡 Inferred | Follows from verified facts | State the inference chain in one clause |
| 🔴 Assumed | Not checked | Label it, and say what would confirm it |

Downgrading a claim from 🟢 to 🔴 is a success, not a failure. The taxonomy exists so
that saying "I did not check this" is a normal, low-cost move rather than an admission.
A system where the only respectable answer is a confident one produces confident answers.
