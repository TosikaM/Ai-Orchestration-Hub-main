#!/usr/bin/env python3
"""
The context generator: scans a repository and writes .github/orchestrator-context.md.

  python scripts/context-gen.py [--repo PATH] [--force]
  python scripts/context-gen.py --check       # report staleness, write nothing

TWO RULES THAT ARE LOAD-BEARING
-------------------------------
1. Anything not detected is written as the literal string "not detected". Never a
   plausible guess. This file is the densest artifact in the system and everything
   downstream trusts it, so a confidently wrong stack propagates into every phase of
   every pipeline. An honest unknown costs one question; a wrong guess costs a
   day of work aimed at the wrong architecture.

2. Two sections are NEVER overwritten on a refresh:
     ## Integration Points   — maintained by hand; a scanner cannot infer them
     ## Verified Commands    — written by verification-loop when it has to ask
   Regenerating either destroys knowledge the scanner has no way to recover. The
   preserved-section mechanism is the reason a refresh is safe to run at all.

3. The `| **Tech Stack**: |` row keeps that exact literal form. The cross-repo connect
   path matches on it to recover a repository's stack, and a cosmetic edit to the table
   would silently make every connected repo record "unknown".
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, config, org_id, redact_scan, repo_slug  # noqa: E402

PRESERVED_SECTIONS = ["## Integration Points", "## Verified Commands"]
STALE_DAYS = 14
NOT_DETECTED = "not detected"

SKIP_DIRS = {
    "node_modules", ".git", "dist", "out", "build", "bin", "obj", "target",
    ".venv", "venv", "__pycache__", ".next", "coverage", "vendor", ".gradle",
}


def detect_stack(repo: Path) -> tuple:
    mappings = config("stack-mappings.json", {})
    stacks = {s["id"]: s for s in mappings.get("stacks", [])}
    for stack_id in mappings.get("detectionOrder", []):
        stack = stacks.get(stack_id)
        if not stack or not stack.get("indicators"):
            continue
        for indicator in stack["indicators"]:
            if "file" in indicator:
                candidates = list(repo.glob(indicator["file"]))[:5]
                if not candidates:
                    candidates = [p for p in list(repo.glob(f"**/{indicator['file']}"))[:20]
                                  if not any(part in SKIP_DIRS for part in p.parts)][:5]
                for candidate in candidates:
                    if "contains" not in indicator:
                        return stack_id, stack
                    try:
                        if indicator["contains"] in candidate.read_text(encoding="utf-8", errors="ignore"):
                            return stack_id, stack
                    except OSError:
                        continue
            elif "directory" in indicator:
                if (repo / indicator["directory"]).is_dir():
                    return stack_id, stack
                nested = [p for p in list(repo.glob(f"**/{indicator['directory']}"))[:20]
                          if p.is_dir() and not any(part in SKIP_DIRS for part in p.parts)]
                if nested:
                    return stack_id, stack
    return "unknown", stacks.get("unknown", {})


def detect_version(repo: Path, stack_id: str) -> str:
    """Read the version from a manifest. Never recall one — that is a named failure mode."""
    import json
    if stack_id in ("angular", "react", "nextjs", "vue", "svelte", "node-typescript"):
        pkg = repo / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for key in ("@angular/core", "next", "react", "vue", "svelte", "typescript"):
                    if key in deps:
                        return f"{key} {deps[key]}"
            except (OSError, ValueError):
                pass
    if stack_id.startswith("dotnet"):
        for csproj in list(repo.glob("**/*.csproj"))[:10]:
            try:
                match = re.search(r"<TargetFramework>([^<]+)</TargetFramework>",
                                  csproj.read_text(encoding="utf-8", errors="ignore"))
                if match:
                    return match.group(1)
            except OSError:
                continue
    if stack_id in ("django", "fastapi"):
        pyproject = repo / "pyproject.toml"
        if pyproject.exists():
            try:
                match = re.search(r'requires-python\s*=\s*"([^"]+)"',
                                  pyproject.read_text(encoding="utf-8"))
                if match:
                    return f"python {match.group(1)}"
            except OSError:
                pass
    return NOT_DETECTED


def detect_architecture(repo: Path) -> str:
    signals = {
        "cqrs": ["Commands", "Queries", "Handlers"],
        "feature-sliced": ["features", "entities", "shared"],
        "layered-mvc": ["Controllers", "Services", "Models"],
        "component-based": ["src/components", "src/app"],
    }
    for pattern, markers in signals.items():
        hits = sum(1 for marker in markers
                   if (repo / marker).is_dir() or list(repo.glob(f"**/{marker}"))[:1])
        if hits >= 2:
            return pattern
    return NOT_DETECTED


def map_layers(repo: Path) -> list:
    rows = []
    known = [
        ("Commands", "command handlers"), ("Queries", "read models"),
        ("Handlers", "message handlers"), ("Controllers", "HTTP entry points"),
        ("Services", "business logic"), ("Models", "domain entities"),
        ("Dto", "data transfer objects"), ("Repositories", "persistence"),
        ("src/components", "UI components"), ("src/services", "client services"),
        ("src/store", "state management"), ("api", "API surface"),
        ("migrations", "schema changes"),
    ]
    for name, description in known:
        direct = repo / name
        found = direct if direct.is_dir() else next(
            (p for p in list(repo.glob(f"**/{name}"))[:8]
             if p.is_dir() and not any(part in SKIP_DIRS for part in p.parts)), None)
        if found:
            rel = found.relative_to(repo).as_posix()
            files = sorted(f.name for f in list(found.glob("*.*"))[:3])
            rows.append((name, rel, ", ".join(files) or "—", description))
    return rows


def read_preserved(existing: str) -> dict:
    """Pull the hand-maintained sections out of the current file so a refresh keeps them."""
    preserved = {}
    if not existing:
        return preserved
    for heading in PRESERVED_SECTIONS:
        start = existing.find(heading)
        if start == -1:
            continue
        after = existing[start + len(heading):]
        end = after.find("\n## ")
        preserved[heading] = after[:end] if end != -1 else after
    return preserved


def build(repo: Path, existing: str) -> str:
    stack_id, stack = detect_stack(repo)
    version = detect_version(repo, stack_id)
    architecture = detect_architecture(repo)
    layers = map_layers(repo)
    conventions = stack.get("conventions", {})
    commands = stack.get("commands", {})
    preserved = read_preserved(existing)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"# {repo.name} — Orchestrator Context",
        f"> Auto-generated: {now} | Stack detection: `config/stack-mappings.json`",
        "",
        "## Project Identity",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Repository | {org_id()}/{repo.name} |",
        # This exact literal row shape is matched by the connect path. Do not restyle it.
        f"| **Tech Stack**: | {stack.get('name', stack_id)} |",
        f"| Architecture | {architecture} |",
        f"| Framework Version | {version} |",
        f"| Testing Framework | {conventions.get('testPattern', NOT_DETECTED)} |",
        f"| Naming Convention | {conventions.get('namingConvention', NOT_DETECTED)} |",
        f"| Mapping Mechanism | {conventions.get('mappingMechanism', NOT_DETECTED)} |",
        "",
        "## Architecture Layers",
        "",
    ]
    if layers:
        lines += ["| Layer | Path | Key Files | Purpose |", "|-------|------|-----------|---------|"]
        lines += [f"| {name} | `{rel}` | {files} | {desc} |" for name, rel, files, desc in layers]
    else:
        lines.append(f"_{NOT_DETECTED} — no recognized layer directories. Read the repo before "
                     f"asserting any structure._")
    lines += [
        "",
        "## Domain Entities",
        "",
        "| Entity | Location | Relationships |",
        "|--------|----------|---------------|",
        "_Populated by `/analyze`. The scanner locates directories; it does not read semantics._",
        "",
        "## Integration Points",
    ]
    if "## Integration Points" in preserved:
        lines.append(preserved["## Integration Points"].rstrip())
    else:
        lines += [
            "",
            "| Type | Endpoint / Interface | Used By |",
            "|------|----------------------|---------|",
            "",
            "_Maintained by hand. The scanner cannot infer these and will never overwrite this "
            "section on a refresh._",
        ]
    lines += ["", "## Verified Commands"]
    if "## Verified Commands" in preserved:
        lines.append(preserved["## Verified Commands"].rstrip())
    else:
        lines += ["", "| Purpose | Command | Verified |", "|---------|---------|----------|"]
        for purpose, candidates in commands.items():
            lines.append(f"| {purpose} | `{candidates[0]}` | candidate, not yet run |")
        if not commands:
            lines.append(f"| — | {NOT_DETECTED} | — |")
        lines += [
            "",
            "_Candidates come from the stack mapping. `verification-loop` replaces a candidate "
            "with the command that actually ran, and this section is never overwritten by a "
            "context refresh — a one-time question that persists beats a permanent "
            "\"not detected\"._",
        ]
    lines += [
        "",
        "## Conventions",
        "",
        "**This repository's own `CLAUDE.md` or `copilot-instructions.md` outranks everything "
        "below.** A hub default that overrides a team's stated convention is a hub that gets "
        "uninstalled.",
        "",
    ]
    for key, value in conventions.items():
        lines.append(f"- **{key}**: {value}")
    lines += [
        "",
        "## Orchestrator Notes",
        "",
        "_Agents append durable observations here. Transient task state does not belong in this "
        "file — it belongs in `memory/sessions/`._",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the repo context file")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    target = repo / ".github" / "orchestrator-context.md"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""

    if args.check:
        if not existing:
            print("not generated — run without --check")
            return 1
        age = (datetime.now(timezone.utc).timestamp() - target.stat().st_mtime) / 86400
        print(f"{target.relative_to(repo)}: {int(age)} days old "
              f"({'STALE' if age > STALE_DAYS else 'fresh'}, threshold {STALE_DAYS}d)")
        return 1 if age > STALE_DAYS else 0

    if existing and not args.force:
        age = (datetime.now(timezone.utc).timestamp() - target.stat().st_mtime) / 86400
        if age <= STALE_DAYS:
            print(f"{target.relative_to(repo)} exists and is {int(age)} days old. "
                  f"Use --force to regenerate.")
            print("Re-analyzing a profiled repo from scratch is the most common avoidable cost "
                  "in this system.")
            return 0

    content = build(repo, existing)

    # The context file records entity names, paths, and structure, and in some repos it
    # is committed. Scan before writing rather than after.
    findings = redact_scan(content, str(target))
    high = [f for f in findings if f["tier"] == "HIGH"]
    if high:
        print("REFUSED: the generated context would contain HIGH-tier secret(s):")
        for finding in high:
            print(f"  - {finding['id']} at line {finding['line']}")
        return 3
    medium = [f for f in findings if f["tier"] == "MEDIUM"]

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    preserved = read_preserved(existing)
    print(f"Wrote {target}")
    if preserved:
        print(f"  preserved: {', '.join(preserved)}")
    if medium:
        print(f"  {len(medium)} MEDIUM redaction finding(s) — review before committing:")
        for finding in medium[:5]:
            print(f"    - {finding['id']} line {finding['line']} ({finding['description']})")
    print("\n  Anything shown as \"not detected\" is genuinely not detected. Fill it in by hand or")
    print("  run /analyze — do not let an agent guess it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
