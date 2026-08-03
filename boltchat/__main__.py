from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from boltchat.bootstrap import bootstrap_from_session
from boltchat.config import load_settings
from boltchat.openai_api import create_app
from boltchat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("BOLTCHAT_HOME", os.getenv("QWENCHAT_HOME", "")).strip()
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
            session_token=args.session_token,
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            force=args.force,
            yes=args.yes,
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    cookie = args.cookie
    session_token = args.session_token
    if cookie in ("-", "--"):
        cookie = sys.stdin.read().strip()
    if not (cookie or session_token):
        print("Error: provide --cookie or --session-token", file=sys.stderr)
        return 1

    async def run() -> None:
        acc = await bootstrap_from_session(
            cookie,
            session_token=session_token,
            account_path=args.account,
        )
        print(f"Saved Bolt account for user {acc.user_name or acc.user_id or '(unknown)'}")
        print(f"  file: {args.account}")

    asyncio.run(run())
    return 0


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("boltchat", "boltchat.exe", "boltchat.cmd", "boltchat.bat", "bolt"):
        return "boltchat"
    return "boltchat"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="BoltChat — OpenAI-compatible API for Bolt.new")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: session -> account file -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--account", default="bolt_account.json", help="Output account file path")
    setup_p.add_argument("--cookie", default=None, help="Skip session prompt and use this cookie value")
    setup_p.add_argument("--session-token", default=None, help="StackBlitz session token")
    setup_p.add_argument("--api-key", default=None, help="API key for BOLTCHAT_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for BOLTCHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for BOLTCHAT_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    init_p = sub.add_parser("init", help="Bootstrap bolt_account.json from cookie/session")
    init_p.add_argument("--cookie", default="", help='Cookie from bolt.new document.cookie, or "-" for stdin')
    init_p.add_argument("--session-token", default="", help="StackBlitz session token")
    init_p.add_argument("--account", default="bolt_account.json", help="Output account file path")
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
