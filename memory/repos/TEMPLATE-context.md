# Per-Repo Context Template

> The shape `scripts/context-gen.py` produces when a repository first connects, written
> to `.github/orchestrator-context.md` in that repository. This file is the template and
> the reference for the shape; the generator is the authority on the content.

> **Replace every `{placeholder}` with a value detected from the repository. Anything not
> detected stays the literal string `not detected`.** Never fill a placeholder with a
> plausible guess. This is the densest artifact in the system and everything downstream
> trusts it, so a confidently wrong stack propagates into every phase of every pipeline.
> An honest unknown costs one question. A wrong guess costs a day of work aimed at the
> wrong architecture, and nothing in the pipeline will contradict it, because the pipeline
> is reading this file.

<!-- THE TECH STACK ROW IN THE TABLE BELOW IS LOAD-BEARING AND MUST KEEP ITS EXACT LITERAL
     FORM: the bolded field name, the trailing colon inside the cell, and the surrounding
     pipes, exactly as `scripts/context-gen.py` emits it. The cross-repo connect path
     recovers a repository's stack by matching a regex against that row. Bolding the whole
     row, dropping the trailing colon, renaming the field to "Stack", or splitting the
     table would all still render correctly and would silently make every connected
     repository record its stack as "unknown" — with no error, because a regex that does
     not match is not a failure, it is a default. Both earlier passes of this system
     shipped that regex against a writer that never emitted the pattern, which is how the
     bug is known. Cosmetic edits to this table are not cosmetic.

     Note also that this comment deliberately does NOT spell out the matched pattern. The
     regex is unanchored and takes the FIRST occurrence in the file, so a comment quoting
     the literal form would itself be matched — ahead of the real row — and the connect
     path would recover this sentence instead of the stack. Describe the row here; do not
     reproduce it. -->

---

# {repo-name} — Orchestrator Context

> Auto-generated: {date} | Refreshed: {last_refresh_date}
> Stack detection: `config/stack-mappings.json`

## Project Identity

| Field | Value |
|-------|-------|
| Repository | {org}/{repo-name} |
| **Tech Stack**: | {detected_stack} |
| Architecture | {detected_pattern} |
| Primary Language | {language} |
| Framework Version | {version} |
| Testing Framework | {test_framework} |
| Naming Convention | {naming_convention} |
| CI/CD | {pipeline_type} |
| Package Manager | {npm/nuget/pip/cargo/go} |
| Project ID | {if_available} |

## Architecture Layers

| Layer | Path | Key Files | Purpose |
|-------|------|-----------|---------|
| {layer_name} | `{path}` | {files} | {description} |

_When no recognized layer directories are found this section says `not detected` and says
why. The scanner locates directories; it does not infer intent from them, and an invented
layer map is worse than an absent one because it reads as a survey of the repository._

## Domain Entities

| Entity | Location | Relationships |
|--------|----------|---------------|

_Populated by `/analyze`. The scanner locates directories; it does not read semantics, so
this table stays empty until something has actually read the code._

## Integration Points

| Type | Endpoint / Interface | Used By |
|------|----------------------|---------|

_Maintained by hand. The scanner cannot infer these and **will never overwrite this
section** on a refresh. Together with Verified Commands it is one of two preserved
sections: regenerating either would destroy knowledge the scanner has no way to recover,
and that preservation is the only reason a refresh is safe to run at all._

## Conventions

**This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks everything in
this section.** A hub default that overrides a team's stated convention is a hub that gets
uninstalled.

- **naming**: {file, class, method, and constant conventions}
- **testPattern**: {spec location and naming}
- **stateManagement**: {approach}
- **styling**: {approach}
- **coverageTarget**: {target}

_Sourced from `config/stack-mappings.json` for the detected stack, not assumed from the
language. A convention that is standard for a framework is not thereby true of this
repository._

## Verified Commands

| Purpose | Command | Verified |
|---------|---------|----------|
| {purpose} | `{command}` | candidate, not yet run |

_Candidates come from the stack mapping. `verification-loop` replaces a candidate with the
command that actually ran, and **this section is never overwritten by a context refresh** —
a one-time question that persists beats a permanent "not detected"._

## Deployment

| Environment | Config | Platform |
|-------------|--------|----------|
| {environment} | {config_path} | {platform} |

_Left as `not detected` unless a pipeline definition or deployment manifest was actually
read. Deployment targets are the placeholders most tempting to guess from convention and
the most expensive to get wrong._

## Orchestrator Notes

_Agents append durable observations here. Transient task state does not belong in this
file — it belongs in `memory/sessions/`, which is discarded at the end of a run. If an
observation is worth keeping across repositories, it does not belong here either: capture
it with `python scripts/memory.py capture`, so it goes through the redaction and injection
guard and earns its way to shared memory by promotion rather than by being typed into a
file that syncs._
