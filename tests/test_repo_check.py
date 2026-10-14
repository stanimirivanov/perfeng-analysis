from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.repo_check import check_repository


class RepositoryPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self._write(
            "CONTRIBUTING.md",
            """# Contributing

## TL;DR

- Follow policy.

## Required issue structure

```markdown
**Repository:** perfeng-analysis
**Milestone:** M03 — Outcome

## Goal

Result.

## Scope

- Included.

## Design decisions

- Decision.

## Security and operations

- Boundary.

## Acceptance criteria

- [ ] Behavior.

## Verification

- Checks.

## Out of scope

- Deferred.
```
""",
        )
        self._write(
            ".github/ISSUE_TEMPLATE/work-item.md",
            """---
name: Work
---
**Repository:** perfeng-analysis
**Milestone:** M03 — Outcome

## Goal

## Scope

## Design decisions

## Security and operations

## Acceptance criteria

- [ ] Behavior.

## Verification

## Out of scope
""",
        )
        self._write(
            ".github/PULL_REQUEST_TEMPLATE.md",
            """## Linked work
- Issue:
- Milestone:
## Outcome and scope
Problem and resulting behavior:
Boundaries and deliberate exclusions:
Assumptions and unresolved questions:
## Design, compatibility and operations
- ADRs:
- Statistical or measurement-semantic effects:
- Contract, CLI and package compatibility effects:
- Security effects:
- Rollout, recovery and rollback:
## Verification
Commands and non-secret evidence:
Checks not run, blocking reason and residual risk:
## Limitations and review
Known limitations and follow-up:
""",
        )
        self._write(
            "docs/decisions/README.md",
            """# Architecture decision records

## TL;DR

- Index.

## Index

| ADR | Status | Decision |
|:--|:--|:--|
| [0001](0001-use-policy.md) | Accepted | Use policy. |
""",
        )
        self._write(
            "docs/decisions/0001-use-policy.md",
            """# ADR-0001: Use policy

- Status: Accepted
- Date: 2026-09-29
- Milestone: M03 — Outcome
- Deciders: Owner
- Supersedes: None
- Superseded by: None

## TL;DR

- Decision.

## Context

Context.
""",
        )
        self._write("docs/guide.md", "# Guide\n\n## Section\n\nText.\n")
        self._write("README.md", "# Project\n\n[Guide](docs/guide.md#section)\n")
        self._write(
            "docs/references.md",
            '# References\n\n[guide]: <guide.md#section> "Guide"\n',
        )
        self._write(
            ".github/workflows/validate.yml",
            "name: Validate\njobs:\n  validate:\n    steps:\n      - uses: actions/checkout@v7\n",
        )

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_accepts_consistent_repository(self) -> None:
        self.assertEqual([], check_repository(self.root))

    def test_reports_links_tldr_and_action_hashes(self) -> None:
        self._write(
            "docs/migration-guide.md",
            "# Migration\n\n## Steps\n\n[Missing](absent.md)\n",
        )
        self._write(
            ".github/workflows/validate.yml",
            "name: Validate\njobs:\n  validate:\n    steps:\n      - uses: actions/checkout@abcdef\n",
        )

        rules = [violation.rule for violation in check_repository(self.root)]

        self.assertIn("docs.internal-link", rules)
        self.assertIn("docs.tldr", rules)
        self.assertIn("workflow.action-version", rules)

    def test_reports_adr_and_template_drift(self) -> None:
        issue = self.root / ".github/ISSUE_TEMPLATE/work-item.md"
        issue.write_text(
            issue.read_text(encoding="utf-8").replace("## Scope", "## Included"), encoding="utf-8"
        )
        adr = self.root / "docs/decisions/0001-use-policy.md"
        adr.write_text(
            adr.read_text(encoding="utf-8").replace("- Status: Accepted", "- Status: Unknown"),
            encoding="utf-8",
        )

        rules = [violation.rule for violation in check_repository(self.root)]

        self.assertIn("adr.status", rules)
        self.assertIn("adr.index", rules)
        self.assertIn("template.issue", rules)

    def test_action_policy_handles_quotes_blocks_and_composites(self) -> None:
        self._write(
            ".github/workflows/validate.yml",
            "steps:\n"
            '  - uses: "actions/checkout@v7" # readable major\n'
            "  - run: |\n"
            "      echo 'uses: owner/not-an-action@abcdef'\n",
        )
        self._write(
            ".github/actions/example/action.yml",
            "runs:\n  using: composite\n  steps:\n    - uses: owner/action@abcdef\n",
        )

        action_violations = [
            violation
            for violation in check_repository(self.root)
            if violation.rule == "workflow.action-version"
        ]

        self.assertEqual(1, len(action_violations))
        self.assertEqual(".github/actions/example/action.yml", action_violations[0].path)


if __name__ == "__main__":
    unittest.main()
