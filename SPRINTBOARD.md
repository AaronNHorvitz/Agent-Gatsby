# Agent Gatsby Weekend Execution Plan
## Goal
Build, test, debug, and package a working local AI pipeline that:
- ingests a locked source text of *The Great Gatsby*
- extracts candidate metaphors
- builds an evidence ledger
- drafts an English essay with citations
- translates the final English essay into Spanish
- translates the final English essay into Mandarin (Simplified Chinese)
- renders three separate PDFs
- includes unit tests, basic integration tests, logs, and a final runnable repository

**Current Status:** Weekend sprint completed. The core pipeline, frozen English master, translations, QA reports, PDFs, manifest, and submission packaging are in shipped state.

---

# 0. Ground Rules for the Weekend
- [x] 0.1 Do **not** start by chasing perfection.
- [x] 0.2 Do **not** start by polishing the README again.
- [x] 0.3 Do **not** start by designing advanced future features.
- [x] 0.4 Build the **smallest working pipeline first**, then harden it.
- [x] 0.5 At every stage, make sure there is a file on disk that proves the stage worked.
- [x] 0.6 At every stage, add at least one test or one validation check.
- [x] 0.7 If a stage fails, fix the stage before moving on.
- [x] 0.8 Always keep the pipeline runnable from the command line.
- [x] 0.9 Commit after each major milestone.

---

# 1. Definition of Done
The project is considered done only if all of the following are true:

- [x] 1.1 Repo has a clean structure.
- [x] 1.2 README reflects the final architecture.
- [x] 1.3 Config file exists and is used by code.
- [x] 1.4 Source text is locked and hashed.
- [x] 1.5 Passage indexing works.
- [x] 1.6 Candidate metaphor extraction works.
- [x] 1.7 Evidence ledger file is produced.
- [x] 1.8 English outline is produced.
- [x] 1.9 English draft is produced.
- [x] 1.10 English quote/citation verification runs.
- [x] 1.11 English final master is produced.
- [x] 1.12 Spanish translation file is produced.
- [x] 1.13 Mandarin translation file is produced.
- [x] 1.14 QA checks for translations run.
- [x] 1.15 Three PDFs are successfully rendered.
- [x] 1.16 Unit tests run cleanly.
- [x] 1.17 At least one lightweight end-to-end test runs.
- [x] 1.18 Logs are written to disk.
- [x] 1.19 Final manifest is written.
- [x] 1.20 The repo can be demonstrated by running a clear command sequence.

---

# 2. Minimum Viable Scope
This is the version you must finish first before adding anything fancy.

## 2.1 Required MVP components
- [x] 2.1.1 `config/config.yaml`
- [x] 2.1.2 `src/agent_gatsby/orchestrator.py`
- [x] 2.1.3 `src/agent_gatsby/data_ingest.py`
- [x] 2.1.4 `src/agent_gatsby/normalize.py`
- [x] 2.1.5 `src/agent_gatsby/index_text.py`
- [x] 2.1.6 `src/agent_gatsby/extract_metaphors.py`
- [x] 2.1.7 `src/agent_gatsby/build_evidence_ledger.py`
- [x] 2.1.8 `src/agent_gatsby/plan_outline.py`
- [x] 2.1.9 `src/agent_gatsby/draft_english.py`
- [x] 2.1.10 `src/agent_gatsby/verify_citations.py`
- [x] 2.1.11 `src/agent_gatsby/critique_and_edit.py`
- [x] 2.1.12 `src/agent_gatsby/translate_spanish.py`
- [x] 2.1.13 `src/agent_gatsby/translate_mandarin.py`
- [x] 2.1.14 `src/agent_gatsby/bilingual_qa.py`
- [x] 2.1.15 `src/agent_gatsby/pdf_compiler.py`
- [x] 2.1.16 `src/agent_gatsby/manifest_writer.py`
- [x] 2.1.17 `tests/`
- [x] 2.1.18 `requirements.txt`
- [x] 2.1.19 `README.md`

## 2.2 Explicitly postpone until MVP works
- [ ] 2.2.1 Embeddings
- [ ] 2.2.2 Semantic retrieval
- [ ] 2.2.3 Train a custom metaphor classifier or create a labeled metaphor dataset
- [ ] 2.2.4 Multi-model routing
- [ ] 2.2.5 Docker
- [ ] 2.2.6 CI/CD
- [ ] 2.2.7 Web UI
- [ ] 2.2.8 Fancy observability dashboards
- [ ] 2.2.9 Parallel execution
- [ ] 2.2.10 Advanced retry schedulers

---

# 3. Weekend Schedule Overview
## 3.1 Thursday Night
Focus: repo scaffold + config + source lock + ingestion + normalization

## 3.2 Friday
Focus: indexing + candidate extraction + evidence ledger + outline

## 3.3 Saturday
Focus: English drafting + verification + editorial pass + tests

## 3.4 Sunday
Focus: translations + translation QA + PDFs + manifest + full dry run + final cleanup

---

