#!/usr/bin/env python3
"""
Measures the discovery footprint and rewrites the derivation block in
config/token-budgets.json. This is the ratchet.

  python scripts/measure-discovery-budget.py            # measure and record
  python scripts/measure-discovery-budget.py --check    # exit 1 if the record is stale
  python scripts/measure-discovery-budget.py --json     # machine-readable

WHY A RATCHET AND NOT JUST A CEILING
------------------------------------
A ceiling with no recorded provenance has three problems, and all three are the kind
that only show up months later:

  1. The number has no history. Nobody knows how 4,000 was derived, when, or against
     what set of skills — so the first person who needs 300 more bytes edits the
     constant, and the ceiling is gone with no trace in the diff that says so.
  2. A new skill defaults to allowed. Add a seventeenth and it passes silently until
     the aggregate happens to trip. There is no "this skill has never been budgeted"
     state.
  3. Nothing tests the test. If `aggregateFrontmatterBytes` becomes the string "4000"
     after a bad merge, the comparison stops comparing rather than failing.

Recording `measuredValue`, `measuredAt`, and `dominantSkill` in the same commit as the
change turns every increase into a visible line in a diff, and turns every decrease
into a locked-in win.

THE PROTOCOL
------------
  Growth that is a real feature   → re-measure, commit the derivation block WITH the
                                    change. The reviewer sees the cost.
  Accidental growth               → do not re-measure. Fix the frontmatter: trigger,
                                    USE FOR, and NOT FOR text belongs in '## Routing'.
  A reduction landed              → re-measure immediately so the recorded value
                                    ratchets DOWN and the win cannot silently erode.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, measure_discovery, read_json, write_json  # noqa: E402

BUDGETS = ROOT / "config" / "token-budgets.json"


def main() -> int:
    check_only = "--check" in sys.argv
    as_json = "--json" in sys.argv

    budgets = read_json(BUDGETS)
    if budgets is None:
        print(f"cannot read {BUDGETS}")
        return 1

    discovery = budgets.setdefault("discovery", {})
    derivation = discovery.setdefault("derivation", {})

    total, per_skill = measure_discovery(ROOT)
    if not per_skill:
        print("No skills found under skills/. Nothing to measure.")
        return 1

    ceiling = discovery.get("aggregateFrontmatterBytes")
    if not isinstance(ceiling, int) or isinstance(ceiling, bool):
        print(
            f"discovery.aggregateFrontmatterBytes is {type(ceiling).__name__}, not an int. "
            f"The ceiling is disabled, not merely wrong. Fix it before measuring."
        )
        return 1

    dominant, dominant_size = max(per_skill, key=lambda pair: pair[1])
    headroom = round((ceiling - total) / ceiling * 100, 1)
    recorded = derivation.get("measuredValue")

    if as_json:
        print(json.dumps({
            "total": total,
            "ceiling": ceiling,
            "headroomPercent": headroom,
            "skillCount": len(per_skill),
            "dominantSkill": dominant,
            "dominantBytes": dominant_size,
            "recorded": recorded,
            "stale": recorded != total,
            "perSkill": [{"skill": n, "bytes": b} for n, b in sorted(per_skill, key=lambda p: -p[1])],
        }, indent=2))
        return 0 if recorded == total and total <= ceiling else 1

    if check_only:
        if recorded != total:
            print(
                f"STALE: token-budgets.json records {recorded}B, actual is {total}B.\n"
                f"       {derivation.get('ratchetProtocol', '')}"
            )
            return 1
        print(f"discovery footprint current: {total}B / {ceiling}B ({headroom}% headroom)")
        return 0 if total <= ceiling else 1

    derivation.update({
        "measuredAt": date.today().isoformat(),
        "measuredValue": total,
        "skillCount": len(per_skill),
        "dominantSkill": f"{dominant} ({dominant_size}B)",
        "headroomPercent": headroom,
    })
    write_json(BUDGETS, budgets)

    print(f"Measured {len(per_skill)} skills: {total}B / {ceiling}B ({headroom}% headroom)")
    print(f"Dominant: {dominant} at {dominant_size}B\n")
    print(f"{'skill':<28}{'bytes':>8}")
    print("-" * 36)
    for name, size in sorted(per_skill, key=lambda pair: -pair[1]):
        flag = "  <-- over per-skill cap" if size > discovery.get("perSkillFrontmatterBytes", 240) else ""
        print(f"{name:<28}{size:>8}{flag}")

    if total > ceiling:
        print("\nOVER CEILING. Move trigger text into the '## Routing' body block.")
        print("Do not raise the ceiling to make this pass unless the growth is a real feature —")
        print("and if it is, say so in the commit message alongside this derivation block.")
        return 1

    print(f"\nRecorded in {BUDGETS.relative_to(ROOT)}. Commit it with whatever changed the footprint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
