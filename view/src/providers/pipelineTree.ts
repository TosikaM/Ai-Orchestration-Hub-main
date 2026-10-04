/**
 * The pipeline tree: every phase of every checkpoint in this workspace, at a glance.
 *
 * WHY THIS VIEW EARNS ITS KEEP
 *
 * The pipeline is a DAG. `review` and `test` are siblings that run at the same time,
 * `deploy` waits for both, phases carry scores against thresholds, and two of them stop
 * dead until a human writes a verdict. A chat transcript renders all of that as prose
 * spread over forty turns, and the question people actually have — "what is running,
 * what is blocked, and on whom" — is answered by scrolling and reconstructing. A tree
 * answers it by existing. That is one of the three reasons the view plane was kept when
 * the rest of the extension was deleted.
 *
 * WHERE THE TRUTH LIVES WHEN TWO FILES DISAGREE
 *
 * A phase's verdict appears in two places: mirrored into the checkpoint by
 * `scripts/pipeline.py`, and standing alone in `<id>.gate-<phase>.json`. The verdict
 * FILE is the authority, because it is the file the Stop hook keys off and the only one
 * this extension is permitted to write. A gate approved from the panel therefore shows a
 * verdict here before the checkpoint mirror catches up on the next `pipeline.py` run,
 * and the tree labels that state rather than hiding it.
 */

import * as path from 'path';
import * as vscode from 'vscode';

import { COMMAND_IDS, SETTINGS, setting } from '../shared/constants';
import { StateReader, toVerdictKind } from '../state/reader';
import {
  BandState,
  GateVerdict,
  PhaseState,
  PipelineCheckpoint,
} from '../shared/types';

/** The status marks `scripts/pipeline.py status` prints, so both surfaces read alike. */
const STATUS_MARKS: Record<string, string> = {
  complete: '[x]',
  active: '[>]',
  failed: '[!]',
  pending: '[ ]',
  skipped: '[-]',
};

const STATUS_ICONS: Record<string, string> = {
  complete: 'pass-filled',
  active: 'play-circle',
  failed: 'error',
  pending: 'circle-outline',
  skipped: 'circle-slash',
};

type NodeKind = 'pipeline' | 'phase' | 'gate' | 'band' | 'contract' | 'note';

export class PipelineNode extends vscode.TreeItem {
  constructor(
    public readonly kind: NodeKind,
    label: string,
    collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly pipelineId?: string,
    public readonly phase?: string,
  ) {
    super(label, collapsibleState);
  }
}

export class PipelineTreeProvider implements vscode.TreeDataProvider<PipelineNode> {
  private readonly changed = new vscode.EventEmitter<PipelineNode | undefined>();
  public readonly onDidChangeTreeData: vscode.Event<PipelineNode | undefined> = this.changed.event;

  constructor(private readonly reader: StateReader) {}

  public refresh(): void {
    this.changed.fire(undefined);
  }

  public getTreeItem(element: PipelineNode): vscode.TreeItem {
    return element;
  }

  public getChildren(element?: PipelineNode): PipelineNode[] {
    if (!element) {
      return this.rootNodes();
    }
    if (element.kind === 'pipeline' && element.pipelineId) {
      return this.pipelineChildren(element.pipelineId);
    }
    if (element.kind === 'band' && element.pipelineId) {
      return this.bandChildren(element.pipelineId);
    }
    return [];
  }

  /* ------------------------------------------------------------------- levels */

  private rootNodes(): PipelineNode[] {
    if (!this.reader.hasWorkspace()) {
      return [note('Open a folder to see its pipelines.')];
    }
    const showCompleted = setting<boolean>(SETTINGS.pipelineShowCompleted, true);
    const checkpoints = this.reader.readPipelines().filter(
      (checkpoint) => showCompleted || isInFlight(checkpoint),
    );

    if (checkpoints.length === 0) {
      const hint = this.reader.isConnected()
        ? 'No pipelines in this workspace. Start one with /pipeline or `python scripts/pipeline.py start "..."`.'
        : 'This repository is not connected. Run /orchestrator-init, or scripts/connect-repo.ps1.';
      return [note(hint)];
    }

    return checkpoints.map((checkpoint) => {
      const node = new PipelineNode(
        'pipeline',
        checkpoint.pipelineId,
        vscode.TreeItemCollapsibleState.Expanded,
        checkpoint.pipelineId,
      );
      const blocked = this.blockedPhases(checkpoint);
      node.description = summarize(checkpoint, blocked.length);
      node.tooltip = new vscode.MarkdownString(pipelineTooltip(checkpoint));
      node.iconPath = new vscode.ThemeIcon(
        blocked.length > 0 ? 'shield' : isInFlight(checkpoint) ? 'debug-start' : 'check-all',
      );
      node.contextValue = 'orchestrator.pipeline';
      if (checkpoint.sourceFile) {
        node.resourceUri = vscode.Uri.file(checkpoint.sourceFile);
      }
      return node;
    });
  }

