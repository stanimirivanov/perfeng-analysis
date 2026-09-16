# Analysis engineering standards

## TL;DR

- Preserve measurement and statistical meaning before optimizing code shape.
- Keep normalization, evaluation, comparison, report assembly and I/O separate.
- Make units, sample populations, windows, direction and missingness explicit.
- Treat every document and packaged contract as untrusted until validated.
- Keep runtime analysis deterministic, bounded and offline.
- Verify both source and installed-wheel behavior with reproducible fixtures.

## Policy strength

Normative terms use the meanings in
[CONTRIBUTING.md](../../CONTRIBUTING.md#policy-language-and-sources-of-truth).
MUST and MUST NOT are requirements; SHOULD and SHOULD NOT are strong defaults
requiring a recorded reason to deviate; MAY is optional.

## Architecture and ownership

Organize around input normalization, distribution calculation, quality/SLO
evaluation, reference comparison, report assembly, validation and output
publication.

- Normalizers translate one explicit source format into contract metrics. They
  do not select policy or decide regressions.
- Evaluators apply explicit policy to validated normalized evidence. They do
  not retrieve or approve baselines.
- Comparators operate on caller-supplied verified candidate/reference evidence
  and explicit policy.
- Report assembly binds exact bytes and identities; it does not attest external
  provenance or publish artifacts.
- CLI and filesystem adapters validate inputs and preserve atomic output; core
  statistical functions remain independent from process and storage concerns.
- Shared contract definitions remain in `perfeng-contracts`.

Use SOLID and patterns as reasoning tools, not quotas. Prefer cohesive functions,
immutable values, composition and direct code over generic processors, managers
or speculative plugin systems.

## Statistical semantics

- Every metric has an explicit name, unit, statistic and better/worse direction.
- Preserve the exact sample population and measurement window. Do not mix
  warm-up, measurement and cooldown or candidate/reference cohorts implicitly.
- Missing, null, unavailable and zero are distinct. Never fabricate evidence to
  complete a result.
- Sample counts are positive integers when known. Request totals, rates and
  iteration counts are not interchangeable observation counts.
- Percentile algorithms, variance convention and coefficient-of-variation
  definition are part of observable behavior and require regression fixtures.
- Unit conversion requires an explicit dimensionally valid rule and tests.
- Quality, SLO and regression outcomes remain independent. Insufficient or
  unstable evidence cannot produce a decisive regression verdict.
- Practical significance and statistical significance are distinct; do not
  claim the latter until an implemented method supports it.
- Structural schema validity does not establish scientific quality or trusted
  provenance.

## Python design

- Use the Python version in `.python-version`, dependencies in `uv.lock`, Ruff
  formatting and the configured type checker.
- Type public functions and parsing/application boundaries. Normalize untyped
  data at adapters and isolate necessary `Any` values.
- Use dataclasses or small classes for values with behavior and frozen values
  where mutation is not part of the model.
- Use `Protocol` only for meaningful consumer contracts or test seams. Do not
  introduce abstract base classes by default.
- Raise precise exceptions for exceptional failures and explicit analysis
  outcomes where callers are expected to branch.
- Preserve causes and do not catch `Exception` merely to relabel every failure.
- Prefer `pathlib`, context managers, iterators and standard-library facilities.
- Keep import-time behavior side-effect-free.
- Docstrings describe public purpose, contracts, failures, units and non-obvious
  side effects without repeating signatures.

## Input, output and resource safety

- Reject duplicate JSON keys, non-finite numbers, ambiguous layouts, identity
  mismatches, size/checksum mismatches and unsupported contract generations.
- Bound input bytes, nesting, collections, diagnostic output and computational
  work before expensive processing.
- Resolve packaged schemas locally and verify their lock; runtime code MUST NOT
  fetch schemas or evidence.
- Write outputs in the destination directory, flush complete bytes, and publish
  atomically and exclusively. A failed attempt leaves no partial final file.
- Never overwrite existing evidence on retry.
- Do not log raw potentially sensitive measurement payloads or credentials.

## Contracts, packaging and compatibility

- Treat CLI behavior, Python APIs, packaged schemas, contract locks, output
  documents and image entry points as compatibility boundaries.
- Never change a published field or metric's meaning in place.
- Update the pinned contract snapshot only through a reviewed change that
  verifies exact bytes, license and affected consumer behavior.
- Package resources MUST resolve from an installed wheel without the source
  checkout.
- Build artifacts are reproducible from `pyproject.toml` and `uv.lock` and do
  not contain tests, credentials, results or machine-local state unless the
  distribution contract explicitly requires them.
- Images use the locked production environment, non-root identity and explicit
  entry points; publication uses the verified final digest.

## Testing

- Use small fixtures with independently understandable expected statistics.
- Test exact boundary values, direction changes, missingness, unstable evidence,
  zero references, unit mismatch, unsupported layouts and contradictory claims.
- Defect fixes SHOULD begin with a failing regression test.
- Tests MUST be deterministic, isolated and independent of network, locale,
  filesystem ordering and wall clock unless those are the subject.
- Source tests prove development behavior; installed-wheel tests prove packaging;
  image probes prove container identity and entry points. One does not replace
  another.
- Coverage is diagnostic evidence, not a target.

## Documentation and dependencies

- Document supported source formats, algorithms, units, assumptions,
  limitations, quality outcomes and caller responsibilities.
- Comments explain statistical decisions and constraints, not syntax.
- Long documents follow the TL;DR policy in CONTRIBUTING.
- Dependencies require a current need, compatible license, maintained release,
  pinned resolution, security review and a proportionate replacement boundary.

## Required verification

Run the exact source checks in CONTRIBUTING, the installed-wheel test for
package-resource changes, and image verification for container changes.
Unavailable checks follow the constrained-environment protocol and MUST NOT be
reported as passed.
