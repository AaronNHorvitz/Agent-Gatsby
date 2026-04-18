"""
Candidate metaphor extraction for Agent Gatsby.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from pathlib import Path
from typing import Any

from agent_gatsby.config import AppConfig
from agent_gatsby.index_text import load_passage_index
from agent_gatsby.llm_client import LLMResponseValidationError, invoke_text_completion
from agent_gatsby.schemas import MetaphorCandidate, PassageIndex, PassageRecord

LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_PASSAGE_CHARS = 12000
DEFAULT_MAX_PASSAGES_PER_BATCH = 40
JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
JSON_ARRAY_RE = re.compile(r"\[\s*{.*}\s*\]", re.DOTALL)
JSON_OBJECT_RE = re.compile(r"{.*}", re.DOTALL)

CANONICAL_CANDIDATE_FIELDS = {
    "candidate_id",
    "label",
    "passage_id",
    "quote",
    "rationale",
    "confidence",
}
FIELD_ALIAS_MAP = {
    "candidateid": "candidate_id",
    "canidateid": "candidate_id",
    "candidateim": "candidate_id",
    "candidateids": "candidate_id",
    "label": "label",
    "metaphor": "label",
    "image": "label",
    "symbol": "label",
    "passageid": "passage_id",
    "passage": "passage_id",
    "passagelocator": "passage_id",
    "quote": "quote",
    "quotespan": "quote",
    "quotation": "quote",
    "excerpt": "quote",
    "rationale": "rationale",
    "rational": "rationale",
    "ratione": "rationale",
    "reason": "rationale",
    "notes": "rationale",
    "interpretation": "rationale",
    "confidence": "confidence",
    "score": "confidence",
    "confidencescore": "confidence",
}
LIST_CONTAINER_KEYS = ("candidates", "results", "items")


def normalize_field_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def find_json_segment(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return stripped

    array_match = JSON_ARRAY_RE.search(stripped)
    if array_match:
        return array_match.group(0)

    object_match = JSON_OBJECT_RE.search(stripped)
    if object_match:
        return object_match.group(0)

    return stripped


def extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if text.startswith("```"):
        text = JSON_FENCE_RE.sub("", text).strip()
    return find_json_segment(text)


def map_candidate_field(raw_key: str) -> str | None:
    normalized_key = normalize_field_key(raw_key)
    if normalized_key in FIELD_ALIAS_MAP:
        return FIELD_ALIAS_MAP[normalized_key]

    canonical_lookup = {normalize_field_key(field): field for field in CANONICAL_CANDIDATE_FIELDS}
    closest = difflib.get_close_matches(normalized_key, canonical_lookup.keys(), n=1, cutoff=0.78)
    if closest:
        return canonical_lookup[closest[0]]
    return None


def extract_candidate_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in LIST_CONTAINER_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value

    raise ValueError("Expected extraction response to be a JSON array or an object containing candidate list data")


def canonicalize_candidate_item(item: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"Candidate item {index} is not an object")

    canonical: dict[str, Any] = {}
    for raw_key, value in item.items():
        mapped_key = map_candidate_field(str(raw_key))
        if mapped_key is None:
            continue
        canonical.setdefault(mapped_key, value)

    canonical.setdefault("candidate_id", f"RAW{index:03d}")
    return canonical


def parse_candidate_response(response_text: str) -> list[MetaphorCandidate]:
    payload = json.loads(extract_json_payload(response_text))
    items = extract_candidate_items(payload)
    return [
        MetaphorCandidate.model_validate(canonicalize_candidate_item(item, index=index))
        for index, item in enumerate(items, start=1)
    ]


def validate_candidate_response(response_text: str) -> None:
    parse_candidate_response(response_text)


def load_extractor_prompt(config: AppConfig) -> str:
    return config.resolve_prompt_path("extractor_prompt_path").read_text(encoding="utf-8")


def load_metaphor_candidates(source: AppConfig | str | Path) -> list[MetaphorCandidate]:
    if isinstance(source, AppConfig):
        path = source.metaphor_candidates_path
    else:
        path = Path(source)

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected candidate file at {path} to contain a JSON array")
    return [MetaphorCandidate.model_validate(item) for item in data]


def chunk_passages(
    passages: list[PassageRecord],
    *,
    max_chars: int = DEFAULT_MAX_PASSAGE_CHARS,
    max_passages: int = DEFAULT_MAX_PASSAGES_PER_BATCH,
) -> list[list[PassageRecord]]:
    batches: list[list[PassageRecord]] = []
    current_batch: list[PassageRecord] = []
    current_chars = 0

    for passage in passages:
        projected_chars = current_chars + len(passage.text) + len(passage.passage_id) + 32
        if current_batch and (projected_chars > max_chars or len(current_batch) >= max_passages):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

        current_batch.append(passage)
        current_chars += len(passage.text) + len(passage.passage_id) + 32

    if current_batch:
        batches.append(current_batch)

    return batches


def render_passage_payload(passages: list[PassageRecord]) -> str:
    payload = [{"passage_id": passage.passage_id, "text": passage.text} for passage in passages]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_extraction_user_prompt(
    passages: list[PassageRecord],
    *,
    batch_index: int,
    total_batches: int,
    stricter_json: bool = False,
) -> str:
    instructions = [
        f"Batch {batch_index} of {total_batches}.",
        "Identify candidate metaphors, recurring symbolic images, and metaphor-adjacent figurative patterns.",
        "Return only a JSON array of candidate objects.",
        "Use only the provided passages.",
        "Every quote must be an exact substring from the referenced passage text.",
        "Do not reveal reasoning, chain-of-thought, or any text before or after the JSON.",
        "Each candidate object must use exactly these keys: candidate_id, label, passage_id, quote, rationale, confidence.",
        "Do not rename keys, even if you are uncertain.",
        "If you are unsure about a candidate, omit it rather than returning malformed JSON.",
    ]
    if stricter_json:
        instructions.append("Do not wrap the JSON in markdown fences or add any explanation.")
        instructions.append("If no good candidates exist, return [] exactly.")

    return "\n".join(instructions) + "\n\nPassages:\n" + render_passage_payload(passages)


def write_candidates(config: AppConfig, candidates: list[MetaphorCandidate]) -> None:
    output_path = config.metaphor_candidates_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([candidate.model_dump() for candidate in candidates], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote %d metaphor candidates to %s", len(candidates), output_path)


def append_debug_output(config: AppConfig, *, batch_index: int, attempt_label: str, response_text: str) -> None:
    output_path = config.extraction_raw_debug_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"===== batch {batch_index} | {attempt_label} =====\n")
        handle.write(response_text.rstrip())
        handle.write("\n\n")


def clear_debug_output(config: AppConfig) -> None:
    output_path = config.extraction_raw_debug_path
    if output_path.exists():
        output_path.unlink()


def normalize_candidate_ids(candidates: list[MetaphorCandidate]) -> list[MetaphorCandidate]:
    normalized: list[MetaphorCandidate] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for candidate in candidates:
        key = (
            candidate.passage_id,
            candidate.quote,
            " ".join(candidate.label.lower().split()),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        normalized.append(candidate)

    return [
        candidate.model_copy(update={"candidate_id": f"C{index:03d}"})
        for index, candidate in enumerate(normalized, start=1)
    ]


def warn_on_candidate_count(config: AppConfig, count: int) -> None:
    minimum = int(config.extraction.get("minimum_candidate_count", 0))
    maximum = int(config.extraction.get("maximum_candidate_count", 0))
    if minimum and count < minimum:
        LOGGER.warning("Extracted candidate count %d is below configured minimum %d", count, minimum)
    if maximum and count > maximum:
        LOGGER.warning("Extracted candidate count %d exceeds configured maximum %d", count, maximum)


def extract_batch_candidates(
    config: AppConfig,
    *,
    system_prompt: str,
    passages: list[PassageRecord],
    batch_index: int,
    total_batches: int,
) -> list[MetaphorCandidate]:
    output_path = str(config.metaphor_candidates_path)
    initial_prompt = build_extraction_user_prompt(passages, batch_index=batch_index, total_batches=total_batches)

    try:
        raw_response = invoke_text_completion(
            config,
            stage_name="extract_metaphors",
            system_prompt=system_prompt,
            user_prompt=initial_prompt,
            output_path=output_path,
            response_validator=validate_candidate_response,
        )
        return parse_candidate_response(raw_response)
    except LLMResponseValidationError as exc:
        append_debug_output(config, batch_index=batch_index, attempt_label="initial_invalid_json", response_text=exc.response_text)
        stricter_prompt = build_extraction_user_prompt(
            passages,
            batch_index=batch_index,
            total_batches=total_batches,
            stricter_json=True,
        )
        try:
            raw_response = invoke_text_completion(
                config,
                stage_name="extract_metaphors",
                system_prompt=system_prompt,
                user_prompt=stricter_prompt,
                output_path=output_path,
                response_validator=validate_candidate_response,
            )
            return parse_candidate_response(raw_response)
        except LLMResponseValidationError as retry_exc:
            append_debug_output(
                config,
                batch_index=batch_index,
                attempt_label="retry_invalid_json",
                response_text=retry_exc.response_text,
            )
            raise


def extract_metaphor_candidates(
    config: AppConfig,
    passage_index: PassageIndex | None = None,
) -> list[MetaphorCandidate]:
    clear_debug_output(config)
    loaded_index = passage_index or load_passage_index(config)
    system_prompt = load_extractor_prompt(config)
    batches = chunk_passages(loaded_index.passages)

    all_candidates: list[MetaphorCandidate] = []
    for batch_number, batch in enumerate(batches, start=1):
        batch_candidates = extract_batch_candidates(
            config,
            system_prompt=system_prompt,
            passages=batch,
            batch_index=batch_number,
            total_batches=len(batches),
        )
        all_candidates.extend(batch_candidates)

    normalized_candidates = normalize_candidate_ids(all_candidates)
    if not normalized_candidates:
        raise ValueError("Extraction produced no candidate metaphor records")

    write_candidates(config, normalized_candidates)
    warn_on_candidate_count(config, len(normalized_candidates))
    return normalized_candidates
