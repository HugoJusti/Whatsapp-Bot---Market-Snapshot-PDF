"""
Entry point for the WhatsApp Market Snapshot Bot.

Usage:
    python main.py               # long-running bot (polls for /report, /quick, /help)
    python main.py --once        # fetch data, generate PDF, send to WA_RECIPIENT, exit
    python main.py --dry-run     # fetch data, generate PDF, open locally — no WhatsApp
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

# ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from data import fetch_market_data
from pdf_gen import generate_pdf

OUTPUT_DIR   = os.getenv("OUTPUT_DIR",   "./output")
WA_RECIPIENT = os.getenv("WA_RECIPIENT", "+85268720365")


# ── modes ─────────────────────────────────────────────────────────────────────
def mode_dry_run() -> None:
    print("[main] DRY RUN – generating PDF (no WhatsApp)")
    data = fetch_market_data()
    pdf_path = os.path.join(OUTPUT_DIR, "market_snapshot.pdf")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = generate_pdf(data, pdf_path)
    print(f"[main] PDF saved: {os.path.abspath(out)}")
    subprocess.Popen(f'start "" "{os.path.abspath(out)}"', shell=True)
    print("[main] Opened PDF in default viewer.")


def mode_once() -> None:
    print("[main] ONE-SHOT – building PDF and sending via WhatsApp")
    data = fetch_market_data()
    pdf_path = os.path.join(OUTPUT_DIR, "market_snapshot.pdf")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generate_pdf(data, pdf_path)
    print(f"[main] PDF ready: {pdf_path}")
    print(f"[main] Sending to {WA_RECIPIENT} …")

    from whatsapp import send_once
    asyncio.run(send_once(pdf_path, WA_RECIPIENT))
    print("[main] Done.")


def mode_bot() -> None:
    print(f"[main] BOT MODE – polling WhatsApp chat with {WA_RECIPIENT}")
    from whatsapp import run_bot
    asyncio.run(run_bot(generate_pdf, fetch_market_data, WA_RECIPIENT))


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="WhatsApp Market Snapshot Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python main.py              # run bot (long-running)\n"
            "  python main.py --once       # send one report, then exit\n"
            "  python main.py --dry-run    # build PDF only, open locally\n"
        ),
    )
    parser.add_argument("--once",    action="store_true",
                        help="build PDF, send to WA_RECIPIENT, exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="build PDF only, open locally, no WhatsApp")
    args = parser.parse_args()

    if args.dry_run:
        mode_dry_run()
    elif args.once:
        mode_once()
    else:
        mode_bot()


if __name__ == "__main__":
    main()
