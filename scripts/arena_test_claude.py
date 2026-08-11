import asyncio, re, sys
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_LINE = re.search(r'^ARENACHAT_COOKIE=(.*)$', Path('arenachat/.env').read_text(), re.M).group(1).strip()
MODEL = "claude-opus-5"
PROMPT = "Write a Python function that merges two sorted lists into one sorted list efficiently. Return only the code."

def clean(raw: str) -> str:
    idx = raw.rfind("Response provided by")
    if idx == -1:
        return ""
    raw = raw[idx:]
    for marker in ("\nUser:", "\n\nAdd files", "\nAdd files", "Inputs are processed"):
        i = raw.find(marker)
        if i != -1:
            raw = raw[:i]
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
            if t and t not in ("Google", "OpenAI", "Anthropic", "xAI", "Meta", "DeepSeek", "Qwen", "Mistral", "Gemini", "Python"):
                skipping = False
            else:
                continue
        out.append(ln)
    return "\n".join(out).strip()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width':1500,'height':950},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        cookies = []
        for pr in [t.strip() for t in COOKIE_LINE.split(';') if '=' in t]:
            k, v = pr.split('=', 1)
            cookies.append({'name': k, 'value': v, 'domain': 'arena.ai', 'path': '/'})
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        page.on('response', lambda r: print('NET', r.status, r.url.split('arena.ai')[-1][:70]) if ('create-evaluation' in r.url or 'post-to' in r.url) else None)
        await page.goto('https://arena.ai/direct', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(6000)
        sel = None
        # buka dropdown
        btns = page.locator('button:has-text("Max")')
        n = await btns.count()
        for i in range(n):
            if await btns.nth(i).is_visible():
                await btns.nth(i).click()
                print('dropdown opened')
                break
        await page.wait_for_timeout(1500)
        # coba klik tab "Text" jika ada
        text_tab = page.locator('button:has-text("Text")').first
        try:
            if await text_tab.is_visible():
                await text_tab.click()
                print('clicked Text tab')
                await page.wait_for_timeout(1500)
        except Exception:
            pass
        # cari input search
        inv = page.locator('input:visible').first
        try:
            await inv.click()
            await inv.type(MODEL, delay=100)
            print('typed', MODEL)
        except Exception as e:
            print('input fail', e)
        await page.wait_for_timeout(3000)
        # cek opsi
        body = await page.evaluate('document.body.innerText')
        lines_with = [l.strip() for l in body.splitlines() if 'claude' in l.lower()]
        print('claude lines:', lines_with[:8])
        # coba klik opsi yang mengandung 'claude'
        opt = page.locator(f'text=/.*claude.*/i').first
        try:
            await opt.click(timeout=6000)
            print('clicked option:', (await opt.inner_text())[:40])
        except Exception as e:
            print('opt click fail:', e)
            # fallback: tekan Escape lalu pakai default; kirim saja
            await page.keyboard.press('Escape')
        await page.wait_for_timeout(1200)
        # kirim prompt
        ta = page.locator('textarea[placeholder*="Ask anything"]').first
        await ta.click()
        await ta.fill(PROMPT)
        await page.keyboard.press('Enter')
        print('prompt sent')
        # tunggu jawaban
        deadline = asyncio.get_event_loop().time() + 180
        prev = ''
        stable = 0
        answer = ''
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(3)
            body = await page.evaluate('document.body.innerText')
            cur = clean(body)
            if cur and cur != prev:
                prev = cur
                answer = cur
                stable = 0
            elif cur:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
        if not answer:
            answer = clean(await page.evaluate('document.body.innerText'))
        print('\n===== ANSWER =====')
        print(answer[:2500])
        print('\n===== END =====')
        await browser.close()

asyncio.run(main())
