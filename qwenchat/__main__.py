from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from qwenchat.bootstrap import bootstrap_from_token
from qwenchat.config import load_settings
from qwenchat.openai_api import create_app
from qwenchat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("QWENCHAT_HOME", "").strip()
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
            token=args.token,
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            force=args.force,
            yes=args.yes,
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    token = args.token
    if token == "-":
        token = sys.stdin.read().strip()
    if not token:
        print("Error: provide --token or pipe token via stdin", file=sys.stderr)
        return 1

    async def run() -> None:
        acc = await bootstrap_from_token(
            token,
            account_path=args.account,
        )
        print(f"Saved Qwen account for user {acc.user_name or acc.user_id}")
        print(f"  file: {args.account}")

    asyncio.run(run())
    return 0


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("qwenchat", "qwenchat.exe", "qwenchat.cmd", "qwenchat.bat", "qwen"):
        return "qwenchat"
    if base.startswith("qwenchat"):
        return "qwenchat"
    return "qwenchat"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="QwenChat — OpenAI-compatible API for Qwen")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: token -> account file -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--account", default="qwen_account.json", help="Output account file path")
    setup_p.add_argument("--token", default=None, help="Skip token prompt and use this value")
    setup_p.add_argument("--api-key", default=None, help="API key for QWENCHAT_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for QWENCHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for QWENCHAT_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    init_p = sub.add_parser("init", help="Bootstrap qwen_account.json from token")
    init_p.add_argument("--token", required=True, help='Qwen JWT token from Local Storage, or "-" for stdin')
    init_p.add_argument("--account", default="qwen_account.json", help="Output account file path")
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
