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

---

# 0. Ground Rules for the Weekend
- [ ] Do **not** start by chasing perfection.
- [ ] Do **not** start by polishing the README again.
- [ ] Do **not** start by designing advanced future features.
- [ ] Build the **smallest working pipeline first**, then harden it.
- [ ] At every stage, make sure there is a file on disk that proves the stage worked.
- [ ] At every stage, add at least one test or one validation check.
- [ ] If a stage fails, fix the stage before moving on.
- [ ] Always keep the pipeline runnable from the command line.
- [ ] Commit after each major milestone.

---

# 1. Definition of Done
The project is considered done only if all of the following are true:

- [ ] Repo has a clean structure.
- [ ] README reflects the final architecture.
- [ ] Config file exists and is used by code.
- [ ] Source text is locked and hashed.
- [ ] Passage indexing works.
- [ ] Candidate metaphor extraction works.
- [ ] Evidence ledger file is produced.
- [ ] English outline is produced.
- [ ] English draft is produced.
- [ ] English quote/citation verification runs.
- [ ] English final master is produced.
- [ ] Spanish translation file is produced.
- [ ] Mandarin translation file is produced.
- [ ] QA checks for translations run.
- [ ] Three PDFs are successfully rendered.
- [ ] Unit tests run cleanly.
- [ ] At least one lightweight end-to-end test runs.
- [ ] Logs are written to disk.
- [ ] Final manifest is written.
- [ ] The repo can be demonstrated by running a clear command sequence.

---

# 2. Minimum Viable Scope
This is the version you must finish first before adding anything fancy.

## Required MVP components
- [ ] `config/config.yaml`
- [ ] `src/agent_gatsby/orchestrator.py`
- [ ] `src/agent_gatsby/data_ingest.py`
- [ ] `src/agent_gatsby/normalize.py`
- [ ] `src/agent_gatsby/index_text.py`
- [ ] `src/agent_gatsby/extract_metaphors.py`
- [ ] `src/agent_gatsby/build_evidence_ledger.py`
- [ ] `src/agent_gatsby/plan_outline.py`
- [ ] `src/agent_gatsby/draft_english.py`
- [ ] `src/agent_gatsby/verify_citations.py`
- [ ] `src/agent_gatsby/critique_and_edit.py`
- [ ] `src/agent_gatsby/translate_spanish.py`
- [ ] `src/agent_gatsby/translate_mandarin.py`
- [ ] `src/agent_gatsby/bilingual_qa.py`
- [ ] `src/agent_gatsby/pdf_compiler.py`
- [ ] `src/agent_gatsby/manifest_writer.py`
- [ ] `tests/`
- [ ] `requirements.txt`
- [ ] `README.md`

## Explicitly postpone until MVP works
- [ ] Embeddings
- [ ] Semantic retrieval
- [ ] Multi-model routing
- [ ] Docker
- [ ] CI/CD
- [ ] Web UI
- [ ] Fancy observability dashboards
- [ ] Parallel execution
- [ ] Advanced retry schedulers

---

# 3. Weekend Schedule Overview
## Thursday Night
Focus: repo scaffold + config + source lock + ingestion + normalization

## Friday
Focus: indexing + candidate extraction + evidence ledger + outline

## Saturday
Focus: English drafting + verification + editorial pass + tests

## Sunday
Focus: translations + translation QA + PDFs + manifest + full dry run + final cleanup

---

# 4. Thursday Night — Setup and Foundation
## 4.1 Create the repo structure
- [ ] Open the repository root.
- [ ] Create `config/`
- [ ] Create `data/source/`
- [ ] Create `data/normalized/`
- [ ] Create `artifacts/manifests/`
- [ ] Create `artifacts/evidence/`
- [ ] Create `artifacts/drafts/`
- [ ] Create `artifacts/translations/`
- [ ] Create `artifacts/qa/`
- [ ] Create `artifacts/logs/`
- [ ] Create `outputs/`
- [ ] Create `fonts/`
- [ ] Create `src/agent_gatsby/`
- [ ] Create `src/agent_gatsby/utils/`
- [ ] Create `tests/`

