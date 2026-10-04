/**
 * The human-gate review panel — and the one place in the view plane that writes.
 *
 * WHY THIS IS THE REASON THE PLANE EXISTS
 *
 * Three pipeline phases are declared `humanGate: true`. The gate is enforced by a Stop
 * hook that refuses to let a session end while an artifact exists with no verdict beside
 * it, so the agent genuinely cannot clear its own gate. What a human then needs is the
 * artifact in front of them and two buttons. A chat window can show the artifact but it
 * cannot show it *while* the session is blocked on it, and it certainly cannot show four
 * of them side by side. This panel is the third of the three reasons the extension was
 * kept when the chat participant, the skill loader, the hub sync, the token budgeter and
 * the context generator were deleted.
 *
 * THE PANEL IS A NICETY OVER A FILE PROTOCOL, NEVER A DEPENDENCY
 *
 * The verdict is a JSON file. `python scripts/pipeline.py approve <id> <phase>` and
 * `python scripts/pipeline.py request-changes <id> <phase> --note "..."` write the same
 * file, so anyone on Linux, in a terminal, in a different editor, or on a machine where
 * this extension is not installed is fully served. Nothing in the pipeline knows or cares
 * which surface produced the verdict; `decidedBy` records it purely so a later reader can
 * tell them apart.
 *
 * ONE HONEST ASYMMETRY BETWEEN THE TWO SURFACES
 *
 * `pipeline.py approve` writes the verdict AND folds it into the checkpoint, marking the
 * phase complete and activating whatever the DAG says is next. This panel writes only the
 * verdict, because the verdict is the only file the view plane may write. That is enough
 * to release the blocked session — the Stop hook reads the verdict file, not the
 * checkpoint — but the checkpoint's mirrored status catches up only on the next
 * `pipeline.py` run. The pipeline tree reconciles the two at read time and labels the
 * gap, so the state is visible rather than merely inconsistent. If you want the
 * checkpoint advanced in the same breath, use the CLI; it is the more complete of the two
 * paths and this file will not pretend otherwise.
 *
 * SECURITY POSTURE OF THE WEBVIEW
 *
 * The artifact is repository-derived text of unknown provenance — an agent wrote it,
 * possibly from a file somebody else wrote. Every interpolation into this webview is HTML
 * -escaped, the content security policy is `default-src 'none'` with nonces for the one
 * style block and the one script, and no local or remote resource root is granted. There
 * is deliberately no Markdown renderer: shipping one would mean either a runtime
 * dependency in a plane that has none, or hand-rolling an HTML generator over untrusted
 * text, and the artifact reads perfectly well as monospaced plain text.
 */

import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import { SETTINGS, gateArtifactName, gateVerdictName, setting, utcNow } from '../shared/constants';
import { StateReader } from '../state/reader';
import { GateVerdict, PendingGate, VerdictKind } from '../shared/types';

/** Which surface wrote the verdict. `scripts/pipeline.py` writes `cli`. */
const DECIDED_BY = 'view';

/**
 * A cap on the note. It is stored in a session-scoped file and read back to an agent, and
 * an unbounded paste into a JSON field is the kind of thing that is nobody's fault and
 * everybody's problem.
 */
const MAX_NOTE_LENGTH = 4000;

/** Identifies which gate a command was invoked against, from a tree node or a quick pick. */
export interface GateTarget {
  pipelineId: string;
  phase: string;
}

function isGateTarget(value: unknown): value is GateTarget {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return typeof candidate.pipelineId === 'string' && typeof candidate.phase === 'string';
}

interface WebviewMessage {
  type: 'approve' | 'request-changes';
  note: string;
}

function parseMessage(value: unknown): WebviewMessage | null {
  if (typeof value !== 'object' || value === null) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  if (candidate.type !== 'approve' && candidate.type !== 'request-changes') {
    return null;
  }
  const note = typeof candidate.note === 'string' ? candidate.note : '';
  return { type: candidate.type, note: note.slice(0, MAX_NOTE_LENGTH) };
}

/**
 * Owns the gate panels and the verdict write. Constructed once in `activate` and
 * disposed with the extension.
 */
export class GateReviewService implements vscode.Disposable {
  private readonly panels = new Map<string, vscode.WebviewPanel>();
  private readonly verdictWritten = new vscode.EventEmitter<GateVerdict>();

