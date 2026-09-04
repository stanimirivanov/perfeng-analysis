# perfeng-analysis

Standalone Python library and CLI for offline k6 summary normalization and
validation of performance policies and analysis-result claims.
Use Python 3.12 and uv. No database, orchestration, or sibling repository is
required. Ruff handles lint/formatting; ty handles type checking.

## Development

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked ty check
uv run --locked python -m unittest discover -s tests -v
uv build
```

## Normalize

```sh
uv run --locked perfeng-analysis --manifest raw-result.json --summary summary.json \
  --artifact-id ACTUAL-DECLARED-UUID --producer-image REGISTRY/IMAGE@sha256:ACTUAL-DIGEST \
  --layout legacy-export --summary-covers-window --output normalized-result.json
```

Replace placeholders with actual capture metadata. The producer image is the
analysis image actually executed, not the k6 image or an invented local digest.
The CLI checks its syntax; the orchestration adapter must attest correspondence.

The manifest must satisfy raw-result/v1, contain the selected summary artifact,
and have valid run identities, unique artifact IDs/URIs, and ordered timestamps.
Summary bytes must match its checksum and size. Only the artifact actually used
appears in sourceArtifacts. Output satisfies normalized-result/v1 with result/v2
records. It is exclusively created; retries never overwrite prior results.
No network requests or uploads are performed.

--summary-covers-window is a caller assertion that this aggregate summarizes
exactly the manifest's measurement interval. A summary cannot prove that fact
or exclude warm-up/cooldown. Do not use this path when the interval is a subset
of the summary's capture: a later JSONL adapter must filter points first.

## Supported inputs and semantics

Choose the layout explicitly: typed accepts the prototype's type/values objects;
legacy-export accepts the flat summary-export shape tested with k6 2.2.0.
The new-machine-readable-summary format is not supported. Do not guess its layout.

Supported mappings are explicit in src/perfeng_analysis/normalizer.py:
HTTP duration/error rate/throughput, checkout/search duration (legacy and current
aliases), account operation duration, and business transaction error rate.
Unknown metrics are skipped by default; explicitly selecting an unknown/missing
metric fails. No supported measurements is an error, not an empty successful
result. Colliding aliases require explicit selection with --metric.

- Trend statistics are copied only when present. Missing/null sample counts
  stay missing/null. Explicit zero, negative, Boolean, or fractional counts fail.
- Error rates remain fractions with unit ratio, not percentages.
- Throughput uses the reported request rate with unit req/s; request totals
  are not observation counts. Scalar rates are represented as distribution.mean,
  without invented percentiles, variance, or sample counts.
- CV is derived only from available positive mean and non-negative standard
  deviation. Missing fields are never filled with zero.
- Thresholds remain raw evidence. They are not promoted to policy or regression
  decisions by this normalizer.

Raw files are never rewritten. Non-finite numbers and duplicate JSON keys are
rejected. Basic schema validation is not a scientific quality check.

## Validate analysis claims

`parse_policy(policy_bytes)` validates a performance-policy document.
`parse_analysis(report_bytes)` validates a report as a self-contained claim;
passing the exact policy bytes as the second argument additionally verifies the
policy checksum, identity, rule coverage, metric selectors, quality evidence,
SLO arithmetic, and regression arithmetic. Both entry points reject duplicate
JSON keys and non-finite numbers and resolve schemas only from the wheel.

Validation does not retrieve artifacts, select a baseline, recompute statistics,
or generate a verdict. Callers must verify artifact bytes before trusting the
measurements referenced by a structurally and semantically valid report.

## Evaluate a candidate

`evaluate_candidate(normalized_bytes, policy_bytes)` evaluates each policy rule
in declaration order. It checks the normalized envelope's run, source-artifact,
and metric identities before using a measurement. Missing metrics, statistics,
sample counts, or required variability evidence produce `INCONCLUSIVE`; unit
mismatches produce `INVALID`; and a coefficient of variation above the policy
maximum produces `UNSTABLE`. SLO bounds are inclusive and yield `PASS` or `FAIL`
only when measurement quality passes.

The returned evaluations conform to the analysis-result rule shape. Regression
is explicitly `NOT_EVALUATED`: reference selection and candidate-versus-reference
comparison are a separate stage. Producer-supplied legacy thresholds never
override the platform policy.

## Compare with an approved reference

`compare_candidate(candidate_bytes, reference_bytes, policy_bytes,
reference_artifact_id=...)` evaluates the same quality and SLO outcomes and adds
a point-estimate regression comparison. It supports absolute and relative
practical differences and applies the policy's lower-is-better or
higher-is-better direction. Meeting the configured degradation threshold is a
failure; improvements and smaller changes pass.

Both candidate and reference quality must pass. Missing reference evidence,
direction mismatches, zero-valued relative references, and non-representable
effects produce `INCONCLUSIVE`. The caller remains responsible for resolving the
policy's pinned baseline and verifying that the supplied reference bytes and
artifact ID are that approved immutable artifact. This function does not perform
baseline selection or statistical significance testing.

## Contracts and provenance

The wheel includes nine immutable schemas and the upstream license from
perfeng-contracts commit 82baa78c9a08851431688f647e69a09d66da42f1 (bundle 0.6.0).
The packaged contracts/lock.json checks their exact bytes before use. No
runtime schema fetching occurs. Update the snapshot in a reviewed change.

Adapted from performance-platform commit
57c1b5074898d4d86476e8b4f99c19eff3a77018:
platform/src/perfeng/normalizer/k6_normalizer.py,
platform/tests/unit/normalization/test_k6_normalizer.py, and
examples/k6/sample-k6-output.json. The prototype fixture is retained; the
implementation and tests are adapted for the new contracts and corrected units.
This records provenance; Git ancestry import is a separate owner-operated step.
The prototype remains untouched.

tests/fixtures/k6-2.2.0-summary.json is an actual summary from the earlier
perfeng-k6 loopback checkout fixture (three iterations). It tests flat export
compatibility, not production latency or statistical reliability. CLI test
manifests and image digests are explicitly synthetic test data.

CI also installs the built wheel in an isolated environment and repeats the
tests, so missing packaged contract resources fail validation.

Point/window normalization, storage, image publication, baseline selection, and
statistical significance testing are not implemented here.
