# Architecture decision records

## TL;DR

- Use an ADR for durable decisions affecting statistical meaning, compatibility,
  security, ownership or cross-component behavior.
- Number ADRs sequentially and never reuse a number.
- Allocate from fresh repository state and renumber concurrent collisions.
- Accepted ADRs are historical records; supersede rather than rewrite them.
- Record alternatives, consequences, scientific limitations and validation.

## When an ADR is required

Create an ADR when a decision materially affects statistical algorithms or
interpretation, public compatibility, contract consumption, security or privacy,
repository ownership, foundational technology, packaging topology or
cross-component behavior. Cheap local implementation choices do not need one.

## Naming and lifecycle

Use a four-digit sequence and short kebab-case name:

```text
0001-select-regression-method.md
```

Statuses are Proposed, Accepted, Rejected, Deprecated or Superseded. Add every
ADR to the index and do not rewrite accepted decisions or consequences.

Immediately before creating an ADR, refresh the branch as the workflow allows
and inspect this index and directory. Allocate the lowest unused number. If
concurrent work collides, rename the later ADR to the next available number and
update its title, index and references. Published numbers remain immutable.

## Template

```markdown
# ADR-NNNN: Decision title

- Status: Proposed
- Date: YYYY-MM-DD
- Milestone: MNN — Outcome
- Deciders:
- Supersedes:
- Superseded by:

## Context

What forces a decision now? Include statistical and compatibility constraints.

## Decision

State the decision and scope precisely.

## Alternatives considered

### Alternative

- Benefits:
- Costs and risks:
- Reason not selected:

## Consequences

### Positive

### Negative

### Neutral or follow-up

## Compatibility and migration

## Security and operations

## Scientific limitations

## Validation

How will assumptions and consequences be verified?
```

## Index

| ADR | Status | Title |
|:--|:--|:--|
| [0001](0001-adopt-contained-kubernetes-analysis.md) | Proposed | Adopt the contained kube-burner recipe without merging cohorts |

| [0002](0002-support-linux-hosts.md) | Proposed | Support Linux development and native browser hosts; retire active Windows support. |
