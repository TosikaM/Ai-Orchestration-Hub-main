/**
 * The view plane's entry point. It wires readers to trees and gets out of the way.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO
 *
 * An earlier version of this extension was the runtime: it hosted a chat participant,
 * loaded skills, routed slash commands, synced content from the hub, budgeted tokens,
 * generated repo context, and wrote memory, pipeline, cross-repo and telemetry state.
 * Roughly five of its twelve services were re-implementations of things the host already
 * did, and its stated central limitation was that it "does not own the generation stream"
 * and therefore "cannot block" — which meant the quality gates it advertised were
 * suggestions.
 *
 * Under Claude Code a PreToolUse hook returns a permission decision of "deny", so the
 * system owns the ACTION stream instead. That is where a hallucination stops being a
 * sentence and becomes an edit, and it is enforced by the plugin, in `hooks/`, not here.
 * What survived into this file is the part a tree does better than a transcript: showing
 * state, and handing a human a gate artifact with two buttons.
 *
 * ONE SETTINGS PREFIX, READ THROUGH ONE FUNCTION
 *
 * Every configuration read in this extension goes through `setting()` in
 * `shared/constants.ts`, which is the only place `getConfiguration` is called and the
 * only place the section name is spelled. That is not tidiness for its own sake. A prior
 * version declared its settings as `aiorchestrator.*` in package.json and read them as
 * `getConfiguration('aiOrchestrator')` in nine call sites; VS Code returns an empty
 * section rather than an error, `get(key, fallback)` on an empty section returns the
 * fallback, and so every user setting in the extension silently had no effect. Nothing
 * failed, nothing logged, and the settings UI looked correct because it reads
 * package.json. One shared constant turns that class of mistake into a compile error.
 */

import * as vscode from 'vscode';

import {
  COMMAND_IDS,
  REFRESH_DEBOUNCE_MS,
  SETTINGS,
  SETTINGS_PREFIX,
  VIEW_IDS,
  WORKSPACE_PATHS,
  setting,
} from './shared/constants';
import { StateReader } from './state/reader';
import { AgentTreeProvider } from './providers/agentTree';
// `escapeHtml` and `createNonce` live beside the gate panel because that is the webview
// whose content is genuinely untrusted. The dashboard imports them rather than growing a
// second copy: two escapers is how one of them ends up subtly weaker than the other.
import { GateReviewService, createNonce, escapeHtml } from './providers/gateReview';
import { MemoryTreeProvider } from './providers/memoryTree';
import { PipelineTreeProvider } from './providers/pipelineTree';
import { RepoTreeProvider } from './providers/repoTree';

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel('AI Orchestrator (View)');
  context.subscriptions.push(output);

  const folder = vscode.workspace.workspaceFolders?.[0];
  const reader = new StateReader(folder?.uri.fsPath, output);
  output.appendLine(`[info] workspace: ${folder?.uri.fsPath ?? '(none open)'}`);
  output.appendLine(`[info] state home: ${reader.stateHome()}`);

  const pipelineTree = new PipelineTreeProvider(reader);
  const agentTree = new AgentTreeProvider(reader);
  const memoryTree = new MemoryTreeProvider(reader);
  const repoTree = new RepoTreeProvider(reader);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider(VIEW_IDS.pipeline, pipelineTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.agents, agentTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.memory, memoryTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.repos, repoTree),
  );

  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.command = COMMAND_IDS.showDashboard;
  context.subscriptions.push(status);

  const gates = new GateReviewService(reader, output);
  context.subscriptions.push(gates);

  const refreshAll = (): void => {
    pipelineTree.refresh();
    agentTree.refresh();
    memoryTree.refresh();
    repoTree.refresh();
    updateStatusBar(reader, status);
  };

  context.subscriptions.push(
    vscode.commands.registerCommand(COMMAND_IDS.refreshViews, refreshAll),
    vscode.commands.registerCommand(COMMAND_IDS.showDashboard, () => showDashboard(context, reader)),
    vscode.commands.registerCommand(COMMAND_IDS.openGateReview, (argument?: unknown) => gates.open(argument)),
    vscode.commands.registerCommand(COMMAND_IDS.approveGate, (argument?: unknown) => gates.approve(argument)),
    vscode.commands.registerCommand(COMMAND_IDS.requestChanges, (argument?: unknown) => gates.requestChanges(argument)),
  );

  // A verdict written from the panel changes what every tree should show, and the file
  // watcher below would catch it too — but only after its debounce, and only when
  // watching is switched on. Refreshing directly keeps the UI honest either way.
  context.subscriptions.push(gates.onDidWriteVerdict(() => refreshAll()));

  // Settings that change what is displayed (which pipelines, how many memory entries)
  // have to take effect without a reload, or they read as broken.
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration(SETTINGS_PREFIX)) {
        refreshAll();
      }
    }),
  );

  if (folder) {
    context.subscriptions.push(...watchSessions(folder, refreshAll, output));
  }

  refreshAll();
}

