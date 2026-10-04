#!/usr/bin/env node
'use strict';
/**
 * PreToolUse (mcp__*): MCP health gating.
 *
 * THE GAP THIS CLOSES
 *
 * `config/tool-registry.json` declares an `optional` block with a carefully-written
 * fallback for every connector: "Emit stories as Markdown", "do not claim the specs
 * were executed". Good design, and entirely declarative — nothing probes whether the
 * server is up. So when a connector is down mid-pipeline, the phase fails with an MCP
 * error, the error-recovery table says "MCP timeout -> retry", and the fallback that
 * was carefully specified is never reached, because nothing ever decides it is time to
 * use it.
 *
 * This turns a repeated timeout into a single fast failure carrying the declared
 * fallback, which is what makes the fallback reachable at all.
 *
 * Health is recorded by the tool-failure path (`markUnhealthy`) and expires on a timer,
 * so a server that recovers is retried without anybody clearing state by hand.
 */

const respond = require('../lib/respond');
const state = require('../../../lib/state');
const config = require('../../../lib/config');

function healthPath() {
  return state.statePath('state', 'mcp-health.json');
}

function loadHealth() {
  return state.readJson(healthPath(), { version: 1, servers: {} });
}

function saveHealth(value) {
  state.writeJsonAtomic(healthPath(), value);
}

/** `mcp__atlassian__create_issue` -> `atlassian` */
function serverOf(toolName) {
  const match = /^mcp__([^_]+(?:_[^_]+)*?)__/.exec(String(toolName || ''));
  return match ? match[1] : null;
}

function policy() {
  const registry = config.toolRegistry();
  return (registry && registry.healthPolicy) || { recheckAfterSeconds: 120, markUnhealthyAfterFailures: 1 };
}

function fallbackFor(server) {
  const registry = config.toolRegistry();
  const optional = (registry && registry.optional) || {};
  const entry = optional[server];
  return entry && entry.fallback ? entry.fallback : null;
}

function markUnhealthy(server, reason) {
  const health = loadHealth();
  const existing = health.servers[server] || { failures: 0 };
  health.servers[server] = {
    failures: (existing.failures || 0) + 1,
    unhealthySince: Date.now(),
    reason: String(reason || '').slice(0, 300),
  };
  saveHealth(health);
  return health.servers[server];
}

function markHealthy(server) {
  const health = loadHealth();
  delete health.servers[server];
  saveHealth(health);
}

function isUnhealthy(server) {
  const health = loadHealth();
  const entry = health.servers[server];
  if (!entry) return null;
  const ttl = (policy().recheckAfterSeconds || 120) * 1000;
  if (Date.now() - (entry.unhealthySince || 0) > ttl) {
    markHealthy(server);
    return null;
  }
  if ((entry.failures || 0) < (policy().markUnhealthyAfterFailures || 1)) return null;
  return entry;
}

async function run(ctx) {
  const server = serverOf(ctx.toolName);
  if (!server) return respond.allow();

  const unhealthy = isUnhealthy(server);
  if (!unhealthy) return respond.allow();

  const fallback = fallbackFor(server);
  const seconds = Math.round((Date.now() - unhealthy.unhealthySince) / 1000);
  return respond.deny([
    '[MCP Health]',
    '',
    `The "${server}" connector was marked unhealthy ${seconds}s ago after `
      + `${unhealthy.failures} failure(s): ${unhealthy.reason || 'no detail recorded'}.`,
    '',
    fallback
      ? `Take the declared fallback instead: ${fallback}`
      : 'No fallback is declared for this connector in config/tool-registry.json. Report the '
        + 'phase as blocked with this reason rather than retrying.',
    '',
    `It will be retried automatically after ${policy().recheckAfterSeconds || 120}s. Retrying `
      + 'now just spends the timeout again.',
  ].join('\n'));
}

module.exports = { run, serverOf, markUnhealthy, markHealthy, isUnhealthy, loadHealth };

if (require.main === module) {
  const stdin = require('../lib/stdin');
  stdin.readPayload().then(async ({ payload }) => {
    const result = await run(stdin.normalize(payload));
    const out = respond.serialize('PreToolUse', result);
    if (out) process.stdout.write(out);
    process.exit(0);
  });
}