  /** Fires after a verdict lands on disk, so the trees and status bar can refresh. */
  public readonly onDidWriteVerdict: vscode.Event<GateVerdict> = this.verdictWritten.event;

  constructor(
    private readonly reader: StateReader,
    private readonly output: vscode.OutputChannel,
  ) {}

  public dispose(): void {
    for (const panel of this.panels.values()) {
      panel.dispose();
    }
    this.panels.clear();
    this.verdictWritten.dispose();
  }

  /* --------------------------------------------------------------- commands */

  /** `orchestrator.openGateReview` */
  public async open(argument?: unknown): Promise<void> {
    const target = await this.resolveTarget(argument, 'Which gate do you want to review?');
    if (!target) {
      return;
    }
    const artifact = this.reader.readGateArtifact(target.pipelineId, target.phase);
    if (artifact === null) {
      void vscode.window.showWarningMessage(
        `No gate artifact for ${target.pipelineId} / ${target.phase}. There is nothing to approve.`,
      );
      return;
    }
    this.showPanel(target, artifact);
  }

  /** `orchestrator.approveGate` */
  public async approve(argument?: unknown): Promise<void> {
    const target = await this.resolveTarget(argument, 'Which gate are you approving?');
    if (!target) {
      return;
    }
    await this.recordVerdict(target, 'approved', '');
  }

  /** `orchestrator.requestChanges` */
  public async requestChanges(argument?: unknown): Promise<void> {
    const target = await this.resolveTarget(argument, 'Which gate needs changes?');
    if (!target) {
      return;
    }
    const note = await vscode.window.showInputBox({
      title: `Request changes — ${target.pipelineId} / ${target.phase}`,
      prompt: 'What has to change? A rejection with no reason is a rejection nobody can act on.',
      validateInput: (value) => (value.trim().length === 0 ? 'A note is required.' : null),
    });
    if (note === undefined) {
      return;
    }
    await this.recordVerdict(target, 'changes-requested', note.trim());
  }

  /* ---------------------------------------------------------------- panel */

  private showPanel(target: GateTarget, artifact: string): void {
    const key = `${target.pipelineId}::${target.phase}`;
    const existing = this.panels.get(key);
    if (existing) {
      existing.webview.html = this.renderHtml(target, artifact);
      existing.reveal(vscode.ViewColumn.Active);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      'orchestrator.gateReview',
      `Gate: ${target.phase}`,
      vscode.ViewColumn.Active,
      {
        enableScripts: true,
        // The panel keeps a half-typed note across a tab switch. Rebuilding it would
        // silently discard what somebody was in the middle of writing.
        retainContextWhenHidden: true,
        // No local resource roots: this webview loads nothing from disk, and granting a
        // root it does not need is a permission somebody later mistakes for a requirement.
        localResourceRoots: [],
      },
    );
    panel.webview.html = this.renderHtml(target, artifact);
    panel.onDidDispose(() => this.panels.delete(key));
    panel.webview.onDidReceiveMessage((raw: unknown) => {
      const message = parseMessage(raw);
      if (!message) {
        this.output.appendLine('[warn] ignored an unrecognised message from the gate webview');
        return;
      }
      void this.handlePanelMessage(target, message, panel);
    });
    this.panels.set(key, panel);
  }

  private async handlePanelMessage(
    target: GateTarget,
    message: WebviewMessage,
    panel: vscode.WebviewPanel,
  ): Promise<void> {
    if (message.type === 'request-changes' && message.note.trim().length === 0) {
      void vscode.window.showWarningMessage(
        'A note is required to request changes. A rejection with no reason is a rejection '
        + 'nobody can act on.',
      );
      return;
    }
    const verdict: VerdictKind = message.type === 'approve' ? 'approved' : 'changes-requested';
    const written = await this.recordVerdict(target, verdict, message.note.trim());
    if (written) {
      panel.dispose();
    }
  }

  /* ---------------------------------------------------------- the one write */

