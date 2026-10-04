# Overlay: `algoworks`

This directory is where organization-specific content lives, and it is the **only** place
in this repository where it is allowed to live.

## The Mechanism

Any file at `overlays/<profile>/<relative-path>` is merged over the same relative path in
the content plane at sync time. The overlay wins.

```
overlays/algoworks/config/tool-registry.json    ->    config/tool-registry.json
overlays/algoworks/memory/shared/instincts.md   ->    memory/shared/instincts.md
overlays/algoworks/templates/dotnet/Service.cs.tmpl  ->  templates/dotnet/Service.cs.tmpl
```

The active profile comes from `hub.config.json`:

```json
"overlay": { "enabled": true, "profile": "algoworks", "path": "overlays/algoworks" }
```

and is recorded per repository as `overlayProfile` in
`.github/orchestrator-install.json`, so a repository can always answer which overlay it
was built with. The plugin exposes the same choice as the `org_profile` user config, whose
value must match a folder name here — a profile naming a directory that does not exist
resolves to no overlay at all, which is a silent no-op rather than an error, so check the
spelling.

An overlay file that has no counterpart in the content plane is still copied. That is how
you add something the neutral hub does not have; it is not how you fix a typo in something
it does.

## The Three Supported Override Targets

Only three shapes are supported, and each has a different merge semantic because a single
semantic would be wrong for at least two of them.

### 1. `config/tool-registry.json` — globs are MERGED, not replaced

`toolGlobs` in the overlay is unioned with the base list. The composed `toolChains` and
`defaults` blocks follow whole-key replacement, but the glob list specifically is additive.

This is the one exception worth understanding rather than memorizing. The base registry's
globs are what makes the shared skills work at all; an organization adding
`mcp_internal_*` almost never means "and remove GitHub". Whole-file replacement would make
that removal the default outcome of adding one entry, and the failure is silent — tools
simply stop resolving, in a skill nobody edited, for a reason nothing logs. Merging makes
addition the default and removal something you have to state.

### 2. `memory/shared/*.md` — appended

Overlay memory files are appended to the hub's, not substituted for them. The hub's shared
memory holds lessons that generalize across every organization that forks this repository;
the overlay's holds lessons about one organization's stack, conventions, and recurring
incidents. Both are true at once, so replacing one with the other would discard evidence
rather than override it.

Note the asymmetry with `scripts/memory.py`: the files under `memory/shared/` are a
rendering of `memory/index/entries.json`, and hand edits to a rendered file are lost on the
next render. An overlay memory file is not a hand edit to the rendering — it is a separate
document appended at sync time — but if an organization wants a lesson to participate in
promotion and confidence scoring, it belongs in the store via `memory.py capture`, not
here.

### 3. `templates/**` — replaced

Scaffolding is replaced wholesale. A code template is a single artifact with a coherent
shape; there is no useful way to merge two versions of a `.tmpl` file, and a partial merge
would produce a file that compiles nowhere. Whole-file replacement is the honest semantic,
and it is why the templates directory is the natural home for anything genuinely
org-shaped: house naming, the logging call your platform team actually uses, the header
your repositories carry.

Anything outside these three targets is not a supported override. If you find yourself
wanting to overlay an agent file or a skill, that is a signal the neutral version is
carrying an assumption it should not — fix it there instead.

## Why `config/` and `agents/` Must Stay Org-Neutral

The hub is meant to be forkable. Another organization should be able to clone it, write
their own `hub.config.json`, drop in `overlays/<their-profile>/`, and have a working
system — without reading every agent file hunting for a team name, a tool prefix, or a
repository URL that only makes sense in one company.

That is not a stylistic preference. It is what makes the neutrality gate in
`scripts/validate-structure.py` *enforceable* rather than aspirational. The gate greps
every `.ts`, `.js`, `.json`, `.yml`, `.md`, `.py`, `.ps1` and `.tmpl` file for a foreign
organization pattern and fails CI on a hit, and it can only do that because there is a
sanctioned place for the strings it is looking for. `overlays/` and `hub.config.json` are
excluded from the scan; everything else is fair game. A rule with no exception mechanism
gets exceptions added to it one file at a time until it means nothing — which is also why
the gate pins the size of its own exclusion list, so growing the escape hatch is a
reviewable line in a diff instead of a quiet edit.

The practical rule when you are about to write an org-specific string into `config/` or
`agents/`: it goes in an overlay, or it goes in `hub.config.json`, or it does not go in.
There is no fourth option, and CI will say so before review does.