## 4.2 Create base files
- [ ] Create `README.md`
- [ ] Create `requirements.txt`
- [ ] Create `pyproject.toml` if you want packaging consistency
- [ ] Create `config/config.yaml`
- [ ] Create `src/agent_gatsby/__init__.py`
- [ ] Create `src/agent_gatsby/schemas.py`
- [ ] Create `src/agent_gatsby/config.py`
- [ ] Create `src/agent_gatsby/orchestrator.py`

## 4.3 Install and verify local environment
- [ ] Activate your environment.
- [ ] Install base dependencies.
- [ ] Verify Python version.
- [ ] Verify `ollama` is installed.
- [ ] Verify `ollama serve` starts.
- [ ] Pull the model you plan to use.
- [ ] Run a trivial test prompt against the local endpoint.
- [ ] Save the exact working command you used.

## 4.4 Build `requirements.txt`
Include only what you actually need.
- [ ] Add `pyyaml`
- [ ] Add `requests`
- [ ] Add `fpdf2`
- [ ] Add `pytest`
- [ ] Add `pydantic` if you want schema validation
- [ ] Add `openai` only if using Ollama’s OpenAI-compatible endpoint
- [ ] Add anything else only if truly necessary

## 4.5 Build `config/config.yaml`
- [ ] Add output directory paths
- [ ] Add artifact directory paths
- [ ] Add model endpoint
- [ ] Add model name
- [ ] Add drafting temperature
- [ ] Add translation settings
- [ ] Add PDF settings
- [ ] Add log level
- [ ] Add source file path
- [ ] Add final output file names

## 4.6 Build `config.py`
- [ ] Write code to load YAML config
- [ ] Validate required keys exist
- [ ] Return config object
- [ ] Add clean error if config file missing
- [ ] Add clean error if required key missing

## 4.7 Build logging utility
- [ ] Create `logging_utils.py`
- [ ] Add file logger
- [ ] Add console logger
- [ ] Make logs go to `artifacts/logs/pipeline.log`
- [ ] Confirm a log message writes successfully

## 4.8 Lock the source text
Decide now: use a local source file as canonical.
- [ ] Place source text in `data/source/gatsby_source.txt`
- [ ] Open file and visually inspect beginning and end
- [ ] Confirm encoding is UTF-8
- [ ] Create `hashing.py`
- [ ] Write a SHA-256 hash function
- [ ] Hash the raw source file
- [ ] Save the hash to `artifacts/manifests/source_manifest.json`

## 4.9 Build `data_ingest.py`
- [ ] Load source text from local file
- [ ] Validate file exists
- [ ] Validate text is non-empty
- [ ] Log file size
- [ ] Log source hash
- [ ] Return raw text string

## 4.10 Build `normalize.py`
- [ ] Write function to normalize line endings
- [ ] Write function to collapse excessive blank lines
- [ ] Preserve chapter markers
- [ ] Preserve paragraph boundaries
- [ ] Save normalized text to `data/normalized/gatsby_locked.txt`
- [ ] Confirm output file exists
- [ ] Confirm output file is readable
- [ ] Confirm chapter headings remain intact

## 4.11 Create first unit tests
- [ ] `test_hashing.py`
  - [ ] verify same file always gives same hash
  - [ ] verify non-empty hash string
- [ ] `test_normalize.py`
  - [ ] verify normalized text is non-empty
  - [ ] verify output still contains chapter markers
  - [ ] verify output does not contain absurd blank-line sequences

## 4.12 End of Thursday checkpoint
Do not move on until all are true:
- [ ] config loads
- [ ] logger works
- [ ] source file is locked
- [ ] source hash manifest exists
- [ ] normalized text file exists
- [ ] first tests pass

---

# 5. Friday — Passage Index, Extraction, Evidence Ledger, Outline
## 5.1 Build `schemas.py`
Create clear structures.
- [ ] Define `SourceManifest`
- [ ] Define `PassageRecord`
- [ ] Define `MetaphorCandidate`
- [ ] Define `EvidenceRecord`
- [ ] Define `OutlineSection`
- [ ] Define `VerificationReport`
- [ ] Define `FinalManifest`
- [ ] Decide whether to use dataclasses or Pydantic
- [ ] Keep schemas simple and serializable

