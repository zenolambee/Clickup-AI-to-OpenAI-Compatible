import asyncio, re, sys
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_LINE = re.search(r'^ARENACHAT_COOKIE=(.*)$', Path('/root/Clickup-AI-to-OpenAI-Compatible/arenachat/.env').read_text(), re.M).group(1).strip()
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.2-codex"
PROMPT = "Write a Python function solve(a,b,c) that finds all integer solutions to linear Diophantine equation ax+by=c, returns generator. Include unit tests."

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width':1500,'height':950},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        cookies = [{'name': k, 'value': v, 'domain': 'arena.ai', 'path': '/'} for k, v in [(pr.split('=',1)[0], pr.split('=',1)[1]) for pr in [t.strip() for t in COOKIE_LINE.split(';') if '=' in t]]]
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        page.on('response', lambda r: print('RESP', r.status, r.url.split('arena.ai')[-1][:80]) if 'create-evaluation' in r.url else None)
        await page.goto('https://arena.ai/direct', wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(6000)
        # buka dropdown
        btns = page.locator('button:has-text("Max")')
        n = await btns.count()
        for i in range(n):
            if await btns.nth(i).is_visible():
                await btns.nth(i).click()
                print('dropdown opened')
                break
        await page.wait_for_timeout(1500)
        # cari input search di menu
        inputs = page.locator('input')
        ni = await inputs.count()
        print('inputs:', ni)
        for i in range(ni):
            inp = inputs.nth(i)
            if await inp.is_visible():
                ph = await inp.get_attribute('placeholder')
                print('input', i, 'ph=', ph)
        # ketik 'codex' pada input pertama visible / focus
        try:
            input_vis = page.locator('input:visible').first
            await input_vis.click()
            await input_vis.fill('codex')
            print('typed codex')
        except Exception as e:
            print('input fail:', e)
        await page.wait_for_timeout(1500)
        body = await page.evaluate('document.body.innerText')
        hits = [ln.strip() for ln in body.splitlines() if 'codex' in ln.lower()]
        print('codex lines:', hits[:10])
        # klik option yang mengandung 'codex'
        opt = page.locator(f'text=/.*codex.*/i').first
        try:
            await opt.click(timeout=6000)
            print('clicked', await opt.inner_text())
        except Exception as e:
            print('opt fail:', e)
            await page.screenshot(path='/tmp/arena_noopt.png')
            await browser.close(); return
        await page.wait_for_timeout(1200)
        # isi prompt & kirim
        ta = page.locator('textarea[placeholder*="Ask anything"]').first
        await ta.click(); await ta.fill(PROMPT); await page.keyboard.press('Enter')
        print('sent')
        ans = ''
        for i in range(45):
            await page.wait_for_timeout(4000)
            body = await page.evaluate('document.body.innerText')
            if 'def ' in body and ('```' in body or 'tests' in body.lower()):
                ans = body; break
            if i % 3 == 0:
                print('wait', (i+1)*4, 's', len(body))
        if not ans:
            ans = await page.evaluate('document.body.innerText')
        await page.screenshot(path='/tmp/arena_codex_ans.png')
        print('\n===== ANSWER =====\n', ans[-2600:])
        await browser.close()

asyncio.run(main())
