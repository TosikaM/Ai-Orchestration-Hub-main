#!/usr/bin/env node
'use strict';
/**
 * Stop: the human gate, made real.
 *
 * WHAT IT REPLACED
 *
 * Three pipeline phases are declared `humanGate: true`, and the entire implementation
 * was a toast notification saying the phase "needs human approval". The protocol text
 * said "post the summary, update status, stop, and wait" — an instruction to the
 * model, enforced by nothing. Instruction-following is exactly the class of control
 * the grounding architecture correctly rates as Moderate.
 *
 * WHAT MAKES IT A GATE
 *
 * The same insight as the fact-forcing gate: you do not need to own the generation
 * stream to own the action stream, and stopping is an action. If a gate artifact
 * exists with no matching verdict file, Stop is blocked. The agent cannot end the turn
 * by asserting that it stopped and waited; it has to actually wait for a file that
 * only a human writes.
 *
 * THE FILE PROTOCOL IS THE POINT
 *
 *   memory/sessions/<pipelineId>.gate-<phase>.md    the artifact to review
 *   memory/sessions/<pipelineId>.gate-<phase>.json  the verdict
 *
 * A JSON file, so `python scripts/pipeline.py approve <id> <phase>` works identically
 * to the view plane's gate panel. The panel is a nicety over a file protocol, never a
 * dependency — anyone on Linux, in a terminal, or in a different editor is fully served.
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const paths = require('../../../lib/paths');
const state = require('../../../lib/state');

function pendingGates(ws) {
  const dir = path.join(ws, 'memory', 'sessions');
  if (!fs.existsSync(dir)) return [];
  let entries;
  try { entries = fs.readdirSync(dir); } catch { return []; }

  const pending = [];
  for (const file of entries) {
    const match = /^(.+)\.gate-([a-z0-9-]+)\.md$/.exec(file);
    if (!match) continue;
    const verdictFile = `${match[1]}.gate-${match[2]}.json`;
    if (entries.includes(verdictFile)) {
      const verdict = state.readJson(path.join(dir, verdictFile), null);
      // A verdict of "changes-requested" is answered; the agent should act on it, not wait.
      if (verdict && verdict.verdict) continue;
    }
    pending.push({
      pipelineId: match[1],
      phase: match[2],
      artifact: path.join(dir, file),
      verdictPath: path.join(dir, verdictFile),
    });
  }
  return pending;
}

function blockMessage(ws, gates) {
  const lines = [
    '[Human Gate]',
    '',
    `${gates.length === 1 ? 'A pipeline phase is' : `${gates.length} pipeline phases are`} `
      + 'waiting on a human verdict. You cannot end the turn while a gate is unanswered — that is',
    'what makes it a gate rather than a request.',
    '',
  ];
  for (const g of gates) {
    const rel = path.relative(ws, g.artifact).replace(/\\/g, '/');
    lines.push(`- \`${g.pipelineId}\` phase **${g.phase}** — artifact: \`${rel}\``);
  }
  lines.push(
    '',
    'What to do now, in order of preference:',
    '',
    '1. If the artifact is not yet complete, finish writing it. A gate with a thin artifact',
    '   trains the reviewer to approve without reading, which defeats every gate in the pipeline.',
    '2. Tell the user the gate is open, summarize what they are approving in three lines, and stop',
    '   asking for anything else.',
    '3. The user approves in the view plane\'s gate panel, or from a terminal:',
    `     python scripts/pipeline.py approve ${gates[0].pipelineId} ${gates[0].phase}`,
    `     python scripts/pipeline.py request-changes ${gates[0].pipelineId} ${gates[0].phase} --note "..."`,
    '',
    'Do not write the verdict file yourself. A gate the agent can clear is not a human gate.',
  );
  return lines.join('\n');
}

async function run(ctx) {
  // If a previous Stop hook already blocked, do not block again — that is an infinite loop.
  if (ctx.stopHookActive) return respond.allow();

  const ws = ctx.cwd || paths.workspaceRoot();
  const gates = pendingGates(ws);
  if (!gates.length) return respond.allow();

  return respond.blockStop(blockMessage(ws, gates));
}

module.exports = { run, pendingGates, blockMessage };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('Stop', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
