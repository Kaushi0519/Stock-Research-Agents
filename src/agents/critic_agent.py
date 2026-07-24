import json

import anthropic

from src.config import ANTHROPIC_API_KEY

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are a fact-checking critic for stock research reports.

You will be given a list of claims, each paired with the exact evidence text
it was supposedly derived from. Your ONLY job is to judge whether each claim
is actually stated or directly supported by ITS OWN evidence text.

Critical rule: judge traceability to the provided evidence, not general
plausibility or your own background knowledge. A claim can be true in the
real world and still be UNSUPPORTED if the specific evidence text given does
not actually state it. Conversely, do not fail a claim just because it
sounds surprising if the evidence text does state it. If the evidence talks
about something related but does not actually support the specific claim
made, mark it unsupported and explain the gap.

For each claim, return:
- claim_index: the index given with the claim
- supported: true only if the evidence text directly states or clearly
  implies the claim
- explanation: one or two sentences citing what the evidence does or does
  not say
"""

CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_index": {"type": "integer"},
                    "supported": {"type": "boolean"},
                    "explanation": {"type": "string"},
                },
                "required": ["claim_index", "supported", "explanation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}


def _assemble_evidence_blocks(claims: list[dict], retrieved_chunks: dict) -> tuple[str, list[int]]:
    """Build the evidence prompt text for every claim that has source_ids.

    Returns the prompt text plus the list of claim indices that were
    actually included (claims with no source_ids are not checkable this
    way and are skipped).
    """
    blocks = []
    checked_indices = []

    for i, claim in enumerate(claims):
        if not claim.get("source_ids"):
            continue

        evidence_texts = []
        for source_id in claim["source_ids"]:
            chunk = retrieved_chunks.get(source_id)
            if chunk:
                evidence_texts.append(f"[{source_id}]: {chunk['text']}")

        if not evidence_texts:
            # Claim cites source_ids we don't actually have chunk text for
            # (shouldn't normally happen, but don't silently skip it -- an
            # uncheckable citation is itself worth flagging).
            evidence_texts.append("(no evidence text found for the cited source_id(s))")

        blocks.append(
            f"CLAIM (index {i}): {claim['text']}\nEVIDENCE:\n" + "\n".join(evidence_texts)
        )
        checked_indices.append(i)

    return "\n\n".join(blocks), checked_indices


def critique_report(report: dict) -> dict:
    """Verify each cited claim in a report against its own cited evidence.

    Mutates and returns `report` with two additions:
    - critic_verdicts: list of {claim_index, supported, explanation} for
      every claim that had source_ids (claims marked as unsourced synthesis
      by the Analysis Agent are not fact-checkable this way and are skipped)
    - flagged_claims: the subset of verdicts judged unsupported, for quick
      surfacing to the user
    """
    claims = report["claims"]
    retrieved_chunks = report.get("_retrieved_chunks", {})

    evidence_text, checked_indices = _assemble_evidence_blocks(claims, retrieved_chunks)

    if not checked_indices:
        report["critic_verdicts"] = []
        report["flagged_claims"] = []
        return report

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": CRITIC_SCHEMA}},
        messages=[{
            "role": "user",
            "content": f"Verify each of the following claims against ONLY its own evidence:\n\n{evidence_text}",
        }],
    )

    verdict_text = next(block.text for block in response.content if block.type == "text")
    verdicts = json.loads(verdict_text)["verdicts"]

    report["critic_verdicts"] = verdicts
    report["flagged_claims"] = [
        {
            "claim_index": v["claim_index"],
            "claim_text": claims[v["claim_index"]]["text"],
            "explanation": v["explanation"],
        }
        for v in verdicts
        if not v["supported"]
    ]

    return report
