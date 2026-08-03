"""GeminiChat — OpenAI-compatible API for Google Gemini via AI Studio session.

NOTE: This mirrors the qwenchat/boltchat pattern. What is captured from the
browser is a **session**, not an "API key". A Gemini API key can only be created
manually in AI Studio (https://aistudio.google.com/apikey); it cannot be extracted
from cookies. This module calls Gemini's internal endpoint using a browser
session and exposes it as OpenAI-compatible endpoints on your local server.

The AI Studio internal endpoint is undocumented and may change; the streaming
transport in client.py is a scaffold marked with REVIEW that must be validated
against the live site before it will stream real answers.
"""

__version__ = "0.1.0"
