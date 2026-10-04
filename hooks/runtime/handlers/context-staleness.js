#!/usr/bin/env node
'use strict';
/**
 * Stop (async): Context Staleness Detector.
 *
 * BATCHED AT STOP, NOT PER SAVE
 *
 * The original specification fired this on every file save. Ten edits in one turn
 * would mean ten staleness evaluations, each writing the same marker. Running once at
 * Stop, over the whole turn's edits, is the same signal for a tenth of the work.
 *
 * PASSIVE BY DESIGN
 *
 * It marks staleness. It does NOT auto-refresh. Regenerating a context file underneath
 * someone who is mid-task is worse than letting them work against a slightly stale
 * one — the refresh rewrites the exact document they were reasoning from, and they
 * have no way to tell it changed. The marker lets the orchestrator refresh at a phase
 * boundary instead, which is the moment where a rewrite is expected.
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const paths = require('../../../lib/paths');
const state = require('../../../lib/state');

const CHANGED_FILE_THRESHOLD = 20;
const SOURCE_EXTENSIONS = new Set([
  '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
  '.cs', '.py', '.java', '.kt', '.go', '.rs', '.rb', '.php',
  '.vue', '.svelte', '.tf', '.sql',
]);

function markerPath(ws) {
  return path.join(state.statePath('state', paths.repoSlug(ws)), 'context-staleness.json');
}

function contextFile(ws) {
  return path.join(ws, '.github', 'orchestrator-context.md');
}

/** Count source files modified since the context file was last written. */
function countChangedSince(ws, since) {
  let count = 0;
  let newModuleDir = null;
  const skip = new Set(['node_modules', '.git', 'dist', 'out', 'bin', 'obj', '.venv', '__pycache__', 'memory']);

  const walk = (dir, depth) => {
    if (depth > 6 || count > CHANGED_FILE_THRESHOLD * 3) return;
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      if (entry.name.startsWith('.') && entry.name !== '.github') continue;
      if (skip.has(entry.name)) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        try {
          if (fs.statSync(full).birthtimeMs > since && !newModuleDir) newModuleDir = full;
        } catch { /* ignore */ }
        walk(full, depth + 1);
      } else if (SOURCE_EXTENSIONS.has(path.extname(entry.name))) {
        try { if (fs.statSync(full).mtimeMs > since) count += 1; } catch { /* ignore */ }
      }
    }
  };
  walk(ws, 0);
  return { count, newModuleDir };
}

async function run(ctx) {
  const ws = ctx.cwd || paths.workspaceRoot();
  const file = contextFile(ws);
  if (!fs.existsSync(file)) return respond.allow();

  let since;
  try { since = fs.statSync(file).mtimeMs; } catch { return respond.allow(); }

  const { count, newModuleDir } = countChangedSince(ws, since);
  const stale = count > CHANGED_FILE_THRESHOLD || Boolean(newModuleDir);
  if (!stale) return respond.allow();

  state.writeJsonAtomic(markerPath(ws), {
    repo: paths.repoSlug(ws),
    contextFile: file,
    contextWrittenAt: new Date(since).toISOString(),
    changedSourceFiles: count,
    newModuleDirectory: newModuleDir ? path.relative(ws, newModuleDir).replace(/\\/g, '/') : null,
    detectedAt: new Date().toISOString(),
    reason: newModuleDir
      ? 'A new module or feature directory appeared, which the layer map will not contain.'
      : `${count} source files changed since the context file was written (threshold ${CHANGED_FILE_THRESHOLD}).`,
    action: 'Suggest a refresh at the next phase boundary. Do not auto-refresh mid-task.',
  });

  return respond.allow();
}

module.exports = { run, countChangedSince, markerPath, CHANGED_FILE_THRESHOLD };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    await run(stdin.normalize(payload));
    process.exit(0);
  });
}
