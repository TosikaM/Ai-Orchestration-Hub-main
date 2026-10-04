/**
 * Every interface in the view plane is declared here, and nowhere else.
 *
 * WHY THIS RULE IS WRITTEN DOWN RATHER THAN ASSUMED
 *
 * A prior version of this extension declared `PipelineState` in two files with two
 * different shapes. That is a duplicate-identifier compile error the moment both files
 * are in the same program, and while it was being untangled the two shapes had already
 * drifted: one carried `phases` as an array, the other as a record keyed by phase name.
 * Fixing the compile error meant choosing which of the two the rest of the code had
 * silently been written against, and there was no way to tell from the types alone.
 *
 * So: one file, one declaration per concept, everything else imports from here. If a
 * shape needs a second variant, it gets a second *name* in this file — never a second
 * declaration of the first name somewhere more convenient.
 *
 * WHAT THESE TYPES ARE, AND WHAT THEY ARE NOT
 *
 * They describe files written by the runtime plane — `scripts/pipeline.py`,
 * `scripts/memory.py`, `scripts/cross-repo.py`, and the hook runtime. They are a
 * *reader's* model of those files, so they are deliberately permissive: fields the
 * writer sets conditionally are optional here, and unknown extra fields are ignored
 * rather than rejected. A checkpoint written by a newer pipeline that added a field
 * must still render in an older view; refusing to display it would be a worse failure
 * than showing a row with one column missing.
 */

/* ------------------------------------------------------------------- pipeline */

/**
 * The lifecycle of one phase. These five values are exactly the ones
 * `scripts/pipeline.py` writes; anything else on disk is treated as unknown and
 * rendered with a question mark rather than being coerced into a neighbour.
 */
export type PhaseStatus = 'pending' | 'active' | 'complete' | 'failed' | 'skipped';

/** The two verdicts a human gate can carry. There is no third, and no "maybe". */
export type VerdictKind = 'approved' | 'changes-requested';

export interface PhaseState {
  status: PhaseStatus | string;
  /** Null until the phase reports a score. Absent and null mean the same thing here. */
  score?: number | null;
  attempts?: number;
  humanGate?: boolean;
  /** The score this phase must reach. Zero means the phase is not score-gated. */
  gateThreshold?: number;
  /** Phase names declared to run alongside this one, straight from the DAG config. */
  parallelWith?: string[];
  /** True once an artifact exists for a human to read. The Stop hook keys off this. */
  gateArtifactWritten?: boolean;
  gateArtifactAt?: string;
  /** The checkpoint's mirror of the verdict. The verdict FILE is the authority. */
  verdict?: VerdictKind | string;
  verdictNote?: string;
  completedAt?: string;
}

export interface PipelineCheckpoint {
  pipelineId: string;
  requirement?: string;
  repo?: string;
  startedAt?: string;
  updatedAt?: string;
  status?: string;
  currentPhase?: string;
  /** How many context compactions this pipeline has survived. */
  compactions?: number;
  phases: Record<string, PhaseState>;
  /** Absolute path of the checkpoint file, filled in by the reader, not by the writer. */
  sourceFile?: string;
}

/**
 * `memory/sessions/<pipelineId>.gate-<phase>.json`, written by `pipeline.py approve`
 * and by this extension's gate panel. Byte-identical from either surface except for
 * `decidedBy`, which records which one of them wrote it.
 */
export interface GateVerdict {
  pipelineId: string;
  phase: string;
  verdict: VerdictKind;
  note: string;
  decidedAt: string;
  decidedBy: string;
}

/**
 * A gate artifact with no verdict beside it — the state that blocks the Stop hook and
 * therefore the state a human has to resolve. Derived by the reader from a directory
 * listing; nothing on disk has this shape.
 */
export interface PendingGate {
  pipelineId: string;
  phase: string;
  /** Absolute path to the `.gate-<phase>.md` artifact. */
  artifactPath: string;
  /** Absolute path the verdict will occupy. It does not exist yet, by definition. */
  verdictPath: string;
}

