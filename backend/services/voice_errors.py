"""Shared error type for the voice providers.

Lives in its own module so a provider can raise it without importing
voice_client.py, which is the module that imports the providers.
"""

from __future__ import annotations


class VoiceError(RuntimeError):
    """A voice call failed in a way the chat UI should show the user.

    `status_code` is what the route returns: 503 for "this is a setup
    problem on this machine" (missing package, missing weights, no API
    key) and 502 for "the provider was there but the call failed".
    """

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code
