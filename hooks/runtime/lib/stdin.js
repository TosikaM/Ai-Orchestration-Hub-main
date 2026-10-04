'use strict';
/**
 * Hook payload input.
 *
 * Claude Code delivers the hook event as JSON on stdin.
 *
 * THE FAILURE THIS FILE EXISTS TO PREVENT
 *
 * An earlier version of this module read stdin unbounded and resolved on a two-second
 * timer. That looks harmless and is not. Trace it through:
 *
 *   a large or slow payload
 *     -> the timer fires before the pipe drains
 *     -> `data` holds partial JSON
 *     -> JSON.parse throws, and the module returned an empty payload
 *     -> normalize() produced ctx.filePath = '' and ctx.command = ''
 *     -> every gate checked `if (!ctx.filePath) return allow()`
 *     -> ALL FIVE BLOCKING GATES SILENTLY PERMITTED THE ACTION
 *
 * Nothing logged, nothing denied, and the reassurance of having gates survived while the
 * protection did not. A payload big enough to trip it is not exotic: a MultiEdit over a
 * large file, or a Bash call carrying a long heredoc.
 *
 * So truncation is now a first-class, propagated fact rather than an invisible one:
 *
 *   - reads are capped at MAX_BYTES and the cap is recorded, not silently applied
 *   - a timeout with unparseable content is reported as `truncated`, never as an empty
 *     payload that happens to parse as "nothing to check"
 *   - run.js and dispatch.js read that flag and make BLOCKING hooks fail CLOSED
 *
 * The general rule this is an instance of: a guard that cannot see its input must not
 * report that its input is fine.
 */

const TIMEOUT_MS = 5000;
const MAX_BYTES = 1024 * 1024; // 1 MiB

function readRaw() {
  return new Promise((resolve) => {
    if (process.stdin.isTTY) {
      resolve({ raw: '', overflow: false, timedOut: false, ended: true });
      return;
    }

    let data = '';
    let bytes = 0;
    let overflow = false;
    let settled = false;

    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try { process.stdin.pause(); } catch { /* ignore */ }
      resolve(result);
    };

    const timer = setTimeout(
      () => finish({ raw: data, overflow, timedOut: true, ended: false }),
      TIMEOUT_MS,
    );

    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => {
      bytes += Buffer.byteLength(chunk, 'utf8');
      if (bytes > MAX_BYTES) {
        // Stop accumulating, but record WHY. Quietly keeping the first megabyte and
        // parsing it would reintroduce exactly the bug this file documents.
        overflow = true;
        finish({ raw: data, overflow: true, timedOut: false, ended: false });
        return;
      }
      data += chunk;
    });
    process.stdin.on('end', () => finish({ raw: data, overflow, timedOut: false, ended: true }));
    process.stdin.on('error', () => finish({ raw: data, overflow, timedOut: false, ended: false }));
  });
}

/**
 * @returns {{raw: string, payload: object, parseError: boolean, truncated: boolean, reason: string|null}}
 */
async function readPayload() {
  const { raw, overflow, timedOut, ended } = await readRaw();

  if (!raw || !raw.trim()) {
    // Genuinely no input — a hand invocation, or a harness that does not pipe. This is
    // NOT truncation: there is nothing to have lost, so a gate seeing no file path is
    // seeing the truth.
    return { raw: '', payload: {}, parseError: false, truncated: false, reason: null };
  }

  try {
    return {
      raw,
      payload: JSON.parse(raw),
      parseError: false,
      truncated: false,
      reason: null,
    };
  } catch {
    const reason = overflow
      ? `payload exceeded ${MAX_BYTES} bytes and was cut off`
      : timedOut
        ? `stdin did not finish within ${TIMEOUT_MS}ms; the payload is incomplete`
        : ended
          ? 'payload is not valid JSON'
          : 'stdin closed before the payload completed';
    // parseError AND truncated. The caller must not treat this as "no input".
    return { raw, payload: {}, parseError: true, truncated: true, reason };
  }
}

/**
 * Normalize the fields handlers use, so a change in the event envelope is a one-file
 * change here rather than a sweep through every handler.
 *
 * `truncated` rides along deliberately: a handler that wants to reason about it can,
 * and run.js enforces the fail-closed rule for blocking hooks regardless.
 */
function normalize(payload = {}, meta = {}) {
  const input = payload.tool_input || payload.toolInput || {};
  return {
    sessionId: payload.session_id || payload.sessionId || process.env.CLAUDE_SESSION_ID || 'default',
    event: payload.hook_event_name || payload.hookEventName || '',
    toolName: payload.tool_name || payload.toolName || '',
    toolInput: input,
    toolResponse: payload.tool_response || payload.toolResponse || null,
    filePath: input.file_path || input.filePath || input.path || '',
    command: input.command || '',
    prompt: payload.prompt || '',
    transcriptPath: payload.transcript_path || payload.transcriptPath || '',
    cwd: payload.cwd || process.cwd(),
    stopHookActive: Boolean(payload.stop_hook_active || payload.stopHookActive),
    truncated: Boolean(meta.truncated),
    truncationReason: meta.reason || null,
    // An unattended run has nobody to answer a gate. Handlers that would otherwise wait
    // for a human need to know, rather than blocking a pipeline until it times out.
    headless: Boolean(
      process.env.ORCHESTRATOR_HEADLESS
      || process.env.CI
      || process.env.GITHUB_ACTIONS,
    ),
    raw: payload,
  };
}

module.exports = { readPayload, normalize, TIMEOUT_MS, MAX_BYTES };
