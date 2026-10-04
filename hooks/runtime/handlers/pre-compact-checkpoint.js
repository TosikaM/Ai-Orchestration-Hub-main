#!/usr/bin/env node
'use strict';
/**
 * PreCompact: checkpoint the in-flight pipeline before the window is compacted.
 *
 * THIS FIXES A REAL DEFECT, NOT A MISSING FEATURE
 *
 * The pipeline service writes a checkpoint on phase transitions, and the design note
 * beside it says "checkpoints survive a window reload, which plain in-memory state
 * does not." True for a reload. Compaction quietly falsifies it: a long `implement`
 * phase that triggers a compaction loses everything since the last gate, because the
 * only durable write happens at a boundary the phase has not reached yet.
 *
 * PreCompact is the one moment where the runtime knows the window is about to be
 * rewritten and can still act. Writing the checkpoint here costs milliseconds and
 * converts "lost the phase" into "resumed at the phase."
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const paths = require('../../../lib/paths');
const state = require('../../../lib/state');

function sessionsDir(ws) {
  return path.join(ws, 'memory', 'sessions');
}

/** Find the most recently modified in-flight pipeline in this workspace. */
function activePipeline(ws) {
  const dir = sessionsDir(ws);
  if (!fs.existsSync(dir)) return null;
  let files;
  try {
    files = fs.readdirSync(dir).filter((f) => f.endsWith('.checkpoint.json'));
  } catch { return null; }
  if (!files.length) return null;

  const newest = files
    .map((f) => ({ f, at: fs.statSync(path.join(dir, f)).mtimeMs }))
    .sort((a, b) => b.at - a.at)[0];
  const checkpoint = state.readJson(path.join(dir, newest.f), null);
  if (!checkpoint) return null;
  if (checkpoint.status === 'complete' || checkpoint.status === 'abandoned') return null;
  return { file: path.join(dir, newest.f), checkpoint };
}

async function run(ctx) {
  const ws = ctx.cwd || paths.workspaceRoot();
  const active = activePipeline(ws);
  if (!active) return respond.allow();

  const { file, checkpoint } = active;
  checkpoint.compactions = (checkpoint.compactions || 0) + 1;
  checkpoint.lastCompactedAt = new Date().toISOString();
  checkpoint.compactionNote =
    'Checkpointed at PreCompact. Anything the phase learned that is not written into this '
    + 'file or into the repo is gone after compaction — re-read before assuming.';
  state.writeJsonAtomic(file, checkpoint);

  const phase = checkpoint.currentPhase || checkpoint.phase || 'unknown';
  return respond.inform([
    '## Orchestrator — pipeline checkpointed before compaction',
    '',
    `Pipeline \`${checkpoint.pipelineId || path.basename(file)}\` was in phase **${phase}**.`,
    `State written to \`${path.relative(ws, file).replace(/\\/g, '/')}\`.`,
    '',
    'After compaction, re-read that file before continuing. Do not restart the pipeline —',
    're-enter at the recorded phase.',
  ].join('\n'));
}

module.exports = { run, activePipeline };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('PreCompact', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