## 5.2 Build `index_text.py`
- [ ] Load `gatsby_locked.txt`
- [ ] Split text into chapters
- [ ] Split chapters into paragraphs
- [ ] Strip useless whitespace from each paragraph
- [ ] Skip empty paragraphs
- [ ] Assign stable `passage_id` values such as `1.1`, `1.2`, etc.
- [ ] Store chapter number
- [ ] Store paragraph number
- [ ] Store raw text
- [ ] Write output to `artifacts/manifests/passage_index.json`
- [ ] Confirm file exists
- [ ] Inspect first 10 passages manually
- [ ] Inspect a middle passage manually
- [ ] Inspect a late passage manually

## 5.3 Create tests for passage indexing
- [ ] `test_passage_index.py`
  - [ ] verify index file is created
  - [ ] verify passage IDs are unique
  - [ ] verify passage IDs are deterministic across reruns
  - [ ] verify every passage has non-empty text
  - [ ] verify chapter numbers are valid integers

## 5.4 Build local LLM client helper
- [ ] Create a helper function for chat completion calls
- [ ] Put it in `utils/` or dedicated `llm_client.py`
- [ ] Read model name from config
- [ ] Read endpoint from config
- [ ] Add timeout handling
- [ ] Add retry handling for malformed output
- [ ] Log each call with stage name
- [ ] Log output path for each call
- [ ] Confirm one successful round-trip call

## 5.5 Write extraction prompt
- [ ] Create prompt file or prompt string for metaphor extraction
- [ ] Force JSON output only
- [ ] Ask for candidate metaphor/image/symbol entries
- [ ] Require `candidate_id`
- [ ] Require `label`
- [ ] Require `passage_id`
- [ ] Require exact quote substring
- [ ] Require short rationale
- [ ] Require confidence score
- [ ] Require no essay prose

## 5.6 Build `extract_metaphors.py`
- [ ] Load passage index
- [ ] Decide how many passages to send per call
- [ ] If using full context, still keep outputs structured
- [ ] Call LLM
- [ ] Parse JSON response
- [ ] Validate each candidate has required fields
- [ ] Save to `artifacts/evidence/metaphor_candidates.json`
- [ ] Log candidate count
- [ ] Manually inspect output for obvious garbage

## 5.7 Add extraction fallback logic
- [ ] If JSON parse fails, save raw response to a debug file
- [ ] Retry once with stricter JSON instruction
- [ ] If still failing, stop and inspect
- [ ] Do not silently continue with bad data

## 5.8 Create tests for extraction output shape
- [ ] `test_metaphor_candidates.py`
  - [ ] verify output file exists
  - [ ] verify candidates are a list
  - [ ] verify each candidate has passage_id
  - [ ] verify each candidate has quote
  - [ ] verify confidence is numeric or convertible

## 5.9 Build `build_evidence_ledger.py`
This is critical.
- [ ] Load candidate file
- [ ] Load passage index
- [ ] For each candidate:
  - [ ] confirm passage_id exists
  - [ ] confirm quote string exists exactly inside passage text
  - [ ] reject candidate if quote does not match
  - [ ] reject candidate if rationale is too vague
  - [ ] normalize label text
- [ ] Promote good candidates into evidence entries
- [ ] Add `status = verified`
- [ ] Save to `artifacts/evidence/evidence_ledger.json`
- [ ] Save rejected candidates to `artifacts/evidence/rejected_candidates.json`
- [ ] Log promoted count
- [ ] Log rejected count

## 5.10 Create tests for the evidence ledger
- [ ] `test_evidence_ledger.py`
  - [ ] verify each evidence record points to valid passage_id
  - [ ] verify quote exists exactly in passage text
  - [ ] verify status is `verified`
  - [ ] verify rejected file is created if rejections exist

## 5.11 Build `plan_outline.py`
- [ ] Load evidence ledger
- [ ] Feed evidence records to LLM
- [ ] Ask for thesis + section plan
- [ ] Force structured JSON output
- [ ] Require section headings
- [ ] Require assigned evidence IDs per section
- [ ] Require intro and conclusion concept
- [ ] Save to `artifacts/drafts/outline.json`
- [ ] Inspect outline manually
- [ ] Confirm section ordering makes sense
- [ ] Confirm no section uses nonexistent evidence IDs

## 5.12 Create tests for outline integrity
- [ ] `test_outline.py`
  - [ ] verify outline file exists
  - [ ] verify thesis is non-empty
  - [ ] verify sections exist
  - [ ] verify all referenced evidence IDs exist in ledger

