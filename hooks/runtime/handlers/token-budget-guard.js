#!/usr/bin/env node
'use strict';
/**
 * Token Budget Guard.
 *
 * Measures the discovery footprint — skill frontmatter name+description, which is
 * parsed and held in context in every session before the user types anything — against
 * the ceiling in config/token-budgets.json.
 *
 * NEVER BLOCKS. `hardFail` is false by design. A blown budget degrades answer quality;
 * it is not a safety incident, and halting somebody's work over it would be a strictly
 * worse outcome than a trimmed prompt. The discovery overrun does warn on every session
 * start until it is fixed, though, because unlike the eager budget this cost is paid by
 * every conversation in every repository, so the nagging is proportionate.
 */

const fs = require('fs');
const path = require('path');
const respond = require('../lib/respond');
const config = require('../../../lib/config');
const paths = require('../../../lib/paths');

function frontmatter(text) {
  if (!text.startsWith('---')) return {};
  const end = text.indexOf('\n---', 3);
  if (end === -1) return {};
  const block = text.slice(3, end);
  const meta = {};
  // A deliberately tiny parser: name and description are single-line scalars by
  // contract (the per-skill byte cap makes a multi-line description impossible), so
  // pulling in a YAML dependency for this would cost more startup than it is worth.
  for (const line of block.split('\n')) {
    const match = /^([A-Za-z0-9_-]+)\s*:\s*(.*)$/.exec(line);
    if (match) meta[match[1]] = match[2].trim().replace(/^["']|["']$/g, '');
  }
  return meta;
}

function measureDiscovery(root) {
  const skillsDir = path.join(root, 'skills');
  if (!fs.existsSync(skillsDir)) return { total: 0, perSkill: [] };
  const perSkill = [];
  for (const entry of fs.readdirSync(skillsDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const file = path.join(skillsDir, entry.name, 'SKILL.md');
    if (!fs.existsSync(file)) continue;
    const meta = frontmatter(fs.readFileSync(file, 'utf8'));
    const bytes = Buffer.byteLength(`${meta.name || ''}${meta.description || ''}`, 'utf8');
    perSkill.push({ skill: entry.name, bytes });
  }
  return { total: perSkill.reduce((sum, s) => sum + s.bytes, 0), perSkill };
}

async function run() {
  const root = paths.pluginRoot();
  if (!root) return respond.allow();

  const budgets = config.tokenBudgets();
  const discovery = budgets.discovery || {};
  const ceiling = discovery.aggregateFrontmatterBytes;
  const perSkillCap = discovery.perSkillFrontmatterBytes;
  if (typeof ceiling !== 'number' || typeof perSkillCap !== 'number') {
    return respond.inform(
      '[Token Budget] A discovery ceiling in config/token-budgets.json is not a number, which '
      + 'means the comparison is silently disabled rather than failing. Run '
      + '`python scripts/validate-structure.py` — the ratchet pins catch exactly this.',
    );
  }

  const { total, perSkill } = measureDiscovery(root);
  const warnAt = ((budgets.warnAtPercent || 85) / 100) * ceiling;
  const over = perSkill.filter((s) => s.bytes > perSkillCap);

  if (total <= warnAt && !over.length) return respond.allow();

  const lines = ['[Token Budget]'];
  if (total > ceiling) {
    lines.push(
      `Discovery footprint is ${total}B against a ${ceiling}B ceiling — OVER. This text loads in `
      + 'every session in every repo, so it is the most expensive text in the system.',
    );
  } else if (total > warnAt) {
    lines.push(`Discovery footprint is ${total}B / ${ceiling}B (${Math.round((total / ceiling) * 100)}%).`);
  }
  for (const s of over) {
    lines.push(
      `  - ${s.skill}: ${s.bytes}B frontmatter, over the ${perSkillCap}B per-skill cap. `
      + "Move trigger, USE FOR, and NOT FOR text into the skill body's '## Routing' block.",
    );
  }
  lines.push('Run `/budget` for a ranked list of what to cut, with a concrete edit for each item.');
  return respond.inform(lines.join('\n'));
}

module.exports = { run, measureDiscovery, frontmatter };

if (require.main === module) {
  run().then((result) => {
    const out = respond.serialize('SessionStart', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
