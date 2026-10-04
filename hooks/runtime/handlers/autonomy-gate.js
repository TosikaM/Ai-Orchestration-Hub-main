#!/usr/bin/env node
'use strict';
/**
 * PreToolUse: the Autonomy Gate.
 *
 * WHAT THIS ANSWERS
 *
 * A review of the earlier architecture made the point cleanly: an autonomous loop with a
 * safety kernel bounds how LONG an agent runs, but says nothing about how FAR it may go.
 * Iterations, tokens and wall-clock are all limits on effort. None of them is a limit on
 * blast radius, and blast radius is the thing a customer actually cares about.
 *
 * So autonomy becomes an explicit level, 0 to 5, resolved from config/policy.json and
 * enforced here at the action stream:
 *
 *   0  explain only          — no writes at all
 *   1  suggest code          — diffs shown, never applied
 *   2  write code            — edits land, each needs approval
 *   3  write, test, correct  — inside a working tree; no branch, no PR, no deploy
 *   4  open a pull request   — an artifact goes in front of colleagues
 *   5  deploy                — something customers touch changes
 *
 * The default ceiling is 3, and that is where it sits deliberately: the jump in blast
 * radius between 3 and 4 is far larger than between any other adjacent pair. Below 4 a
 * mistake stays in a working tree somebody has to look at. At 4 it enters a review queue
 * with a plausible description attached. At 5 it is in production.
 *
 * WHY THIS IS A SEPARATE HOOK FROM config-protection AND destructive-gate
 *
 * They answer different questions and a single hook answering all three would be a hook
 * whose denial message could not be specific. config-protection asks "is this file a
 * gate?". destructive-gate asks "is this command irreversible?". This asks "is this
 * CLASS of action permitted at the level this repository is operating at?" — a git push
 * is neither a governance file nor destructive, and at level 3 it is still forbidden.
 *
 * FAILURE POLICY
 *
 * Fails CLOSED on an unresolved policy, like the destructive gate and unlike everything
 * else in this runtime. If the organization has narrowed autonomy and that narrowing
 * cannot be read, proceeding on the shipped defaults would grant exactly what somebody
 * deliberately withheld. The recoverable failure is "run policy.py resolve"; the
 * unrecoverable one is a deploy nobody authorised.
 */

const respond = require('../lib/respond');
const globs = require('../lib/glob');
const policy = require('../../../lib/policy');

/** Tool + command shapes, mapped to the minimum autonomy level that permits them. */
const LEVEL_REQUIRED = [
  { level: 2, test: (ctx) => ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'].includes(ctx.toolName),
    what: 'modifying a file' },
  { level: 4, test: (ctx) => /\bgit\s+push\b/i.test(ctx.command || ''), what: 'pushing a branch' },
  { level: 4, test: (ctx) => /\bgh\s+pr\s+create\b|\bgit\s+request-pull\b/i.test(ctx.command || ''),
    what: 'opening a pull request' },
  { level: 5, test: (ctx) => /\bgh\s+pr\s+merge\b|\bgit\s+merge\s+.*--no-ff\b/i.test(ctx.command || ''),
    what: 'merging a pull request' },
  { level: 5, test: (ctx) => /\b(kubectl|helm|terraform|serverless|flyctl|vercel|netlify)\b/i.test(ctx.command || ''),
    what: 'operating deployment tooling' },
  { level: 5, test: (ctx) => /\bdocker\s+push\b|\bnpm\s+publish\b|\bdotnet\s+nuget\s+push\b/i.test(ctx.command || ''),
    what: 'publishing an artifact' },
];

function levelName(level) {
  return ({
    0: 'explain only', 1: 'suggest code', 2: 'write code',
    3: 'write, test and self-correct', 4: 'open a pull request', 5: 'deploy',
  })[level] || 'unknown';
}

function denial(what, required, actual) {
  return [
    '[Autonomy Gate]',
    '',
    `${what} requires autonomy level ${required} (${levelName(required)}).`,
    `This repository is operating at level ${actual} (${levelName(actual)}).`,
    '',
    'This is a policy limit on BLAST RADIUS, not a limit on effort, so retrying or',
    'rephrasing will not clear it. What you can do instead:',
    '',
    `  - Do the level-${actual} version of the work and stop at the boundary. Produce the`,
    '    branch contents, the PR body, or the deployment plan as an artifact, and hand it',
    '    to a human to execute.',
    '  - Say plainly which action you were about to take and why it is needed.',
    '',
    'Raising the level is a human decision recorded in the decision log:',
    '  python scripts/policy.py autonomy          # what the levels mean here',
    '  python scripts/decision.py log --decision "raise autonomy to N for <repo>" --rationale "..."',
    '',
    'A repository cannot raise its own level — only an organization or project layer can,',
    'and scripts/policy.py refuses a widening from a narrower layer.',
  ].join('\n');
}

function unresolved(reason) {
  return [
    '[Autonomy Gate]',
    '',
    'The autonomy policy could not be resolved, so this action cannot be cleared.',
    '',
    `  ${reason}`,
    '',
    'This gate fails CLOSED, unlike most of this runtime. Your organization has narrowed',
    'autonomy somewhere, and proceeding on the shipped defaults would grant exactly what',
    'that narrowing withheld.',
  ].join('\n');
}

async function run(ctx) {
  const state = policy.load();

  // Nothing to enforce for a read.
  const isWrite = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'].includes(ctx.toolName);
  const isShell = ['Bash', 'PowerShell'].includes(ctx.toolName);
  if (!isWrite && !isShell) return respond.allow();

  if (!state.policy) {
    if (state.source === 'none') return respond.allow(); // no policy shipped at all
    return respond.deny(unresolved(state.reason));
  }

  const level = policy.autonomyLevel();
  if (level === null || level === undefined) return respond.allow();

  // Files the data policy puts out of bounds at any level. A .env is not a blast-radius
  // question, it is a "that must never be read or written by an agent" question.
  if (isWrite && ctx.filePath) {
    const forbidden = policy.forbiddenPathGlobs();
    if (globs.matchesAny(ctx.filePath, forbidden)) {
      return respond.deny([
        '[Autonomy Gate]',
        '',
        `${ctx.filePath} matches a forbidden path in the data policy`,
        '(config/policy.json -> dataPolicy.forbiddenPathGlobs).',
        '',
        'Credential and key material is out of bounds at every autonomy level. If a value',
        'here genuinely needs to change, a human changes it.',
      ].join('\n'));
    }
  }

  for (const rule of LEVEL_REQUIRED) {
    let matches = false;
    try { matches = rule.test(ctx); } catch { matches = false; }
    if (matches && level < rule.level) {
      return respond.deny(denial(rule.what, rule.level, level));
    }
  }

  return respond.allow();
}

module.exports = { run, LEVEL_REQUIRED, levelName, denial };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('PreToolUse', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
