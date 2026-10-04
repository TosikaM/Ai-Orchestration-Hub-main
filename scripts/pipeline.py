#!/usr/bin/env python3
"""
The SDLC pipeline: a DAG scheduler over JSON, with checkpoints and real human gates.

  python scripts/pipeline.py start "<requirement>"
  python scripts/pipeline.py status [<pipelineId>]
  python scripts/pipeline.py ready <pipelineId>              # which phases can run now
  python scripts/pipeline.py complete <pipelineId> <phase> [--score N]
  python scripts/pipeline.py gate <pipelineId> <phase> --artifact <file>
  python scripts/pipeline.py approve <pipelineId> <phase> [--note "..."]
  python scripts/pipeline.py request-changes <pipelineId> <phase> --note "..."
  python scripts/pipeline.py resume <pipelineId>
  python scripts/pipeline.py abandon <pipelineId>

WHY A DAG AND NOT AN ARRAY
--------------------------
The protocol always described `review` and `test` running in parallel. A fixed
six-element array cannot do that, so for a long time the prose and the code disagreed
and the prose was the one people read. Here the shape lives in
config/pipeline-graph.json, `review` and `test` are siblings, and `deploy` waits for
both — the parallelism is a property of the data, not a claim in a document.

WHY THE HUMAN GATE IS A FILE
----------------------------
A gate whose entire implementation is a notification is a request. This writes an
artifact and waits for a verdict file, and a Stop hook refuses to let the session end
while an artifact has no verdict. The agent cannot clear its own gate.

The verdict being JSON on disk is what makes the view plane optional rather than
required: `pipeline.py approve` and the gate panel write the identical file, so anyone
in a terminal, on Linux, or in a different editor is fully served.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, config, read_json, repo_slug, utc_now, write_json  # noqa: E402

SESSIONS = ROOT / "memory" / "sessions"
MAX_GATE_FAILURES = 3


def graph() -> dict:
    data = config("pipeline-graph.json")
    if data is None:
        # A silent fallback to built-in defaults is the failure mode `doctor` exists to
        # catch. Say so loudly instead of quietly running a different pipeline.
        print("WARNING: config/pipeline-graph.json unreadable. Using a minimal built-in DAG.",
              file=sys.stderr)
        return {
            "entry": "analyze",
            "phases": {
                "analyze": {"next": ["implement"], "gate": 0, "humanGate": True},
                "implement": {"next": ["review", "test"], "gate": 0, "humanGate": False},
                "review": {"next": ["deploy"], "gate": 80, "humanGate": False},
                "test": {"next": ["deploy"], "gate": 80, "humanGate": False},
                "deploy": {"next": ["complete"], "gate": 0, "humanGate": True},
                "complete": {"next": [], "gate": 0, "humanGate": False},
            },
            "__fallback": True,
        }
    return data


def checkpoint_path(pipeline_id: str) -> Path:
    return SESSIONS / f"{pipeline_id}.checkpoint.json"


def gate_artifact_path(pipeline_id: str, phase: str) -> Path:
    return SESSIONS / f"{pipeline_id}.gate-{phase}.md"


def gate_verdict_path(pipeline_id: str, phase: str) -> Path:
    return SESSIONS / f"{pipeline_id}.gate-{phase}.json"


def new_id() -> str:
    return f"pipe-{int(time.time() * 1000):x}"[:12]


def load(pipeline_id: str) -> dict | None:
    return read_json(checkpoint_path(pipeline_id))


def save(checkpoint: dict) -> None:
    checkpoint["updatedAt"] = utc_now()
    write_json(checkpoint_path(checkpoint["pipelineId"]), checkpoint)


def all_pipelines() -> list:
    if not SESSIONS.is_dir():
        return []
    out = []
    for path in sorted(SESSIONS.glob("*.checkpoint.json")):
        data = read_json(path)
        if data:
            out.append(data)
    return out


def parents_of(dag: dict, phase: str) -> list:
    return [name for name, meta in dag["phases"].items() if phase in meta.get("next", [])]


def ready_phases(checkpoint: dict, dag: dict) -> list:
    """
    A phase is ready when every parent is complete and it is not itself done.
    This is the whole scheduler, and keeping it this small is why parallelism works:
    `review` and `test` both have `implement` as their only parent, so both go ready
    at once and nothing special-cases them.
    """
    statuses = checkpoint["phases"]
    ready = []
    for name in dag["phases"]:
        if statuses.get(name, {}).get("status") in ("complete", "skipped"):
            continue
        parents = parents_of(dag, name)
        if not parents and name != dag["entry"]:
            continue
        if name == dag["entry"] and not parents:
            if statuses.get(name, {}).get("status") in (None, "pending", "active", "failed"):
                ready.append(name)
            continue
        if all(statuses.get(p, {}).get("status") == "complete" for p in parents):
            ready.append(name)
    return ready


def pending_gate(checkpoint: dict) -> tuple | None:
    for phase, meta in checkpoint["phases"].items():
        if meta.get("gateArtifactWritten") and not meta.get("verdict"):
            return phase, meta
    return None


# ------------------------------------------------------------------ commands

def cmd_start(args) -> int:
    dag = graph()
    pipeline_id = new_id()
    checkpoint = {
        "pipelineId": pipeline_id,
        "requirement": args.requirement,
        "repo": repo_slug(Path.cwd()),
        "startedAt": utc_now(),
        "updatedAt": utc_now(),
        "status": "active",
        "currentPhase": dag["entry"],
        "compactions": 0,
        "phases": {
            name: {
                "status": "pending",
                "score": None,
                "attempts": 0,
                "humanGate": bool(meta.get("humanGate")),
                "gateThreshold": meta.get("gate", 0),
                "parallelWith": meta.get("parallelWith", []),
            }
            for name, meta in dag["phases"].items()
        },
    }
    checkpoint["phases"][dag["entry"]]["status"] = "active"
    save(checkpoint)

    print(f"Pipeline {pipeline_id} started.")
    print(f"  requirement: {args.requirement}")
    print(f"  entry phase: {dag['entry']}")
    print(f"  checkpoint:  {checkpoint_path(pipeline_id).relative_to(ROOT)}")
    if dag["phases"][dag["entry"]].get("humanGate"):
        print(f"\n  '{dag['entry']}' is human-gated. Write the artifact with:")
        print(f"    python scripts/pipeline.py gate {pipeline_id} {dag['entry']} --artifact <file>")
    return 0


def render(checkpoint: dict, dag: dict) -> None:
    print(f"{checkpoint['pipelineId']}  [{checkpoint.get('status', 'active')}]  "
          f"repo={checkpoint.get('repo', '?')}")
    print(f"  {checkpoint.get('requirement', '')[:100]}")
    if checkpoint.get("compactions"):
        print(f"  survived {checkpoint['compactions']} compaction(s)")
    print()
    marks = {"complete": "[x]", "active": "[>]", "failed": "[!]", "pending": "[ ]", "skipped": "[-]"}
    for name in dag["phases"]:
        meta = checkpoint["phases"].get(name, {})
        status = meta.get("status", "pending")
        line = f"  {marks.get(status, '[?]')} {name:<12} {status:<10}"
        if meta.get("score") is not None:
            threshold = meta.get("gateThreshold", 0)
            verdict = "PASS" if meta["score"] >= threshold else "FAIL"
            line += f" score {meta['score']}/{threshold} {verdict}"
        if meta.get("parallelWith"):
            line += f"  ∥ {', '.join(meta['parallelWith'])}"
        if meta.get("humanGate"):
            if meta.get("verdict"):
                line += f"  gate:{meta['verdict']}"
            elif meta.get("gateArtifactWritten"):
                line += "  gate:AWAITING HUMAN"
            else:
                line += "  gate:human"
        if meta.get("attempts", 0) > 1:
            line += f"  attempts {meta['attempts']}"
        print(line)

    ready = ready_phases(checkpoint, dag)
    pending = pending_gate(checkpoint)
    print()
    if pending:
        phase, _ = pending
        print(f"  BLOCKED on a human gate at '{phase}'.")
        print(f"    approve:  python scripts/pipeline.py approve {checkpoint['pipelineId']} {phase}")
        print(f"    reject:   python scripts/pipeline.py request-changes "
              f"{checkpoint['pipelineId']} {phase} --note \"...\"")
    elif ready:
        print(f"  ready now: {', '.join(ready)}"
              + ("   (these run in parallel)" if len(ready) > 1 else ""))
    else:
        print("  nothing ready — the pipeline is complete or stalled.")


def cmd_status(args) -> int:
    dag = graph()
    if args.pipeline_id:
        checkpoint = load(args.pipeline_id)
        if not checkpoint:
            print(f"no pipeline {args.pipeline_id}")
            return 1
        render(checkpoint, dag)
        return 0
    pipelines = all_pipelines()
    if not pipelines:
        print("No pipelines in this workspace.")
        return 0
    for checkpoint in pipelines:
        render(checkpoint, dag)
        print()
    return 0


def cmd_ready(args) -> int:
    dag = graph()
    checkpoint = load(args.pipeline_id)
    if not checkpoint:
        print(f"no pipeline {args.pipeline_id}")
        return 1
    pending = pending_gate(checkpoint)
    if pending:
        print(f"blocked: human gate at '{pending[0]}' has no verdict")
        return 1
    ready = ready_phases(checkpoint, dag)
    print(" ".join(ready) if ready else "(none)")
    return 0


def cmd_complete(args) -> int:
    dag = graph()
    checkpoint = load(args.pipeline_id)
    if not checkpoint:
        print(f"no pipeline {args.pipeline_id}")
        return 1
    if args.phase not in checkpoint["phases"]:
        print(f"'{args.phase}' is not a phase in this pipeline")
        return 1

    meta = checkpoint["phases"][args.phase]
    meta["attempts"] = meta.get("attempts", 0) + 1
    threshold = meta.get("gateThreshold", 0)

    if args.score is not None:
        meta["score"] = args.score
        if args.score < threshold:
            meta["status"] = "failed"
            save(checkpoint)
            print(f"'{args.phase}' scored {args.score}, below the gate of {threshold}. FAILED.")
            if meta["attempts"] >= MAX_GATE_FAILURES:
                print(f"\n  This phase has now failed {meta['attempts']} times.")
                print("  Escalate to the human. Three identical failures is a signal about the")
                print("  approach, not about the effort — a fourth attempt is very unlikely to differ.")
            return 1

    if meta.get("humanGate") and not meta.get("verdict"):
        meta["status"] = "active"
        save(checkpoint)
        print(f"'{args.phase}' is human-gated and has no verdict. Not marking it complete.")
        print(f"  write the artifact:  python scripts/pipeline.py gate "
              f"{args.pipeline_id} {args.phase} --artifact <file>")
        return 1

    meta["status"] = "complete"
    meta["completedAt"] = utc_now()
    for name in ready_phases(checkpoint, dag):
        if checkpoint["phases"][name]["status"] == "pending":
            checkpoint["phases"][name]["status"] = "active"

    ready = ready_phases(checkpoint, dag)
    checkpoint["currentPhase"] = ready[0] if ready else args.phase
    if all(p["status"] in ("complete", "skipped") for p in checkpoint["phases"].values()):
        checkpoint["status"] = "complete"
    save(checkpoint)

    print(f"'{args.phase}' complete" + (f" (score {args.score})" if args.score is not None else "") + ".")
    if ready:
        print(f"  now ready: {', '.join(ready)}"
              + ("   — run these in parallel" if len(ready) > 1 else ""))
    else:
        print("  pipeline complete.")
    return 0


def cmd_gate(args) -> int:
    checkpoint = load(args.pipeline_id)
    if not checkpoint:
        print(f"no pipeline {args.pipeline_id}")
        return 1
    artifact_target = gate_artifact_path(args.pipeline_id, args.phase)
    artifact_target.parent.mkdir(parents=True, exist_ok=True)

    if args.artifact:
        source = Path(args.artifact)
        if not source.exists():
            print(f"artifact file not found: {source}")
            return 1
        artifact_target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    elif not artifact_target.exists():
        artifact_target.write_text(
            f"# Human gate — {args.pipeline_id} / {args.phase}\n\n"
            f"**Requirement:** {checkpoint.get('requirement', '')}\n\n"
            f"_No artifact was supplied. A gate with a thin artifact trains the reviewer to_\n"
            f"_approve without reading, which defeats every gate in the pipeline at once._\n",
            encoding="utf-8",
        )

    checkpoint["phases"][args.phase]["gateArtifactWritten"] = True
    checkpoint["phases"][args.phase]["gateArtifactAt"] = utc_now()
    save(checkpoint)

    print(f"Gate artifact written: {artifact_target.relative_to(ROOT)}")
    print("The Stop hook will now block the session until a verdict exists.")
    print(f"  approve:  python scripts/pipeline.py approve {args.pipeline_id} {args.phase}")
    return 0


def write_verdict(pipeline_id: str, phase: str, verdict: str, note: str) -> int:
    checkpoint = load(pipeline_id)
    if not checkpoint:
        print(f"no pipeline {pipeline_id}")
        return 1
    if phase not in checkpoint["phases"]:
        print(f"'{phase}' is not a phase in this pipeline")
        return 1

    write_json(gate_verdict_path(pipeline_id, phase), {
        "pipelineId": pipeline_id,
        "phase": phase,
        "verdict": verdict,
        "note": note or "",
        "decidedAt": utc_now(),
        "decidedBy": "cli",
    })
    checkpoint["phases"][phase]["verdict"] = verdict
    checkpoint["phases"][phase]["verdictNote"] = note or ""
    if verdict == "approved":
        checkpoint["phases"][phase]["status"] = "complete"
        checkpoint["phases"][phase]["completedAt"] = utc_now()
        dag = graph()
        for name in ready_phases(checkpoint, dag):
            if checkpoint["phases"][name]["status"] == "pending":
                checkpoint["phases"][name]["status"] = "active"
    else:
        checkpoint["phases"][phase]["status"] = "failed"
    save(checkpoint)

    print(f"{phase}: {verdict}")
    if note:
        print(f"  note: {note}")
    if verdict == "approved":
        ready = ready_phases(checkpoint, graph())
        if ready:
            print(f"  now ready: {', '.join(ready)}")
    return 0


def cmd_approve(args) -> int:
    return write_verdict(args.pipeline_id, args.phase, "approved", args.note)


def cmd_request_changes(args) -> int:
    if not args.note:
        print("--note is required. A rejection with no reason is a rejection nobody can act on.")
        return 2
    return write_verdict(args.pipeline_id, args.phase, "changes-requested", args.note)


def cmd_resume(args) -> int:
    dag = graph()
    checkpoint = load(args.pipeline_id)
    if not checkpoint:
        print(f"no pipeline {args.pipeline_id}")
        return 1
    checkpoint["status"] = "active"
    checkpoint["resumedAt"] = utc_now()
    save(checkpoint)
    print(f"Resumed {args.pipeline_id}.")
    print("  Re-entering at the recorded phase. The pipeline is NOT restarted.")
    print()
    render(checkpoint, dag)
    return 0


def cmd_abandon(args) -> int:
    checkpoint = load(args.pipeline_id)
    if not checkpoint:
        print(f"no pipeline {args.pipeline_id}")
        return 1
    checkpoint["status"] = "abandoned"
    checkpoint["abandonedAt"] = utc_now()
    save(checkpoint)
    print(f"{args.pipeline_id} marked abandoned. The checkpoint is kept for the record.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrator SDLC pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start"); p.add_argument("requirement"); p.set_defaults(func=cmd_start)
    p = sub.add_parser("status"); p.add_argument("pipeline_id", nargs="?"); p.set_defaults(func=cmd_status)
    p = sub.add_parser("ready"); p.add_argument("pipeline_id"); p.set_defaults(func=cmd_ready)

    p = sub.add_parser("complete")
    p.add_argument("pipeline_id"); p.add_argument("phase")
    p.add_argument("--score", type=int, default=None)
    p.set_defaults(func=cmd_complete)

    p = sub.add_parser("gate")
    p.add_argument("pipeline_id"); p.add_argument("phase")
    p.add_argument("--artifact", default=None)
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("approve")
    p.add_argument("pipeline_id"); p.add_argument("phase"); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("request-changes")
    p.add_argument("pipeline_id"); p.add_argument("phase"); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_request_changes)

    p = sub.add_parser("resume"); p.add_argument("pipeline_id"); p.set_defaults(func=cmd_resume)
    p = sub.add_parser("abandon"); p.add_argument("pipeline_id"); p.set_defaults(func=cmd_abandon)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
