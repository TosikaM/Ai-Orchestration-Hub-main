#!/usr/bin/env node
'use strict';
/**
 * PreToolUse: Config Protection — the guard-the-guard hook.
 *
 * THE OBSERVED BEHAVIOR
 *
 * Given a failing gate and the ability to edit the gate, an agent will sometimes edit
 * the gate. It is not malice. It is an optimizer finding the cheapest path to green,
 * and editing one number is cheaper than fixing the code.
 *
 * WHY THAT MATTERS MORE HERE THAN ALMOST ANYWHERE
 *
 * Every quality claim this system makes is defined in a file an agent can edit:
 *
 *   discovery + eager token budgets   config/token-budgets.json
 *   autonomy level, permissions       config/policy.json
 *   quality gate >= 80                config/pipeline-graph.json, config/policy.json
 *   human gates                       config/pipeline-graph.json  (humanGate: false)
 *   org neutrality                    scripts/validate-structure.py
 *   structure validation              scripts/validate-structure.py
 *   CI enforcement                    .github/workflows/ci.yml
 *   redaction tiers                   config/redaction-patterns.json
 *   hook registration                 hooks/hooks.json, hooks/runtime/registry.json
 *   eval thresholds                   evals/evals.json
 *
 * "The agent can edit these freely" and "the guarantees hold" cannot both be true.
 *
 * DENY IS NOT REFUSE-FOREVER
 *
 * The escape is deliberate and leaves a trace: ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT set
 * to the basename, for one file, for one session. Widening a gate should require a
 * decision, and a decision should be visible in the shell history of whoever made it.
 * That is a different thing from being impossible.
 */

const path = require('path');
const respond = require('../lib/respond');

/**
 * Basenames, not paths. A governance file that gets moved is still a governance file,
 * and a path list would silently stop protecting it the day someone reorganizes.
 */
const GOVERNANCE_FILES = new Set([
  'token-budgets.json',
  // The policy document governs autonomy level, per-agent permissions, the data policy
  // and the composite quality gate. It is now the single most valuable file to edit if
  // you want a gate to stop applying, so it belongs here ahead of everything else.
  'policy.json',
  'policy.schema.json',
  'model-pricing.json',
  'pipeline-graph.json',
  'redaction-patterns.json',
  'stack-mappings.json',
  'tool-registry.json',
  'install-profiles.json',
  'hub.config.json',
  'validate-structure.py',
  'measure-discovery-budget.py',
  'context-bill.py',
  'hooks.json',
  'registry.json',
  'plugin.json',
  'marketplace.json',
  'evals.json',
  'touchfiles.json',
  'ci.yml',
  'evals-periodic.yml',
  'governance.yml',
  'CODEOWNERS',
]);

/** Directories whose whole contents are governance, whatever the filename. */
const GOVERNANCE_DIRS = ['hooks/runtime/', '.claude-plugin/', 'migrations/'];

function isGovernance(filePath) {
  const normalized = String(filePath || '').replace(/\\/g, '/');
  if (GOVERNANCE_FILES.has(path.basename(normalized))) return true;
  return GOVERNANCE_DIRS.some((dir) => normalized.includes(dir));
}

function allowedByOverride(filePath) {
  const raw = process.env.ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT;
  if (!raw) return false;
  const allowed = raw.split(/[;,]/).map((s) => s.trim()).filter(Boolean);
  if (allowed.includes('*')) return true;
  const base = path.basename(String(filePath).replace(/\\/g, '/'));
  return allowed.includes(base) || allowed.some((a) => String(filePath).replace(/\\/g, '/').endsWith(a));
}

function denial(file) {
  return [
    '[Config Protection]',
    '',
    `${file} defines a quality gate. Editing it to resolve a failure changes what`,
    '"passing" means rather than making the work pass.',
    '',
    'If the gate is genuinely wrong, say so explicitly:',
    '  1. State which gate, what it currently enforces, and why that is wrong here',
    `  2. Record the decision:  python scripts/decision.py log --scope repo --decision "..."`,
    `  3. Re-run with:          ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT=${file}`,
    '',
    'If the gate is right, fix the code, the frontmatter, or the budget usage instead.',
    '',
    'Ratchet note: if you are LOWERING a measured budget because a reduction landed,',
    'that is the ratchet working as designed — take the override and record why.',
  ].join('\n');
}

async function run(ctx) {
  const filePath = ctx.filePath;
  if (!filePath) return respond.allow();
  if (!isGovernance(filePath)) return respond.allow();
  if (allowedByOverride(filePath)) {
    return respond.inform(
      `[Config Protection] Governance edit to ${path.basename(filePath)} permitted by `
      + 'ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT. Record the reason in the decision log.',
    );
  }
  return respond.deny(denial(path.basename(String(filePath).replace(/\\/g, '/'))));
}

module.exports = { run, isGovernance, GOVERNANCE_FILES, GOVERNANCE_DIRS };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('PreToolUse', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
