#!/usr/bin/env python3
"""
Minimal script: navigate to a URL, capture a screenshot of the element
located by an XPath, and optionally send it to Telegram.

This file was simplified to only keep screenshot functionality.
"""
import argparse
import os
import platform
import time
import io
import math
import requests
from PIL import Image
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


load_dotenv()


def create_driver(headless=True, window_size=(1366, 900)):
    options = Options()
    if headless:
        options.add_argument("--headless=new")

    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    system = platform.system()
    # Allow environment overrides for user-data-dir, profile, binary and chromedriver path.
    # This restores the previous platform-specific behavior while remaining configurable.
    if system == "Windows":
        user_data = os.getenv("CHROME_USER_DATA_DIR", "C:\\Users\\naveen.simma\\AppData\\Local\\Google\\Chrome\\User Data\\Default")
        profile = os.getenv("CHROME_PROFILE_DIR", "Profile 1")
        options.add_argument(f"user-data-dir={user_data}")
        options.add_argument(f"--profile-directory={profile}")
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
        if chromedriver_path:
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())
    elif system == "Linux":
        user_data = os.getenv("CHROME_USER_DATA_DIR", "/home/ubuntu/snap/chromium/common/chromium")
        profile = os.getenv("CHROME_PROFILE_DIR", "Profile 1")
        options.add_argument(f"user-data-dir={user_data}")
        options.add_argument(f"--profile-directory={profile}")
        chrome_bin = os.getenv("CHROME_BINARY", "/usr/bin/chromium-browser")
        if os.path.exists(chrome_bin):
            options.binary_location = chrome_bin
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
        if os.path.exists(chromedriver_path):
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())
    else:
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    return driver


def capture_element_screenshot(driver, xpath, out_path, timeout=15):
    """Wait for element and save its screenshot to `out_path`.

    Returns `out_path` on success, raises on failure.
    """
    wait = WebDriverWait(driver, timeout)
    elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
    # scroll into view and let paint settle
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
    time.sleep(0.3)
    # save element-only screenshot
    elem.screenshot(out_path)
    return out_path


def capture_element_full(driver, xpath, out_path, timeout=15, max_single_height=15000):
    """Capture the full element even if it is larger than the viewport.

    Attempts a single full-page screenshot by resizing the window when the
    document height is reasonable; otherwise falls back to tiled scrolling
    and stitching.
    """
    wait = WebDriverWait(driver, timeout)
    elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    metrics = driver.execute_script(
        "var e=arguments[0];var r=e.getBoundingClientRect();return {left:r.left,top:r.top,width:r.width,height:r.height,scrollY:window.scrollY,docHeight:Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),docWidth:Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),viewportHeight:window.innerHeight,viewportWidth:window.innerWidth};",
        elem,
    )

    elem_top = int(metrics["top"] + metrics["scrollY"])
    elem_left = int(metrics["left"])
    elem_width = int(math.ceil(metrics["width"]))
    elem_height = int(math.ceil(metrics["height"]))
    doc_height = int(metrics["docHeight"])
    doc_width = int(metrics["docWidth"])

    # Try single-shot full-page capture if page height is not too large
    if doc_height <= max_single_height:
        orig_size = driver.get_window_size()
        try:
            driver.set_window_size(max(doc_width, 800), max(doc_height, 600))
            png = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(png)).convert("RGB")
            crop = img.crop((elem_left, elem_top, elem_left + elem_width, elem_top + elem_height))
            crop.save(out_path)
            return out_path
        finally:
            try:
                driver.set_window_size(orig_size["width"], orig_size["height"])
            except Exception:
                pass

    # Otherwise perform tiled capture while scrolling and stitch
    viewport_h = int(metrics["viewportHeight"])
    viewport_w = int(metrics["viewportWidth"])

    start_y = elem_top
    end_y = elem_top + elem_height

    # Determine scroll positions (tile top positions)
    tiles = []
    y = max(0, start_y - (start_y % viewport_h))
    while y < end_y:
        tiles.append(y)
        y += viewport_h

    stitched = Image.new("RGB", (elem_width, elem_height))
    pasted_any = False
    for scroll_y in tiles:
        driver.execute_script(f"window.scrollTo(0, {scroll_y});")
        time.sleep(0.3)
        png = driver.get_screenshot_as_png()
        img = Image.open(io.BytesIO(png)).convert("RGB")

        rel_top = elem_top - scroll_y
        crop_top = max(0, rel_top)
        crop_bottom = min(viewport_h, rel_top + elem_height)

        if crop_bottom <= crop_top:
            continue

        # crop within the viewport image
        crop = img.crop((elem_left, crop_top, elem_left + elem_width, crop_bottom))

        paste_y = max(0, scroll_y - start_y)
        stitched.paste(crop, (0, paste_y))
        pasted_any = True

    if not pasted_any:
        raise RuntimeError("Failed to capture element by tiled stitching")

    stitched.save(out_path)
    return out_path


