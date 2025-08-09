import os
import json
import html
import logging
from datetime import datetime
from telegram import Update, MessageEntity
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
from telegram.error import TelegramError


BOT_TOKEN = ""   # Replace with your actual bot token
DATA_FILE = "user_data.json"

logging.basicConfig(level=logging.INFO, filename="bot.log")
logger = logging.getLogger(__name__)

# Load and save user data
def load_user_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_user_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save user data: {e}")

user_data = load_user_data()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            "state": "idle",
            "video_file_id": None,
            "video_caption": None,
            "caption_entities": None,
            "image_file_id": None,
            "has_spoiler": False
        }
        save_user_data(user_data)
    await update.message.reply_text(
        "🎥 Send a video followed by a JPEG image to set it as cover."
    )

# Handle video message
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    video = update.message.video
    if not video:
        return await update.message.reply_text("❌ Please send a valid video.")

    caption_entities = [
        {
            "offset": e.offset,
            "length": e.length,
            "type": e.type,
            "user": e.user.to_dict() if e.type == "text_mention" else None
        }
        for e in update.message.caption_entities or []
    ]
    user_data[user_id] = {
        "state": "waiting_for_image",
        "video_file_id": video.file_id,
        "video_caption": update.message.caption,
        "caption_entities": caption_entities,
        "image_file_id": None,
        "has_spoiler": user_data.get(user_id, {}).get("has_spoiler", False)
    }
    save_user_data(user_data)
    await update.message.reply_text("✅ Video received. Now send a JPEG image for the cover.")

# Handle photo message
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photos = update.message.photo
    if user_id not in user_data or user_data[user_id]["state"] != "waiting_for_image":
        return await update.message.reply_text("❌ Please send a video first.")

    smallest = min(photos, key=lambda p: p.file_size)
    largest = max(photos, key=lambda p: p.file_size)

    if smallest.file_size > 200 * 1024 or smallest.width > 320 or smallest.height > 320:
        return await update.message.reply_text("❌ Image must be ≤200 KB and ≤320x320 pixels.")

    user_data[user_id]["image_file_id"] = largest.file_id
    save_user_data(user_data)

    try:
        entities = [
            MessageEntity(
                type=e["type"],
                offset=e["offset"],
                length=e["length"],
                user=e.get("user")
            ) for e in user_data[user_id]["caption_entities"]
        ] if user_data[user_id]["caption_entities"] else None

        await context.bot.send_video(
            chat_id=update.message.chat_id,
            video=user_data[user_id]["video_file_id"],
            cover=user_data[user_id]["image_file_id"],
            caption=user_data[user_id]["video_caption"],
            caption_entities=entities,
            supports_streaming=True,
            has_spoiler=user_data[user_id]["has_spoiler"]
        )
        await update.message.reply_text("✅ Video sent with the cover!")

    except TelegramError as e:
        await update.message.reply_text(f"❌ Error sending video: {str(e)}")

    user_data[user_id] = {
        "state": "idle",
        "video_file_id": None,
        "video_caption": None,
        "caption_entities": None,
        "image_file_id": None,
        "has_spoiler": False
    }
    save_user_data(user_data)

# Main runner
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()

