# AIviralBot

This Telegram bot accepts screenshots of crypto transactions and uses OCR to verify the presence of the expected address and payment code before delivering access PDF.

Requirements
- Python 3.8+
- Tesseract OCR installed on the system

Python dependencies
- See `requirements.txt` (install with `pip install -r requirements.txt`).

Windows: installing Tesseract
1. Download the Tesseract installer from: https://github.com/tesseract-ocr/tesseract/releases
   - Choose the latest Windows (vintage) installer (for example: `tesseract-ocr-setup-...exe`).
2. Run the installer and note the installation path (by default: `C:\Program Files\Tesseract-OCR`).
3. Add the installation folder to your PATH or set the `TESSERACT_CMD` environment variable in your shell/OS. Example in PowerShell:

```powershell
$env:TESSERACT_CMD = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

Using the bot
1. Create a `.env` with `TELEGRAM_TOKEN`, `OWNER_CHAT_ID`, `STORAGE_CHANNEL_ID`, and optionally `PDF_PATH`, `SAVE_DIR`, `WAIT_SECONDS`.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the bot:

```powershell
python bot.py
```

Notes on OCR accuracy
- OCR can fail on low-quality images, watermarks, or stylized fonts. If verification fails, the bot will forward the screenshot to the storage channel for manual review.
- You can improve OCR by ensuring screenshots clearly show the address and memo/tag fields.

Security
- This project stores screenshots and forwards them to the configured storage channel; ensure the channel is private and you comply with privacy requirements.

