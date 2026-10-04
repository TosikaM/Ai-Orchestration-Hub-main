'use strict';
/**
 * A small, dependency-free glob matcher.
 *
 * The hook runtime must start in tens of milliseconds and must work from a plugin
 * cache directory with no node_modules. Pulling in a glob library for the handful of
 * patterns in an exempt list would trade that for convenience we do not need.
 *
 * Supports: `*` (no separator), `**` (any depth), `?`, `{a,b}`, and character classes.
 * Matching is case-insensitive and separator-agnostic, because half of this system
 * runs on Windows and half in CI on Linux, and a gate that silently stops matching
 * when the separator flips is the worst kind of gate.
 */

function normalize(p) {
  return String(p || '').replace(/\\/g, '/').replace(/^\.\//, '');
}

function toRegExp(pattern) {
  const glob = normalize(pattern);
  let out = '';
  for (let i = 0; i < glob.length; i += 1) {
    const ch = glob[i];
    if (ch === '*') {
      if (glob[i + 1] === '*') {
        // `**/` consumes any number of path segments, including none.
        if (glob[i + 2] === '/') { out += '(?:.*/)?'; i += 2; } else { out += '.*'; i += 1; }
      } else {
        out += '[^/]*';
      }
    } else if (ch === '?') {
      out += '[^/]';
    } else if (ch === '{') {
      const close = glob.indexOf('}', i);
      if (close === -1) { out += '\\{'; } else {
        const alts = glob.slice(i + 1, close).split(',').map((a) => a.replace(/[.+^${}()|[\]\\]/g, '\\$&'));
        out += `(?:${alts.join('|')})`;
        i = close;
      }
    } else if (ch === '[') {
      const close = glob.indexOf(']', i);
      if (close === -1) { out += '\\['; } else { out += glob.slice(i, close + 1); i = close; }
    } else if ('.+^$()|\\'.includes(ch)) {
      out += `\\${ch}`;
    } else {
      out += ch;
    }
  }
  return new RegExp(`^${out}$`, 'i');
}

const cache = new Map();

function match(filePath, pattern) {
  if (!cache.has(pattern)) cache.set(pattern, toRegExp(pattern));
  const candidate = normalize(filePath);
  const re = cache.get(pattern);
  if (re.test(candidate)) return true;
  // A bare pattern like `**/*.md` should also match a relative path with no leading
  // segments, and a pattern anchored at the repo root should match an absolute path
  // whose tail agrees.
  const segments = candidate.split('/');
  for (let i = 1; i < segments.length; i += 1) {
    if (re.test(segments.slice(i).join('/'))) return true;
  }
  return false;
}

function matchesAny(filePath, patterns) {
  if (!patterns || !patterns.length) return false;
  return patterns.some((p) => p && match(filePath, p));
}

/** Read a comma- or semicolon-separated glob list out of an environment variable. */
function fromEnv(name) {
  const raw = process.env[name];
  if (!raw) return [];
  return raw.split(/[;,]/).map((s) => s.trim()).filter(Boolean);
}

module.exports = { normalize, toRegExp, match, matchesAny, fromEnv };
