from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from higgsfieldchat.config import load_settings
from higgsfieldchat.openai_api import create_app
from higgsfieldchat.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("HIGGSFIELDCHAT_HOME", "").strip()
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
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            write_cookie_to_env=args.write_cookie if args.write_cookie is not None else None,
            force=args.force,
            yes=args.yes,
        )
    )


def cmd_init(args: argparse.Namespace) -> int:
    from higgsfieldchat.account import HiggsfieldAccount, parse_browser_cookie, save_higgsfield_account

    cookie = args.cookie
    if cookie == "-":
        cookie = sys.stdin.read().strip()
    if not cookie:
        print("Error: provide --cookie or pipe cookie via stdin", file=sys.stderr)
        return 1

    parsed = parse_browser_cookie(cookie)
    __session = parsed.get("__session", "")
    if not __session:
        print("Error: cookie missing __session", file=sys.stderr)
        return 1

    acc = HiggsfieldAccount(
        __session=__session,
        full_cookie=cookie.strip().rstrip(";"),
    )
    save_higgsfield_account(acc, args.account)
    print(f"Saved Higgsfield account to {args.account}")
    return 0


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("higgsfield", "higgsfield.exe", "higgsfield.cmd", "higgsfield.bat"):
        return "higgsfield"
    if base.startswith("higgsfieldchat"):
        return "higgsfieldchat"
    return "higgsfield"


def main(argv: list[str] | None = None) -> None:
    prog = _prog_name()
    parser = argparse.ArgumentParser(prog=prog, description="Higgsfield AI OpenAI-compatible API")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    init_p = sub.add_parser("init", help="Bootstrap higgsfield_account.json from browser cookie")
    init_p.add_argument("--cookie", required=True, help='Full document.cookie string, or "-" for stdin')
    init_p.add_argument("--account", default="higgsfield_account.json", help="Output account file path")
    init_p.set_defaults(func=cmd_init)

    setup_p = sub.add_parser("setup", help="Interactive wizard: cookie -> account file -> .env")
    setup_p.add_argument("--env", default=".env", help="Path to write environment file (default: .env)")
    setup_p.add_argument("--account", default="higgsfield_account.json", help="Output account file path")
    setup_p.add_argument("--cookie", default=None, help="Skip cookie prompt and use this value")
    setup_p.add_argument("--api-key", default=None, help="API key for HIGGSFIELDCHAT_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for HIGGSFIELDCHAT_HOST")
    setup_p.add_argument("--port", default=None, help="Port for HIGGSFIELDCHAT_PORT")
    setup_p.add_argument(
        "--write-cookie",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Store HIGGSFIELD_COOKIE in .env (default: ask interactively)",
    )
    setup_p.add_argument("--force", action="store_true", help="Overwrite .env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        print(
            f"\nFirst, run:\n"
            f"  {prog} setup\n"
            f"Or:\n"
            f"  {prog} init --cookie \"<paste document.cookie from higgsfield.ai>\"\n"
            f"Then start the API server:\n"
            f"  {prog} serve\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()