## 5.13 End of Friday checkpoint
Do not move on until all are true:
- [ ] passage index exists
- [ ] LLM client works
- [ ] metaphor candidate file exists
- [ ] evidence ledger exists
- [ ] rejected candidates file exists if needed
- [ ] outline exists
- [ ] all Friday tests pass

---

# 6. Saturday — English Essay, Verification, Editorial Pass
## 6.1 Write drafting prompt
- [ ] Create a section drafting prompt
- [ ] Tell model to write one section at a time
- [ ] Require use of provided evidence only
- [ ] Forbid invented quotes
- [ ] Forbid invented citations
- [ ] Forbid conversational filler
- [ ] Require academic tone
- [ ] Require citation markers to remain intact

## 6.2 Build `draft_english.py`
- [ ] Load outline
- [ ] Load evidence ledger
- [ ] Loop over outline sections one at a time
- [ ] For each section:
  - [ ] gather only the section’s evidence IDs
  - [ ] build prompt with heading + evidence
  - [ ] call LLM
  - [ ] save raw section draft to disk
- [ ] Combine all section drafts into one markdown file
- [ ] Save combined file to `artifacts/drafts/analysis_english_draft.md`
- [ ] Confirm headings exist
- [ ] Confirm text is non-empty
- [ ] Confirm citations appear in a consistent format

## 6.3 Decide citation format now
Pick one and use it consistently.
- [ ] Choose passage ID format such as `(Passage 5.18)`
- [ ] Or choose chapter/paragraph format
- [ ] Or choose a simple in-house textual locator
- [ ] Use the same format everywhere
- [ ] Update drafting and verification logic accordingly

## 6.4 Build `verify_citations.py`
This file is non-negotiable.
- [ ] Load English draft
- [ ] Load evidence ledger
- [ ] Load passage index
- [ ] Extract all quoted strings from the draft
- [ ] Extract all citation markers from the draft
- [ ] For each quote:
  - [ ] confirm exact match in source passage or ledger quote
- [ ] For each citation:
  - [ ] confirm locator resolves
- [ ] Create a verification report
- [ ] Save report to `artifacts/qa/english_verification_report.json`
- [ ] If verification fails, exit with failure

## 6.5 Create tests for quote verification
- [ ] `test_quote_verification.py`
  - [ ] verify real quote passes
  - [ ] verify fake quote fails
  - [ ] verify valid passage ID resolves
  - [ ] verify invalid passage ID fails

## 6.6 Build `critique_and_edit.py`
- [ ] Load verified English draft
- [ ] Ask LLM to improve transitions, cohesion, and style
- [ ] Explicitly forbid changing quoted text
- [ ] Explicitly forbid adding new citations
- [ ] Explicitly forbid changing citation markers
- [ ] Save output to `artifacts/drafts/analysis_english_final.md`
- [ ] Compare old and new versions manually
- [ ] Confirm quotes stayed identical
- [ ] Confirm no citations disappeared

## 6.7 Add test or validation for editorial integrity
- [ ] `test_editorial_integrity.py`
  - [ ] verify all original citation markers remain in final draft
  - [ ] verify all direct quotes remain present
  - [ ] verify final file exists and is non-empty

## 6.8 Manual English review pass
Read it like a hiring reviewer, not like a coder.
- [ ] Read thesis
- [ ] Read introduction
- [ ] Check whether it sounds generic
- [ ] Check whether claims feel grounded
- [ ] Check whether transitions are smooth
- [ ] Check whether conclusion actually concludes
- [ ] Check whether metaphor analysis feels serious and not canned
- [ ] Mark any obvious weak sections
- [ ] Fix weak sections now, not later

## 6.9 Create a lightweight integration test
- [ ] `test_pipeline_smoke.py`
  - [ ] run ingestion on a small sample
  - [ ] run normalization
  - [ ] run indexing
  - [ ] run verification functions
  - [ ] assert artifacts are produced

## 6.10 End of Saturday checkpoint
Do not move on until all are true:
- [ ] English draft exists
- [ ] English verification report exists
- [ ] English final file exists
- [ ] quote verification tests pass
- [ ] editorial integrity checks pass
- [ ] smoke test passes
- [ ] English essay is human-reviewed once

