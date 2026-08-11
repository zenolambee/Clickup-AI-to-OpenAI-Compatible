import asyncio, re
from pathlib import Path
from playwright.async_api import async_playwright
COOKIE_LINE = re.search(r'^ARENACHAT_COOKIE=(.*)$', Path('arenachat/.env').read_text(), re.M).group(1).strip()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width':1500,'height':950})
        cookies = [{'name': k, 'value': v, 'domain': 'arena.ai', 'path': '/'} for pr in [t.strip() for t in COOKIE_LINE.split(';') if '=' in t] for k, v in [pr.split('=',1)]]
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        await page.goto('https://arena.ai/direct', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(6000)
        btns = page.locator('button:has-text("Max")')
        for i in range(await btns.count()):
            if await btns.nth(i).is_visible():
                await btns.nth(i).click(); break
        await page.wait_for_timeout(1800)
        # klik Text tab
        try:
            tt = page.locator('button:has-text("Text")').first
            if await tt.is_visible():
                await tt.click()
                await page.wait_for_timeout(2000)
                print('Text tab clicked')
        except Exception as e:
            print('tab err', e)
        # ketik 'claude' di search
        try:
            inv = page.locator('input:visible').first
            await inv.click()
            await inv.type('claude', delay=80)
            await page.wait_for_timeout(4000)
            print('typed claude')
        except Exception as e:
            print('input err', e)
        # dump semua elemen dengan teks mengandung claude (berbagai selector)
        seen = set()
        for sel in ['[role="option"]', '[role="menuitem"]', 'li', 'button', '[class*="item"]', '[class*="option"]']:
            loc = page.locator(sel)
            n = await loc.count()
            for j in range(min(n, 120)):
                try:
                    t = (await loc.nth(j).inner_text()).strip()
                except Exception:
                    continue
                if t and t not in seen:
                    seen.add(t)
        hits = [t for t in seen if 'claude' in t.lower()]
        print('claude option texts:', hits[:30])
        # juga cari elemen apa pun yang mengandung claude
        els = page.locator('text=/claude/i')
        print('locator count:', await els.count())
        for j in range(min(await els.count(), 25)):
            try:
                print('  elem:', (await els.nth(j).inner_text())[:60])
            except Exception:
                pass
        await page.screenshot(path='/tmp/arena_claude_menu.png')
        await b.close()
asyncio.run(main())