export function deactivate(): void {
  // Everything this extension creates is registered in `context.subscriptions` and is
  // disposed by the host. There is no background work, no timer that outlives the
  // window, and nothing on disk to flush — which is one of the quieter benefits of a
  // plane that reads.
}

/* ====================================================== watching and status */

/**
 * Watch `memory/sessions/**`, debounced.
 *
 * That directory is where the pipeline's whole visible state lives: checkpoints, gate
 * artifacts, verdicts, and band files. A single `pipeline.py complete` can touch three of
 * them, and an atomic write arrives as a create followed by a rename, so one logical
 * change can produce four events. Rebuilding four trees per event means visible flicker
 * for no added information; collapsing the burst first costs a quarter of a second that
 * nobody perceives.
 */
function watchSessions(
  folder: vscode.WorkspaceFolder,
  refresh: () => void,
  output: vscode.OutputChannel,
): vscode.Disposable[] {
  const pattern = new vscode.RelativePattern(folder, `${WORKSPACE_PATHS.sessions}/**`);
  const watcher = vscode.workspace.createFileSystemWatcher(pattern);
  let pending: NodeJS.Timeout | undefined;

  const schedule = (): void => {
    if (!setting<boolean>(SETTINGS.refreshOnFileChange, true)) {
      return;
    }
    if (pending) {
      clearTimeout(pending);
    }
    pending = setTimeout(() => {
      pending = undefined;
      refresh();
    }, REFRESH_DEBOUNCE_MS);
  };

  const listeners = [
    watcher.onDidCreate(schedule),
    watcher.onDidChange(schedule),
    watcher.onDidDelete(schedule),
  ];
  output.appendLine(`[info] watching ${WORKSPACE_PATHS.sessions}/** for changes`);

  // A debounce timer outliving the window would fire a refresh against disposed trees,
  // so the pending timeout is cleared as part of teardown rather than left to expire.
  const timerGuard: vscode.Disposable = {
    dispose: () => {
      if (pending) {
        clearTimeout(pending);
        pending = undefined;
      }
    },
  };
  return [watcher, ...listeners, timerGuard];
}

/**
 * The status bar answers one question without anyone opening a view: is something
 * waiting on me? A blocked gate is the only state in this system where the machine is
 * genuinely stopped until a human acts, so it is the only state that earns the
 * attention-grabbing background colour.
 */
function updateStatusBar(reader: StateReader, status: vscode.StatusBarItem): void {
  if (!reader.hasWorkspace() || !reader.isConnected()) {
    status.hide();
    return;
  }

  const pending = reader.readPendingGates();
  if (pending.length > 0) {
    const first = pending[0];
    status.text = `$(shield) ${pending.length} gate${pending.length === 1 ? '' : 's'} awaiting you`;
    status.tooltip = `${first.pipelineId} / ${first.phase} is blocked on a human verdict. `
      + 'The agent cannot end its turn until one exists.';
    status.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    status.show();
    return;
  }

  status.backgroundColor = undefined;
  const active = reader.readPipelines().find(
    (checkpoint) => (checkpoint.status ?? 'active') === 'active',
  );
  if (active) {
    status.text = `$(pulse) ${active.currentPhase ?? 'pipeline'}`;
    status.tooltip = `${active.pipelineId}: ${active.requirement ?? 'no requirement recorded'}`;
  } else {
    status.text = '$(circuit-board) orchestrator';
    status.tooltip = 'No pipeline running in this workspace.';
  }
  status.show();
}

/* ================================================================ dashboard */

let dashboard: vscode.WebviewPanel | undefined;

/**
 * A one-screen summary across the four trees. Everything on it is derived from files, and
 * every value interpolated into it is escaped — repo names, requirements and memory
 * titles all originate outside this extension, so none of them is trusted markup.
 */
function showDashboard(context: vscode.ExtensionContext, reader: StateReader): void {
  if (dashboard) {
    dashboard.webview.html = renderDashboard(reader);
    dashboard.reveal(vscode.ViewColumn.Active);
    return;
  }
  // The dashboard displays and never posts back, so scripting is off entirely and no
  // resource root is granted. A webview with no script is a webview with no attack
  // surface worth reasoning about, and this one loses nothing by having none.
  const panel = vscode.window.createWebviewPanel(
    'orchestrator.dashboard',
    'AI Orchestrator',
    vscode.ViewColumn.Active,
    { enableScripts: false, localResourceRoots: [] },
  );
  panel.webview.html = renderDashboard(reader);
  panel.onDidDispose(() => {
    dashboard = undefined;
  }, null, context.subscriptions);
  dashboard = panel;
}

