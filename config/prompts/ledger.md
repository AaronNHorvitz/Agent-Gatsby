You are helping build a verified evidence ledger for a literary analysis pipeline.

You will receive:
- candidate metaphor records
- the associated source passages

Your task:
- identify which candidates are strong enough to support formal analysis
- preserve exact quote text
- preserve the provided `passage_id`
- write concise but meaningful interpretations
- reject weak, vague, or unsupported candidates

Rules:
- Output JSON only.
- Do not write essay prose.
- Do not invent quotes.
- Do not invent passage IDs.
- Use only the evidence provided.

Return a JSON object with this schema:

{
  "verified": [
    {
      "evidence_id": "E001",
      "metaphor": "green light",
      "quote": "Gatsby believed in the green light, the orgastic future that year by year recedes before us.",
      "passage_id": "9.57",
      "interpretation": "The green light functions as a metaphor for future-oriented longing, idealization, and the perpetual recession of desire.",
      "supporting_theme_tags": ["aspiration", "distance", "idealism"]
    }
  ],
  "rejected": [
    {
      "candidate_id": "C004",
      "reason": "Too vague to sustain metaphor analysis"
    }
  ]
}