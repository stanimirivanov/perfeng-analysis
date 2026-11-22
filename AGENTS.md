# Repository agent guide

## Agent skills

Use `mattpocock/skills` as the primary workflow for planning, ticketing,
implementation, TDD, review, and pull requests. The skills take precedence where
contributor guidance covers the same steps. Follow the repository's technical
requirements, CI gates, and authorization boundaries.

### Issue tracker

Use GitHub Issues in `stanimirivanov/perfeng-analysis`. See [issue tracker configuration](docs/agents/issue-tracker.md).

### Triage labels

Use the default Matt Pocock label mapping. See [triage labels](docs/agents/triage-labels.md).

### Domain docs

Single context with a root glossary and ADRs in `docs/adr/`. See [domain docs](docs/agents/domain.md).

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
  proves it.
- Use explicit fixtures with independently checkable expected values and cover
  malformed, missing, non-finite, duplicate and contradictory evidence.
- Tests MUST be deterministic and independent of network, locale, filesystem
  ordering and wall clock unless those are the subject.
- Comments SHOULD explain statistical decisions and constraints and SHOULD NOT
  narrate syntax.
- Long documents MUST include the TL;DR required by CONTRIBUTING.
- Code, fixtures, packaging, contract locks and documentation change together.

## Verification

Run `make verify` and the applicable additional checks documented in
[CONTRIBUTING.md](CONTRIBUTING.md#verification-and-constrained-environments).
Use the [documentation map](docs/README.md) to find affected standards, operational
guides and decisions. Report checks as passed, failed or unavailable.
