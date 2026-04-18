from __future__ import annotations

from agent_gatsby.normalize import normalize_source_text


def test_normalize_source_text_strips_gutenberg_boilerplate_and_preserves_structure() -> None:
    raw_text = (
        "\ufeffThe Project Gutenberg eBook of The Great Gatsby\r\n"
        "\r\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK THE GREAT GATSBY ***\r\n"
        "\r\n"
        "The Great Gatsby\r\n"
        "\r\n"
        "Table of Contents\r\n"
        "\r\n"
        "I\r\n"
        "II\r\n"
        "\r\n"
        "I\r\n"
        "\r\n"
        "In my younger and more vulnerable years\r\n"
        "my father gave me some advice.\r\n"
        "\r\n"
        "Gatsby reached toward the green light.\r\n"
        "\r\n"
        "II\r\n"
        "\r\n"
        "The valley of ashes stretched out\r\n"
        "under a gray sky.\r\n"
        "\r\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK THE GREAT GATSBY ***\r\n"
    )

    normalized = normalize_source_text(raw_text)

    assert normalized.startswith("Chapter I")
    assert "Table of Contents" not in normalized
    assert "my father gave me some advice." in normalized
    assert "In my younger and more vulnerable years\nmy father" not in normalized
    assert "\r" not in normalized
    assert "\n\n\n" not in normalized
    assert "Chapter II" in normalized

