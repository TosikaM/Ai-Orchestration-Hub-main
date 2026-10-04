'use strict';
/**
 * Machine-scoped state: JSON files under ~/.orchestrator/, plus append-only JSONL
 * ledgers. Deliberately files rather than a database — `doctor` stays easy to write,
 * the state stays diffable and eyeball-able, and nothing about it is scoped to one
 * editor. A terminal session, a CI job, and the view plane all read the same bytes.
 *
 * Writes are atomic (temp file, then rename) because a hook killed halfway through a
 * write must not leave truncated JSON that every later session fails to parse.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const paths = require('./paths');

function readJson(file, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^﻿/, ''));
  } catch {
    return fallback;
  }
}

function writeJsonAtomic(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  fs.renameSync(tmp, file);
}

function statePath(...parts) {
  return path.join(paths.stateHome(), ...parts);
}

/* ---------------------------------------------------------------- session state */

/**
 * Per-session scratch state, keyed by the session id Claude Code supplies.
 * A 30-minute idle timeout and a 500-entry cap keep the file from becoming a log:
 * this is a working set, not a history.
 */
const SESSION_TIMEOUT_MS = 30 * 60 * 1000;
const MAX_TRACKED_ENTRIES = 500;

function sessionFile(sessionId) {
  const safe = String(sessionId || 'default').replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 96);
  return statePath('sessions', `${safe}.json`);
}

function loadSession(sessionId) {
  const file = sessionFile(sessionId);
  const raw = readJson(file, null);
  const now = Date.now();
  if (!raw || typeof raw !== 'object' || now - (raw.updatedAt || 0) > SESSION_TIMEOUT_MS) {
    return { sessionId: String(sessionId || 'default'), createdAt: now, updatedAt: now, entries: {}, counters: {} };
  }
  return raw;
}

function saveSession(session) {
  session.updatedAt = Date.now();
  const keys = Object.keys(session.entries || {});
  if (keys.length > MAX_TRACKED_ENTRIES) {
    // Drop the oldest half rather than the newest: the recent working set is what
    // the gate actually reasons about.
    const sorted = keys
      .map((k) => [k, session.entries[k]])
      .sort((a, b) => (a[1].at || 0) - (b[1].at || 0));
    for (const [k] of sorted.slice(0, Math.floor(keys.length / 2))) {
      delete session.entries[k];
    }
  }
  writeJsonAtomic(sessionFile(session.sessionId), session);
  return session;
}

/** True the first time this key is seen in the session; false forever after. */
function markFirstTouch(session, key, meta = {}) {
  session.entries = session.entries || {};
  if (session.entries[key]) return false;
  session.entries[key] = { at: Date.now(), ...meta };
  return true;
}

function bumpCounter(session, name) {
  session.counters = session.counters || {};
  session.counters[name] = (session.counters[name] || 0) + 1;
  return session.counters[name];
}

/* ------------------------------------------------------------ connected repos */

function connectedReposPath() {
  return statePath('state', 'connected-repos.json');
}

function loadConnectedRepos() {
  return readJson(connectedReposPath(), { version: 1, repos: [], groups: [], active: null });
}

function saveConnectedRepos(value) {
  writeJsonAtomic(connectedReposPath(), value);
}

/* ------------------------------------------------------------- append-only log */

/**
 * Hash-chained JSONL. Each line carries `prev` = sha256 of the previous raw line,
 * which makes a deletion or an edit detectable without making the log immutable.
 *
 * Threat model, stated plainly: this is forensic observability, not an exfiltration
 * control. It records what was attempted so an accident is auditable. A determined
 * leaker bypasses it trivially. It catches carelessness, which is the 99% case.
 */
function appendChained(file, record) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  let prev = 'genesis';
  if (fs.existsSync(file)) {
    const lines = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean);
    if (lines.length) {
      prev = crypto.createHash('sha256').update(lines[lines.length - 1], 'utf8').digest('hex');
    }
  }
  const line = JSON.stringify({ ...record, prev, at: new Date().toISOString() });
  fs.appendFileSync(file, `${line}\n`, { encoding: 'utf8', mode: 0o600 });
  return line;
}

function verifyChain(file) {
  if (!fs.existsSync(file)) return { ok: true, lines: 0, brokenAt: null };
  const lines = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean);
  let prev = 'genesis';
  for (let i = 0; i < lines.length; i += 1) {
    let parsed;
    try {
      parsed = JSON.parse(lines[i]);
    } catch {
      return { ok: false, lines: lines.length, brokenAt: i + 1, reason: 'unparseable line' };
    }
    if (parsed.prev !== prev) {
      return { ok: false, lines: lines.length, brokenAt: i + 1, reason: 'prev hash mismatch' };
    }
    prev = crypto.createHash('sha256').update(lines[i], 'utf8').digest('hex');
  }
  return { ok: true, lines: lines.length, brokenAt: null };
}

function telemetryPath() {
  return statePath('telemetry.jsonl');
}

function egressPath() {
  return statePath('security', 'egress.jsonl');
}

function sha256(text) {
  return crypto.createHash('sha256').update(String(text), 'utf8').digest('hex');
}

module.exports = {
  readJson,
  writeJsonAtomic,
  statePath,
  SESSION_TIMEOUT_MS,
  loadSession,
  saveSession,
  markFirstTouch,
  bumpCounter,
  loadConnectedRepos,
  saveConnectedRepos,
  connectedReposPath,
  appendChained,
  verifyChain,
  telemetryPath,
  egressPath,
  sha256,
};
