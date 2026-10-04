# Shared Memory — MCP Tool Chains

<!-- GENERATED from memory/index/entries.json by scripts/memory.py.
     Edit through `python scripts/memory.py`, not by hand: the write path runs
     the redaction and injection guard, and hand edits are lost on the next render. -->

<!-- The Tool Chain Registry below is ship-time content, and `scripts/memory.py` does not
     preserve it: the next render rewrites this file from the index and the table goes.
     That is survivable only because the table is a copy, not a source. The authority for
     these five chains is config/tool-registry.json -> toolChains, and it stays the
     authority. Restore this section from there, never the other way round. -->

## How this works

This file is the one exception to "shared memory ships empty". The other three rendered
categories hold *learned* claims, which must be earned by observation in more than one
repository before they load everywhere. The chains below are not learned claims — they
are structural facts about the tool surface, true on the day the hub is installed,
derived from `config/tool-registry.json` rather than from anyone's session. Shipping them
is not seeding the well; it is documenting what is already there.

Learned entries can still land in this file. A `--type tool-chain` capture that survives
promotion — confidence ≥ 0.7 and observed in ≥ 2 repositories — is a chain somebody found
by using the tools, and it is rendered alongside the rest of the categories:

```
python scripts/memory.py capture --type tool-chain \
  --title "..." --context "..." --resolution "..."
```

**The registry and `config/tool-registry.json` must be kept in sync.** They are two
representations of the same five chains, and nothing checks that they agree. When a
sequence changes, change it in the JSON first — that is what agents actually load at
runtime — and then mirror it here. A stale row in this table is worse than a missing one,
because it reads as documentation of current behavior.

## Tool Chain Registry

Sourced from `config/tool-registry.json` → `toolChains`.

| Chain | Sequence | Use when | What it saves versus the naive approach |
|-------|----------|----------|------------------------------------------|
| **Code Analysis** | `structural-graph` → `grep_search` → `read_file` | Locating where a symbol or field lives before reading anything. | Opening candidate files one at a time until the right one appears. |
| **Implementation** | `read_file` → `replace_string_in_file` → `run_in_terminal` | Making a change and immediately proving it builds. | Editing several files, then discovering the first one broke the build. |
| **Review** | `get_changed_files` → `read_file` → `run_in_terminal` | Reviewing a diff rather than a whole repository. | Whole-repo scanning, which produces a finding list nobody reads. |
| **Story Creation** | `mcp_atlassian_*` | Writing stories and acceptance criteria into a tracker. | Manual transcription from chat into the tracker. |
| **E2E Testing** | `mcp_playwright_*` → `run_in_terminal` | Generating and executing browser end-to-end specs. | Hand-writing selectors against a page you have not loaded. |

The saving in the last column is stated as the behavior avoided, not as a number. No
measurement of these chains exists yet, and a percentage invented to make the table look
rigorous would be repeated back as fact by everything that reads this file.

Each chain also carries a `budgetPerStep` in the registry — 2000 to 3000 tokens per step,
1500 for story creation. That is a per-step ceiling for the chain's output, not a promise
about totals, and it lives in the JSON because that is where the budget checks read it.

Two of these five depend on optional MCP connectors, and no connector is enabled out of
the box (`defaults.enabledConnectors` is empty, deliberately: every MCP tool description
is always-on context competing with the discovery budget). Story Creation needs
`mcp_atlassian_*` and E2E Testing needs `mcp_playwright_*`. When the connector is absent
or unhealthy, take the fallback declared in `config/tool-registry.json` → `optional` —
emit the stories as Markdown without inventing a ticket number, emit the specs as files
without claiming they were executed — rather than retrying a timeout. A carefully
specified fallback that is never reached because the caller keeps retrying is decoration.

<!-- ENTRY FORMAT — for rendered entries, which appear below this section:

### <title>
- **Confidence**: <effective, after decay> (recorded <stored value>)
- **Seen in**: <repo>, <repo>
- **Context**: <the task the chain was used for>
- **Resolution**: <the sequence, and why that order>
- **Applies to**: <stack or "all">
- **First observed**: <ISO-8601> · **Last reinforced**: <ISO-8601>
- **Counter-examples**: <count, only when one has been recorded>
- **Related**: <title of a weakly-matching entry, when one exists>

Entries are ordered by effective confidence, highest first.
-->

_No learned entries yet. The five chains above are configuration, not memory; memory
itself ships empty because seeding it with invented learnings would poison the well on
day one._
