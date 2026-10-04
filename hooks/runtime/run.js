#!/usr/bin/env node
'use strict';
/**
 * Single-hook entry point.
 *
 *   node hooks/runtime/run.js <hookId>
 *
 * Reads the event payload from stdin, resolves the hook in registry.json, checks the
 * flags, calls the handler's exported run(ctx), and serializes the decision.
 *
 * Failure policy, stated because it is the interesting part: a handler that throws is
 * treated as ALLOW, not as DENY. That looks like the wrong default for a gate, and it
 * is a deliberate trade. A crashing gate that blocks every edit turns a bug in our
 * hook into a total work stoppage for the user, with no obvious cause and no way to
 * proceed. A crashing gate that permits degrades to the pre-gate world and says so
 * loudly on stderr. The failure we accept is the recoverable one.
 *
 * The one exception is the destructive gate, which fails closed — see its handler.
 */

const path = require('path');
const flags = require('./flags');
const stdin = require('./lib/stdin');
const respond = require('./lib/respond');

const DEBUG = ['1', 'true', 'on'].includes(String(process.env.ORCHESTRATOR_HOOK_DEBUG || '').toLowerCase());

function log(...args) {
  if (DEBUG) process.stderr.write(`[orchestrator-hook] ${args.join(' ')}\n`);
}

/**
 * Write the decision and exit only once it has actually left the process.
 *
 * `process.stdout.write(out); process.exit(0)` looks correct and truncates output larger
 * than the pipe buffer, because exit() does not flush a pending asynchronous write. On a
 * denial that is catastrophically quiet: the harness receives a partial JSON object,
 * fails to parse a permissionDecision out of it, and proceeds as though the hook had
 * permitted the action. The denial text is long precisely because it needs to be
 * useful — which is exactly what pushes it past the buffer.
 *
 * So: write with a completion callback, and keep a short watchdog for the case where the
 * consumer never drains and the callback therefore never fires.
 */
function finish(out, code) {
  if (!out) {
    process.exit(code);
    return;
  }
  let done = false;
  const exit = () => { if (!done) { done = true; process.exit(code); } };
  const watchdog = setTimeout(exit, 2000);
  watchdog.unref?.();
  process.stdout.write(out, () => { clearTimeout(watchdog); exit(); });
}

async function main() {
  const hookId = process.argv[2];
  if (!hookId) {
    process.stderr.write('run.js: no hook id given\n');
    process.exit(0);
  }

  const meta = flags.hookMeta(hookId);
  if (!meta) {
    process.stderr.write(
      `[orchestrator-hook] "${hookId}" is not in hooks/runtime/registry.json. `
      + 'The manifest and the registry have drifted; validate-structure.py catches this in CI.\n',
    );
    process.exit(0);
  }

  if (!flags.isHookEnabled(hookId)) {
    log(`${hookId} disabled (profile=${flags.activeProfile()})`);
    process.exit(0);
  }

  const { payload, parseError, truncated, reason } = await stdin.readPayload();
  const ctx = stdin.normalize(payload, { truncated, reason });

  // FAIL CLOSED ON A PAYLOAD WE COULD NOT READ.
  //
  // A truncated payload normalizes to empty strings, and every gate treats an empty
  // file path or command as "nothing to check" and allows. That turns a slow pipe into
  // a silent bypass of every blocking gate at once.
  //
  // So a blocking hook that cannot see its input denies and says why. A non-blocking
  // one proceeds — it can only advise, and advice degraded by a truncated payload is a
  // smaller loss than a work stoppage.
  if (truncated && meta.blocking) {
    // The refusal shape is event-specific: PreToolUse denies a tool call, Stop blocks the
    // turn from ending. Emitting a `deny` on a Stop event serializes to a plain message,
    // which the harness reads as "no objection" — the precise failure this branch exists
    // to prevent, reintroduced one layer up.
    const refuse = meta.event === 'Stop' ? respond.blockStop : respond.deny;
    const out = respond.serialize(meta.event, refuse([
      `[${hookId}]`,
      '',
      'The hook payload could not be read in full, so this action cannot be cleared.',
      '',
      `  ${reason}`,
      '',
      'This gate fails closed on an unreadable payload. A gate that cannot see its input',
      'must not report that its input is fine — treating a truncated payload as "nothing',
      'to check" would silently disable every blocking gate at once.',
      '',
      'If this recurs, the payload is likely very large (a MultiEdit over a big file, or',
      'a command carrying a long heredoc). Split the operation, or raise MAX_BYTES in',
      'hooks/runtime/lib/stdin.js deliberately.',
    ].join('\n')));
    return finish(out, 0);
  }
  if (parseError) log(`${hookId}: unparseable payload (${reason}) — non-blocking, continuing`);

  let handler;
  try {
    handler = require(path.join(__dirname, 'handlers', `${meta.handler}.js`));
  } catch (error) {
    process.stderr.write(`[orchestrator-hook] cannot load handler "${meta.handler}": ${error.message}\n`);
    process.exit(0);
  }

  if (typeof handler.run !== 'function') {
    process.stderr.write(
      `[orchestrator-hook] handler "${meta.handler}" does not export run(ctx). `
      + 'Every handler must export run() as well as a CLI entry so the dispatcher can call it in-process.\n',
    );
    process.exit(0);
  }

  let result;
  try {
    result = await handler.run(ctx, { hookId, meta, flags });
  } catch (error) {
    process.stderr.write(`[orchestrator-hook] ${hookId} threw: ${error.stack || error.message}\n`);
    result = respond.allow();
  }

  const out = respond.serialize(meta.event, result || respond.allow());
  return finish(out, 0);
}

main().catch((error) => {
  process.stderr.write(`[orchestrator-hook] fatal: ${error.stack || error.message}\n`);
  process.exit(0);
});
