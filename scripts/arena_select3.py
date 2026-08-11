import asyncio, re
from pathlib import Path
from playwright.async_api import async_playwright
COOKIE_LINE = re.search(r'^ARENACHAT_COOKIE=(.*)$', Path('/root/Clickup-AI-to-OpenAI-Compatible/arenachat/.env').read_text(), re.M).group(1).strip()
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width':1500,'height':950})
        cookies = [{'name': k, 'value': v, 'domain': 'arena.ai', 'path': '/'} for k, v in [(pr.split('=',1)[0], pr.split('=',1)[1]) for pr in [t.strip() for t in COOKIE_LINE.split(';') if '=' in t]]]
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        await page.goto('https://arena.ai/direct', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(5000)
        btns = page.locator('button:has-text("Max")')
        for i in range(await btns.count()):
            if await btns.nth(i).is_visible():
                await btns.nth(i).click(); break
        await page.wait_for_timeout(1500)
        inv = page.locator('input:visible').first
        await inv.click()
        await inv.type('gpt-5.2-codex', delay=120)
        await page.wait_for_timeout(3000)
        body = await page.evaluate('document.body.innerText')
        print('BODY tail:\n', body[-1400:])
        for sel in ['[role="option"]', '[role="menuitem"]', 'li']:
            n = await page.locator(sel).count()
            if n:
                print('sel', sel, 'n', n)
                for j in range(min(n, 10)):
                    try:
                        print('  ', (await page.locator(sel).nth(j).inner_text())[:60])
                    except Exception:
                        pass
        await page.screenshot(path='/tmp/arena_typed.png')
        await browser.close()
asyncio.run(main())
