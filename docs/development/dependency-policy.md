# perfeng-analysis dependency policy

## TL;DR

- Runtime dependencies must serve current analysis behavior and remain separate
  from development-only quality tools.
- `pyproject.toml` declares intent and `uv.lock` records the exact resolved
  graph; update them together through `uv`.
- `make verify` is offline after bootstrap; `make supply-chain` uses current
  vulnerability data and normally requires network access.
- Review license, maintenance, security, determinism and replacement cost
  before admitting a dependency.
- Dependency updates are focused changes and must preserve source, wheel and
  image behavior where applicable.

## Dependency boundaries

Libraries under `[project.dependencies]` ship with `perfeng-analysis` and form
part of its runtime and image attack surface. Ruff, ty and other development
tools belong under `[dependency-groups].dev`; they MUST NOT become wheel runtime
requirements merely to simplify local tooling.

Python's development group already provides the necessary tooling separation.
Do not create a second project or introduce another language toolchain solely
to imitate another repository's harness layout.

## Admission criteria

A new dependency MUST have a concrete current use, a maintained release, a
license compatible with Apache-2.0 distribution, bounded and understood input
behavior, and a proportionate replacement boundary. Prefer the standard library
for small deterministic repository tooling when that avoids a lasting runtime
or build dependency.

Parsing and validation libraries operate on untrusted evidence. Their limits,
format behavior and failure semantics require explicit tests; structural
validation never substitutes for scientific-quality checks.

## Locking and updates

- Change declared requirements and `uv.lock` together using `uv`.
- Do not hand-edit the lock to obtain a preferred diff.
- Keep dependency-only upgrades separate from statistical behavior changes
  unless inseparable for correctness or security.
- Run `make bootstrap`, `make verify` and `make supply-chain` after an update.
- Changes affecting packaging or runtime resources also run installed-wheel and
  image checks as applicable.

GitHub Actions MAY use release tags or commit SHA pins; the harness does not
require semantic-major tags. Retain readable version comments alongside SHA
pins where practical and review every action update. This does not relax
immutable product image digests or contract checksums.

Dependabot may propose grouped GitHub Actions updates. Python updates remain a
manual, lockfile-aware workflow until the hosted updater supports the pinned uv
toolchain reliably. Every dependency change remains subject to normal review;
automation is not evidence that compatibility or statistical meaning is
preserved.

## Vulnerabilities and licenses

`uv audit --locked` checks the resolved graph against current vulnerability
data. The Make target audits the supported Linux resolution targets
explicitly. A finding is assessed for reachability, affected version, fix
availability and operational exposure; exceptions require an owner, rationale
and review trigger rather than a silent ignore.

Python package license metadata is not uniformly reliable. Until a maintained,
pinned allowlist tool is adopted and its baseline reviewed, license admission is
a required human review rather than a falsely authoritative automated pass. The
absence of a `make license` target is deliberate and MUST NOT be described as
automated license compliance.

## Constrained environments

Bootstrap and vulnerability lookups may need network access. The inner loop is
designed to run with `uv --offline` after bootstrap. If current advisory data or
another required input is unavailable, follow CONTRIBUTING: report the exact
command as not run, the blocker, evidence that did run and the residual risk.
