'use strict';
/**
 * Whether a given hook should run at all.
 *
 * Resolution, most specific first:
 *   1. ORCHESTRATOR_HOOKS_ENABLED=false            — the global kill switch
 *   2. ORCHESTRATOR_DISABLED_HOOKS=<csv of ids>    — surgical, per session
 *   3. The hook's declared profiles vs. the active profile
 *
 * Two rules that are load-bearing:
 *
 * An invalid profile falls back to `standard`, never to off. A typo in a config value
 * must not silently disable every gate in the system — that is the failure mode where
 * a guard looks installed and is not.
 *
 * Some hooks ignore the profile system entirely. A profile is a convenience dial for
 * friction; it is not a security dial. Prompt defense and the memory redaction guard
 * are exempt because turning them off by choosing a lighter profile would be a footgun
 * disguised as a preference. The global kill switch still works — one obvious switch,
 * not a hidden one.
 */

const fs = require('fs');
const path = require('path');

const VALID_PROFILES = ['minimal', 'standard', 'strict'];
const DEFAULT_PROFILE = 'standard';

let registryCache = null;

function registry() {
  if (registryCache) return registryCache;
  try {
    registryCache = JSON.parse(fs.readFileSync(path.join(__dirname, 'registry.json'), 'utf8'));
  } catch {
    registryCache = { hooks: {}, dispatchers: {}, profileExempt: [] };
  }
  return registryCache;
}

function hooksEnabled() {
  const raw = process.env.ORCHESTRATOR_HOOKS_ENABLED
    ?? process.env.CLAUDE_PLUGIN_OPTION_HOOKS_ENABLED;
  if (raw === undefined || raw === '') return true;
  return !['0', 'false', 'off', 'no', 'disabled'].includes(String(raw).toLowerCase());
}

function activeProfile() {
  const raw = String(
    process.env.ORCHESTRATOR_HOOK_PROFILE
    || process.env.CLAUDE_PLUGIN_OPTION_HOOK_PROFILE
    || DEFAULT_PROFILE,
  ).toLowerCase();
  return VALID_PROFILES.includes(raw) ? raw : DEFAULT_PROFILE;
}

function disabledIds() {
  const raw = process.env.ORCHESTRATOR_DISABLED_HOOKS || '';
  return new Set(raw.split(/[;,]/).map((s) => s.trim()).filter(Boolean));
}

function isProfileExempt(hookId) {
  return (registry().profileExempt || []).includes(hookId);
}

function hookMeta(hookId) {
  return (registry().hooks || {})[hookId] || null;
}

function dispatcherMeta(dispatcherId) {
  return (registry().dispatchers || {})[dispatcherId] || null;
}

function isHookEnabled(hookId) {
  if (!hooksEnabled()) return false;
  if (disabledIds().has(hookId)) return false;
  if (isProfileExempt(hookId)) return true;
  const meta = hookMeta(hookId);
  if (!meta) return false;
  return (meta.profiles || []).includes(activeProfile());
}

module.exports = {
  VALID_PROFILES,
  DEFAULT_PROFILE,
  registry,
  hooksEnabled,
  activeProfile,
  disabledIds,
  isProfileExempt,
  hookMeta,
  dispatcherMeta,
  isHookEnabled,
};
