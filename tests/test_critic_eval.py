"""Real-model eval for the Critic Agent's claim-verification judgment.

Unlike test_critic_agent.py (which mocks the LLM to test wiring), this file
makes real API calls and checks the critic's actual judgment against known
right answers -- specifically including the trap the whole Critic Agent
exists to catch: a claim that sounds true/plausible but is not actually
stated by its cited evidence must still be flagged unsupported. "Sounds
right" is not the bar; "the cited text actually says this" is.
"""

from src.agents.critic_agent import critique_report

EVAL_CASES = [
    {
        "name": "directly_supported",
        "claim": "The company's revenue grew 8% year over year.",
        "evidence": "Total revenue for the fiscal year increased 8% compared to the prior year, driven by strong product sales.",
        "expected_supported": True,
    },
    {
        "name": "directly_contradicted",
        "claim": "The company's revenue declined 8% year over year.",
        "evidence": "Total revenue for the fiscal year increased 8% compared to the prior year, driven by strong product sales.",
        "expected_supported": False,
    },
    {
        "name": "plausible_but_unstated",
        "claim": "The company's CFO announced a new $10 billion stock buyback program.",
        "evidence": "The company faces supply chain risk due to its concentration of manufacturing partners in a single region.",
        "expected_supported": False,
    },
    {
        "name": "overreach_beyond_evidence",
        "claim": "Revenue more than doubled compared to the prior year.",
        "evidence": "Revenue increased approximately 3% compared to the prior year, a modest improvement.",
        "expected_supported": False,
    },
]


def test_critic_judges_claims_against_evidence_not_plausibility():
    claims = [{"text": c["claim"], "source_ids": [c["name"]]} for c in EVAL_CASES]
    retrieved_chunks = {c["name"]: {"text": c["evidence"]} for c in EVAL_CASES}

    report = {
        "ticker": "TEST",
        "claims": claims,
        "_retrieved_chunks": retrieved_chunks,
    }

    result = critique_report(report)

    verdicts_by_index = {v["claim_index"]: v for v in result["critic_verdicts"]}

    failures = []
    for i, case in enumerate(EVAL_CASES):
        verdict = verdicts_by_index.get(i)
        assert verdict is not None, f"No verdict returned for case '{case['name']}'"
        if verdict["supported"] != case["expected_supported"]:
            failures.append(
                f"{case['name']}: expected supported={case['expected_supported']}, "
                f"got {verdict['supported']} ({verdict['explanation']})"
            )

    assert not failures, "Critic judgment mismatches:\n" + "\n".join(failures)
