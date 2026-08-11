import asyncio, re, sys
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
        await page.wait_for_timeout(6000)
        btns = page.locator('button:has-text("Max")')
        for i in range(await btns.count()):
            if await btns.nth(i).is_visible():
                await btns.nth(i).click(); break
        await page.wait_for_timeout(2000)
        inv = page.locator('input:visible')
        print('visible inputs:', await inv.count())
        await inv.first.click()
        await inv.first.fill('codex')
        print('typed')
        for t in [2, 3, 5]:
            await page.wait_for_timeout(t*1000)
            # dump items (elemen dengan role option / listitem)
            opts = page.locator('[role="option"]')
            print('opts at', t, 's:', await opts.count())
            for j in range(min(await opts.count(), 8)):
                print('  ', (await opts.nth(j).inner_text())[:40])
            body = await page.evaluate('document.body.innerText')
            lines = [l.strip() for l in body.splitlines() if 'codex' in l.lower() or 'gpt-5.2' in l]
            print('lines codex:', lines[:8])
        await page.screenshot(path='/tmp/arena_filtered.png')
        await browser.close()
asyncio.run(main())
