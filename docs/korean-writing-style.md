<!-- doc-id: korean-writing-style -->
<!-- lang: en -->

[한국어](korean-writing-style.ko.md) | [English](korean-writing-style.md)

# Korean technical writing standard

<!-- toc:start -->
## Contents

- [Principles](#principles)
- [Terminology](#terminology)
- [Support status language](#support-status-language)
- [Sentences and sections](#sentences-and-sections)
- [Review and automated validation](#review-and-automated-validation)
<!-- toc:end -->

This document defines how Mystack's Korean documentation is written and
reviewed. Korean pages are not sentence-by-sentence translations. They preserve
technical meaning and sources while organizing the content for Korean readers.

<!-- section: principles -->
## Principles

- Use polite explanatory Korean endings consistently.
- Put one main claim or action in each sentence and one topic in each paragraph.
- Lead with the conclusion and the reader's next action. Put background afterward.
- Preserve technical meaning and sources without copying English word order.
- Keep tables short. Explain long constraints and exceptions below the table.

The standard draws on the National Institute of Korean Language's [plain public
language guide](https://www.korean.go.kr/common/download.do?c_file_name=d1ce1113-cc07-4f4c-9ea2-dd920eecba7b.pdf&file_path=etcData)
and the [Microsoft Learn technical content style
guide](https://learn.microsoft.com/ko-kr/contribute/content/style-quick-start).

<!-- section: terminology -->
## Terminology

Keep code identifiers, API names, configuration keys, error codes, and proper
technical names in their original form and format them as inline code. Use
natural Korean for ordinary explanatory nouns. The Korean counterpart contains
the normative replacement table.

Literal field names and stable identifiers remain unchanged. Add a Korean
explanation when they first appear.

<!-- section: status -->
## Support status language

Korean prose uses these four states:

- **검증 완료** (verified): the public API was tested with the named client and version;
- **일부 지원** (partial): the main path works with documented limitations;
- **미지원** (unsupported): the request is rejected with an explicit error;
- **범위 제외** (out of scope): the project intentionally does not implement it.

Machine-readable status values remain in English and are formatted as code with
an adjacent Korean explanation.

<!-- section: structure -->
## Sentences and sections

Split ordered actions into a numbered list instead of one long sentence. State a
limitation first, then add its reason and workaround only when useful.

Documentation distinguishes the **AWS contract** from the **current
implementation**. The former comes from official AWS documentation or a pinned
SDK model. The latter is behavior tested in this repository. Recognizing a
request or successfully running Spark SQL is not enough to claim AWS semantics.

<!-- section: validation -->
## Review and automated validation

Review Korean pages for polite endings, focused sentences, natural terminology,
inline-code formatting, and discoverable unsupported/error behavior. English
and Korean counterparts retain identical `doc-id`, ordered `section` markers,
and primary-source URLs.

Run `make docs` before review. It validates pairs, section order, links, sources,
and Korean style. This follows the automated quality guidance in the AWS
[hexagonal architecture best
practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/best-practices.html).
