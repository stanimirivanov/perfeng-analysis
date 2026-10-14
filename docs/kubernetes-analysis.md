# Kubernetes benchmark analysis

## TL;DR

- Normalize individual kube-burner pod-latency observations, never its summary or derived quantiles.
- Keep historical archive/host captures separate from the exact contained OCI recipe.
- Reuse the existing offline normalizer, policy evaluator, baseline-reference inputs and report CLI.
- Unknown statistics and missing references remain inconclusive; no statistical significance is claimed.
- Environmental qualification, producer attestation and baseline approval remain caller-owned gates.
- Run `make verify`, `make validate` and the installed-wheel suite before promotion.

## Supported execution recipes

| Provenance | Workload | Support |
|:--|:--|:--|
| `release-archive` | `pod-startup-smoke` | Historical host/archive reader remains supported. |
| `oci-image` | `pod-startup-contained/1.0.0` | kube-burner 2.8.5 with exact workload SHA-256 `1dd90543d8cbd79014fbb522890463c0ee0c324d0ecff92973da58423500a29d`. |

Both use test ID `pod-startup-k8s`. The contained recipe comes from
`perfeng-k8s` commit `a0e2b670bea91af182aaff78c925f4a3c6d1d861`.
Its upstream Job is still named `pod-startup-smoke`; that observation field is
not the platform's workload identity. Do not rename observations to make them
fit or relabel an OCI execution as an archive.

The raw manifest must pass the existing `raw-result/v2` contract and integrity
checks. A mutable image tag, mixed archive/OCI fields, changed contained
workload/version/hash or unsupported tool version is rejected. An arbitrary
schema-valid workload is not an approved normalization recipe. This is an
additive reader capability; it does not rewrite old captures.

The bundled 0.13.0 schemas already express OCI provenance and the unchanged
raw-result, normalized-result, policy and analysis shapes used by bundle 0.22.0.
The new fixture verifies a 0.22.0 raw manifest through those pinned validators.
The input's `contractsVersion` is preserved, not relabelled as the validator
snapshot version. This change does not import the new benchmark-evidence
contract or upgrade unrelated packaged schemas.

## Offline workflow

Retrieve and verify the actual raw manifest and selected artifact through the
owning orchestration/storage boundary. Supply explicit local files:

```sh
perfeng-analysis --manifest raw-result.json \
  --summary podLatencyMeasurement-pod-startup-smoke.json \
  --artifact-id ACTUAL-DECLARED-UUID \
  --producer-image REGISTRY/ANALYSIS@sha256:ACTUAL-DIGEST \
  --output normalized-result.json
```

The producer image argument describes the analysis executable, not the
kube-burner runner or benchmark candidate. The caller attests those identities;
the CLI does not contact registries or authenticate image provenance.

The adapter verifies selected bytes against the manifest's SHA-256 and size,
ten unique iterations, Run/Job/measurement identity and offset-qualified
timestamps in the half-open measurement interval `[start, end)`. All six
latency distributions use milliseconds, lower-is-better direction, population
standard deviation and linearly interpolated sample percentiles. Missing,
negative or non-finite observations are errors, not zero latency. An explicitly
selected subset must still have complete observations for every selected metric.
Only the artifact actually normalized enters `sourceArtifacts`.

Use `perfeng-report` with the normalized bytes, their exact artifact claim,
policy, analysis producer image and policy-keyed `--baseline` inputs as described
in the [README](../README.md#build-an-analysis-report). Report creation verifies
artifact sizes/checksums and retains non-blocking mode. Both CLIs publish local
outputs atomically and exclusively; retries never overwrite existing evidence.
Failed input validation leaves no final output. There are no downloads, uploads,
cluster calls or baseline selection in the analysis process.

## Decisions and compatibility

The existing policy pipeline keeps quality, SLO and regression outcomes distinct:

- Inclusive SLO bounds produce PASS/FAIL only after measurement quality passes.
- Meeting or exceeding the practical degradation threshold is a regression FAIL.
- Missing metrics/statistics/sample counts/CV or approved references remain
  INCONCLUSIVE; excessive variability is UNSTABLE and unit mismatch is INVALID.
- Untrusted candidate/reference quality and a relative comparison against zero
  cannot produce a decisive regression result.

For `pod-startup-k8s`, candidate and reference workload ID, version and SHA-256
must match exactly. This prevents the host/archive and contained paths, or
different contained recipes, from becoming interchangeable baselines. Other
test families retain their existing comparison behavior. The caller still
checks the environment/profile fingerprint, candidate compatibility and
baseline approval; workload equality does not prove those facts.

Before using a report as a comparable benchmark decision, the caller must
independently verify measurement-scoped `kubernetes-benchmark-evidence/v1`
bytes, integrity and Run binding; trusted profile and cluster/environment
identity; complete capture coverage; pressure/interference observations; and
eligibility. REJECTED or UNKNOWN evidence is diagnostic only. This reader does
not inspect that evidence and its statistical quality PASS is not an
environmental qualification PASS. In particular, the local integration profile
is not a production-performance cohort. Ten observations and practical
point-estimate comparisons do not establish statistical significance.

## Verification and rollout

`tests/fixtures/kubernetes` contains synthetic observations, a byte-bound OCI
manifest and an illustrative policy. The image digest and artifact identities
are not a published runtime selection. Ready latency values are 100 through
109 ms: mean/median 104.5 ms, population variance 8.25 ms² and p95 108.55 ms.
Tests independently check all six distributions, then exercise the normalization
CLI, exact artifact claims, policy-keyed reference and report CLI together.

The decision matrix covers pass, SLO failure, regression, missing references,
missing measurements/statistics/quality evidence, insufficient samples,
candidate/reference instability, invalid units, zero-relative-reference and
threshold boundaries. Negative tests cover provenance/workload drift,
timestamp boundaries, checksum/size mismatch, summaries/quantiles mistaken for
observations, exclusive outputs and cross-workload references. The complete
suite also retains archive, k6 and Playwright compatibility coverage.

Run `make verify` and `make validate`, then repeat tests with the built wheel
installed without the source package using the CI command. No image entry point
changes or live execution are needed for this reader change. A later M04 runtime
promotion must build/verify/publish the analysis image and select its real
digest. Until then no deployed bundle changes. Rollback selects the prior reader
and disables contained OCI analysis; it never rewrites OCI evidence as an archive.
