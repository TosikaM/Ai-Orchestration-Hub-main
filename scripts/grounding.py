#!/usr/bin/env python3
"""
The grounding evidence manifest: verify files and symbols before they are cited.

  python scripts/grounding.py check "<text containing paths and symbols>"
  python scripts/grounding.py manifest --file <path>
  python scripts/grounding.py verify-symbol <Name>

WHAT IT DOES
------------
Extracts path-shaped and symbol-shaped tokens from a piece of text, resolves each one
against the filesystem and the structural graph, and emits an EXISTS / NOT FOUND
manifest. The model is handed evidence BEFORE it answers rather than being asked
afterwards whether it was sure.

THE ONE DESIGN RULE
-------------------
**The manifest never cries wolf.** If nothing in a batch resolves, the whole batch is
suppressed rather than reported as a wall of NOT FOUND. A manifest that flags every
capitalized word trains its reader to skip it, and a skipped manifest is worse than no
manifest because the system still believes it is grounded.

WHAT THIS CANNOT DO, STATED PLAINLY
------------------------------------
It prevents: describing a file that does not exist when the user named it; calling a
method a class does not have; silently continuing past a truncation.

It does not prevent: a wrong claim about a file that does exist and was genuinely read.
That needs semantic verification, which is out of scope for a lexical index. Saying so
is part of the design rather than a gap in it.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graph as graph_mod  # noqa: E402

PATH_TOKEN = re.compile(r"\b([\w./-]+/[\w./-]+\.\w{1,6})\b|`([^`\n]*\.\w{1,6}[^`\n]*)`")
SYMBOL_TOKEN = re.compile(r"\b([A-Z][A-Za-z0-9]{2,}(?:\.[A-Za-z][A-Za-z0-9]{2,})?)\b")

# Words that look like symbols and are not. Without this the manifest reports on every
# capitalized noun in a sentence and immediately becomes noise.
SYMBOL_STOPWORDS = {
    "The", "This", "That", "These", "Those", "When", "Where", "What", "Which", "Then",
    "Note", "Warning", "Error", "Steps", "Rules", "Output", "Usage", "Example", "README",
    "TODO", "FIXME", "HTTP", "HTTPS", "JSON", "YAML", "API", "URL", "SQL", "CLI", "MCP",
    "Claude", "Python", "JavaScript", "TypeScript", "Markdown", "GitHub", "Windows",
    "Linux", "Docker", "None", "True", "False", "Read", "Write", "Edit", "Bash", "Glob",
}


def extract_paths(text: str) -> list:
    out = []
    for match in PATH_TOKEN.finditer(text):
        token = (match.group(1) or match.group(2) or "").strip()
        if token and token not in out:
            out.append(token)
    return out


def extract_symbols(text: str) -> list:
    out = []
    for match in SYMBOL_TOKEN.finditer(text):
        token = match.group(1)
        head = token.split(".")[0]
        if head in SYMBOL_STOPWORDS or token in out:
            continue
        out.append(token)
    return out


def verify_paths(repo: Path, tokens: list) -> list:
    results = []
    for token in tokens:
        candidate = repo / token
        exists = candidate.exists()
        if not exists:
            # A path may be quoted relative to a subdirectory. One cheap glob before
            # declaring it missing — a false NOT FOUND is as damaging as a false EXISTS.
            matches = list(repo.glob(f"**/{Path(token).name}"))[:3]
            if matches:
                results.append({
                    "token": token, "status": "MOVED",
                    "detail": f"not at that path; found at {matches[0].relative_to(repo).as_posix()}",
                })
                continue
        results.append({
            "token": token,
            "status": "EXISTS" if exists else "NOT FOUND",
            "detail": str(candidate.relative_to(repo)) if exists else "no file at this path",
        })
    return results


def verify_symbols(repo: Path, tokens: list) -> list:
    index = graph_mod.load(repo)
    symbols = index.get("symbols", {})
    results = []
    for token in tokens:
        head, _, member = token.partition(".")
        if member:
            if head not in symbols:
                results.append({"token": token, "status": "NOT FOUND",
                                "detail": f"'{head}' is not in the index"})
                continue
            if member in symbols:
                where = symbols[member][0]
                results.append({"token": token, "status": "EXISTS",
                                "detail": f"{where['file']}:{where['line']}"})
                continue
            where = symbols[head][0]
            results.append({
                "token": token, "status": "MEMBER NOT FOUND",
                "detail": (f"'{head}' exists at {where['file']}:{where['line']} but '{member}' "
                           f"is not in the index. Do not describe it — list the members that are."),
            })
            continue
        if head in symbols:
            where = symbols[head][0]
            results.append({"token": token, "status": "EXISTS",
                            "detail": f"{where['file']}:{where['line']}"})
        else:
            results.append({"token": token, "status": "NOT FOUND",
                            "detail": "not in the index"})
    return results


def render(path_results: list, symbol_results: list, index: dict) -> str:
    resolved = sum(1 for r in path_results + symbol_results if r["status"] == "EXISTS")
    total = len(path_results) + len(symbol_results)

    # Never cry wolf: nothing resolved means the extraction was probably wrong, not that
    # the whole codebase is missing.
    if total and resolved == 0:
        return (
            "_Evidence manifest suppressed: none of the extracted tokens resolved, which "
            "usually means the extraction misfired rather than that everything is absent. "
            "Verify by hand with `python scripts/graph.py find <symbol>`._"
        )
    if total == 0:
        return "_No file paths or symbols to verify._"

    lines = ["## Evidence manifest", "", graph_mod.header(index), ""]
    if path_results:
        lines.append("**Files**")
        for r in path_results:
            mark = {"EXISTS": "🟢", "MOVED": "🟡"}.get(r["status"], "🔴")
            lines.append(f"- {mark} `{r['token']}` — {r['status']}: {r['detail']}")
        lines.append("")
    if symbol_results:
        lines.append("**Symbols**")
        for r in symbol_results:
            mark = {"EXISTS": "🟢"}.get(r["status"], "🔴")
            lines.append(f"- {mark} `{r['token']}` — {r['status']}: {r['detail']}")
        lines.append("")
    missing = [r for r in path_results + symbol_results if r["status"] != "EXISTS"]
    if missing:
        lines.append(
            f"**{len(missing)} token(s) did not resolve.** Do not describe them. Either open "
            f"the file and cite what you find, or say it was not found — an honest \"not found\" "
            f"outranks a plausible guess."
        )
    if index.get("truncated"):
        lines.append("")
        lines.append("⚠️ The index is TRUNCATED. Absence here proves nothing; presence still does.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grounding evidence manifest")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check"); p.add_argument("text"); p.add_argument("--repo", default=".")
    p = sub.add_parser("manifest"); p.add_argument("--file", required=True); p.add_argument("--repo", default=".")
    p = sub.add_parser("verify-symbol"); p.add_argument("name"); p.add_argument("--repo", default=".")

    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    if args.command == "verify-symbol":
        return graph_mod.cmd_find(repo, args.name)

    if args.command == "manifest":
        source = Path(args.file)
        if not source.exists():
            print(f"no such file: {source}")
            return 1
        text = source.read_text(encoding="utf-8")
    else:
        text = args.text

    index = graph_mod.load(repo)
    print(render(
        verify_paths(repo, extract_paths(text)),
        verify_symbols(repo, extract_symbols(text)),
        index,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
