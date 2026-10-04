'use strict';
/**
 * Gate bookkeeping: what has this session already been gated on, and how many times
 * has it been told.
 *
 * Two numbers carry the whole design.
 *
 * First touch per file per session. Gating every edit makes the tool unusable and gets
 * the gate switched off within a day. Gating the first one buys the investigation
 * exactly once, at the moment it is worth the most — before the blast radius is
 * unknown and an edit has already landed.
 *
 * A denial budget. After three full blocks in a session, denials collapse to one line
 * carrying an ordinal. Repeating an identical eight-line block burns context and,
 * worse, turns into wallpaper the model learns to pattern-match past. A gate that is
 * ignored is a gate that is not there.
 */

const state = require('../../../lib/state');
const globs = require('./glob');

const FULL_BLOCK_BUDGET = 3;

/**
 * Paths where "who imports this" carries no signal. Gating them is pure friction with
 * no investigation to buy.
 */
const DEFAULT_EXEMPT = [
  '**/*.test.*',
  '**/*.spec.*',
  '**/__tests__/**',
  '**/node_modules/**',
  '**/dist/**',
  '**/out/**',
  '**/.git/**',
  'memory/sessions/**',
  'memory/index/**',
  'evals/runs/**',
  'knowledge/inbox/**',
  'knowledge/extracted/**',
  '**/*.md',
  '**/*.txt',
  '**/*.lock',
  '**/package-lock.json',
];

function exemptGlobs() {
  return DEFAULT_EXEMPT.concat(globs.fromEnv('ORCHESTRATOR_GATE_EXEMPT_GLOBS'));
}

function isExempt(filePath) {
  if (!filePath) return true;
  return globs.matchesAny(filePath, exemptGlobs());
}

function isDisabled() {
  const raw = String(process.env.ORCHESTRATOR_GATEGUARD || '').toLowerCase();
  return ['off', '0', 'false', 'disabled', 'no'].includes(raw);
}

/**
 * @returns {{first: boolean, ordinal: number, condensed: boolean, session: object}}
 */
function checkFirstTouch(sessionId, kind, key) {
  const session = state.loadSession(sessionId);
  const composite = `${kind}:${globs.normalize(key)}`;
  const first = state.markFirstTouch(session, composite, { kind });
  if (!first) {
    state.saveSession(session);
    return { first: false, ordinal: 0, condensed: false, session };
  }
  const ordinal = state.bumpCounter(session, 'denials');
  state.saveSession(session);
  return { first: true, ordinal, condensed: ordinal > FULL_BLOCK_BUDGET, session };
}

/** Record that the facts were satisfied so a retry of the same operation proceeds. */
function clearTouch(sessionId, kind, key) {
  const session = state.loadSession(sessionId);
  const composite = `${kind}:${globs.normalize(key)}`;
  session.entries = session.entries || {};
  session.entries[composite] = { at: Date.now(), kind, satisfied: true };
  state.saveSession(session);
}

module.exports = {
  FULL_BLOCK_BUDGET,
  DEFAULT_EXEMPT,
  exemptGlobs,
  isExempt,
  isDisabled,
  checkFirstTouch,
  clearTouch,
};
