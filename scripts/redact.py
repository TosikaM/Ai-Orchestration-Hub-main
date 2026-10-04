#!/usr/bin/env python3
"""
The redaction CLI.

  python scripts/redact.py --text "..."          # scan a string
  python scripts/redact.py --from-file <path>    # scan a file
  python scripts/redact.py --auto-redact <path>  # rewrite auto-redactable findings
  python scripts/redact.py --lint                # ReDoS check on the taxonomy itself
  python scripts/redact.py --json

EXIT CODES (the contract other tools depend on)
  0  clean
  2  MEDIUM findings — confirm with a human
  3  HIGH findings — blocked

SCAN AT THE SINK, NOT BEFORE IT
--------------------------------
Always scan the EXACT bytes that will be written or sent. Write to a temp file, scan
that file, and pass the SAME file onward. Scanning a string and then re-rendering it
reopens a scan-versus-send gap, and that gap is where the interesting failures live.

CALIBRATION IS THE HARD PART
-----------------------------
A gate that cries wolf gets ignored, and an ignored gate is worse than no gate because
it manufactures a false sense of coverage. Only genuinely-secret credentials are HIGH.
Stripe publishable keys, Google AIza keys, JWTs, and env-style assignments are MEDIUM:
they are context-variable and produce false positives at a rate that would train people
to click through.

Repository visibility never promotes a tier. A public repo earns sterner per-finding
confirmation on MEDIUM findings; it does not turn MEDIUM into HIGH.

There is intentionally NO key that disables HIGH blocking.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import config, redact_scan, redaction_patterns  # noqa: E402

EXIT_CLEAN, EXIT_MEDIUM, EXIT_HIGH = 0, 2, 3


def lint_patterns() -> int:
    """
    Catastrophic-backtracking check. Every pattern must be linear-time, because these run
    on every memory write and every context generation — a pathological regex here turns
    a guard into a hang, and a hung guard gets removed.
    """
    _, _, data = redaction_patterns()
    problems = []
    nested_quantifier = re.compile(r"\([^)]*[+*]\)[+*]|\([^)]*\{\d+,\}\)[+*]")
    for pattern in data.get("patterns", []):
        regex = pattern["regex"]
        if nested_quantifier.search(regex):
            problems.append(f"{pattern['id']}: nested unbounded quantifier — {regex}")
        if regex.count("(.*)") > 1 or ".*.*" in regex:
            problems.append(f"{pattern['id']}: multiple unbounded wildcards — {regex}")
        try:
            re.compile(regex)
        except re.error as exc:
            problems.append(f"{pattern['id']}: does not compile — {exc}")
    for suppression in data.get("suppressions", []):
        try:
            re.compile(suppression["regex"])
        except re.error as exc:
            problems.append(f"suppression {suppression['id']}: does not compile — {exc}")

    if problems:
        print(f"REDOS LINT FAILED ({len(problems)}):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"ReDoS lint clean: {len(data.get('patterns', []))} patterns, "
          f"{len(data.get('suppressions', []))} suppressions, all linear-time.")
    return 0


def report(findings: list, as_json: bool, source: str) -> int:
    tiers = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for finding in findings:
        tiers.setdefault(finding["tier"], []).append(finding)

    if as_json:
        print(json.dumps({
            "source": source,
            "findings": [{k: v for k, v in f.items() if k not in ("span", "start")} for f in findings],
            "counts": {tier: len(rows) for tier, rows in tiers.items()},
        }, indent=2))
    else:
        if not findings:
            print(f"{source}: clean")
        else:
            print(f"{source}: {len(findings)} finding(s)\n")
            for tier in ("HIGH", "MEDIUM", "LOW"):
                for finding in tiers[tier]:
                    print(f"  [{tier:<6}] line {finding['line']:<5} {finding['id']:<26} "
                          f"{finding['preview']}  {finding['description']}")
            if tiers["HIGH"]:
                print("\nHIGH findings BLOCK the write or the send. There is no override.")
            elif tiers["MEDIUM"]:
                print("\nMEDIUM findings need a human decision. Auto-redactable ones can be")
                print("rewritten with --auto-redact.")

    if tiers["HIGH"]:
        return EXIT_HIGH
    if tiers["MEDIUM"]:
        return EXIT_MEDIUM
    return EXIT_CLEAN


def auto_redact(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    findings = redact_scan(text, str(path))
    replaceable = sorted(
        [f for f in findings if f["autoRedactable"]],
        key=lambda f: -f["start"],
    )
    if not replaceable:
        print(f"{path}: nothing auto-redactable "
              f"({len(findings)} finding(s), none marked autoRedactable).")
        return report(findings, False, str(path))

    out = text
    for finding in replaceable:
        head, tail = out[:finding["start"]], out[finding["start"]:]
        out = head + tail.replace(finding["span"], finding["redactToken"], 1)
    path.write_text(out, encoding="utf-8")
    print(f"{path}: replaced {len(replaceable)} auto-redactable finding(s).")
    remaining = redact_scan(out, str(path))
    return report(remaining, False, str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Redaction scanner")
    parser.add_argument("--text")
    parser.add_argument("--from-file")
    parser.add_argument("--auto-redact")
    parser.add_argument("--lint", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.lint:
        return lint_patterns()
    if args.auto_redact:
        return auto_redact(Path(args.auto_redact))
    if args.from_file:
        path = Path(args.from_file)
        if not path.exists():
            print(f"no such file: {path}")
            return 1
        return report(redact_scan(path.read_text(encoding="utf-8"), str(path)), args.json, str(path))
    if args.text is not None:
        return report(redact_scan(args.text), args.json, "<text>")

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
