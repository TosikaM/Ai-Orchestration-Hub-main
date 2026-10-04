#!/usr/bin/env node
'use strict';
/**
 * Stop: Citation Guard.
 *
 * Audits the turn's final response for claims about this codebase that shipped without
 * a verifiable `file:line`.
 *
 * HONEST ABOUT ITS OWN STRENGTH
 *
 * This is Advisory, and it stays Advisory even now that the runtime can block. The
 * reason is worth stating rather than hiding: the detector is lexical, and a lexical
 * detector on prose has a false-positive rate that would make blocking intolerable.
 * A gate that fires wrongly one time in five gets disabled in a week, and then you
 * have neither the gate nor the warning.
 *
 * What DOES block is the fact-forcing gate, one layer earlier, on the action rather
 * than the sentence. That is the right division of labor: police actions strictly,
 * police prose visibly. Making both strict would break the tool; making both advisory
 * would be the old architecture's weakness.
 *
 * It appends a gap list rather than rewriting the response, because silently editing
 * an agent's output hides the failure from the person who most needs to see it.
 */

const fs = require('fs');
const respond = require('../lib/respond');

/** A `file:line` or a fenced/backticked path — the shapes that count as a citation. */
const CITATION = /`[^`\n]*[\w/\\.-]+\.\w+(?::\d+(?:-\d+)?)?[^`\n]*`|\[[^\]]+\]\([^)]+\)|\b[\w/\\.-]+\.\w{1,5}:\d+/;

/**
 * Sentences that assert something about *this* codebase. Deliberately narrow: general
 * statements about a language or a framework are not claims about the repository, and
 * flagging them is exactly how this becomes noise.
 */
const CLAIM_SHAPES = [
  /\bthe\s+\w+\s+(?:service|handler|component|controller|module|repository|store|reducer|middleware)\s+(?:does|handles|returns|calls|reads|writes|validates|dispatches)\b/i,
  /\bthis\s+is\s+(?:handled|implemented|defined|configured|validated)\s+in\b/i,
  /\bthe\s+config(?:uration)?\s+sets\b/i,
  /\bthere\s+(?:is|are)\s+no\s+\w+(?:\s+\w+)?\s+(?:for|in|that)\b/i,
  /\bthe\s+repo(?:sitory)?\s+(?:uses|has|does not have|lacks)\b/i,
];

/** Text that is exempt because it is already marked as unverified, or is not a claim. */
const EXEMPT = [
  /🟡/, /🔴/,
  /\bI (?:will|would|plan to|propose|suggest|recommend)\b/i,
  /\b(?:typically|generally|usually|in most|by convention|in \w+ projects)\b/i,
  /^\s*[-*]\s*\[[ x]\]/,
];

function isFenced(lines, index) {
  let fenced = false;
  for (let i = 0; i < index; i += 1) {
    if (/^\s*```/.test(lines[i])) fenced = !fenced;
  }
  return fenced;
}

/** Extract the assistant's last message from the transcript, if one is available. */
function lastAssistantText(transcriptPath) {
  if (!transcriptPath || !fs.existsSync(transcriptPath)) return '';
  let lines;
  try {
    lines = fs.readFileSync(transcriptPath, 'utf8').split('\n').filter(Boolean);
  } catch { return ''; }

  for (let i = lines.length - 1; i >= 0; i -= 1) {
    let entry;
    try { entry = JSON.parse(lines[i]); } catch { continue; }
    const message = entry.message || entry;
    if (message.role !== 'assistant') continue;
    const content = message.content;
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
      const text = content.filter((c) => c && c.type === 'text').map((c) => c.text).join('\n');
      if (text.trim()) return text;
    }
  }
  return '';
}

function audit(text) {
  const lines = String(text || '').split('\n');
  const gaps = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.trim() || isFenced(lines, i)) continue;
    if (EXEMPT.some((re) => re.test(line))) continue;
    if (!CLAIM_SHAPES.some((re) => re.test(line))) continue;
    if (CITATION.test(line)) continue;
    gaps.push({ line: i + 1, text: line.trim().slice(0, 160) });
  }
  return gaps;
}

async function run(ctx) {
  const text = lastAssistantText(ctx.transcriptPath);
  if (!text) return respond.allow();

  const gaps = audit(text);
  if (!gaps.length) return respond.allow();

  const shown = gaps.slice(0, 6);
  const lines = [
    `**Citation gaps:** ${gaps.length} claim(s) about this codebase shipped without a \`file:line\`.`,
    '',
    ...shown.map((g) => `  - "${g.text}"`),
  ];
  if (gaps.length > shown.length) lines.push(`  - …and ${gaps.length - shown.length} more`);
  lines.push(
    '',
    'Either open the file and cite it, or downgrade the claim to 🔴 assumed and say what would',
    'confirm it. Negative claims need evidence too — "there is no handler for X" is a claim about',
    'this codebase and gets challenged far less often than it should.',
  );
  return respond.inform(lines.join('\n'));
}

module.exports = { run, audit, lastAssistantText, CITATION, CLAIM_SHAPES };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('Stop', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
