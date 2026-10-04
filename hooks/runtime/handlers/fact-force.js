#!/usr/bin/env node
'use strict';
/**
 * PreToolUse: the Fact-Forcing Gate.
 *
 * ---------------------------------------------------------------------------
 * Portions of this file are derived from ECC's `scripts/hooks/gateguard-fact-force.js`
 *
 *   Copyright (c) 2026 Affaan Mustafa
 *
 *   Permission is hereby granted, free of charge, to any person obtaining a copy
 *   of this software and associated documentation files (the "Software"), to deal
 *   in the Software without restriction, including without limitation the rights
 *   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 *   copies of the Software, and to permit persons to whom the Software is
 *   furnished to do so, subject to the following conditions:
 *
 *   The above copyright notice and this permission notice shall be included in all
 *   copies or substantial portions of the Software.
 *
 *   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 *   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 *   SOFTWARE.
 *
 * ECC's own header credits GateGuard (https://github.com/zunoworks/gateguard).
 * ---------------------------------------------------------------------------
 *
 * WHY THIS EXISTS
 *
 * The architecture document this system grew out of contains an honest admission:
 * grounding is enforced at three points, rated Strong / Moderate / Advisory, and the
 * last one "cannot block." Every word of that was true when the runtime streamed a
 * prompt into a chat window it did not own.
 *
 * It is no longer true. A PreToolUse hook runs before a tool executes and can deny it.
 * That does not require owning the generation stream — it owns the *action* stream,
 * which is where a hallucination stops being a sentence and becomes an edit. A wrong
 * paragraph is cheap. A wrong edit to a file whose importers nobody enumerated is not.
 *
 * THE INSIGHT WORTH PRESERVING
 *
 * Asking a model "are you sure?" is answered "yes" by construction — the same context
 * that produced the claim evaluates the claim. Self-assessment is close to worthless
 * here. Forced *retrieval* is not: an agent cannot produce the importer list without
 * actually searching, and the act of searching creates the awareness that the question
 * never did.
 *
 * So this gate does not ask for confidence. It asks for facts it can tell were fetched.
 *
 * FOUR DESIGN DETAILS THAT ARE EXPENSIVE TO REDISCOVER
 *
 *   1. First touch per file per session, not every edit. Gating every edit makes the
 *      tool unusable and it gets switched off. Gating the first one buys the
 *      investigation exactly once, when it is worth the most.
 *   2. Fact 4 is the anti-drift fact and is deliberately unrelated to the file. Forty
 *      turns into a session, the goal being executed and the goal that was given are
 *      not reliably the same thing, and nothing else in this system checks for that.
 *   3. A denial budget. After three full blocks, denials collapse to one line with an
 *      ordinal. An identical eight-line block repeated ten times becomes wallpaper.
 *   4. Narrow recovery before broad recovery. A gate that offers only "turn it all
 *      off" gets turned all off, permanently, the first time it is inconvenient.
 *      Offering a scalpel before the sledgehammer is what keeps the gate installed.
 *
 * The compliance cost here is unusually low, and that is not an accident: fact 1 in a
 * generic repository means a manual tree walk, but this system maintains a structural
 * graph, so the answer is one CLI call. The gate is cheap to satisfy precisely because
 * the orchestrator already did the indexing work.
 */

const path = require('path');
const fs = require('fs');
const respond = require('../lib/respond');
const gate = require('../lib/gate-state');
const paths = require('../../../lib/paths');

const EDIT_TOOLS = new Set(['Edit', 'MultiEdit', 'NotebookEdit']);
const WRITE_TOOLS = new Set(['Write']);

function graphHint() {
  const root = paths.pluginRoot();
  const script = root ? path.join(root, 'scripts', 'graph.py') : null;
  if (script && fs.existsSync(script)) {
    return 'Fastest path: `python scripts/graph.py importers <file>` reads the cached '
      + 'symbol index instead of walking the tree. Fall back to Grep if the index is cold.';
  }
  return 'Search the tree with Grep or Glob.';
}

function editGate(filePath) {
  return [
    '[Fact-Forcing Gate]',
    '',
    `Before editing ${filePath}, present these facts:`,
    '',
    `1. Every file that imports or requires this one. ${graphHint()}`,
    '2. The exported functions, classes, or types this change affects, each with `file:line`',
    '3. If this file reads or writes persisted data, its field names and shapes',
    "4. The user's current instruction, quoted verbatim",
    '',
    'Present the facts, then retry the same operation.',
    '',
    'Fact 4 is not about the file. It is the drift check: forty turns into a session,',
    'the goal you are executing and the goal you were given are not reliably the same.',
  ].join('\n');
}

function writeGate(filePath) {
  return [
    '[Fact-Forcing Gate]',
    '',
    `Before creating ${filePath}, present these facts:`,
    '',
    '1. The file and line that will call or import this new file',
    '2. Confirmation that no existing file already serves this purpose — search first',
    '3. Which entry in the file manifest authorizes this path. Inventing files that are',
    '   not in the manifest is forbidden by golden rule G1.',
    "4. The user's current instruction, quoted verbatim",
    '',
    'Present the facts, then retry the same operation.',
  ].join('\n');
}

function condensed(action, filePath, ordinal) {
  return (
    `[Fact-Forcing Gate] (denial #${ordinal} this session) First ${action} of ${filePath}: `
    + "state importers, affected exports, data shapes if any, and the user's verbatim "
    + 'instruction, then retry. '
    + '(Path-scoped escape: ORCHESTRATOR_GATE_EXEMPT_GLOBS. Full disable: ORCHESTRATOR_GATEGUARD=off.)'
  );
}

function withRecovery(message) {
  return [
    message,
    '',
    'Narrow recovery: add a matching path glob to ORCHESTRATOR_GATE_EXEMPT_GLOBS to skip',
    'first-touch checks for that path only, without disabling any other gate.',
    '',
    'Broad recovery: if this gate is blocking setup or repair work, run the session with',
    'ORCHESTRATOR_GATEGUARD=off, or add pre:edit-write:fact-force to ORCHESTRATOR_DISABLED_HOOKS.',
  ].join('\n');
}

/**
 * @param {object} ctx normalized hook payload
 * @returns {{decision: string, reason?: string}}
 */
async function run(ctx) {
  if (gate.isDisabled()) return respond.allow();

  const tool = ctx.toolName;
  const isEdit = EDIT_TOOLS.has(tool);
  const isWrite = WRITE_TOOLS.has(tool);
  if (!isEdit && !isWrite) return respond.allow();

  const filePath = ctx.filePath;
  if (!filePath) return respond.allow();
  if (gate.isExempt(filePath)) return respond.allow();

  // A Write to a path that does not exist yet is a creation; a Write over an existing
  // file is an edit wearing a Write's clothes, and the importer question still applies.
  const exists = (() => { try { return fs.existsSync(filePath); } catch { return false; } })();
  const action = isWrite && !exists ? 'create' : 'edit';

  const touch = gate.checkFirstTouch(ctx.sessionId, action, filePath);
  if (!touch.first) return respond.allow();

  const display = path.basename(filePath);
  if (touch.condensed) {
    return respond.deny(condensed(action, display, touch.ordinal));
  }
  const body = action === 'create' ? writeGate(filePath) : editGate(filePath);
  return respond.deny(withRecovery(body));
}

module.exports = { run, editGate, writeGate, condensed };

/* CLI entry, so the handler is testable standalone and runnable outside the dispatcher. */
if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('PreToolUse', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
