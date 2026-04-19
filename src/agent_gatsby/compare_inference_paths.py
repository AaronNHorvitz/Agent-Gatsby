"""
Compare one real drafting prompt across multiple local inference interfaces.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from agent_gatsby.config import AppConfig, load_config
from agent_gatsby.draft_english import (
    build_draft_user_prompt,
    build_evidence_lookup,
    gather_section_evidence,
    load_draft_prompt,
)
from agent_gatsby.index_text import PassageIndex, load_passage_index
from agent_gatsby.llm_client import build_client, describe_response, extract_message_text, extract_reasoning_text
from agent_gatsby.plan_outline import load_evidence_records, load_outline
from agent_gatsby.schemas import EvidenceRecord, OutlinePlan, OutlineSection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare one drafting prompt across the OpenAI-compatible, native Ollama, and CLI interfaces."
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to the repo config file.",
    )
    parser.add_argument(
        "--section-id",
        default=None,
        help="Explicit outline section ID to compare. Defaults to the first outline section.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for debug artifacts. Defaults to artifacts/qa/interface_compare.",
    )
    parser.add_argument(
        "--skip-cli",
        action="store_true",
        help="Skip the ollama CLI comparison path.",
    )
    return parser.parse_args()


def load_section_context(config: AppConfig, section_id: str | None) -> tuple[OutlinePlan, OutlineSection, list[EvidenceRecord], PassageIndex]:
    outline = load_outline(config)
    evidence_records = load_evidence_records(config)
    passage_index = load_passage_index(config)
    evidence_lookup = build_evidence_lookup(evidence_records)

    if section_id is None:
        if not outline.sections:
            raise ValueError("Outline contains no sections to compare")
        section = outline.sections[0]
    else:
        try:
            section = next(item for item in outline.sections if item.section_id == section_id)
        except StopIteration as exc:
            available = ", ".join(item.section_id for item in outline.sections)
            raise ValueError(f"Unknown section ID '{section_id}'. Available: {available}") from exc

    section_evidence = gather_section_evidence(section, evidence_lookup)
    return outline, section, section_evidence, passage_index


def build_prompt_bundle(
    config: AppConfig,
    *,
    outline: OutlinePlan,
    section: OutlineSection,
    evidence_records: list[EvidenceRecord],
    passage_index: PassageIndex,
) -> tuple[str, str]:
    system_prompt = load_draft_prompt(config)
    user_prompt = build_draft_user_prompt(
        config,
        outline,
        section_type="body",
        heading=section.heading,
        section_notes=section.purpose or "",
        evidence_records=evidence_records,
        passage_index=passage_index,
    )
    return system_prompt, user_prompt


def resolve_output_dir(config: AppConfig, custom_output_dir: str | None) -> Path:
    if custom_output_dir:
        output_dir = config.resolve_repo_path(custom_output_dir)
    else:
        output_dir = config.resolve_repo_path(config.paths.qa_dir) / "interface_compare"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def derive_native_ollama_endpoint(config: AppConfig) -> str:
    parsed = urlparse(str(config.require_mapping_value("models", "endpoint")))
    path = parsed.path or ""
    if path.endswith("/v1"):
        path = path[:-3]
    path = path.rstrip("/")
    return urlunparse(parsed._replace(path=path))


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def call_openai_compatible(config: AppConfig, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    client = build_client(config)
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=config.model_name_for("primary_reasoner"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=float(config.llm_defaults.get("temperature", 0.2)),
        top_p=float(config.llm_defaults.get("top_p", 0.9)),
        max_tokens=int(config.llm_defaults.get("max_tokens", 4096)),
        timeout=int(config.models.get("timeout_seconds", 180)),
    )
    elapsed = round(time.perf_counter() - start, 3)
    content = extract_message_text(response)
    reasoning = extract_reasoning_text(response)
    return {
        "path": "openai_compatible",
        "ok": True,
        "elapsed_seconds": elapsed,
        "finish_reason": getattr(response.choices[0], "finish_reason", None),
        "response_text": content,
        "reasoning_text": reasoning,
        "response_len": len(content),
        "reasoning_len": len(reasoning),
        "description": describe_response(response),
    }


def call_native_ollama_chat(config: AppConfig, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    endpoint = derive_native_ollama_endpoint(config) + "/api/chat"
    payload = {
        "model": config.model_name_for("primary_reasoner"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": float(config.llm_defaults.get("temperature", 0.2)),
            "top_p": float(config.llm_defaults.get("top_p", 0.9)),
            "num_predict": int(config.llm_defaults.get("max_tokens", 4096)),
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urlopen(request, timeout=int(config.models.get("timeout_seconds", 180))) as response:
        raw_response = json.loads(response.read().decode("utf-8"))
    elapsed = round(time.perf_counter() - start, 3)

    message = raw_response.get("message", {})
    content = str(message.get("content", raw_response.get("response", "")) or "")
    reasoning = str(message.get("thinking", raw_response.get("thinking", "")) or "")
    return {
        "path": "native_ollama_chat",
        "ok": True,
        "elapsed_seconds": elapsed,
        "finish_reason": raw_response.get("done_reason"),
        "response_text": content,
        "reasoning_text": reasoning,
        "response_len": len(content),
        "reasoning_len": len(reasoning),
        "raw_response": raw_response,
    }


def build_cli_prompt(system_prompt: str, user_prompt: str) -> str:
    return (
        "System instructions:\n"
        + system_prompt.strip()
        + "\n\nUser request:\n"
        + user_prompt.strip()
        + "\n"
    )


def call_ollama_cli(config: AppConfig, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    ollama_binary = shutil.which("ollama")
    if not ollama_binary:
        raise FileNotFoundError("Could not find 'ollama' on PATH")

    start = time.perf_counter()
    completed = subprocess.run(
        [ollama_binary, "run", config.model_name_for("primary_reasoner")],
        input=build_cli_prompt(system_prompt, user_prompt),
        capture_output=True,
        text=True,
        timeout=int(config.models.get("timeout_seconds", 180)),
        check=False,
    )
    elapsed = round(time.perf_counter() - start, 3)
    return {
        "path": "ollama_cli",
        "ok": completed.returncode == 0,
        "elapsed_seconds": elapsed,
        "returncode": completed.returncode,
        "response_text": completed.stdout,
        "stderr_text": completed.stderr,
        "response_len": len(completed.stdout),
        "stderr_len": len(completed.stderr),
    }


def capture_call(name: str, func: Any) -> dict[str, Any]:
    try:
        return func()
    except (HTTPError, URLError, subprocess.SubprocessError, TimeoutError, OSError, ValueError) as exc:
        return {
            "path": name,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:  # pragma: no cover - defensive debug path
        return {
            "path": name,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def write_artifacts(
    output_dir: Path,
    *,
    system_prompt: str,
    user_prompt: str,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    write_text(output_dir / "system_prompt.md", system_prompt)
    write_text(output_dir / "user_prompt.md", user_prompt)
    write_text(output_dir / "summary.json", json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    for result in results:
        prefix = result["path"]
        write_text(output_dir / f"{prefix}_metadata.json", json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        if "response_text" in result:
            write_text(output_dir / f"{prefix}_response.txt", str(result["response_text"]))
        if "reasoning_text" in result:
            write_text(output_dir / f"{prefix}_reasoning.txt", str(result["reasoning_text"]))
        if "stderr_text" in result:
            write_text(output_dir / f"{prefix}_stderr.txt", str(result["stderr_text"]))


def print_summary(summary: dict[str, Any]) -> None:
    print(f"Section: {summary['section_id']} — {summary['section_heading']}")
    print(f"Prompt chars: system={summary['system_prompt_chars']} user={summary['user_prompt_chars']}")
    print(f"Artifacts: {summary['output_dir']}")
    print()
    for result in summary["results"]:
        label = result["path"]
        if result["ok"]:
            print(
                f"{label}: ok elapsed={result.get('elapsed_seconds')}s "
                f"response_len={result.get('response_len')} reasoning_len={result.get('reasoning_len', 0)} "
                f"finish_reason={result.get('finish_reason', 'n/a')}"
            )
        else:
            if "error" in result:
                print(f"{label}: error {result['error']}")
            else:
                print(
                    f"{label}: failed elapsed={result.get('elapsed_seconds', 'n/a')}s "
                    f"returncode={result.get('returncode', 'n/a')} stderr_len={result.get('stderr_len', 0)}"
                )


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    outline, section, evidence_records, passage_index = load_section_context(config, args.section_id)
    system_prompt, user_prompt = build_prompt_bundle(
        config,
        outline=outline,
        section=section,
        evidence_records=evidence_records,
        passage_index=passage_index,
    )
    output_dir = resolve_output_dir(config, args.output_dir)

    results = [
        capture_call(
            "openai_compatible",
            lambda: call_openai_compatible(
                config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            ),
        ),
        capture_call(
            "native_ollama_chat",
            lambda: call_native_ollama_chat(
                config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            ),
        ),
    ]
    if not args.skip_cli:
        results.append(
            capture_call(
                "ollama_cli",
                lambda: call_ollama_cli(
                    config,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                ),
            )
        )

    summary = {
        "config_path": str(config.config_path),
        "model_name": config.model_name_for("primary_reasoner"),
        "section_id": section.section_id,
        "section_heading": section.heading,
        "evidence_ids": [record.evidence_id for record in evidence_records],
        "allowed_passage_ids": [record.passage_id for record in evidence_records],
        "system_prompt_chars": len(system_prompt),
        "user_prompt_chars": len(user_prompt),
        "output_dir": str(output_dir),
        "results": results,
    }

    write_artifacts(
        output_dir,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        summary=summary,
        results=results,
    )
    print_summary(summary)
    return 0 if any(result.get("ok") for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
