#!/usr/bin/env python3
"""
The structural graph: a cached, lexical symbol index.

  python scripts/graph.py build [--repo PATH]     # (re)build the index
  python scripts/graph.py find <symbol>           # where is it defined
  python scripts/graph.py importers <file>        # who depends on this
  python scripts/graph.py summary                 # the ~2K-token digest
  python scripts/graph.py stale                   # mark the cache stale
  python scripts/graph.py status                  # size and age

WHAT THIS IS, AND WHAT IT IS HONESTLY NOT
------------------------------------------
It is a regex-driven index of paths, exports, classes, functions, and imports. It
answers "does this symbol exist" and "who references this file" in one call instead of
a tree walk, which is why the fact-forcing gate is cheap to satisfy in this system and
expensive in a generic one.

It is not a parser and does not pretend to be. It will miss a symbol produced by a
macro, a decorator that renames, or a dynamic export. That is an acceptable trade for
running in milliseconds with no toolchain — but it means the index is authoritative
about PRESENCE and only suggestive about ABSENCE.

Which leads to the one rule that matters: **never assert a symbol the index does not
contain.** If a caller asks about `UserService.validateCredentialsAsync` and the index
has the class but not the method, the answer names the methods it does have. Not a
plausible location. A real class with a method it does not have is the most convincing
kind of wrong answer, because everything around it checks out.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ROOT, repo_slug, state_path, read_json, write_json, utc_now  # noqa: E402

SOURCE_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".cs", ".py", ".java", ".kt", ".go", ".rs", ".rb", ".php",
    ".vue", ".svelte", ".scala", ".swift",
}
SKIP_DIRS = {
    "node_modules", ".git", "dist", "out", "build", "bin", "obj", "target",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage", "vendor",
    ".gradle", ".idea", ".vs", "packages",
}
MAX_FILES = 8000
MAX_FILE_BYTES = 400_000
STALE_AFTER_SECONDS = 60 * 60

# Deliberately conservative. A pattern that over-matches puts symbols in the index that
# do not exist, which is worse than missing one: the whole value of the index is that a
# hit can be trusted.
PATTERNS = {
    "class": re.compile(
        r"^\s*(?:export\s+)?(?:public\s+|internal\s+|private\s+|protected\s+|abstract\s+|sealed\s+|final\s+|static\s+)*"
        r"(?:class|interface|struct|enum|record|trait|protocol)\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.MULTILINE,
    ),
    "function": re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:public\s+|private\s+|protected\s+|internal\s+|static\s+)*"
        r"(?:function|func|def|fn)\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.MULTILINE,
    ),
    "arrow": re.compile(
        r"^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:=][^=\n]*=>",
        re.MULTILINE,
    ),
    "method": re.compile(
        r"^\s{2,}(?:public\s+|private\s+|protected\s+|internal\s+|static\s+|async\s+|override\s+)*"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?::[^{\n]+)?\s*\{",
        re.MULTILINE,
    ),
    "export": re.compile(
        r"^\s*export\s+(?:default\s+)?(?:const|let|var|class|function|interface|type|enum)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)",
        re.MULTILINE,
    ),
}

IMPORT_PATTERNS = [
    re.compile(r"""^\s*import\s+(?:[\w*\s{},]+\s+from\s+)?['"]([^'"]+)['"]""", re.MULTILINE),
    re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""", re.MULTILINE),
    re.compile(r"^\s*from\s+([\w.]+)\s+import\s", re.MULTILINE),
    re.compile(r"^\s*using\s+([\w.]+)\s*;", re.MULTILINE),
    re.compile(r"^\s*#include\s+[<\"]([^>\"]+)[>\"]", re.MULTILINE),
]


def cache_file(repo: Path) -> Path:
    return state_path("cache", repo_slug(repo), "graph.json")


def iter_source_files(repo: Path):
    count = 0
    for path in repo.rglob("*"):
        if count >= MAX_FILES:
            return
        if not path.is_file():
            continue
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        count += 1
        yield path


def build(repo: Path) -> dict:
    started = time.time()
    symbols: dict[str, list] = {}
    files: dict[str, dict] = {}
    truncated = False
    scanned = 0

    for path in iter_source_files(repo):
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(repo).as_posix()
        line_starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                line_starts.append(i + 1)

        def line_of(index: int) -> int:
            low, high = 0, len(line_starts) - 1
            while low < high:
                mid = (low + high + 1) // 2
                if line_starts[mid] <= index:
                    low = mid
                else:
                    high = mid - 1
            return low + 1

        found = []
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                name = match.group(1)
                entry = {"file": rel, "line": line_of(match.start()), "kind": kind}
                symbols.setdefault(name, []).append(entry)
                found.append({"name": name, "kind": kind, "line": entry["line"]})

        imports = []
        for pattern in IMPORT_PATTERNS:
            imports.extend(pattern.findall(text))

        files[rel] = {
            "symbols": [f["name"] for f in found],
            "imports": sorted(set(imports)),
            "lines": len(line_starts),
        }

    if scanned >= MAX_FILES:
        truncated = True

    graph = {
        "version": 2,
        "repo": str(repo),
        "repoSlug": repo_slug(repo),
        "builtAt": utc_now(),
        "builtAtEpoch": time.time(),
        "durationMs": int((time.time() - started) * 1000),
        "fileCount": len(files),
        "symbolCount": len(symbols),
        "truncated": truncated,
        "truncationNote": (
            f"Scan stopped at {MAX_FILES} files. The index is INCOMPLETE — absence of a "
            f"symbol proves nothing in a truncated index. Narrow the repo or raise MAX_FILES."
        ) if truncated else None,
        "stale": False,
        "symbols": symbols,
        "files": files,
    }
    write_json(cache_file(repo), graph)
    return graph


