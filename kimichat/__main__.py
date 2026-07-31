from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from kimichat.account import extract_refresh_token
from kimichat.bootstrap import bootstrap_from_token
from kimichat.config import load_settings
from kimichat.openai_api import create_app
from kimichat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("KIMICHAT_HOME", "").strip()
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
            token=args.refresh_token,
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            force=args.force,
            yes=args.yes,
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    raw = args.refresh_token
    if raw == "-":
        raw = sys.stdin.read().strip()
    if not raw:
        print("Error: provide --refresh-token or pipe it via stdin", file=sys.stderr)
        return 1

    token, cookies = extract_refresh_token(raw)
    if not token:
        print("Error: could not find a refresh_token in the input", file=sys.stderr)
        return 1

    async def run() -> None:
        acc = await bootstrap_from_token(
            token,
            cookies=cookies,
            account_path=args.account,
        )
        print(f"Saved Kimi account for user {acc.user_name or acc.user_id or '(unknown)'}")
        print(f"  file: {args.account}")

    asyncio.run(run())
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="kimichat", description="KimiChat — OpenAI-compatible API for Kimi (kimi.com)"
    )
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: token -> account file -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--account", default="kimi_account.json", help="Output account file path")
    setup_p.add_argument("--refresh-token", default=None, help="Skip prompt and use this refresh_token")
    setup_p.add_argument("--api-key", default=None, help="API key for KIMICHAT_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for KIMICHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for KIMICHAT_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    init_p = sub.add_parser("init", help="Bootstrap kimi_account.json from refresh_token")
    init_p.add_argument(
        "--refresh-token",
        required=True,
        help='Kimi refresh_token from Local Storage, or "-" for stdin',
    )
    init_p.add_argument("--account", default="kimi_account.json", help="Output account file path")
    init_p.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        print(
            "\nNew here? Run the interactive setup wizard:\n"
            "  kimichat setup\n"
            "Or start the API server:\n"
            "  kimichat serve\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
