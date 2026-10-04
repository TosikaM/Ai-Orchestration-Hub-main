#!/usr/bin/env node
'use strict';
/**
 * Multi-hook, single-process dispatcher.
 *
 *   node hooks/runtime/dispatch.js stop:dispatcher:sync
 *
 * Reads the payload once, loads every handler the dispatcher owns, and calls each
 * one's exported run(ctx) in the same Node process. Five hooks at the Stop event cost
 * one interpreter startup (~50-100 ms) instead of five.
 *
 * This is why every handler exports run(payload) alongside its CLI entry, and why that
 * was a hard requirement from the first handler rather than something to add later:
 * retrofitting a run() export onto handlers written as scripts is a rewrite, not a
 * refactor.
 *
 * Async dispatchers detach and never make the user wait. Learning capture, staleness
 * detection, and telemetry are all things that should happen and none of them is worth
 * a single second of somebody's attention.
 */

const path = require('path');
const flags = require('./flags');
const stdin = require('./lib/stdin');
const respond = require('./lib/respond');

const DEBUG = ['1', 'true', 'on'].includes(String(process.env.ORCHESTRATOR_HOOK_DEBUG || '').toLowerCase());

function log(...args) {
  if (DEBUG) process.stderr.write(`[orchestrator-dispatch] ${args.join(' ')}\n`);
}

/**
 * Write, then exit once the write has actually left the process. `write()` followed by
 * `exit()` truncates anything larger than the pipe buffer, and a truncated decision is
 * read by the harness as no decision — which reads as permission. See run.js for the
 * same guard and the fuller explanation.
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

async function callHandler(hookId, ctx) {
  const meta = flags.hookMeta(hookId);
  if (!meta) { log(`${hookId} not in registry`); return null; }
  if (!flags.isHookEnabled(hookId)) { log(`${hookId} disabled`); return null; }

  let handler;
  try {
    handler = require(path.join(__dirname, 'handlers', `${meta.handler}.js`));
  } catch (error) {
    process.stderr.write(`[orchestrator-dispatch] cannot load "${meta.handler}": ${error.message}\n`);
    return null;
  }
  if (typeof handler.run !== 'function') {
    process.stderr.write(`[orchestrator-dispatch] "${meta.handler}" does not export run(ctx)\n`);
    return null;
  }
  try {
    return await handler.run(ctx, { hookId, meta, flags });
  } catch (error) {
    // One failing handler must not take down the others. A learning that fails to be
    // captured is a small loss; a Stop hook that crashes and blocks the turn is not.
    process.stderr.write(`[orchestrator-dispatch] ${hookId} threw: ${error.stack || error.message}\n`);
    return null;
  }
}

async function main() {
  const dispatcherId = process.argv[2];
  if (!dispatcherId) { process.exit(0); }

  const dispatcher = flags.dispatcherMeta(dispatcherId);
  if (!dispatcher) {
    process.stderr.write(`[orchestrator-dispatch] "${dispatcherId}" is not in registry.json\n`);
    process.exit(0);
  }
  if (!flags.hooksEnabled()) process.exit(0);

  const { payload, parseError, truncated, reason } = await stdin.readPayload();
  const ctx = stdin.normalize(payload, { truncated, reason });

  // The synchronous Stop dispatcher owns the human gate, which is blocking. A truncated
  // payload there would let a session end with a gate still unanswered — the one thing
  // that gate exists to prevent — so it fails closed. The async dispatcher only does
  // bookkeeping and degrades quietly instead.
  if (truncated && dispatcher.mode === 'sync') {
    const out = respond.serialize(dispatcher.event, respond.blockStop([
      `[${dispatcherId}]`,
      '',
      'The hook payload could not be read in full, so the synchronous stop checks did not run.',
      '',
      `  ${reason}`,
      '',
      'This dispatcher owns the human gate. Allowing a stop here would end a session with a',
      'gate potentially unanswered, which is exactly what the gate exists to prevent.',
      '',
      'Re-run, or inspect memory/sessions/ for an unanswered *.gate-*.md with no matching',
      '.json verdict.',
    ].join('\n')));
    return finish(out, 0);
  }
  if (parseError) log(`unparseable payload (${reason}) — async dispatcher, continuing`);

  // A Stop hook that fires because a previous Stop hook blocked would loop forever.
  if (ctx.stopHookActive && dispatcher.event === 'Stop') {
    log('stop_hook_active is set — not re-blocking');
    process.exit(0);
  }

  const results = [];
  for (const hookId of dispatcher.hookIds || []) {
    /* eslint-disable no-await-in-loop */
    // Sequential on purpose: these handlers share session state files, and the
    // ordering in the registry is meaningful (citation guard before the human gate).
    const result = await callHandler(hookId, ctx);
    if (result) results.push(result);
  }

  if (dispatcher.mode === 'async') {
    // Nothing is emitted. The work is the point, not the response.
    process.exit(0);
  }

  const merged = respond.merge(results);
  const out = respond.serialize(dispatcher.event, merged);
  return finish(out, 0);
}

main().catch((error) => {
  process.stderr.write(`[orchestrator-dispatch] fatal: ${error.stack || error.message}\n`);
  process.exit(0);
});
