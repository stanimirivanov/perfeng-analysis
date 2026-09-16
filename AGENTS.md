# Repository working agreement

## TL;DR

- Read `CONTRIBUTING.md`; it is the canonical workflow policy.
- Preserve statistical meaning, units, provenance and missing-data semantics.
- Keep normalization, evaluation, report assembly and orchestration concerns
  distinct.
- Run the exact checks and report their results honestly.

This file is the concise, tool-facing entry point for contributors and coding
agents. [CONTRIBUTING.md](CONTRIBUTING.md) is the canonical workflow policy.
Normative terms such as MUST, SHOULD and MAY have the meanings defined there.

## Before changing anything

1. You MUST read [CONTRIBUTING.md](CONTRIBUTING.md), especially its ambiguity,
   issue-timing, verification and external-side-effect rules.
2. You MUST inspect the branch and working tree and preserve pre-existing work.
3. You MUST read the relevant
   [engineering standards](docs/development/engineering-standards.md), contract
   provenance, image guide and accepted [ADRs](docs/decisions/README.md).
4. You MUST use repository-local checks and MUST NOT claim an unavailable or
   unexecuted check passed.

If implementation, fixtures, bundled contracts and documented statistical
meaning disagree, you MUST NOT silently pick one. Correct an obvious local
defect or propose a superseding ADR. Ordinary ambiguity follows CONTRIBUTING.

## Repository responsibility

`perfeng-analysis` owns offline normalization, measurement-quality evaluation,
SLO and regression comparison, analysis-report assembly, validation, and the
packaged analysis CLIs. It does not own test execution, artifact retrieval,
baseline approval/selection, orchestration or shared contract definitions.

- Shared contract meaning belongs in `perfeng-contracts`; this repository pins
  and validates an immutable snapshot.
- The caller supplies verified local bytes and attests producer/reference
  identity.
- Storage, scheduling and baseline lifecycle remain in their owning components.
- Output publication is atomic and exclusive; retries MUST NOT overwrite prior
  evidence.

## Shape of work

- Each task and pull request MUST deliver one coherent, independently
  reviewable analysis outcome.
- Statistical behavior changes, dependency updates and broad cleanup MUST stay
  separate unless inseparable for correctness.
- Scope, assumptions, supported inputs, unit/statistical effects, compatibility,
  affected consumers and verification evidence MUST be explicit.
- Prefer a working vertical analysis path over speculative frameworks or unused
  adapters.

## Analysis and implementation rules

- Missing or unavailable evidence is never zero and MUST NOT become a fabricated
  pass, failure, sample count, variance or percentile.
- Preserve declared units, metric direction, sample population and measurement
  window. Conversion or aggregation requires an explicit tested rule.
- Normalization describes measurements; evaluation applies policy; report
  assembly binds verified evidence. Keep these responsibilities separate.
- Structural contract validity does not prove scientific quality, trusted
  provenance or approved baseline selection.
- Parsed JSON, bundled schemas and caller-supplied files are untrusted input and
  MUST be bounded and validated before calculation.
- Analysis remains deterministic and offline. Runtime code MUST NOT discover,
  download or upload evidence.
- Python package resources MUST work from an installed wheel without the source
  tree.

Follow the engineering standards and relevant README sections.

## Quality and documentation

- Test observable statistical and contract behavior at the lowest boundary that
  proves it. Defect fixes SHOULD begin with a failing regression test.
- Use explicit fixtures with independently checkable expected values and cover
  malformed, missing, non-finite, duplicate and contradictory evidence.
- Tests MUST be deterministic and independent of network, locale, filesystem
  ordering and wall clock unless those are the subject.
- Comments SHOULD explain statistical decisions and constraints and SHOULD NOT
  narrate syntax.
- Long documents MUST include the TL;DR required by CONTRIBUTING.
- Code, fixtures, packaging, contract locks and documentation change together.

## Completion

The canonical required checks and completion-report format are defined in
[CONTRIBUTING.md](CONTRIBUTING.md). Follow them after every work item.
