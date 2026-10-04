#!/usr/bin/env node
'use strict';
/**
 * SessionStart: inject the small, high-value, always-on set.
 *
 * WHAT THIS REPLACES
 *
 * Under the previous architecture a chat participant *always* streamed repo context,
 * memory, and the evidence manifest before any command ran. Guaranteed injection. Move
 * to native skill dispatch and that guarantee is gone: a skill loads when the model
 * decides to load it.
 *
 * The answer is not to rebuild guaranteed injection. It is to split the difference
 * honestly. A very small set — active decisions, staleness, the discovery footprint —
 * is pushed unconditionally here, because the agent cannot know to ask for it. Every-
 * thing else becomes retrieved on demand, which is the better pattern anyway and is
 * what progressive disclosure argued for all along.
 *
 * THE CAP IS THE POINT
 *
 * Session-start injection is the most easily-bloated always-on surface in any system
 * like this. It is where "we load context automatically" quietly becomes "we spend
 * 2,000 tokens before you type" with nobody deciding to. Hard-capped from
 * config/token-budgets.json -> sessionStart.maxChars, and the cap is reported when it
 * bites rather than truncating silently.
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const config = require('../../../lib/config');
const paths = require('../../../lib/paths');
const state = require('../../../lib/state');

const STALE_DAYS = 14;

function contextFile(ws) {
  return path.join(ws, '.github', 'orchestrator-context.md');
}

function sectionContextStatus(ws) {
  const file = contextFile(ws);
  if (!fs.existsSync(file)) {
    return '- **Repo context:** not generated. Run `/orchestrator-init` before any analysis — every claim you '
      + 'make about this repository is otherwise ungrounded.';
  }
  const ageDays = Math.floor((Date.now() - fs.statSync(file).mtimeMs) / 86400000);
  if (ageDays > STALE_DAYS) {
    return `- **Repo context:** \`.github/orchestrator-context.md\` is ${ageDays} days old `
      + `(stale past ${STALE_DAYS}). Re-run \`/orchestrator-init\` if the architecture has moved; otherwise `
      + 'treat its layer map as 🟡 inferred rather than 🟢 verified.';
  }
  return `- **Repo context:** \`.github/orchestrator-context.md\` (${ageDays}d old). Read it before analysis.`;
}

function sectionActiveDecisions(ws) {
  const slug = paths.repoSlug(ws);
  const candidates = [
    path.join(ws, 'memory', 'decisions', `${slug}.jsonl`),
    path.join(state.statePath('decisions'), `${slug}.jsonl`),
  ];
  const file = candidates.find((c) => fs.existsSync(c));
  if (!file) return null;

  let lines;
  try {
    lines = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean);
  } catch { return null; }

  const superseded = new Set();
  const decided = [];
  for (const line of lines) {
    let event;
    try { event = JSON.parse(line); } catch { continue; }
    if (event.kind === 'supersede' || event.kind === 'redact') {
      if (event.supersedes) superseded.add(event.supersedes);
    } else if (event.kind === 'decide') {
      decided.push(event);
    }
  }
  const active = decided.filter((d) => !superseded.has(d.id)).slice(-8);
  if (!active.length) return null;

  const budgets = config.tokenBudgets();
  const cap = (budgets.memoryRead && budgets.memoryRead.maxInjectedDecisions) || 8;
  const rows = active.slice(-cap).map((d) => `  - \`${d.id}\` ${d.decision}`);
  return [
    '- **Settled decisions on this repo** — treat each as settled, with its rationale. If you are',
    '  about to reverse one, say so explicitly and say why:',
    ...rows,
  ].join('\n');
}

function sectionDiscoveryFootprint() {
  const budgets = config.tokenBudgets();
  const derivation = (budgets.discovery && budgets.discovery.derivation) || {};
  if (typeof derivation.measuredValue !== 'number') {
    return '- **Discovery budget:** never measured. Run '
      + '`python scripts/measure-discovery-budget.py` and commit the result — an unrecorded '
      + 'ceiling is a disabled ceiling wearing the costume of an enabled one.';
  }
  const ceiling = budgets.discovery.aggregateFrontmatterBytes;
  const pct = Math.round((derivation.measuredValue / ceiling) * 100);
  if (pct < (budgets.warnAtPercent || 85)) return null;
  return `- **Discovery budget:** ${derivation.measuredValue}B / ${ceiling}B (${pct}%). `
    + 'This is paid on every session in every repo. Run `/budget` for a ranked list of what to cut.';
}

/**
 * Delegate to the token-budget-guard handler in-process.
 *
 * The registry declares `session:start:token-budget-guard` as invoked from here rather
 * than registered separately, so that session start costs one Node process instead of
 * two. This is the call that makes that claim true. Without it the registry would be
 * describing a hook nothing executes — which is exactly the defect this runtime was
 * built to eliminate, and it would be embarrassing to reintroduce it at the one place
 * the claim is written down.
 *
 * It is a stronger check than the recorded-value read above: the guard MEASURES the
 * skill files rather than trusting `derivation.measuredValue`, so it also catches a
 * stale record, a per-skill cap violation, and a ceiling that has become a string.
 */
