from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from arenachat.config import load_settings
from arenachat.openai_api import create_app


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("ARENACHAT_HOME", "").strip()
    if home:
        os.chdir(Path(home).expanduser().resolve())
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
    return 0


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

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        print(
            f"\nFirst, set up your credentials:\n"
            f"  1. Copy your arena.ai cookie from browser DevTools\n"
            f"  2. Create .env file with ARENACHAT_COOKIE=\"...\"\n"
            f"\nThen start the server:\n"
            f"  {prog} serve\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
