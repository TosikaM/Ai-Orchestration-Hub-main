'use strict';
/**
 * Destructive-command classification.
 *
 * Two categories, and the distinction is the whole design:
 *
 *   FORBIDDEN — never runs from an agent context, no override, no exempt glob.
 *               Infrastructure mutation and history rewriting on a shared branch.
 *               The stack mappings already knew about some of these and recorded the
 *               knowledge as `stateWarning: "Never run apply from an agent context"`,
 *               which is prose in a config file that nothing reads. This is the same
 *               knowledge, enforced.
 *
 *   GATED     — legitimate but irreversible. Allowed once the agent has stated what it
 *               modifies and how to roll it back. The gate buys the thinking, not the
 *               refusal.
 *
 * Detection is deliberately lexical and conservative. A shell command is not reliably
 * parseable, so this errs toward flagging: a false gate costs one turn, and a missed
 * `rm -rf` costs a workday.
 */

const config = require('../../../lib/config');

/** Commands that must never run from an agent context. */
const FORBIDDEN = [
  { re: /\bterraform\s+(apply|destroy)\b/i, why: 'mutates real infrastructure' },
  { re: /\bkubectl\s+(delete|apply|replace|drain|cordon)\b/i, why: 'mutates a live cluster' },
  { re: /\bhelm\s+(install|upgrade|uninstall|rollback)\b/i, why: 'mutates a live cluster' },
  { re: /\baws\s+\w+\s+(delete|terminate|remove)-/i, why: 'deletes cloud resources' },
  { re: /\baz\s+\w+\s+delete\b/i, why: 'deletes cloud resources' },
  { re: /\bgcloud\s+\w+\s+delete\b/i, why: 'deletes cloud resources' },
  { re: /\bgit\s+push\s+(--force|-f)\b(?!.*--force-with-lease)/i, why: 'force-push discards other people\'s commits' },
  { re: /\bgit\s+push\s+.*\b(main|master|release\/|prod)\b.*\s(--force|-f)\b/i, why: 'force-push to a protected branch' },
  { re: /\bdrop\s+(database|schema|table)\b/i, why: 'destroys persisted data' },
  { re: /\bmkfs(\.\w+)?\b|\bdd\s+if=.*\bof=\/dev\//i, why: 'destroys a filesystem or device' },
  { re: /\b(shutdown|reboot|halt)\b/i, why: 'takes the machine down' },
  { re: /:\(\)\{\s*:\|:&\s*\};:/, why: 'fork bomb' },
  // PowerShell forms. This project is Windows-primary, so these are not exotic cases —
  // they are the shape the same mistakes actually take here.
  { re: /\bFormat-Volume\b|\bClear-Disk\b|\bInitialize-Disk\b/i, why: 'destroys a volume' },
  { re: /\bStop-Computer\b|\bRestart-Computer\b/i, why: 'takes the machine down' },
  { re: /\bRemove-Item\b[^\n]*\b[A-Za-z]:\\\s*(-|$)/i, why: 'targets a drive root' },
];

/** Irreversible but legitimate. Gated, not forbidden. */
const GATED = [
  { re: /\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+/i, why: 'recursive or forced delete' },
  { re: /\bRemove-Item\b[^\n]*-Recurse[^\n]*-Force/i, why: 'recursive forced delete' },
  { re: /\bgit\s+reset\s+--hard\b/i, why: 'discards uncommitted work' },
  { re: /\bgit\s+clean\s+-[a-zA-Z]*f/i, why: 'deletes untracked files' },
  { re: /\bgit\s+checkout\s+--\s+\./i, why: 'discards all working-tree changes' },
  { re: /\bgit\s+(rebase|filter-branch|filter-repo)\b/i, why: 'rewrites history' },
  { re: /\bnpm\s+publish\b|\bdotnet\s+nuget\s+push\b|\btwine\s+upload\b|\bcargo\s+publish\b/i, why: 'publishes a package that cannot be unpublished cleanly' },
  { re: /\bgh\s+release\s+(create|delete)\b/i, why: 'creates or deletes a public release' },
  { re: /\btruncate\b|\b>\s*\/dev\/(sd|nvme)/i, why: 'truncates a file or device' },
  { re: /\bdocker\s+(system\s+prune|volume\s+rm)\b/i, why: 'deletes container volumes or caches' },
  { re: /\bchmod\s+-R\s+777\b/i, why: 'removes filesystem protection recursively' },
];

/** Commands the stack mappings declared forbidden for the detected stack. */
function stackForbidden() {
  const mappings = config.stackMappings();
  if (!mappings || !Array.isArray(mappings.stacks)) return [];
  const out = [];
  for (const stack of mappings.stacks) {
    for (const cmd of stack.forbiddenCommands || []) {
      out.push({
        re: new RegExp(`\\b${cmd.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+')}`, 'i'),
        why: stack.forbiddenCommandsReason || `declared forbidden for the ${stack.id} stack`,
        stack: stack.id,
      });
    }
  }
  return out;
}

/**
 * Classify a shell command.
 * @returns {{verdict: 'allow'|'gate'|'forbid', why: string|null, pattern: string|null}}
 */
function classify(command) {
  const text = String(command || '');
  if (!text.trim()) return { verdict: 'allow', why: null, pattern: null };

  for (const rule of FORBIDDEN.concat(stackForbidden())) {
    if (rule.re.test(text)) {
      return { verdict: 'forbid', why: rule.why, pattern: String(rule.re) };
    }
  }
  for (const rule of GATED) {
    if (rule.re.test(text)) {
      return { verdict: 'gate', why: rule.why, pattern: String(rule.re) };
    }
  }
  return { verdict: 'allow', why: null, pattern: null };
}

module.exports = { classify, FORBIDDEN, GATED, stackForbidden };
