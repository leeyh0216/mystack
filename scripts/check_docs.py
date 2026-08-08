"""Validate Mystack's bilingual documentation and Korean writing contract.

The contract follows the principle of automating documentation checks in CI:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
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
)
DOC_ID_PATTERN = re.compile(r"<!--\s*doc-id:\s*([a-z0-9./_-]+)\s*-->")
SECTION_PATTERN = re.compile(r"<!--\s*section:\s*([a-z0-9_-]+)\s*-->")
URL_PATTERN = re.compile(r"https://[^)\s>]+")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+)\)")
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")
LINK_DESTINATION_PATTERN = re.compile(r"\]\([^)]+\)")
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->")
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
    return "ko" if path.name.endswith(".ko.md") else "en"


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
    documents = maintained_documents()
    violations: list[str] = []
    for document in documents:
        text = document.read_text(encoding="utf-8")
        validate_document(document, text, violations)
        validate_pair(document, text, violations)
    if violations:
        raise SystemExit("Documentation contract violations:\n" + "\n".join(violations))
    print(f"documentation.contract.clean documents={len(documents)}")


if __name__ == "__main__":
    main()
