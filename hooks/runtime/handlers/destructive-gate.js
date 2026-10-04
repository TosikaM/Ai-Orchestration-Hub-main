#!/usr/bin/env node
'use strict';
/**
 * PreToolUse (Bash | PowerShell): the Destructive Command Gate.
 *
 * Two categories, and the distinction is the design:
 *
 *   FORBIDDEN — never from an agent context. No override, no exempt glob, no profile
 *               that turns it off. `terraform apply`, `kubectl delete`, force-pushing
 *               a protected branch, `DROP DATABASE`. The stack mappings already
 *               recorded some of this knowledge as prose ("Never run apply from an
 *               agent context") in a config file nothing read. Here it is enforced.
 *
 *   GATED     — legitimate but irreversible. `rm -rf`, `git reset --hard`,
 *               `npm publish`. Denied once, with a demand for the blast radius and a
 *               rollback line, then allowed on retry. The gate buys the thinking.
 *
 * THIS HANDLER FAILS CLOSED
 *
 * Every other hook in this runtime treats an internal error as ALLOW, because a
 * crashing gate that blocks all work is worse than one that degrades to the pre-gate
 * world. This one inverts that. If classification throws, the command is denied. The
 * asymmetry is the point: the recoverable failure here is "the agent had to ask you to
 * run it yourself," and the unrecoverable one is a dropped database.
 */

const respond = require('../lib/respond');
const destructive = require('../lib/destructive');
const gate = require('../lib/gate-state');

function forbidden(command, why) {
  return [
    '[Destructive Command — Forbidden]',
    '',
    `This command ${why} and must not run from an agent context.`,
    '',
    `  ${String(command).slice(0, 400)}`,
    '',
    'There is no override for this class. If it genuinely needs to run, hand it to the',
    'user to run themselves, with the exact command and what it will do.',
    '',
    'What you can do instead: produce the plan, the manifest diff, or the dry-run output',
    '(`terraform plan`, `kubectl diff`, `--dry-run`) and present that for approval.',
  ].join('\n');
}

function gated(command, why, ordinal, condensed) {
  if (condensed) {
    return (
      `[Destructive Command] (denial #${ordinal} this session) ${why}. State what it `
      + 'modifies and the one-line rollback, then retry.'
    );
  }
  return [
    '[Destructive Command]',
    '',
    `This command ${why}. Before running it, present:`,
    '',
    '1. Every file, branch, or data store it modifies or deletes — enumerated, not summarized',
    '2. A one-line rollback procedure, or an explicit statement that there is none',
    "3. The user's current instruction, quoted verbatim",
    '',
    `  ${String(command).slice(0, 400)}`,
    '',
    'Present the facts, then retry the same command.',
    '',
    'Narrow recovery: prefer the reversible form first — `git stash` over `git reset --hard`,',
    '`rm -i` or a move-to-trash over `rm -rf`, `--dry-run` before the real thing.',
  ].join('\n');
}

/**
 * Both shells are gated. This project is Windows-primary, so PowerShell is the shell
 * most commands actually run through — gating only Bash would leave the gate looking
 * installed while the destructive commands went around it. `Remove-Item -Recurse -Force`
 * deletes exactly as thoroughly as `rm -rf`.
 */
const SHELL_TOOLS = new Set(['Bash', 'PowerShell']);

async function run(ctx) {
  if (!SHELL_TOOLS.has(ctx.toolName)) return respond.allow();
  const command = ctx.command;
  if (!command) return respond.allow();

  let verdict;
  try {
    verdict = destructive.classify(command);
  } catch (error) {
    // Fail closed. See the header.
    return respond.deny(
      '[Destructive Command] The destructive-command classifier failed to run '
      + `(${error.message}), so this command cannot be cleared. This gate fails closed by `
      + 'design. Run the command yourself if you are confident it is safe.',
    );
  }

  if (verdict.verdict === 'forbid') {
    return respond.deny(forbidden(command, verdict.why));
  }
  if (verdict.verdict === 'gate') {
    if (gate.isDisabled()) return respond.allow();
    // Key on the classified pattern, not the exact command string: `rm -rf a` and
    // `rm -rf b` are the same lesson, and gating both teaches nothing the first did not.
    const touch = gate.checkFirstTouch(ctx.sessionId, 'bash', verdict.pattern || command);
    if (!touch.first) return respond.allow();
    return respond.deny(gated(command, verdict.why, touch.ordinal, touch.condensed));
  }
  return respond.allow();
}

module.exports = { run, forbidden, gated };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('PreToolUse', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
