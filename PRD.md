# Product Requirements Document (PRD)
## Agent Gatsby
### Local, Citation-Verified Literary Analysis and Translation Pipeline

---

## 1. Document Control

**Product Name:** Agent Gatsby  
**Document Type:** Product Requirements Document (PRD)  
**Version:** 1.0  
**Status:** Draft / Execution-Ready  
**Primary Owner:** Aaron Horvitz  
**Target Completion:** Sunday night, April 19  
**Buffer Date:** Monday, April 20  
**Primary Delivery Artifacts:**
- English literary analysis PDF
- Spanish translation PDF
- Mandarin (Simplified Chinese) translation PDF
- GitHub repository containing code, tests, README, and execution instructions

---

## 2. Executive Summary

Agent Gatsby is a local-first AI pipeline designed to ingest a fixed source text of *The Great Gatsby*, extract metaphorically significant evidence, generate a grounded English literary analysis with citations, translate that analysis into Spanish and Mandarin, and render three separate submission-ready PDF artifacts.

This system is not intended to be a one-shot prompt demo. It is intended to demonstrate the ability to design and implement a constrained, auditable, production-minded AI-enabled system that prioritizes:

- evidence grounding
- explicit intermediate state
- citation integrity
- deterministic artifact generation
- translation fidelity
- local execution
- testability
- reproducibility

The repository itself is part of the deliverable. Therefore, the product is both:

1. the generated documents, and  
2. the engineering system used to produce them.

---

## 3. Product Vision

Build a local AI system that does **not** merely generate text, but instead produces defensible, inspectable, and submission-ready artifacts through a multi-stage workflow that separates:

- extraction from drafting
- drafting from verification
- authorship from translation
- content generation from layout
- orchestration from evaluation

The desired outcome is a repo and output package that communicates:

> "This builder understands how to engineer reliable AI systems under constraints."

---

## 4. Background and Context

A naive solution to this assignment would likely:

1. load the full source text into a large-context model
2. request a 10-page essay with citations
3. translate it twice
4. export three PDFs

While fast, that approach is fragile. It is especially weak on:

- exact quote fidelity
- reliable citations
- structural consistency across translations
- reproducibility
- recoverability when a stage fails
- testability
- overall engineering credibility

Agent Gatsby exists to solve those weaknesses by treating the assignment as a system design and implementation problem rather than a pure prompting problem.

---

## 5. Problem Statement

The system must generate three polished literary-analysis artifacts from a fixed source text while operating under the following constraints:

- local execution only
- no external API dependency in the reference implementation
- limited build time over a weekend
- high emphasis on correctness and professionalism
- public GitHub visibility of the underlying implementation
- output must include citations
- output must include translations
- outputs must be upload-ready PDFs

The core problem is not simply generating fluent prose. The core problem is engineering a pipeline that produces traceable, defensible results.

---

## 6. Product Goal

### Primary Goal
Produce a working local pipeline and final document package by Sunday night that demonstrates end-to-end AI system implementation quality.

### Success Definition
The system is successful if it can:

- ingest and lock the source text
- build a passage-addressable text representation
- extract and validate metaphor evidence
- generate a structured English essay from verified evidence
- verify quotes and citation references
- translate the final English master into Spanish and Mandarin
- perform structural QA on translations
- render three readable PDFs
- pass unit tests and at least one smoke/integration test
- present a clean, credible GitHub repository

---

## 7. Product Goals and Non-Goals

### 7.1 Goals
- Create a deterministic, local-first literary analysis pipeline
- Demonstrate engineering rigor through modular stages and test coverage
- Maximize citation accuracy and traceability
- Keep the architecture understandable and auditable
- Deliver submission-ready artifacts on time
- Show evidence of implementation discipline in the repo

### 7.2 Non-Goals
- Build a generalized literary analysis platform
- Build a web application
- Optimize for maximum autonomy at the expense of reliability
- Add unnecessary orchestration frameworks
- Solve literary scholarship comprehensively
- Build a benchmark-level translation system
- Add advanced retrieval, embeddings, or Docker unless time allows after MVP completion

---

## 8. Target Users

### 8.1 Primary User
**Builder / Applicant (Aaron)**  
The person running the system locally, debugging it, validating outputs, and submitting final artifacts.

