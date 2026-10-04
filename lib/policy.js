'use strict';
/**
 * Policy access for the hook runtime.
 *
 * THE RESOLUTION LOGIC LIVES IN ONE PLACE, AND IT IS PYTHON
 *
 * `scripts/policy.py` owns layer merging and the narrowing guard. This module does NOT
 * reimplement that. Two implementations of a precedence rule is two precedence rules,
 * and the one that drifts is always the one nobody runs by hand — which here would be
 * the one actually enforcing at the tool call.
 *
 * So: policy.py writes its resolved output to a cache, and this module reads it.
 *
 * WHAT HAPPENS WHEN THE CACHE IS MISSING
 *
 * The interesting case, and the one worth being deliberate about.
 *
 *   - No narrowing layers are populated (organization/project/repository/environment are
 *     all empty, and there is no repo-local policy file). Then `defaults` IS the resolved
 *     policy, byte for byte, and reading it directly is not a guess. Use it.
 *
 *   - Narrowing layers ARE populated but no cache exists. Then the shipped defaults are
 *     WIDER than what the organization intends, and using them would hand an agent
 *     permissions somebody deliberately withheld. Refuse, and say which command fixes it.
 *
 * Failing open on the first case and closed on the second is the only combination that
 * is neither unusable nor quietly wrong.
 */

const fs = require('fs');
const path = require('path');
const config = require('./config');
const paths = require('./paths');

const NARROWING_LAYERS = ['organization', 'project', 'repository', 'environment'];

let cached = null;

function cachePath() {
  return path.join(paths.stateHome(), 'state', 'resolved-policy.json');
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

/**
 * @returns {{policy: object|null, source: string, stale: boolean, reason: string|null}}
 */
function load() {
  if (cached) return cached;

  const doc = config.loadConfig('policy.json');
  if (!doc) {
    cached = {
      policy: null,
      source: 'none',
      stale: false,
      reason: 'config/policy.json is missing or unparseable.',
    };
    return cached;
  }

  const resolvedCache = readJson(cachePath());
  if (resolvedCache && resolvedCache.resolved) {
    cached = { policy: resolvedCache.resolved, source: 'cache', stale: false, reason: null };
    return cached;
  }

  const populated = NARROWING_LAYERS.filter(
    (layer) => doc[layer] && Object.keys(doc[layer]).length > 0,
  );
  const repoLocal = path.join(paths.workspaceRoot(), '.github', 'orchestrator-policy.json');
  if (fs.existsSync(repoLocal)) populated.push('repository-local');

  if (populated.length === 0) {
    // Defaults are the whole policy. Not a guess.
    cached = { policy: doc.defaults || {}, source: 'defaults', stale: false, reason: null };
    return cached;
  }

  cached = {
    policy: null,
    source: 'unresolved',
    stale: true,
    reason:
      `Policy layers [${populated.join(', ')}] are populated but no resolved cache exists at `
      + `${cachePath()}. The shipped defaults are wider than what those layers intend, so `
      + 'using them would grant permissions somebody deliberately withheld. '
      + 'Run: python scripts/policy.py resolve --json > "' + cachePath() + '"',
  };
  return cached;
}

function get(dotted, fallback) {
  const { policy } = load();
  if (!policy) return fallback;
  let node = policy;
  for (const part of String(dotted).split('.')) {
    if (!node || typeof node !== 'object' || !(part in node)) return fallback;
    node = node[part];
  }
  return node === undefined ? fallback : node;
}

function autonomyLevel() {
  return get('autonomy.level', null);
}

/**
 * Capability check. Deny beats allow, and absence is denial.
 * A broader grant implies its dotted children (`repo.write` implies `repo.write.tests`),
 * never the reverse.
 */
function isAllowed(agent, capability) {
  const agents = get('permissions.agents', null);
  if (!agents) return { allowed: false, reason: 'no permission table resolved' };
  const entry = agents[agent];
  if (!entry) {
    return {
      allowed: false,
      reason: `'${agent}' has no permission entry; an agent with no declared permissions gets none`,
    };
  }
  const deny = entry.deny || [];
  const allow = entry.allow || [];
  if (deny.includes(capability)) {
    return { allowed: false, reason: `'${capability}' is explicitly denied for ${agent}` };
  }
  if (allow.includes(capability)) return { allowed: true, reason: null };
  for (const granted of allow) {
    if (capability.startsWith(`${granted}.`)) {
      return { allowed: true, reason: `granted via '${granted}'` };
    }
  }
  return { allowed: false, reason: `'${capability}' is not in ${agent}'s allow list; absence is denial` };
}

function forbiddenPathGlobs() {
  return get('dataPolicy.forbiddenPathGlobs', []);
}

function resetCache() {
  cached = null;
}

module.exports = {
  load, get, autonomyLevel, isAllowed, forbiddenPathGlobs, cachePath, resetCache,
  NARROWING_LAYERS,
};