/* ------------------------------------------------------------------ cross-repo */

export interface ConnectedRepo {
  name: string;
  path: string;
  techStack?: string;
  role?: string;
  connectedDate?: string;
  lastSync?: string;
  contextFile?: string;
  status?: string;
}

/**
 * A named set of repos with an execution order. The order is dependency-first —
 * producers before consumers — which is why it is stored separately from `repos`
 * rather than inferred from it.
 */
export interface RepoGroup {
  name: string;
  repos: string[];
  executionOrder?: string[];
}

export interface RepoRegistry {
  version?: number;
  repos: ConnectedRepo[];
  groups?: RepoGroup[];
  /** Name of the active repo, or null when no repo has been switched to. */
  active?: string | null;
  activeGroup?: string | null;
}

/** One repo's completed leg of a contract band. */
export interface BandRepoCompletion {
  repo: string;
  changes?: string[];
  /** Interfaces this repo now exposes, in `Name: shape` form. */
  exposedInterfaces?: string[];
  buildStatus?: string;
  notes?: string;
  completedAt?: string;
}

/**
 * `memory/sessions/<pipelineId>.band.json` — a cross-repo pipeline in flight, with the
 * contracts each finished repo exposed. Downstream repos must consume those names as
 * written, which is the whole reason the band records them.
 */
export interface BandState {
  pipelineId: string;
  requirement?: string;
  executionOrder: string[];
  completedRepos: BandRepoCompletion[];
  /** Contract name to shape. Flattened from `exposedInterfaces` by `cross-repo.py`. */
  sharedContracts?: Record<string, string>;
  remainingRepos: string[];
  pipelineState?: string;
  startedAt?: string;
}

/* --------------------------------------------------------------------- memory */

export type MemoryCategory = 'anti-pattern' | 'best-practice' | 'tool-chain' | 'instinct';

/**
 * One promoted entry, parsed back out of the rendered Markdown in `memory/shared/`.
 *
 * The store is `memory/index/entries.json`; these files are a rendering of it. The view
 * reads the rendering rather than the index on purpose — the rendering is what syncs to
 * consumer repositories, so it is the copy that exists in a repo the hub is not checked
 * out beside. `confidence` is the effective value after decay; `recordedConfidence` is
 * the stored one, and showing both is how "why did this drop" has a visible answer.
 */
export interface MemoryEntry {
  title: string;
  category: MemoryCategory;
  confidence: number | null;
  recordedConfidence: number | null;
  seenInRepos: string[];
  context: string;
  resolution: string;
  appliesTo: string;
  firstObserved: string;
  lastReinforced: string;
  /** Absolute path of the Markdown file this entry was parsed out of. */
  sourceFile: string;
}

/* --------------------------------------------------------------------- agents */

/**
 * The frontmatter of an `*.agent.md` file, plus where it was found. `tools` is the
 * declared least-privilege surface; an agent with no `tools` line has not declared one,
 * which is a different and more interesting fact than declaring an empty list — hence
 * the optional field rather than a defaulted empty array.
 */
export interface AgentDefinition {
  name: string;
  description: string;
  tools?: string[];
  model?: string;
  filePath: string;
  /** True when the body carries the Prompt Defense Baseline every agent is meant to. */
  hasPromptDefense: boolean;
}

/* ------------------------------------------------------------------ telemetry */

/**
 * One line of `~/.orchestrator/telemetry.jsonl`. Local-only, off unless
 * ORCHESTRATOR_TELEMETRY is on, and it records counts and durations rather than content.
 * `prev` is the sha256 of the previous raw line, which is what makes a deletion in the
 * middle of the ledger detectable.
 */
export interface TelemetryRecord {
  event: string;
  repo?: string;
  sessionId?: string;
  pipelinePhase?: string | null;
  toolCounts?: Record<string, number>;
  hookProfile?: string;
  prev?: string;
  at?: string;
}
