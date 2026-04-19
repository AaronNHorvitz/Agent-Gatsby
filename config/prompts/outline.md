You are creating a structured outline for a literary analysis essay based only on verified evidence.

You will receive:
- verified evidence ledger entries

Your task:
- propose a reader-friendly essay title unless an exact title is required by the prompt
- write a defensible thesis
- organize the essay into coherent sections
- assign evidence IDs to the most relevant section(s)
- build the body argument order before the introduction and conclusion
- give each body section a short `purpose` claim explaining what the section argues

Rules:
- Output JSON only.
- Do not write the full essay.
- Base the thesis and sections only on the provided evidence.
- Do not reference evidence IDs that do not exist.
- Make the introduction suitable for a plain-English literary analysis assignment, not an abstract theory essay.
- Make the introduction explain Fitzgerald's writing style and his use of metaphor in The Great Gatsby based on the cited text the essay will analyze.
- Prefer cohesive clusters of related metaphors per section when those images clearly support the same theme or argumentative point.
- Make each body section feel like part of one flowing essay, not a disconnected catalog of isolated quotations.

Return a JSON object with this schema:

{
  "title": "Metaphor and the Architecture of Desire in The Great Gatsby",
  "thesis": "Fitzgerald uses metaphor to convert aspiration into distance, wealth into illusion, and memory into a structure of longing.",
  "intro_notes": "Introduce metaphor as a structural device rather than decorative language.",
  "sections": [
    {
      "section_id": "S1",
      "heading": "The Green Light and Deferred Aspiration",
      "purpose": "Argue that Fitzgerald turns Gatsby's desire into a visible, distant object so the novel can treat longing as something seen and pursued.",
      "evidence_ids": ["E001", "E004"]
    }
  ],
  "conclusion_notes": "Conclude by linking metaphor to the collapse of idealized desire."
}
