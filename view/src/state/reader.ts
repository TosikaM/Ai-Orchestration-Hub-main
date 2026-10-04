/**
 * The read side of the view plane. Nothing in this file changes anything on disk.
 *
 * WHY EVERY READ IS DEFENSIVE
 *
 * These files are written by another process — `scripts/pipeline.py`, `scripts/memory.py`,
 * the hook runtime — while this extension is running. A checkpoint can be caught
 * mid-rename, a Markdown file can be half-synced, a JSONL ledger can end in a partial
 * line, and a hand-edited registry can be valid JSON of entirely the wrong shape. A
 * `TreeDataProvider` that throws on any of those does not fail politely: VS Code marks
 * the view as errored and it stays errored until the window is reloaded, so one bad byte
 * in one session file takes out the pipeline tree for the rest of the day.
 *
 * So every read here yields `null` or an empty array and logs one line to the output
 * channel. The tree then renders "nothing to show" instead of a red box, which is both
 * survivable and honest: an empty tree with a logged reason beats a plausible-looking
 * tree assembled from a file we could not actually parse.
 *
 * A MISSING FILE IS NOT A WARNING
 *
 * Most of these paths are absent in the ordinary case — a repo with no pipeline running
 * has no `memory/sessions/`, and a machine with telemetry off has no ledger. Warning on
 * absence would fill the channel with noise and train the reader to ignore it, so
 * absence is silent and only a file that exists and will not parse gets a line.
 *
 * VALIDATION IS DELIBERATELY SHALLOW
 *
 * Each guard checks the fields this extension actually reads and nothing else. Full
 * schema validation would reject a checkpoint written by a newer pipeline version that
 * added a field, and refusing to display work in flight because it carries one unknown
 * key is a worse outcome than rendering a row with a column missing.
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

import {
  BAND_SUFFIX,
  CHECKPOINT_SUFFIX,
  GATE_ARTIFACT_PATTERN,
  MEMORY_FILES,
  STATE_HOME_DIR_NAME,
  STATE_HOME_ENV_VAR,
  STATE_PATHS,
  SETTINGS,
  TELEMETRY_TAIL_LINES,
  WORKSPACE_PATHS,
  gateArtifactName,
  gateVerdictName,
  setting,
} from '../shared/constants';
import {
  AgentDefinition,
  BandState,
  GateVerdict,
  MemoryCategory,
  MemoryEntry,
  PendingGate,
  PipelineCheckpoint,
  RepoRegistry,
  TelemetryRecord,
  VerdictKind,
} from '../shared/types';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

export class StateReader {
  private readonly workspaceRoot: string | undefined;
  private readonly output: vscode.OutputChannel;

  constructor(workspaceRoot: string | undefined, output: vscode.OutputChannel) {
    this.workspaceRoot = workspaceRoot;
    this.output = output;
  }

  /* ------------------------------------------------------------ path resolution */

  /** True when there is a folder open at all. Every tree renders a hint when there is not. */
  public hasWorkspace(): boolean {
    return typeof this.workspaceRoot === 'string' && this.workspaceRoot.length > 0;
  }

  public workspacePath(...parts: string[]): string | null {
    if (!this.workspaceRoot) {
      return null;
    }
    return path.join(this.workspaceRoot, ...parts);
  }

  /**
   * Machine-scoped state. The order — setting, then environment variable, then the
   * home directory — is the same order `lib/paths.js` and `scripts/_lib.py` use. An
   * explicit override has to beat inference, because a developer running against a
   * second state tree must be able to say so.
   */
  public stateHome(): string {
    const configured = setting<string>(SETTINGS.stateHome, '').trim();
    if (configured) {
      return configured;
    }
    const fromEnv = process.env[STATE_HOME_ENV_VAR];
    if (fromEnv && fromEnv.trim()) {
      return fromEnv.trim();
    }
    return path.join(os.homedir(), STATE_HOME_DIR_NAME);
  }

  public statePath(...parts: string[]): string {
    return path.join(this.stateHome(), ...parts);
  }

  public sessionsDir(): string | null {
    return this.workspacePath(WORKSPACE_PATHS.sessions);
  }

  /* --------------------------------------------------------------- primitives */

  public warn(message: string): void {
    this.output.appendLine(`[warn] ${message}`);
  }

  /** Reads a text file. Absent is `null` and silent; unreadable is `null` and logged. */
  public readText(file: string): string | null {
    if (!fs.existsSync(file)) {
      return null;
    }
    try {
      return fs.readFileSync(file, 'utf8');
    } catch (error) {
      this.warn(`could not read ${file}: ${String(error)}`);
      return null;
    }
  }

  /** Parses JSON through a shape guard. A file of the wrong shape is a logged null. */
  private readJson<T>(file: string, guard: (value: unknown) => value is T): T | null {
    const raw = this.readText(file);
    if (raw === null) {
      return null;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      this.warn(`invalid JSON in ${file}: ${String(error)}`);
      return null;
    }
    if (!guard(parsed)) {
      this.warn(`unexpected shape in ${file} — ignoring it rather than guessing at it`);
      return null;
    }
    return parsed;
  }

  /** A directory listing that yields an empty array instead of throwing. */
  private listDir(dir: string | null): string[] {
    if (!dir || !fs.existsSync(dir)) {
      return [];
    }
    try {
      return fs.readdirSync(dir);
    } catch (error) {
      this.warn(`could not list ${dir}: ${String(error)}`);
      return [];
    }
  }

  /* ---------------------------------------------------------------- pipelines */

  public readPipelines(): PipelineCheckpoint[] {
    const dir = this.sessionsDir();
    const checkpoints: PipelineCheckpoint[] = [];
    for (const name of this.listDir(dir).sort()) {
      if (!name.endsWith(CHECKPOINT_SUFFIX) || !dir) {
        continue;
      }
      const file = path.join(dir, name);
      const checkpoint = this.readJson(file, isPipelineCheckpoint);
      if (checkpoint) {
        checkpoint.sourceFile = file;
        checkpoints.push(checkpoint);
      }
    }
    // Newest first: a session that has just moved is the one somebody is looking for.
    checkpoints.sort((a, b) => asString(b.updatedAt).localeCompare(asString(a.updatedAt)));
    return checkpoints;
  }

  public readPipeline(pipelineId: string): PipelineCheckpoint | null {
    const dir = this.sessionsDir();
    if (!dir) {
      return null;
    }
    const file = path.join(dir, `${pipelineId}${CHECKPOINT_SUFFIX}`);
    const checkpoint = this.readJson(file, isPipelineCheckpoint);
    if (checkpoint) {
      checkpoint.sourceFile = file;
    }
    return checkpoint;
  }

  /**
   * The verdict file, which is the authority. The checkpoint carries a mirror of the
   * same value, but the two can legitimately disagree: this extension writes the verdict
   * file and cannot update the checkpoint, so a gate approved from the panel shows a
   * verdict here and no mirror there until the next `pipeline.py` run reconciles it.
   * Readers should prefer this.
   */
  public readGateVerdict(pipelineId: string, phase: string): GateVerdict | null {
    const dir = this.sessionsDir();
    if (!dir) {
      return null;
    }
    return this.readJson(path.join(dir, gateVerdictName(pipelineId, phase)), isGateVerdict);
  }

  /**
   * Gate artifacts with no verdict beside them. This is exactly the set that blocks the
   * Stop hook, computed the same way the hook computes it — from the directory listing,
   * not from the checkpoint — so the two surfaces cannot drift.
   */
  public readPendingGates(): PendingGate[] {
    const dir = this.sessionsDir();
    const names = this.listDir(dir);
    if (!dir || names.length === 0) {
      return [];
    }
    const present = new Set(names);
    const pending: PendingGate[] = [];
    for (const name of names.sort()) {
      const match = GATE_ARTIFACT_PATTERN.exec(name);
      if (!match) {
        continue;
      }
      const [, pipelineId, phase] = match;
      const verdictFile = gateVerdictName(pipelineId, phase);
      if (present.has(verdictFile)) {
        const verdict = this.readJson(path.join(dir, verdictFile), isGateVerdict);
        // A recorded "changes-requested" is an answered gate. The agent should act on
        // it rather than wait, so it is not pending for our purposes either.
        if (verdict) {
          continue;
        }
      }
      pending.push({
        pipelineId,
        phase,
        artifactPath: path.join(dir, name),
        verdictPath: path.join(dir, verdictFile),
      });
    }
    return pending;
  }

  /** The Markdown a human is being asked to approve. Rendered escaped, never as HTML. */
  public readGateArtifact(pipelineId: string, phase: string): string | null {
    const dir = this.sessionsDir();
    if (!dir) {
      return null;
    }
    return this.readText(path.join(dir, gateArtifactName(pipelineId, phase)));
  }

  public readBand(pipelineId: string): BandState | null {
    const dir = this.sessionsDir();
    if (!dir) {
      return null;
    }
    return this.readJson(path.join(dir, `${pipelineId}${BAND_SUFFIX}`), isBandState);
  }

  /* --------------------------------------------------------------------- repos */

  public readRegistry(): RepoRegistry | null {
    return this.readJson(this.statePath(...STATE_PATHS.connectedRepos.split('/')), isRepoRegistry);
  }

  /* -------------------------------------------------------------------- agents */

  /**
   * Agent definitions.
   *
   * Under the plugin distribution model the agents live in the plugin, not in the
   * consumer repository, so `.github/agents/` exists only where somebody ran
   * `connect-repo.ps1 -Vendor` for an offline or audit requirement. We look there first
   * because a vendored copy is the one that repo is actually running, and fall back to
   * `agents/` for the case where the open folder is the hub checkout itself. When
   * neither exists the tree says so rather than implying the repo has no agents — it
   * has ten, and they are inside the plugin where this extension cannot see them.
   */
  public readAgents(): { agents: AgentDefinition[]; source: string | null } {
    for (const relative of [WORKSPACE_PATHS.vendoredAgents, WORKSPACE_PATHS.hubAgents]) {
      const dir = this.workspacePath(relative);
      const names = this.listDir(dir).filter((name) => name.endsWith('.agent.md'));
      if (!dir || names.length === 0) {
        continue;
      }
      const agents: AgentDefinition[] = [];
      for (const name of names.sort()) {
        const file = path.join(dir, name);
        const body = this.readText(file);
        if (body === null) {
          continue;
        }
        const meta = parseFrontmatter(body);
        if (!meta) {
          this.warn(`${file}: no leading frontmatter block — skipped`);
          continue;
        }
        agents.push({
          name: meta.name ?? path.basename(name, '.agent.md'),
          description: meta.description ?? '',
          tools: meta.tools ? splitList(meta.tools) : undefined,
          model: meta.model,
          filePath: file,
          hasPromptDefense: body.includes('## Prompt Defense Baseline'),
        });
      }
      if (agents.length > 0) {
        return { agents, source: relative };
      }
    }
    return { agents: [], source: null };
  }

  /* -------------------------------------------------------------------- memory */

  /**
   * Shared memory, parsed out of the rendered Markdown under `memory/shared/`.
   *
   * The parser is tied to the exact block `scripts/memory.py` renders — an `### title`
   * followed by `- **Key**: value` lines. That coupling is deliberate and worth stating:
   * it is a parser for one known writer, not a Markdown reader, and it will produce
   * nothing at all if the renderer changes shape. Producing nothing is the right failure
   * here, because a half-parsed learning shown as fact is worse than an empty tree.
   */
  public readMemory(): MemoryEntry[] {
    const dir = this.workspacePath(WORKSPACE_PATHS.sharedMemory);
    if (!dir) {
      return [];
    }
    const entries: MemoryEntry[] = [];
    for (const [filename, meta] of Object.entries(MEMORY_FILES)) {
      const file = path.join(dir, filename);
      const body = this.readText(file);
      if (body === null) {
        continue;
      }
      entries.push(...parseMemoryFile(body, meta.category as MemoryCategory, file));
    }
    return entries;
  }

  /* ----------------------------------------------------------------- telemetry */

  /**
   * The tail of the local telemetry ledger. Absent means telemetry is off, which is the
   * default and is not an error — the dashboard says "off" rather than "0 events",
   * because those are different facts and only one of them is true.
   */
  public readTelemetry(limit: number = TELEMETRY_TAIL_LINES): TelemetryRecord[] {
    const file = this.statePath(STATE_PATHS.telemetry);
    const raw = this.readText(file);
    if (raw === null) {
      return [];
    }
    const lines = raw.split('\n').filter((line) => line.trim().length > 0);
    const records: TelemetryRecord[] = [];
    for (const line of lines.slice(-limit)) {
      try {
        const parsed: unknown = JSON.parse(line);
        if (isRecord(parsed) && typeof parsed.event === 'string') {
          // The guard above already establishes the one required field. TypeScript
          // still refuses a direct assertion from Record<string, unknown>, because
          // the two types do not structurally overlap enough for it; every other
          // field on TelemetryRecord is optional, so widening through unknown is
          // exactly as safe as the guard and no more.
          records.push(parsed as unknown as TelemetryRecord);
        }
      } catch {
        // A ledger is append-only and can be caught mid-append, so a trailing partial
        // line is expected rather than exceptional. Skip it without a warning.
        continue;
      }
    }
    return records;
  }

  /** True when this workspace has been connected — the same file that activates us. */
  public isConnected(): boolean {
    const file = this.workspacePath(WORKSPACE_PATHS.installState);
    return file !== null && fs.existsSync(file);
  }
}