def send_telegram_photo(token, chat_id, image_path, caption=None):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(image_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        r = requests.post(url, data=data, files=files, timeout=30)

    # Improved error reporting for debugging
    try:
        r.raise_for_status()
    except requests.HTTPError:
        # Try to show response body to help debugging (rate limits, wrong chat id, bad token)
        try:
            print(f"Telegram API error: status={r.status_code} body={r.text}")
        except Exception:
            print(f"Telegram API error: status={r.status_code}")
        raise

    try:
        return r.json()
    except ValueError:
        return {"status_code": r.status_code, "raw_text": r.text}


def send_telegram_document(token, chat_id, file_path, caption=None):
    """Send a file as document (fallback if sendPhoto fails)."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        r = requests.post(url, data=data, files=files, timeout=60)

    try:
        r.raise_for_status()
    except requests.HTTPError:
        try:
            print(f"sendDocument error: status={r.status_code} body={r.text}")
        except Exception:
            print(f"sendDocument error: status={r.status_code}")
        raise

    try:
        return r.json()
    except ValueError:
        return {"status_code": r.status_code, "raw_text": r.text}


def get_bot_info(token):
    """Call getMe to validate the bot token."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def send_telegram_message(token, chat_id, text):
    """Send a simple text message to validate chat id and token."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    r = requests.post(url, data=data, timeout=10)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        try:
            print(f"sendMessage error: status={r.status_code} body={r.text}")
        except Exception:
            print(f"sendMessage error: status={r.status_code}")
        raise
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Capture element screenshot and optionally send to Telegram")
    parser.add_argument("--url", default="https://in.tradingview.com/chart/r2VxzAz6/?symbol=NSE%3ANIFTY", help="Target page URL")
    parser.add_argument("--xpath", default="/html/body/div[2]/div/div[6]/div/div[2]/div[1]/div[1]/div[1]/div[2]/div", help="XPath of element to screenshot")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    parser.add_argument("--screenshot-path", default="watchlist_screenshot.png", help="Path to save screenshot")
    parser.add_argument("--full", action="store_true", help="Capture full element (single-shot or stitched) when element is larger than viewport")
    parser.add_argument("--token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram bot token")
    parser.add_argument("--chat", default=os.getenv("TELEGRAM_CHAT_ID"), help="Telegram chat id")
    parser.add_argument("--no-send", action="store_true", help="Do NOT send screenshot to Telegram (default: send)")
    parser.add_argument("--test-bot", action="store_true", help="Call getMe to validate bot token and print result")
    parser.add_argument("--test-send", action="store_true", help="Send a test text message to the provided chat id and print result")
    args = parser.parse_args()

    driver = create_driver(headless=args.headless)
    try:
        driver.get(args.url)
        print(f"Captured page: {args.url}")

        # Diagnostic options: check token/chat before attempting photo upload
        if args.test_bot:
            if not args.token:
                raise SystemExit("Telegram token required for --test-bot")
            print("Calling getMe to validate bot token...")
            try:
                info = get_bot_info(args.token)
                print("getMe response:", info)
            except Exception as e:
                print("getMe failed:", e)
            return

        if args.test_send:
            if not args.token or not args.chat:
                raise SystemExit("Telegram token and chat id required for --test-send")
            print(f"Sending test message to chat {args.chat}...")
            try:
                resp = send_telegram_message(args.token, args.chat, "Test message from get_watchlist_data.py")
                print("sendMessage response:", resp)
            except Exception as e:
                print("sendMessage failed:", e)
            return

        print(f"Capturing element by XPath: {args.xpath}")
        screenshot_path = capture_element_screenshot(driver, args.xpath, args.screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")

        # By default the script sends the screenshot. Use --no-send to opt out.
        if not args.no_send:
            if not args.token or not args.chat:
                raise SystemExit("Telegram token and chat id required to send screenshot")

            # Sanity checks before upload
            if not os.path.exists(screenshot_path):
                raise SystemExit(f"Screenshot file not found: {screenshot_path}")
            try:
                size = os.path.getsize(screenshot_path)
            except Exception:
                size = None
            print(f"Sending screenshot to Telegram chat {args.chat}... file={screenshot_path} size={size}")

            try:
                resp = send_telegram_photo(args.token, args.chat, screenshot_path, caption=None)
                print("Telegram response:", resp)
                print("Screenshot sent to Telegram successfully")
            except Exception as e:
                print("sendPhoto failed, trying sendDocument fallback...", e)
                try:
                    resp = send_telegram_document(args.token, args.chat, screenshot_path, caption=None)
                    print("sendDocument response:", resp)
                    print("Screenshot sent as document to Telegram successfully")
                except Exception as e2:
                    print("Failed to send screenshot to Telegram with both methods:", e2)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
