# perfeng-analysis

Standalone Python library and CLI for offline k6, Playwright, and kube-burner
normalization, plus validation of performance policies and analysis-result claims.
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

For a native Playwright measurement artifact, omit the k6-only layout and
window assertion:

```sh
uv run --locked perfeng-analysis --manifest raw-result.json \
  --summary playwright-measurements.json --artifact-id ACTUAL-DECLARED-UUID \
  --producer-image REGISTRY/IMAGE@sha256:ACTUAL-DIGEST \
  --output normalized-result.json
```

The kube-burner pod-latency artifact uses the same option shape as Playwright:

```sh
uv run --locked perfeng-analysis --manifest raw-result.json \
  --summary podLatencyMeasurement-pod-startup-smoke.json \
  --artifact-id ACTUAL-DECLARED-UUID \
  --producer-image REGISTRY/IMAGE@sha256:ACTUAL-DIGEST \
  --output normalized-result.json
```

Replace placeholders with actual capture metadata. The producer image is the
analysis image actually executed, not the k6 image or an invented local digest.
The CLI checks its syntax; the orchestration adapter must attest correspondence.

The manifest must satisfy raw-result/v1 or raw-result/v2, contain the selected artifact,
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

For k6, choose the layout explicitly: typed accepts the prototype's type/values objects;
legacy-export accepts the flat summary-export shape tested with k6 2.2.0.
The new-machine-readable-summary format is not supported. Do not guess its layout.

Playwright input must use `playwright-measurements/v2`. Each duration name is
normalized as a lower-is-better latency in milliseconds because the source
contract declares `durationMs`; no other browser metric semantics are inferred.
Every selected metric must contain exactly one value for every declared
measurement iteration. The adapter calculates mean, median, p90, p95, p99,
population standard deviation, minimum, maximum, and CV. Percentiles use linear
interpolation (Hyndman-Fan type 7). The document's run, test, workload, window,
and creation time must agree with the raw manifest.

Kube-burner input must be the `kube-burner-pod-latency-json` artifact from the
reviewed `pod-startup-k8s` test and `pod-startup-smoke` workload. The producer
must use release-archive provenance. The adapter requires exactly the ten
distinct iterations and verifies every observation's run, job, metric, and
timestamp against the manifest. It computes distributions from the individual
observations rather than trusting kube-burner's derived quantile document.

The six explicit lower-is-better millisecond metrics cover scheduling,
initialization, containers-ready, pod-ready, containers-started, and
ready-to-start-containers latency. They use the same mean, median, percentile,
population standard deviation, minimum, maximum, sample-count, and CV
definitions as Playwright. Kube-burner `--metric` values are normalized metric
names such as `k8s.pod.ready.duration`; missing, unknown, empty, or duplicate
selections fail.

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
policy's pinned baselines and verifying that the supplied reference bytes and
artifact IDs are those approved immutable artifacts. This function does not
perform baseline selection or statistical significance testing.

## Build an analysis report

`build_analysis_report(...)` assembles a complete `analysis/v1` document from
the exact candidate bytes, policy bytes, artifact reference, producer identity,
and caller-supplied creation time. Policy-keyed `ReferenceInput` values bind each
available approved baseline ID and version to its verified bytes and artifact
claim. A missing policy baseline makes only its dependent regression rules
`INCONCLUSIVE`; other references remain independently usable. When multiple
baseline identities resolve to the same immutable artifact, the report includes
that artifact once while retaining every policy-to-artifact evaluation binding.

The builder verifies artifact sizes and SHA-256 checksums against the supplied
bytes, binds artifact run identities to their normalized documents, records the
exact policy checksum, forces non-blocking mode, and rejects reports that predate
their inputs. It validates the completed document before returning an isolated
object. Retrieving or publishing bytes and attesting the producer image remain
the caller's responsibilities.

The separate CLI keeps normalization compatibility intact and writes its result
with exclusive creation:

```sh
uv run --locked perfeng-report \
  --candidate normalized-result.json \
  --candidate-artifact normalized-artifact.json \
  --policy performance-policy.json \
  --producer-image REGISTRY/IMAGE@sha256:ACTUAL-DIGEST \
  --output analysis-result.json
```

Supply every available policy-selected baseline with a repeatable argument:

```sh
--baseline BASELINE_ID VERSION reference-result.json reference-artifact.json
```

The earlier `--reference reference-result.json` and `--reference-artifact
reference-artifact.json` pair remains supported for policies containing exactly
one distinct baseline. All inputs are explicit local files. The command performs
no discovery, downloads, or uploads, and it never overwrites an existing output.

## Container image

Build and verify the Linux AMD64 runtime locally:

```sh
docker build --platform linux/amd64 -t perfeng-analysis:local-check .
uv run --locked python scripts/image.py verify perfeng-analysis:local-check
```

The default entry point is the existing normalization CLI. Run report generation
with `--entrypoint perfeng-report`. The image is digest-pinned, contains the
locked production environment, and runs as UID/GID 65532 without network access
being required by either command. Mount explicit read-only inputs and a writable
output location when it is used by a Job.

The manual [image publication workflow](docs/images.md) builds and verifies the
image and optionally publishes it to GHCR. Deployments must pin the verified
final image digest printed by that workflow, not its mutable build tag, local
image ID, Python base digest, or uv image digest.

## Contracts and provenance

The wheel includes twelve immutable schemas and the upstream license from
perfeng-contracts commit badd9206a88a48042dda54a25c6e362088d23858 (bundle 0.13.0).
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

Point/window filtering, storage, baseline selection, and statistical
significance testing are not implemented here.