/* ================================================================ shape guards */

function isPipelineCheckpoint(value: unknown): value is PipelineCheckpoint {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.pipelineId === 'string' && isRecord(value.phases);
}

function isGateVerdict(value: unknown): value is GateVerdict {
  if (!isRecord(value)) {
    return false;
  }
  const verdict = value.verdict;
  return verdict === 'approved' || verdict === 'changes-requested';
}

function isRepoRegistry(value: unknown): value is RepoRegistry {
  if (!isRecord(value)) {
    return false;
  }
  return Array.isArray(value.repos);
}

function isBandState(value: unknown): value is BandState {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.pipelineId === 'string'
    && Array.isArray(value.executionOrder)
    && Array.isArray(value.completedRepos)
    && Array.isArray(value.remainingRepos)
  );
}

/* ================================================================== parsing */

/**
 * The frontmatter these files actually carry: a leading `---` block of flat
 * `key: value` scalars. It is not a YAML parser and does not pretend to be one — no
 * nesting, no block scalars, no anchors. Shipping a YAML dependency to read six keys
 * would put a runtime dependency in a plane whose whole claim is that it has none.
 * A file using a construct this cannot read yields the keys it could read; the caller
 * falls back to the filename for the name, which is the field that matters.
 */
export function parseFrontmatter(body: string): Record<string, string> | null {
  // A leading byte-order mark makes `startsWith('---')` false and the whole block
  // invisible, which presents as "this agent has no frontmatter" for a file that plainly
  // does. Strip it before anything else looks at the text.
  const normalized = body.charCodeAt(0) === 0xFEFF ? body.slice(1) : body;
  if (!normalized.startsWith('---')) {
    return null;
  }
  const end = normalized.indexOf('\n---', 3);
  if (end === -1) {
    return null;
  }
  const block = normalized.slice(normalized.indexOf('\n', 3) + 1, end);
  const meta: Record<string, string> = {};
  for (const line of block.split('\n')) {
    const match = /^([A-Za-z][\w-]*)\s*:\s*(.*)$/.exec(line);
    if (!match) {
      continue;
    }
    const [, key, rawValue] = match;
    meta[key] = rawValue.trim().replace(/^["'](.*)["']$/, '$1');
  }
  return meta;
}

/** `Read, Grep, Glob` and `[Read, Grep]` both appear in the wild. Accept both. */
export function splitList(value: string): string[] {
  return value
    .replace(/^\[(.*)\]$/, '$1')
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

/**
 * Parse one rendered shared-memory file into entries. Only the fields the tree shows
 * are extracted; a line the renderer added that we do not recognise is ignored rather
 * than treated as a parse failure.
 */
export function parseMemoryFile(
  body: string,
  category: MemoryCategory,
  sourceFile: string,
): MemoryEntry[] {
  // Split on the entry headings rather than walking the file with a running "current
  // entry" variable. One block per entry is both simpler to read and impossible to get
  // wrong at the boundaries, which is where a line-at-a-time parser usually breaks.
  const blocks = body.split(/^###[ \t]+/m).slice(1);
  const entries: MemoryEntry[] = [];

  for (const block of blocks) {
    const lines = block.split('\n');
    const title = (lines.shift() ?? '').trim();
    if (!title) {
      continue;
    }
    const entry: MemoryEntry = {
      title,
      category,
      confidence: null,
      recordedConfidence: null,
      seenInRepos: [],
      context: '',
      resolution: '',
      appliesTo: 'all',
      firstObserved: '',
      lastReinforced: '',
      sourceFile,
    };

    for (const line of lines) {
      const field = /^-\s+\*\*([^*]+)\*\*:\s*(.*)$/.exec(line);
      if (!field) {
        continue;
      }
      const key = field[1].trim().toLowerCase();
      const value = field[2].trim();

      if (key === 'confidence') {
        const numbers = /([0-9]*\.?[0-9]+)(?:\s*\(recorded\s*([0-9]*\.?[0-9]+)\))?/.exec(value);
        if (numbers) {
          entry.confidence = Number.parseFloat(numbers[1]);
          entry.recordedConfidence = numbers[2] === undefined
            ? entry.confidence
            : Number.parseFloat(numbers[2]);
        }
      } else if (key === 'seen in') {
        entry.seenInRepos = value.split(',').map((item) => item.trim()).filter(Boolean);
      } else if (key === 'context') {
        entry.context = value;
      } else if (key === 'resolution') {
        entry.resolution = value;
      } else if (key === 'applies to') {
        entry.appliesTo = value || 'all';
      } else if (key === 'first observed') {
        // Rendered as `<iso> · **Last reinforced**: <iso>` on a single line.
        const both = /^(\S+)(?:\s*·\s*\*\*Last reinforced\*\*:\s*(\S+))?/.exec(value);
        if (both) {
          entry.firstObserved = both[1];
          entry.lastReinforced = both[2] ?? '';
        }
      } else if (key === 'last reinforced') {
        entry.lastReinforced = value;
      }
    }
    entries.push(entry);
  }
  return entries;
}

/**
 * Narrow a loose verdict string to the two values the protocol defines. The checkpoint
 * mirror is typed as a plain string on purpose, because a hand-edited checkpoint can
 * contain anything; this is where that possibility stops.
 */
export function toVerdictKind(value: string | undefined): VerdictKind | null {
  return value === 'approved' || value === 'changes-requested' ? value : null;
}
