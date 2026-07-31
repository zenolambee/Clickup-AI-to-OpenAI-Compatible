from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from grokchat.bootstrap import bootstrap_from_cookie

log = logging.getLogger(__name__)

ENV_TEMPLATE = """# GrokChat — OpenAI-compatible proxy for Grok
GROKCHAT_API_KEY={api_key}
GROKCHAT_HOST={host}
GROKCHAT_PORT={port}
GROKCHAT_ACCOUNT={account}
GROKCHAT_DEFAULT_MODEL=grok-3

# --- Cookie Auth (isi salah satu: individual atau full cookies) ---

# Opsi A: Isi masing-masing cookie (recommended)
GROKCHAT_SSO=
GROKCHAT_SSO_RW=
GROKCHAT_X_USERID=

# Opsi B: Full cookie string (copy all dari DevTools)
# GROKCHAT_COOKIES=
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
    account_path = account_path or Path("grok_account.json")

    if not cookies:
        print("\n=== GrokChat Setup ===\n")
        print("To get your Grok cookies:")
        print("  1. Open https://grok.com in your browser")
        print("  2. Open DevTools → Application → Cookies → https://grok.com")
        print("  3. Right-click → Copy All (or copy the full cookie string)")
        print()
        cookies = await _prompt("Paste your grok.com cookies", "")

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
        api_key = await _prompt("API key for clients", "sk-grokchat")
    if not host:
        host = await _prompt("Bind host", "127.0.0.1")
    if port is None:
        port_str = await _prompt("Port", "1996")
        port = int(port_str) if port_str.isdigit() else 1996

    env_content = ENV_TEMPLATE.format(
        api_key=api_key,
        host=host,
        port=port,
        account=account_path.name,
    )
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(env_content, encoding="utf-8")
    print(f"\nSaved .env to {env_path}")
    print(f"\nStart the server:\n  python -m grokchat serve\n")
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
