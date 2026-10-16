# perfeng-analysis coding harness

## TL;DR

- Use the [documentation map](../README.md) to load only the policy and domain
  guidance relevant to the task.
- Run `make bootstrap` once when locked dependencies change, then use
  `make verify` as the network-independent development loop.
- Run `make validate` before handoff; it adds current vulnerability data to the
  deterministic verification suite.
- Package-resource changes also need the installed-wheel check, and image
  changes need the documented Linux AMD64 image verification.
- Report every unavailable check explicitly; never present an unexecuted check
  as passed.

## Purpose

The harness combines guidance read before editing with deterministic feedback
after each change. It makes the repository's statistical, packaging and
workflow expectations discoverable without asking contributors to read every
document or remember CI-only commands.

This inventory does not replace the root [Makefile](../../Makefile),
[CONTRIBUTING.md](../../CONTRIBUTING.md) or the analysis
[engineering standards](engineering-standards.md).

## Cost and timing tiers

| Tier | Intended timing | Characteristics |
|:--|:--|:--|
| T0 — route | Before editing | Read-only task routing through `AGENTS.md`, `CONTRIBUTING.md` and the documentation map. |
| T1 — inner loop | During editing | Focused tests and `make verify`; deterministic and offline after bootstrap. |
| T2 — acceptance | Before handoff | `make validate`, including vulnerability data that normally requires network access. |
| T3 — specialized | When the changed boundary requires it | Installed-wheel tests, Linux AMD64 image verification or publication workflows. |

Cost tiers describe when feedback belongs, not permission to skip an applicable
check. The constrained-environment protocol in CONTRIBUTING always applies.

## Command surface

| Command | What it establishes |
|:--|:--|
| `make bootstrap` | Locked Python and development dependencies are available. |
| `make doctor` | The effective Git, uv, Python and Make toolchain is visible. |
| `make fmt` | Repository-owned Python is formatted; inspect the resulting diff. |
| `make docs-check` | Local links, TL;DR policy, ADR bookkeeping and templates satisfy mechanical policy. |
| `make check` | Formatting, documentation policy, lock state, lint and static types pass. |
| `make test` | The deterministic source test suite passes. |
| `make build` | Source and wheel distributions build from locked inputs. |
| `make verify` | Checks, tests and distribution build pass without network after bootstrap. |
| `make vuln` | The locked dependency graph is checked against current vulnerability data for supported Linux and Windows targets. |
| `make supply-chain` | The repository's automated dependency-risk checks pass. |
| `make validate` | The complete portable acceptance aggregate passes. |

`make validate` deliberately excludes Docker and publication. Package-resource
changes additionally run the installed-wheel command from CONTRIBUTING. Image
or entry-point changes additionally build and verify the image as documented in
[the image guide](../images.md).

The source test suite includes a direct-import boundary check: modules outside
the named CLI/output adapters cannot import those adapters, and runtime modules
cannot import process or network client modules. New modules follow the core
rule by default. The check permits local URL parsing and packaged-resource
reads. It is a structural early warning, not a sandbox or a replacement for
behavioral tests of offline operation.

## Feedback design

A recurring review finding SHOULD become one of:

1. clearer guidance in the narrow canonical document;
2. an early deterministic check with an actionable failure;
3. a focused behavioral regression test; or
4. an explicit, owned exception when automation would be misleading.

Checks MUST NOT silently rewrite expected output, weaken statistical or
compatibility invariants, require ambient unpinned packages, or report an
unavailable dependency as healthy. Failures should identify the affected path,
the violated rule and the likely correction.

## CI mapping

The existing Linux `validate` job remains the stable required context and keeps
the installed-wheel and image probes it historically covered. Windows
verification proves the portable inner loop. Supply-chain feedback is separate
because it depends on current external vulnerability data and has a different
failure mode.

The harness does not constrain GitHub Action reference styles. Tags and commit
SHA pins are reviewed through the normal dependency workflow. Product image
digests and contract checksums remain immutable content identities and are not
replaced by floating tags.

## Maintaining the harness

Harness changes are ordinary reviewed changes. Measure false positives,
runtime, repeated suppressions and escaped defects. Update this guide, the
documentation map, Make targets and CI together whenever the command surface or
feedback ownership changes.