#### Needs
- a predictable pipeline
- restartable stages
- clear logs
- testable modules
- explicit files on disk
- minimal abstraction overhead
- strong odds of finishing on time

### 8.2 Secondary User
**Reviewer / Hiring Manager / Technical Reviewer**  
The person reviewing the repository and possibly inspecting the output quality, architecture, or implementation choices.

#### Needs
- understandable architecture
- clean repo structure
- evidence of engineering discipline
- sensible tradeoffs
- proof that the system is more than a one-prompt wrapper

### 8.3 Tertiary User
**Future Maintainer (possibly same person later)**  
The person returning to the repo after submission.

#### Needs
- clear module boundaries
- reproducible runs
- versioned prompts/config
- logs and manifests
- enough structure to debug or extend later

---

## 9. User Stories

### 9.1 Source Handling
As a builder, I want the source text to be locked and hashed so that citations do not drift across runs.

### 9.2 Passage Addressing
As a builder, I want the novel segmented into stable passage IDs so that evidence and citations can be validated mechanically.

### 9.3 Evidence Extraction
As a builder, I want the model to identify candidate metaphors in structured form so that the essay can be built from explicit evidence rather than freeform memory.

### 9.4 Evidence Promotion
As a builder, I want invalid candidates rejected automatically so that only grounded evidence is used downstream.

### 9.5 Controlled Drafting
As a builder, I want the English essay drafted section by section from bounded evidence sets so that unsupported claims are minimized.

### 9.6 Verification
As a builder, I want quote and citation checks to run automatically so that literary claims remain defensible.

### 9.7 Translation Fidelity
As a builder, I want translations based on a frozen English master so that all three final artifacts remain aligned.

### 9.8 Output Packaging
As a builder, I want deterministic PDF rendering so that the final documents look professional and can be uploaded directly.

### 9.9 Reviewability
As a reviewer, I want the repo to show modular design, logging, tests, and explicit artifacts so that I can trust the engineering process.

---

## 10. Product Scope

### 10.1 In Scope
- local source ingestion
- source normalization
- source hashing and manifest creation
- passage indexing
- candidate metaphor extraction
- evidence ledger generation
- outline creation
- English draft generation
- citation and quote verification
- editorial refinement
- English master freeze
- Spanish translation
- Mandarin translation (Simplified Chinese)
- translation QA
- deterministic PDF rendering
- final manifest creation
- CLI orchestration
- unit tests
- one smoke/integration test
- logging
- GitHub-ready documentation

### 10.2 Out of Scope
- web UI
- multi-user workflow
- cloud deployment
- advanced semantic retrieval
- benchmark evaluation suite
- browser automation
- full CI/CD
- containerization unless time remains after the MVP is complete
- support for arbitrary books or arbitrary literary prompts in v1

---

## 11. Product Principles

### 11.1 Evidence Before Prose
The system must not begin with essay generation. It must begin with evidence discovery and validation.

### 11.2 Explicit State Over Hidden Magic
All critical intermediate decisions should be serialized to disk.

### 11.3 Verification Before Promotion
A stage is not complete just because the model produced text. A stage is complete only after validation passes.

### 11.4 Deterministic Rendering
The model produces content. A separate renderer produces final PDF artifacts.

### 11.5 Minimum Viable Complexity
The reference implementation should avoid unnecessary frameworks and abstractions.

### 11.6 Local-First by Default
The baseline implementation should run locally on the target workstation.

---

## 12. High-Level Product Flow

1. Load locked source text
2. Normalize source
3. Segment into indexed passages
4. Extract candidate metaphors
5. Validate and promote evidence into ledger
6. Generate thesis and outline
7. Draft English essay section by section
8. Verify quotes and citation markers
9. Run editorial refinement on English
10. Freeze English master
11. Translate English master to Spanish
12. Translate English master to Mandarin
13. Perform structural QA on translations
14. Render 3 PDFs
15. Write final manifest
16. Run tests and dry-run validation

---

## 13. Functional Requirements

## 13.1 Source Acquisition and Locking

### Requirement
The system shall read a fixed local copy of the source text and generate a source manifest.

### Inputs
- `data/source/gatsby_source.txt`

