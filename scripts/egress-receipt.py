#!/usr/bin/env python3
"""
The egress ledger: a hash-chained, content-free record of attempted off-machine sends.

  python scripts/egress-receipt.py write --sink hub.clone --bytes-from <file> --note "..."
  python scripts/egress-receipt.py verify
  python scripts/egress-receipt.py tail [-n 20]

THREAT MODEL, STATED PLAINLY
-----------------------------
This is **forensic observability, not an exfiltration control.** It records what was
attempted so an accident is auditable. A determined leaker bypasses it trivially. What
it catches is carelessness — which is the 99% case, and the case the redaction gate is
also aimed at.

Writing that sentence down matters as much as the code. A ledger described as a security
control will be trusted as one, and then somebody will decide a second control is
unnecessary because "we have the ledger."

THREE PROPERTIES
----------------
- **Receipt before send.** Fail-closed sinks refuse the send when the receipt cannot be
  written; fail-open sinks warn and proceed. Which is which is declared in
  config/redaction-patterns.json -> sinks, not decided here.
- **Content-free.** A sha256 of the exact bytes plus a byte count. Never payload text.
  A ledger that stored payloads would itself become the leak.
- **Tamper-evident.** Each line carries `prev` = sha256 of the previous raw line, so a
  deletion or an edit is detectable without making the log immutable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import config, state_path, utc_now  # noqa: E402


def ledger_path() -> Path:
    return state_path("security", "egress.jsonl")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def last_line_hash(path: Path) -> str:
    if not path.exists():
        return "genesis"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return "genesis"
    return sha256_bytes(lines[-1].encode("utf-8"))


def sink_polarity(sink: str) -> str:
    sinks = (config("redaction-patterns.json", {}) or {}).get("sinks", {})
    return (sinks.get(sink) or {}).get("polarity", "fail-open")


def cmd_write(args) -> int:
    path = ledger_path()

    if args.bytes_from:
        source = Path(args.bytes_from)
        if not source.exists():
            print(f"no such file: {source}")
            return 1
        data = source.read_bytes()
    elif args.text is not None:
        data = args.text.encode("utf-8")
    else:
        data = b""

    record = {
        "sink": args.sink,
        "polarity": sink_polarity(args.sink),
        "destination": args.destination or "",
        "byteCount": len(data),
        "sha256": sha256_bytes(data) if data else None,
        "note": args.note or "",
        "at": utc_now(),
        "prev": last_line_hash(path),
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # not all filesystems support it; the ledger is still written
    except OSError as exc:
        if record["polarity"] == "fail-closed":
            print(f"RECEIPT FAILED and '{args.sink}' is fail-closed: {exc}")
            print("The send must not proceed. A fail-closed sink without a receipt is exactly")
            print("the case this ledger exists to make impossible.")
            return 3
        print(f"WARNING: receipt failed for fail-open sink '{args.sink}': {exc}", file=sys.stderr)
        return 0

    print(f"receipt written: {args.sink} · {record['byteCount']} bytes · "
          f"{(record['sha256'] or '')[:16]}… · {record['polarity']}")
    return 0


def cmd_verify(args) -> int:
    path = ledger_path()
    if not path.exists():
        print("no ledger yet — nothing has been sent off-machine, or nothing was recorded")
        return 0
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    prev = "genesis"
    for number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            print(f"CHAIN BROKEN at line {number}: unparseable")
            return 1
        if record.get("prev") != prev:
            print(f"CHAIN BROKEN at line {number}: prev hash mismatch")
            print("  A line was edited or removed. The ledger is tamper-evident, not")
            print("  tamper-proof — this is the evidence, not the prevention.")
            return 1
        prev = sha256_bytes(line.encode("utf-8"))
    print(f"chain intact: {len(lines)} receipt(s) in {path}")
    return 0


def cmd_tail(args) -> int:
    path = ledger_path()
    if not path.exists():
        print("no ledger yet")
        return 0
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for line in lines[-args.n:]:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        print(f"{record.get('at','?'):<22} {record.get('sink',''):<18} "
              f"{record.get('byteCount',0):>9}B  {record.get('destination','')} "
              f"{record.get('note','')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Egress ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("write")
    p.add_argument("--sink", required=True)
    p.add_argument("--destination", default="")
    p.add_argument("--bytes-from", default=None)
    p.add_argument("--text", default=None)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_write)

    sub.add_parser("verify").set_defaults(func=cmd_verify)
    p = sub.add_parser("tail"); p.add_argument("-n", type=int, default=20); p.set_defaults(func=cmd_tail)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
