You are performing structural QA on a translated literary analysis document.

You will receive:
- the English master
- a translated version

Your task:
- compare structure, not style alone
- verify heading parity
- verify citation marker parity
- verify quote marker parity where applicable
- identify major omissions or structural mismatches

Rules:
- Output JSON only.
- Be concise and specific.
- Do not rewrite the translation.

Return a JSON object with this schema:

{
  "heading_count_match": true,
  "citation_count_match": true,
  "quote_marker_count_match": true,
  "major_issues": [],
  "notes": "No major structural mismatch detected."
}