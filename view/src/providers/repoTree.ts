/**
 * The connected-repos tree, read from `~/.orchestrator/state/connected-repos.json`.
 *
 * WHY THAT PATH AND NOT THE EDITOR'S OWN STORAGE
 *
 * This registry used to live in the extension's `globalState`, which meant the answer to
 * "which repo am I working in" existed only inside one running editor process. A
 * terminal could not read it, CI could not read it, and a second window disagreed with
 * the first. Moving it to a file under the machine-scoped state home made it readable by
 * everything, and this view became a reader of shared state rather than the owner of
 * private state — which is the plane boundary in one concrete example.
 *
 * The consequence to be honest about: switching the active repo is a write, so it is not
 * here. `python scripts/cross-repo.py switch <name>` does it, and this tree shows the
 * result. A button here would have to write a second file the view plane is not allowed
 * to write, and inventing an exception for convenience is how the boundary erodes.
 *
 * THIS IS THE LIVE REGISTRY, NOT THE COMMITTED ONE
 *
 * `registry/connected-repos.yml` in the hub is a second registry answering a different
 * question — which repositories this hub claims, and in what build order — and nothing
 * reconciles the two automatically. So a repo declared there but never `connect`ed on
 * this machine will not appear in this tree, and that is a real gap rather than a
 * rendering bug. What this tree shows is what `cross-repo.py list` shows, because both
 * read the same file.
 */

import * as vscode from 'vscode';

import { STATE_PATHS } from '../shared/constants';
import { StateReader } from '../state/reader';
import { ConnectedRepo, RepoGroup } from '../shared/types';

type NodeKind = 'repo' | 'group' | 'detail' | 'note';

export class RepoNode extends vscode.TreeItem {
  constructor(
    public readonly kind: NodeKind,
    label: string,
    collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly repoName?: string,
  ) {
    super(label, collapsibleState);
  }
}

export class RepoTreeProvider implements vscode.TreeDataProvider<RepoNode> {
  private readonly changed = new vscode.EventEmitter<RepoNode | undefined>();
  public readonly onDidChangeTreeData: vscode.Event<RepoNode | undefined> = this.changed.event;

  constructor(private readonly reader: StateReader) {}

  public refresh(): void {
    this.changed.fire(undefined);
  }

  public getTreeItem(element: RepoNode): vscode.TreeItem {
    return element;
  }

  public getChildren(element?: RepoNode): RepoNode[] {
    if (!element) {
      return this.rootNodes();
    }
    if (element.kind === 'group' && element.repoName) {
      return this.groupChildren(element.repoName);
    }
    return [];
  }

  private rootNodes(): RepoNode[] {
    const registry = this.reader.readRegistry();
    if (!registry) {
      return [
        note(
          `No registry at ${this.reader.statePath(...STATE_PATHS.connectedRepos.split('/'))}. `
          + 'Connect a repo with `python scripts/cross-repo.py connect <path>`.',
        ),
      ];
    }
    if (registry.repos.length === 0) {
      return [note('The registry exists but has no repos in it yet.')];
    }

    const active = registry.active ?? null;
    const nodes: RepoNode[] = registry.repos.map((repo) => repoNode(repo, repo.name === active));

    for (const group of registry.groups ?? []) {
      nodes.push(groupNode(group, group.name === registry.activeGroup));
    }
    return nodes;
  }

  private groupChildren(groupName: string): RepoNode[] {
    const registry = this.reader.readRegistry();
    const group = (registry?.groups ?? []).find((candidate) => candidate.name === groupName);
    if (!group) {
      return [note('That group is no longer in the registry.')];
    }
    const order = group.executionOrder && group.executionOrder.length > 0
      ? group.executionOrder
      : group.repos;

    return order.map((name, index) => {
      const item = new RepoNode(
        'detail',
        `${index + 1}. ${name}`,
        vscode.TreeItemCollapsibleState.None,
        name,
      );
      item.iconPath = new vscode.ThemeIcon('arrow-small-right');
      item.tooltip = new vscode.MarkdownString(
        'Execution order is dependency-first: producers before consumers. A consumer run '
        + 'ahead of its producer works against a contract that has not been proven to exist yet.',
      );
      return item;
    });
  }
}

/* ============================================================ pure helpers */

function note(message: string): RepoNode {
  const item = new RepoNode('note', message, vscode.TreeItemCollapsibleState.None);
  item.iconPath = new vscode.ThemeIcon('info');
  return item;
}

function repoNode(repo: ConnectedRepo, isActive: boolean): RepoNode {
  const node = new RepoNode(
    'repo',
    isActive ? `${repo.name} (active)` : repo.name,
    vscode.TreeItemCollapsibleState.None,
    repo.name,
  );
  const parts = [repo.techStack ?? 'stack unknown'];
  if (repo.role && repo.role !== '-') {
    parts.push(repo.role);
  }
  if (repo.status && repo.status !== 'active') {
    parts.push(repo.status);
  }
  node.description = parts.join(' · ');
  node.iconPath = new vscode.ThemeIcon(isActive ? 'star-full' : 'repo');
  node.tooltip = new vscode.MarkdownString(repoTooltip(repo, isActive));
  node.resourceUri = vscode.Uri.file(repo.path);
  node.contextValue = isActive ? 'orchestrator.activeRepo' : 'orchestrator.repo';
  node.command = {
    command: 'revealFileInOS',
    title: 'Reveal repository folder',
    arguments: [vscode.Uri.file(repo.path)],
  };
  return node;
}

function groupNode(group: RepoGroup, isActive: boolean): RepoNode {
  const node = new RepoNode(
    'group',
    isActive ? `${group.name} (active group)` : group.name,
    vscode.TreeItemCollapsibleState.Collapsed,
    group.name,
  );
  node.description = `${group.repos.length} repos`;
  node.iconPath = new vscode.ThemeIcon('folder-library');
  node.contextValue = 'orchestrator.repoGroup';
  return node;
}

function repoTooltip(repo: ConnectedRepo, isActive: boolean): string {
  const lines = [`**${repo.name}**`, `\`${repo.path}\``];
  if (repo.techStack) {
    lines.push(`Stack: ${repo.techStack}`);
  }
  if (repo.lastSync) {
    lines.push(`Last sync: ${repo.lastSync}`);
  }
  lines.push(
    isActive
      ? 'This is the active repo. Switch with `python scripts/cross-repo.py switch <name>`.'
      : 'Make this the active repo with `python scripts/cross-repo.py switch ' + repo.name + '`.',
  );
  return lines.join('\n\n');
}
