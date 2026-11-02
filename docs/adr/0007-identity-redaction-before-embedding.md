# 0007. Remove names, contacts and institutions before embedding

**Status:** Accepted

## Context
Half of the match score is the MiniLM similarity between the resume and the job text. A
counterfactual test on the holdout set (swap only the candidate's name, to names linked
with different genders, regions and religions) moved scores by up to 9 points and changed
the top-5 jobs for 20% of variants. Institution swaps moved scores by up to 4 points.

## Decision
`services/redaction.py` removes the candidate's name (account and parsed), email, phone,
links and institution names before the text is embedded or classified. Skills,
experience and location are still parsed from the full text; recruiters still see the
original resume.

## Consequences
- Name swaps now change scores by 0 points and institution swaps by at most 2, with no
  top-5 changes; a test fails if this regresses. Matching quality is unchanged (holdout
  NDCG@5 0.965 vs 0.966).
- Institution removal is pattern-based (Institute, College, University...), so unusual
  names can slip through.
- This addresses identity signals in the text. It is not a measurement of outcomes for real
  candidate groups, which would need consented demographic data.

## Alternatives considered
- **No change, disclose the effect**: rejected; the effect is avoidable.
- **Embed only the skills section**: loses the experience descriptions that carry most of
  the semantic signal.
