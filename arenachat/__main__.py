from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from arenachat.config import load_settings
from arenachat.openai_api import create_app
from arenachat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("ARENACHAT_HOME", "").strip()
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
            cookie=args.cookie,
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            force=args.force,
            yes=args.yes,
        )
    )


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("arena", "arena.exe", "arena.cmd", "arena.bat"):
        return "arena"
    if base.startswith("arenachat"):
        return "arenachat"
    return "arena"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="Arena AI OpenAI-compatible API")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: cookie -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--cookie", default=None, help="Skip cookie prompt and use this value")
    setup_p.add_argument("--api-key", default=None, help="API key for ARENACHAT_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for ARENACHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for ARENACHAT_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

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