### Outputs
- `artifacts/manifests/source_manifest.json`

### Acceptance Criteria
- source file exists
- source file is readable
- source file is non-empty
- SHA-256 hash is generated
- manifest contains at least:
  - source path
  - file hash
  - encoding
  - timestamp

---

## 13.2 Source Normalization

### Requirement
The system shall normalize the source text into a stable internal representation without destroying chapter or paragraph structure.

### Inputs
- raw source text

### Outputs
- `data/normalized/gatsby_locked.txt`

### Acceptance Criteria
- normalized file exists
- chapter markers preserved
- paragraph structure preserved
- excessive blank lines collapsed
- output is readable and non-empty

---

## 13.3 Passage Indexing

### Requirement
The system shall split the normalized source into stable, addressable passage records.

### Inputs
- normalized text

### Outputs
- `artifacts/manifests/passage_index.json`

### Passage Record Must Include
- `passage_id`
- `chapter`
- `paragraph`
- `text`

### Acceptance Criteria
- passage index exists
- passage IDs are unique
- passage IDs are deterministic across reruns
- every passage has non-empty text

---

## 13.4 Candidate Metaphor Extraction

### Requirement
The system shall generate a structured set of candidate metaphor records from the indexed source.

### Inputs
- passage index

### Outputs
- `artifacts/evidence/metaphor_candidates.json`

### Candidate Record Must Include
- `candidate_id`
- `label`
- `passage_id`
- `quote`
- `rationale`
- `confidence`

### Acceptance Criteria
- output file exists
- output is parseable as structured data
- each record references a real passage ID
- candidate records are human-reviewable

---

## 13.5 Evidence Ledger Generation

### Requirement
The system shall validate candidate records and promote valid ones into a verified evidence ledger.

### Inputs
- candidate metaphor file
- passage index

### Outputs
- `artifacts/evidence/evidence_ledger.json`
- `artifacts/evidence/rejected_candidates.json`

### Validation Rules
- passage ID must exist
- quote must appear exactly in source passage text
- evidence must be sufficiently interpretable and non-empty
- invalid candidates must be rejected, not silently passed through

### Acceptance Criteria
- evidence ledger exists
- rejected candidates file exists if applicable
- every evidence entry is traceable to a passage
- every promoted quote exact-matches source text

---

## 13.6 Thesis and Outline Generation

### Requirement
The system shall generate a thesis and section outline from verified evidence rather than from unconstrained source-wide prompting.

### Inputs
- evidence ledger

### Outputs
- `artifacts/drafts/outline.json`

### Outline Must Include
- essay title
- thesis
- ordered sections
- section headings
- evidence IDs per section

### Acceptance Criteria
- outline file exists
- thesis is non-empty
- sections are ordered
- referenced evidence IDs exist

---

## 13.7 English Draft Generation

### Requirement
The system shall generate the English essay section by section using only evidence assigned to each section.

### Inputs
- outline
- evidence ledger

### Outputs
- `artifacts/drafts/analysis_english_draft.md`

### Constraints
- no invented quotes
- no invented citations
- no unsupported claims
- academic tone required
- citations must use bracketed chapter.paragraph locators such as `[5.18]`
- page-number citations are out of scope for v1

### Acceptance Criteria
- English draft exists
- draft has multiple sections
- section order matches outline
- citations appear in expected `[chapter.paragraph]` format

---

## 13.8 Quote and Citation Verification

### Requirement
The system shall verify quotes and citation markers in the English draft.

### Inputs
- English draft
- evidence ledger
- passage index

### Outputs
- `artifacts/qa/english_verification_report.json`

### Checks Must Include
- exact quote matching
- citation resolution
- evidence linkage validation
- readable failure reporting

### Acceptance Criteria
- verification report exists
- failures are visible and understandable
- pipeline can halt on verification failure

---

## 13.9 English Editorial Refinement

### Requirement
The system shall refine the English draft for clarity and coherence without altering verified quotes or introducing new citations.

### Inputs
- verified English draft

### Outputs
- `artifacts/drafts/analysis_english_final.md`

### Constraints
- direct quotes may not be changed
- citation markers may not be changed
- no new evidence may be introduced

### Acceptance Criteria
- final English file exists
- prose quality improves
- quote and citation integrity remain intact

