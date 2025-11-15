# TradingView Nifty Screenshot -> Telegram

This small Python utility captures TradingView chart screenshots at multiple timeframes and sends them to Telegram.

Requirements
- Python 3.8+
- Chrome browser installed (matching Chromium/Chrome stable works)

Install dependencies (PowerShell):

```powershell
python -m pip install -r requirements.txt
```

Usage (PowerShell):

Set environment variables or pass via flags. Example using environment variables:

```powershell
$env:TELEGRAM_BOT_TOKEN = "<your_bot_token>";
$env:TELEGRAM_CHAT_ID = "<your_chat_id>";
python capture_nifty_screenshots.py --symbol "NSE:NIFTY" --intervals 1 5 15 60 D --headless
```

Or pass token/chat directly:

```powershell
python capture_nifty_screenshots.py --symbol "NSE:NIFTY" --intervals 1 5 15 60 D --token "<bot>" --chat "<chat_id>"
```

Notes
- The script uses `webdriver-manager` to auto-download ChromeDriver.
- Some TradingView UI elements (cookie banners, paywalls) may appear; the script attempts a best-effort dismiss.
- If headless screenshots fail, try without `--headless` to debug interactive rendering.

Files
- `capture_nifty_screenshots.py`: main script
- `requirements.txt`: Python dependencies
- `.env.example`: example environment variables
