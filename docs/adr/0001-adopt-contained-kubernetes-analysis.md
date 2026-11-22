# ADR-0001: Adopt the contained kube-burner recipe without merging cohorts

- Status: Proposed
- Date: 2026-10-14
- Milestone: M04 — Kubernetes Benchmark Decision Loop
- Deciders: Repository owner (pending review)
- Supersedes: None
- Superseded by: None

## TL;DR

- Add the reviewed OCI recipe alongside, not in place of, historical archive input.
- Preserve the existing six metric definitions, statistical algorithms and offline CLIs.
- Require identical Kubernetes workload identities for baseline comparison.
- Keep qualification/eligibility and provenance attestation separate from statistical quality.

## Context

M04 packages kube-burner 2.8.5 as a contained OCI runner with a new workload
identity. The archive-only analysis reader rejects that path even though its
packaged raw-result/v2 schema already represents OCI provenance. Accepting any
OCI workload or comparing host and contained results would silently merge
different execution conditions.

## Decision

Adopt `pod-startup-contained/1.0.0` at the exact reviewed workload hash from
perfeng-k8s commit `a0e2b670bea91af182aaff78c925f4a3c6d1d861`, paired with OCI
provenance and kube-burner 2.8.5. Retain archive/`pod-startup-smoke` behavior.
Normalize individual observations through the existing six metric mappings and
descriptive statistics. Reject Kubernetes candidate/reference workload identity
differences before evaluating regression. Other test families remain unchanged.

Reuse the pinned schemas and unchanged normalized/report contracts. Preserve
the manifest's contracts version. Do not introduce untyped qualification flags
into normalized metric metadata or interpret statistical quality as environmental
eligibility. The caller must verify the separately retained benchmark evidence,
selected environment/profile, runner identity and approved baseline.

## Alternatives considered

- Accept all OCI/workload combinations: less maintenance but admits unreviewed
  populations and execution semantics.
- Relabel contained executions as historical archive input: corrupts provenance
  and makes different workloads appear comparable.
- Add a parallel Kubernetes reporting engine or change result schemas: duplicates
  existing behavior without a new measurement requirement.
- Refresh every packaged schema: unnecessary for unchanged wire shapes and
  expands this reader change into unrelated contract migration.

## Consequences and compatibility

Archive captures remain readable; the contained OCI path is additive. Kubernetes
reference comparisons now fail closed on differing workload IDs, versions or
hashes. Changing the supported contained recipe requires a reviewed reader
update. A syntactically valid image digest is not authenticated provenance.
No database, API, CLI option or image entry-point changes are required.

## Security, operations and scientific limitations

Inputs remain explicit local files with verified artifact checksums and sizes.
Outputs remain atomic and exclusive. No network, cluster mutation, storage or
baseline approval authority is added. Local integration evidence is not a
production comparison cohort; missing qualification cannot grant eligibility.
Ten observations support descriptive statistics and policy's practical
point-estimate comparison, not statistical significance.

No runtime is promoted by this ADR. Later packaging must publish and select a
verified analysis image. Rollback repins the previous reader and retains raw
evidence without converting provenance.

## Validation

Synthetic byte-bound OCI fixtures exercise all six metrics, half-open timestamp
windows, provenance/recipe rejection, quality/SLO/regression decisions, baseline
identity and both CLIs. Run the complete source and installed-wheel suites,
`make verify` and `make validate`. See [the operating guide](../kubernetes-analysis.md).