---

## 13.10 Frozen English Master

### Requirement
The system shall freeze the verified final English analysis as the canonical translation source.

### Inputs
- English final

### Outputs
- `artifacts/final/analysis_english_master.md`

### Acceptance Criteria
- English master exists
- downstream translation stages use this file only

---

## 13.11 Spanish Translation

### Requirement
The system shall translate the frozen English master into Spanish in bounded chunks.

### Inputs
- English master

### Outputs
- `artifacts/translations/analysis_spanish_draft.md`

### Constraints
- preserve headings
- preserve citation markers
- translate quoted content into Spanish
- preserve quotation boundaries
- preserve structural order
- maintain academic tone

### Acceptance Criteria
- Spanish file exists
- Spanish file is non-empty
- heading count matches English
- citation structure preserved

---

## 13.12 Mandarin Translation

### Requirement
The system shall translate the frozen English master into Mandarin rendered in Simplified Chinese.

### Inputs
- English master

### Outputs
- `artifacts/translations/analysis_mandarin_draft.md`

### Constraints
- preserve headings
- preserve citation markers
- translate quoted content into Simplified Chinese
- preserve quotation boundaries
- preserve structure
- output in Simplified Chinese
- remain compatible with PDF rendering

### Acceptance Criteria
- Mandarin file exists
- Mandarin file is non-empty
- heading count matches English
- citation structure preserved

---

## 13.13 Translation QA

### Requirement
The system shall generate structural QA reports for Spanish and Mandarin outputs.

### Inputs
- English master
- Spanish draft
- Mandarin draft

### Outputs
- `artifacts/qa/spanish_qa_report.json`
- `artifacts/qa/mandarin_qa_report.json`

### Checks Must Include
- heading parity
- citation marker parity
- section count parity
- section order parity
- quote marker parity after full translation
- non-empty output checks

### Acceptance Criteria
- both QA reports exist
- mismatches are visible and understandable
- major structural mismatches can be corrected before rendering
- v1 QA is sufficient when structural parity passes and a human completes intro, middle, and conclusion spot checks

---

## 13.14 PDF Rendering

### Requirement
The system shall render three separate PDFs from finalized text artifacts.

### Inputs
- English master
- Spanish draft
- Mandarin draft
- local fonts

### Outputs
- `outputs/Gatsby_Analysis_English.pdf`
- `outputs/Gatsby_Analysis_Spanish.pdf`
- `outputs/Gatsby_Analysis_Mandarin.pdf`

### Constraints
- readable page margins
- plain academic formatting
- page numbers
- Unicode-safe rendering for Mandarin
- separate files per language
- no decorative layout

### Acceptance Criteria
- all three PDF files exist
- all three files open successfully
- Mandarin PDF renders without broken characters
- file size is non-zero

---

## 13.15 Final Manifest

### Requirement
The system shall generate a final manifest summarizing the run.

### Inputs
- source manifest
- config
- output artifact paths
- QA reports

### Outputs
- `outputs/final_manifest.json`

### Manifest Must Include
- timestamp
- source hash
- model name(s)
- config path
- output file paths
- QA artifact paths

### Acceptance Criteria
- final manifest exists
- final manifest is readable
- final manifest reflects actual files generated

---

## 13.16 Orchestration

### Requirement
The system shall expose a command-line orchestration layer that can run:
- the full pipeline
- individual stages

### Inputs
- CLI arguments
- config path

### Outputs
- stage execution
- logs
- files on disk

### Acceptance Criteria
- `--run all` works
- `--run <stage>` works
- failures produce readable output
- stages can be rerun independently

---

## 14. Non-Functional Requirements

## 14.1 Local Execution
The reference system must run locally on the target development machine.

## 14.2 Reproducibility
A rerun using the same locked source and config should produce structurally similar outputs and identical deterministic artifacts where applicable.

## 14.3 Auditability
Intermediate files must be stored so the process can be inspected after execution.

## 14.4 Recoverability
The system must support rerunning a failed stage without rebuilding the entire pipeline.

## 14.5 Testability
Core modules must be covered by unit tests and at least one smoke/integration test.

## 14.6 Readability
The codebase must be understandable to a technical reviewer.

