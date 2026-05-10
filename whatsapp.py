"""
Playwright-based WhatsApp Web automation.
Manages a persistent browser session; no QR scan after first run.

Exported:
    run_bot(generate_pdf_fn, fetch_data_fn)  – long-running polling loop
    send_once(pdf_path)                      – opens WA, sends one file, exits
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

from playwright.async_api import (
    BrowserContext,
    Page,
    async_playwright,
)

SESSION_DIR  = os.getenv("SESSION_DIR",  "./wa_session")
OUTPUT_DIR   = os.getenv("OUTPUT_DIR",   "./output")
WA_RECIPIENT = os.getenv("WA_RECIPIENT", "+85268720365")

POLL_INTERVAL = 3   # seconds between message checks
WA_URL        = "https://web.whatsapp.com"


# ── logging ───────────────────────────────────────────────────────────────────
def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── browser setup ─────────────────────────────────────────────────────────────
async def _get_context(playwright) -> BrowserContext:
    os.makedirs(SESSION_DIR, exist_ok=True)
    return await playwright.chromium.launch_persistent_context(
        SESSION_DIR,
        headless=False,
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        args=["--no-sandbox"],
    )


async def _wait_for_load(page: Page, timeout: int = 120_000) -> None:
    _log("Waiting for WhatsApp Web to load (scan QR if prompted) …")
    try:
        await page.wait_for_function(
            """() => (
                document.querySelector('[data-icon="search"]') ||
                document.querySelector('[aria-label="Chat list"]') ||
                document.querySelector('#pane-side') ||
                document.querySelector('[data-testid="chat-list"]') ||
                document.querySelector('div[role="navigation"]')
            ) !== null""",
            timeout=timeout,
        )
        _log("WhatsApp Web ready.")
    except Exception:
        _log("WARNING: could not confirm WA loaded — proceeding anyway.")
    await asyncio.sleep(2)


async def _open_chat(page: Page, phone: str) -> None:
    clean = phone.replace("+", "").replace(" ", "")
    _log(f"Opening chat: {phone}")
    await page.goto(f"{WA_URL}/send?phone={clean}", wait_until="domcontentloaded")
    await asyncio.sleep(3)
    # Wait for ANY compose box variant — WhatsApp changes these selectors regularly
    try:
        await page.wait_for_function("""
            () => (
                document.querySelector('[data-testid="conversation-compose-box-input"]') ||
                document.querySelector('div[contenteditable="true"][data-tab]') ||
                document.querySelector('footer div[contenteditable="true"]') ||
                document.querySelector('div[role="textbox"]')
            ) !== null
        """, timeout=30_000)
    except Exception:
        _log("WARNING: compose box not found — proceeding anyway.")
    _log("Chat open.")


# ── send helpers ──────────────────────────────────────────────────────────────
async def _get_compose_box(page: Page):
    selectors = [
        '[data-testid="conversation-compose-box-input"]',
        'footer div[contenteditable="true"]',
        'div[contenteditable="true"][data-tab]',
        'div[role="textbox"]',
    ]
    for sel in selectors:
        el = page.locator(sel).first
        try:
            await el.wait_for(timeout=5_000)
            return el
        except Exception:
            continue
    return None


async def _send_text(page: Page, text: str) -> None:
    box = await _get_compose_box(page)
    if not box:
        _log("ERROR: could not find compose box to send text.")
        return
    await box.click()
    lines = text.split("\n")
    for i, line in enumerate(lines):
        await box.type(line)
        if i < len(lines) - 1:
            await page.keyboard.press("Shift+Enter")
    await page.keyboard.press("Enter")
    await asyncio.sleep(0.5)
    _log(f"Sent text ({len(text)} chars)")


async def _send_file(page: Page, file_path: str, caption: str = "") -> None:
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        _log(f"ERROR: file not found: {abs_path}")
        return

    _log(f"Attaching: {abs_path}")

    # Step 1 — click the attach button (plus-rounded icon)
    for sel in ['span[data-icon="plus-rounded"]', 'span[data-icon="plus"]',
                '[data-testid="attach-menu-plus"]', '[title="Attach"]']:
        try:
            btn = page.locator(sel).first
            await btn.wait_for(timeout=4_000)
            await btn.click()
            await asyncio.sleep(1)
            break
        except Exception:
            continue

    # Step 2 — click the "Document" option in the menu
    for sel in ['//div[@role="application"]/ul//span[text()="Document"]',
                '//*[contains(text(),"Document")]']:
        try:
            await page.locator(f'xpath={sel}').first.click(timeout=3_000)
            await asyncio.sleep(1)
            break
        except Exception:
            continue

    # Step 3 — use input[type='file'][multiple] which has accept="*"
    file_input = page.locator("input[type='file'][multiple]").first
    await file_input.set_input_files(abs_path)
    await asyncio.sleep(2)

    # Step 4 — caption
    if caption:
        try:
            cap = page.locator('[contenteditable="true"]').nth(1)
            await cap.wait_for(timeout=4_000)
            await cap.fill(caption)
            await asyncio.sleep(0.3)
        except Exception:
            pass

    # Step 5 — send button
    for send_sel in ['span[data-icon="wds-ic-send-filled"]', '[data-testid="send"]',
                     'span[data-icon="send"]', 'button[aria-label="Send"]']:
        try:
            btn = page.locator(send_sel).first
            await btn.wait_for(timeout=5_000)
            await btn.click()
            await asyncio.sleep(2)
            _log("File sent.")
            return
        except Exception:
            continue
    _log("ERROR: send button not found.")


# ── message detection ─────────────────────────────────────────────────────────
async def _last_command(page: Page) -> Tuple[str, int]:
    """Return (command_text, total_message_count) from the open chat."""
    try:
        result = await page.evaluate("""
            () => {
                const blocks = [...document.querySelectorAll('.copyable-text')];
                const count = blocks.length;
                for (let i = blocks.length - 1; i >= 0; i--) {
                    const spans = blocks[i].querySelectorAll('span');
                    for (const s of spans) {
                        const t = (s.innerText || '').trim();
                        if (t.startsWith('/') && t.length < 30) {
                            return [t, count];
                        }
                    }
                }
                return ['', count];
            }
        """)
        return result[0] or "", int(result[1] or 0)
    except Exception:
        return "", 0


# ── quick summary ─────────────────────────────────────────────────────────────
def _quick_summary(data: List[Dict[str, Any]]) -> str:
    lines = ["*Global Markets – Quick Summary*\n"]
    for d in data:
        dot = "🟢" if d["is_open"] else "⚫"
        if d["pct_change"] is not None:
            sign = "+" if d["pct_change"] >= 0 else ""
            lines.append(
                f"{dot} *{d['index_name']}*:  "
                f"{d['current']:,.2f} {d['currency']}  "
                f"({sign}{d['pct_change']:.2f}%)"
            )
        else:
            lines.append(f"{dot} *{d['index_name']}*: N/A")
    lines.append("\n_Data: yfinance  •  Not financial advice_")
    return "\n".join(lines)


# ── command router ────────────────────────────────────────────────────────────
async def _handle_command(
    page: Page,
    cmd: str,
    generate_pdf_fn: Callable,
    fetch_data_fn: Callable,
) -> None:
    if cmd == "/report":
        _log("Command /report received.")
        await _send_text(page, "Fetching live data and generating PDF …")
        data = fetch_data_fn()
        pdf_path = os.path.join(OUTPUT_DIR, "market_snapshot.pdf")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        generate_pdf_fn(data, pdf_path)
        await _send_file(page, pdf_path)

    elif cmd == "/quick":
        _log("Command /quick received.")
        await _send_text(page, "Fetching market data …")
        data = fetch_data_fn()
        await _send_text(page, _quick_summary(data))

    elif cmd == "/help":
        _log("Command /help received.")
        await _send_text(
            page,
            "*Market Bot – Commands*\n\n"
            "*/report*  –  Full PDF market snapshot\n"
            "*/quick*   –  Text summary of all markets\n"
            "*/help*    –  Show this message\n\n"
            "_Powered by yfinance_",
        )

    else:
        _log(f"Unknown command ignored: {cmd!r}")


# ── public API ────────────────────────────────────────────────────────────────
async def run_bot(
    generate_pdf_fn: Callable,
    fetch_data_fn: Callable,
    phone: str = WA_RECIPIENT,
) -> None:
    async with async_playwright() as p:
        ctx  = await _get_context(p)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        await page.goto(WA_URL)
        await _wait_for_load(page)
        await _open_chat(page, phone)

        _log(f"Bot polling chat with {phone}. Send /report, /quick, or /help.")

        # Wait for chat to fully load before snapshotting
        await asyncio.sleep(5)
        last_cmd, last_count = await _last_command(page)
        _log(f"Startup snapshot: {last_cmd!r} ({last_count} messages) — will ignore.")

        while True:
            try:
                msg, count = await _last_command(page)
                if msg and (count > last_count or msg != last_cmd):
                    last_cmd, last_count = msg, count
                    _log(f"New command: {msg!r}")
                    try:
                        await _handle_command(page, msg.strip().lower(),
                                              generate_pdf_fn, fetch_data_fn)
                    except Exception as cmd_exc:
                        _log(f"Command error: {cmd_exc}")
                    finally:
                        # Always re-snapshot so bot's own reply messages don't re-trigger
                        _, last_count = await _last_command(page)
                await asyncio.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                _log("Bot stopped by user.")
                break
            except Exception as exc:
                _log(f"Poll error: {exc}")
                await asyncio.sleep(5)

        await ctx.close()


async def send_once(pdf_path: str, phone: str = WA_RECIPIENT) -> None:
    async with async_playwright() as p:
        ctx  = await _get_context(p)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(WA_URL)
        await _wait_for_load(page)
        await _open_chat(page, phone)
        await _send_file(page, pdf_path)
        _log("Done. Closing browser.")
        await ctx.close()


# ── standalone hello-world test ───────────────────────────────────────────────
if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Hello from Market Bot! 👋"

    async def _hello():
        async with async_playwright() as p:
            ctx  = await _get_context(p)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(WA_URL)
            await _wait_for_load(page)
            await _open_chat(page, WA_RECIPIENT)
            await _send_text(page, msg)
            _log("Hello-world message sent.")
            await asyncio.sleep(3)
            await ctx.close()

    asyncio.run(_hello())
