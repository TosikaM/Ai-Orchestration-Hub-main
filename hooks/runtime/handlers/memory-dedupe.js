#!/usr/bin/env node
'use strict';
/**
 * Memory write guard: dedupe, redact, and score.
 *
 * DELIBERATELY NOT AN EVENT HOOK
 *
 * Every other guard in this runtime hangs off a Claude Code event. This one is a
 * function called at the write site, which is what the specification actually
 * describes ("runs before any append to memory/shared/*.md"). Modeling it as an event
 * would leave the write path unguarded whenever the event did not fire, and an
 * unguarded write path is the whole problem. Not every guard is a hook; some are just
 * a function you must call, and the honest fix is to make the call site the only way
 * to write. `scripts/memory.py` and this module are that call site.
 *
 * WHY DEDUPE IS A TOKEN CONTROL, NOT HYGIENE
 *
 * Shared memory is loaded into the eager context on every invocation, and the digest
 * reader takes the most relevant entries first. An un-deduplicated file grows without
 * bound and its duplicates crowd out distinct lessons. Deduplication is a budget
 * mechanism that happens to also keep the file readable.
 *
 * THE CONFIDENCE ARITHMETIC
 *
 * The promotion rule (confidence >= 0.7 AND seen in >= 2 repos) was a good rule with
 * no input: nothing in the system ever computed a confidence number, so nothing was
 * ever promoted. These deltas are that input. A dedupe hit that adds a NEW repo is the
 * +0.15 case and is the primary way an instinct reaches the promotion floor.
 */

const respond = require('../lib/respond');
const redact = require('../../../lib/redact');

const INITIAL_CONFIDENCE = 0.4;
const DELTA = {
  newRepo: 0.15,
  sameRepo: 0.05,
  counterExample: -0.25,
  decayPer90Days: -0.05,
};
const FLOOR = 0.1;
const CEILING = 0.95;

function clamp(value) {
  return Math.min(CEILING, Math.max(FLOOR, Math.round(value * 100) / 100));
}

/** Normalize for comparison: case, punctuation, and filler words carry no signal. */
function normalize(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\b(the|a|an|is|are|was|were|to|of|in|on|for|and|or|that|this|it)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Token-set similarity. Cheap, explainable, and good enough to catch a restatement. */
function similarity(a, b) {
  const left = new Set(normalize(a).split(' ').filter(Boolean));
  const right = new Set(normalize(b).split(' ').filter(Boolean));
  if (!left.size || !right.size) return 0;
  let shared = 0;
  for (const token of left) if (right.has(token)) shared += 1;
  return (2 * shared) / (left.size + right.size);
}

const STRONG_MATCH = 0.72;
const WEAK_MATCH = 0.45;

/**
 * Compare an incoming entry against the existing set.
 *
 * Comparison is on TITLE and RESOLUTION, never on CONTEXT. Context is repo-specific
 * and will differ even when the lesson is word-for-word identical — comparing it
 * guarantees you never detect a duplicate.
 */
function classify(incoming, existing) {
  let best = { score: 0, entry: null };
  for (const entry of existing) {
    const score = Math.max(
      similarity(incoming.title, entry.title),
      similarity(incoming.resolution, entry.resolution),
    );
    if (score > best.score) best = { score, entry };
  }
  if (best.score >= STRONG_MATCH) return { action: 'reinforce', match: best.entry, score: best.score };
  if (best.score >= WEAK_MATCH) return { action: 'append-cross-referenced', match: best.entry, score: best.score };
  return { action: 'append', match: null, score: best.score };
}

/** Apply the reinforcement delta and return the updated entry. */
function reinforce(entry, repo) {
  const seen = new Set(entry.seenInRepos || []);
  const isNewRepo = repo && !seen.has(repo);
  if (repo) seen.add(repo);
  const delta = isNewRepo ? DELTA.newRepo : DELTA.sameRepo;
  return {
    ...entry,
    seenInRepos: [...seen],
    confidence: clamp((typeof entry.confidence === 'number' ? entry.confidence : INITIAL_CONFIDENCE) + delta),
    lastReinforced: new Date().toISOString(),
    reinforcements: (entry.reinforcements || 0) + 1,
  };
}

function recordCounterExample(entry, note) {
  return {
    ...entry,
    confidence: clamp((entry.confidence ?? INITIAL_CONFIDENCE) + DELTA.counterExample),
    counterExamples: [...(entry.counterExamples || []), { note, at: new Date().toISOString() }],
  };
}

/**
 * Decay applied lazily at READ time, never at write time, and never as deletion.
 *
 * Deletion-by-decay stays deferred for the stated reason: calibrating a rate needs
 * real usage data and guessing one would silently discard useful learnings. That
 * reasoning holds for deletion and does not hold for ranking. A lazily-applied
 * ranking decay discards nothing — it just stops a three-year-old instinct from
 * outranking last week's — so a wrong rate here is cheap and correctable.
 */
function decayedConfidence(entry, now = Date.now()) {
  const base = typeof entry.confidence === 'number' ? entry.confidence : INITIAL_CONFIDENCE;
  const last = Date.parse(entry.lastReinforced || entry.firstObserved || 0);
  if (!last) return base;
  const periods = Math.floor((now - last) / (90 * 86400000));
  if (periods <= 0) return base;
  return clamp(base + periods * DELTA.decayPer90Days);
}

function shouldPromote(entry) {
  const confidence = decayedConfidence(entry);
  const repos = (entry.seenInRepos || []).length;
  return confidence >= 0.7 && repos >= 2;
}

/**
 * The guard called before any write. Throws on HIGH-tier secrets and on injection
 * markers — there is no flag that turns that off.
 */
function guard(entry) {
  redact.guardFreeText('title', entry.title || '');
  redact.guardFreeText('context', entry.context || '');
  redact.guardFreeText('resolution', entry.resolution || '');
  return true;
}

/** Hook-shaped entry point, so the runtime can invoke it uniformly. Normally unused. */
async function run() {
  return respond.allow();
}

module.exports = {
  run,
  guard,
  classify,
  reinforce,
  recordCounterExample,
  decayedConfidence,
  shouldPromote,
  similarity,
  normalize,
  INITIAL_CONFIDENCE,
  DELTA,
  STRONG_MATCH,
  WEAK_MATCH,
};
