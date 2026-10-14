# Contributing to perfeng-analysis

## TL;DR

- Deliver one coherent, verified analysis outcome per issue and pull request.
- Use MUST, SHOULD and MAY as defined below; lowercase wording is explanatory.
- Proceed on documented, reversible assumptions and stop for choices that
  materially affect statistical meaning, compatibility, security or external
  state.
- Prepare requested changes without staging or committing, then print issue
  content for the repository owner.
- Run exact checks, including packaging where applicable, and report unavailable
  checks as not run—never as passed.
- Use exact published milestone titles in the form `MNN — Outcome`.

## Policy language and sources of truth

- **MUST** and **MUST NOT** identify requirements. A deviation needs an explicit
  reviewer-approved exception recorded in the issue or pull request.
- **SHOULD** and **SHOULD NOT** identify strong defaults. A deviation is allowed
  only when its reason and trade-off are recorded.
- **MAY** identifies an optional choice.

Lowercase guidance does not silently create another normative level.

| Concern | Canonical source |
|:--|:--|
| Contributor workflow, issue timing, escalation and completion | This document |
| Concise contributor and agent entry point | [AGENTS.md](AGENTS.md) |
| Task-oriented documentation routing | [docs/README.md](docs/README.md) |
| Coding harness and verification tiers | [docs/development/harness.md](docs/development/harness.md) |
| Analysis and Python engineering | [docs/development/engineering-standards.md](docs/development/engineering-standards.md) |
| Dependency admission and supply-chain checks | [docs/development/dependency-policy.md](docs/development/dependency-policy.md) |
| Architecture decisions | [docs/decisions](docs/decisions/README.md) |
| Cross-repository milestones | [perfeng-environment roadmap](https://github.com/stanimirivanov/perfeng-environment/blob/main/docs/roadmap/milestones.md) |
| Supported behavior and exact commands | [README.md](README.md) |
| Image publication | [docs/images.md](docs/images.md) |

When sources conflict, the narrower source governs its concern. An accepted ADR
governs its decision until superseded. Surface unresolved conflict rather than
quietly choosing the convenient rule.

## Before starting

A contributor MUST inspect the branch and working tree and preserve unrelated
changes; read affected code, tests, fixtures, contract locks and documentation;
identify the smallest independently reviewable outcome; identify affected units,
statistics, quality states, contracts, consumers, packaging and operations; and
select the workflow under [Issue timing](#issue-timing).

A contributor MUST NOT discard, overwrite, reformat or incorporate unrelated
work to obtain a clean diff. Destructive operations and external writes outside
the task require explicit authorization.

An ADR MUST be proposed when a change establishes or revises durable statistical
semantics, compatibility, contract consumption, security, repository ownership,
foundational technology or cross-component behavior.

## Ambiguity and escalation

Before escalating, inspect relevant code, fixtures, contracts, tests,
documentation, ADRs and issue history and perform safe read-only investigation.

A contributor MAY proceed with a documented assumption only when it is local,
reversible and inexpensive; stays in scope; does not alter published semantics,
scientific conclusions, security or external state; does not weaken acceptance;
and would not materially change what reviewers believe they approve. Record the
assumption and consequence.

A contributor MUST stop for a decision when missing information could materially
change outcome, milestone, metric meaning, units, sample population, policy
verdict, compatibility, security, an irreversible action, publication or a
choice between materially different analysis designs. State evidence, options,
consequences and work that can safely continue.

## Issue timing

- When an issue number is supplied, follow its scope and milestone. A material
  mismatch follows the escalation rules.
- Without an issue number, prepare the smallest coherent requested change and
  print a complete proposed issue in the completion report. The owner creates
  the issue and then creates or renames the branch with its number.
- Contributors acting for the owner MUST NOT stage, commit, push, create or
  modify issues, create pull requests, publish wheels or images, create releases,
  or change milestones unless explicitly requested.
- Read-only investigation and scoping MAY occur before an issue exists.

Creating or modifying GitHub records, packages, images or releases is an
externally visible write and requires explicit authority.

## Milestones and required issue

Use exact published titles in the form `MNN — Short outcome`. Published
milestones MUST NOT be reused, renumbered or casually renamed. GitHub owns live
assignment; the centralized
[roadmap](https://github.com/stanimirivanov/perfeng-environment/blob/main/docs/roadmap/milestones.md)
owns intended outcomes and sequencing.

Every implementation issue uses:

```markdown
**Repository:** perfeng-analysis
**Milestone:** MNN — Outcome

## Goal

Describe the problem and observable result.

## Scope

- Included behavior and boundaries.

## Design decisions

- Choices, assumptions, statistical and compatibility effects, and ADRs.

## Security and operations

- Trust boundaries, evidence handling, publication, rollout and recovery.

## Acceptance criteria

- [ ] Observable analysis behavior and verification evidence.
- [ ] Relevant invalid, missing, unstable and inconclusive behavior.
- [ ] Documentation, packaging and consumer effects.

## Verification

- Required, focused fixture, wheel and image checks.

## Out of scope

- Explicit exclusions and deferred work.
```

Acceptance criteria MUST describe observable behavior or verifiable invariants,
not implementation activities. Known limitations MUST be visible.

## Pull-request-sized work

A pull request MUST solve one coherent analysis problem, leave the package
buildable, include code, fixtures, tests, documentation and packaging changes
required for the outcome, and prove important invalid or inconclusive behavior.

Split independent semantics, broad cleanup, dependencies and unrelated
formatting. A vertical change may touch parsing, normalization, evaluation,
reporting and fixtures when they form one observable result. Do not create
placeholder adapters or statistical abstractions for roadmap appearance.

## Development workflow

1. Select the workflow defined in [Issue timing](#issue-timing).
2. Prepare one focused change without staging, committing or pushing for the
   owner.
3. Add or update independently understandable fixtures and tests.
4. Implement the smallest coherent solution and update documentation.
5. Format and run exact checks.
6. Review the diff for secrets, generated churn, semantic changes, assumptions,
   lock/package drift and unrelated edits.
7. Print the canonical [completion report](#completion-report).
8. The owner creates or confirms the issue and branch, may adjust the change,
   commits with `[#N]`, pushes and opens the pull request.

Do not store task-specific issue bodies, PR descriptions or handoff notes in
the repository.

## External operations and destructive actions

Read-only inspection is allowed when relevant. Filesystem, Docker, registry,
GitHub and other mutations MUST remain within requested scope and authority.

- Analysis runtime behavior MUST remain offline and operate on explicit local
  inputs.
- Credentials and sensitive evidence MUST NOT appear in arguments, logs,
  fixtures, built distributions or Git.
- Output creation remains atomic and exclusive; existing results MUST NOT be
  overwritten as implicit recovery.
- Publishing wheels, images or releases requires explicit authorization and an
  immutable reviewed revision.
- Deletion, history changes and artifact replacement require explicit authority
  and verified exact targets.

## Verification and constrained environments

Resolve locked dependencies once after checkout or dependency changes:

```sh
make bootstrap
```

Run the network-independent inner loop before handoff:

```sh
make verify
```

Run the complete portable acceptance aggregate when current vulnerability data
is available:

```sh
make validate
```

The stable targets wrap these exact checks:

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked ty check
uv run --locked python -m unittest discover -s tests -v
uv build
```

`make verify` wraps the deterministic source and build checks and is offline
after `make bootstrap`. `make validate` adds the network-dependent supply-chain
checks. Changes affecting package resources MUST also run the installed-wheel
test from CI. Image or entry-point changes MUST build and verify the Linux AMD64
image as documented. The command ownership and timing tiers are recorded in the
[harness guide](docs/development/harness.md).

When a check cannot run because of sandbox, platform, network, credentials,
Docker or another environmental constraint, report the exact command as **not
run**, the blocker and attempts, checks that passed, residual risk, and where it
should run. Never weaken a check or claim an unexecuted check passed. Report a
failure even when it appears unrelated.

## Documentation

Every long narrative document MUST contain `## TL;DR` immediately after its
title and status metadata. A document is long when it has at least 800 words,
more than five second-level sections, or is an architecture, security,
compatibility, migration or operational guide readers consult selectively.
Issue and PR templates are excluded.

The TL;DR SHOULD state purpose, intended reader, important outcome and next
action in three to seven bullets. Statistical semantics, supported inputs,
contract provenance, CLI and packaging behavior change with the code that makes
them inaccurate. Accepted ADRs are historical; supersede rather than rewrite.

## Pull request description

A pull request MUST state the linked issue and milestone; outcome and exclusions;
assumptions and unresolved questions; statistical, contract and compatibility
effects; verification including checks not run; packaging, security,
publication, rollout and rollback; and known limitations.

## Review checklist

- [ ] MUST: The issue uses the required structure and exact milestone title.
- [ ] MUST: The change is one coherent analysis outcome.
- [ ] MUST: Units, direction, sample population, windows and missing values retain
      explicit meaning.
- [ ] MUST: Normalization, evaluation, report assembly and orchestration remain
      correctly separated.
- [ ] MUST: Success and relevant invalid/inconclusive paths are tested.
- [ ] MUST: Contract locks, fixtures, package resources and documentation agree.
- [ ] MUST: Analysis remains deterministic and offline.
- [ ] MUST: Applicable source, wheel and image checks passed or are reported.
- [ ] MUST: No secrets, result data, machine paths or unrelated churn are present.
- [ ] MUST: An ADR exists when the decision meets the ADR threshold.

## Completion report

After every work item, print the repository, exact milestone, proposed issue
title, complete issue body, assumptions and limitations, verification outcomes
distinguished as passed/failed/not run, and a suggested `[#N]` commit subject.
When an issue exists, repeat or amend it so delivered scope is auditable.
Printing the report does not publish external records.