# 4. Thursday Night — Setup and Foundation
## 4.1 Create the repo structure
- [x] 4.1.1 Open the repository root.
- [x] 4.1.2 Create `config/`
- [x] 4.1.3 Create `data/source/`
- [x] 4.1.4 Create `data/normalized/`
- [x] 4.1.5 Create `artifacts/manifests/`
- [x] 4.1.6 Create `artifacts/evidence/`
- [x] 4.1.7 Create `artifacts/drafts/`
- [x] 4.1.8 Create `artifacts/translations/`
- [x] 4.1.9 Create `artifacts/qa/`
- [x] 4.1.10 Create `artifacts/logs/`
- [x] 4.1.11 Create `outputs/`
- [x] 4.1.12 Create `fonts/`
- [x] 4.1.13 Create `src/agent_gatsby/`
- [x] 4.1.14 Do not create `src/agent_gatsby/utils/` unless it becomes necessary
- [x] 4.1.15 Create `tests/`

## 4.2 Create base files
- [x] 4.2.1 Create `README.md`
- [x] 4.2.2 Create `requirements.txt`
- [x] 4.2.3 Create `pyproject.toml` if you want packaging consistency
- [x] 4.2.4 Create `config/config.yaml`
- [x] 4.2.5 Create `src/agent_gatsby/__init__.py`
- [x] 4.2.6 Create `src/agent_gatsby/schemas.py`
- [x] 4.2.7 Create `src/agent_gatsby/config.py`
- [x] 4.2.8 Create `src/agent_gatsby/orchestrator.py`

## 4.3 Install and verify local environment
- [x] 4.3.1 Activate your environment.
- [x] 4.3.2 Install base dependencies.
- [x] 4.3.3 Verify Python version.
- [x] 4.3.4 Verify `ollama` is installed.
- [x] 4.3.5 Verify `ollama serve` starts.
- [x] 4.3.6 Pull the model you plan to use.
- [x] 4.3.7 Run a trivial test prompt against the local endpoint.
- [x] 4.3.8 Save the exact working command you used.

## 4.4 Build `requirements.txt`
Include only what you actually need.
- [x] 4.4.1 Add `pyyaml`
- [x] 4.4.2 Add `requests`
- [x] 4.4.3 Add `fpdf2`
- [x] 4.4.4 Add `pytest`
- [x] 4.4.5 Add `pydantic` if you want schema validation
- [x] 4.4.6 Add `openai` only if using Ollama’s OpenAI-compatible endpoint
- [x] 4.4.7 Add anything else only if truly necessary

## 4.5 Build `config/config.yaml`
- [x] 4.5.1 Add output directory paths
- [x] 4.5.2 Add artifact directory paths
- [x] 4.5.3 Add model endpoint
- [x] 4.5.4 Add model name
- [x] 4.5.5 Add drafting temperature
- [x] 4.5.6 Add translation settings
- [x] 4.5.7 Add PDF settings
- [x] 4.5.8 Add log level
- [x] 4.5.9 Add source file path
- [x] 4.5.10 Add final output file names

## 4.6 Build `config.py`
- [x] 4.6.1 Write code to load YAML config
- [x] 4.6.2 Validate required keys exist
- [x] 4.6.3 Return config object
- [x] 4.6.4 Add clean error if config file missing
- [x] 4.6.5 Add clean error if required key missing

## 4.7 Build logging utility
- [x] 4.7.1 Create `logging_utils.py`
- [x] 4.7.2 Add file logger
- [x] 4.7.3 Add console logger
- [x] 4.7.4 Make logs go to `artifacts/logs/pipeline.log`
- [x] 4.7.5 Confirm a log message writes successfully

## 4.8 Lock the source text
Decide now: use a local source file as canonical.
- [x] 4.8.1 Place source text in `data/source/gatsby_source.txt`
- [x] 4.8.2 Open file and visually inspect beginning and end
- [x] 4.8.3 Confirm encoding is UTF-8
- [x] 4.8.4 Implement SHA-256 hashing in the ingestion path
- [x] 4.8.5 Write a SHA-256 hash function
- [x] 4.8.6 Hash the raw source file
- [x] 4.8.7 Save the hash to `artifacts/manifests/source_manifest.json`

## 4.9 Build `data_ingest.py`
- [x] 4.9.1 Load source text from local file
- [x] 4.9.2 Validate file exists
- [x] 4.9.3 Validate text is non-empty
- [x] 4.9.4 Log file size
- [x] 4.9.5 Log source hash
- [x] 4.9.6 Return raw text string

## 4.10 Build `normalize.py`
- [x] 4.10.1 Write function to normalize line endings
- [x] 4.10.2 Write function to collapse excessive blank lines
- [x] 4.10.3 Preserve chapter markers
- [x] 4.10.4 Preserve paragraph boundaries
- [x] 4.10.5 Save normalized text to `data/normalized/gatsby_locked.txt`
- [x] 4.10.6 Confirm output file exists
- [x] 4.10.7 Confirm output file is readable
- [x] 4.10.8 Confirm chapter headings remain intact

## 4.11 Create first unit tests
- [x] 4.11.1 `test_hashing.py`
  - [x] 4.11.1.1 verify same file always gives same hash
  - [x] 4.11.1.2 verify non-empty hash string
- [x] 4.11.2 `test_normalize.py`
  - [x] 4.11.2.1 verify normalized text is non-empty
  - [x] 4.11.2.2 verify output still contains chapter markers
  - [x] 4.11.2.3 verify output does not contain absurd blank-line sequences

