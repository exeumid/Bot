
import os
import json
import logging
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHANNEL_FILE = "channels.json"
USERS_FILE = "users.json"
MAX_CHANNELS = 10


def load_json(file, default):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_channels():
    return load_json(CHANNEL_FILE, [])


def get_users():
    return load_json(USERS_FILE, [])


def is_admin(user_id):
    return user_id == ADMIN_ID


async def check_subscriptions(user_id, context):
    channels = get_channels()

    for channel in channels:
        try:
            member = await context.bot.get_chat_member(
                channel, user_id
            )
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False

    return True


def subscription_keyboard():
    channels = get_channels()
    buttons = []

    for channel in channels:
        name = channel.replace("@", "")
        buttons.append([
            InlineKeyboardButton(
                f"📢 {name}",
                url=f"https://t.me/{name}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Obunani tekshirish",
            callback_data="check_sub"
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = get_users()

    if user.id not in users:
        users.append(user.id)
        save_json(USERS_FILE, users)

    if not await check_subscriptions(user.id, context):
        await update.message.reply_text(
            "🔒 Botdan foydalanish uchun quyidagi "
            "kanallarga obuna bo'ling:",
            reply_markup=subscription_keyboard()
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "🔎 Anime qidirish",
                callback_data="search_help"
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Bot haqida",
                callback_data="about"
            )
        ]
    ]

    await update.message.reply_text(
        "🎌 ANIME FINDER\n\n"
        "Anime nomi yoki ID raqamini yuboring.\n\n"
        "Masalan:\n"
        "Naruto\n"
        "20\n"
        "Attack on Titan",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def anime_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await check_subscriptions(user_id, context):
        await update.message.reply_text(
            "🔒 Avval kanallarga obuna bo'ling:",
            reply_markup=subscription_keyboard()
        )
        return

    query = update.message.text.strip()

    if not query:
        return

    await update.message.reply_text("🔎 Anime qidirilmoqda...")

    try:
        if query.isdigit():
            url = f"https://api.jikan.moe/v4/anime/{query}"
            response = requests.get(url, timeout=20)
            data = response.json().get("data")

            if not data:
                await update.message.reply_text("Anime topilmadi.")
                return

            anime_list = [data]

        else:
            url = "https://api.jikan.moe/v4/anime"
            response = requests.get(
                url,
                params={"q": query, "limit": 5},
                timeout=20
            )
            anime_list = response.json().get("data", [])

        if not anime_list:
            await update.message.reply_text(
                "😕 Anime topilmadi. Boshqa nom bilan urinib ko'ring."
            )
            return

        for anime in anime_list[:5]:
            title = anime.get("title", "Noma'lum")
            title_jp = anime.get("title_japanese") or "Noma'lum"
            anime_id = anime.get("mal_id", "-")
            episodes = anime.get("episodes") or "Noma'lum"
            score = anime.get("score") or "Noma'lum"
            status = anime.get("status") or "Noma'lum"
            synopsis = anime.get("synopsis") or "Tavsif mavjud emas."
            genres = ", ".join(
                g["name"] for g in anime.get("genres", [])
            ) or "Noma'lum"
            image = anime.get("images", {}).get("jpg", {}).get("image_url")
            link = anime.get("url", "")

            text = (
                f"🎌 {title}\n"
                f"🇯🇵 Yaponcha: {title_jp}\n"
                f"🆔 ID: {anime_id}\n"
                f"📺 Qismlar: {episodes}\n"
                f"⭐ Reyting: {score}\n"
                f"📌 Holati: {status}\n"
                f"🎭 Janr: {genres}\n\n"
                f"📝 {synopsis[:800]}"
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Anime haqida", url=link)]
            ]) if link else None

            if image:
                await update.message.reply_photo(
                    photo=image,
                    caption=text[:1024],
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=keyboard
                )

    except Exception as e:
        logging.exception(e)
        await update.message.reply_text(
            "⚠️ Qidiruvda xatolik. Birozdan keyin urinib ko'ring."
        )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return

    keyboard = [
        [InlineKeyboardButton("📢 Kanallar", callback_data="channels")],
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton("➖ Kanal o'chirish", callback_data="remove_channel")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("📨 Xabar yuborish", callback_data="broadcast")]
    ]

    await update.message.reply_text(
        "⚙️ ADMIN PANEL",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "check_sub":
        if await check_subscriptions(user_id, context):
            await query.edit_message_text(
                "✅ Obuna tasdiqlandi!\n/start buyrug'ini yuboring."
            )
        else:
            await query.answer(
                "❌ Hali barcha kanallarga obuna bo'lmagansiz.",
                show_alert=True
            )
        return

    if data == "search_help":
        await query.message.reply_text(
            "🔎 Anime nomini yoki ID raqamini yuboring."
        )
        return

    if data == "about":
        await query.message.reply_text(
            "🎌 Anime Finder — anime qidirish bot."
        )
        return

    if not is_admin(user_id):
        return

    if data == "channels":
        channels = get_channels()
        text = "📢 Kanallar:\n\n" + (
            "\n".join(channels) if channels else "Kanallar yo'q."
        )
        await query.message.reply_text(text)

    elif data == "add_channel":
        context.user_data["action"] = "add_channel"
        await query.message.reply_text(
            "➕ Kanal username'ini yuboring.\n"
            "Masalan: @mychannel"
        )

    elif data == "remove_channel":
        channels = get_channels()

        if not channels:
            await query.message.reply_text("Kanal mavjud emas.")
            return

        buttons = [
            [InlineKeyboardButton(c, callback_data=f"del:{c}")]
            for c in channels
        ]

        await query.message.reply_text(
            "O'chiriladigan kanalni tanlang:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("del:"):
        channel = data[4:]
        channels = get_channels()

        if channel in channels:
            channels.remove(channel)
            save_json(CHANNEL_FILE, channels)

        await query.message.reply_text(f"🗑 O'chirildi: {channel}")

    elif data == "stats":
        await query.message.reply_text(
            f"📊 Statistika\n\n"
            f"👥 Foydalanuvchilar: {len(get_users())}\n"
            f"📢 Kanallar: {len(get_channels())}/{MAX_CHANNELS}"
        )

    elif data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.message.reply_text(
            "📨 Barcha foydalanuvchilarga yuboriladigan "
            "matnni jo'nating."
        )


async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    action = context.user_data.get("action")
    text = update.message.text.strip()

    if action == "add_channel":
        channels = get_channels()

        if not text.startswith("@"):
            await update.message.reply_text(
                "❌ Kanal @username shaklida bo'lishi kerak."
            )
            return

        if text in channels:
            await update.message.reply_text("Kanal oldin qo'shilgan.")
        elif len(channels) >= MAX_CHANNELS:
            await update.message.reply_text(
                "❌ Maksimal 10 ta kanal qo'shish mumkin."
            )
        else:
            channels.append(text)
            save_json(CHANNEL_FILE, channels)
            await update.message.reply_text(
                f"✅ Kanal qo'shildi: {text}\n"
                "Bot kanal ichida administrator bo'lishi kerak."
            )

        context.user_data.pop("action", None)

    elif action == "broadcast":
        users = get_users()
        success = 0

        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=text
                )
                success += 1
            except Exception:
                pass

        await update.message.reply_text(
            f"📨 Yuborildi: {success}/{len(users)}"
        )
        context.user_data.pop("action", None)

    else:
        await anime_search(update, context)


async def main():
    if not TOKEN or not 8660202952:
        raise RuntimeError(
            "9180620467:AAEUU_YrMSlMcBsqM46luKu0GYftSxsT_9I"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text)
    )

    print("Anime Finder ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
                  