## 14.7 Simplicity
The architecture should prefer simple, explicit Python code over opaque orchestration frameworks.

## 14.8 Time-Bounded Deliverability
The system must be buildable and stabilizable over a weekend.

---

## 15. Product Architecture Requirements

### 15.1 Architectural Style
- modular pipeline
- file-based intermediate state
- deterministic CLI orchestration
- local model integration
- deterministic renderer

### 15.2 Required Modules
- config loader
- logger
- source ingestion
- normalization
- passage indexing
- model client
- candidate extraction
- evidence ledger builder
- outline planner
- English drafter
- citation verifier
- editorial refiner
- Spanish translator
- Mandarin translator
- translation QA module
- PDF compiler
- manifest writer
- orchestrator

### 15.3 Discouraged Architectural Choices
- unnecessary agent frameworks
- deeply nested orchestration abstractions
- runtime network dependency for core execution
- non-versioned prompts
- hidden global state

---

## 16. Data and Artifact Requirements

### 16.1 Required Intermediate Artifacts
- `source_manifest.json`
- `gatsby_locked.txt`
- `passage_index.json`
- `metaphor_candidates.json`
- `evidence_ledger.json`
- `rejected_candidates.json` if applicable
- `outline.json`
- `analysis_english_draft.md`
- `english_verification_report.json`
- `analysis_english_final.md`
- `analysis_english_master.md`
- `analysis_spanish_draft.md`
- `analysis_mandarin_draft.md`
- `spanish_qa_report.json`
- `mandarin_qa_report.json`
- final PDFs
- `final_manifest.json`

### 16.2 Artifact Philosophy
Artifacts must exist not just for debugging, but to demonstrate that the pipeline is a real system with inspectable stages.

---

## 17. Success Metrics

### 17.1 Delivery Metrics
- 3 PDF outputs generated
- 1 final manifest generated
- 1 README aligned with implementation
- repo pushed and reviewable

### 17.2 Quality Metrics
- 100% of promoted evidence quotes exact-match source text
- English verification report generated successfully
- translation QA reports generated successfully
- all PDFs open without errors

### 17.3 Engineering Metrics
- unit tests pass
- smoke test passes
- full pipeline can complete end-to-end at least once
- logs written to disk
- repo structure remains clean and understandable

### 17.4 Human Review Metrics
- English essay reads as analytical rather than generic
- citation format is consistent
- translations are structurally aligned
- repo communicates deliberate engineering choices

---

## 18. Testing Requirements

## 18.1 Required Unit Tests
- source hashing correctness
- normalization preserves structure
- passage IDs are deterministic and unique
- quote verification succeeds on valid quote
- quote verification fails on invalid quote
- translation artifacts exist and preserve structure
- PDF generation succeeds with Unicode-safe font handling

## 18.2 Required Smoke Test
A reduced end-to-end test that verifies the pipeline can run through major stages and produce expected artifacts.

## 18.3 Manual QA Requirements
- read the English essay fully at least once
- inspect at least one Spanish section manually
- inspect at least one Mandarin section manually
- open all three PDFs manually
- inspect repo after push

---

## 19. Logging and Error Handling Requirements

### 19.1 Logging
The system must write:
- console logs
- persistent file logs

### 19.2 Error Handling
The system must fail clearly on:
- missing source file
- malformed config
- broken model endpoint
- invalid JSON from model
- quote verification failure
- missing font file for Mandarin PDF
- translation QA failures if severe

### 19.3 Recovery Behavior
The system should support restarting from the failed stage whenever possible.

---

## 20. Dependencies and Tooling Requirements

### 20.1 Required Dependencies
- Python
- YAML config loader
- PDF library
- local model client or Ollama-compatible client
- test framework

### 20.2 Allowed Dependency Philosophy
Every added dependency must be justified by one of:
- essential functionality
- substantial time savings
- improved reliability

### 20.3 Disallowed Dependency Philosophy
Do not add a dependency just because it is popular or expressive.

---

## 21. UX / CLI Requirements

### 21.1 Command-Line UX
The CLI must be clear and minimal.

### Required Usage Patterns
- run full pipeline
- run single stage
- specify config file
- print readable errors

### 21.2 Output UX
The generated files should be easy to locate and named clearly.