function renderDashboard(reader: StateReader): string {
  const nonce = createNonce();
  const csp = `default-src 'none'; style-src 'nonce-${nonce}'`;

  const pipelines = reader.readPipelines();
  const pending = reader.readPendingGates();
  const registry = reader.readRegistry();
  const memory = reader.readMemory();
  const showTelemetry = setting<boolean>(SETTINGS.dashboardShowTelemetry, false);
  const telemetry = showTelemetry ? reader.readTelemetry() : [];

  const pipelineRows = pipelines.length === 0
    ? '<tr><td colspan="4">No pipelines in this workspace.</td></tr>'
    : pipelines.map((checkpoint) => {
      const phases = Object.values(checkpoint.phases);
      const done = phases.filter((phase) => phase.status === 'complete' || phase.status === 'skipped').length;
      return `<tr>
          <td><code>${escapeHtml(checkpoint.pipelineId)}</code></td>
          <td>${escapeHtml(checkpoint.status ?? 'active')}</td>
          <td>${done}/${phases.length}</td>
          <td>${escapeHtml(truncate(checkpoint.requirement ?? '', 90))}</td>
        </tr>`;
    }).join('\n');

  const gateRows = pending.length === 0
    ? '<p class="ok">No gate is waiting on a verdict.</p>'
    : `<ul>${pending.map((gate) => `<li><code>${escapeHtml(gate.pipelineId)}</code> — `
        + `<strong>${escapeHtml(gate.phase)}</strong></li>`).join('')}</ul>`;

  const repos = registry?.repos ?? [];
  const repoRows = repos.length === 0
    ? '<p>No connected repos in the registry.</p>'
    : `<ul>${repos.map((repo) => {
      const active = repo.name === registry?.active ? ' <em>(active)</em>' : '';
      return `<li>${escapeHtml(repo.name)} — ${escapeHtml(repo.techStack ?? 'stack unknown')}${active}</li>`;
    }).join('')}</ul>`;

  const memoryCounts = new Map<string, number>();
  for (const entry of memory) {
    memoryCounts.set(entry.category, (memoryCounts.get(entry.category) ?? 0) + 1);
  }
  const memoryRows = memory.length === 0
    ? '<p>Shared memory is empty. It ships empty on purpose — seeding it with invented '
      + 'learnings would poison the well on day one.</p>'
    : `<ul>${[...memoryCounts.entries()].map(([category, count]) =>
      `<li>${escapeHtml(category)}: ${count}</li>`).join('')}</ul>`;

  const telemetrySection = !showTelemetry
    ? '<p>Telemetry summary is off in settings.</p>'
    : telemetry.length === 0
      ? '<p>No telemetry ledger on this machine. It is local-only and off unless '
        + '<code>ORCHESTRATOR_TELEMETRY</code> is set, so this means "not recorded", not "zero".</p>'
      : `<p>${telemetry.length} recent event(s) in the local ledger.</p>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Orchestrator</title>
<style nonce="${nonce}">
  body {
    font-family: var(--vscode-font-family);
    color: var(--vscode-foreground);
    background: var(--vscode-editor-background);
    padding: 1rem 1.5rem 2rem;
    line-height: 1.5;
  }
  h1 { font-size: 1.2rem; margin: 0 0 0.25rem; }
  h2 { font-size: 1rem; margin: 1.5rem 0 0.5rem; }
  .lede { color: var(--vscode-descriptionForeground); margin: 0 0 1rem; max-width: 60ch; }
  table { border-collapse: collapse; width: 100%; }
  th, td {
    text-align: left;
    padding: 0.3rem 0.6rem 0.3rem 0;
    border-bottom: 1px solid var(--vscode-panel-border);
    vertical-align: top;
  }
  ul { margin: 0.25rem 0; padding-left: 1.2rem; }
  code { font-family: var(--vscode-editor-font-family); }
  .ok { color: var(--vscode-descriptionForeground); }
  footer {
    margin-top: 2rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--vscode-panel-border);
    color: var(--vscode-descriptionForeground);
    font-size: 0.82rem;
    max-width: 70ch;
  }
</style>
</head>
<body>
  <h1>AI Orchestrator</h1>
  <p class="lede">
    Everything below is read from files on disk. This window starts nothing and stops
    nothing; the pipeline runs in Claude Code.
  </p>

  <h2>Pipelines</h2>
  <table>
    <thead><tr><th>id</th><th>status</th><th>phases</th><th>requirement</th></tr></thead>
    <tbody>${pipelineRows}</tbody>
  </table>

  <h2>Gates awaiting a human</h2>
  ${gateRows}

  <h2>Connected repos</h2>
  ${repoRows}

  <h2>Shared memory</h2>
  ${memoryRows}

  <h2>Telemetry</h2>
  ${telemetrySection}

  <footer>
    Every action this window offers is also a command line. Approve a gate with
    <code>python scripts/pipeline.py approve &lt;id&gt; &lt;phase&gt;</code>, switch repos with
    <code>python scripts/cross-repo.py switch &lt;name&gt;</code>, and query memory with
    <code>python scripts/memory.py search "..."</code>. Nothing here is the only way in.
  </footer>
</body>
</html>`;
}

function truncate(value: string, limit: number): string {
  return value.length <= limit ? value : `${value.slice(0, limit - 1)}…`;
}
