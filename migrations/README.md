# Migrations

Upgrading the hub is cheap: the plugin is versioned and `/plugin marketplace update`
replaces it wholesale. Upgrading the *state an install left in somebody's repository* is
not, because that state is on their disk, was written by a version we no longer ship, and
is the only record of what we did to a repository we do not own.

A migration is the thing that reconciles the two.

## When a Migration Is Required

Write one for **any change to on-disk shape that could break an existing install**. The
test is not "did the file format change" but "would a repository connected under the old
version behave incorrectly, or be misdescribed, under the new one".

Concretely, that means:

| Change | Migration required? |
|---|---|
| A new key in `.github/orchestrator-install.json` that readers rely on | Yes — old installs do not have it |
| A path we used to write and no longer do | Yes — the copy on disk is now stale and unowned |
| A change to the managed `.gitignore` block | Yes — the old block keeps ignoring things |
| Anything set through `git update-index` | Yes, always — invisible state cannot be discovered by the user |
| A config value moving between files | Yes, at minimum as a report |
| A new skill, agent, prompt, or command | No — the plugin carries these; nothing is on the user's disk |
| A change to a value inside `config/` that ships with the hub | No — it syncs |

The line falls where it does because of what an install is. Under v3.1 an install is two
files plus two side effects, and the side effects are the part a file listing cannot see.
Every one of the seed migrations exists because of a side effect or a file we stopped
writing; none of them exists because content changed.

If you are unsure, the question that settles it: *if a colleague upgraded and never read
the release notes, would anything on their disk now be wrong?* If yes, it needs a
migration, because release notes are not a mechanism.

## Naming

```
NNNN-kebab-case-description.py
```

Four zero-padded digits, monotonically increasing, followed by a description of the effect
in the imperative. `scripts/orchestrator.py` finds them with the glob
`[0-9][0-9][0-9][0-9]-*.py` and sorts them lexically, which is why the padding is not
cosmetic — `10-foo.py` sorts before `2-foo.py` and would run out of order.

**A number is used once and never reused, and a filename is never changed after it
ships.** The runner records the *stem* (`0003-narrow-gitignore-block`) in
`appliedMigrations` inside the install state, so the filename is the migration's identity.
Rename a migration and every repository that already ran it will run it again, this time
against a repository whose shape it no longer expects. Delete a migration and its entry
becomes an orphan nobody can explain.

## The Contract

Every migration is a standalone Python 3 script that takes `--repo PATH` and exports two
functions:

```python
def applies_to(state: dict) -> bool     # is there anything to do here?
def migrate(state: dict) -> dict        # do it; return a report
```

`state` is built by the script's own `read_state(repo, options)` and has exactly three
keys:

| Key | Contains |
|---|---|
| `repo` | `pathlib.Path` to the consumer repository being migrated |
| `install` | the parsed `.github/orchestrator-install.json`, or `None` if absent |
| `options` | the flags this run was given, as a plain dict |

The repository travels *inside* `state` rather than as a second parameter, and that is
deliberate: a migration that has to reach outside its argument for the path it operates on
or the flags it was given ends up with two answers to "what am I working on", and the two
drift the first time somebody adds a flag. One argument also means a caller — a test, or a
future runner — can exercise a migration by constructing a dict.

The rules the contract implies:

- **`applies_to` must be honest and cheap.** It is the only thing standing between a
  second run and a second application. Every seed migration's predicate is written so that
  running it twice in a row is a no-op, because the runner's `appliedMigrations` list
  protects the runner's path and nothing protects a developer running the script by hand.
- **`migrate` returns a report, and raises on failure.** The report is a dict describing
  what changed; the exception is what stops the run. Do not return a report with an error
  field and exit 0 — the runner reads the exit code, and a migration that fails quietly is
  worse than one that fails.
- **The script prints what it did.** `cmd_upgrade` captures stdout and echoes it indented
  under the migration's name, and on failure prints the last five lines of stderr. That
  output is the entire user-visible record of an upgrade, so a migration that succeeds
  silently has told nobody anything.
- **Exit non-zero on failure, zero on "did not apply".** Not applying is a normal outcome
  and must not stop an upgrade.
