from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from gemini.bootstrap import bootstrap_from_cookie

log = logging.getLogger(__name__)

ENV_TEMPLATE = """# GeminiChat — OpenAI-compatible proxy for Google Gemini
GEMINICHAT_API_KEY={api_key}
GEMINICHAT_HOST={host}
GEMINICHAT_PORT={port}
GEMINICHAT_ACCOUNT={account}
GEMINICHAT_DEFAULT_MODEL=gemini-2.0-flash

# Get your Gemini cookies:
# 1. Open https://gemini.google.com in your browser
# 2. Open DevTools (F12) → Application → Cookies → https://gemini.google.com
# 3. Copy the full cookie string (must include __Secure-1PSID)
# 4. Paste it below (or run: python -m gemini init --cookies "...")
GEMINICHAT_COOKIES=
"""


async def _prompt(question: str, default: str = "") -> str:
    prompt_text = f"{question} [{default}]: " if default else f"{question}: "
    loop = asyncio.get_running_loop()
    value = await loop.run_in_executor(None, input, prompt_text)
    value = value.strip()
    return value if value else default


def _ask_bool(question: str, default: bool = False) -> bool:
    prompt = f"{question} ({'Y/n' if default else 'y/N'}): "
    value = input(prompt).strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "1")


async def run_interactive_setup(
    *,
    env_path: Path | None = None,
    account_path: Path | None = None,
    cookies: str | None = None,
    api_key: str | None = None,
    host: str | None = None,
    port: int | None = None,
    force: bool = False,
    yes: bool = False,
) -> int:
    env_path = env_path or Path(".env")
    account_path = account_path or Path("gemini_account.json")

    if not cookies:
        print("\n=== GeminiChat Setup ===\n")
        print("To get your Gemini cookies:")
        print("  1. Open https://gemini.google.com in your browser")
        print("  2. Open DevTools \u2192 Application \u2192 Cookies \u2192 https://gemini.google.com")
        print("  3. Copy the full cookie string (must include __Secure-1PSID)")
        print()
        cookies = await _prompt("Paste your gemini.google.com cookies", "")

    if not cookies:
        print("Error: cookies are required", file=__import__("sys").stderr)
        return 1

    try:
        acc = await bootstrap_from_cookie(
            cookies,
            account_path=str(account_path),
        )
        print(f"\nAuthenticated as {acc.user_name or acc.user_id}")
        if acc.user_email:
            print(f"  email: {acc.user_email}")
        print(f"  account saved to: {account_path}")
    except Exception as e:
        print(f"Error: authentication failed: {e}", file=__import__("sys").stderr)
        return 1

    if env_path.exists() and not force:
        if yes:
            overwrite = True
        else:
            overwrite = _ask_bool(f"\n.env already exists at {env_path}. Overwrite?", default=False)
        if not overwrite:
            print("Skipping .env")
            return 0

    if not api_key:
        api_key = await _prompt("API key for clients", "sk-geminichat")
    if not host:
        host = await _prompt("Bind host", "127.0.0.1")
    if port is None:
        port_str = await _prompt("Port", "1993")
        port = int(port_str) if port_str.isdigit() else 1993

    env_content = ENV_TEMPLATE.format(
        api_key=api_key,
        host=host,
        port=port,
        account=account_path.name,
    )
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(env_content, encoding="utf-8")
    print(f"\nSaved .env to {env_path}")
    print(f"\nStart the server:\n  python -m gemini serve\n")
    return 0


def run_interactive_setup_sync(
    *,
    env_path: Path | None = None,
    account_path: Path | None = None,
    cookies: str | None = None,
    api_key: str | None = None,
    host: str | None = None,
    port: int | None = None,
    force: bool = False,
    yes: bool = False,
) -> int:
    return asyncio.run(
        run_interactive_setup(
            env_path=env_path,
            account_path=account_path,
            cookies=cookies,
            api_key=api_key,
            host=host,
            port=port,
            force=force,
            yes=yes,
        )
    )
