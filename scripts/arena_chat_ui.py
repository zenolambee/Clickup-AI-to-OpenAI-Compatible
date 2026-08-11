import asyncio, re, json
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_LINE = re.search(
    r'^ARENACHAT_COOKIE=(.*)$',
    Path('/root/Clickup-AI-to-OpenAI-Compatible/arenachat/.env').read_text(),
    re.M,
).group(1).strip()

PROMPT = "Implement in Python a lock-free async counter using asyncio: atomic increment returning new value, safe read, benchmark with 1000 concurrent increments. Return only production-ready code."

async def main():
    events = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width':1500,'height':950},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        cookies = []
        for pr in COOKIE_LINE.split(';'):
            pr = pr.strip()
            if '=' in pr:
                k, v = pr.split('=', 1)
                cookies.append({'name': k, 'value': v, 'domain': 'arena.ai', 'path': '/'})
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        async def on_req(req):
            u = req.url
            if any(x in u for x in ('create-evaluation', 'post-to-evaluation', 'stream/')):
                body = ''
                if req.method == 'POST':
                    try:
                        body = (await req.post_data()) or ''
                    except Exception:
                        body = ''
                events.append(('REQ', req.method, u, body[:500]))
                print('REQ', req.method, u.split('arena.ai')[-1], 'body[:120]=', body[:120])
        async def on_resp(resp):
            u = resp.url
            if any(x in u for x in ('create-evaluation', 'post-to-evaluation', 'stream/')):
                try:
                    txt = await resp.text()
                except Exception:
                    txt = ''
                events.append(('RESP', resp.status, u, txt[:400]))
                print('RESP', resp.status, u.split('arena.ai')[-1], txt[:200])
        page.on('request', on_req)
        page.on('response', on_resp)

        print('goto direct...')
        resp = await page.goto('https://arena.ai/direct', wait_until='domcontentloaded', timeout=60000)
        print('status', resp.status)
        await page.wait_for_timeout(6000)

        # pilih model: klik dropdown area model
        # cari elemen berisi 'Max' di area model
        try:
            # kemungkinan button dropdown model
            sel = page.locator('text=Max').first
            # Hati-hati: banyak "Max"; gunakan yang terlihat dekat header
            visible = page.locator('button:has-text("Max")')
            n = await visible.count()
            print('buttons with Max:', n)
            for i in range(n):
                if await visible.nth(i).is_visible():
                    await visible.nth(i).click()
                    print('clicked Max button', i)
                    break
            await page.wait_for_timeout(1500)
        except Exception as e:
            print('model dropdown select error:', e)

        # dump visible text after dropdown
        body = await page.evaluate('document.body.innerText')
        # cek apakah ada menu pilihan model
        m = re.findall(r'gpt-5\.2-codex|gpt-5\.3-codex|claude-opus|Max', body)
        print('model menu tokens:', m[:10])
        await page.screenshot(path='/tmp/arena_dropdown.png')

        # isi textarea
        ta = page.locator('textarea[placeholder*="Ask anything"]').first
        print('textarea count visible:', await page.locator('textarea:visible').count())
        await ta.click()
        await ta.fill(PROMPT)
        print('filled prompt')
        await page.screenshot(path='/tmp/arena_filled.png')
        # kirim: cari tombol kirim (mungkin button dengan svg/aria-label)
        await page.keyboard.press('Enter')
        print('pressed Enter')
        # Tunggu respons beberapa saat
        for i in range(36):
            await page.wait_for_timeout(5000)
            body = await page.evaluate('document.body.innerText')
            if 'Stop' in body or 'Generating' in body.lower():
                print(f'...generating at {i*5}s')
                continue
            if len(events) > 0:
                print(f'...after {i*5}s events captured')
            # if answer looks present (code blocks)
            if '```' in body or 'def ' in body or len(body) > 3000:
                print('answer-looking content present at', (i+1)*5, 's')
                break
        await page.screenshot(path='/tmp/arena_after.png', full_page=False)
        body = await page.evaluate('document.body.innerText')
        print('\n===== BODY AFTER =====')
        print(body[-3500:])
        # tangkap session dari events
        print('\n===== EVENTS =====')
        for ev in events:
            print(ev[0], ev[1], ev[2].split('arena.ai')[-1])
            if ev[0] == 'RESP':
                print(' body:', ev[3][:300])
        # ekstrak evaluationSessionId dari body jika ada
        m = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', body)
        print('\nsession-ish uuids in body:', m[:5])
        await browser.close()

asyncio.run(main())
