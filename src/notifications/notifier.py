from abc import ABC, abstractmethod

import requests


class Notifier(ABC):
    """Abstract interface for sending push notifications.

    Swappable so a provider (ntfy.sh, Pushover, email/SMS) can be added or
    replaced later without changing any of the calling code -- callers only
    ever depend on this interface, never on a concrete provider.
    """

    @abstractmethod
    def send(
        self, title: str, message: str, priority: str = "default", click_url: str = None
    ) -> bool:
        """Send a notification. `click_url`, if given, is opened when the
        notification itself is tapped. Returns True on success, False on
        failure."""
        raise NotImplementedError


class NtfyNotifier(Notifier):
    """Sends push notifications via ntfy.sh.

    SECURITY NOTE: on the public ntfy.sh server, anyone who knows your topic
    name can subscribe to it and read your notifications -- there is no
    access control by default. `topic` must be a long, random, hard-to-guess
    string (e.g. a UUID), not a descriptive name like "stock-alerts". Treat
    it like a secret: keep it in `.env`, never commit it or log it.
    """

    _PRIORITY_MAP = {"low": "low", "default": "default", "high": "high", "urgent": "urgent"}

    def __init__(self, topic: str, base_url: str = "https://ntfy.sh"):
        if not topic:
            raise ValueError("ntfy topic must not be empty")
        self.topic = topic
        self.base_url = base_url.rstrip("/")

    def send(
        self, title: str, message: str, priority: str = "default", click_url: str = None
    ) -> bool:
        headers = {
            "Title": title,
            "Priority": self._PRIORITY_MAP.get(priority, "default"),
        }
        if click_url:
            headers["Click"] = click_url

        try:
            response = requests.post(
                f"{self.base_url}/{self.topic}",
                data=message.encode("utf-8"),
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False
