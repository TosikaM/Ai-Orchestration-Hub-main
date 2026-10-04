'use strict';
/**
 * The redaction engine. Reads config/redaction-patterns.json — the same file the
 * Python CLI and the validator read, because a taxonomy that exists twice is a
 * taxonomy that disagrees with itself within a month (P6).
 *
 * Calibration, stated because it is the part that is actually hard: a gate that cries
 * wolf gets ignored, and an ignored gate is worse than no gate because it manufactures
 * a false sense of coverage. Only genuinely-secret credentials are HIGH. Stripe
 * publishable keys, Google AIza keys, JWTs, and env-style assignments are MEDIUM —
 * they are context-variable and produce false positives at a rate that would train
 * people to click through.
 *
 * There is intentionally NO key that disables HIGH blocking.
 */

const config = require('./config');

const EXIT = { CLEAN: 0, MEDIUM: 2, HIGH: 3 };

let compiled = null;

function compile() {
  if (compiled) return compiled;
  const data = config.redactionPatterns();
  if (!data) {
    // Fail closed on the *engine*, fail open on the scan: with no taxonomy we cannot
    // claim a string is clean, so we say so rather than returning an empty finding list.
    compiled = { unavailable: true, patterns: [], suppressions: [] };
    return compiled;
  }
  compiled = {
    unavailable: false,
    patterns: (data.patterns || []).map((p) => ({
      ...p,
      re: new RegExp(p.regex, p.regex.startsWith('^') ? 'gm' : 'g'),
      nearRe: p.nearRegex ? new RegExp(p.nearRegex, 'i') : null,
    })),
    suppressions: (data.suppressions || []).map((s) => ({
      ...s,
      re: new RegExp(s.regex, 'i'),
    })),
    sinks: data.sinks || {},
  };
  return compiled;
}

function lineOf(text, index) {
  let line = 1;
  for (let i = 0; i < index && i < text.length; i += 1) {
    if (text[i] === '\n') line += 1;
  }
  return line;
}

function suppressed(engine, pattern, matchedSpan, filePath) {
  for (const s of engine.suppressions) {
    if (s.appliesToTiers && !s.appliesToTiers.includes(pattern.tier)) continue;
    if (s.scope === 'path') {
      if (filePath && s.re.test(String(filePath))) return s.id;
    } else if (s.re.test(matchedSpan)) {
      return s.id;
    }
  }
  return null;
}

/**
 * Scan a string. Returns { findings, highest, unavailable }.
 * `filePath` is optional and only used by path-scoped suppressions.
 */
function scan(text, filePath) {
  const engine = compile();
  if (engine.unavailable) {
    return { unavailable: true, findings: [], highest: null };
  }
  const findings = [];
  const source = String(text || '');

  for (const pattern of engine.patterns) {
    pattern.re.lastIndex = 0;
    let match;
    while ((match = pattern.re.exec(source)) !== null) {
      if (match[0].length === 0) { pattern.re.lastIndex += 1; continue; }
      const span = match[1] !== undefined ? match[1] : match[0];

      // Proximity gating keeps high-entropy shapes (a 40-char base64 blob) from
      // firing unless the surrounding text says what they are.
      if (pattern.nearRe) {
        const window = pattern.nearWindow || 120;
        const from = Math.max(0, match.index - window);
        const context = source.slice(from, match.index + match[0].length + window);
        if (!pattern.nearRe.test(context)) continue;
      }

      const reason = suppressed(engine, pattern, match[0], filePath);
      if (reason) continue;

      findings.push({
        id: pattern.id,
        tier: pattern.tier,
        category: pattern.category,
        description: pattern.description,
        line: lineOf(source, match.index),
        preview: span.length > 12 ? `${span.slice(0, 4)}…${span.slice(-2)}` : '…',
        autoRedactable: Boolean(pattern.autoRedactable),
        redactToken: pattern.redactToken || '<REDACTED>',
        start: match.index,
        length: match[0].length,
        span,
      });
    }
  }

  const order = { HIGH: 3, MEDIUM: 2, LOW: 1 };
  const highest = findings.reduce(
    (acc, f) => (acc === null || order[f.tier] > order[acc] ? f.tier : acc),
    null,
  );
  return { unavailable: false, findings, highest };
}

/** Replace every auto-redactable finding with its token. Non-auto findings are left alone. */
function autoRedact(text) {
  const { findings } = scan(text);
  const replaceable = findings
    .filter((f) => f.autoRedactable)
    .sort((a, b) => b.start - a.start);
  let out = String(text || '');
  for (const f of replaceable) {
    out = out.slice(0, f.start) + out.slice(f.start).replace(f.span, f.redactToken);
  }
  return out;
}

function exitCodeFor(highest) {
  if (highest === 'HIGH') return EXIT.HIGH;
  if (highest === 'MEDIUM') return EXIT.MEDIUM;
  return EXIT.CLEAN;
}

/**
 * The write-site guard. Throws on HIGH; that is the whole point.
 *
 * Memory is re-injected into future prompts, which makes the memory store an
 * injection surface as well as a storage surface. A resolution note that says
 * "ignore previous instructions" will be read back to an agent as context in three
 * months, in a different repository, with no human in the loop.
 */
const INJECTION_MARKERS = new RegExp(
  '(?:^|\\n)\\s*(?:ignore\\s+(?:all\\s+)?(?:previous|prior|above)'
  + '|disregard\\s+(?:the\\s+)?(?:above|system|instructions)'
  + '|you\\s+are\\s+now\\b'
  + '|new\\s+(?:system\\s+)?instructions?\\s*:'
  + '|</?(?:system|instructions?)>'
  + '|BEGIN\\s+SYSTEM\\s+PROMPT)',
  'i',
);

function hasInjection(text) {
  return INJECTION_MARKERS.test(String(text || ''));
}

function guardFreeText(field, value, { allowMedium = true } = {}) {
  if (hasInjection(value)) {
    throw new Error(
      `${field}: refusing to persist prompt-injection markers. Stored text is re-read `
      + 'as context in future sessions, so this would be a delayed instruction, not data.',
    );
  }
  const { findings, unavailable } = scan(value);
  if (unavailable) {
    throw new Error(
      `${field}: redaction taxonomy unavailable (config/redaction-patterns.json). `
      + 'Refusing the write rather than claiming the text is clean.',
    );
  }
  const high = findings.filter((f) => f.tier === 'HIGH');
  if (high.length) {
    throw new Error(
      `${field}: refusing to persist ${high.length} HIGH-tier secret(s): `
      + `${high.map((f) => `${f.id}@line ${f.line}`).join(', ')}`,
    );
  }
  const medium = findings.filter((f) => f.tier === 'MEDIUM');
  if (medium.length && !allowMedium) {
    throw new Error(
      `${field}: ${medium.length} MEDIUM-tier finding(s) require confirmation: `
      + `${medium.map((f) => f.id).join(', ')}`,
    );
  }
  return { findings };
}

module.exports = {
  EXIT,
  scan,
  autoRedact,
  exitCodeFor,
  hasInjection,
  guardFreeText,
  INJECTION_MARKERS,
};
