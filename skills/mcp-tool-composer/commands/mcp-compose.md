# Command: mcp-compose

Used by the `mcp-tool-composer` skill.

## Steps
1. Load the parent `SKILL.md` and `config/tool-registry.json`.
2. Select or compose a chain from the registry's declared chains.
3. Attach a token budget and a fallback to every step.
4. Report the total estimated cost.

## Outputs
- The chain: step, tool, purpose, budget, fallback
- The MCP surface cost against the ceiling

## Rules
- Never invent a tool name. Compose from the registry.
- Every optional tool declares what happens without it.
