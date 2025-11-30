import os
import logging
import asyncio
import random
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import pytesseract

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import qrcode


# ===================== LOAD ENV ============================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "0"))
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", "0"))
PDF_PATH = os.getenv("PDF_PATH", "files/AIViral Tutorial.pdf")
SAVE_DIR = os.getenv("SAVE_DIR", "screenshots")
WAIT_SECONDS = int(os.getenv("WAIT_SECONDS", "12"))

SOL_ADDRESS = "8oF1AnnAyXpd5sKNyxQtbpVc8BsVGiL5NHzYAqwX5YV6"
ETH_ADDRESS = "0xcd89FDc784Fa70DBe35A97544FcF2E6BEbE5d6E9"
MONOBANK_URL = "https://send.monobank.ua/jar/7tjdex7qHm"

os.makedirs(SAVE_DIR, exist_ok=True)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SESSIONS = {}  # user_id -> details


# ===================== HELPERS =============================

def generate_code(user_id: int):
    return f"U{user_id}-{random.randint(1000,9999)}"


def make_qr(data: str):
    img = qrcode.make(data)
    bio = BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return bio


# ===================== HANDLERS ============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 Pay with Crypto", callback_data="pay_crypto")],
        [InlineKeyboardButton("🏦 Pay via Monobank", callback_data="pay_bank")],
    ]
    await update.message.reply_text(
        "🚀 Hello! I am AIViral, your personal AI assistant for creating viral content!\n\n"
        "Want to make videos that get 100K+ views—even if you:\n"
        "• Have never filmed before?\n"
        "• Don't know how to edit?\n"
        "• Have no ideas?\n\n"
        "🔥 Our AI does everything for you:\n"
        "✅ Generates scripts in 10 seconds\n"
        "✅ Creates videos with trending music\n"
        "✅ Adds subtitles and effects—automatically\n\n"
        "💡 Thousands of users are already earning from donations, ads, and affiliate programs!\n\n"
        "⚠️ Attention: Access is limited to a small number of users.\n\n"
        "💸 Access Cost: **299 UAH** or **7$**\n\n"
        "👇 Select your payment method:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown" 
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id

    if query.data == "pay_crypto":
        code = generate_code(user_id)
        SESSIONS[user_id] = {"code": code}

        kb = [
            [InlineKeyboardButton("Solana", callback_data="pay_sol")],
            [InlineKeyboardButton("Ethereum", callback_data="pay_eth")],
        ]

        await query.edit_message_text(
            f"Your code: <b>{code}</b>\n\n"
            "Select the payment network:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )

    elif query.data in ("pay_sol", "pay_eth"):
        chain = "SOL" if query.data == "pay_sol" else "ETH"
        address = SOL_ADDRESS if chain == "SOL" else ETH_ADDRESS
        protocol = "solana" if chain == "SOL" else "ethereum"

        # persist chain and address in session for later verification
        if user_id not in SESSIONS:
            SESSIONS[user_id] = {}
        SESSIONS[user_id]["chain"] = chain
        SESSIONS[user_id]["address"] = address

        code = SESSIONS[user_id].get("code") or generate_code(user_id)
        SESSIONS[user_id]["code"] = code
        uri = f"{protocol}:{address}"

        qr = make_qr(uri)

        await query.message.reply_photo(
            qr,
            caption=(
                f"Payment via <b>{chain}</b>\n\n"
                f"Address: <code>{address}</code>\n\n"
                f"Your code: <b>{code}</b>\n\n"
                "1) Scan the QR or paste the address\n"
                "2) Include the code in the memo/tag\n"
                "3) Send a screenshot of the transaction"
            ),
            parse_mode="HTML"
        )
    elif query.data == "pay_bank":
        # Monobank payment flow
        code = generate_code(user_id)
        SESSIONS[user_id] = {"code": code, "method": "BANK"}

        kb = [
            [InlineKeyboardButton("Open Monobank", url=MONOBANK_URL)],
        ]

        await query.edit_message_text(
            (
                f"Your code: <b>{code}</b>\n\n"
                "Pay using the Monobank link below. In the payment description/memo include your code.\n\n"
                "After payment, please send a screenshot of the receipt for verification."
            ),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    try:
        photo = update.message.photo[-1]
        f = await photo.get_file()

        filename = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        path = os.path.join(SAVE_DIR, filename)
        await f.download_to_drive(path)

        # Run verification on saved screenshot
        session = SESSIONS.get(user_id, {})
        expected_address = session.get("address")
        expected_code = session.get("code")
        expected_bank = "monobank" if session.get("method") == "BANK" else None

        await update.message.reply_text("Screenshot received! Verifying...")

        result = verify_screenshot(path, expected_address, expected_code, expected_bank)

        # Compose verification message
        addr_msg = "found" if result["address_found"] else "NOT found"
        code_msg = "found" if result["code_found"] else "NOT found"
        bank_msg = "found" if result.get("bank_found") else "NOT found"

        if expected_bank:
            verification_text = (
                f"Screenshot Verification:\nBank (Monobank): {bank_msg}\nCode: {code_msg}\n\n"
                "If both bank mention and code are found — the receipt is likely genuine. Otherwise — check the payment description or photo quality."
            )
        else:
            verification_text = (
                f"Screenshot Verification:\nAddress: {addr_msg}\nCode: {code_msg}\n\n"
                "If both fields are found — the screenshot is likely genuine. Otherwise — check the memo/tag correctness or photo quality."
            )

        await update.message.reply_text(verification_text)

        # Forward to storage channel with OCR excerpt
        ocr_excerpt = (result.get("text") or "").strip()[:800]
        with open(path, "rb") as file:
            await context.bot.send_document(
                chat_id=STORAGE_CHANNEL_ID,
                document=file,
                caption=(f"Screenshot from {user.full_name}\nID: {user_id}\nCode: {expected_code}\n\nOCR excerpt:\n{ocr_excerpt}")
            )

        # If verification positive, deliver PDF after waiting, else still inform user
        if session.get("method") == "BANK":
            success = result.get("bank_found") and result.get("code_found")
        else:
            success = result.get("address_found") and result.get("code_found")

        if success:
            await asyncio.sleep(WAIT_SECONDS)
            await context.bot.send_document(
                chat_id=user_id,
                document=open(PDF_PATH, "rb")
            )
            await update.message.reply_text("Done! Thank you for your payment ❤️")
        else:
            await update.message.reply_text(
                "Verification showed a possible mismatch. The administrator has already received the photo for manual review."
            )

    except Exception as e:
        await context.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text=f"[ERROR] {repr(e)}"
        )
        await update.message.reply_text("An error occurred, but the administrator has been notified.")


def preprocess_for_ocr(path: str) -> Image.Image:
    """Open image and apply basic preprocessing to improve OCR accuracy."""
    img = Image.open(path).convert("RGB")
    # convert to grayscale
    gray = ImageOps.grayscale(img)
    # increase contrast
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(1.5)
    # apply slight sharpen
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    return sharpened


def verify_screenshot(path: str, expected_address: str = None, expected_code: str = None, expected_bank: str = None) -> dict:
    """Run OCR on the image and check whether expected address, code or bank mention appear.

    Returns a dict: {"address_found": bool, "code_found": bool, "bank_found": bool, "text": str}
    """
    try:
        img = preprocess_for_ocr(path)
        text = pytesseract.image_to_string(img)
        lowered = text.lower()

        address_found = False
        code_found = False
        bank_found = False

        if expected_address:
            # check raw address and allow variations (with or without protocol prefix)
            if expected_address.lower() in lowered or expected_address.replace('0x', '').lower() in lowered:
                address_found = True

        if expected_code:
            if expected_code.lower() in lowered:
                code_found = True

        if expected_bank:
            # check common keywords for Monobank receipts
            bank_keywords = ["monobank", "mono", "monobank.ua"]
            for k in bank_keywords:
                if k in lowered:
                    bank_found = True
                    break

        return {"address_found": address_found, "code_found": code_found, "bank_found": bank_found, "text": text}
    except Exception as e:
        logger.exception("OCR verification failed")
        return {"address_found": False, "code_found": False, "bank_found": False, "text": ""}


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send the payment screenshot.")


# ===================== MAIN ================================

def main():
    # Try modern Application API first (v20+). If the runtime/install yields the
    # AttributeError seen in the traceback (Updater object has no attribute ...),
    # fall back to legacy Updater approach.
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        print("Bot started (Application).")
        app.run_polling()
    except AttributeError as e:
        logger.warning("Application build failed, falling back to Updater: %s", e)
        # Legacy fallback using Updater. Import inside block to avoid import-time issues.
        from telegram.ext import Updater

        # wrapper to run async handlers in sync context
        def sync_wrapper(coro):
            def _inner(update, context):
                try:
                    asyncio.run(coro(update, context))
                except RuntimeError:
                    # If an event loop is already running, schedule the task
                    loop = asyncio.get_event_loop()
                    loop.create_task(coro(update, context))
            return _inner

        # Try to get appropriate filters attributes for legacy Updater
        photo_filter = getattr(filters, "PHOTO", None) or getattr(filters, "photo", None)
        text_filter = getattr(filters, "TEXT", None) or getattr(filters, "text", None)
        command_filter = getattr(filters, "COMMAND", None) or getattr(filters, "command", None)

        if photo_filter is None or text_filter is None or command_filter is None:
            logger.warning("Could not resolve filters attributes; message filters may not work as expected.")

        # Create Updater without 'use_context' to support environments where that kwarg is absent
        updater = Updater(TELEGRAM_TOKEN)
        dp = updater.dispatcher

        # Register handlers (wrap async handlers to run in sync dispatcher)
        dp.add_handler(CommandHandler("start", sync_wrapper(start)))
        dp.add_handler(CallbackQueryHandler(sync_wrapper(button_handler)))
        if photo_filter is not None:
            dp.add_handler(MessageHandler(photo_filter, sync_wrapper(handle_photo)))
        else:
            dp.add_handler(MessageHandler(filters.PHOTO if hasattr(filters, "PHOTO") else filters.photo, sync_wrapper(handle_photo)))

        if text_filter is not None and command_filter is not None:
            dp.add_handler(MessageHandler(text_filter & ~command_filter, sync_wrapper(handle_text)))
        else:
            # fallback to common names
            fallback_text = filters.TEXT if hasattr(filters, "TEXT") else filters.text
            fallback_cmd = filters.COMMAND if hasattr(filters, "COMMAND") else filters.command
            dp.add_handler(MessageHandler(fallback_text & ~fallback_cmd, sync_wrapper(handle_text)))

        print("Bot started (Updater fallback).")
        updater.start_polling()
        updater.idle()


if __name__ == "__main__":
    main()
