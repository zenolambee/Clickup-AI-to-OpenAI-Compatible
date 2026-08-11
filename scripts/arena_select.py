import asyncio, re
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_LINE = re.search(r'^ARENACHAT_COOKIE=(.*)$', Path('/root/Clickup-AI-to-OpenAI-Compatible/arenachat/.env').read_text(), re.M).group(1).strip()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width':1500,'height':950},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        cookies = [{'name': k, 'value': v, 'domain': 'arena.ai', 'path': '/'} for k, v in [(pr.split('=',1)[0], pr.split('=',1)[1]) for pr in [t.strip() for t in COOKIE_LINE.split(';') if '=' in t]]]
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        await page.goto('https://arena.ai/direct', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(6000)
        # cari tombol yang memuat "Max"
        btns = page.locator('button:has-text("Max")')
        n = await btns.count()
        print('buttons Max:', n)
        for i in range(n):
            if await btns.nth(i).is_visible():
                await btns.nth(i).click()
                print('clicked visible Max button', i)
                break
        await page.wait_for_timeout(2000)
        body = await page.evaluate('document.body.innerText')
        print('BODY after click (first 2500):')
        print(body[:2500])
        await page.screenshot(path='/tmp/arena_models_menu.png')
        await browser.close()

asyncio.run(main())
