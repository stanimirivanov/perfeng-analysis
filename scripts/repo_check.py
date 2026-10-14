"""Validate mechanical repository documentation and workflow policy.

The checker deliberately uses only the Python standard library so it remains
available from the locked development environment without adding a product
dependency. Semantic correctness still belongs to review and behavioral tests.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

SKIPPED_DIRECTORIES = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "vendor",
}
ADR_FILE = re.compile(r"^(\d{4})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
ADR_HEADING = re.compile(r"^# ADR-(\d{4}): (\S.*)$")
ADR_METADATA = re.compile(r"^- ([A-Za-z][A-Za-z ]+):\s*(.*?)\s*$")
ADR_INDEX_ROW = re.compile(
    r"^\|\s*\[(?:ADR-)?(\d{4})\]\(([^)]+)\)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
)
MILESTONE = re.compile(r"^M\d{2} — \S.*$")
ACTION_USE = re.compile(r"^\s*(?:-\s*)?uses:\s*(.*?)\s*$")
YAML_BLOCK_SCALAR = re.compile(r"^\s*(?:-\s*)?[^:#]+:\s*[|>][+-]?\d*\s*(?:#.*)?$")
INLINE_LINK = re.compile(r"!?\[[^]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))")
REFERENCE_LINK = re.compile(
    r"^[ ]{0,3}\[[^]]+\]:\s*(?:<([^>]+)>|([^\s]+))(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*$"
)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
WORD = re.compile(r"[\w]+(?:['_-][\w]+)*", re.UNICODE)

ALLOWED_ADR_STATUSES = {"Proposed", "Accepted", "Rejected", "Deprecated", "Superseded"}
REQUIRED_ADR_METADATA = (
    "Status",
    "Date",
    "Milestone",
    "Deciders",
    "Supersedes",
    "Superseded by",
)
PR_POLICY: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "perfeng-analysis": (
        (
            "Linked work",
            "Outcome and scope",
            "Design, compatibility and operations",
            "Verification",
            "Limitations and review",
        ),
        (
            "Issue:",
            "Milestone:",
            "Problem and resulting behavior:",
            "Boundaries and deliberate exclusions:",
            "Assumptions and unresolved questions:",
            "ADRs:",
            "Statistical or measurement-semantic effects:",
            "Contract, CLI and package compatibility effects:",
            "Security effects:",
            "Rollout, recovery and rollback:",
            "Commands and non-secret evidence:",
            "Checks not run, blocking reason and residual risk:",
            "Known limitations and follow-up:",
        ),
    ),
    "perfeng-contracts": (
        (
            "Linked work",
            "Outcome and scope",
            "Design, compatibility and release",
            "Verification",
            "Limitations and review",
        ),
        (
            "Issue:",
            "Milestone:",
            "Problem and resulting contract behavior:",
            "Affected producers and consumers:",
            "Boundaries and deliberate exclusions:",
            "Assumptions and unresolved questions:",
            "ADRs:",
            "Compatibility and migration:",
            "Security effects:",
            "Bundle/release effects:",
            "Commands and non-secret evidence:",
            "Checks not run, blocking reason and residual risk:",
            "Known limitations and follow-up:",
        ),
    ),
}


@dataclass(frozen=True, order=True)
class Violation:
    """One actionable policy failure."""

    path: str
    line: int
    rule: str
    message: str
    fix: str
    policy: str

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.line}: [{self.rule}] {self.message}; "
            f"fix: {self.fix}; policy: {self.policy}"
        )


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    line: int


@dataclass
class Document:
    path: str
    lines: list[str]
    headings: list[Heading]
    anchors: set[str]
    links: list[tuple[str, int]]
    word_count: int

    @property
    def second_levels(self) -> list[Heading]:
        return [heading for heading in self.headings if heading.level == 2]


@dataclass(frozen=True)
class ADRRecord:
    number: str
    path: str
    title: str
    metadata: dict[str, tuple[str, int]]


def github_anchor(value: str) -> str:
    """Return the GitHub-style anchor used by repository documentation."""

    value = re.sub(r"!?\[([^]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value).lower()
    result: list[str] = []
    pending_dash = False
    for character in value:
        if character.isalnum() or character in "_-":
            if pending_dash and result:
                result.append("-")
            result.append(character)
            pending_dash = False
        elif character.isspace():
            pending_dash = True
    return "".join(result)


def parse_markdown(path: str, content: str) -> Document:
    """Parse the Markdown subset needed by repository policy."""

    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    headings: list[Heading] = []
    anchors: set[str] = set()
    anchor_counts: dict[str, int] = {}
    links: list[tuple[str, int]] = []
    words = 0
    fence_character = ""
    fence_width = 0

    for line_number, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        fence = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence:
            marker = fence.group(1)
            if not fence_character:
                fence_character = marker[0]
                fence_width = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_width:
                fence_character = ""
                fence_width = 0
            continue
        if fence_character:
            continue

        reference = REFERENCE_LINK.match(line)
        if reference:
            links.append((reference.group(1) or reference.group(2), line_number))

        prose = re.sub(r"`[^`]*`", " ", line)
        words += len(WORD.findall(prose))
        for match in INLINE_LINK.finditer(prose):
            links.append((match.group(1) or match.group(2), line_number))

        heading_match = HEADING.match(stripped)
        if not heading_match:
            continue
        heading = Heading(len(heading_match.group(1)), heading_match.group(2).strip(), line_number)
        headings.append(heading)
        base = github_anchor(heading.text)
        count = anchor_counts.get(base, 0)
        anchors.add(base if count == 0 else f"{base}-{count}")
        anchor_counts[base] = count + 1

    return Document(path, lines, headings, anchors, links, words)


def load_documents(root: Path) -> dict[str, Document]:
    documents: dict[str, Document] = {}
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if any(part in SKIPPED_DIRECTORIES for part in relative.parts):
            continue
        key = relative.as_posix()
        documents[key] = parse_markdown(key, path.read_text(encoding="utf-8"))
    return documents


def exact_path_exists(root: Path, relative: Path) -> bool:
    current = root
    if relative == Path("."):
        return True
    for part in relative.parts:
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current /= part
    return True


def check_links(root: Path, documents: dict[str, Document]) -> list[Violation]:
    violations: list[Violation] = []
    root = root.resolve()
    for document in documents.values():
        source_directory = Path(document.path).parent
        for destination, line in document.links:
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or destination.startswith("//"):
                continue
            path_text = unquote(parsed.path)
            relative = (
                Path(path_text.lstrip("/\\"))
                if path_text.startswith(("/", "\\"))
                else source_directory / path_text
            )
            if not path_text:
                relative = Path(document.path)
            target = (root / relative).resolve()
            try:
                normalized = target.relative_to(root)
            except ValueError:
                violations.append(
                    Violation(
                        document.path,
                        line,
                        "docs.internal-link",
                        f'link "{destination}" escapes the repository root',
                        "link to a checked-in repository path",
                        "CONTRIBUTING.md#documentation",
                    )
                )
                continue
            if not exact_path_exists(root, normalized):
                violations.append(
                    Violation(
                        document.path,
                        line,
                        "docs.internal-link",
                        f'link "{destination}" does not resolve with matching letter case',
                        "correct the relative path or capitalization",
                        "CONTRIBUTING.md#documentation",
                    )
                )
                continue
            if parsed.fragment:
                target_document = documents.get(normalized.as_posix())
                anchor = unquote(parsed.fragment)
                if target_document is not None and anchor not in target_document.anchors:
                    violations.append(
                        Violation(
                            document.path,
                            line,
                            "docs.internal-link",
                            f'link "{destination}" references a missing heading anchor',
                            "use the target heading's generated anchor",
                            "CONTRIBUTING.md#documentation",
                        )
                    )
    return violations


def requires_tldr(document: Document) -> bool:
    if document.path.startswith(".github/"):
        return False
    lowered = document.path.lower()
    selective = (
        lowered.startswith("docs/architecture/")
        or lowered == "security.md"
        or any(
            term in lowered
            for term in (
                "compatibility",
                "migration",
                "workflow",
                "operations",
                "runbook",
                "end-to-end",
            )
        )
    )
    return document.word_count >= 800 or len(document.second_levels) > 5 or selective


def check_tldr(documents: dict[str, Document]) -> list[Violation]:
    violations: list[Violation] = []
    for document in documents.values():
        if not requires_tldr(document):
            continue
        if document.second_levels and document.second_levels[0].text == "TL;DR":
            continue
        line = document.second_levels[0].line if document.second_levels else 1
        violations.append(
            Violation(
                document.path,
                line,
                "docs.tldr",
                "long or selectively consulted documentation does not start with `## TL;DR`",
                "add TL;DR as the first second-level section after title and metadata",
                "CONTRIBUTING.md#documentation",
            )
        )
    return violations


def read_adrs(documents: dict[str, Document]) -> tuple[dict[str, ADRRecord], list[Violation]]:
    records: dict[str, ADRRecord] = {}
    violations: list[Violation] = []
    for path, document in documents.items():
        if not path.startswith("docs/decisions/") or path == "docs/decisions/README.md":
            continue
        filename = Path(path).name
        filename_match = ADR_FILE.fullmatch(filename)
        if not filename_match:
            violations.append(
                Violation(
                    path,
                    1,
                    "adr.filename",
                    "ADR filename is not four-digit lowercase kebab-case",
                    "rename it to `NNNN-short-decision.md` and update links",
                    "docs/decisions/README.md#naming-and-lifecycle",
                )
            )
            continue
        number = filename_match.group(1)
        heading_match = ADR_HEADING.fullmatch(document.lines[0] if document.lines else "")
        title = ""
        if not heading_match:
            violations.append(
                Violation(
                    path,
                    1,
                    "adr.heading",
                    "ADR heading does not match `# ADR-NNNN: Decision title`",
                    "use the filename number in the canonical heading",
                    "docs/decisions/README.md#naming-and-lifecycle",
                )
            )
        else:
            title = heading_match.group(2)
            if heading_match.group(1) != number:
                violations.append(
                    Violation(
                        path,
                        1,
                        "adr.number",
                        "ADR heading number does not match its filename",
                        "renumber the heading or unpublished file consistently",
                        "docs/decisions/README.md#naming-and-lifecycle",
                    )
                )
        metadata: dict[str, tuple[str, int]] = {}
        first_section = min(
            (heading.line for heading in document.second_levels), default=len(document.lines) + 1
        )
        for index, line in enumerate(document.lines[1 : first_section - 1], start=2):
            match = ADR_METADATA.fullmatch(line.strip())
            if match:
                if match.group(1) in metadata:
                    violations.append(
                        Violation(
                            path,
                            index,
                            "adr.metadata",
                            f'duplicate metadata field "{match.group(1)}"',
                            "keep exactly one value before the first section",
                            "docs/decisions/README.md#template",
                        )
                    )
                metadata[match.group(1)] = (match.group(2), index)
        for field in REQUIRED_ADR_METADATA:
            if field not in metadata:
                violations.append(
                    Violation(
                        path,
                        1,
                        "adr.metadata",
                        f'missing required metadata field "{field}"',
                        f"add `- {field}: ...` before the first section",
                        "docs/decisions/README.md#template",
                    )
                )
        status = metadata.get("Status", ("", 1))
        if status[0] and status[0] not in ALLOWED_ADR_STATUSES:
            violations.append(
                Violation(
                    path,
                    status[1],
                    "adr.status",
                    f'unsupported ADR status "{status[0]}"',
                    "use a documented lifecycle status",
                    "docs/decisions/README.md#naming-and-lifecycle",
                )
            )
        recorded_date = metadata.get("Date", ("", 1))
        if recorded_date[0]:
            try:
                date.fromisoformat(recorded_date[0])
            except ValueError:
                violations.append(
                    Violation(
                        path,
                        recorded_date[1],
                        "adr.date",
                        f'invalid ISO date "{recorded_date[0]}"',
                        "use YYYY-MM-DD",
                        "docs/decisions/README.md#template",
                    )
                )
        milestone = metadata.get("Milestone", ("", 1))
        if milestone[0] and not MILESTONE.fullmatch(milestone[0]):
            violations.append(
                Violation(
                    path,
                    milestone[1],
                    "adr.milestone",
                    f'invalid milestone "{milestone[0]}"',
                    "use the exact `MNN — Outcome` title",
                    "CONTRIBUTING.md#milestones-and-required-issue",
                )
            )
        if number in records:
            violations.append(
                Violation(
                    path,
                    1,
                    "adr.number",
                    f"ADR-{number} duplicates {records[number].path}",
                    "refresh repository state and renumber the later unpublished ADR",
                    "docs/decisions/README.md#naming-and-lifecycle",
                )
            )
        else:
            records[number] = ADRRecord(number, path, title, metadata)
    return records, violations


def check_adrs(documents: dict[str, Document]) -> list[Violation]:
    records, violations = read_adrs(documents)
    numbers = sorted(int(number) for number in records)
    if numbers != list(range(1, len(numbers) + 1)):
        path = records[f"{numbers[0]:04d}"].path if numbers else "docs/decisions/README.md"
        violations.append(
            Violation(
                path,
                1,
                "adr.sequence",
                "ADR numbers are not a contiguous sequence starting at 0001",
                "restore history or renumber unpublished ADRs from fresh state",
                "docs/decisions/README.md#naming-and-lifecycle",
            )
        )

    index = documents.get("docs/decisions/README.md")
    entries: dict[str, tuple[str, str, int]] = {}
    if index is None:
        return violations + [
            Violation(
                "docs/decisions/README.md",
                1,
                "adr.index",
                "ADR index is missing",
                "restore the decision index",
                "CONTRIBUTING.md#policy-language-and-sources-of-truth",
            )
        ]
    for line_number, line in enumerate(index.lines, start=1):
        match = ADR_INDEX_ROW.match(line.strip())
        if match:
            if match.group(1) in entries:
                violations.append(
                    Violation(
                        index.path,
                        line_number,
                        "adr.index",
                        f"ADR-{match.group(1)} has duplicate index rows",
                        "keep one row for each decision number",
                        "docs/decisions/README.md#index",
                    )
                )
            entries[match.group(1)] = (match.group(2).strip(), match.group(3).strip(), line_number)
    for number, record in records.items():
        entry = entries.get(number)
        if entry is None:
            violations.append(
                Violation(
                    record.path,
                    1,
                    "adr.index",
                    f"ADR-{number} is not registered in the index",
                    "add an index row linking the decision and status",
                    "docs/decisions/README.md#index",
                )
            )
            continue
        if Path(entry[0]).name != Path(record.path).name:
            violations.append(
                Violation(
                    index.path,
                    entry[2],
                    "adr.index",
                    f"ADR-{number} index link does not match its file",
                    "link the indexed number to the ADR file",
                    "docs/decisions/README.md#index",
                )
            )
        status = record.metadata.get("Status", ("", 1))[0]
        if entry[1] != status:
            violations.append(
                Violation(
                    index.path,
                    entry[2],
                    "adr.index",
                    f"ADR-{number} index status does not match metadata",
                    "copy the ADR lifecycle status into the index",
                    "docs/decisions/README.md#index",
                )
            )
    for number, entry in entries.items():
        if number not in records:
            violations.append(
                Violation(
                    index.path,
                    entry[2],
                    "adr.index",
                    f"index entry ADR-{number} has no decision file",
                    "restore the file or remove an unpublished stale row",
                    "docs/decisions/README.md#index",
                )
            )
    for record in records.values():
        status = record.metadata.get("Status", ("", 1))[0]
        replacement, replacement_line = record.metadata.get("Superseded by", ("", 1))
        references = re.findall(r"ADR-(\d{4})", replacement)
        if status == "Superseded" and not references:
            violations.append(
                Violation(
                    record.path,
                    replacement_line,
                    "adr.supersession",
                    "superseded ADR does not identify its replacement",
                    "link the replacing ADR in `Superseded by`",
                    "docs/decisions/README.md#naming-and-lifecycle",
                )
            )
        for reference in references:
            if reference not in records:
                violations.append(
                    Violation(
                        record.path,
                        replacement_line,
                        "adr.supersession",
                        f"replacement ADR-{reference} does not exist",
                        "link an existing replacement",
                        "docs/decisions/README.md#naming-and-lifecycle",
                    )
                )
    return violations


def fenced_issue_body(document: Document) -> str | None:
    in_markdown = False
    body: list[str] = []
    for line in document.lines:
        stripped = line.strip()
        if not in_markdown and stripped.lower() in {"```markdown", "~~~markdown"}:
            in_markdown = True
            body = []
            continue
        if in_markdown and stripped in {"```", "~~~"}:
            candidate = "\n".join(body)
            if "**Repository:**" in candidate and "**Milestone:**" in candidate:
                return candidate
            in_markdown = False
            continue
        if in_markdown:
            body.append(line)
    return None


def check_templates(documents: dict[str, Document]) -> list[Violation]:
    violations: list[Violation] = []
    policy = documents.get("CONTRIBUTING.md")
    issue = documents.get(".github/ISSUE_TEMPLATE/work-item.md")
    pull_request = documents.get(".github/PULL_REQUEST_TEMPLATE.md")
    if policy is None or issue is None:
        return [
            Violation(
                "CONTRIBUTING.md" if policy is None else ".github/ISSUE_TEMPLATE/work-item.md",
                1,
                "template.issue",
                "canonical policy or issue template is missing",
                "restore both canonical sources",
                "CONTRIBUTING.md#required-issue-structure",
            )
        ]
    canonical_body = fenced_issue_body(policy)
    if canonical_body is None:
        violations.append(
            Violation(
                policy.path,
                1,
                "template.issue",
                "no canonical fenced issue body was found",
                "keep the repository issue structure in a Markdown fence",
                "CONTRIBUTING.md#required-issue-structure",
            )
        )
    else:
        canonical = parse_markdown("canonical-issue.md", canonical_body)
        expected = [heading.text for heading in canonical.second_levels]
        actual = [heading.text for heading in issue.second_levels]
        if expected != actual:
            violations.append(
                Violation(
                    issue.path,
                    issue.second_levels[0].line if issue.second_levels else 1,
                    "template.issue",
                    "issue section names or order differ from canonical policy",
                    "align the template with the fenced issue structure",
                    "CONTRIBUTING.md#required-issue-structure",
                )
            )
        canonical_checks = sum(
            line.strip().startswith(("- [ ] ", "- [x] ", "- [X] ")) for line in canonical.lines
        )
        actual_checks = sum(
            line.strip().startswith(("- [ ] ", "- [x] ", "- [X] ")) for line in issue.lines
        )
        if canonical_checks != actual_checks:
            violations.append(
                Violation(
                    issue.path,
                    1,
                    "template.issue",
                    "issue acceptance checklist has drifted from canonical policy",
                    "align the number of canonical acceptance prompts",
                    "CONTRIBUTING.md#required-issue-structure",
                )
            )

    repository_match = next(
        (
            re.match(r"\*\*Repository:\*\*\s*(\S+)", line.strip())
            for line in issue.lines
            if line.strip().startswith("**Repository:**")
        ),
        None,
    )
    repository = repository_match.group(1) if repository_match else ""
    expected_policy = PR_POLICY.get(repository)
    if pull_request is None:
        violations.append(
            Violation(
                ".github/PULL_REQUEST_TEMPLATE.md",
                1,
                "template.pull-request",
                "pull request template is missing",
                "restore the repository-specific review template",
                "CONTRIBUTING.md#pull-request-description",
            )
        )
    elif expected_policy is None:
        violations.append(
            Violation(
                issue.path,
                1,
                "template.pull-request",
                f'unsupported repository identity "{repository}"',
                "use the canonical repository name",
                "CONTRIBUTING.md#required-issue-structure",
            )
        )
    else:
        headings, markers = expected_policy
        actual_headings = tuple(heading.text for heading in pull_request.second_levels)
        if actual_headings != headings:
            violations.append(
                Violation(
                    pull_request.path,
                    1,
                    "template.pull-request",
                    "pull request section names or order have drifted",
                    "restore the repository-specific review structure",
                    "CONTRIBUTING.md#pull-request-description",
                )
            )
        content = "\n".join(pull_request.lines)
        for marker in markers:
            if marker not in content:
                violations.append(
                    Violation(
                        pull_request.path,
                        1,
                        "template.pull-request",
                        f'missing required prompt "{marker}"',
                        "restore the prompt required by the completion policy",
                        "CONTRIBUTING.md#pull-request-description",
                    )
                )
    return violations


def action_references(text: str) -> list[tuple[str, int]]:
    """Return actual YAML uses values while ignoring block-scalar content."""
    references: list[tuple[str, int]] = []
    block_indent: int | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if block_indent is not None:
            if not stripped or indent > block_indent:
                continue
            block_indent = None
        if YAML_BLOCK_SCALAR.match(line):
            block_indent = indent
            continue
        match = ACTION_USE.match(line)
        if not match:
            continue
        raw = match.group(1).strip()
        if raw.startswith(('"', "'")):
            quote = raw[0]
            closing = raw.find(quote, 1)
            reference = raw[1:closing] if closing >= 0 else raw
        else:
            reference = raw.split("#", 1)[0].strip()
        references.append((reference, line_number))
    return references


def check_workflow_actions(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    workflow_root = root / ".github" / "workflows"
    action_root = root / ".github" / "actions"
    paths: set[Path] = set()
    if workflow_root.exists():
        paths.update((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")))
    if action_root.exists():
        paths.update((*action_root.rglob("action.yml"), *action_root.rglob("action.yaml")))
    for path in sorted(paths):
        for reference, line_number in action_references(path.read_text(encoding="utf-8")):
            if reference.startswith(("./", "docker://")):
                continue
            _, separator, version = reference.rpartition("@")
            if separator and re.fullmatch(r"v\d+", version):
                continue
            violations.append(
                Violation(
                    path.relative_to(root).as_posix(),
                    line_number,
                    "workflow.action-version",
                    f'action reference "{reference}" is not a semantic major tag',
                    "use `owner/action@vN`; immutable hashes remain required for product artifacts, not GitHub Action `uses`",
                    "docs/development/dependency-policy.md#locking-and-updates",
                )
            )
    return violations


def check_repository(root: Path) -> list[Violation]:
    """Return every deterministic repository-policy violation."""

    documents = load_documents(root)
    violations = [
        *check_links(root, documents),
        *check_tldr(documents),
        *check_adrs(documents),
        *check_templates(documents),
        *check_workflow_actions(root),
    ]
    return sorted(violations)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    arguments = parser.parse_args()
    violations = check_repository(arguments.root.resolve())
    for violation in violations:
        print(violation, file=sys.stderr)
    if violations:
        print(f"repo-check: found {len(violations)} policy violation(s)", file=sys.stderr)
        return 1
    print("repo-check: repository policy checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