## 4.12 End of Thursday checkpoint
Do not move on until all are true:
- [x] 4.12.1 config loads
- [x] 4.12.2 logger works
- [x] 4.12.3 source file is locked
- [x] 4.12.4 source hash manifest exists
- [x] 4.12.5 normalized text file exists
- [x] 4.12.6 first tests pass

---

# 5. Friday — Passage Index, Extraction, Evidence Ledger, Outline
## 5.1 Build `schemas.py`
Create clear structures.
- [x] 5.1.1 Define `SourceManifest`
- [x] 5.1.2 Define `PassageRecord`
- [x] 5.1.3 Define `MetaphorCandidate`
- [x] 5.1.4 Define `EvidenceRecord`
- [x] 5.1.5 Define `OutlineSection`
- [x] 5.1.6 Define `VerificationReport`
- [x] 5.1.7 Define `FinalManifest`
- [x] 5.1.8 Decide whether to use dataclasses or Pydantic
- [x] 5.1.9 Keep schemas simple and serializable

## 5.2 Build `index_text.py`
- [x] 5.2.1 Load `gatsby_locked.txt`
- [x] 5.2.2 Split text into chapters
- [x] 5.2.3 Split chapters into paragraphs
- [x] 5.2.4 Strip useless whitespace from each paragraph
- [x] 5.2.5 Skip empty paragraphs
- [x] 5.2.6 Assign stable `passage_id` values such as `1.1`, `1.2`, etc.
- [x] 5.2.7 Store chapter number
- [x] 5.2.8 Store paragraph number
- [x] 5.2.9 Store raw text
- [x] 5.2.10 Write output to `artifacts/manifests/passage_index.json`
- [x] 5.2.11 Confirm file exists
- [x] 5.2.12 Inspect first 10 passages manually
- [x] 5.2.13 Inspect a middle passage manually
- [x] 5.2.14 Inspect a late passage manually

## 5.3 Create tests for passage indexing
- [x] 5.3.1 `test_passage_index.py`
  - [x] 5.3.1.1 verify index file is created
  - [x] 5.3.1.2 verify passage IDs are unique
  - [x] 5.3.1.3 verify passage IDs are deterministic across reruns
  - [x] 5.3.1.4 verify every passage has non-empty text
  - [x] 5.3.1.5 verify chapter numbers are valid integers

## 5.4 Build local LLM client helper
- [x] 5.4.1 Create a helper function for chat completion calls
- [x] 5.4.2 Put it in `utils/` or dedicated `llm_client.py`
- [x] 5.4.3 Read model name from config
- [x] 5.4.4 Read endpoint from config
- [x] 5.4.5 Add timeout handling
- [x] 5.4.6 Add retry handling for malformed output
- [x] 5.4.7 Log each call with stage name
- [x] 5.4.8 Log output path for each call
- [x] 5.4.9 Confirm one successful round-trip call

## 5.5 Write extraction prompt
- [x] 5.5.1 Create prompt file or prompt string for metaphor extraction
- [x] 5.5.2 Force JSON output only
- [x] 5.5.3 Ask for candidate metaphor/image/symbol entries
- [x] 5.5.4 Require `candidate_id`
- [x] 5.5.5 Require `label`
- [x] 5.5.6 Require `passage_id`
- [x] 5.5.7 Require exact quote substring
- [x] 5.5.8 Require short rationale
- [x] 5.5.9 Require confidence score
- [x] 5.5.10 Require no essay prose

## 5.6 Build `extract_metaphors.py`
- [x] 5.6.1 Load passage index
- [x] 5.6.2 Decide how many passages to send per call
- [x] 5.6.3 If using full context, still keep outputs structured
- [x] 5.6.4 Call LLM
- [x] 5.6.5 Parse JSON response
- [x] 5.6.6 Validate each candidate has required fields
- [x] 5.6.7 Save to `artifacts/evidence/metaphor_candidates.json`
- [x] 5.6.8 Log candidate count
- [x] 5.6.9 Manually inspect output for obvious garbage

## 5.7 Add extraction fallback logic
- [x] 5.7.1 If JSON parse fails, save raw response to a debug file
- [x] 5.7.2 Retry once with stricter JSON instruction
- [x] 5.7.3 If still failing, stop and inspect
- [x] 5.7.4 Do not silently continue with bad data

## 5.8 Create tests for extraction output shape
- [x] 5.8.1 `test_metaphor_candidates.py`
  - [x] 5.8.1.1 verify output file exists
  - [x] 5.8.1.2 verify candidates are a list
  - [x] 5.8.1.3 verify each candidate has passage_id
  - [x] 5.8.1.4 verify each candidate has quote
  - [x] 5.8.1.5 verify confidence is numeric or convertible

## 5.9 Build `build_evidence_ledger.py`
This is critical.
- [x] 5.9.1 Load candidate file
- [x] 5.9.2 Load passage index
- [x] 5.9.3 For each candidate:
  - [x] 5.9.3.1 confirm passage_id exists
  - [x] 5.9.3.2 confirm quote string exists exactly inside passage text
  - [x] 5.9.3.3 reject candidate if quote does not match
  - [x] 5.9.3.4 reject candidate if rationale is too vague
  - [x] 5.9.3.5 normalize label text
