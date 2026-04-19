from __future__ import annotations

from agent_gatsby.bilingual_qa import build_translation_qa_report


def test_build_translation_qa_report_passes_for_structurally_matching_translation() -> None:
    english = '# Title\n\n### Intro\n\nHe says "hello" [1].\n'
    translated = '# Titulo\n\n### Introduccion\n\nEl dice "hola" [1].\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["heading_count_match"] is True
    assert report["section_order_match"] is True
    assert report["citation_count_match"] is True
    assert report["quote_marker_count_match"] is True
    assert report["major_issues"] == []


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
    translated = '# Titulo\n\n> *“hola”* [1]\n\nEl ensayo llama esto “importante” en el cuerpo.\n\n## Citas\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, cap. 1, párr. 1, pasaje citado que comienza con "hello".\n'

    report = build_translation_qa_report(
        language="spanish",
        english_master=english,
        translated_text=translated,
    )

    assert report["quote_marker_count_match"] is True
    assert report["major_issues"] == []
