#!/usr/bin/env python3
"""
Shared helpers for the orchestrator scripts.

One module, because the alternative is six scripts each with their own slightly
different frontmatter parser, and the day they disagree is the day a budget check
passes on a file the skill loader rejects. Design principle P6: one source of truth
per fact, and that includes the code that reads the fact.

Dependency policy: standard library plus `pyyaml`. Nothing else. The content plane
must be buildable and checkable without entering a package manager, and every
dependency added here is one a consumer repo's CI has to install before it can run
a validation that is supposed to be cheap.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment guidance, not logic
    sys.stderr.write(
        "This script needs pyyaml.\n"
        "  pip install pyyaml\n"
        "It is the only third-party dependency in the content plane, deliberately.\n"
    )
    raise

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- the inventories
# These lists are the contract. A skill folder that is not in SKILLS is an unbudgeted
# skill; an agent file not in AGENTS is undiscovered. Adding to a list is a reviewable
# line in a diff, which is the entire point of keeping them here rather than globbing.

AGENTS = [
    "orchestrator", "analyst", "developer", "reviewer", "ba", "qa",
    "graph-navigator", "architect", "security", "knowledge-curator",
]

SKILLS = [
    "sdlc-orchestrator", "repo-context-builder", "cqrs-developer", "quality-sentinel",
    "structural-graph", "cross-repo-orchestration", "continuous-learning", "autonomous-loop",
    "verification-loop", "context-budget", "mcp-tool-composer", "grounding-guard",
    "security-review", "architecture-decision", "release-engineering", "knowledge-base",
    "git-workflow",
]

COMMANDS = [
    "orchestrator-init", "sdlc-start", "plan", "pipeline", "analyze", "explore",
    "implement", "review", "test", "qa", "verify", "security", "adr", "release",
    "document", "graph", "ground", "budget", "loop", "memory", "learn", "repo",
    "mcp-compose", "knowledge", "project-brief", "git", "mode", "doctor",
]

CONTEXTS = ["dev", "review", "research"]

HOOKS = [
    "fact-force", "config-protection", "prompt-defense", "destructive-gate", "autonomy-gate",
    "mcp-health", "session-bootstrap", "token-budget-guard", "pre-compact-checkpoint",
    "citation-guard", "human-gate", "learning-capture", "context-staleness",
    "telemetry", "session-teardown", "memory-dedupe",
]

# Commands that mutate session state rather than invoking a skill, so they have no
# skills/<name>/commands/ entry and must be exempt from the command-skill parity check.
BUILTIN_COMMANDS = {"orchestrator-init", "mode", "doctor"}

KNOWN_TOOLS = {
    "Read", "Write", "Edit", "Grep", "Glob", "Bash",
    "Agent", "AskUserQuestion", "WebSearch", "WebFetch", "NotebookEdit",
}

# Skills whose entire purpose is verification. A verifier that can mutate the thing it
# verifies is not a verifier. Enforced, not advised.
READ_ONLY_SKILLS = {"grounding-guard", "structural-graph", "mcp-tool-composer"}
MUTATING_TOOLS = {"Write", "Edit", "NotebookEdit"}


# ------------------------------------------------------------------ file helpers

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value) -> None:
    """Atomic write. A process killed mid-write must not leave truncated JSON that
    every later run fails to parse."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def frontmatter(path: Path):
    """Returns (mapping, error). A file without a leading --- block yields (None, reason)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not text.startswith("---"):
        return None, "missing YAML frontmatter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "malformed frontmatter"
    try:
        return yaml.safe_load(parts[1]) or {}, None
    except yaml.YAMLError as exc:
        return None, f"invalid YAML frontmatter: {exc}"


def frontmatter_and_body(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        return yaml.safe_load(parts[1]) or {}, parts[2]
    except yaml.YAMLError:
        return {}, parts[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ------------------------------------------------------------------ configuration

_config_cache: dict = {}


def config(name: str, default=None):
    """Load a file from config/. Cached for the process lifetime."""
    if name in _config_cache:
        return _config_cache[name]
    value = read_json(ROOT / "config" / name, default)
    _config_cache[name] = value
    return value


def hub_config():
    if "__hub" not in _config_cache:
        _config_cache["__hub"] = read_json(ROOT / "hub.config.json", {})
    return _config_cache["__hub"]


def org_id() -> str:
    return (hub_config().get("org") or {}).get("id", "unknown")


def budgets():
    return config("token-budgets.json", {})


def state_home() -> Path:
    explicit = os.environ.get("ORCHESTRATOR_HOME")
    if explicit:
        return Path(explicit)
    name = (hub_config().get("state") or {}).get("homeDirName", ".orchestrator")
    return Path.home() / name


def state_path(*parts) -> Path:
    path = state_home().joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def repo_slug(repo_path: Path | None = None) -> str:
    base = (repo_path or Path.cwd()).resolve().name or "workspace"
    slug = re.sub(r"[^a-z0-9._-]+", "-", base.lower()).strip("-")
    return slug or "workspace"


# ------------------------------------------------------------------ measurement

def measure_discovery(root: Path = ROOT):
    """
    The discovery footprint: utf-8 bytes of name + description across every skill's
    frontmatter. This is loaded in every session before the user types anything, which
    makes it the most expensive text in the repository.

    Defined here rather than in the measurement script so the validator and the
    measurer cannot disagree about what the number means.
    """
    per_skill = []
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return 0, per_skill
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, problem = frontmatter(skill_md)
        if problem or not meta:
            continue
        payload = f"{meta.get('name', '')}{meta.get('description', '')}"
        per_skill.append((skill_dir.name, len(payload.encode("utf-8"))))
    return sum(size for _, size in per_skill), per_skill


# ------------------------------------------------------------------ redaction

_redaction_cache = None


def redaction_patterns():
    global _redaction_cache
    if _redaction_cache is None:
        data = config("redaction-patterns.json", {})
        compiled = []
        for p in data.get("patterns", []):
            flags = re.MULTILINE if p["regex"].startswith("^") else 0
            compiled.append({
                **p,
                "re": re.compile(p["regex"], flags),
                "nearRe": re.compile(p["nearRegex"], re.IGNORECASE) if p.get("nearRegex") else None,
            })
        suppressions = [
            {**s, "re": re.compile(s["regex"], re.IGNORECASE)}
            for s in data.get("suppressions", [])
        ]
        _redaction_cache = (compiled, suppressions, data)
    return _redaction_cache


def redact_scan(text: str, file_path: str | None = None):
    """Returns a list of findings. An empty taxonomy raises rather than reporting clean —
    we cannot claim a string is safe using rules we failed to load."""
    patterns, suppressions, data = redaction_patterns()
    if not patterns:
        raise RuntimeError(
            "config/redaction-patterns.json is missing or empty. Refusing to report "
            "text as clean using a taxonomy that did not load."
        )
    findings = []
    source = text or ""

    def is_suppressed(pattern, matched: str) -> bool:
        for s in suppressions:
            tiers = s.get("appliesToTiers")
            if tiers and pattern["tier"] not in tiers:
                continue
            if s.get("scope") == "path":
                if file_path and s["re"].search(str(file_path)):
                    return True
            elif s["re"].search(matched):
                return True
        return False

    for pattern in patterns:
        for match in pattern["re"].finditer(source):
            span = match.group(1) if match.groups() else match.group(0)
            if pattern["nearRe"]:
                window = pattern.get("nearWindow", 120)
                start = max(0, match.start() - window)
                context = source[start:match.end() + window]
                if not pattern["nearRe"].search(context):
                    continue
            if is_suppressed(pattern, match.group(0)):
                continue
            findings.append({
                "id": pattern["id"],
                "tier": pattern["tier"],
                "category": pattern.get("category", ""),
                "description": pattern.get("description", ""),
                "line": source.count("\n", 0, match.start()) + 1,
                "preview": f"{span[:4]}…{span[-2:]}" if len(span) > 12 else "…",
                "autoRedactable": bool(pattern.get("autoRedactable")),
                "redactToken": pattern.get("redactToken", "<REDACTED>"),
                "start": match.start(),
                "span": span,
            })
    return findings


INJECTION_MARKERS = re.compile(
    r"(?:^|\n)\s*(?:ignore\s+(?:all\s+)?(?:previous|prior|above)"
    r"|disregard\s+(?:the\s+)?(?:above|system|instructions)"
    r"|you\s+are\s+now\b"
    r"|new\s+(?:system\s+)?instructions?\s*:"
    r"|</?(?:system|instructions?)>"
    r"|BEGIN\s+SYSTEM\s+PROMPT)",
    re.IGNORECASE,
)


def is_interactive() -> bool:
    """
    Is there a human present who could answer a confirmation?

    This decides how a MEDIUM redaction finding is treated, so getting it wrong in the
    permissive direction is the expensive mistake. It therefore answers "no" whenever it
    is not certain: no TTY, or any of the usual unattended markers.
    """
    if os.environ.get("ORCHESTRATOR_HEADLESS") or os.environ.get("CI") \
            or os.environ.get("GITHUB_ACTIONS"):
        return False
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def guard_free_text(field: str, value: str, interactive: bool | None = None) -> list:
    """
    The write-site guard. Raises on injection markers, on HIGH-tier secrets, and — when
    nobody is present to be asked — on MEDIUM-tier findings too.

    Stored memory is re-injected into future prompts, which makes the memory store an
    injection surface as well as a storage surface: a "resolution" that reads "ignore
    previous instructions" becomes a delayed instruction, read back to an agent in three
    months, in a different repository, with no human in the loop.

    WHY MEDIUM BLOCKS WHEN UNATTENDED
    ---------------------------------
    The tier taxonomy calls MEDIUM "confirm with the user". That is the right treatment
    at an interactive sink, and it is meaningless at this one. `memory.py capture` and
    `decision.py log` are called from hooks and from CI, where there is no user to
    confirm — so "confirm" silently degrades to "proceed", and a MEDIUM finding (an email
    address, an internal hostname, a JWT, a developer's home path) is written into a
    store that syncs to every connected repository.

    Two facts make the unattended case different from the interactive one, and both are
    true here: nobody can answer, and the destination is shared. So when the process is
    not interactive, MEDIUM is treated as blocking and the caller is told which finding
    to fix. `--allow-medium` exists for the deliberate case, because a rule with no
    escape gets worked around rather than obeyed.
    """
    if INJECTION_MARKERS.search(value or ""):
        raise ValueError(
            f"{field}: refusing to persist prompt-injection markers. "
            "Stored text is re-read as context in future sessions."
        )
    findings = redact_scan(value or "")

    high = [f for f in findings if f["tier"] == "HIGH"]
    if high:
        ids = ", ".join(f"{f['id']}@line {f['line']}" for f in high)
        raise ValueError(f"{field}: refusing to persist {len(high)} HIGH-tier secret(s): {ids}")

    if interactive is None:
        interactive = is_interactive()
    if not interactive:
        medium = [f for f in findings if f["tier"] == "MEDIUM"]
        if medium:
            ids = ", ".join(f"{f['id']}@line {f['line']}" for f in medium)
            raise ValueError(
                f"{field}: {len(medium)} MEDIUM-tier finding(s) and no human present to "
                f"confirm: {ids}. This store syncs to every connected repository, so an "
                f"unattended 'confirm' would mean 'proceed'. Rewrite the text, or pass "
                f"--allow-medium if this is deliberate."
            )
    return findings


# ------------------------------------------------------------------ output helpers

def ok(message: str) -> None:
    print(f"[ OK ] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def info(message: str) -> None:
    print(f"       {message}")
