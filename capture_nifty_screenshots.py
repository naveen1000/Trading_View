#!/usr/bin/env python3
"""Capture TradingView chart screenshots for NIFTY (or any symbol) at different intervals and send to Telegram.

Usage example (PowerShell):
  $env:TELEGRAM_BOT_TOKEN="<token>"; $env:TELEGRAM_CHAT_ID="<chat_id>"; python capture_nifty_screenshots.py --symbol "NSE:NIFTY" --intervals 1 5 15 60 D

Environment variables:
  TELEGRAM_BOT_TOKEN  - Telegram bot token (optional if passed via --token)
  TELEGRAM_CHAT_ID    - Telegram chat id or channel (optional if passed via --chat)

This script uses Selenium + webdriver-manager to auto-download ChromeDriver.
"""
import argparse
import io
import os
import platform
import time
from urllib.parse import quote_plus

import requests
from PIL import Image
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


load_dotenv()


def create_driver(headless=True, window_size=(1366, 900)):
    options = Options()
    if headless:
        # Use new headless mode where available
        options.add_argument("--headless=new")

    #common options
    #options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    #options.add_argument("--disable-gpu")
    #options.add_argument("--no-sandbox")
    #options.add_argument("--disable-dev-shm-usage")
    # Optional: reduce detection surface
    #options.add_argument("--disable-blink-features=AutomationControlled")

    system = platform.system()
    print(f"Detected OS: {system}")
    # For Windows
    if system == "Windows":
        CHROME_DATA_PATH = "user-data-dir=C:\\Users\\naveen.simma\\AppData\\Local\\Google\\Chrome\\User Data\\Default"
        options.add_argument(CHROME_DATA_PATH)
        options.add_argument('--profile-directory=Profile 1')
        service = Service("D:\\projects\\Wapp\\chromedriver.exe")
    
    # For Ubuntu
    elif system == "Linux":
        CHROME_UBUNTU_USER_DATA_PATH = "/home/ubuntu/snap/chromium/common/chromium"
        UBUNTU_PROFILE_DIRECTORY = "Profile 1"
        options.add_argument(f"user-data-dir={CHROME_UBUNTU_USER_DATA_PATH}")
        options.add_argument(f"--profile-directory={UBUNTU_PROFILE_DIRECTORY}")
        options.binary_location = "/usr/bin/chromium-browser"
        service = Service("/usr/bin/chromedriver")

    driver = webdriver.Chrome(service=service, options=options)
    return driver


def capture_chart(driver, symbol, interval, out_path, wait=7):
    """Open TradingView chart for `symbol` with `interval` and save screenshot to `out_path`.

    Tries to screenshot the chart element; falls back to full-page screenshot.
    """
    symbol_enc = quote_plus(symbol)
    url = f"https://www.tradingview.com/chart/?symbol={symbol_enc}&interval={interval}"
    driver.get(url)
    time.sleep(wait)

    # Try to accept cookies or dismiss popups if present (best-effort)
    try:
        # many locales use "Accept" text; this is best-effort and won't break if not found
        btn = driver.find_element(By.XPATH, "//button[text()='Accept' or text()='I accept' or text()='Accept all']")
        btn.click()
        time.sleep(1)
    except Exception:
        pass

    # Try to find the chart view element (common selectors used by TradingView)
    selectors = [
        "div.tv-chart-view",
        "div.chart-container",
        "div#tv_chart_container",
    ]

    for sel in selectors:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, sel)
            png = elem.screenshot_as_png
            image = Image.open(io.BytesIO(png))
            image.save(out_path)
            return out_path
        except Exception:
            continue

    # Fallback: full page screenshot
    png = driver.get_screenshot_as_png()
    image = Image.open(io.BytesIO(png))
    image.save(out_path)
    return out_path


def send_telegram_photo(token, chat_id, image_path, caption=None):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(image_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        r = requests.post(url, data=data, files=files, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Capture TradingView chart screenshots and send to Telegram")
    parser.add_argument("--symbol", default=os.getenv("SYMBOL", "NSE:NIFTY"), help="Symbol, e.g. 'NSE:NIFTY' or 'NSE:INFY'")
    parser.add_argument("--intervals", nargs="+", default=["15", "60", "D"], help="List of intervals, e.g. 1 5 15 60 D")
    parser.add_argument("--out-dir", default="screenshots", help="Directory to save screenshots")
    parser.add_argument("--token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram bot token")
    parser.add_argument("--chat", default=os.getenv("TELEGRAM_CHAT_ID"), help="Telegram chat id")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    args = parser.parse_args()

    if not args.token or not args.chat:
        print("Error: Telegram token and chat id required (env or args).")
        return

    os.makedirs(args.out_dir, exist_ok=True)
    driver = create_driver(headless=args.headless)

    try:
        for interval in args.intervals:
            fname = f"{args.symbol.replace(':','_')}_{interval}.png"
            out_path = os.path.join(args.out_dir, fname)
            print(f"Capturing {args.symbol} @ {interval} -> {out_path}")
            capture_chart(driver, args.symbol, interval, out_path)
            print(f"Sending {os.path.basename(out_path)} to Telegram chat {args.chat}")
            try:
                send_telegram_photo(args.token, args.chat, out_path, caption=f"{args.symbol} {interval}")
            except Exception as e:
                print(f"Failed to send {out_path} to Telegram: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