- [x] 5.9.4 Promote good candidates into evidence entries
- [x] 5.9.5 Add `status = verified`
- [x] 5.9.6 Save to `artifacts/evidence/evidence_ledger.json`
- [x] 5.9.7 Save rejected candidates to `artifacts/evidence/rejected_candidates.json`
- [x] 5.9.8 Log promoted count
- [x] 5.9.9 Log rejected count
- [ ] 5.9.10 Allow a tiny explicit manual override path only if extraction misses essential evidence
- [ ] 5.9.11 Log any manual overrides clearly in the ledger or run artifacts
- [ ] 5.9.12 Set a target verified evidence count for the final essay build
- [ ] 5.9.13 Review promoted metaphor records manually for obvious misclassification before freezing the ledger
- [ ] 5.9.14 Use manual overrides only for high-confidence core metaphors the model misses

## 5.10 Create tests for the evidence ledger
- [x] 5.10.1 `test_evidence_ledger.py`
  - [x] 5.10.1.1 verify each evidence record points to valid passage_id
  - [x] 5.10.1.2 verify quote exists exactly in passage text
  - [x] 5.10.1.3 verify status is `verified`
  - [x] 5.10.1.4 verify rejected file is created if rejections exist

## 5.11 Build `plan_outline.py`
- [x] 5.11.1 Load evidence ledger
- [x] 5.11.2 Feed evidence records to LLM
- [x] 5.11.3 Ask for thesis + section plan
- [x] 5.11.4 Force structured JSON output
- [x] 5.11.5 Require section headings
- [x] 5.11.6 Require assigned evidence IDs per section
- [x] 5.11.7 Require intro and conclusion concept
- [x] 5.11.8 Save to `artifacts/drafts/outline.json`
- [x] 5.11.9 Inspect outline manually
- [x] 5.11.10 Confirm section ordering makes sense
- [x] 5.11.11 Confirm no section uses nonexistent evidence IDs

## 5.12 Create tests for outline integrity
- [x] 5.12.1 `test_outline.py`
  - [x] 5.12.1.1 verify outline file exists
  - [x] 5.12.1.2 verify thesis is non-empty
  - [x] 5.12.1.3 verify sections exist
  - [x] 5.12.1.4 verify all referenced evidence IDs exist in ledger

## 5.13 End of Friday checkpoint
Do not move on until all are true:
- [x] 5.13.1 passage index exists
- [x] 5.13.2 LLM client works
- [x] 5.13.3 metaphor candidate file exists
- [x] 5.13.4 evidence ledger exists
- [x] 5.13.5 rejected candidates file exists if needed
- [x] 5.13.6 outline exists
- [x] 5.13.7 all Friday tests pass

---

# 6. Saturday — English Essay, Verification, Editorial Pass
## 6.1 Write drafting prompt
- [x] 6.1.1 Create a section drafting prompt
- [x] 6.1.2 Tell model to write one section at a time
- [x] 6.1.3 Require use of provided evidence only
- [x] 6.1.4 Forbid invented quotes
- [x] 6.1.5 Forbid invented citations
- [x] 6.1.6 Forbid conversational filler
- [x] 6.1.7 Require academic tone
- [x] 6.1.8 Require citation markers to remain intact

## 6.2 Build `draft_english.py`
- [x] 6.2.1 Load outline
- [x] 6.2.2 Load evidence ledger
- [x] 6.2.3 Loop over outline sections one at a time
- [x] 6.2.4 For each section:
  - [x] 6.2.4.1 gather only the section’s evidence IDs
  - [x] 6.2.4.2 build prompt with heading + evidence
  - [x] 6.2.4.3 call LLM
  - [x] 6.2.4.4 save raw section draft to disk
- [x] 6.2.5 Combine all section drafts into one markdown file
- [x] 6.2.6 Save combined file to `artifacts/drafts/analysis_english_draft.md`
- [x] 6.2.7 Confirm headings exist
- [x] 6.2.8 Confirm text is non-empty
- [x] 6.2.9 Confirm citations appear in `[chapter.paragraph]` format
- [x] 6.2.10 Add target word count variable
- [x] 6.2.11 Add estimated page target variable
- [x] 6.2.12 Add words-per-page estimate variable
- [x] 6.2.13 Report actual draft word count
- [x] 6.2.14 Report estimated page count

## 6.3 Lock citation format now
This decision is already made; implement it consistently.
- [x] 6.3.1 Use canonical bracketed chapter.paragraph markers such as `[5.18]` internally
- [x] 6.3.2 Render final report citations explicitly as `[#n, Chapter X, Paragraph Y]`
- [x] 6.3.3 Do not use page numbers
- [x] 6.3.4 Use the same format everywhere
- [x] 6.3.5 Add a final `Citations` appendix and machine-readable citation registry
- [x] 6.3.6 Update drafting and verification logic accordingly

## 6.4 Build `verify_citations.py`
This file is non-negotiable.
- [x] 6.4.1 Load English draft
- [x] 6.4.2 Load evidence ledger
- [x] 6.4.3 Load passage index
- [x] 6.4.4 Extract all quoted strings from the draft
- [x] 6.4.5 Extract all citation markers from the draft
- [x] 6.4.6 For each quote:
  - [x] 6.4.6.1 confirm exact match in source passage or ledger quote
- [x] 6.4.7 For each citation:
  - [x] 6.4.7.1 confirm locator resolves