  /**
   * Write the verdict file.
   *
   * gate-verdict-write — THIS IS THE VIEW PLANE'S ONLY WRITE, AND THE ONLY ONE ALLOWED.
   *
   * `scripts/validate-structure.py` greps `view/src/**` for filesystem writes and fails
   * the build unless the file containing one also contains that marker string. The marker
   * is not a suppression; it is a signature on a claim, and the claim is this: the view
   * plane reads state and owns no orchestration, with exactly one exception — a human's
   * verdict on a human gate, which by definition cannot originate anywhere else.
   *
   * If a second write ever seems necessary here, the honest reading is that the boundary
   * was drawn in the wrong place, not that this comment should be copied into a second
   * file. The work belongs in `scripts/` or in a hook, where the runtime plane lives.
   *
   * The write is temp-file-then-rename for the same reason `lib/state.js` and
   * `scripts/_lib.py` do it: a process killed midway through must not leave truncated
   * JSON that every later reader fails to parse — and here the reader that would fail is
   * the Stop hook, which would then hold the session open on a gate that was answered.
   */
  private async recordVerdict(
    target: GateTarget,
    verdict: VerdictKind,
    note: string,
  ): Promise<boolean> {
    const sessionsDir = this.reader.sessionsDir();
    if (!sessionsDir) {
      void vscode.window.showErrorMessage('No workspace folder is open, so there is nowhere to write a verdict.');
      return false;
    }

    const artifactPath = path.join(sessionsDir, gateArtifactName(target.pipelineId, target.phase));
    if (!fs.existsSync(artifactPath)) {
      void vscode.window.showErrorMessage(
        `No gate artifact at ${artifactPath}. Refusing to write a verdict on a gate that does not exist.`,
      );
      return false;
    }

    const verdictPath = path.join(sessionsDir, gateVerdictName(target.pipelineId, target.phase));
    if (fs.existsSync(verdictPath)) {
      const overwrite = await vscode.window.showWarningMessage(
        `${target.pipelineId} / ${target.phase} already has a verdict. Replace it?`,
        { modal: true },
        'Replace',
      );
      if (overwrite !== 'Replace') {
        return false;
      }
    } else if (verdict === 'approved' && setting<boolean>(SETTINGS.gateReviewConfirmApprove, true)) {
      const confirmed = await vscode.window.showWarningMessage(
        `Approve ${target.phase} in ${target.pipelineId}?`,
        { modal: true, detail: 'This releases an agent session that is currently blocked on your verdict.' },
        'Approve',
      );
      if (confirmed !== 'Approve') {
        return false;
      }
    }

    const record: GateVerdict = {
      pipelineId: target.pipelineId,
      phase: target.phase,
      verdict,
      // Stored verbatim. This note is human-authored, session-scoped, and discarded with
      // the session — unlike a memory capture, which syncs to every connected repository
      // and therefore goes through the redaction and injection guard in `memory.py`.
      note,
      decidedAt: utcNow(),
      decidedBy: DECIDED_BY,
    };

    const temporary = `${verdictPath}.${process.pid}.tmp`;
    try {
      await fs.promises.writeFile(temporary, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
      await fs.promises.rename(temporary, verdictPath);
    } catch (error) {
      this.output.appendLine(`[error] could not record the verdict at ${verdictPath}: ${String(error)}`);
      void vscode.window.showErrorMessage(
        `Could not write the verdict: ${String(error)}. `
        + `From a terminal: python scripts/pipeline.py ${verdict === 'approved' ? 'approve' : 'request-changes'} `
        + `${target.pipelineId} ${target.phase}`,
      );
      return false;
    }

    this.output.appendLine(`[info] verdict ${verdict} recorded for ${target.pipelineId} / ${target.phase}`);
    this.verdictWritten.fire(record);
    void vscode.window.showInformationMessage(
      `${target.phase}: ${verdict}. The blocked session can now end its turn. `
      + 'Run any `pipeline.py` command to fold the verdict into the checkpoint.',
    );
    return true;
  }

  /* --------------------------------------------------------------- helpers */

  /** Take the target from a tree node when there is one, otherwise ask. */
  private async resolveTarget(argument: unknown, placeholder: string): Promise<GateTarget | null> {
    if (isGateTarget(argument)) {
      return { pipelineId: argument.pipelineId, phase: argument.phase };
    }
    const pending = this.reader.readPendingGates();
    if (pending.length === 0) {
      void vscode.window.showInformationMessage('No gate is waiting on a verdict in this workspace.');
      return null;
    }
    if (pending.length === 1) {
      return { pipelineId: pending[0].pipelineId, phase: pending[0].phase };
    }
    const picked = await vscode.window.showQuickPick(
      pending.map((gate: PendingGate) => ({
        label: `${gate.phase}`,
        description: gate.pipelineId,
        detail: gate.artifactPath,
        gate,
      })),
      { placeHolder: placeholder, matchOnDescription: true },
    );
    return picked ? { pipelineId: picked.gate.pipelineId, phase: picked.gate.phase } : null;
  }

  private renderHtml(target: GateTarget, artifact: string): string {
    const nonce = createNonce();
    const csp = [
      "default-src 'none'",
      `style-src 'nonce-${nonce}'`,
      `script-src 'nonce-${nonce}'`,
    ].join('; ');

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gate review</title>
<style nonce="${nonce}">
  body {
    font-family: var(--vscode-font-family);
    color: var(--vscode-foreground);
    background: var(--vscode-editor-background);
    padding: 1rem 1.25rem 2rem;
    line-height: 1.5;
  }
  h1 { font-size: 1.15rem; margin: 0 0 0.25rem; }
  .meta { color: var(--vscode-descriptionForeground); font-size: 0.85rem; margin-bottom: 1rem; }
  pre {
    background: var(--vscode-textCodeBlock-background);
    border: 1px solid var(--vscode-panel-border);
    border-radius: 4px;
    padding: 0.75rem 1rem;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 55vh;
    overflow-y: auto;
    font-family: var(--vscode-editor-font-family);
    font-size: var(--vscode-editor-font-size);
  }
  label { display: block; margin: 1rem 0 0.35rem; font-weight: 600; }
  textarea {
    width: 100%;
    min-height: 5rem;
    box-sizing: border-box;
    color: var(--vscode-input-foreground);
    background: var(--vscode-input-background);
    border: 1px solid var(--vscode-input-border, var(--vscode-panel-border));
    border-radius: 4px;
    padding: 0.5rem;
    font-family: var(--vscode-font-family);
  }
  .actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
  button {
    color: var(--vscode-button-foreground);
    background: var(--vscode-button-background);
    border: none;
    border-radius: 2px;
    padding: 0.45rem 1rem;
    cursor: pointer;
    font-size: 0.9rem;
  }
  button.secondary {
    color: var(--vscode-button-secondaryForeground);
    background: var(--vscode-button-secondaryBackground);
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .footnote {
    margin-top: 1.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--vscode-panel-border);
    color: var(--vscode-descriptionForeground);
    font-size: 0.82rem;
  }
  code { font-family: var(--vscode-editor-font-family); }
</style>
</head>
<body>
  <h1>${escapeHtml(target.phase)}</h1>
  <div class="meta">
    Pipeline <code>${escapeHtml(target.pipelineId)}</code> is blocked until this gate has a verdict.
  </div>

  <pre>${escapeHtml(artifact)}</pre>

  <label for="note">Note</label>
  <textarea id="note" placeholder="Required to request changes; optional on approval."></textarea>

  <div class="actions">
    <button id="approve" type="button">Approve</button>
    <button id="changes" type="button" class="secondary" disabled>Request changes</button>
  </div>

  <div class="footnote">
    The verdict is a JSON file next to the artifact. The same file can be written from a
    terminal with
    <code>python scripts/pipeline.py approve ${escapeHtml(target.pipelineId)} ${escapeHtml(target.phase)}</code>,
    which also advances the checkpoint — this panel writes the verdict only.
  </div>

<script nonce="${nonce}">
  const vscodeApi = acquireVsCodeApi();
  const note = document.getElementById('note');
  const approve = document.getElementById('approve');
  const changes = document.getElementById('changes');

  // A rejection with no reason is a rejection nobody can act on, so the button stays
  // disabled until there is something to act on.
  const sync = () => { changes.disabled = note.value.trim().length === 0; };
  note.addEventListener('input', sync);
  sync();

  const send = (type) => {
    approve.disabled = true;
    changes.disabled = true;
    vscodeApi.postMessage({ type, note: note.value });
  };
  approve.addEventListener('click', () => send('approve'));
  changes.addEventListener('click', () => send('request-changes'));
</script>
</body>
</html>`;
  }
}

/* ============================================================ pure helpers */

/**
 * Escape every character that can change the meaning of surrounding HTML. The artifact
 * and the pipeline id both originate outside this extension, so they are escaped without
 * exception — including in attribute positions, which is why the quote characters are in
 * the list and not only the angle brackets.
 */
export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * A fresh nonce per render, from the cryptographic generator rather than `Math.random`.
 * A predictable nonce is not a nonce: the whole mechanism is that an injected script tag
 * cannot carry the right value, and a value an attacker can compute is one they can carry.
 */
export function createNonce(): string {
  return crypto.randomBytes(16).toString('hex');
}
