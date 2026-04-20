from __future__ import annotations

from agent_gatsby.bilingual_qa import build_translation_qa_report, translation_report_is_renderable


def test_build_translation_qa_report_passes_for_structurally_matching_translation() -> None:
    english = '# Title\n\n### Intro\n\n> *"hello"* [1]\n\nBody text.\n\n## Citations\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello".\n'
    translated = '# Titulo\n\n### Introduccion\n\n> *“hola”* [1]\n\nTexto del cuerpo.\n\n## Citas\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, cap. 1, párr. 1, pasaje citado que comienza "hello".\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["heading_count_match"] is True
    assert report["section_order_match"] is True
    assert report["citation_count_match"] is True
    assert report["quote_marker_count_match"] is True
    assert report["citations_section_present"] is True
    assert report["citation_entry_count_match"] is True
    assert report["english_citation_entry_count"] == 1
    assert report["translated_citation_entry_count"] == 1
    assert report["major_issues"] == []
    assert translation_report_is_renderable(report) is True


def test_build_translation_qa_report_flags_changed_citations() -> None:
    english = '# Title\n\n### Intro\n\nHe says "hello" [1].\n'
    translated = '# Titulo\n\n### Introduccion\n\nEl dice "hola" [2].\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["citation_count_match"] is False
    assert report["major_issues"]


def test_build_translation_qa_report_ignores_extra_body_quotes_when_protected_quotes_match() -> None:
    english = '# Title\n\n> *"hello"* [1]\n\nBody text.\n\n## Citations\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello".\n'
    translated = '# Titulo\n\n> *“hola”* [1]\n\nEl ensayo llama esto “importante” en el cuerpo.\n\n## Citas\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, cap. 1, párr. 1, pasaje citado que comienza "hello".\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["quote_marker_count_match"] is True
    assert report["major_issues"] == []


def test_build_translation_qa_report_flags_untranslated_english_quotes_in_body() -> None:
    english = '# Title\n\n> *"hello world there"* [1]\n\n## Citations\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello world there".\n'
    translated = '# Titulo\n\n> *"hello world there"* [1]\n\n## Citas\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, cap. 1, párr. 1, pasaje citado que comienza "hello world there".\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["untranslated_body_quote_count"] == 1
    assert report["major_issues"]


def test_build_translation_qa_report_does_not_flag_translated_spanish_multiword_quotes() -> None:
    english = '# Title\n\n> *"hello world there"* [1]\n\n## Citations\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello world there".\n'
    translated = '# Titulo\n\n> *"la conducta puede fundamentarse en la roca firme"* [1]\n\n## Citas\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, cap. 1, párr. 1, pasaje citado que comienza "hello world there".\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["untranslated_body_quote_count"] == 0
    assert report["major_issues"] == []


def test_build_translation_qa_report_flags_heading_without_citation_entries() -> None:
    english = '# Title\n\nBody text [1].\n\n## Citations\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello".\n'
    translated = '# Titulo\n\nTexto del cuerpo [1].\n\n## Citas\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["citations_section_present"] is True
    assert report["translated_citation_entry_count"] == 0
    assert report["citations_heading_without_entries"] is True
    assert translation_report_is_renderable(report) is False


def test_build_translation_qa_report_flags_mandarin_mixed_script_and_forbidden_names() -> None:
    english = '# Title\n\n### Intro\n\nBody text [1].\n\n## Citations\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello".\n'
    translated = '# 标题\n\n### 引言\n\n菲茨平写道，中西Middle向西现在似乎像是宇宙的边缘[1]然而事情继续发展。\n\n## 引文\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, 第1章，第1段，引文开头："hello".\n'

    report = build_translation_qa_report(
        language="mandarin",
        english_master=english,
        translated_text=translated,
    )

    assert report["mixed_script_issue_count"] >= 1
    assert report["forbidden_mandarin_variant_count"] >= 1
    assert report["major_issues"]


def test_build_translation_qa_report_flags_spanish_internal_tokens_scripts_and_escape_artifacts() -> None:
    english = '# Title\n\nBody text [10].\n\n## Citations\n\n1. Ref.\n'
    translated = '# Titulo\n\nla luna prematura AGCIT себя [10] y como si la casa hubiera guiñado un$\\\\un ojo [12].\n\n## Citas\n\n1. Ref.\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["internal_token_issue_count"] >= 1
    assert report["foreign_script_issue_count"] >= 1
    assert report["escape_sequence_issue_count"] >= 1
    assert report["citation_neighborhood_issue_count"] >= 1
    assert translation_report_is_renderable(report) is False


def test_build_translation_qa_report_flags_known_bad_spanish_token() -> None:
    english = '# Title\n\nBody text [15].\n\n## Citations\n\n1. Ref.\n'
    translated = '# Titulo\n\njuegos nerviosos y esporádíamos [15].\n\n## Citas\n\n1. Ref.\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["known_bad_token_count"] >= 1
    assert translation_report_is_renderable(report) is False


def test_build_translation_qa_report_flags_repeated_mandarin_ellipsis_before_citation() -> None:
    english = '# Title\n\nBody text [30].\n\n## Citations\n\n1. Ref.\n'
    translated = '# 标题\n\n这构成了听觉意象……………… [30]\n\n## 引文\n\n1. Ref.\n'

    report = build_translation_qa_report(
        language="mandarin",
        english_master=english,
        translated_text=translated,
    )

    assert report["repeated_ellipsis_issue_count"] >= 1
    assert report["citation_neighborhood_issue_count"] >= 1
    assert translation_report_is_renderable(report) is False


def test_build_translation_qa_report_flags_unlocalized_bibliography_metadata_and_markdown_leak() -> None:
    english = '# Title\n\nBody text [1].\n\n## Citations\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello".\n'
    translated = '# 标题\n\n### # 梦想的瓦解\n\n正文 [1]。\n\n## 引文\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello".\n'

    report = build_translation_qa_report(
        language="mandarin",
        english_master=english,
        translated_text=translated,
    )

    assert report["markdown_heading_leak_count"] >= 1
    assert report["bibliography_localization_issue_count"] >= 1
    assert translation_report_is_renderable(report) is False