- [x] 6.4.8 Create a verification report
- [x] 6.4.9 Save report to `artifacts/qa/english_verification_report.json`
- [x] 6.4.10 If verification fails, exit with failure
- [x] 6.4.11 Add zero-tolerance invalid quote rate variable
- [x] 6.4.12 Add zero-tolerance invalid citation rate variable
- [x] 6.4.13 Add advisory unsupported-claim threshold variable
- [x] 6.4.14 Report unsupported-claim estimate for human review

## 6.5 Create tests for quote verification
- [x] 6.5.1 `test_quote_verification.py`
  - [x] 6.5.1.1 verify real quote passes
  - [x] 6.5.1.2 verify fake quote fails
  - [x] 6.5.1.3 verify valid passage ID resolves
  - [x] 6.5.1.4 verify invalid passage ID fails

## 6.6 Build `critique_and_edit.py`
- [x] 6.6.1 Load verified English draft
- [x] 6.6.2 Ask LLM to improve transitions, cohesion, and style
- [x] 6.6.3 Explicitly forbid changing quoted text
- [x] 6.6.4 Explicitly forbid adding new citations
- [x] 6.6.5 Explicitly forbid changing citation markers
- [x] 6.6.6 Save output to `artifacts/drafts/analysis_english_final.md`
- [x] 6.6.7 Compare old and new versions manually
- [x] 6.6.8 Confirm quotes stayed identical
- [x] 6.6.9 Confirm no citations disappeared

## 6.7 Add test or validation for editorial integrity
- [x] 6.7.1 `test_editorial_integrity.py`
  - [x] 6.7.1.1 verify all original citation markers remain in final draft
  - [x] 6.7.1.2 verify all direct quotes remain present
  - [x] 6.7.1.3 verify final file exists and is non-empty

## 6.8 Manual English review pass
Read it like a hiring reviewer, not like a coder.
- [x] 6.8.1 Read thesis
- [x] 6.8.2 Read introduction
- [x] 6.8.3 Check whether it sounds generic
- [x] 6.8.4 Check whether claims feel grounded
- [x] 6.8.5 Check whether transitions are smooth
- [x] 6.8.6 Check whether conclusion actually concludes
- [x] 6.8.7 Check whether metaphor analysis feels serious and not canned
- [x] 6.8.8 Mark any obvious weak sections
- [x] 6.8.9 Fix weak sections now, not later
- [x] 6.8.10 Review whether promoted metaphors are actually defensible readings of the text
- [x] 6.8.11 Reject or correct any metaphor records that feel misclassified

## 6.9 Create a lightweight integration test
- [x] 6.9.1 `test_orchestrator.py`
  - [x] 6.9.1.1 run ingestion on a small sample
  - [x] 6.9.1.2 run normalization
  - [x] 6.9.1.3 run indexing
  - [x] 6.9.1.4 run orchestrated verification and artifact-writing paths
  - [x] 6.9.1.5 assert artifacts are produced

## 6.10 End of Saturday checkpoint
Do not move on until all are true:
- [x] 6.10.1 English draft exists
- [x] 6.10.2 English verification report exists
- [x] 6.10.3 English final file exists
- [x] 6.10.4 quote verification tests pass
- [x] 6.10.5 editorial integrity checks pass
- [x] 6.10.6 smoke test passes
- [x] 6.10.7 English essay is human-reviewed once
- [x] 6.10.8 verified evidence count meets target
- [x] 6.10.9 draft word count is in target range
- [x] 6.10.10 invalid quote rate is zero
- [x] 6.10.11 invalid citation rate is zero
- [x] 6.10.12 metaphor accuracy has one human review pass

---

# 7. Sunday — Translation, QA, PDFs, Manifest, Final Dry Run
Status note: Sunday implementation, live production artifacts, translation cleanup, QA, PDFs, and manifest generation are complete. Remaining open items are optional repo/browser housekeeping only.

## 7.1 Freeze English master
- [x] 7.1.1 Copy or rename final English file as `artifacts/final/analysis_english_master.md`
- [x] 7.1.2 Treat this file as immutable
- [x] 7.1.3 Do not translate from a draft that is still moving

## 7.2 Build translation chunker utility
- [x] 7.2.1 Create helper to split English master by headings
- [x] 7.2.2 If sections are too long, split by paragraph groups
- [x] 7.2.3 Preserve order
- [x] 7.2.4 Preserve heading text
- [x] 7.2.5 Preserve citation markers
- [x] 7.2.6 Preserve quotation boundaries while translating quoted content
- [ ] 7.2.7 Save chunk metadata if helpful

## 7.3 Build `translate_spanish.py`
- [x] 7.3.1 Load English master
- [x] 7.3.2 Split into chunks
- [x] 7.3.3 For each chunk:
  - [x] 7.3.3.1 call LLM
  - [x] 7.3.3.2 preserve heading structure
  - [x] 7.3.3.3 preserve citation markers
  - [x] 7.3.3.4 translate quoted content and preserve quotation boundaries
  - [ ] 7.3.3.5 save raw chunk output if needed
- [x] 7.3.4 Reassemble final Spanish markdown
- [x] 7.3.5 Save to `artifacts/translations/analysis_spanish_draft.md`

