from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from claudechat.bootstrap import bootstrap_from_cookies
from claudechat.config import load_settings
from claudechat.openai_api import create_app
from claudechat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("CLAUDE_HOME", "").strip()
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
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            force=args.force,
            yes=args.yes,
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    cookies = args.cookies
    if cookies == "-":
        cookies = sys.stdin.read().strip()
    if not cookies:
        print("Error: provide --cookies or pipe cookies via stdin", file=sys.stderr)
        return 1

    cookie_list = [c.strip() for c in cookies.split("||") if c.strip()]
    if not cookie_list:
        print("Error: no cookies provided (separate multiple with ||)", file=sys.stderr)
        return 1

    async def run() -> None:
        accounts = await bootstrap_from_cookies(
            cookie_list,
            account_path=args.account,
        )
        print(f"Saved {len(accounts)} Claude account(s)")
        print(f"  file: {args.account}")
        for i, acc in enumerate(accounts):
            print(f"  #{i + 1}: org={acc.organization_id[:16]}... user={acc.user_name or acc.user_id or '?'}")

    asyncio.run(run())
    return 0


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("claudechat", "claudechat.exe", "claudechat.cmd", "claudechat.bat", "claude"):
        return "claudechat"
    if base.startswith("claudechat"):
        return "claudechat"
    return "claudechat"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="ClaudeChat — OpenAI-compatible API for Claude (claude.ai)")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: cookies -> account file -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--account", default="claude_accounts", help="Output accounts directory (default: claude_accounts/)")
    setup_p.add_argument("--api-key", default=None, help="API key for CLAUDE_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for CLAUDE_HOST")
    setup_p.add_argument("--port", default=None, help="Port for CLAUDE_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    init_p = sub.add_parser("init", help="Bootstrap accounts from cookies")
    init_p.add_argument("--cookies", required=True, help='Full cookie string(s), separate multiple with "||", or "-" for stdin')
    init_p.add_argument("--account", default="claude_accounts", help="Output accounts directory (default: claude_accounts/)")
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
