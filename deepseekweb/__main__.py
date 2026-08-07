from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from deepseekweb.account import DeepSeekWebAccount, save_deepseek_account
from deepseekweb.config import load_settings
from deepseekweb.openai_api import create_app
from deepseekweb.setup_cli import run_interactive_setup


def cmd_serve(_: argparse.Namespace) -> int:
    home = os.getenv("DEEPSEEKWEB_HOME", "").strip()
    if home:
        os.chdir(Path(home).expanduser().resolve())
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    token = args.token
    if token == "-":
        token = sys.stdin.read().strip()
    if not token:
        print("Error: provide --token or pipe token via stdin", file=sys.stderr)
        return 1
    acc = DeepSeekWebAccount(user_token=token.strip(), ds_session_id=(args.ds_session_id or "").strip())
    save_deepseek_account(acc, args.account)
    print(f"Saved DeepSeek account to {args.account}")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    return run_interactive_setup(
        env_path=Path(args.env) if args.env else None,
        account_path=Path(args.account) if args.account else None,
        token=args.token,
        ds_session_id=args.ds_session_id,
        api_key=args.api_key,
        host=args.host,
        port=args.port,
        force=args.force,
        yes=args.yes,
    )


def _prog_name() -> str:
    base = Path(sys.argv[0]).name.lower()
    if base in ("deepseekweb", "deepseekweb.exe", "deepseekweb.cmd", "deepseekweb.bat"):
        return "deepseekweb"
    return "deepseekweb"


def main(argv: list[str] | None = None) -> None:
    prog = "deepseekweb"
    parser = argparse.ArgumentParser(prog=prog, description="DeepSeek web (chat.deepseek.com) OpenAI-compatible API")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start OpenAI-compatible API server")
    serve_p.set_defaults(func=cmd_serve)

    init_p = sub.add_parser("init", help="Bootstrap account from browser localStorage token")
    init_p.add_argument("--token", required=True, help="userToken from chat.deepseek.com localStorage, or \"-\" for stdin")
    init_p.add_argument("--ds-session-id", default=None, help="Optional ds_session_id cookie value")
    init_p.add_argument("--account", default="deepseek_account.json", help="Output account file path")
    init_p.set_defaults(func=cmd_init)

    setup_p = sub.add_parser("setup", help="Interactive wizard: token -> account file -> deepseekweb.env")
    setup_p.add_argument("--env", default="deepseekweb.env", help="Path to write env file (default: deepseekweb.env)")
    setup_p.add_argument("--account", default="deepseek_account.json", help="Output account file path")
    setup_p.add_argument("--token", default=None, help="Skip prompt and use this userToken")
    setup_p.add_argument("--ds-session-id", default=None, help="Optional ds_session_id cookie value")
    setup_p.add_argument("--api-key", default=None, help="Local API key for DEEPSEEKWEB_API_KEY")
    setup_p.add_argument("--host", default=None, help="Bind host for DEEPSEEKWEB_HOST")
    setup_p.add_argument("--port", default=None, help="Port for DEEPSEEKWEB_PORT")
    setup_p.add_argument("--force", action="store_true", help="Overwrite deepseekweb.env without asking")
    setup_p.add_argument("-y", "--yes", action="store_true", help="Accept defaults with minimal prompts")
    setup_p.set_defaults(func=cmd_setup)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        print(
            f"\nFirst, run:\n"
            f"  {prog} init --token \"<userToken from chat.deepseek.com>\"\n"
            f"Or the interactive wizard:\n"
            f"  {prog} setup\n"
            f"Then start the API server:\n"
            f"  {prog} serve\n",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()