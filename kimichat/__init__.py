"""KimiChat — OpenAI-compatible API for Kimi (kimi.com / Moonshot) via cookie/token auth.

Educational / unofficial. Mirrors the qwenchat package pattern in this repo:
a small FastAPI proxy that speaks the OpenAI Chat Completions protocol while
routing requests to Kimi's internal web API using your browser session
(refresh_token / access_token taken from kimi.com).
"""

__version__ = "0.1.0"
