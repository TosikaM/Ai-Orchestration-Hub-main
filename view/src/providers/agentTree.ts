/**
 * The agents tree: what the frontmatter of each `*.agent.md` declares.
 *
 * WHAT THIS CAN AND CANNOT SEE, STATED PLAINLY
 *
 * Under the plugin distribution model the agents ship inside the plugin, not inside the
 * consumer repository. This extension reads files on disk in the open folder, so in a
 * normal install it can see agents in exactly two situations: the folder is the hub
 * checkout itself, or somebody ran `connect-repo.ps1 -Vendor` to put a copy in
 * `.github/agents/` for an offline or audit requirement.
 *
 * When neither is true the tree says the agents are in the plugin and this view cannot
 * read them. That is a worse-looking answer than showing an empty list and a better one:
 * an empty list is read as "this repo has no agents", which is false — it has ten, and
 * they are loaded and working. An honest "not found" outranks a plausible guess.
 *
 * The tree also flags an agent whose body has no Prompt Defense Baseline, because that
 * is the section every agent is supposed to carry and its absence is invisible in a
 * transcript.
 */

import * as path from 'path';
import * as vscode from 'vscode';

import { StateReader } from '../state/reader';
import { AgentDefinition } from '../shared/types';

type NodeKind = 'agent' | 'detail' | 'note';

export class AgentNode extends vscode.TreeItem {
  constructor(
    public readonly kind: NodeKind,
    label: string,
    collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly agent?: AgentDefinition,
  ) {
    super(label, collapsibleState);
  }
}

export class AgentTreeProvider implements vscode.TreeDataProvider<AgentNode> {
  private readonly changed = new vscode.EventEmitter<AgentNode | undefined>();
  public readonly onDidChangeTreeData: vscode.Event<AgentNode | undefined> = this.changed.event;

  constructor(private readonly reader: StateReader) {}

  public refresh(): void {
    this.changed.fire(undefined);
  }

  public getTreeItem(element: AgentNode): vscode.TreeItem {
    return element;
  }

  public getChildren(element?: AgentNode): AgentNode[] {
    if (!element) {
      return this.rootNodes();
    }
    if (element.kind === 'agent' && element.agent) {
      return detailNodes(element.agent);
    }
    return [];
  }

  private rootNodes(): AgentNode[] {
    if (!this.reader.hasWorkspace()) {
      return [note('Open a folder to see its agent definitions.')];
    }
    const { agents, source } = this.reader.readAgents();
    if (agents.length === 0) {
      return [
        note(
          'No agent files on disk here. The plugin carries the agents, and this view reads '
          + 'files — so this says nothing about whether they are loaded.',
        ),
      ];
    }

    const nodes = agents.map((agent) => {
      const node = new AgentNode(
        'agent',
        agent.name,
        vscode.TreeItemCollapsibleState.Collapsed,
        agent,
      );
      node.description = agent.tools ? `${agent.tools.length} tools` : 'no tools declared';
      node.tooltip = new vscode.MarkdownString(agentTooltip(agent));
      node.iconPath = new vscode.ThemeIcon(agent.hasPromptDefense ? 'person' : 'warning');
      node.resourceUri = vscode.Uri.file(agent.filePath);
      node.command = {
        command: 'vscode.open',
        title: 'Open agent definition',
        arguments: [vscode.Uri.file(agent.filePath)],
      };
      node.contextValue = 'orchestrator.agent';
      return node;
    });

    if (source) {
      nodes.unshift(note(`Read from \`${source}/\` in this workspace.`));
    }
    return nodes;
  }
}

/* ============================================================ pure helpers */

function note(message: string): AgentNode {
  const item = new AgentNode('note', message, vscode.TreeItemCollapsibleState.None);
  item.iconPath = new vscode.ThemeIcon('info');
  return item;
}

function detailNodes(agent: AgentDefinition): AgentNode[] {
  const nodes: AgentNode[] = [];

  if (agent.description) {
    const item = new AgentNode('detail', agent.description, vscode.TreeItemCollapsibleState.None);
    item.iconPath = new vscode.ThemeIcon('note');
    item.tooltip = agent.description;
    nodes.push(item);
  }

  if (agent.model) {
    const item = new AgentNode('detail', `model: ${agent.model}`, vscode.TreeItemCollapsibleState.None);
    item.iconPath = new vscode.ThemeIcon('chip');
    nodes.push(item);
  }

  const tools = agent.tools ?? [];
  if (tools.length > 0) {
    const item = new AgentNode(
      'detail',
      `tools: ${tools.join(', ')}`,
      vscode.TreeItemCollapsibleState.None,
    );
    item.iconPath = new vscode.ThemeIcon('tools');
    item.tooltip = new vscode.MarkdownString(
      'The declared least-privilege surface. An agent that declares more than it needs is '
      + 'not a bug that shows up as a failure, which is why it is worth being able to see.',
    );
    nodes.push(item);
  } else {
    const item = new AgentNode(
      'detail',
      'no tools declared',
      vscode.TreeItemCollapsibleState.None,
    );
    item.iconPath = new vscode.ThemeIcon('warning');
    item.tooltip = 'No `tools:` line in the frontmatter. That is different from declaring an empty list.';
    nodes.push(item);
  }

  if (!agent.hasPromptDefense) {
    const item = new AgentNode(
      'detail',
      'no Prompt Defense Baseline',
      vscode.TreeItemCollapsibleState.None,
    );
    item.iconPath = new vscode.ThemeIcon('warning');
    item.tooltip = new vscode.MarkdownString(
      'The body has no `## Prompt Defense Baseline` section. Every agent is meant to carry a '
      + 'stated identity boundary, because the hub distributes Markdown into contexts '
      + 'automatically and an agent with no boundary inherits whatever arrives.',
    );
    nodes.push(item);
  }

  const file = new AgentNode(
    'detail',
    path.basename(agent.filePath),
    vscode.TreeItemCollapsibleState.None,
  );
  file.iconPath = new vscode.ThemeIcon('file');
  file.resourceUri = vscode.Uri.file(agent.filePath);
  file.command = {
    command: 'vscode.open',
    title: 'Open agent definition',
    arguments: [vscode.Uri.file(agent.filePath)],
  };
  nodes.push(file);

  return nodes;
}

function agentTooltip(agent: AgentDefinition): string {
  const lines = [`**${agent.name}**`];
  if (agent.description) {
    lines.push(agent.description);
  }
  lines.push(`\`${agent.filePath}\``);
  return lines.join('\n\n');
}
