"""BoltChat — OpenAI-compatible API for Bolt.new via browser session auth.

NOTE: Bolt.new's AI backend is proprietary and private. This module provides a
complete OpenAI-compatible HTTP surface plus a client that targets the *known*
StackBlitz session/streaming surface. Because Bolt's internal chat protocol is
undocumented and may change, the transport in client.py is a scaffold that must
be validated/refined against the live site before it will actually stream.
"""

__version__ = "0.1.0"
