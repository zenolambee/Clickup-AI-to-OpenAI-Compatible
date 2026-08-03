from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from geminichat.bootstrap import bootstrap_from_session
from geminichat.config import load_settings
from geminichat.openai_api import create_app
from geminichat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("GEMINICHAT_HOME", os.getenv("QWENCHAT_HOME", "")).strip()
    if home:
        os.chdir(Path(home).expanduser().resolve())
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    return asyncio.run(
        run_interactive_setup(
            env_path=Path(args.env) if args.env else None,
            account_path=Path(args.account) if args.account else None,
            cookie=args.cookie,
            sapisid=args.sapisid,
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            force=args.force,
            yes=args.yes,
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    cookie = args.cookie
    sapisid = args.sapisid
    if cookie in ("-", "--"):
        cookie = sys.stdin.read().strip()
    if not (cookie or sapisid):
        print("Error: provide --cookie or --sapisid", file=sys.stderr)
        return 1

    async def run() -> None:
        acc = await bootstrap_from_session(
            cookie,
            sapisid=sapisid,
            account_path=args.account,
        )
        print(f"Saved Gemini account (email={acc.user_email or 'unknown'})")
        print(f"  file: {args.account}")

    asyncio.run(run())
    return 0


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("geminichat", "geminichat.exe", "geminichat.cmd", "geminichat.bat", "gemini"):
        return "geminichat"
    return "geminichat"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="GeminiChat — OpenAI-compatible API for Google Gemini")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: session -> account file -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--account", default="gemini_account.json", help="Output account file path")
    setup_p.add_argument("--cookie", default=None, help="Skip session prompt and use this cookie value")
    setup_p.add_argument("--sapisid", default=None, help="SAPISID token from cookie/localStorage")
    setup_p.add_argument("--api-key", default=None, help="API key for GEMINICHAT_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for GEMINICHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for GEMINICHAT_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    init_p = sub.add_parser("init", help="Bootstrap gemini_account.json from cookie/SAPISID")
    init_p.add_argument("--cookie", default="", help='Cookie from aistudio.google.com, or "-" for stdin')
    init_p.add_argument("--sapisid", default="", help="SAPISID token")
    init_p.add_argument("--account", default="gemini_account.json", help="Output account file path")
    init_p.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        print(
            f"\nNew here? Run the interactive setup wizard:\n"
            f"  {prog} setup\n"
            f"Or start the API server:\n"
            f"  {prog} serve\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