- **Never write outside the target repository.** A migration touches the repo passed in
  `--repo` and nothing else. It does not edit the hub, and it does not edit the user's
  editor configuration — see `0005`, which reports rather than moves for exactly that
  reason.
- **Delegate rather than duplicate.** `0003` shells out to `scripts/gitignore.py apply`
  instead of copying the managed-block body, because two copies of a block definition
  disagree the first time one of them changes.

Migrations import `scripts/_lib.py` for `read_json`, `write_json` and `utc_now`.
`write_json` is atomic; a hand-rolled write in a migration is how a process killed at the
wrong moment leaves truncated install state that every later run fails to parse. The
import carries `_lib`'s one dependency, `pyyaml`, which is already required to run
anything else in `scripts/`.

## Order, and Why a Failure Stops the Run

`python scripts/orchestrator.py upgrade` runs the migrations in filename order, skipping
any already listed in `appliedMigrations`, and **stops at the first non-zero exit**. It
writes the install state before returning, so the migrations that did succeed stay
recorded and a re-run resumes rather than restarts.

Stopping is not conservatism about unknown errors. Later migrations assume earlier ones
ran, and in this set the assumption is load-bearing:

- `0002` decides what it may delete by reading ownership out of the manifest that `0001`
  back-fills. Run alone against a pre-v3.1 repository, it sees an empty manifest, owns
  nothing, and reports that it can delete nothing — technically safe, but it has silently
  done none of the work it was supposed to do.
- `0004` reconciles the `skip-worktree` bits against the manifest entry `0001` writes.
  Without it, it can still read the bits from git, but it cannot tell which of them the
  orchestrator claimed.
- `0003` prints the files that became visible to git again by comparing against the
  manifest, and an empty manifest makes every file look foreign.

So a failure in `0001` does not merely leave `0001` undone. It turns `0002`, `0003` and
`0004` into migrations that run on false premises and report confident, wrong results —
which is worse than not running them, and much worse than stopping.

## The Seed Set (v3.0 → v3.1)

| Migration | Effect | Default |
|---|---|---|
| `0001-add-writes-manifest` | Back-fills the operations manifest. Every adopted path is **weak** ownership. | Applies |
| `0002-prune-synced-content` | Removes `.github/{agents,prompts,hooks,skills,contexts,memory/shared}/` — only paths the manifest owns. | **Dry run**; needs `--apply` |
| `0003-narrow-gitignore-block` | Rewrites the managed block from ten paths to two. | Applies |
| `0004-clear-skip-worktree` | Clears `skip-worktree` and `assume-unchanged` on paths no longer synced. | Applies |
| `0005-report-settings-migration` | Reports where the old `aiorchestrator.*` settings went. Writes nothing. | Reports |

`0002` is the only one that deletes files, and it is the only one that defaults to showing
you the plan instead of executing it. That asymmetry is the rule for anything added later:
a migration whose mistake is recoverable can apply itself, and a migration whose mistake
is a deleted file asks first.

The cost of that rule is worth stating plainly. `cmd_upgrade` records a migration in
`appliedMigrations` on any zero exit, and a dry run exits zero, so after an upgrade `0002`
is marked applied while having deleted nothing — and the next upgrade skips it. The
printed plan is the only prompt anybody gets. A migration that defers work to a human must
say so in its output, because the runner will not ask twice.

## Verifying One Before It Ships

There is no migration test harness, and pretending otherwise would be worse than saying
so. What is available:

```
python migrations/NNNN-name.py --repo /path/to/a/copy      # against a COPY, first
python scripts/orchestrator.py --repo /path/to/a/copy doctor
python scripts/orchestrator.py --repo /path/to/a/copy uninstall --dry-run
```

Note the argument order: `--repo` belongs to `orchestrator.py`'s top-level parser, so it
goes before the subcommand. Migration scripts take it after, because they have no
subcommands.

`doctor` after the migration is the check that matters most, and `uninstall --dry-run` is
the second: between them they read every part of the install state a migration can corrupt,
and a migration that leaves either of them describing the repository incorrectly has
broken the thing the manifest exists to make possible.
