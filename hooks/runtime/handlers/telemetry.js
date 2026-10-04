#!/usr/bin/env node
'use strict';
/**
 * Stop (async): local telemetry.
 *
 * LOCAL-ONLY, DEFAULT-OFF, NO NETWORK IMPORT
 *
 * There is no HTTP client in this file and there is not going to be one. Telemetry
 * writes a JSONL line to ~/.orchestrator/telemetry.jsonl and stops. Off unless
 * ORCHESTRATOR_TELEMETRY=on.
 *
 * WHY IT EXISTS AT ALL
 *
 * Because several claims in this system are currently unmeasured, and the honest way
 * to hold them is to make them measurable rather than to assert a number. The source
 * material this project descends from claimed "87% token savings" in two places with
 * no measurement anywhere in the repository, and that figure was deleted rather than
 * propagated. If you want a number to put in front of a stakeholder, turn this on and
 * generate a real one. An invented benchmark in a tool whose stated purpose is
 * preventing hallucination would be an unusually poor look.
 *
 * WHAT IT RECORDS: counts and durations. Never file contents, never prompt text,
 * never a path outside the workspace-relative form.
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const paths = require('../../../lib/paths');
const state = require('../../../lib/state');

function enabled() {
  const raw = String(process.env.ORCHESTRATOR_TELEMETRY || '').toLowerCase();
  return ['on', '1', 'true', 'yes'].includes(raw);
}

function countTurnTools(transcriptPath) {
  if (!transcriptPath || !fs.existsSync(transcriptPath)) return {};
  let lines;
  try { lines = fs.readFileSync(transcriptPath, 'utf8').split('\n').filter(Boolean); } catch { return {}; }
  const counts = {};
  // Only the tail: this runs on every Stop, and re-parsing a long transcript each time
  // would make an async nicety into a real cost.
  for (const line of lines.slice(-200)) {
    let entry;
    try { entry = JSON.parse(line); } catch { continue; }
    const content = (entry.message || entry).content;
    if (!Array.isArray(content)) continue;
    for (const block of content) {
      if (block && block.type === 'tool_use' && block.name) {
        counts[block.name] = (counts[block.name] || 0) + 1;
      }
    }
  }
  return counts;
}

async function run(ctx) {
  if (!enabled()) return respond.allow();

  const ws = ctx.cwd || paths.workspaceRoot();
  const sessionsDir = path.join(ws, 'memory', 'sessions');

  let pipelinePhase = null;
  try {
    const checkpoints = fs.existsSync(sessionsDir)
      ? fs.readdirSync(sessionsDir).filter((f) => f.endsWith('.checkpoint.json'))
      : [];
    if (checkpoints.length) {
      const newest = checkpoints
        .map((f) => ({ f, at: fs.statSync(path.join(sessionsDir, f)).mtimeMs }))
        .sort((a, b) => b.at - a.at)[0];
      const checkpoint = state.readJson(path.join(sessionsDir, newest.f), null);
      pipelinePhase = checkpoint && (checkpoint.currentPhase || checkpoint.phase);
    }
  } catch { /* telemetry never fails loudly */ }

  try {
    state.appendChained(state.telemetryPath(), {
      event: 'turn',
      repo: paths.repoSlug(ws),
      sessionId: ctx.sessionId,
      pipelinePhase,
      toolCounts: countTurnTools(ctx.transcriptPath),
      hookProfile: process.env.ORCHESTRATOR_HOOK_PROFILE
        || process.env.CLAUDE_PLUGIN_OPTION_HOOK_PROFILE || 'standard',
    });
  } catch { /* ignore */ }

  return respond.allow();
}

module.exports = { run, enabled, countTurnTools };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    await run(stdin.normalize(payload));
    process.exit(0);
  });
}
