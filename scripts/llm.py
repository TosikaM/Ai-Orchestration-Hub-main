#!/usr/bin/env python3
"""
The LLM gateway — the headless path to the model.

  python scripts/llm.py ask "<prompt>" [--agent developer] [--skill quality-sentinel]
  python scripts/llm.py ask --from-file prompt.md --agent analyst --json
  python scripts/llm.py models          # resolved routing table
  python scripts/llm.py cost [--since ISO]
  python scripts/llm.py doctor          # can we reach a model at all?

WHAT THIS IS, AND — MORE IMPORTANTLY — WHAT IT IS NOT
-----------------------------------------------------
A review of the earlier architecture said the biggest gap was that Claude itself was
never defined: no model selection, no auth story, no retries, no cost tracking, no
prompt versioning. That was true, and it is worth being precise about how v3.1 answers
it, because the answer is not one gateway for everything.

There are two paths to the model, and conflating them produces a worse system:

  THE INTERACTIVE PATH — a developer in a Claude Code session.
      There is no gateway here and there should not be one. Claude Code owns the model,
      the auth, the retries and the context window. Inserting a proxy would mean
      re-implementing a working runtime in order to sit in front of it, which is exactly
      the mistake the v3.0.0 architecture made with skill loading and command routing.
      This system contributes skills, agents and hooks to that session and otherwise
      stays out of the way. It deliberately does NOT override the user's model: silently
      swapping somebody's model mid-session is a surprising thing to do.

  THE HEADLESS PATH — evals, CI, batch runs, anything with no human attached.
      This file. Here every concern the review named is real, because nothing else is
      handling them.

So the gateway is narrow on purpose. It is not an abstraction layer over "an LLM"; it is
the disciplined way this system makes an unattended call.

WHAT IT GUARANTEES ON EVERY CALL
--------------------------------
  1. Model resolved from policy, never from a hardcoded string, and RECORDED with the
     result. A score attached to an unknown model is not a measurement.
  2. Redaction scan of the outgoing prompt. A HIGH-tier finding aborts the call.
  3. An egress receipt written BEFORE the send. This sink is fail-closed: no receipt,
     no send.
  4. Bounded retries with exponential backoff, and NO cross-family fallback.
  5. Token accounting, and cost only when a price table has actually been filled in.
  6. A prompt fingerprint, so a behavioural change can be traced to the text that caused
     it rather than argued about.

WHY THERE IS NO FALLBACK MODEL
------------------------------
`model.fallback` is null in policy and this gateway honours it. When the chosen model is
unavailable the call FAILS and says so. A silent downgrade produces a result attributed
to a model that did not generate it, which quietly corrupts every eval score and every
comparison built on them — and the corruption is invisible, because the output still
looks like an answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, config, read_json, redact_scan, state_path, utc_now  # noqa: E402

LEDGER = "llm.jsonl"
MIN_INTERVAL_SECONDS = 0.25


def policy_model_block() -> dict:
    doc = config("policy.json", {}) or {}
    return ((doc.get("defaults") or {}).get("model")) or {}


def resolve_model(agent: str | None, skill: str | None) -> tuple:
    """
    Routing is by SKILL first, then agent, then the default.

    Skill beats agent because the cost lever lives at the skill level: `structural-graph`
    is mechanical and high-volume whatever agent invokes it, and `security-review` needs
    the capable tier whoever asks for it. Routing on the caller instead of the work is
    how a cheap tier ends up doing the judgement.
    """
    block = policy_model_block()
    routing = block.get("routing") or {}
    if skill and skill in routing:
        return routing[skill], f"routing.{skill}"
    if agent and agent in routing:
        return routing[agent], f"routing.{agent}"
    return block.get("default"), "model.default"


def pricing_for(model: str) -> dict | None:
    table = config("model-pricing.json", {}) or {}
    entry = (table.get("models") or {}).get(model)
    if not entry:
        return None
    if entry.get("input") is None or entry.get("output") is None:
        return None
    return entry


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def ledger_path() -> Path:
    return state_path("llm", LEDGER)


def write_egress_receipt(prompt: str, model: str, note: str) -> bool:
    """
    Receipt before send, and this sink is fail-closed. Returns False when the receipt
    could not be written, and the caller must abort — a send with no record is exactly
    what the ledger exists to make impossible.
    """
    script = ROOT / "scripts" / "egress-receipt.py"
    if not script.exists():
        return False
    tmp = state_path("llm", "outgoing.tmp")
    try:
        # Scan and receipt the EXACT bytes that will be sent. Writing to a temp file and
        # receipting that file — rather than receipting a string and re-rendering it —
        # closes the scan-versus-send gap where the two can differ.
        tmp.write_text(prompt, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script), "write",
             "--sink", "llm.headless",
             "--destination", model,
             "--bytes-from", str(tmp),
             "--note", note],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


_last_call = [0.0]


def rate_limit() -> None:
    elapsed = time.time() - _last_call[0]
    if elapsed < MIN_INTERVAL_SECONDS:
        time.sleep(MIN_INTERVAL_SECONDS - elapsed)
    _last_call[0] = time.time()


TOKEN_HINT = re.compile(r'"(?:input_tokens|output_tokens)"\s*:\s*(\d+)')


def call_model(prompt: str, model: str, timeout: int) -> dict:
    """
    One invocation of the headless CLI. Returns a dict; never raises for a model-side
    failure, because the caller needs the reason recorded rather than a traceback.
    """
    command = ["claude", "-p", prompt]
    if model:
        command = ["claude", "--model", model, "-p", prompt]

    started = time.time()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        return {
            "ok": completed.returncode == 0,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "exitCode": completed.returncode,
            "durationMs": int((time.time() - started) * 1000),
            "reason": None if completed.returncode == 0 else f"exit {completed.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "", "exitCode": -1,
                "durationMs": int((time.time() - started) * 1000),
                "reason": f"timeout after {timeout}s"}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "", "exitCode": -1,
                "durationMs": 0,
                "reason": "the `claude` CLI is not on PATH — install Claude Code, or run "
                          "the interactive path instead"}


def ask(prompt: str, agent: str | None, skill: str | None, purpose: str) -> dict:
    block = policy_model_block()
    model, routed_by = resolve_model(agent, skill)
    max_retries = int(block.get("maxRetries", 3))
    timeout = int(block.get("timeoutSeconds", 300))
    fallback = block.get("fallback")

    record = {
        "at": utc_now(),
        "agent": agent,
        "skill": skill,
        "purpose": purpose,
        "model": model,
        "routedBy": routed_by,
        "promptFingerprint": fingerprint(prompt),
        "promptChars": len(prompt),
    }

    # 1. Redaction BEFORE anything leaves. HIGH aborts; there is no override.
    try:
        findings = redact_scan(prompt)
    except RuntimeError as exc:
        record.update(ok=False, reason=f"redaction taxonomy unavailable: {exc}")
        append_ledger(record)
        return record

    high = [f for f in findings if f["tier"] == "HIGH"]
    if high:
        record.update(
            ok=False,
            reason=f"aborted: {len(high)} HIGH-tier finding(s) in the prompt: "
                   + ", ".join(f"{f['id']}@line {f['line']}" for f in high),
            redactionFindings=len(findings),
        )
        append_ledger(record)
        return record
    record["redactionFindings"] = len(findings)

    # 2. Receipt before send. Fail-closed.
    if not write_egress_receipt(prompt, model or "default", purpose):
        record.update(ok=False, reason="egress receipt could not be written; this sink is "
                                       "fail-closed, so the call was not made")
        append_ledger(record)
        return record

    # 3. Bounded retries. No cross-family fallback.
    attempts = []
    for attempt in range(1, max_retries + 1):
        rate_limit()
        result = call_model(prompt, model, timeout)
        attempts.append({"attempt": attempt, "ok": result["ok"],
                         "reason": result["reason"], "durationMs": result["durationMs"]})
        if result["ok"]:
            record.update(
                ok=True, reason=None, attempts=attempts,
                durationMs=result["durationMs"],
                outputChars=len(result["stdout"]),
                output=result["stdout"],
            )
            annotate_cost(record, prompt, result["stdout"])
            append_ledger(record)
            return record

        # A missing CLI will not become present on a retry.
        if result["reason"] and "not on PATH" in result["reason"]:
            break
        if attempt < max_retries:
            time.sleep(min(2 ** attempt, 30))

    record.update(ok=False, attempts=attempts,
                  reason=attempts[-1]["reason"] if attempts else "no attempt made")
    if fallback:
        record["fallbackNote"] = (
            f"policy declares a fallback ({fallback}) but this gateway does not use one: a "
            "result attributed to a model that did not produce it corrupts every score built "
            "on it, invisibly."
        )
    append_ledger(record)
    return record


def annotate_cost(record: dict, prompt: str, output: str) -> None:
    """
    Tokens are reported as an ESTIMATE and labelled as one; cost only when a price table
    has been filled in. Reporting a currency figure derived from an unset table would be
    the exact class of invented number this project refuses elsewhere.
    """
    per_token = (config("token-budgets.json", {}) or {}).get("charsPerTokenEstimate", 4)
    record["estimatedInputTokens"] = -(-len(prompt) // per_token)
    record["estimatedOutputTokens"] = -(-len(output) // per_token)
    record["tokenEstimateBasis"] = f"chars/{per_token} — an estimate, not a measurement"

    price = pricing_for(record.get("model") or "")
    if not price:
        record["cost"] = None
        record["costNote"] = (
            "not configured — config/model-pricing.json ships with null prices on purpose. "
            "Fill it from the official pricing page and commit the date it was read."
        )
        return
    cost = (record["estimatedInputTokens"] / 1_000_000) * price["input"] \
        + (record["estimatedOutputTokens"] / 1_000_000) * price["output"]
    record["cost"] = round(cost, 6)
    record["costNote"] = "derived from estimated tokens — an estimate of an estimate"


def append_ledger(record: dict) -> None:
    path = ledger_path()
    slim = {k: v for k, v in record.items() if k != "output"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(slim) + "\n")
    except OSError:
        pass  # never fail a call because the ledger could not be appended


def cmd_ask(args) -> int:
    if args.from_file:
        source = Path(args.from_file)
        if not source.exists():
            print(f"no such file: {source}")
            return 1
        prompt = source.read_text(encoding="utf-8")
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = sys.stdin.read()

    record = ask(prompt, args.agent, args.skill, args.purpose)

    if args.json:
        print(json.dumps(record, indent=2))
        return 0 if record.get("ok") else 1

    if record.get("ok"):
        print(record["output"])
        print(f"\n--- {record['model']} via {record['routedBy']} · "
              f"{record['durationMs']}ms · ~{record['estimatedInputTokens']}+"
              f"{record['estimatedOutputTokens']} tokens (estimate)", file=sys.stderr)
        return 0

    print(f"CALL FAILED: {record.get('reason')}", file=sys.stderr)
    return 1


def cmd_models(args) -> int:
    block = policy_model_block()
    print("Headless model routing (the interactive path is NOT affected)\n")
    print(f"  default          {block.get('default')}")
    print(f"  maxRetries       {block.get('maxRetries')}")
    print(f"  timeoutSeconds   {block.get('timeoutSeconds')}")
    print(f"  fallback         {block.get('fallback')}  <- null by design")
    routing = block.get("routing") or {}
    if routing:
        print("\n  routing (skill or agent -> model):")
        for key, model in routing.items():
            print(f"    {key:<26} {model}")
    print(f"\n  {block.get('routingRationale', '')}")

    table = config("model-pricing.json", {}) or {}
    configured = [m for m, v in (table.get("models") or {}).items() if v.get("input") is not None]
    print(f"\n  pricing configured for {len(configured)} model(s)"
          + ("" if configured else " — cost reporting will say 'not configured'"))
    return 0


def cmd_cost(args) -> int:
    path = ledger_path()
    if not path.exists():
        print("No headless calls recorded yet.")
        return 0
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if args.since and row.get("at", "") < args.since:
            continue
        rows.append(row)

    if not rows:
        print("No calls in that window.")
        return 0

    ok = [r for r in rows if r.get("ok")]
    tokens_in = sum(r.get("estimatedInputTokens", 0) for r in ok)
    tokens_out = sum(r.get("estimatedOutputTokens", 0) for r in ok)
    costed = [r for r in ok if r.get("cost") is not None]

    print(f"{len(rows)} call(s), {len(ok)} successful\n")
    print(f"  estimated tokens   {tokens_in:,} in · {tokens_out:,} out")
    if costed:
        print(f"  estimated cost     {sum(r['cost'] for r in costed):.4f} "
              f"across {len(costed)} priced call(s)")
    else:
        print("  cost               not configured — config/model-pricing.json has null prices")
        print("                     Tokens above are the honest half of the answer.")

    by_model = {}
    for r in ok:
        by_model.setdefault(r.get("model") or "?", 0)
        by_model[r["model"] if r.get("model") else "?"] += 1
    print("\n  by model:")
    for model, count in sorted(by_model.items(), key=lambda kv: -kv[1]):
        print(f"    {model:<32} {count}")

    failed = [r for r in rows if not r.get("ok")]
    if failed:
        print(f"\n  {len(failed)} failure(s):")
        for r in failed[-5:]:
            print(f"    {r.get('at')}  {str(r.get('reason'))[:90]}")
    return 0


def cmd_doctor(args) -> int:
    problems = []
    block = policy_model_block()
    if not block.get("default"):
        problems.append(("no default model in policy", "set defaults.model.default in config/policy.json"))

    try:
        redact_scan("probe")
    except RuntimeError as exc:
        problems.append((f"redaction taxonomy unavailable: {exc}",
                         "restore config/redaction-patterns.json — the gateway refuses to send without it"))

    result = subprocess.run(["where" if os.name == "nt" else "which", "claude"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        problems.append(("the `claude` CLI is not on PATH",
                         "npm install -g @anthropic-ai/claude-code"))
    else:
        print(f"  claude CLI: {result.stdout.strip().splitlines()[0]}")

    if not (ROOT / "scripts" / "egress-receipt.py").exists():
        problems.append(("scripts/egress-receipt.py missing",
                         "this sink is fail-closed; without it no headless call can be made"))

    print(f"\nLLM gateway — {'HEALTHY' if not problems else f'{len(problems)} problem(s)'}")
    for problem, fix in problems:
        print(f"  PROBLEM  {problem}")
        print(f"           fix: {fix}")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless LLM gateway")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ask")
    p.add_argument("prompt", nargs="?")
    p.add_argument("--from-file")
    p.add_argument("--agent")
    p.add_argument("--skill")
    p.add_argument("--purpose", default="headless")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ask)

    sub.add_parser("models").set_defaults(func=cmd_models)
    p = sub.add_parser("cost"); p.add_argument("--since"); p.set_defaults(func=cmd_cost)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
