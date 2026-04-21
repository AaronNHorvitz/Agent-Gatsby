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

---

## Post-Sprint Iteration 1
### Multi-Model Routing and Benchmarking

**Objective:** add task-based model routing, capture comparable per-task metrics, and benchmark a mixed-model configuration without destabilizing the shipped reference pipeline.

**Status:** planned

**Why this iteration exists**
- the shipped reference path assumes one primary reasoning model for most generation tasks
- translation and critique are different workloads from English literary analysis
- the next iteration should make model choice explicit per task, not implicit per module
- the repo needs a safe way to compare mixed-model runs against the current baseline

**Proposed first benchmark profile**
- English outline, draft, expansion, and critique: `Gemma 4`
- Spanish translation and cleanup: `Qwen 32B`
- Mandarin translation and cleanup: `Qwen 32B`
- dynamic validation and final forensic audit: keep the current critic path first, then compare later if useful

**Planned scope**
- add task-based model routing in config and config resolution helpers
- update core LLM call sites to resolve by task name instead of ad hoc model keys
- record comparable metrics for LLM calls and stage results
- add a benchmarking path for mixed-model runs versus baseline runs
- document how to switch routing profiles locally

**Granular milestone board**
- `Milestone 1:` routing design locked
  - define task names for English, Spanish, Mandarin, and critic workloads
  - preserve the current single-model path as the fallback baseline
- `Milestone 2:` config and client routing implemented
  - add model-routing config surface
  - resolve models by task in one shared path
- `Milestone 3:` stage integration completed
  - English path routed
  - Spanish path routed
  - Mandarin path routed
  - critic and audit paths reviewed
- `Milestone 4:` metrics and benchmark harness implemented
  - capture per-call latency, retries, output length, and resolved model
  - compare baseline versus mixed-model outputs
- `Milestone 5:` first benchmark run completed
  - baseline run captured
  - mixed-model run captured
  - QA and artifact comparison summarized

**Definition of done for the iteration**
- a routing table can switch models by task without code edits
- the baseline route still works unchanged
- the first mixed-model route runs locally
- metrics are written to disk for comparison
- README and task docs explain the routing and benchmark workflow

**Primary risks**
- routing logic spreads across too many modules instead of staying centralized
- different models may preserve citations and placeholders differently
- benchmark data may be noisy if stage outputs are not normalized enough to compare
- local runtime or VRAM pressure may make some model combinations impractical

**Out of scope for this iteration**
- automated model search across every available local model
- cloud-hosted benchmark infrastructure
- generalized hyperparameter tuning
- large-scale UI or dashboard work
