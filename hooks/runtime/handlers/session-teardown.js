#!/usr/bin/env node
'use strict';
/**
 * SessionEnd: flush and release.
 *
 * Two jobs, both of which exist because the alternative is a stuck system that nobody
 * can diagnose:
 *
 *   1. Release any cross-repo band lock this session held. A band serializes work
 *      across repositories so two agents do not implement the same contract twice. A
 *      lock that outlives its session blocks every future run and looks like a hang.
 *      Locks carry the session id and a timestamp so a crashed session's lock can also
 *      be reclaimed by age.
 *
 *   2. Mark the session closed in the state directory so `doctor` can distinguish
 *      "in flight" from "abandoned", and so stale session files get cleaned up rather
 *      than accumulating one per conversation forever.
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const paths = require('../../../lib/paths');
const state = require('../../../lib/state');

const LOCK_MAX_AGE_MS = 60 * 60 * 1000;
const SESSION_FILE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

function locksDir() {
  return state.statePath('locks');
}

function releaseLocks(sessionId) {
  const dir = locksDir();
  let files;
  try { files = fs.readdirSync(dir); } catch { return 0; }
  let released = 0;
  for (const file of files) {
    const full = path.join(dir, file);
    const lock = state.readJson(full, null);
    if (!lock) continue;
    const mine = lock.sessionId === sessionId;
    const expired = Date.now() - Date.parse(lock.acquiredAt || 0) > LOCK_MAX_AGE_MS;
    if (mine || expired) {
      try { fs.unlinkSync(full); released += 1; } catch { /* ignore */ }
    }
  }
  return released;
}

/** Session scratch files are a working set, not a history. Old ones are noise. */
function pruneSessionFiles() {
  const dir = state.statePath('sessions');
  let files;
  try { files = fs.readdirSync(dir); } catch { return 0; }
  let pruned = 0;
  for (const file of files) {
    const full = path.join(dir, file);
    try {
      if (Date.now() - fs.statSync(full).mtimeMs > SESSION_FILE_MAX_AGE_MS) {
        fs.unlinkSync(full);
        pruned += 1;
      }
    } catch { /* ignore */ }
  }
  return pruned;
}

async function run(ctx) {
  const ws = ctx.cwd || paths.workspaceRoot();
  releaseLocks(ctx.sessionId);
  pruneSessionFiles();

  if (String(process.env.ORCHESTRATOR_TELEMETRY || '').toLowerCase() === 'on') {
    try {
      state.appendChained(state.telemetryPath(), {
        event: 'session-end',
        repo: paths.repoSlug(ws),
        sessionId: ctx.sessionId,
      });
    } catch { /* ignore */ }
  }
  return respond.allow();
}

module.exports = { run, releaseLocks, pruneSessionFiles, locksDir, LOCK_MAX_AGE_MS };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    await run(stdin.normalize(payload));
    process.exit(0);
  });
}