def load(repo: Path, auto_build: bool = True) -> dict | None:
    path = cache_file(repo)
    graph = read_json(path)
    if graph is None:
        return build(repo) if auto_build else None
    age = time.time() - graph.get("builtAtEpoch", 0)
    # A stale index is rebuilt, never served. Serving one is worse than having none,
    # because the answer arrives looking authoritative.
    if graph.get("stale") or age > STALE_AFTER_SECONDS:
        return build(repo) if auto_build else graph
    return graph


def mark_stale(repo: Path) -> None:
    path = cache_file(repo)
    graph = read_json(path)
    if graph:
        graph["stale"] = True
        write_json(path, graph)


def age_string(graph: dict) -> str:
    age = int(time.time() - graph.get("builtAtEpoch", 0))
    if age < 60:
        return f"{age}s ago"
    if age < 3600:
        return f"{age // 60}m ago"
    return f"{age // 3600}h ago"


def header(graph: dict) -> str:
    line = (f"graph: {graph['symbolCount']} symbols across {graph['fileCount']} files, "
            f"built {age_string(graph)}")
    if graph.get("truncated"):
        line += "  [TRUNCATED — absence proves nothing]"
    return line


def cmd_find(repo: Path, name: str) -> int:
    graph = load(repo)
    print(header(graph))
    hits = graph["symbols"].get(name)
    if hits:
        for hit in hits:
            print(f"  {hit['file']}:{hit['line']}  ({hit['kind']})")
        return 0

    # Near misses matter here. "Not found" plus "these exist" is what stops the caller
    # inventing a plausible location, which is the failure this index exists to prevent.
    lowered = name.lower()
    near = sorted(s for s in graph["symbols"] if lowered in s.lower() or s.lower() in lowered)[:12]
    print(f"  NOT FOUND: '{name}' does not appear in the index.")
    if near:
        print("  Similar symbols that DO exist:")
        for candidate in near:
            first = graph["symbols"][candidate][0]
            print(f"    {candidate}  ({first['file']}:{first['line']})")
    else:
        print("  No similar symbol either. Do not describe this symbol — it is not here.")
    return 1


def cmd_importers(repo: Path, target: str) -> int:
    graph = load(repo)
    print(header(graph))
    stem = Path(target).stem
    target_rel = target.replace("\\", "/").lstrip("./")

    importers = []
    for rel, meta in graph["files"].items():
        if rel == target_rel:
            continue
        for imp in meta["imports"]:
            normalized = imp.replace("\\", "/")
            if normalized.endswith(stem) or f"/{stem}" in normalized or normalized.split("/")[-1] == stem:
                importers.append(rel)
                break

    if importers:
        print(f"  {len(importers)} file(s) import {target_rel}:")
        for rel in sorted(importers):
            print(f"    {rel}")
    else:
        print(f"  No file in the index imports {target_rel}.")
        print("  Note: this index is lexical. A dynamic import, a barrel re-export, or a")
        print("  DI registration will not appear here. Treat zero as 'none found', not 'none exist'.")
    return 0


def cmd_summary(repo: Path) -> int:
    graph = load(repo)
    print(header(graph))
    print()
    by_dir: dict[str, int] = {}
    for rel in graph["files"]:
        top = rel.split("/")[0] if "/" in rel else "."
        by_dir[top] = by_dir.get(top, 0) + 1
    print("Top-level layout:")
    for name, count in sorted(by_dir.items(), key=lambda p: -p[1])[:15]:
        print(f"  {name:<30} {count} files")
    print()
    classes = [(n, e[0]) for n, e in graph["symbols"].items() if e[0]["kind"] == "class"]
    print(f"Types and classes ({len(classes)}), first 40:")
    for name, entry in sorted(classes)[:40]:
        print(f"  {name:<34} {entry['file']}:{entry['line']}")
    return 0


def cmd_status(repo: Path) -> int:
    graph = read_json(cache_file(repo))
    if graph is None:
        print("no index built yet — run `python scripts/graph.py build`")
        return 1
    print(header(graph))
    print(f"  cache: {cache_file(repo)}")
    print(f"  stale flag: {graph.get('stale', False)}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    repo = Path.cwd()
    if "--repo" in args:
        index = args.index("--repo")
        repo = Path(args[index + 1]).resolve()
        del args[index:index + 2]

    command = args[0]
    if command == "build":
        graph = build(repo)
        print(header(graph))
        print(f"  written to {cache_file(repo)}")
        if graph.get("truncationNote"):
            print(f"  WARNING: {graph['truncationNote']}")
        return 0
    if command == "find" and len(args) > 1:
        return cmd_find(repo, args[1])
    if command == "importers" and len(args) > 1:
        return cmd_importers(repo, args[1])
    if command == "summary":
        return cmd_summary(repo)
    if command == "stale":
        mark_stale(repo)
        print("index marked stale; it will rebuild on next read")
        return 0
    if command == "status":
        return cmd_status(repo)

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
