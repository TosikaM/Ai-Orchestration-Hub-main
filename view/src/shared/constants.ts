/**
 * Identifiers and paths that must agree across the extension, and with the runtime
 * plane's files. Anything spelled in more than one place belongs here.
 */

import * as vscode from 'vscode';

/**
 * THE SETTINGS PREFIX. Read this before changing it.
 *
 * A prior version of this extension declared its settings in package.json as
 * `aiorchestrator.*` and read them back with `getConfiguration('aiOrchestrator')` — a
 * capital O — in nine separate call sites. VS Code does not error on a configuration
 * section that does not exist; it returns an empty section, and `get('someKey',
 * fallback)` on an empty section returns the fallback. So every one of those nine reads
 * silently returned the default. Not one user setting in the extension had any effect,
 * the UI showed the settings correctly because the UI reads package.json, and there was
 * no failure anywhere to notice.
 *
 * That was the highest-impact defect in the source material this project was rebuilt
 * from, and it was invisible precisely because the failure mode of a wrong section name
 * is "everything keeps working, at the defaults".
 *
 * The fix is structural rather than a spelling correction: the prefix is one exported
 * constant, every read goes through `settings()` in this file, and package.json spells
 * the same lowercase string. A typo now breaks compilation instead of breaking
 * behaviour quietly.
 */
export const SETTINGS_PREFIX = 'aiorchestrator';

/**
 * Setting keys, relative to SETTINGS_PREFIX. Same argument as above: a key typed at the
 * call site is a key that can drift from package.json without anything failing.
 */
export const SETTINGS = {
  stateHome: 'stateHome',
  refreshOnFileChange: 'refreshOnFileChange',
  pipelineShowCompleted: 'pipeline.showCompleted',
  memoryMaxEntriesPerCategory: 'memory.maxEntriesPerCategory',
  gateReviewConfirmApprove: 'gateReview.confirmApprove',
  dashboardShowTelemetry: 'dashboard.showTelemetry',
} as const;

/**
 * The one and only way this extension reads a user setting. Nothing else in the
 * codebase calls `getConfiguration`, which is what makes the section name impossible to
 * get wrong in a tenth place.
 */
export function settings(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration(SETTINGS_PREFIX);
}

/** Typed read with an explicit fallback, so a missing key is visible at the call site. */
export function setting<T>(key: string, fallback: T): T {
  return settings().get<T>(key, fallback);
}

/** The activity-bar container and the four trees inside it. */
export const VIEW_CONTAINER_ID = 'orchestrator';

export const VIEW_IDS = {
  pipeline: 'orchestrator-pipeline',
  agents: 'orchestrator-agents',
  memory: 'orchestrator-memory',
  repos: 'orchestrator-repos',
} as const;

export const COMMAND_IDS = {
  showDashboard: 'orchestrator.showDashboard',
  refreshViews: 'orchestrator.refreshViews',
  openGateReview: 'orchestrator.openGateReview',
  approveGate: 'orchestrator.approveGate',
  requestChanges: 'orchestrator.requestChanges',
} as const;

/* ------------------------------------------------------------------- state paths */

/**
 * Workspace-relative paths. These are the runtime plane's layout, not this
 * extension's — if one of them changes in `scripts/`, it changes here in the same
 * commit or the trees quietly go empty.
 */
export const WORKSPACE_PATHS = {
  /** Pipeline checkpoints, gate artifacts, gate verdicts, and band files. */
  sessions: 'memory/sessions',
  /** The rendered shared-memory Markdown that syncs to every connected repo. */
  sharedMemory: 'memory/shared',
  /** Vendored agent definitions. Absent in a normal plugin install — see below. */
  vendoredAgents: '.github/agents',
  /** Agent definitions when the workspace IS the hub checkout. */
  hubAgents: 'agents',
  /** Presence of this file is what activates the extension. */
  installState: '.github/orchestrator-install.json',
  repoContext: '.github/orchestrator-context.md',
} as const;

/**
 * Machine-scoped state, outside any repository, so a terminal session, a CI job, and
 * this extension all read the same bytes. Resolution order is the setting, then
 * ORCHESTRATOR_HOME, then ~/.orchestrator — matching `lib/paths.js` and
 * `scripts/_lib.py`, which is the only reason all three agree about where state lives.
 */
export const STATE_HOME_DIR_NAME = '.orchestrator';
export const STATE_HOME_ENV_VAR = 'ORCHESTRATOR_HOME';

export const STATE_PATHS = {
  connectedRepos: 'state/connected-repos.json',
  telemetry: 'telemetry.jsonl',
} as const;

/* ------------------------------------------------------------------ file naming */

/** `<pipelineId>.checkpoint.json` */
export const CHECKPOINT_SUFFIX = '.checkpoint.json';
/** `<pipelineId>.band.json` */
export const BAND_SUFFIX = '.band.json';
/** `<pipelineId>.gate-<phase>.md` — the artifact a human reads. */
export const GATE_ARTIFACT_PATTERN = /^(.+)\.gate-([a-z0-9-]+)\.md$/;

export function gateArtifactName(pipelineId: string, phase: string): string {
  return `${pipelineId}.gate-${phase}.md`;
}

export function gateVerdictName(pipelineId: string, phase: string): string {
  return `${pipelineId}.gate-${phase}.json`;
}

/**
 * Which shared-memory file holds which category. Keyed by filename because that is what
 * a directory listing gives us.
 */
export const MEMORY_FILES: Record<string, { category: string; label: string }> = {
  'anti-patterns.md': { category: 'anti-pattern', label: 'Anti-Patterns' },
  'best-practices.md': { category: 'best-practice', label: 'Best Practices' },
  'tool-chains.md': { category: 'tool-chain', label: 'MCP Tool Chains' },
  'instincts.md': { category: 'instinct', label: 'Instincts (promotion candidates)' },
};

/* ---------------------------------------------------------------------- timing */

/**
 * How long to wait after a file event before refreshing the trees.
 *
 * A single `pipeline.py complete` touches the checkpoint and can touch a gate artifact
 * and a verdict in the same tick, and an atomic write shows up as a create plus a
 * rename. Refreshing on each event means rebuilding four trees three or four times for
 * one logical change, with visible flicker. A quarter of a second is long enough to
 * collapse that burst and short enough that nobody perceives the delay as lag.
 */
export const REFRESH_DEBOUNCE_MS = 250;

/**
 * How many telemetry lines to read from the tail of the ledger. The file is append-only
 * and never rotated by the runtime, so reading all of it would make an optional
 * dashboard section into a real cost on a long-lived machine.
 */
export const TELEMETRY_TAIL_LINES = 500;

/**
 * The timestamp format the runtime plane writes: ISO-8601, seconds precision, `Z`.
 * `Date.prototype.toISOString` emits milliseconds, so it is trimmed to match. Two
 * surfaces writing the same file in two different timestamp formats is the kind of
 * cosmetic inconsistency that later gets mistaken for a bug in whichever one you
 * happen to be debugging.
 */
export function utcNow(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}
