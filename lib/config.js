'use strict';
/**
 * Configuration resolution, and the only source of organization identity.
 *
 * Resolution order, most specific first:
 *   0. CLAUDE_PLUGIN_ROOT / the resolved plugin root  (the shipped defaults)
 *   1. <workspace>/.github/config/                    (what actually synced into this repo)
 *   2. <workspace>/.orchestrator.json                 (a per-repo local override)
 *   3. Environment variables                          (a per-session override)
 *
 * Every reader goes through here. Two config files with slightly different values is
 * the single most common way a system like this rots, and P6 exists to prevent it.
 */

const fs = require('fs');
const path = require('path');
const paths = require('./paths');

const cache = new Map();

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^﻿/, ''));
  } catch {
    return null;
  }
}

/**
 * Load a config file by its name under config/. Returns null when it cannot be found
 * or parsed — callers decide whether that is fatal. Nothing here throws, because a
 * hook that crashes on a malformed config file is worse than one that declines to run.
 */
function loadConfig(name) {
  if (cache.has(name)) return cache.get(name);

  const candidates = [];
  const ws = paths.workspaceRoot();
  if (ws) {
    candidates.push(path.join(ws, '.github', 'config', name));
  }
  const root = paths.pluginRoot();
  if (root) {
    candidates.push(path.join(root, 'config', name));
    candidates.push(path.join(root, name));
  }

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      const parsed = readJson(candidate);
      if (parsed) {
        parsed.__source = candidate;
        cache.set(name, parsed);
        return parsed;
      }
    }
  }
  cache.set(name, null);
  return null;
}

function hubConfig() {
  const root = paths.pluginRoot();
  if (!root) return null;
  if (cache.has('__hub')) return cache.get('__hub');
  const parsed = readJson(path.join(root, 'hub.config.json'));
  cache.set('__hub', parsed);
  return parsed;
}

/** The org id. The one place any other module may ask. */
function orgId() {
  const hub = hubConfig();
  return (hub && hub.org && hub.org.id) || 'unknown';
}

function tokenBudgets() {
  return loadConfig('token-budgets.json') || {
    charsPerTokenEstimate: 4,
    discovery: { perSkillFrontmatterBytes: 240, aggregateFrontmatterBytes: 4000 },
    eager: { totalChars: 18000, layers: {} },
    priority: [],
    sessionStart: { maxChars: 8000 },
    warnAtPercent: 85,
    hardFail: false,
    __fallback: true,
  };
}

function pipelineGraph() {
  return loadConfig('pipeline-graph.json');
}

function stackMappings() {
  return loadConfig('stack-mappings.json');
}

/**
 * The prescriptive architecture floor for NEW work, per stack. Deliberately a separate
 * file from stack-mappings.json: that one detects what a repo already is, this one
 * records what a new one should be. Merging them would make an observed fact
 * indistinguishable from a recorded decision.
 *
 * Returns null when absent or unparseable, like every other reader here — callers decide
 * whether that is fatal. Treat a null as "no baseline recorded", never as "no constraint".
 */
function architectureBaseline() {
  return loadConfig('architecture-baseline.json');
}

/**
 * The baseline entry governing a stack id from stack-mappings.json detectionOrder.
 * Returns null when nothing covers the id, which is a real answer: it means the stack was
 * added to stack-mappings.json without a corresponding baseline, and the caller should say
 * so rather than falling back to whichever entry happens to be first.
 */
function baselineForStack(stackId) {
  const doc = architectureBaseline();
  if (!doc || !Array.isArray(doc.baselines)) return null;
  return doc.baselines.find(
    (entry) => Array.isArray(entry.appliesToStacks) && entry.appliesToStacks.includes(stackId)
  ) || null;
}

function toolRegistry() {
  return loadConfig('tool-registry.json');
}

function redactionPatterns() {
  return loadConfig('redaction-patterns.json');
}

/**
 * A user-facing plugin option. Claude Code exposes userConfig values as
 * CLAUDE_PLUGIN_OPTION_<UPPER_SNAKE>; an env var of our own always wins so a session
 * can be adjusted without touching the plugin UI.
 */
function option(key, fallback) {
  const upper = String(key).toUpperCase().replace(/[^A-Z0-9]+/g, '_');
  const own = process.env[`ORCHESTRATOR_${upper}`];
  if (own !== undefined && own !== '') return own;
  const plugin = process.env[`CLAUDE_PLUGIN_OPTION_${upper}`];
  if (plugin !== undefined && plugin !== '') return plugin;
  return fallback;
}

function booleanOption(key, fallback) {
  const raw = option(key, undefined);
  if (raw === undefined) return fallback;
  return !['0', 'false', 'off', 'no', 'disabled'].includes(String(raw).toLowerCase());
}

function numberOption(key, fallback) {
  const raw = option(key, undefined);
  if (raw === undefined) return fallback;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/** Only for tests. Configuration is cached for the process lifetime by design. */
function resetCache() {
  cache.clear();
}

module.exports = {
  loadConfig,
  hubConfig,
  orgId,
  tokenBudgets,
  pipelineGraph,
  stackMappings,
  architectureBaseline,
  baselineForStack,
  toolRegistry,
  redactionPatterns,
  option,
  booleanOption,
  numberOption,
  resetCache,
};
