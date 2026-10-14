# perfeng-analysis documentation map

## TL;DR

- Start with [CONTRIBUTING.md](../CONTRIBUTING.md) for workflow policy, then
  use this map to load only the sources relevant to the task.
- Product behavior and exact commands belong in the root
  [README](../README.md); engineering constraints belong in the development
  guides; durable decisions belong in ADRs.
- Analysis changes must preserve statistical meaning, contract provenance and
  installed-package behavior.
- Update this map when a canonical document moves or a recurring task lacks a
  clear route.

## Route by task

| Task or changed area | Read before changing it | Verify or consult as needed |
|:--|:--|:--|
| Contributor workflow, issue scope or completion report | [CONTRIBUTING.md](../CONTRIBUTING.md) | [Agent entry point](../AGENTS.md) |
| Normalization, evaluation, comparison or reporting | [Analysis engineering standards](development/engineering-standards.md), relevant [README](../README.md) section | Contract fixtures and focused tests |
| Contained Kubernetes OCI analysis and decision fixtures | [Kubernetes analysis](kubernetes-analysis.md), [ADR 0001](decisions/0001-adopt-contained-kubernetes-analysis.md) | Source and installed-wheel suites; caller-owned qualification and baseline eligibility |
| CLI, output publication or package resources | [Analysis engineering standards](development/engineering-standards.md) | Installed-wheel and image checks documented in the [harness guide](development/harness.md) |
| Build, CI, repository policy or developer experience | [Harness guide](development/harness.md) | [Dependency policy](development/dependency-policy.md), `make docs-check`, `make verify` |
| Dependency admission, updates or vulnerabilities | [Dependency policy](development/dependency-policy.md) | [Security policy](../SECURITY.md), `make supply-chain` |
| Runtime image or publication | [Image guide](images.md) | Image verification and manual publication workflow |
| Durable statistical, compatibility, ownership or security decision | [ADR index](decisions/README.md) | Relevant fixtures and affected consumer documentation |
| Supported commands and analysis behavior | [README](../README.md) | `make help` |
| Vulnerability reporting | [Security policy](../SECURITY.md) | Relevant trust-boundary documentation |

## Canonical collections

- [Development](development/) contains engineering, harness and dependency
  policy.
- [Decisions](decisions/README.md) records durable choices and their lifecycle.
- [Image publication](images.md) defines the container build, verification and
  publication boundary.
- [Security](../SECURITY.md) defines vulnerability reporting and contribution
  expectations.

## Keeping the map useful

A change MUST update this page when it adds, renames, moves or removes a
canonical source or creates a recurring task without a clear route. Keep this
page focused on routing rather than copying policy or implementation detail.
`make docs-check` validates repository-local links and documentation structure;
semantic accuracy still requires review.
