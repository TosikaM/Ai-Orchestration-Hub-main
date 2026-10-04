/**
 * The shared-memory tree: what this system has learned, by category.
 *
 * WHY BROWSING BEATS QUERYING HERE
 *
 * `python scripts/memory.py search "<query>"` is the right tool when you know what you
 * are looking for. Most of the value of a memory store is in the case where you do not:
 * seeing that four anti-patterns have accumulated around one subsystem, or that an
 * instinct you disagree with has been reinforced in three repositories, is a thing you
 * find by looking rather than by searching. That is the second of the three reasons the
 * view plane was kept.
 *
 * WHAT THE NUMBERS MEAN
 *
 * Each entry shows its effective confidence and, when they differ, the recorded value it
 * decayed from. Decay is applied at read time and only affects ranking — nothing is ever
 * deleted by it — so a gap between the two numbers means "this has not been reinforced
 * in a while", not "this was downgraded". Showing both is how that question has a
 * visible answer instead of requiring someone to read `scripts/memory.py`.
 *
 * Everything here is a rendering of `memory/index/entries.json`, and this view reads the
 * rendering rather than the index deliberately: the Markdown is the copy that syncs into
 * consumer repositories, so it is the copy that exists in a repo where the hub is not
 * checked out beside it.
 */

import * as vscode from 'vscode';

import { MEMORY_FILES, SETTINGS, setting } from '../shared/constants';
import { StateReader } from '../state/reader';
import { MemoryEntry } from '../shared/types';

type NodeKind = 'category' | 'entry' | 'detail' | 'note';

/**
 * Category id to the heading the renderer uses, inverted from the filename map so the
 * two cannot drift. The tuple assertion is load-bearing: without it the mapped value is
 * `string[][]`, which `Object.fromEntries` will not accept.
 */
const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  Object.values(MEMORY_FILES).map((meta) => [meta.category, meta.label] as const),
);

const CATEGORY_ICONS: Record<string, string> = {
  'anti-pattern': 'error',
  'best-practice': 'verified',
  'tool-chain': 'plug',
  instinct: 'lightbulb',
};

export class MemoryNode extends vscode.TreeItem {
  constructor(
    public readonly kind: NodeKind,
    label: string,
    collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly category?: string,
    public readonly entry?: MemoryEntry,
  ) {
    super(label, collapsibleState);
  }
}

export class MemoryTreeProvider implements vscode.TreeDataProvider<MemoryNode> {
  private readonly changed = new vscode.EventEmitter<MemoryNode | undefined>();
  public readonly onDidChangeTreeData: vscode.Event<MemoryNode | undefined> = this.changed.event;

  /**
   * Parsed once per refresh rather than once per expanded node. Four files re-parsed on
   * every tree callback would be wasteful for no gain, and the file watcher is what
   * makes the cache correct: it clears on the same event that changes the files.
   */
  private cache: MemoryEntry[] | null = null;

  constructor(private readonly reader: StateReader) {}

  public refresh(): void {
    this.cache = null;
    this.changed.fire(undefined);
  }

  public getTreeItem(element: MemoryNode): vscode.TreeItem {
    return element;
  }

  public getChildren(element?: MemoryNode): MemoryNode[] {
    if (!element) {
      return this.categoryNodes();
    }
    if (element.kind === 'category' && element.category) {
      return this.entryNodes(element.category);
    }
    if (element.kind === 'entry' && element.entry) {
      return detailNodes(element.entry);
    }
    return [];
  }

  private entries(): MemoryEntry[] {
    if (this.cache === null) {
      this.cache = this.reader.readMemory();
    }
    return this.cache;
  }

  private categoryNodes(): MemoryNode[] {
    if (!this.reader.hasWorkspace()) {
      return [note('Open a folder to browse its shared memory.')];
    }
    const all = this.entries();
    const nodes: MemoryNode[] = [];

    for (const [category, label] of Object.entries(CATEGORY_LABELS)) {
      const count = all.filter((entry) => entry.category === category).length;
      const node = new MemoryNode(
        'category',
        label,
        count > 0
          ? vscode.TreeItemCollapsibleState.Collapsed
          : vscode.TreeItemCollapsibleState.None,
        category,
      );
      node.description = count === 0 ? 'empty' : `${count}`;
      node.iconPath = new vscode.ThemeIcon(CATEGORY_ICONS[category] ?? 'book');
      node.contextValue = 'orchestrator.memoryCategory';
      nodes.push(node);
    }

    if (all.length === 0) {
      nodes.push(
        note(
          'Nothing promoted yet. Memory ships empty on purpose — an entry reaches shared '
          + 'memory only at confidence 0.7 or higher and after being seen in two repos.',
        ),
      );
    }
    return nodes;
  }

