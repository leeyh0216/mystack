"""Top-of-document contents generation contracts.

GitHub heading-anchor behavior is documented at:
https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-table-of-contents
"""

from __future__ import annotations

from scripts.quality.check_docs import ROOT, rendered_toc, validate_toc, with_rendered_toc


def test_renders_a_compact_h2_contents_index_with_code_and_link_labels() -> None:
    document = ROOT / "docs" / "example.md"
    text = """# Guide

Introduction.

## First `value`

## [Second guide](other.md)

### Nested detail
"""

    toc = rendered_toc(document, text)

    assert (
        toc
        == """<!-- toc:start -->
## Contents

- [First value](#first-value)
- [Second guide](#second-guide)
<!-- toc:end -->"""
    )


def test_replaces_a_stale_contents_index_and_validates_the_result() -> None:
    document = ROOT / "docs" / "example.ko.md"
    stale = """# 안내

<!-- toc:start -->
## 목차

- [오래된 항목](#오래된-항목)
<!-- toc:end -->

## 시작

## 다음 작업
"""

    rendered = with_rendered_toc(document, stale)
    violations: list[str] = []
    validate_toc(document, rendered, violations)

    assert "- [시작](#시작)" in rendered
    assert "- [다음 작업](#다음-작업)" in rendered
    assert violations == []
