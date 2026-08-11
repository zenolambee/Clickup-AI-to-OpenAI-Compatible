"""Playwright-backed chat for Arena AI.

arena.ai protects /nextjs-api/stream/create-evaluation with Turnstile/recaptcha,
so direct HTTP chat from the proxy is blocked. Running the real UI in a
headless browser lets the challenge complete normally and returns the answer.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_BROWSER = None
_CTX = None
_PAGE = None
_LOCK = asyncio.Lock()
_COOKIE: str = ""


def set_cookie(cookie: str) -> None:
    global _COOKIE
    _COOKIE = cookie


def _parse_cookies(cookie_line: str) -> list[dict[str, str]]:
    out = []
    for piece in cookie_line.split(";"):
        piece = piece.strip()
        if "=" in piece:
            k, _, v = piece.partition("=")
            out.append({"name": k, "value": v, "domain": "arena.ai", "path": "/"})
    return out


async def _ensure_page():
    global _BROWSER, _CTX, _PAGE
    if _PAGE is not None and not _PAGE.is_closed():
        return _PAGE
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    _BROWSER = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
    _CTX = await _BROWSER.new_context(
        viewport={"width": 1500, "height": 950},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    await _CTX.add_cookies(_parse_cookies(_COOKIE))
    _PAGE = await _CTX.new_page()
    resp = await _PAGE.goto("https://arena.ai/direct", wait_until="domcontentloaded", timeout=60000)
    log.info("arena /direct status=%s", resp.status if resp else None)
    await _PAGE.wait_for_timeout(5500)
    return _PAGE


async def browser_ask(prompt: str, *, model: str | None = None, timeout_s: float = 150.0) -> str:
    """Send prompt through the Arena UI and return the model answer text."""
    async with _LOCK:
        page = await _ensure_page()
        try:
            await page.goto("https://arena.ai/direct", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(6000)
        except Exception:
            pass
        ta = page.locator('textarea[placeholder*="Ask anything"]').first
        await ta.click()
        await ta.fill(prompt)
        await page.keyboard.press("Enter")
        body = await page.evaluate("document.body.innerText")
        deadline = asyncio.get_event_loop().time() + timeout_s
        prev_len = len(body)
        stable = 0
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(3)
            body = await page.evaluate("document.body.innerText")
            has_answer = "Response provided by" in body
            if has_answer:
                raw = _clean_answer(body)
                if len(raw) >= 8:
                    # ensure generation finished
                    if "Stop" not in body and "Generating" not in body:
                        if raw != _clean_answer(prev_body if 'prev_body' in dir() else body):
                            stable = 0
                        else:
                            stable += 1
                        if stable >= 2:
                            return raw
                prev_body = body
            if len(body) != prev_len:
                prev_len = len(body)
                stable = 0
            else:
                stable += 1
        body = await page.evaluate("document.body.innerText")
        raw = _clean_answer(body)
        if raw:
            return raw
        raise TimeoutError("arena browser chat did not return an answer")


def _clean_answer(raw: str) -> str:
    """Strip Arena UI chrome and return the newest assistant answer."""
    # Locate latest 'Response provided by' block FIRST
    idx_prov = raw.rfind("Response provided by")
    if idx_prov == -1:
        return ""
    raw = raw[idx_prov:]
    # cut at next new "User:" or footer
    for marker in ("\nUser:", "\n\nAdd files", "\nAdd files", "Inputs are processed"):
        idx = raw.find(marker)
        if idx != -1:
            raw = raw[:idx]
            break
    lines = raw.splitlines()
    out = []
    skipping = True
    for ln in lines:
        t = ln.strip()
        if t.startswith("Response provided by"):
            skipping = True
            continue
        if skipping:
            # skip provider name line (Google/OpenAI/...), and "Python" header
            if t and t not in ("Google", "OpenAI", "Anthropic", "xAI", "Meta",
                               "DeepSeek", "Qwen", "Mistral", "Gemini", "Python"):
                skipping = False
            else:
                if t == "":
                    continue
                continue
        out.append(ln)
    final = "\n".join(out).strip()
    while final and final[-1] in " \n\t\r":
        final = final[:-1]
    if final and final[-1] in ".,;:":
        final = final[:-1]
    return final


def fallback(raw: str) -> str:
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines[-1] if lines else ""
async def close() -> None:
    global _BROWSER, _CTX, _PAGE
    for obj in (_PAGE, _CTX, _BROWSER):
        if obj is not None:
            try:
                await obj.close()
            except Exception:
                pass
    _PAGE = _CTX = _BROWSER = None
