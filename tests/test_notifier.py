from unittest.mock import MagicMock, patch

import pytest
import requests

from src.notifications.notifier import NtfyNotifier


def test_ntfy_notifier_requires_topic():
    with pytest.raises(ValueError):
        NtfyNotifier(topic="")


@patch("src.notifications.notifier.requests.post")
def test_ntfy_notifier_send_success(mock_post):
    mock_response = MagicMock()
    mock_post.return_value = mock_response

    notifier = NtfyNotifier(topic="test-topic-abc123")
    result = notifier.send("Test Title", "Test message", priority="high")

    assert result is True
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.args[0] == "https://ntfy.sh/test-topic-abc123"
    assert call_args.kwargs["headers"]["Title"] == "Test Title"
    assert call_args.kwargs["headers"]["Priority"] == "high"
    assert call_args.kwargs["data"] == b"Test message"


@patch("src.notifications.notifier.requests.post")
def test_ntfy_notifier_send_with_click_url_sets_click_header(mock_post):
    mock_post.return_value = MagicMock()

    notifier = NtfyNotifier(topic="test-topic-abc123")
    notifier.send("Title", "Message", click_url="http://192.168.1.5:8000/reports/7")

    assert mock_post.call_args.kwargs["headers"]["Click"] == "http://192.168.1.5:8000/reports/7"


@patch("src.notifications.notifier.requests.post")
def test_ntfy_notifier_send_without_click_url_omits_click_header(mock_post):
    mock_post.return_value = MagicMock()

    notifier = NtfyNotifier(topic="test-topic-abc123")
    notifier.send("Title", "Message")

    assert "Click" not in mock_post.call_args.kwargs["headers"]


@patch("src.notifications.notifier.requests.post")
def test_ntfy_notifier_send_unknown_priority_falls_back_to_default(mock_post):
    mock_post.return_value = MagicMock()

    notifier = NtfyNotifier(topic="test-topic-abc123")
    notifier.send("Title", "Message", priority="not-a-real-priority")

    assert mock_post.call_args.kwargs["headers"]["Priority"] == "default"


@patch("src.notifications.notifier.requests.post")
def test_ntfy_notifier_send_http_error_returns_false(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("500")
    mock_post.return_value = mock_response

    notifier = NtfyNotifier(topic="test-topic-abc123")
    result = notifier.send("Title", "Message")

    assert result is False


@patch("src.notifications.notifier.requests.post")
def test_ntfy_notifier_send_connection_error_returns_false(mock_post):
    mock_post.side_effect = requests.ConnectionError("no internet")

    notifier = NtfyNotifier(topic="test-topic-abc123")
    result = notifier.send("Title", "Message")

    assert result is False