### 21.3 Developer UX
The repo should be navigable by a reviewer within a few minutes.

---

## 22. Repo and Documentation Requirements

### 22.1 README Must Cover
- purpose
- architecture
- key stages
- local execution philosophy
- repo structure
- how to run
- what outputs are generated
- why the system is structured this way

### 22.2 Repo Quality Expectations
- clear folders
- no stray scratch files
- no broken commands in documentation
- consistent naming
- professional output naming

---

## 23. Risks and Mitigations

## 23.1 Risk: Candidate extraction quality is weak
**Mitigation:** allow manual curation fallback for the evidence ledger.

## 23.2 Risk: Quote verification fails repeatedly
**Mitigation:** simplify citation format, normalize punctuation carefully, and keep evidence bounded.

## 23.3 Risk: English draft feels generic
**Mitigation:** force outline-from-evidence and perform one strong human review pass.

## 23.4 Risk: Translation drift
**Mitigation:** translate from frozen English master and run structural QA.

## 23.5 Risk: Mandarin PDF rendering fails
**Mitigation:** use a known working Unicode/CJK font and test rendering early.

## 23.6 Risk: Weekend time compression
**Mitigation:** prioritize MVP and defer all non-essential features.

## 23.7 Risk: Repo appears over-engineered or under-engineered
**Mitigation:** keep the architecture simple but explicit, with visible tests and artifacts.

---

## 24. Tradeoffs

### 24.1 Chosen Tradeoff
Prefer reliability over maximal autonomy.

### 24.2 Chosen Tradeoff
Prefer explicit file-based state over hidden orchestration magic.

### 24.3 Chosen Tradeoff
Prefer simple Python orchestration over framework-heavy abstraction.

### 24.4 Chosen Tradeoff
Prefer bounded, verifiable stages over a single elegant but fragile prompt chain.

---

## 25. Locked V1 Decisions

- English citations use bracketed chapter.paragraph locators such as `[5.18]`. These locators reference the locked passage index rather than printed page numbers.
- The Spanish and Mandarin outputs fully translate the essay, including quoted content, while preserving citation markers and quotation boundaries.
- Exact quote verification applies to the English master only. Translated outputs are promoted through structural QA plus human spot checks.
- PDF styling remains intentionally plain and professional: title, headings, readable margins, page numbers, and Unicode-safe fonts without decorative layout.
- Manual evidence overrides are allowed only as a tiny explicit fallback in the verified evidence ledger, and every override must be logged.
- Minimum translation QA for v1 is heading parity, citation parity, section order parity, quote-marker parity, non-empty output checks, and manual intro/middle/conclusion spot checks.

---

## 26. MVP Definition

The MVP is complete when:

- source is locked and hashed
- normalized file exists
- passage index exists
- evidence ledger exists
- outline exists
- English final exists
- English verification report exists
- Spanish translation exists
- Mandarin translation exists
- translation QA reports exist
- 3 PDFs exist
- final manifest exists
- tests pass
- full pipeline completes once
- repo is presentable

---

## 27. V1.1 / Post-MVP Enhancements

Only consider these if MVP is complete and stable:

- semantic retrieval / embeddings
- improved bilingual semantic QA
- richer PDF styling
- model routing by task
- containerized execution
- regression comparison of outputs across reruns
- richer evaluation metrics

---

## 28. Delivery Plan

### Friday
- repo setup
- config
- logging
- source lock
- normalization
- passage index
- extraction
- evidence ledger

### Saturday
- outline
- English draft
- verification
- editorial pass
- core tests

### Sunday
- translations
- translation QA
- PDFs
- manifest
- full dry run
- final cleanup
- push repo

### Monday Buffer Only
- fix bugs
- rerun outputs
- upload artifacts
- no redesign

---

## 29. Final Product Statement

Agent Gatsby is a local, modular, citation-aware AI pipeline for producing a literary analysis of *The Great Gatsby* and two translated companion artifacts. Its primary value is not that it can generate prose, but that it demonstrates how to engineer an AI-enabled system that is:

- grounded
- inspectable
- testable
- restartable
- reproducible
- presentable

The final success condition is not merely three PDFs.

The final success condition is a repository and output package that together demonstrate implementation competence under deadline pressure.

---
```
