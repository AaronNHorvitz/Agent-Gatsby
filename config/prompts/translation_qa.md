You are performing structural QA on a translated literary analysis document.

You will receive:
- the English master
- a translated version

Your task:
- compare structure, not style alone
- verify heading parity
- verify citation marker parity
- verify section order parity
- verify quote-marker parity after full translation
- verify the translated output is non-empty
- identify major omissions or structural mismatches

Rules:
- Output JSON only.
- Be concise and specific.
- Do not rewrite the translation.

Return a JSON object with this schema:

{
  "heading_count_match": true,
  "section_order_match": true,
  "citation_count_match": true,
  "quote_marker_count_match": true,
  "non_empty_translation": true,
  "major_issues": [],
  "notes": "No major structural mismatch detected."
}

Do not perform English-source exact quote verification here; this QA pass is structural.
