# Command: document

Used by the `sdlc-orchestrator` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Gather the artifacts this pipeline produced: PRs, stories, test results, ADRs.
3. Generate README updates, release notes, and CHANGELOG entries.
4. If a documentation MCP is available per `config/tool-registry.json`, create or update
   the page. If not, emit the Markdown.
5. Comment on the tracking issue with every link.

## Outputs
- Updated README / CHANGELOG
- A documentation page, when a documentation connector is configured
- Release notes

## Rules
- Describe what shipped, not how the branch got there.
- Never invent a ticket number, a version, or a contributor name. Omit what you cannot verify.
