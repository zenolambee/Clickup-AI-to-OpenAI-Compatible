from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from grokchat.bootstrap import bootstrap_from_cookie
from grokchat.config import load_settings
from grokchat.openai_api import create_app
from grokchat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("GROKCHAT_HOME", "").strip()
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
            cookies=args.cookies,
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

    async def run() -> None:
        acc = await bootstrap_from_cookie(
            cookies,
            account_path=args.account,
        )
        print(f"Saved Grok account for user {acc.user_name or acc.user_id}")
        if acc.user_email:
            print(f"  email: {acc.user_email}")
        print(f"  file: {args.account}")

    asyncio.run(run())
    return 0


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("grokchat", "grokchat.exe", "grokchat.cmd", "grokchat.bat", "grok"):
        return "grokchat"
    if base.startswith("grokchat"):
        return "grokchat"
    return "grokchat"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="GrokChat — OpenAI-compatible API for Grok")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: cookies -> account file -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--account", default="grok_account.json", help="Output account file path")
    setup_p.add_argument("--cookies", default=None, help="Skip cookies prompt and use this value")
    setup_p.add_argument("--api-key", default=None, help="API key for GROKCHAT_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for GROKCHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for GROKCHAT_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    init_p = sub.add_parser("init", help="Bootstrap grok_account.json from browser cookies")
    init_p.add_argument("--cookies", required=True, help='Full document.cookie string, or "-" for stdin')
    init_p.add_argument("--account", default="grok_account.json", help="Output account file path")
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
