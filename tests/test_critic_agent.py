import json
from unittest.mock import MagicMock, patch

from src.agents.critic_agent import _assemble_evidence_blocks, critique_report


def test_assemble_evidence_blocks_skips_unsourced_claims():
    claims = [
        {"text": "Claim with source", "source_ids": ["news:AAPL:1"]},
        {"text": "Unsourced synthesis claim", "source_ids": []},
    ]
    retrieved_chunks = {"news:AAPL:1": {"text": "Evidence text here."}}

    text, checked_indices = _assemble_evidence_blocks(claims, retrieved_chunks)

    assert checked_indices == [0]
    assert "Claim with source" in text
    assert "Evidence text here." in text
    assert "Unsourced synthesis claim" not in text


def test_assemble_evidence_blocks_concatenates_multiple_sources():
    claims = [{"text": "Multi-sourced claim", "source_ids": ["a", "b"]}]
    retrieved_chunks = {
        "a": {"text": "First piece of evidence."},
        "b": {"text": "Second piece of evidence."},
    }

    text, checked_indices = _assemble_evidence_blocks(claims, retrieved_chunks)

    assert checked_indices == [0]
    assert "First piece of evidence." in text
    assert "Second piece of evidence." in text


def test_assemble_evidence_blocks_handles_missing_chunk():
    claims = [{"text": "Claim citing a missing chunk", "source_ids": ["nonexistent"]}]

    text, checked_indices = _assemble_evidence_blocks(claims, {})

    assert checked_indices == [0]
    assert "no evidence text found" in text


def test_critique_report_no_cited_claims_is_noop():
    report = {
        "ticker": "AAPL",
        "claims": [{"text": "Pure synthesis", "source_ids": []}],
        "_retrieved_chunks": {},
    }

    result = critique_report(report)

    assert result["critic_verdicts"] == []
    assert result["flagged_claims"] == []


@patch("src.agents.critic_agent.anthropic.Anthropic")
def test_critique_report_builds_flagged_claims_from_verdicts(mock_anthropic_cls):
    report = {
        "ticker": "AAPL",
        "claims": [
            {"text": "Supported claim", "source_ids": ["news:1"]},
            {"text": "Unsupported claim", "source_ids": ["news:2"]},
        ],
        "_retrieved_chunks": {
            "news:1": {"text": "This directly supports the first claim."},
            "news:2": {"text": "This is unrelated to the second claim."},
        },
    }

    fake_verdicts = {
        "verdicts": [
            {"claim_index": 0, "supported": True, "explanation": "Directly stated."},
            {"claim_index": 1, "supported": False, "explanation": "Evidence doesn't mention this."},
        ]
    }

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = json.dumps(fake_verdicts)
    mock_response = MagicMock()
    mock_response.content = [mock_text_block]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    result = critique_report(report)

    assert len(result["critic_verdicts"]) == 2
    assert result["flagged_claims"] == [{
        "claim_index": 1,
        "claim_text": "Unsupported claim",
        "explanation": "Evidence doesn't mention this.",
    }]
