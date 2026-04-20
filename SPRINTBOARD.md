# Sprintboard
## Weekend Execution Dashboard

**Objective:** design, implement, validate, and package a local AI pipeline for Treasury's supplemental *Great Gatsby* challenge.

**Status:** shipped

**Scope of the weekend sprint**
- lock a local source text of *The Great Gatsby*
- extract evidence before drafting
- generate a cited English analysis
- translate the frozen English master into Spanish and Mandarin
- render three upload-ready PDFs
- write QA reports, logs, and a final manifest

**What shipped**
- locked source text, source manifest, and deterministic passage index
- evidence ledger, citation registry, and citation text artifact
- English draft, bounded expansion path, verification pass, dynamic validation reports, and frozen English master
- Spanish and Mandarin translations from the frozen English master with bounded chunk fallback and document-level dynamic validation
- deterministic PDF rendering for English, Spanish, and Mandarin
- translation QA reports, PDF audit reports, LLM forensic audit reports, and final manifest

**Current outputs**
- `outputs/Gatsby_Analysis_English.pdf`
- `outputs/Gatsby_Analysis_Spanish.pdf`
- `outputs/Gatsby_Analysis_Mandarin.pdf`
- `outputs/final_manifest.json`

**Validation completed**
- unit tests for source integrity, indexing, citation handling, translation QA, and PDF rendering
- English master regression checks before promotion
- dynamic critic-correction reports for English, Spanish, and Mandarin markdown finalization
- Spanish and Mandarin structural QA before rendering
- post-PDF audit reports for English, Spanish, and Mandarin
- post-PDF LLM forensic audit reports, with a small blocking list for prompt leaks and leaked assistant text
- deterministic artifact generation with logs and manifests written to disk

**What this repo demonstrates**
- AI implementation in a real local test environment
- explicit evidence grounding instead of one-shot generation
- bounded retry and fallback behavior around translation placeholder drift
- verification gates before artifact promotion
- multilingual generation with structure preservation
- deterministic packaging of final outputs

**Open risks**
- visual PDF QA is still partly manual
- translated prose remains more fragile than the English master
- local model behavior can still drift, so the QA and audit gates matter

**Optional next steps**
- add image-based visual QA for final PDFs
- strengthen canonical quote reuse across translated body paragraphs
- tighten renderer handling for mixed Latin/CJK line wrapping

**Out of scope for this sprint**
- cloud deployment
- web UI
- Docker
- CI/CD
- embeddings or semantic retrieval
- generalized multi-book support

For the full implementation checklist and historical work log, see `TASKS.md`.