## 7.4 Build `translate_mandarin.py`
- [x] 7.4.1 Load English master
- [x] 7.4.2 Split into chunks
- [x] 7.4.3 For each chunk:
  - [x] 7.4.3.1 call LLM
  - [x] 7.4.3.2 require Simplified Chinese
  - [x] 7.4.3.3 preserve heading structure
  - [x] 7.4.3.4 preserve citation markers
  - [x] 7.4.3.5 translate quoted content and preserve quotation boundaries
- [x] 7.4.4 Reassemble final Mandarin markdown
- [x] 7.4.5 Save to `artifacts/translations/analysis_mandarin_draft.md`

## 7.5 Build `bilingual_qa.py`
This can be basic but must exist.
- [x] 7.5.1 Load English master
- [x] 7.5.2 Load Spanish draft
- [x] 7.5.3 Load Mandarin draft
- [x] 7.5.4 Confirm both translation files are non-empty
- [x] 7.5.5 Count headings in English vs Spanish
- [x] 7.5.6 Count headings in English vs Mandarin
- [x] 7.5.7 Count citation markers in each file
- [x] 7.5.8 Count quote markers / quotation boundaries in each file
- [x] 7.5.9 Compare section order in each file
- [x] 7.5.10 Flag mismatches
- [x] 7.5.11 Save `artifacts/qa/spanish_qa_report.json`
- [x] 7.5.12 Save `artifacts/qa/mandarin_qa_report.json`

## 7.6 Create tests for translation integrity
- [x] 7.6.1 `test_translation_integrity.py`
  - [ ] 7.6.1.1 verify heading counts match
  - [x] 7.6.1.2 verify section order matches English
  - [x] 7.6.1.3 verify citation markers survive
  - [x] 7.6.1.4 verify quote-marker counts survive
  - [x] 7.6.1.5 verify translation files are non-empty

## 7.7 Manual translation spot checks
You do not need to be perfect in both languages, but you must do spot checks.
- [x] 7.7.1 Check title in Spanish for professionalism
- [x] 7.7.2 Check title in Mandarin for correct rendering
- [x] 7.7.3 Check one middle paragraph in Spanish
- [x] 7.7.4 Check one conclusion paragraph in Spanish
- [x] 7.7.5 Check one middle paragraph in Mandarin
- [x] 7.7.6 Check one conclusion paragraph in Mandarin
- [x] 7.7.7 Confirm quotations are translated and citation markers stayed intact
- [x] 7.7.8 Confirm weird garbage characters are absent

## 7.8 Build `pdf_compiler.py`
- [x] 7.8.1 Load English markdown/text
- [x] 7.8.2 Load Spanish markdown/text
- [x] 7.8.3 Load Mandarin markdown/text
- [x] 7.8.4 Configure page size
- [x] 7.8.5 Configure margins
- [x] 7.8.6 Keep layout plain and professional
- [x] 7.8.7 Configure default font for English/Spanish
- [x] 7.8.8 Configure CJK-capable font for Mandarin
- [x] 7.8.9 Add page numbers
- [x] 7.8.10 Render English PDF
- [x] 7.8.11 Render Spanish PDF
- [x] 7.8.12 Render Mandarin PDF
- [x] 7.8.13 Save all three files in `outputs/`

## 7.9 Add PDF tests
- [x] 7.9.1 `test_pdf_unicode.py`
  - [x] 7.9.1.1 verify PDF files are created
  - [x] 7.9.1.2 verify file size > 0
  - [x] 7.9.1.3 verify Mandarin PDF renders without Unicode exception

## 7.10 Build `manifest_writer.py`
- [x] 7.10.1 Collect source hash
- [x] 7.10.2 Collect model name
- [x] 7.10.3 Collect config path
- [x] 7.10.4 Collect generated artifact paths
- [x] 7.10.5 Collect QA report paths
- [x] 7.10.6 Collect timestamp
- [x] 7.10.7 Save to `outputs/final_manifest.json`

## 7.11 Wire everything into `orchestrator.py`
- [x] 7.11.1 Add stage registry
- [x] 7.11.2 Add command-line argument parsing
- [x] 7.11.3 Add `--run all`
- [x] 7.11.4 Add `--run <stage>`
- [x] 7.11.5 Add stage-level logging
- [x] 7.11.6 Add clean failure messages
- [x] 7.11.7 Add exit code non-zero on stage failure

## 7.12 Do a full dry run
- [x] 7.12.1 Delete or refresh stale intermediate files if necessary
- [x] 7.12.2 Run pipeline end-to-end
- [x] 7.12.3 Watch console logs
- [x] 7.12.4 Note first point of failure if any
- [x] 7.12.5 Fix failure
- [x] 7.12.6 Rerun
- [x] 7.12.7 Do not stop until full run completes once cleanly

## 7.13 Run full test suite
- [x] 7.13.1 Run `pytest`
- [x] 7.13.2 Read failures carefully
- [x] 7.13.3 Fix failing tests
- [x] 7.13.4 Re-run `pytest`
- [x] 7.13.5 Repeat until tests pass cleanly

## 7.14 Do final human QA on outputs
- [x] 7.14.1 Open English PDF
- [x] 7.14.2 Open Spanish PDF
- [x] 7.14.3 Open Mandarin PDF
- [x] 7.14.4 Confirm each file opens
- [x] 7.14.5 Confirm title page or opening section looks clean
- [x] 7.14.6 Confirm no broken characters
- [x] 7.14.7 Confirm page breaks are reasonable
- [x] 7.14.8 Confirm file names are professional

