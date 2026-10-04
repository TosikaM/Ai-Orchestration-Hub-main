'use strict';
/**
 * Path resolution for the plugin, the workspace, and machine-scoped state.
 *
 * CLAUDE_PLUGIN_ROOT is not reliably populated across every Claude Code version and
 * install scope. The defensive answer other projects reached for is a ~1,500-character
 * inlined JavaScript resolver in every hook command string, which works and is
 * unreadable. The fallback lives here instead, run.js calls it once, and the manifest
 * commands stay one line each.
 *
 * The accepted residual risk: if run.js itself cannot be located, the hook no-ops
 * rather than mis-resolving. A hook that silently does nothing is a smaller failure
 * than a hook that reads the wrong tree and reports confidently about it.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

/** Marker files that identify this repository as the plugin root. */
const ROOT_MARKERS = ['hub.config.json', '.claude-plugin/plugin.json'];

function looksLikePluginRoot(dir) {
  if (!dir) return false;
  return ROOT_MARKERS.every((marker) => fs.existsSync(path.join(dir, marker)));
}

/** Walk upward from `start` looking for the plugin root markers. */
function findUpward(start, limit = 8) {
  let current = start;
  for (let i = 0; i < limit; i += 1) {
    if (looksLikePluginRoot(current)) return current;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return null;
}

/**
 * Resolve the plugin root. Order matters: an explicit env var beats inference,
 * because a developer running against a local checkout must be able to say so.
 */
function pluginRoot() {
  const explicit = process.env.ORCHESTRATOR_PLUGIN_ROOT || process.env.CLAUDE_PLUGIN_ROOT;
  if (explicit && looksLikePluginRoot(explicit)) return explicit;
  if (explicit && fs.existsSync(explicit)) return explicit;

  const fromThisFile = findUpward(__dirname);
  if (fromThisFile) return fromThisFile;

  return null;
}

/** The repository the user is actually working in, which is usually not the plugin. */
function workspaceRoot() {
  const explicit = process.env.CLAUDE_PROJECT_DIR || process.env.ORCHESTRATOR_WORKSPACE;
  if (explicit && fs.existsSync(explicit)) return explicit;
  return process.cwd();
}

/**
 * Machine-scoped state. Deliberately outside any repository so that a terminal
 * session, a CI job, and the view plane all read the same files, and so that
 * uninstalling the plugin from one repo does not orphan another repo's state.
 */
function stateHome() {
  const explicit = process.env.ORCHESTRATOR_HOME;
  if (explicit) return explicit;
  return path.join(os.homedir(), '.orchestrator');
}

function stateDir(...parts) {
  const dir = path.join(stateHome(), ...parts);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/** A stable, filesystem-safe identifier for a repository path. */
function repoSlug(repoPath = workspaceRoot()) {
  const base = path.basename(path.resolve(repoPath)) || 'workspace';
  const normalized = base.toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  return normalized || 'workspace';
}

/** True when `child` is inside `parent`. Used to refuse writes outside the workspace. */
function isInside(parent, child) {
  const rel = path.relative(path.resolve(parent), path.resolve(child));
  return rel !== '' && !rel.startsWith('..') && !path.isAbsolute(rel);
}

module.exports = {
  ROOT_MARKERS,
  looksLikePluginRoot,
  findUpward,
  pluginRoot,
  workspaceRoot,
  stateHome,
  stateDir,
  repoSlug,
  isInside,
};
