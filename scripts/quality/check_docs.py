"""Validate Mystack's bilingual documentation and Korean writing contract.

The contract follows the principle of automating documentation checks in CI:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
OFFICIAL_SOURCES = (
    "https://docs.aws.amazon.com",
    "https://docs.github.com",
    "https://github.com/boto/botocore",
    "https://docs.docker.com",
    "https://docs.python.org",
    "https://docs.astral.sh",
    "https://direnv.net",
    "https://www.korean.go.kr",
    "https://learn.microsoft.com",
    "https://spark.apache.org",
    "https://trino.io",
    "https://github.com/apache/spark",
    "https://github.com/trinodb/trino",
)
DOC_ID_PATTERN = re.compile(r"<!--\s*doc-id:\s*([a-z0-9./_-]+)\s*-->")
SECTION_PATTERN = re.compile(r"<!--\s*section:\s*([a-z0-9_-]+)\s*-->")
URL_PATTERN = re.compile(r"https://[^)\s>]+")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+)\)")
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")
LINK_DESTINATION_PATTERN = re.compile(r"\]\([^)]+\)")
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->")
TOC_START = "<!-- toc:start -->"
TOC_END = "<!-- toc:end -->"
TOC_BLOCK_PATTERN = re.compile(rf"{re.escape(TOC_START)}.*?{re.escape(TOC_END)}\n*", re.DOTALL)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
MARKDOWN_LINK_LABEL_PATTERN = re.compile(r"\[([^]]+)\]\([^)]+\)")
PLAIN_NARRATIVE_ENDING = re.compile(
    r"(한다|된다|있다|없다|이다|아니다|둔다|남는다|따른다|"
    r"보존한다|거부한다|사용한다|관리한다|적용한다|구성한다|"
    r"소유한다|유지한다|확인한다|실행한다|허용한다|지원한다|"
    r"기록한다|반환한다|전환한다|정의한다|제공한다|필요하다|"
    r"가능하다|중요하다|유효하다)\.(?:\s|$)"
)
TRANSLATIONESE_TERMS = (
    (re.compile(r"(?i)(^|[^a-z])gate([^a-z]|$)"), "확인 절차, 판정 기준, 변경 조건 또는 잠금"),
    (re.compile(r"(?i)(^|[^a-z])gap([^a-z]|$)"), "미지원 항목 또는 남은 차이"),
    (re.compile(r"(?i)(^|[^a-z])shape([^a-z]|$)"), "요청 구조, 응답 구조 또는 데이터 구조"),
    (re.compile(r"(?i)(^|[^a-z])bounded([^a-z]|$)"), "상한이 있는 또는 최대 크기가 정해진"),
    (re.compile(r"(?i)(^|[^a-z])(freeze|slice|runbook|fixture)([^a-z]|$)"), "문맥에 맞는 한국어"),
    (re.compile(r"(?i)public[ -]edge|fail[ -]closed"), "공개 API 경계 또는 안전하게 거부"),
)


def counterpart(path: Path) -> Path:
    if path.name.endswith(".ko.md"):
        return path.with_name(path.name.removesuffix(".ko.md") + ".md")
    return path.with_name(path.stem + ".ko.md")


def document_language(path: Path) -> str:
    return "ko" if path.name.endswith((".ko.md", ".ko.generated.md")) else "en"


def first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1) if match else ""


def all_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    return [match.group(1) for match in pattern.finditer(text)]


def source_urls(text: str) -> list[str]:
    return sorted({match.group(0).rstrip(".,;") for match in URL_PATTERN.finditer(text)})


def maintained_documents() -> list[Path]:
    documents = [
        ROOT / "README.md",
        ROOT / "README.ko.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "CONTRIBUTING.ko.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]
    return [path for path in documents if not path.name.endswith(".generated.md")]


def all_documentation_documents() -> list[Path]:
    """Return every repository-owned Markdown document, including generated references."""

    return [
        ROOT / "README.md",
        ROOT / "README.ko.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "CONTRIBUTING.ko.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]


def _without_toc(text: str) -> str:
    return TOC_BLOCK_PATTERN.sub("", text)


def _headings(text: str) -> list[tuple[int, str]]:
    """Read Markdown headings while ignoring fenced code blocks and a previous contents block."""

    headings: list[tuple[int, str]] = []
    in_code_fence = False
    for line in _without_toc(text).splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        match = HEADING_PATTERN.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def _display_heading(value: str) -> str:
    return MARKDOWN_LINK_LABEL_PATTERN.sub(r"\1", value).replace("`", "")


def _github_anchor(value: str, seen: dict[str, int]) -> str:
    """Render the GitHub-compatible anchor used by the intentionally simple H2 index."""

    normalized = _display_heading(value).casefold().strip()
    characters = [
        character if character.isalnum() or character in {"-", "_", " "} else ""
        for character in normalized
    ]
    anchor = "".join(characters).replace(" ", "-")
    anchor = re.sub(r"-+", "-", anchor).strip("-")
    occurrence = seen.get(anchor, 0)
    seen[anchor] = occurrence + 1
    return anchor if occurrence == 0 else f"{anchor}-{occurrence}"


def rendered_toc(path: Path, text: str) -> str:
    """Return the compact H2-only top-of-document index for one Markdown document."""

    headings = _headings(text)
    if not headings or headings[0][0] != 1:
        raise ValueError(f"document has no H1 heading: {path.relative_to(ROOT)}")
    seen: dict[str, int] = {}
    entries = [
        (_display_heading(heading), _github_anchor(heading, seen))
        for level, heading in headings
        if level == 2
    ]
    if not entries:
        raise ValueError(
            f"document has no H2 headings for its contents index: {path.relative_to(ROOT)}"
        )
    title = "목차" if document_language(path) == "ko" else "Contents"
    lines = [TOC_START, f"## {title}", ""]
    lines.extend(f"- [{display}](#{anchor})" for display, anchor in entries)
    lines.extend([TOC_END])
    return "\n".join(lines)


def with_rendered_toc(path: Path, text: str) -> str:
    """Insert or replace the single contents block directly after the document H1."""

    without_toc = _without_toc(text).rstrip() + "\n"
    lines = without_toc.splitlines()
    in_code_fence = False
    h1_index: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_code_fence = not in_code_fence
            continue
        match = HEADING_PATTERN.match(line)
        if not in_code_fence and match and len(match.group(1)) == 1:
            h1_index = index
            break
    if h1_index is None:
        raise ValueError(f"document has no H1 heading: {path.relative_to(ROOT)}")
    suffix = lines[h1_index + 1 :]
    while suffix and not suffix[0].strip():
        suffix.pop(0)
    rendered = rendered_toc(path, without_toc)
    return "\n".join([*lines[: h1_index + 1], "", rendered, "", *suffix]).rstrip() + "\n"


def write_tocs(documents: list[Path]) -> int:
    updated = 0
    for document in documents:
        original = document.read_text(encoding="utf-8")
        rendered = with_rendered_toc(document, original)
        if original != rendered:
            document.write_text(rendered, encoding="utf-8")
            updated += 1
    return updated


def validate_toc(path: Path, text: str, violations: list[str]) -> None:
    try:
        expected = with_rendered_toc(path, text)
    except ValueError as error:
        violations.append(str(error))
        return
    if text != expected:
        violations.append(
            f"missing or stale top-of-document contents index: {path.relative_to(ROOT)}; "
            "run uv run python scripts/quality/check_docs.py --write-toc"
        )


def validate_document(path: Path, text: str, violations: list[str]) -> None:
    relative = path.relative_to(ROOT)
    language = document_language(path)
    paired = counterpart(path)
    if not paired.exists():
        violations.append(f"missing language pair: {relative} -> {paired.name}")
        return
    if not first_match(DOC_ID_PATTERN, text):
        violations.append(f"missing doc-id marker: {relative}")
    if f"<!-- lang: {language} -->" not in text:
        violations.append(f"missing language marker: {relative} expected={language}")
    if not all_matches(SECTION_PATTERN, text):
        violations.append(f"missing section markers: {relative}")
    if paired.name not in text:
        violations.append(f"missing language backlink: {relative}")
    if not any(source in text for source in OFFICIAL_SOURCES):
        violations.append(f"missing direct official source: {relative}")
    validate_relative_links(path, text, violations)
    if language == "ko":
        validate_korean_style(path, text, violations)


def validate_pair(path: Path, text: str, violations: list[str]) -> None:
    if document_language(path) != "en":
        return
    paired = counterpart(path)
    if not paired.exists():
        return
    paired_text = paired.read_text(encoding="utf-8")
    pair_name = f"{path.relative_to(ROOT)} <-> {paired.relative_to(ROOT)}"
    if first_match(DOC_ID_PATTERN, text) != first_match(DOC_ID_PATTERN, paired_text):
        violations.append(f"doc-id mismatch: {pair_name}")
    if all_matches(SECTION_PATTERN, text) != all_matches(SECTION_PATTERN, paired_text):
        violations.append(f"section order mismatch: {pair_name}")
    if source_urls(text) != source_urls(paired_text):
        violations.append(f"source URL mismatch: {pair_name}")


def validate_relative_links(path: Path, text: str, violations: list[str]) -> None:
    for match in MARKDOWN_LINK_PATTERN.finditer(text):
        target = match.group(1).split("#", maxsplit=1)[0]
        if not target or target.startswith(("https://", "http://", "mailto:")):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            violations.append(f"unresolved relative link: {path.relative_to(ROOT)} -> {target}")


def validate_korean_style(path: Path, text: str, violations: list[str]) -> None:
    in_code_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        trimmed = line.strip()
        if trimmed.startswith(("```", "~~~")):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        prose = INLINE_CODE_PATTERN.sub("", line)
        prose = LINK_DESTINATION_PATTERN.sub("]", prose)
        prose = HTML_COMMENT_PATTERN.sub("", prose)
        if PLAIN_NARRATIVE_ENDING.search(prose):
            violations.append(
                f"plain Korean narrative ending: {path.relative_to(ROOT)}:{line_number}"
            )
        if path.name == "korean-writing-style.ko.md":
            continue
        for pattern, hint in TRANSLATIONESE_TERMS:
            if pattern.search(prose):
                violations.append(
                    f"translationese: {path.relative_to(ROOT)}:{line_number} prefer={hint}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-toc",
        action="store_true",
        help="Render the compact top-of-document contents index into every Markdown document",
    )
    args = parser.parse_args()
    all_documents = all_documentation_documents()
    if args.write_toc:
        updated = write_tocs(all_documents)
        print(f"documentation.toc.updated documents={updated} total={len(all_documents)}")
        return
    documents = maintained_documents()
    violations: list[str] = []
    for document in all_documents:
        validate_toc(document, document.read_text(encoding="utf-8"), violations)
    for document in documents:
        text = document.read_text(encoding="utf-8")
        validate_document(document, text, violations)
        validate_pair(document, text, violations)
    if violations:
        raise SystemExit("Documentation contract violations:\n" + "\n".join(violations))
    print(f"documentation.contract.clean documents={len(documents)}")


if __name__ == "__main__":
    main()