---

# 7. Sunday — Translation, QA, PDFs, Manifest, Final Dry Run
## 7.1 Freeze English master
- [ ] Copy or rename final English file as `artifacts/final/analysis_english_master.md`
- [ ] Treat this file as immutable
- [ ] Do not translate from a draft that is still moving

## 7.2 Build translation chunker utility
- [ ] Create helper to split English master by headings
- [ ] If sections are too long, split by paragraph groups
- [ ] Preserve order
- [ ] Preserve heading text
- [ ] Preserve citation markers
- [ ] Preserve quotes
- [ ] Save chunk metadata if helpful

## 7.3 Build `translate_spanish.py`
- [ ] Load English master
- [ ] Split into chunks
- [ ] For each chunk:
  - [ ] call LLM
  - [ ] preserve heading structure
  - [ ] preserve citation markers
  - [ ] preserve quote formatting
  - [ ] save raw chunk output if needed
- [ ] Reassemble final Spanish markdown
- [ ] Save to `artifacts/translations/analysis_spanish_draft.md`

## 7.4 Build `translate_mandarin.py`
- [ ] Load English master
- [ ] Split into chunks
- [ ] For each chunk:
  - [ ] call LLM
  - [ ] require Simplified Chinese
  - [ ] preserve heading structure
  - [ ] preserve citation markers
  - [ ] preserve quote formatting
- [ ] Reassemble final Mandarin markdown
- [ ] Save to `artifacts/translations/analysis_mandarin_draft.md`

## 7.5 Build `bilingual_qa.py`
This can be basic but must exist.
- [ ] Load English master
- [ ] Load Spanish draft
- [ ] Load Mandarin draft
- [ ] Count headings in English vs Spanish
- [ ] Count headings in English vs Mandarin
- [ ] Count citation markers in each file
- [ ] Count quote markers in each file
- [ ] Flag mismatches
- [ ] Save `artifacts/qa/spanish_qa_report.json`
- [ ] Save `artifacts/qa/mandarin_qa_report.json`

## 7.6 Create tests for translation integrity
- [ ] `test_translation_integrity.py`
  - [ ] verify heading counts match
  - [ ] verify citation markers survive
  - [ ] verify translation files exist
  - [ ] verify translation files are non-empty

## 7.7 Manual translation spot checks
You do not need to be perfect in both languages, but you must do spot checks.
- [ ] Check title in Spanish for professionalism
- [ ] Check title in Mandarin for correct rendering
- [ ] Check one middle paragraph in Spanish
- [ ] Check one conclusion paragraph in Spanish
- [ ] Check one middle paragraph in Mandarin
- [ ] Check one conclusion paragraph in Mandarin
- [ ] Confirm citations stayed intact
- [ ] Confirm weird garbage characters are absent

## 7.8 Build `pdf_compiler.py`
- [ ] Load English markdown/text
- [ ] Load Spanish markdown/text
- [ ] Load Mandarin markdown/text
- [ ] Configure page size
- [ ] Configure margins
- [ ] Configure default font for English/Spanish
- [ ] Configure CJK-capable font for Mandarin
- [ ] Render English PDF
- [ ] Render Spanish PDF
- [ ] Render Mandarin PDF
- [ ] Save all three files in `outputs/`

## 7.9 Add PDF tests
- [ ] `test_pdf_unicode.py`
  - [ ] verify PDF files are created
  - [ ] verify file size > 0
  - [ ] verify Mandarin PDF renders without Unicode exception

## 7.10 Build `manifest_writer.py`
- [ ] Collect source hash
- [ ] Collect model name
- [ ] Collect config path
- [ ] Collect generated artifact paths
- [ ] Collect QA report paths
- [ ] Collect timestamp
- [ ] Save to `outputs/final_manifest.json`

## 7.11 Wire everything into `orchestrator.py`
- [ ] Add stage registry
- [ ] Add command-line argument parsing
- [ ] Add `--run all`
- [ ] Add `--run <stage>`
- [ ] Add stage-level logging
- [ ] Add clean failure messages
- [ ] Add exit code non-zero on stage failure