  private pipelineChildren(pipelineId: string): PipelineNode[] {
    const checkpoint = this.reader.readPipeline(pipelineId);
    if (!checkpoint) {
      return [note('The checkpoint for this pipeline is gone or unreadable.')];
    }

    const nodes: PipelineNode[] = [];
    // Insertion order in the checkpoint follows the DAG config, so iterating the record
    // gives the phases in graph order without this file needing its own copy of the DAG.
    for (const [name, phase] of Object.entries(checkpoint.phases)) {
      nodes.push(this.phaseNode(checkpoint, name, phase));
    }

    const band = this.reader.readBand(pipelineId);
    if (band) {
      const bandNode = new PipelineNode(
        'band',
        'cross-repo band',
        vscode.TreeItemCollapsibleState.Collapsed,
        pipelineId,
      );
      bandNode.description = `${band.completedRepos.length}/${band.executionOrder.length} repos`;
      bandNode.iconPath = new vscode.ThemeIcon('repo-forked');
      bandNode.tooltip = new vscode.MarkdownString(
        'Repos are finished in dependency order. Contracts a finished repo exposes must be '
        + 'consumed downstream **as named** — renaming one locally is how a band produces '
        + 'repositories that each compile and do not talk to each other.',
      );
      nodes.push(bandNode);
    }
    return nodes;
  }

  private phaseNode(
    checkpoint: PipelineCheckpoint,
    name: string,
    phase: PhaseState,
  ): PipelineNode {
    const verdictFile = phase.humanGate
      ? this.reader.readGateVerdict(checkpoint.pipelineId, name)
      : null;
    const status = effectiveStatus(phase, verdictFile);
    const node = new PipelineNode(
      'phase',
      `${STATUS_MARKS[status] ?? '[?]'} ${name}`,
      vscode.TreeItemCollapsibleState.None,
      checkpoint.pipelineId,
      name,
    );
    node.description = phaseDescription(phase, status, verdictFile);
    node.tooltip = new vscode.MarkdownString(phaseTooltip(name, phase, verdictFile));
    node.iconPath = new vscode.ThemeIcon(STATUS_ICONS[status] ?? 'question');

    // An unanswered human gate is the one row in this tree that is a call to action, so
    // it is the one row that is clickable. Everything else here is information.
    if (isAwaitingHuman(phase, verdictFile)) {
      node.contextValue = 'orchestrator.pendingGate';
      node.command = {
        command: COMMAND_IDS.openGateReview,
        title: 'Open Gate Review',
        arguments: [{ pipelineId: checkpoint.pipelineId, phase: name }],
      };
    } else {
      node.contextValue = 'orchestrator.phase';
    }
    return node;
  }