## 7.15 Final repo cleanup
- [x] 7.15.1 Remove junk scratch files
- [x] 7.15.2 Remove debug outputs you do not want visible
- [x] 7.15.3 Keep useful logs and artifacts
- [x] 7.15.4 Confirm README matches actual implementation
- [x] 7.15.5 Confirm commands in README really work
- [x] 7.15.6 Confirm file tree in README matches repo
- [x] 7.15.7 Confirm no hard-coded machine-specific paths remain

## 7.16 Final Git tasks
- [x] 7.16.1 `git status`
- [x] 7.16.2 Inspect all changed files
- [x] 7.16.3 Make final commit with a clean message
- [x] 7.16.4 Push repo
- [ ] 7.16.5 Open repo in browser
- [x] 7.16.6 Confirm important files are present
- [x] 7.16.7 Confirm README renders correctly

## 7.17 End of Sunday checkpoint
Do not stop until all are true:
- [x] 7.17.1 Spanish draft exists
- [x] 7.17.2 Mandarin draft exists
- [x] 7.17.3 Spanish QA report exists
- [x] 7.17.4 Mandarin QA report exists
- [x] 7.17.5 three PDFs exist
- [x] 7.17.6 final manifest exists
- [x] 7.17.7 end-to-end run completed once
- [x] 7.17.8 tests pass
- [x] 7.17.9 repo is pushed and presentable

---

# 8. Detailed File-by-File Build Checklist
## 8.1 `src/agent_gatsby/orchestrator.py`
- [x] 8.1.1 load config
- [x] 8.1.2 initialize logger
- [x] 8.1.3 parse CLI args
- [x] 8.1.4 map stage names to functions
- [x] 8.1.5 support `all`
- [x] 8.1.6 support single-stage runs
- [x] 8.1.7 handle exceptions cleanly
- [x] 8.1.8 log start and finish for each stage

## 8.2 `src/agent_gatsby/data_ingest.py`
- [x] 8.2.1 read local source file
- [x] 8.2.2 validate existence
- [x] 8.2.3 validate encoding
- [x] 8.2.4 validate non-empty contents
- [x] 8.2.5 compute file hash
- [x] 8.2.6 return raw text

## 8.3 `src/agent_gatsby/normalize.py`
- [x] 8.3.1 normalize whitespace
- [x] 8.3.2 normalize line endings
- [x] 8.3.3 preserve structure
- [x] 8.3.4 write locked normalized file

## 8.4 `src/agent_gatsby/index_text.py`
- [x] 8.4.1 split chapters
- [x] 8.4.2 split paragraphs
- [x] 8.4.3 assign IDs
- [x] 8.4.4 serialize JSON
- [x] 8.4.5 write passage index

## 8.5 `src/agent_gatsby/extract_metaphors.py`
- [x] 8.5.1 load index
- [x] 8.5.2 build prompt
- [x] 8.5.3 call model
- [x] 8.5.4 parse JSON
- [x] 8.5.5 validate fields
- [x] 8.5.6 save candidate file
- [x] 8.5.7 save raw response on failure

## 8.6 `src/agent_gatsby/build_evidence_ledger.py`
- [x] 8.6.1 load candidates
- [x] 8.6.2 exact-match quotes
- [x] 8.6.3 validate locators
- [x] 8.6.4 promote valid entries
- [x] 8.6.5 save verified ledger
- [x] 8.6.6 save rejected list

## 8.7 `src/agent_gatsby/plan_outline.py`
- [x] 8.7.1 load ledger
- [x] 8.7.2 build thesis prompt
- [x] 8.7.3 parse structured output
- [x] 8.7.4 save outline JSON

## 8.8 `src/agent_gatsby/draft_english.py`
- [x] 8.8.1 load outline
- [x] 8.8.2 load ledger
- [x] 8.8.3 draft section by section
- [x] 8.8.4 combine sections
- [x] 8.8.5 save markdown file

## 8.9 `src/agent_gatsby/verify_citations.py`
- [x] 8.9.1 extract quotes
- [x] 8.9.2 extract citation markers
- [x] 8.9.3 validate quotes
- [x] 8.9.4 validate locators
- [x] 8.9.5 write QA report

## 8.10 `src/agent_gatsby/critique_and_edit.py`
- [ ] 8.10.1 improve prose only
- [x] 8.10.2 preserve quotes
- [x] 8.10.3 preserve citations
- [x] 8.10.4 write final English file

## 8.11 `src/agent_gatsby/translate_spanish.py`
- [x] 8.11.1 chunk English master
- [x] 8.11.2 translate each chunk
- [x] 8.11.3 reassemble file
- [x] 8.11.4 save markdown

## 8.12 `src/agent_gatsby/translate_mandarin.py`
- [x] 8.12.1 chunk English master
- [x] 8.12.2 translate each chunk
- [x] 8.12.3 force Simplified Chinese
- [x] 8.12.4 reassemble file
- [x] 8.12.5 save markdown

