"""Validate bilingual documentation pairs, backlinks, and direct official references.

Documentation quality follows AWS guidance to automate tests in CI:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html
"""

from __future__ import annotations

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
)


def counterpart(path: Path) -> Path:
    if path.name.endswith(".ko.md"):
        return path.with_name(path.name.removesuffix(".ko.md") + ".md")
    return path.with_name(path.stem + ".ko.md")


def main() -> None:
    documents = [ROOT / "README.md", ROOT / "README.ko.md", *sorted((ROOT / "docs").rglob("*.md"))]
    violations: list[str] = []
    for document in documents:
        if document.name.endswith(".generated.md"):
            continue
        paired = counterpart(document)
        if not paired.exists():
            violations.append(
                f"missing language pair: {document.relative_to(ROOT)} -> {paired.name}"
            )
            continue
        text = document.read_text(encoding="utf-8")
        if paired.name not in text:
            violations.append(f"missing language backlink: {document.relative_to(ROOT)}")
        if not any(source in text for source in OFFICIAL_SOURCES):
            violations.append(f"missing direct official source: {document.relative_to(ROOT)}")
    if violations:
        raise SystemExit("Documentation contract violations:\n" + "\n".join(violations))
    print(f"documentation.contract.clean documents={len(documents)}")


if __name__ == "__main__":
    main()