  private entryNodes(category: string): MemoryNode[] {
    const limit = Math.max(1, setting<number>(SETTINGS.memoryMaxEntriesPerCategory, 50));
    const rows = this.entries().filter((entry) => entry.category === category);
    // The renderer already orders by effective confidence, so a cap keeps the strongest
    // entries and drops the tail rather than taking an arbitrary slice.
    const shown = rows.slice(0, limit);

    const nodes = shown.map((entry) => {
      const node = new MemoryNode(
        'entry',
        entry.title,
        vscode.TreeItemCollapsibleState.Collapsed,
        category,
        entry,
      );
      node.description = confidenceLabel(entry);
      node.tooltip = new vscode.MarkdownString(entryTooltip(entry));
      node.iconPath = new vscode.ThemeIcon('circle-filled');
      node.resourceUri = vscode.Uri.file(entry.sourceFile);
      node.contextValue = 'orchestrator.memoryEntry';
      return node;
    });

    if (rows.length > shown.length) {
      nodes.push(
        note(`${rows.length - shown.length} more not shown — raise the per-category limit in settings.`),
      );
    }
    return nodes;
  }
}

/* ============================================================ pure helpers */

function note(message: string): MemoryNode {
  const item = new MemoryNode('note', message, vscode.TreeItemCollapsibleState.None);
  item.iconPath = new vscode.ThemeIcon('info');
  return item;
}

function confidenceLabel(entry: MemoryEntry): string {
  if (entry.confidence === null) {
    return 'confidence unrecorded';
  }
  const effective = entry.confidence.toFixed(2);
  const recorded = entry.recordedConfidence;
  const decayed = recorded !== null && Math.abs(recorded - entry.confidence) > 0.005;
  const repos = entry.seenInRepos.length;
  const seen = repos > 0 ? ` · ${repos} repo${repos === 1 ? '' : 's'}` : '';
  return decayed && recorded !== null
    ? `${effective} (from ${recorded.toFixed(2)})${seen}`
    : `${effective}${seen}`;
}

function detailNodes(entry: MemoryEntry): MemoryNode[] {
  const rows: Array<{ label: string; value: string; icon: string }> = [];

  if (entry.resolution) {
    rows.push({ label: 'do instead', value: entry.resolution, icon: 'arrow-right' });
  }
  if (entry.context) {
    rows.push({ label: 'context', value: entry.context, icon: 'note' });
  }
  if (entry.seenInRepos.length > 0) {
    rows.push({ label: 'seen in', value: entry.seenInRepos.join(', '), icon: 'repo' });
  }
  rows.push({ label: 'applies to', value: entry.appliesTo || 'all', icon: 'symbol-namespace' });
  if (entry.lastReinforced) {
    rows.push({ label: 'last reinforced', value: entry.lastReinforced, icon: 'history' });
  }

  return rows.map((row) => {
    const item = new MemoryNode(
      'detail',
      `${row.label}: ${row.value}`,
      vscode.TreeItemCollapsibleState.None,
      entry.category,
      entry,
    );
    item.iconPath = new vscode.ThemeIcon(row.icon);
    item.tooltip = row.value;
    return item;
  });
}

function entryTooltip(entry: MemoryEntry): string {
  const lines = [`**${entry.title}**`];
  if (entry.resolution) {
    lines.push(`Do instead: ${entry.resolution}`);
  }
  if (entry.context) {
    lines.push(`Context: ${entry.context}`);
  }
  if (entry.confidence !== null && entry.recordedConfidence !== null
    && Math.abs(entry.recordedConfidence - entry.confidence) > 0.005) {
    lines.push(
      `Effective confidence ${entry.confidence.toFixed(2)}, decayed from a recorded `
      + `${entry.recordedConfidence.toFixed(2)}. Decay affects ranking only — nothing is deleted by it.`,
    );
  }
  return lines.join('\n\n');
}