async function sectionBudgetGuard(hooks) {
  if (hooks && !hooks.isHookEnabled('session:start:token-budget-guard')) return null;
  try {
    const guard = require('./token-budget-guard');
    const result = await guard.run();
    return result && result.context ? result.context : null;
  } catch (error) {
    process.stderr.write(`[session-bootstrap] token-budget-guard failed: ${error.message}\n`);
    return null;
  }
}

function sectionPendingGate(ws) {
  const dir = path.join(ws, 'memory', 'sessions');
  if (!fs.existsSync(dir)) return null;
  let entries;
  try { entries = fs.readdirSync(dir); } catch { return null; }
  const pending = entries
    .filter((f) => /\.gate-[a-z]+\.md$/.test(f))
    .filter((f) => !entries.includes(f.replace(/\.md$/, '.json')));
  if (!pending.length) return null;
  return `- **Human gate pending:** ${pending.join(', ')}. The pipeline is stopped and waiting for a `
    + 'verdict. Approve with `python scripts/pipeline.py approve <pipelineId> <phase>` or use the '
    + 'gate panel in the view plane. Do not advance the pipeline past it.';
}

function sectionActiveBand(ws) {
  const dir = path.join(ws, 'memory', 'sessions');
  if (!fs.existsSync(dir)) return null;
  let bands;
  try { bands = fs.readdirSync(dir).filter((f) => f.endsWith('.band.json')); } catch { return null; }
  if (!bands.length) return null;
  const latest = bands.sort().pop();
  const band = state.readJson(path.join(dir, latest), null);
  if (!band || !band.remainingRepos || !band.remainingRepos.length) return null;
  return `- **Cross-repo band in flight** (\`${latest}\`): ${band.completedRepos?.length || 0} repo(s) done, `
    + `next is \`${band.remainingRepos[0]}\`. Consume the upstream shared contracts as named — `
    + 'do not re-derive them.';
}

async function run(ctx, meta) {
  const ws = ctx.cwd || paths.workspaceRoot();
  const budgets = config.tokenBudgets();
  const cap = (budgets.sessionStart && budgets.sessionStart.maxChars) || 8000;

  // The budget guard is delegated to in-process rather than registered as its own hook,
  // so session start costs one Node process instead of two. It runs first because a
  // disabled ceiling is the kind of thing you want to hear about before anything else.
  const guardSection = await sectionBudgetGuard(meta && meta.flags);

  const sections = [
    guardSection,
    sectionContextStatus(ws),
    sectionPendingGate(ws),
    sectionActiveBand(ws),
    sectionActiveDecisions(ws),
    sectionDiscoveryFootprint(),
  ].filter(Boolean);

  if (!sections.length) return respond.allow();

  let body = [
    '## Orchestrator — session bootstrap',
    '',
    ...sections,
    '',
    '_Pushed unconditionally because you cannot know to ask for it. Everything else this system_',
    '_knows is retrieved on demand: run `/analyze` for structure, `/memory` for learnings,_',
    '_`/repo` for the band, `/knowledge` for the curated knowledge base._',
  ].join('\n');

  if (body.length > cap) {
    body = `${body.slice(0, cap - 80)}\n\n_[session-start context trimmed at ${cap} chars]_`;
  }

  return respond.inform(body);
}

module.exports = {
  run, sectionContextStatus, sectionActiveDecisions, sectionPendingGate, sectionBudgetGuard,
};

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('SessionStart', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