## 7.12 Do a full dry run
- [ ] Delete stale intermediate files if necessary
- [ ] Run pipeline end-to-end
- [ ] Watch console logs
- [ ] Note first point of failure if any
- [ ] Fix failure
- [ ] Rerun
- [ ] Do not stop until full run completes once cleanly

## 7.13 Run full test suite
- [ ] Run `pytest`
- [ ] Read failures carefully
- [ ] Fix failing tests
- [ ] Re-run `pytest`
- [ ] Repeat until tests pass cleanly

## 7.14 Do final human QA on outputs
- [ ] Open English PDF
- [ ] Open Spanish PDF
- [ ] Open Mandarin PDF
- [ ] Confirm each file opens
- [ ] Confirm title page or opening section looks clean
- [ ] Confirm no broken characters
- [ ] Confirm page breaks are reasonable
- [ ] Confirm file names are professional

## 7.15 Final repo cleanup
- [ ] Remove junk scratch files
- [ ] Remove debug outputs you do not want visible
- [ ] Keep useful logs and artifacts
- [ ] Confirm README matches actual implementation
- [ ] Confirm commands in README really work
- [ ] Confirm file tree in README matches repo
- [ ] Confirm no hard-coded machine-specific paths remain

## 7.16 Final Git tasks
- [ ] `git status`
- [ ] Inspect all changed files
- [ ] Make final commit with a clean message
- [ ] Push repo
- [ ] Open repo in browser
- [ ] Confirm important files are present
- [ ] Confirm README renders correctly

## 7.17 End of Sunday checkpoint
Do not stop until all are true:
- [ ] Spanish draft exists
- [ ] Mandarin draft exists
- [ ] Spanish QA report exists
- [ ] Mandarin QA report exists
- [ ] three PDFs exist
- [ ] final manifest exists
- [ ] end-to-end run completed once
- [ ] tests pass
- [ ] repo is pushed and presentable

---

# 8. Detailed File-by-File Build Checklist
## 8.1 `src/agent_gatsby/orchestrator.py`
- [ ] load config
- [ ] initialize logger
- [ ] parse CLI args
- [ ] map stage names to functions
- [ ] support `all`
- [ ] support single-stage runs
- [ ] handle exceptions cleanly
- [ ] log start and finish for each stage

## 8.2 `src/agent_gatsby/data_ingest.py`
- [ ] read local source file
- [ ] validate existence
- [ ] validate encoding
- [ ] validate non-empty contents
- [ ] compute file hash
- [ ] return raw text

## 8.3 `src/agent_gatsby/normalize.py`
- [ ] normalize whitespace
- [ ] normalize line endings
- [ ] preserve structure
- [ ] write locked normalized file

## 8.4 `src/agent_gatsby/index_text.py`
- [ ] split chapters
- [ ] split paragraphs
- [ ] assign IDs
- [ ] serialize JSON
- [ ] write passage index

## 8.5 `src/agent_gatsby/extract_metaphors.py`
- [ ] load index
- [ ] build prompt
- [ ] call model
- [ ] parse JSON
- [ ] validate fields
- [ ] save candidate file
- [ ] save raw response on failure

## 8.6 `src/agent_gatsby/build_evidence_ledger.py`
- [ ] load candidates
- [ ] exact-match quotes
- [ ] validate locators
- [ ] promote valid entries
- [ ] save verified ledger
- [ ] save rejected list

## 8.7 `src/agent_gatsby/plan_outline.py`
- [ ] load ledger
- [ ] build thesis prompt
- [ ] parse structured output
- [ ] save outline JSON

## 8.8 `src/agent_gatsby/draft_english.py`
- [ ] load outline
- [ ] load ledger
- [ ] draft section by section
- [ ] combine sections
- [ ] save markdown file

## 8.9 `src/agent_gatsby/verify_citations.py`
- [ ] extract quotes
- [ ] extract citation markers
- [ ] validate quotes
- [ ] validate locators
- [ ] write QA report

## 8.10 `src/agent_gatsby/critique_and_edit.py`
- [ ] improve prose only
- [ ] preserve quotes
- [ ] preserve citations
- [ ] write final English file

## 8.11 `src/agent_gatsby/translate_spanish.py`
- [ ] chunk English master
- [ ] translate each chunk
- [ ] reassemble file
- [ ] save markdown

