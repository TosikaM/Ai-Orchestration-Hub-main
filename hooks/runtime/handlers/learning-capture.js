#!/usr/bin/env node
'use strict';
/**
 * Stop (async): Learning Capture.
 *
 * Asynchronous on purpose. Capturing a learning is worth doing and is worth exactly
 * zero seconds of the user's attention. It never blocks, never prompts, and a failure
 * here is logged and dropped rather than surfaced.
 *
 * WHAT IT WILL NOT CAPTURE, AND WHY THAT LIST MATTERS MORE THAN THE CAPTURE LIST
 *
 * Shared memory syncs to every connected repository. A bad entry is not a local
 * mistake, it is organization-wide replication of a wrong idea, re-injected as context
 * into every future session in every repo. The bar for writing is therefore high, and
 * every write goes through the redaction and injection guard first — an agent that
 * debugs an auth failure and writes "regenerated the token to sk-ant-..." would
 * otherwise have replicated a live credential into every repository in the company.
 *
 * This handler writes a CANDIDATE, not an entry. Promotion into memory/shared/ happens
 * through `scripts/memory.py`, which applies the dedupe and confidence arithmetic. A
 * turn-level heuristic should not have direct write access to the organization's
 * shared brain.
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const paths = require('../../../lib/paths');
const state = require('../../../lib/state');
const redact = require('../../../lib/redact');

/** Signals that a turn contained something worth remembering. */
const CAPTURE_SIGNALS = [
  { kind: 'error-recovered', re: /\b(?:that|this)\s+(?:fixed|resolved|worked)\b|\bnow\s+(?:builds|passes|compiles)\b/i },
  { kind: 'pattern-discovered', re: /\bturns out\b|\bthe reason (?:is|was)\b|\broot cause\b/i },
  { kind: 'convention-corrected', re: /\bthis repo (?:uses|prefers|expects)\b|\bconvention here is\b/i },
  { kind: 'anti-pattern', re: /\bdo not\b.*\bbecause\b|\bavoid\b.*\bit (?:breaks|fails|silently)\b/i },
];

/** Signals that a turn is NOT worth remembering, even if it matched above. */
const REJECT_SIGNALS = [
  /\bticket\s+\w+-\d+\b/i,          // one ticket, not a general lesson
  /\bon (?:this|the) branch\b/i,    // branch-local
  /\bfor now\b|\btemporarily\b/i,   // explicitly transient
  /\bI think\b|\bprobably\b|\bmight be\b/i, // inferred but not verified
];

function lastAssistantText(transcriptPath) {
  if (!transcriptPath || !fs.existsSync(transcriptPath)) return '';
  let lines;
  try { lines = fs.readFileSync(transcriptPath, 'utf8').split('\n').filter(Boolean); } catch { return ''; }
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    let entry;
    try { entry = JSON.parse(lines[i]); } catch { continue; }
    const message = entry.message || entry;
    if (message.role !== 'assistant') continue;
    const content = message.content;
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
      const text = content.filter((c) => c && c.type === 'text').map((c) => c.text).join('\n');
      if (text.trim()) return text;
    }
  }
  return '';
}

function detect(text) {
  if (!text) return null;
  if (REJECT_SIGNALS.some((re) => re.test(text))) return null;
  for (const signal of CAPTURE_SIGNALS) {
    if (signal.re.test(text)) return signal.kind;
  }
  return null;
}

function extractTitle(text, kind) {
  const sentence = String(text)
    .split(/(?<=[.!?])\s+/)
    .find((s) => CAPTURE_SIGNALS.some((sig) => sig.re.test(s)));
  const raw = (sentence || text).replace(/\s+/g, ' ').trim();
  return `${kind}: ${raw.slice(0, 110)}`;
}

async function run(ctx) {
  const text = lastAssistantText(ctx.transcriptPath);
  const kind = detect(text);
  if (!kind) return respond.allow();

  const ws = ctx.cwd || paths.workspaceRoot();
  const repo = paths.repoSlug(ws);

  const candidate = {
    kind,
    repo,
    title: extractTitle(text, kind),
    context: text.slice(0, 900),
    resolution: text.slice(0, 600),
    sessionId: ctx.sessionId,
    capturedAt: new Date().toISOString(),
    status: 'candidate',
    confidence: 0.4,
    seenInRepos: [repo],
  };

  // The guard is not optional and there is no flag that skips it.
  try {
    redact.guardFreeText('title', candidate.title);
    redact.guardFreeText('context', candidate.context);
    redact.guardFreeText('resolution', candidate.resolution);
  } catch (error) {
    // Record that something was rejected, without recording what it contained.
    const rejectFile = path.join(state.statePath('memory'), 'rejected-captures.jsonl');
    state.appendChained(rejectFile, {
      repo, kind, reason: error.message.slice(0, 200), sessionId: ctx.sessionId,
    });
    return respond.allow();
  }

  const candidatesFile = path.join(ws, 'memory', 'sessions', 'learning-candidates.jsonl');
  try {
    fs.mkdirSync(path.dirname(candidatesFile), { recursive: true });
    fs.appendFileSync(candidatesFile, `${JSON.stringify(candidate)}\n`, 'utf8');
  } catch {
    // A learning we failed to write is a small loss. Never surface it.
  }
  return respond.allow();
}

module.exports = { run, detect, extractTitle, CAPTURE_SIGNALS, REJECT_SIGNALS };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    await run(stdin.normalize(payload));
    process.exit(0);
  });
}
