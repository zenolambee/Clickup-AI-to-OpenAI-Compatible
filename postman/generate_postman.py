#!/usr/bin/env python3
"""
Postman collection generator for AI Proxy Chat.

Usage:
  python postman/generate_postman.py                    # print all providers
  python postman/generate_postman.py --provider notion   # print one provider
  python postman/generate_postman.py --fetch-models      # fetch models from running servers
  python postman/generate_postman.py --output-dir ./out  # write files instead of print
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROVIDERS = {
    "notionchat": {
        "name": "NotionChat",
        "port": 1994,
        "api_key": "sk-notionchat",
        "default_model": "notion-ai",
        "cmd": "notion serve",
    },
    "qwenchat": {
        "name": "QwenChat",
        "port": 1995,
        "api_key": "sk-qwenchat",
        "default_model": "qwen3.7-plus",
        "cmd": "qwen serve",
    },
    "claudechat": {
        "name": "ClaudeChat",
        "port": 1998,
        "api_key": "sk-claudechat",
        "default_model": "claude-sonnet-4-20250514",
        "cmd": "claude serve",
    },
    "grokchat": {
        "name": "GrokChat",
        "port": 1996,
        "api_key": "sk-grokchat",
        "default_model": "grok-3",
        "cmd": "grok serve",
    },
    "kimichat": {
        "name": "KimiChat",
        "port": 1997,
        "api_key": "sk-kimichat",
        "default_model": "kimi",
        "cmd": "kimi serve",
    },
    "geminichat": {
        "name": "GeminiChat",
        "port": 1997,
        "api_key": "sk-geminichat",
        "default_model": "gemini-2.5-flash",
        "cmd": "geminichat serve",
    },
    "gemini": {
        "name": "Gemini (Standalone)",
        "port": 1993,
        "api_key": "sk-geminichat",
        "default_model": "gemini-2.0-flash",
        "cmd": "python -m gemini serve",
    },
    "boltchat": {
        "name": "BoltChat",
        "port": 1996,
        "api_key": "sk-boltchat",
        "default_model": "bolt-agent",
        "cmd": "bolt serve",
    },
    "higgsfieldchat": {
        "name": "HiggsfieldChat",
        "port": 1992,
        "api_key": "sk-higgsfieldchat",
        "default_model": "supercomputer",
        "cmd": "higgsfield serve",
    },
    "arenachat": {
        "name": "ArenaChat",
        "port": 1998,
        "api_key": "sk-arenachat",
        "default_model": "gpt-4o",
        "cmd": "arena serve",
    },
    "pokeechat": {
        "name": "PokeeChat",
        "port": 1993,
        "api_key": "sk-pokeechat",
        "default_model": "pokee-isaac",
        "cmd": "pokee serve",
    },
    "deepseekchat": {
        "name": "DeepSeekChat",
        "port": 1996,
        "api_key": "sk-deepseekchat",
        "default_model": "deepseek-v4-flash",
        "cmd": "deepseek serve",
    },
    "deepseekweb": {
        "name": "DeepSeekWeb",
        "port": 1997,
        "api_key": "sk-deepseekweb",
        "default_model": "deepseek-v4-flash",
        "cmd": "deepseekweb serve",
    },
}


def build_collection(provider_id: str, info: dict, models: list[str] | None = None) -> dict:
    model = models[0] if models else info["default_model"]
    base_url = f"http://127.0.0.1:{info['port']}"

    return {
        "info": {
            "name": info["name"],
            "description": (
                f"OpenAI-compatible API for {info['name']}.\n\n"
                f"1. Import `{info['name'].replace(' ', '')}.local.postman_environment.json`\n"
                f"2. Select the environment\n"
                f"3. Run `{info['cmd']}`\n"
                f"4. Send requests\n\n"
                f"Models: {', '.join(models) if models else info['default_model']}"
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{api_key}}", "type": "string"}],
        },
        "item": [
            {
                "name": "Health",
                "item": [
                    {
                        "name": "Healthz",
                        "request": {
                            "auth": {"type": "noauth"},
                            "method": "GET",
                            "header": [],
                            "url": "{{base_url}}/healthz",
                        },
                    }
                ],
            },
            {
                "name": "Models",
                "item": [
                    {
                        "name": "List Models",
                        "request": {
                            "method": "GET",
                            "header": [],
                            "url": "{{base_url}}/v1/models",
                        },
                    }
                ],
            },
            {
                "name": "Chat",
                "item": [
                    {
                        "name": "Chat Completions",
                        "request": {
                            "method": "POST",
                            "header": [{"key": "Content-Type", "value": "application/json"}],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps(
                                    {
                                        "model": "{{model}}",
                                        "user": "{{session_id}}",
                                        "stream": False,
                                        "messages": [{"role": "user", "content": "What are you?"}],
                                    },
                                    indent=2,
                                ),
                                "options": {"raw": {"language": "json"}},
                            },
                            "url": "{{base_url}}/v1/chat/completions",
                        },
                    },
                    {
                        "name": "Chat Completions (stream)",
                        "request": {
                            "method": "POST",
                            "header": [
                                {"key": "Content-Type", "value": "application/json"},
                                {"key": "Accept", "value": "text/event-stream"},
                            ],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps(
                                    {
                                        "model": "{{model}}",
                                        "user": "{{session_id}}",
                                        "stream": True,
                                        "messages": [
                                            {"role": "user", "content": "Say hello in one short sentence."}
                                        ],
                                    },
                                    indent=2,
                                ),
                                "options": {"raw": {"language": "json"}},
                            },
                            "url": "{{base_url}}/v1/chat/completions",
                        },
                    },
                    {
                        "name": "Chat Completions (with system)",
                        "request": {
                            "method": "POST",
                            "header": [{"key": "Content-Type", "value": "application/json"}],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps(
                                    {
                                        "model": "{{model}}",
                                        "user": "{{session_id}}",
                                        "stream": False,
                                        "messages": [
                                            {"role": "system", "content": "You are a helpful assistant. Keep answers short."},
                                            {"role": "user", "content": "Explain JSON in 2 sentences."},
                                        ],
                                    },
                                    indent=2,
                                ),
                                "options": {"raw": {"language": "json"}},
                            },
                            "url": "{{base_url}}/v1/chat/completions",
                        },
                    },
                ],
            },
        ],
        "variable": [
            {"key": "base_url", "value": base_url},
            {"key": "api_key", "value": info["api_key"]},
            {"key": "model", "value": model},
            {"key": "session_id", "value": f"{provider_id}-session-1"},
        ],
    }


def build_environment(provider_id: str, info: dict) -> dict:
    return {
        "name": f"{info['name']} Local",
        "values": [
            {"key": "base_url", "value": f"http://127.0.0.1:{info['port']}", "type": "default"},
            {"key": "api_key", "value": info["api_key"], "type": "secret"},
            {"key": "model", "value": info["default_model"], "type": "default"},
            {"key": "session_id", "value": f"{provider_id}-session-1", "type": "default"},
        ],
    }


def fetch_models(base_url: str, api_key: str) -> list[str]:
    import urllib.request

    req = urllib.request.Request(f"{base_url}/v1/models", headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"  [!] Failed to fetch models: {e}", file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser(description="Generate Postman collections for AI Proxy Chat")
    parser.add_argument("--provider", "-p", choices=list(PROVIDERS.keys()) + ["all"], default="all")
    parser.add_argument("--fetch-models", "-f", action="store_true", help="Fetch models from running servers")
    parser.add_argument("--output-dir", "-o", type=str, help="Write output files to directory")
    args = parser.parse_args()

    providers = PROVIDERS.items() if args.provider == "all" else [(args.provider, PROVIDERS[args.provider])]

    for provider_id, info in providers:
        models = None
        if args.fetch_models:
            base_url = f"http://127.0.0.1:{info['port']}"
            print(f"  Fetching models from {provider_id} ({base_url})...", file=sys.stderr)
            models = fetch_models(base_url, info["api_key"])
            if models:
                print(f"    Found {len(models)} models", file=sys.stderr)
                info["default_model"] = models[0]

        collection = build_collection(provider_id, info, models)
        environment = build_environment(provider_id, info)

        safe_name = info["name"].replace(" ", "").replace("(", "").replace(")", "")
        coll_name = f"{safe_name}.postman_collection.json"
        env_name = f"{safe_name}.local.postman_environment.json"

        if args.output_dir:
            out_dir = Path(args.output_dir) / provider_id
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / coll_name).write_text(json.dumps(collection, indent=2))
            (out_dir / env_name).write_text(json.dumps(environment, indent=2))
            print(f"  Wrote {out_dir / coll_name}")
            print(f"  Wrote {out_dir / env_name}")
        else:
            print(f"\n=== {info['name']} ===")
            print(json.dumps(collection, indent=2))
            print("---")
            print(json.dumps(environment, indent=2))


if __name__ == "__main__":
    main()