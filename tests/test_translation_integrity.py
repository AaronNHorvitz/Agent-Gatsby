from __future__ import annotations

import json
from pathlib import Path

from agent_gatsby.config import load_config
from agent_gatsby.llm_client import LLMResponseValidationError
from agent_gatsby.translate_mandarin import translate_mandarin
from agent_gatsby.translate_spanish import translate_spanish
from agent_gatsby.translation_common import (
    dynamic_validation_loop,
    extract_translated_quote_lookup,
    extract_visible_citation_markers,
    freeze_english_master,
    localize_citation_metadata_line,
    normalize_translated_body,
    split_markdown_into_chunks,
)


def write_translation_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "artifacts/drafts").mkdir(parents=True)
    (repo_root / "config/prompts/translator_es.md").write_text("Translate to Spanish.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_es_cleanup.md").write_text("Clean up Spanish.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_zh.md").write_text("Translate to Simplified Chinese.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_zh_cleanup.md").write_text("Clean up Simplified Chinese.\n", encoding="utf-8")
    english_final = """# An Analysis of Metaphors in The Great Gatsby

### Introduction

Metaphor text:
> *"the green light"* [1]

Gatsby reaches for the green light [1].

### Conclusion

Nick returns to the dream and its distance [1].

## Citations

1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "In my younger and more vulnerable years my father gave me some advice...".
"""
    (repo_root / "artifacts/drafts/analysis_english_final.md").write_text(english_final, encoding="utf-8")

    config_text = """
paths:
  repo_root: "."
  config_dir: "config"
  source_dir: "data/source"
  normalized_dir: "data/normalized"
  artifacts_dir: "artifacts"
  manifests_dir: "artifacts/manifests"
  evidence_dir: "artifacts/evidence"
  drafts_dir: "artifacts/drafts"
  final_dir: "artifacts/final"
  translations_dir: "artifacts/translations"
  qa_dir: "artifacts/qa"
  logs_dir: "artifacts/logs"
  outputs_dir: "outputs"
  fonts_dir: "fonts"
source:
  file_path: "data/source/gatsby_source.txt"
  normalized_output_path: "data/normalized/gatsby_locked.txt"
  manifest_output_path: "artifacts/manifests/source_manifest.json"
  encoding: "utf-8"
indexing:
  output_path: "artifacts/manifests/passage_index.json"
  chapter_pattern: "^Chapter\\\\s+[IVXLC0-9]+$"
  paragraph_split_strategy: "blank_line"
models:
  endpoint: "http://localhost:11434/v1"
  api_key: "ollama"
  primary_reasoner: "gemma4:26b"
  translator_es: "gemma4:26b"
  translator_zh: "gemma4:26b"
  timeout_seconds: 1
  max_retries: 0
  retry_backoff_seconds: 0
llm_defaults:
  temperature: 0.2
  top_p: 0.9
  max_tokens: 512
prompts:
  translator_es_prompt_path: "config/prompts/translator_es.md"
  translator_es_cleanup_prompt_path: "config/prompts/translator_es_cleanup.md"
  translator_zh_prompt_path: "config/prompts/translator_zh.md"
  translator_zh_cleanup_prompt_path: "config/prompts/translator_zh_cleanup.md"
drafting:
  final_output_path: "artifacts/drafts/analysis_english_final.md"
  master_output_path: "artifacts/final/analysis_english_master.md"
translation:
  max_chunk_chars: 80
  post_edit_body: true
  preserve_headings: true
  preserve_citations: true
translation_outputs:
  spanish_output_path: "artifacts/translations/analysis_spanish_draft.md"
  mandarin_output_path: "artifacts/translations/analysis_mandarin_draft.md"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def extract_chunk_from_prompt(user_prompt: str) -> str:
    if "English markdown chunk:\n\n" in user_prompt:
        return user_prompt.split("English markdown chunk:\n\n", maxsplit=1)[1]
    if "Existing translated markdown chunk:\n\n" in user_prompt:
        return user_prompt.split("Existing translated markdown chunk:\n\n", maxsplit=1)[1]
    if "Existing translated markdown fragment:\n\n" in user_prompt:
        return user_prompt.split("Existing translated markdown fragment:\n\n", maxsplit=1)[1]
    if "English markdown fragment:\n\n" in user_prompt:
        return user_prompt.split("English markdown fragment:\n\n", maxsplit=1)[1]
    raise AssertionError(f"Unexpected prompt shape: {user_prompt}")


def test_split_markdown_into_chunks_preserves_block_boundaries() -> None:
    text = "# Title\n\n## One\n\nAlpha beta gamma.\n\n## Two\n\nDelta epsilon zeta."
    chunks = split_markdown_into_chunks(text, max_chars=30)

    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)
    assert chunks[0].startswith("# Title")


def test_translate_spanish_freezes_master_and_preserves_citations(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    prompts: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs["user_prompt"]
        prompts.append(user_prompt)
        return extract_chunk_from_prompt(user_prompt)

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert config.english_master_output_path.exists()
    assert config.spanish_translation_output_path.exists()
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]", "[1]"]
    assert "## Citas" in translated_text
    assert '1. F. Scott Fitzgerald, *El gran Gatsby*, cap. 1, párr. 1, pasaje citado que comienza "the green light".' in translated_text
    assert any("Existing translated markdown chunk:" in prompt for prompt in prompts)


def test_translate_mandarin_writes_output(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return extract_chunk_from_prompt(kwargs["user_prompt"])

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_mandarin(config)

    assert config.mandarin_translation_output_path.exists()
    assert translated_text.startswith("# An Analysis")
    assert "## 引文" in translated_text
    assert '1. F. Scott Fitzgerald，《了不起的盖茨比》，第1章，第1段，引文开头："the green light"。' in translated_text


def test_translate_spanish_falls_back_to_fragment_stitching_when_placeholders_drift(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    calls: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs["user_prompt"]
        calls.append(user_prompt)
        if "English markdown chunk:" in user_prompt:
            raise LLMResponseValidationError("Translated chunk changed the citation placeholder inventory", "")
        return extract_chunk_from_prompt(user_prompt)

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert config.spanish_translation_output_path.exists()
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]", "[1]"]
    assert any("English markdown chunk:" in call for call in calls)
    assert any("English markdown fragment:" in call for call in calls)
    assert any("Existing translated markdown chunk:" in call for call in calls)


def test_translate_spanish_uses_fragment_safe_cleanup_when_cleanup_chunk_placeholders_drift(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    calls: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs["user_prompt"]
        calls.append(user_prompt)
        if "Existing translated markdown chunk:" in user_prompt:
            raise LLMResponseValidationError("Translated chunk changed the citation placeholder inventory", "")
        return extract_chunk_from_prompt(user_prompt)

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert config.spanish_translation_output_path.exists()
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]", "[1]"]
    assert any("Existing translated markdown chunk:" in call for call in calls)
    assert any("Existing translated markdown fragment:" in call for call in calls)


def test_dynamic_validation_loop_applies_surgical_replacements_and_regex_fallbacks(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    prompt_path = repo_root / "config/prompts/dynamic_validation_critic.md"
    prompt_path.write_text("Return JSON only.\n", encoding="utf-8")
    config.prompts["dynamic_validation_prompt_path"] = "config/prompts/dynamic_validation_critic.md"
    config.verification["dynamic_validation_enabled"] = True

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return json.dumps(
            {
                "defects": [
                    {"hallucination": "metáían", "correction": "metáforas"},
                    {"hallucination": "imimita", "correction": "imita"},
                ],
                "notes": "Found two token-level defects.",
            }
        )

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    original_text = (
        "# Título\n\n"
        "metáían [1]\n\n"
        "0\n\n"
        "La casa imimita el orden [2],\n\n"
        "## Citas\n\n"
        '1. F. Scott Fitzgerald, *El gran Gatsby*, cap. 1, párr. 1, pasaje citado que comienza "metáían".\n'
    )

    sanitized_text, report = dynamic_validation_loop(
        config,
        text=original_text,
        language_name="Spanish",
        stage_name="dynamic_validate_spanish_translation",
    )

    assert report["status"] == "fixed"
    assert "metáían" not in sanitized_text
    assert "imimita" not in sanitized_text
    assert "metáforas" in sanitized_text
    assert "imita" in sanitized_text
    assert "\n0\n" not in sanitized_text
    assert "[2]," not in sanitized_text
    assert extract_visible_citation_markers(sanitized_text) == extract_visible_citation_markers(original_text)


def test_translate_spanish_runs_dynamic_validation_before_writing_output(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    prompt_path = repo_root / "config/prompts/dynamic_validation_critic.md"
    prompt_path.write_text("Return JSON only.\n", encoding="utf-8")
    config.prompts["dynamic_validation_prompt_path"] = "config/prompts/dynamic_validation_critic.md"
    config.verification["dynamic_validation_enabled"] = True

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        stage_name = kwargs["stage_name"]
        user_prompt = kwargs["user_prompt"]
        if stage_name == "dynamic_validate_english_master":
            return json.dumps({"defects": [], "notes": "No defects found."})
        if stage_name == "translate_spanish":
            return extract_chunk_from_prompt(user_prompt).replace("green light", "metáían")
        if stage_name == "translate_spanish_cleanup":
            return extract_chunk_from_prompt(user_prompt)
        if stage_name == "dynamic_validate_spanish_translation":
            return json.dumps(
                {
                    "defects": [
                        {"hallucination": "metáían", "correction": "metáforas"},
                    ],
                    "notes": "Found one token-level defect.",
                }
            )
        return extract_chunk_from_prompt(user_prompt)

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert "metáían" not in translated_text
    assert "metáforas" in translated_text
    assert config.spanish_translation_output_path.exists()


def test_freeze_english_master_applies_known_regression_fixes_and_writes_report(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        '# Title\n\nThe novel follows Nick Carrawical, and Fitzgerald says the Valley of West was a mistake, and Gatsby tried to maintain a punctiliously manner. '
        'He does not use metaphor merely as a decorative layer. '
        'The outline leans too hard on literal and figurative heat. '
        'Nick remarks, Your place looks like the Es World’s Fair [18]. '
        'He could still look out over the solemn dumping ground [5], hear the thin and far away [30] echoes of a dead dream, '
        'and note that a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity [6]. '
        'The ash-grey men, who move dimly and already crumbling through the powdery air [4], remain part of the landscape while grotesleque gardens rise nearby.\n',
        encoding="utf-8",
    )

    frozen = freeze_english_master(config)

    assert "Nick Carraway" in frozen
    assert "Valley of Ashes" in frozen
    assert "punctilious manner" in frozen
    assert "He does not use metaphors merely" in frozen
    assert "rising heat and social pressure" in frozen
    assert '*"Your place looks like the World’s Fair"* [18].' in frozen
    assert "grotesque gardens" in frozen
    assert '"look out over the solemn dumping ground" [5]' in frozen
    assert 'the "thin and far away" [30] echoes of a dead dream' in frozen
    assert '"a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity" [6]' in frozen
    assert '"ash-grey men, who move dimly and already crumbling through the powdery air" [4]' in frozen
    report_path = repo_root / "artifacts/qa/english_master_regression_report.json"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert '"status": "passed"' in report_text


def test_freeze_english_master_flags_unquoted_exact_quote_reuse(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        '# Title\n\nHe refers to the great wet barnyard of Long Island Sound [3].\n',
        encoding="utf-8",
    )

    try:
        freeze_english_master(config)
    except ValueError as exc:
        assert "terminology/regression validation" in str(exc)
    else:
        raise AssertionError("freeze_english_master should reject unquoted direct quote reuse")


def test_freeze_english_master_quotes_additional_exact_quote_reuse_patterns(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        '# Title\n\n'
        'Gatsby is described as Jay Gatsby of West Egg, Long Island, sprang from his Platonic conception of himself [13]. '
        'Later the pressure rises until the straw seats of the car hovered on the edge of combustion [22]. '
        'In the hotel scene, in this heat every extra gesture was an affront to the common store of life [23]. '
        'The ending fades into a man’s voice, very thin and far away [30].\n',
        encoding="utf-8",
    )

    frozen = freeze_english_master(config)

    assert '"Jay Gatsby of West Egg, Long Island, sprang from his Platonic conception of himself" [13]' in frozen
    assert '"the straw seats of the car hovered on the edge of combustion" [22]' in frozen
    assert '"in this heat every extra gesture was an affront to the common store of life" [23]' in frozen
    assert '"a man’s voice, very thin and far away" [30]' in frozen


def test_freeze_english_master_paraphrases_glass_against_hard_malice_prose_reuse(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        "# Title\n\n"
        "The novel concludes this arc by revealing that Jay Gatsby had broken up like glass against Tom’s hard malice [27].\n",
        encoding="utf-8",
    )

    frozen = freeze_english_master(config)

    assert "Jay Gatsby had broken up like glass against Tom’s hard malice [27]" not in frozen
    assert "Gatsby is described as breaking like glass against Tom’s hard malice [27]" in frozen


def test_freeze_english_master_fixes_denial_of_reality_and_quotes_ragged_edge_reference(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        "# Title\n\n"
        "By framing his ascent as a spiritual and fated event, Gatsby attempts to insulate his fragile identity from the unreality of reality that haunts his early years.\n\n"
        "In conclusion, the Middle West seemed like the ragged edge of the universe [2] when Nick looked back on it.\n",
        encoding="utf-8",
    )

    frozen = freeze_english_master(config)

    assert "unreality of reality" not in frozen
    assert "denial of reality" in frozen
    assert '*"the ragged edge of the universe"* [2]' in frozen


def test_freeze_english_master_normalizes_valley_of_ashes_only_in_prose(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        "# Title\n\n"
        "The novel turns the landscape into a valley of ashes where moral waste collects.\n\n"
        "> *\"This is a valley of ashes—a fantastic farm where ashes grow like wheat\"* [4]\n\n"
        "1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 2, para. 1, cited passage beginning "
        "\"This is a valley of ashes—a fantastic farm where ashes grow like wheat...\".\n",
        encoding="utf-8",
    )

    frozen = freeze_english_master(config)

    assert "the Valley of Ashes where moral waste collects" in frozen
    assert '"This is a valley of ashes—a fantastic farm where ashes grow like wheat"' in frozen


def test_extract_translated_quote_lookup_reads_inline_cited_quotes() -> None:
    translated = '\n'.join(
        [
            'El narrador observa «el borde deshilachado del universo» [2] en el pasaje.',
            'Más tarde, la imagen reaparece como «el gran corral húmedo de Long Island Sound» [3].',
        ]
    )

    lookup = extract_translated_quote_lookup(translated)

    assert lookup[2] == "«el borde deshilachado del universo»"
    assert lookup[3] == "«el gran corral húmedo de Long Island Sound»"


def test_localize_citation_metadata_line_uses_language_overrides_when_quote_lookup_is_missing() -> None:
    spanish_line = '29. F. Scott Fitzgerald, *The Great Gatsby*, ch. 9, para. 35, cited passage beginning "His eyes leaked continuously with excitement".'
    mandarin_line = '27. F. Scott Fitzgerald, *The Great Gatsby*, ch. 8, para. 9, cited passage beginning "It was this night that he told me the strange story of his youth...".'

    localized_spanish = localize_citation_metadata_line(spanish_line, language_name="Spanish", translated_quote_lookup={})
    localized_mandarin = localize_citation_metadata_line(
        mandarin_line,
        language_name="Simplified Chinese",
        translated_quote_lookup={},
    )

    assert "Los ojos se le llenaban continuamente de emoción" in localized_spanish
    assert "‘杰伊·盖茨比’像玻璃一样在汤姆冷酷的恶意面前碎裂了" in localized_mandarin


def test_normalize_translated_body_fixes_remaining_spanish_and_mandarin_overliteral_phrases() -> None:
    spanish = (
        "La confrontación entre Gatsby y Tom proporciona el momento en que esta artificialidad se rompe físicamente. "
        "El impacto del antagonismo de Tom no solo hiere a Gatsby; rompe físicamente la imagen que él ha pasado años perfeccionando."
    )
    mandarin = (
        "Please provide the markdown fragment you would like me to revise. "
        "I am ready to apply the professional academic copyediting standards described in your instructions. "
        "灰烬是如此普遍，以至于它在物理层面上改变了生活其中的人，而这种虚假性也在物理层面发生破碎的时刻显现出来。 "
        "因为环境在物理层面上吞噬了角色。 "
        "因为环境在物理层面已然吞噬了角色。 "
        "汤姆所带来的敌意冲击更在物理层面上粉碎了他多年来苦心经营的形象。 "
        "汤姆的敌意所带来的冲击更在物理层面上击碎了他多年来致力于完善的形象。 "
        "盖茨比社会地位的崩塌，始于其庄园在物理层面的荒废。 "
        "这也反映在他庄园物理层面的退化中。 "
        ">*“整个商队旅馆像纸牌屋一样倒塌了”* AGColog[18]"
    )

    normalized_spanish = normalize_translated_body(spanish, language_name="Spanish")
    normalized_mandarin = normalize_translated_body(mandarin, language_name="Simplified Chinese")

    assert "rompe físicamente" not in normalized_spanish
    assert "quiebra de forma visible" in normalized_spanish
    assert "quiebra simbólicamente la imagen" in normalized_spanish
    assert "物理层面" not in normalized_mandarin
    assert "Please provide the markdown fragment" not in normalized_mandarin
    assert "切实地改变了生活其中的人" in normalized_mandarin
    assert "明显走向破碎的时刻" in normalized_mandarin
    assert "逐渐吞噬了角色" in normalized_mandarin
    assert "已然吞噬了角色" in normalized_mandarin
    assert "象征性地粉碎了他多年来苦心经营的形象" in normalized_mandarin
    assert "更象征性地击碎了他多年来致力于完善的形象" in normalized_mandarin
    assert "其庄园明显可见的荒废" in normalized_mandarin
    assert "庄园明显可见的退化" in normalized_mandarin
    assert '>*“整个商队旅馆像纸牌屋一样倒塌了”* [18]' in normalized_mandarin


def test_normalize_translated_body_removes_prompt_leaks_and_current_spanish_mandarin_corruptions() -> None:
    spanish = (
        "Fitzgerald utiliza metáfor yas para ilustcionar el problema. "
        "Esto ocurre durante el apogeencia de la fiesta, y el narración describe la cesta de un servicio de catering [10]. "
        "Please provide the Spanish markdown fragment you would like me to revise. "
        "I am ready to apply the professional academic copyediting standards described in your instructions. "
        "Los personajes pierta la capacidad de seguir adelante, y El emocionante murmullo de su voz era un tónico salvaje bajo la lluvia."
    )
    mandarin = (
        "菲茨杰是否存在利用地质和空间隐喻，建立了一个人物与景观都不具备固定、可靠中心的的世界。 "
        "他将长显长岛海峡那巨大的湿漉漉的牲口棚写成从餐饮承包园的篮子里产出的景象。 "
        "来自长岛西卵的杰伊·构想中的杰伊·盖茨比随即出现，杰伊·盖茨比那模糊的轮廓已变得如一个男人般厚实感。 "
        "他的轮廓后来又被误写成实体感感。 "
        "这套叙骗手段最终压在盖盖茨比身上。 "
        "《了_不起的盖茨比》里的尼克·是否·卡拉威听着黄色鸡模音乐，闻到香骗的气味。 "
        "在 [12] 在文中，菲茨杰拉德将汤向描述为一个能产生巨大杠杆作用的躯体。 "
        "灰烬最终在物理层面上吞噬着生活其中的人们。 "
        "这种不稳定性从生物层面延伸到了物理层面。"
    )

    normalized_spanish = normalize_translated_body(spanish, language_name="Spanish")
    normalized_mandarin = normalize_translated_body(mandarin, language_name="Simplified Chinese")

    assert "metáfor yas" not in normalized_spanish
    assert "ilustcionar" not in normalized_spanish
    assert "apogeencia" not in normalized_spanish
    assert "servicio de catering" not in normalized_spanish
    assert "Please provide the Spanish markdown fragment" not in normalized_spanish
    assert "professional academic copyediting standards" not in normalized_spanish
    assert "pierta" not in normalized_spanish
    assert "emocionante murmullo de su voz" not in normalized_spanish
    assert "metáforas" in normalized_spanish
    assert "ilustrar" in normalized_spanish
    assert "apogeo" in normalized_spanish
    assert "servicio de banquetes" in normalized_spanish
    assert "pierden" in normalized_spanish
    assert "El excitante ondular de su voz" in normalized_spanish

    assert "菲茨杰是否存在" not in normalized_mandarin
    assert "长显长岛海峡" not in normalized_mandarin
    assert "餐饮承包园" not in normalized_mandarin
    assert "构想中的杰伊·盖茨比" not in normalized_mandarin
    assert "厚实感" not in normalized_mandarin
    assert "叙骗手段" not in normalized_mandarin
    assert "盖盖茨比" not in normalized_mandarin
    assert "菲茨杰拉德利用地质和空间隐喻" in normalized_mandarin
    assert "长岛海峡那片潮湿而阔大的牲口院" in normalized_mandarin
    assert "餐饮承包商" in normalized_mandarin
    assert "来自长岛西卵的杰伊·盖茨比" in normalized_mandarin
    assert "已充实为一个男人的实体感" in normalized_mandarin
    assert "实体感感" not in normalized_mandarin
    assert "叙事手段" in normalized_mandarin
    assert "盖茨比" in normalized_mandarin
    assert "《了_不起的盖茨比》" not in normalized_mandarin
    assert "尼克·是否·卡拉威" not in normalized_mandarin
    assert "黄色鸡模音乐" not in normalized_mandarin
    assert "香骗" not in normalized_mandarin
    assert "在 [12] 在文中" not in normalized_mandarin
    assert "菲茨杰拉德将汤向描述为" not in normalized_mandarin
    assert "物理层面" not in normalized_mandarin
    assert "《了不起的盖茨比》" in normalized_mandarin
    assert "尼克·卡拉威" in normalized_mandarin
    assert "黄色鸡尾酒音乐" in normalized_mandarin
    assert "香槟" in normalized_mandarin
    assert "在 [12] 中" in normalized_mandarin
    assert "菲茨杰拉德将汤姆描述为" in normalized_mandarin
    assert "逐渐吞噬着生活其中的人们" in normalized_mandarin
    assert "这种不稳定性从生物意象延伸到了流体意象" in normalized_mandarin
