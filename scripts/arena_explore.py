import asyncio, re, json
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_LINE = re.search(
    r'^ARENACHAT_COOKIE=(.*)$',
    Path('/root/Clickup-AI-to-OpenAI-Compatible/arenachat/.env').read_text(),
    re.M,
).group(1).strip()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width':1400,'height':900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        parts = [t.strip() for t in COOKIE_LINE.split(';') if t.strip()]
        namevals = []
        for pr in parts:
            if '=' in pr:
                k, v = pr.split('=', 1)
                namevals.append((k, v))
        # arena has cookie domain arena.ai
        cookies = [{'name': k, 'value': v, 'domain': 'arena.ai', 'path': '/'} for k, v in namevals]
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        page.on('console', lambda msg: print('CONSOLE:', msg.type, msg.text[:200]))
        print('goto direct...')
        resp = await page.goto('https://arena.ai/direct', wait_until='domcontentloaded', timeout=60000)
        print('status:', resp.status if resp else None)
        await page.wait_for_timeout(8000)
        print('title:', await page.title())
        # dump textarea/input & buttons
        textareas = await page.locator('textarea').count()
        inputs = await page.locator('input').count()
        buttons = await page.locator('button').count()
        print('textareas:', textareas, 'inputs:', inputs, 'buttons:', buttons)
        for i in range(min(textareas, 5)):
            ta = page.locator('textarea').nth(i)
            ph = await ta.get_attribute('placeholder')
            print('TA', i, 'placeholder=', ph, 'visible=', await ta.is_visible())
        # dump some model-ish UI text
        body_text = await page.evaluate('document.body.innerText')
        print('BODY SNIPPET:\n', body_text[:1500])
        await page.screenshot(path='/tmp/arena_ui.png', full_page=False)
        await browser.close()

asyncio.run(main())
