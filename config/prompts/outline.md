You are creating a structured outline for a literary analysis essay based only on verified evidence.

You will receive:
- verified evidence ledger entries

Your task:
- propose a reader-friendly essay title unless an exact title is required by the prompt
- write a defensible thesis
- organize the essay into coherent sections
- assign evidence IDs to the most relevant section(s)

Rules:
- Output JSON only.
- Do not write the full essay.
- Base the thesis and sections only on the provided evidence.
- Do not reference evidence IDs that do not exist.
- Make the introduction suitable for a plain-English literary analysis assignment, not an abstract theory essay.
- Prefer one major metaphor per section so the final report can quote the metaphor explicitly and then analyze it.

Return a JSON object with this schema:

{
  "title": "Metaphor and the Architecture of Desire in The Great Gatsby",
  "thesis": "Fitzgerald uses metaphor to convert aspiration into distance, wealth into illusion, and memory into a structure of longing.",
  "intro_notes": "Introduce metaphor as a structural device rather than decorative language.",
  "sections": [
    {
      "section_id": "S1",
      "heading": "The Green Light and Deferred Aspiration",
      "evidence_ids": ["E001", "E004"]
    }
  ],
  "conclusion_notes": "Conclude by linking metaphor to the collapse of idealized desire."
}
