from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn

from deepseekchat.config import load_settings
from deepseekchat.openai_api import create_app
from deepseekchat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("DEEPSEEKCHAT_HOME", "").strip()
    if home:
        os.chdir(Path(home).expanduser().resolve())
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    return run_interactive_setup(
        env_path=Path(args.env) if args.env else None,
        api_key=args.api_key,
        deepseek_api_key=args.deepseek_api_key,
        host=args.host,
        port=args.port,
        force=args.force,
        yes=args.yes,
    )


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("deepseek", "deepseek.exe", "deepseek.cmd", "deepseek.bat"):
        return "deepseek"
    if base.startswith("deepseekchat"):
        return "deepseekchat"
    return "deepseekchat"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="DeepSeek OpenAI-compatible API")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    setup_p = sub.add_parser("setup", help="Interactive wizard: API key -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--api-key", default=None, help="Local API key for DEEPSEEKCHAT_API_KEY")
    setup_p.add_argument("--deepseek-api-key", default=None, help="Your DeepSeek key (DEEPSEEK_API_KEY, starts with sk-)")
    setup_p.add_argument("--host", default=None, help="Bind host for DEEPSEEKCHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for DEEPSEEKCHAT_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        print(
            f"\nFirst, run:\n"
            f"  {prog} setup\n"
            f"Then start the API server:\n"
            f"  {prog} serve\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()