## 8.12 `src/agent_gatsby/translate_mandarin.py`
- [ ] chunk English master
- [ ] translate each chunk
- [ ] force Simplified Chinese
- [ ] reassemble file
- [ ] save markdown

## 8.13 `src/agent_gatsby/bilingual_qa.py`
- [ ] compare heading counts
- [ ] compare citation counts
- [ ] compare quote markers
- [ ] write reports

## 8.14 `src/agent_gatsby/pdf_compiler.py`
- [ ] load text files
- [ ] set fonts
- [ ] render pages
- [ ] save PDFs
- [ ] catch Unicode errors

## 8.15 `src/agent_gatsby/manifest_writer.py`
- [ ] gather hashes
- [ ] gather outputs
- [ ] gather model info
- [ ] write manifest JSON

---

# 9. Debugging Checklist
Use this when something breaks.

## 9.1 If the local model call fails
- [ ] confirm `ollama serve` is running
- [ ] confirm model is pulled
- [ ] confirm endpoint URL matches config
- [ ] run a tiny manual test prompt
- [ ] inspect logs
- [ ] reduce prompt size if necessary
- [ ] save raw failure output

## 9.2 If JSON parsing fails
- [ ] inspect raw model response
- [ ] add stricter JSON-only instructions
- [ ] ask model for array/object only
- [ ] strip code fences before parsing if necessary
- [ ] retry once
- [ ] if still failing, simplify the schema

## 9.3 If quote verification fails
- [ ] print failing quote
- [ ] print referenced passage text
- [ ] check punctuation mismatch
- [ ] check whitespace normalization mismatch
- [ ] check curly quotes vs straight quotes
- [ ] decide whether verifier should normalize quotes before matching

## 9.4 If translations lose citations
- [ ] verify chunk boundaries
- [ ] explicitly instruct model not to alter citation markers
- [ ] compare citation counts before and after
- [ ] rerun only broken chunks

## 9.5 If Mandarin PDF breaks
- [ ] confirm font file exists
- [ ] confirm font supports CJK
- [ ] confirm font registration code is correct
- [ ] test a one-line Mandarin string first
- [ ] then test full document

## 9.6 If end-to-end run is messy
- [ ] delete stale intermediate files
- [ ] rerun from earliest failing stage
- [ ] confirm config values
- [ ] confirm directory paths
- [ ] confirm all expected artifacts are being written

---

# 10. Anti-Procrastination Execution Rules
These are here because the project is large and ADHD can make it easy to drift.

- [ ] Work only from this checklist.
- [ ] Do not redesign the system midstream unless something is clearly broken.
- [ ] Do not start polishing the repo visuals before the pipeline works.
- [ ] Do not chase optional features before tests pass.
- [ ] After finishing each section, physically check the box.
- [ ] After each major milestone, run the relevant test.
- [ ] After each major milestone, commit the code.

## Mandatory commit points
- [ ] after Thursday foundation
- [ ] after Friday evidence ledger + outline
- [ ] after Saturday English pipeline
- [ ] after Sunday translations + PDFs + tests
- [ ] after final cleanup

---

# 11. Final Submission Prep Checklist
Before you submit your application materials:

- [ ] confirm repo link works
- [ ] confirm README is current
- [ ] confirm repo shows actual code, not just architecture
- [ ] confirm final PDFs open correctly
- [ ] confirm file names are clean and professional
- [ ] confirm there are no embarrassing debug prints in visible files
- [ ] confirm tests exist in repo
- [ ] confirm logs do not expose anything unnecessary
- [ ] confirm the project clearly demonstrates implementation discipline
- [ ] confirm the output package is ready for upload

---

# 12. Absolute Final Checklist
You are done only when every box below is checked:

- [ ] source locked
- [ ] normalized text saved
- [ ] passage index saved
- [ ] candidate metaphors saved
- [ ] evidence ledger saved
- [ ] outline saved
- [ ] English draft saved
- [ ] English verification passed
- [ ] English final saved
- [ ] Spanish draft saved
- [ ] Mandarin draft saved
- [ ] translation QA reports saved
- [ ] English PDF saved
- [ ] Spanish PDF saved
- [ ] Mandarin PDF saved
- [ ] final manifest saved
- [ ] tests pass
- [ ] end-to-end pipeline works
- [ ] repo pushed
- [ ] submission artifacts ready