"""Load the pygbag web build in headless Chromium and report what happens.

Serves build/voidsiege/build/web, opens it, taps the canvas, saves screenshots and
the browser console to web-smoke/, and fails if Python raised an exception.
"""
import asyncio
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.async_api import async_playwright

WEB = Path("build/voidsiege/build/web")
OUT = Path("web-smoke")


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


async def main():
    OUT.mkdir(exist_ok=True)
    serve()
    logs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 844, "height": 390}, is_mobile=True, has_touch=True)
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        await page.goto("http://127.0.0.1:8000/index.html#debug")
        for i, wait in enumerate((15, 15, 15)):
            await page.wait_for_timeout(wait * 1000)
            await page.screenshot(path=str(OUT / f"shot{i}.png"))
            await page.mouse.click(422, 195)
        await page.wait_for_timeout(5000)
        await page.screenshot(path=str(OUT / "final.png"))
        # Python's own output goes to the on-page xterm terminal, not the JS console
        terminal = await page.evaluate("""() => {
            const rows = document.querySelectorAll('.xterm-rows > div');
            return Array.from(rows).map(r => r.textContent).join('\\n');
        }""")
        canvas = await page.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return 'no canvas';
            const copy = document.createElement('canvas');
            copy.width = c.width; copy.height = c.height;
            const ctx = copy.getContext('2d');
            ctx.drawImage(c, 0, 0);
            const px = ctx.getImageData(0, 0, c.width, c.height).data;
            const colors = new Set();
            for (let i = 0; i < px.length; i += 4 * 97) colors.add((px[i] << 16) | (px[i + 1] << 8) | px[i + 2]);
            return `canvas ${c.width}x${c.height} css ${c.clientWidth}x${c.clientHeight} colors=${colors.size}`;
        }""")
        logs.append("---- terminal ----\n" + terminal)
        logs.append("---- " + canvas)
        await browser.close()
    text = "\n".join(logs)
    (OUT / "console.txt").write_text(text, encoding="utf-8")
    print(text[-20000:])
    if "Traceback" in text or "Error:" in text:
        sys.exit("Python error in the web build (see console above)")
    colors = int(canvas.rsplit("colors=", 1)[-1]) if "colors=" in canvas else 0
    if colors < 20:
        sys.exit(f"The game canvas looks blank ({canvas})")


asyncio.run(main())
