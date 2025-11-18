#!/usr/bin/env python3
"""Extract TradingView watchlist data using Selenium.

This script navigates to TradingView watchlist and extracts data from the specified xpath.

Usage example (PowerShell):
  $env:TELEGRAM_BOT_TOKEN="<token>"; python get_watchlist_data.py
  python get_watchlist_data.py --url "https://www.tradingview.com/watchlist/"

"""
import argparse
import io
import json
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

    # common options
    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Optional: reduce detection surface
    options.add_argument("--disable-blink-features=AutomationControlled")

    system = platform.system()

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


def get_watchlist_data(driver, url, xpath, wait=7):
    """Navigate to TradingView watchlist and extract data from xpath.
    
    Args:
        driver: Selenium WebDriver instance
        url: TradingView watchlist URL
        xpath: XPath to extract data from
        wait: Wait time in seconds for page to load
    
    Returns:
        Extracted element data (text or HTML)
    """
    driver.get(url)
    time.sleep(wait)
    time.sleep(30)

    # Try to accept cookies or dismiss popups if present (best-effort)
    try:
        btn = driver.find_element(By.XPATH, "//button[text()='Accept' or text()='I accept' or text()='Accept all']")
        btn.click()
        time.sleep(1)
    except Exception:
        pass

    try:
        elem = driver.find_element(By.XPATH, xpath)
        # Get text content
        text_data = elem.text
        # Get inner HTML
        html_data = elem.get_attribute("innerHTML")
        
        return {
            "text": text_data,
            "html": html_data,
            "tag": elem.tag_name,
            "class": elem.get_attribute("class"),
        }
    except Exception as e:
        print(f"Error extracting data from xpath: {e}")
        return None


def capture_div_screenshot(driver, xpath, out_path):
    """Capture screenshot of a div element by xpath and save to file.
    
    Args:
        driver: Selenium WebDriver instance
        xpath: XPath to the element
        out_path: Output file path for screenshot
    
    Returns:
        Path to saved screenshot or None if failed
    """
    try:
        elem = driver.find_element(By.XPATH, xpath)
        png = elem.screenshot_as_png
        image = Image.open(io.BytesIO(png))
        image.save(out_path)
        print(f"Screenshot saved to {out_path}")
        return out_path
    except Exception as e:
        print(f"Error capturing screenshot: {e}")
        return None


def send_telegram_photo(token, chat_id, image_path, caption=None):
    """Send photo to Telegram chat.
    
    Args:
        token: Telegram bot token
        chat_id: Telegram chat ID
        image_path: Path to image file
        caption: Optional caption for the photo
    
    Returns:
        Telegram API response
    """
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
    parser = argparse.ArgumentParser(description="Extract TradingView watchlist data and send screenshot to Telegram")
    parser.add_argument("--url", default="https://in.tradingview.com/chart/r2VxzAz6/?symbol=NSE%3ANIFTY", help="TradingView watchlist URL")
    parser.add_argument("--xpath", default="/html/body/div[2]/div/div[6]/div/div[2]/div[1]/div[1]/div[1]/div[2]/div", 
                        help="XPath to extract data from")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    parser.add_argument("--output", default=None, help="Save output to JSON file")
    parser.add_argument("--screenshot", action="store_true", help="Capture screenshot of div")
    parser.add_argument("--screenshot-path", default="watchlist_screenshot.png", help="Path to save screenshot")
    parser.add_argument("--token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram bot token")
    parser.add_argument("--chat", default=os.getenv("TELEGRAM_CHAT_ID"), help="Telegram chat id")
    parser.add_argument("--send-telegram", action="store_true", help="Send screenshot to Telegram")
    args = parser.parse_args()

    print(f"Connecting to {args.url}")
    driver = create_driver(headless=args.headless)

    try:
        print(f"Extracting data from xpath: {args.xpath}")
        data = get_watchlist_data(driver, args.url, args.xpath)
        
        if data:
            print("\n=== Watchlist Data ===")
            print(json.dumps(data, indent=2))
            
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"\nData saved to {args.output}")
        else:
            print("No data extracted.")
        
        # Capture and send screenshot if requested
        if args.screenshot:
            print(f"\nCapturing screenshot of div...")
            screenshot_path = capture_div_screenshot(driver, args.xpath, args.screenshot_path)
            
            if screenshot_path and args.send_telegram:
                if not args.token or not args.chat:
                    print("Error: Telegram token and chat id required to send screenshot.")
                else:
                    print(f"Sending screenshot to Telegram chat {args.chat}...")
                    try:
                        send_telegram_photo(args.token, args.chat, screenshot_path, caption="Watchlist Screenshot")
                        print("Screenshot sent to Telegram successfully!")
                    except Exception as e:
                        print(f"Failed to send screenshot to Telegram: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