## 8.13 `src/agent_gatsby/bilingual_qa.py`
- [x] 8.13.1 compare heading counts
- [x] 8.13.2 compare citation counts
- [x] 8.13.3 compare quote markers
- [x] 8.13.4 write reports

## 8.14 `src/agent_gatsby/pdf_compiler.py`
- [x] 8.14.1 load text files
- [x] 8.14.2 set fonts
- [x] 8.14.3 render pages
- [x] 8.14.4 save PDFs
- [x] 8.14.5 catch Unicode errors

## 8.15 `src/agent_gatsby/manifest_writer.py`
- [x] 8.15.1 gather hashes
- [x] 8.15.2 gather outputs
- [x] 8.15.3 gather model info
- [x] 8.15.4 write manifest JSON

---

# 9. Debugging Checklist
Use this when something breaks.

## 9.1 If the local model call fails
- [ ] 9.1.1 confirm `ollama serve` is running
- [ ] 9.1.2 confirm model is pulled
- [ ] 9.1.3 confirm endpoint URL matches config
- [ ] 9.1.4 run a tiny manual test prompt
- [ ] 9.1.5 inspect logs
- [ ] 9.1.6 reduce prompt size if necessary
- [ ] 9.1.7 save raw failure output

## 9.2 If JSON parsing fails
- [ ] 9.2.1 inspect raw model response
- [ ] 9.2.2 add stricter JSON-only instructions
- [ ] 9.2.3 ask model for array/object only
- [ ] 9.2.4 strip code fences before parsing if necessary
- [ ] 9.2.5 retry once
- [ ] 9.2.6 if still failing, simplify the schema

## 9.3 If quote verification fails
- [ ] 9.3.1 print failing quote
- [ ] 9.3.2 print referenced passage text
- [ ] 9.3.3 check punctuation mismatch
- [ ] 9.3.4 check whitespace normalization mismatch
- [ ] 9.3.5 check curly quotes vs straight quotes
- [ ] 9.3.6 decide whether verifier should normalize quotes before matching

## 9.4 If translations lose citations
- [ ] 9.4.1 verify chunk boundaries
- [ ] 9.4.2 explicitly instruct model not to alter citation markers
- [ ] 9.4.3 compare citation counts before and after
- [ ] 9.4.4 rerun only broken chunks

## 9.5 If Mandarin PDF breaks
- [ ] 9.5.1 confirm font file exists
- [ ] 9.5.2 confirm font supports CJK
- [ ] 9.5.3 confirm font registration code is correct
- [ ] 9.5.4 test a one-line Mandarin string first
- [ ] 9.5.5 then test full document

## 9.6 If end-to-end run is messy
- [ ] 9.6.1 delete stale intermediate files
- [ ] 9.6.2 rerun from earliest failing stage
- [ ] 9.6.3 confirm config values
- [ ] 9.6.4 confirm directory paths
- [ ] 9.6.5 confirm all expected artifacts are being written

---

# 10. Execution Discipline Notes
These record the operating rules and checkpoint cadence used during the weekend build.

## 10.1 Core rules
- [x] 10.1.1 Work only from this checklist.
- [x] 10.1.2 Do not redesign the system midstream unless something is clearly broken.
- [x] 10.1.3 Do not start polishing the repo visuals before the pipeline works.
- [x] 10.1.4 Do not chase optional features before tests pass.
- [x] 10.1.5 After finishing each section, physically check the box.
- [x] 10.1.6 After each major milestone, run the relevant test.
- [x] 10.1.7 After each major milestone, commit the code.

## 10.2 Mandatory commit points
- [x] 10.2.1 after Thursday foundation
- [x] 10.2.2 after Friday evidence ledger + outline
- [x] 10.2.3 after Saturday English pipeline
- [x] 10.2.4 after Sunday translations + PDFs + tests
- [x] 10.2.5 after final cleanup

---

# 11. Final Submission Prep Checklist
Before you submit your application materials:

- [x] 11.1 confirm repo link works
- [x] 11.2 confirm README is current
- [x] 11.3 confirm repo shows actual code, not just architecture
- [x] 11.4 confirm final PDFs open correctly
- [x] 11.5 confirm file names are clean and professional
- [x] 11.6 confirm there are no embarrassing debug prints in visible files
- [x] 11.7 confirm tests exist in repo
- [ ] 11.8 confirm logs do not expose anything unnecessary
- [x] 11.9 confirm the project clearly demonstrates implementation discipline
- [x] 11.10 confirm the output package is ready for upload

---

# 12. Absolute Final Checklist
You are done only when every box below is checked:

- [x] 12.1 source locked
- [x] 12.2 normalized text saved
- [x] 12.3 passage index saved
- [x] 12.4 candidate metaphors saved
- [x] 12.5 evidence ledger saved
- [x] 12.6 outline saved
- [x] 12.7 English draft saved
- [x] 12.8 English verification passed
- [x] 12.9 English final saved
- [x] 12.10 Spanish draft saved
- [x] 12.11 Mandarin draft saved
- [x] 12.12 translation QA reports saved
- [x] 12.13 English PDF saved
- [x] 12.14 Spanish PDF saved
- [x] 12.15 Mandarin PDF saved
- [x] 12.16 final manifest saved
- [x] 12.17 tests pass
- [x] 12.18 end-to-end pipeline works
- [x] 12.19 repo pushed
- [x] 12.20 submission artifacts ready