  private bandChildren(pipelineId: string): PipelineNode[] {
    const band = this.reader.readBand(pipelineId);
    if (!band) {
      return [note('The band file is gone or unreadable.')];
    }
    const nodes: PipelineNode[] = [];
    for (const done of band.completedRepos) {
      const item = new PipelineNode(
        'contract',
        `[x] ${done.repo}`,
        vscode.TreeItemCollapsibleState.None,
        pipelineId,
      );
      item.description = `build ${done.buildStatus ?? '?'}`;
      item.iconPath = new vscode.ThemeIcon('pass-filled');
      const exposes = done.exposedInterfaces ?? [];
      item.tooltip = new vscode.MarkdownString(
        exposes.length > 0
          ? `Exposes, to be consumed as named:\n\n${exposes.map((line) => `- \`${line}\``).join('\n')}`
          : 'This repo recorded no exposed interfaces.',
      );
      nodes.push(item);
    }
    for (const pending of band.remainingRepos) {
      const item = new PipelineNode(
        'contract',
        `[ ] ${pending}`,
        vscode.TreeItemCollapsibleState.None,
        pipelineId,
      );
      item.iconPath = new vscode.ThemeIcon('circle-outline');
      nodes.push(item);
    }
    nodes.push(...contractNodes(band, pipelineId));
    return nodes;
  }

  /** Phases whose artifact is written and whose verdict is still missing. */
  private blockedPhases(checkpoint: PipelineCheckpoint): string[] {
    const blocked: string[] = [];
    for (const [name, phase] of Object.entries(checkpoint.phases)) {
      const verdict = phase.humanGate
        ? this.reader.readGateVerdict(checkpoint.pipelineId, name)
        : null;
      if (isAwaitingHuman(phase, verdict)) {
        blocked.push(name);
      }
    }
    return blocked;
  }
}

/* ============================================================ pure helpers */

function note(message: string): PipelineNode {
  const item = new PipelineNode('note', message, vscode.TreeItemCollapsibleState.None);
  item.iconPath = new vscode.ThemeIcon('info');
  return item;
}

function isInFlight(checkpoint: PipelineCheckpoint): boolean {
  const status = checkpoint.status ?? 'active';
  return status !== 'complete' && status !== 'abandoned';
}

/**
 * The verdict file wins over the checkpoint mirror. They agree in every case except the
 * one this extension creates: a verdict written from the gate panel, before any
 * `pipeline.py` command has run to fold it back into the checkpoint.
 */
function effectiveStatus(phase: PhaseState, verdict: GateVerdict | null): string {
  if (verdict?.verdict === 'approved' && phase.status !== 'complete') {
    return 'complete';
  }
  if (verdict?.verdict === 'changes-requested' && phase.status !== 'failed') {
    return 'failed';
  }
  return typeof phase.status === 'string' ? phase.status : 'pending';
}

function isAwaitingHuman(phase: PhaseState, verdict: GateVerdict | null): boolean {
  return Boolean(phase.gateArtifactWritten) && verdict === null && !toVerdictKind(phase.verdict);
}

function phaseDescription(
  phase: PhaseState,
  status: string,
  verdict: GateVerdict | null,
): string {
  const parts: string[] = [status];

  if (typeof phase.score === 'number') {
    const threshold = phase.gateThreshold ?? 0;
    parts.push(`score ${phase.score}/${threshold} ${phase.score >= threshold ? 'PASS' : 'FAIL'}`);
  }
  const parallel = phase.parallelWith ?? [];
  if (parallel.length > 0) {
    parts.push(`∥ ${parallel.join(', ')}`);
  }
  if (phase.humanGate) {
    if (verdict) {
      parts.push(`gate ${verdict.verdict} (${verdict.decidedBy})`);
    } else if (isAwaitingHuman(phase, verdict)) {
      parts.push('gate AWAITING HUMAN');
    } else if (toVerdictKind(phase.verdict)) {
      parts.push(`gate ${phase.verdict}`);
    } else {
      parts.push('gate human');
    }
  }
  if ((phase.attempts ?? 0) > 1) {
    parts.push(`attempts ${phase.attempts}`);
  }
  return parts.join(' · ');
}

function phaseTooltip(name: string, phase: PhaseState, verdict: GateVerdict | null): string {
  const lines = [`**${name}** — ${phase.status}`];
  if (typeof phase.score === 'number') {
    const threshold = phase.gateThreshold ?? 0;
    lines.push(`Score ${phase.score} against a threshold of ${threshold}.`);
  }
  if ((phase.attempts ?? 0) >= 3) {
    lines.push(
      `This phase has been attempted ${phase.attempts} times. Three identical failures is a `
      + 'signal about the approach rather than about the effort.',
    );
  }
  if (verdict) {
    lines.push(`Verdict **${verdict.verdict}** recorded ${verdict.decidedAt} by ${verdict.decidedBy}.`);
    if (verdict.note) {
      lines.push(`Note: ${verdict.note}`);
    }
    if (!toVerdictKind(phase.verdict)) {
      lines.push(
        '_The checkpoint has not recorded this verdict yet. The verdict file is what releases '
        + 'the blocked session; the checkpoint catches up on the next `pipeline.py` run._',
      );
    }
  } else if (isAwaitingHuman(phase, verdict)) {
    lines.push('An artifact is waiting for a verdict. The agent cannot end its turn until one exists.');
  }
  return lines.join('\n\n');
}

function summarize(checkpoint: PipelineCheckpoint, blockedCount: number): string {
  const phases = Object.values(checkpoint.phases);
  const done = phases.filter((phase) => phase.status === 'complete' || phase.status === 'skipped').length;
  const parts = [`${done}/${phases.length}`, checkpoint.status ?? 'active'];
  if (blockedCount > 0) {
    parts.push(`${blockedCount} gate${blockedCount === 1 ? '' : 's'} awaiting a human`);
  }
  if ((checkpoint.compactions ?? 0) > 0) {
    parts.push(`survived ${checkpoint.compactions} compaction(s)`);
  }
  return parts.join(' · ');
}

function pipelineTooltip(checkpoint: PipelineCheckpoint): string {
  const lines = [`**${checkpoint.pipelineId}**`];
  if (checkpoint.requirement) {
    lines.push(checkpoint.requirement);
  }
  if (checkpoint.repo) {
    lines.push(`Repo: \`${checkpoint.repo}\``);
  }
  if (checkpoint.updatedAt) {
    lines.push(`Updated ${checkpoint.updatedAt}`);
  }
  if (checkpoint.sourceFile) {
    lines.push(`\`${path.basename(checkpoint.sourceFile)}\``);
  }
  return lines.join('\n\n');
}

function contractNodes(band: BandState, pipelineId: string): PipelineNode[] {
  const contracts = Object.entries(band.sharedContracts ?? {});
  if (contracts.length === 0) {
    return [];
  }
  return contracts.map(([key, shape]) => {
    const item = new PipelineNode(
      'contract',
      key,
      vscode.TreeItemCollapsibleState.None,
      pipelineId,
    );
    item.description = shape || '(no shape recorded)';
    item.iconPath = new vscode.ThemeIcon('symbol-interface');
    item.tooltip = new vscode.MarkdownString(
      `Consume \`${key}\` downstream exactly as named. If the name is genuinely wrong, `
      + 'change it upstream and re-advance the band.',
    );
    return item;
  });
}
