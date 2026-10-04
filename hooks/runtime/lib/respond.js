'use strict';
/**
 * The hook response protocol, in one place.
 *
 * Every handler returns a plain object describing what it decided; only run.js and
 * dispatch.js serialize. Keeping the wire format out of the handlers is what makes a
 * handler callable both as a standalone CLI hook and in-process from the dispatcher,
 * which the single-process Stop phase depends on.
 */

/** Allow the action. Nothing is written; an empty response is a permit. */
function allow() {
  return { decision: 'allow' };
}

/**
 * Deny the action. `reason` is text the model reads and must respond to — it is the
 * only channel a gate has, so it should say what to do, not just what went wrong.
 */
function deny(reason) {
  return { decision: 'deny', reason };
}

/** Ask the user rather than deciding. Reserved for genuinely user-owned choices. */
function ask(reason) {
  return { decision: 'ask', reason };
}

/** Add context to the model's view without changing the decision. */
function inform(context) {
  return { decision: 'allow', context };
}

/** Block a Stop, forcing the agent to keep working. */
function blockStop(reason) {
  return { decision: 'block', reason };
}

function serialize(event, result) {
  if (!result || result.decision === 'allow') {
    if (result && result.context) {
      if (event === 'SessionStart') {
        return JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'SessionStart',
            additionalContext: result.context,
          },
        });
      }
      if (event === 'PreToolUse') {
        return JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            permissionDecision: 'allow',
            permissionDecisionReason: result.context,
          },
        });
      }
      return JSON.stringify({ systemMessage: result.context });
    }
    return '';
  }

  if (event === 'PreToolUse' && (result.decision === 'deny' || result.decision === 'ask')) {
    return JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: result.decision,
        permissionDecisionReason: result.reason,
      },
    });
  }

  if (result.decision === 'block') {
    return JSON.stringify({ decision: 'block', reason: result.reason });
  }

  return JSON.stringify({ systemMessage: result.reason || '' });
}

/**
 * Merge several handler results into one response for the dispatcher.
 * A block or a deny anywhere wins; contexts concatenate.
 */
function merge(results) {
  const decisive = results.find((r) => r && (r.decision === 'deny' || r.decision === 'block'));
  const contexts = results.filter((r) => r && r.context).map((r) => r.context);
  if (decisive) {
    const extra = contexts.length ? `\n\n${contexts.join('\n\n')}` : '';
    return { ...decisive, reason: `${decisive.reason}${extra}` };
  }
  if (contexts.length) return { decision: 'allow', context: contexts.join('\n\n') };
  return { decision: 'allow' };
}

module.exports = { allow, deny, ask, inform, blockStop, serialize, merge };
