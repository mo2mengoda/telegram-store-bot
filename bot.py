"""
Telegram Store Bot
------------------
A shop assistant bot: browse products, place an order step by step
(product -> quantity -> name -> phone -> address -> confirm), save the
orders to a CSV file and notify the store owner instantly.

Setup:
    1. Create a bot with @BotFather and copy the token
    2. Copy .env.example to .env and fill in BOT_TOKEN and ADMIN_CHAT_ID
    3. pip install -r requirements.txt
    4. python bot.py
"""

import csv
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # optional: owner gets order alerts

BASE = Path(__file__).parent
PRODUCTS = json.loads((BASE / "products.json").read_text(encoding="utf-8"))
ORDERS_FILE = BASE / "orders.csv"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("store-bot")

QTY, NAME, PHONE, ADDRESS, CONFIRM = range(5)
MAIN_MENU = ReplyKeyboardMarkup(
    [["🛍️ المنتجات", "📦 اطلب الآن"], ["📞 تواصل معنا", "ℹ️ عن المتجر"]],
    resize_keyboard=True,
)


def product_by_id(pid: str) -> dict | None:
    return next((p for p in PRODUCTS if p["id"] == pid), None)


def products_keyboard(prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f'{p["name"]} - {p["price"]} ج', callback_data=f'{prefix}:{p["id"]}')]
            for p in PRODUCTS]
    return InlineKeyboardMarkup(rows)


def save_order(order: dict) -> None:
    new_file = not ORDERS_FILE.exists()
    with ORDERS_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(order))
        if new_file:
            writer.writeheader()
        writer.writerow(order)


# ---------- general commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or ""
    await update.message.reply_text(
        f"أهلاً {name} 👋\nأنا مساعد المتجر، أقدر أعرض لك المنتجات وأسجل طلبك في دقيقة.",
        reply_markup=MAIN_MENU,
    )


async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اختار منتج علشان تشوف تفاصيله:", reply_markup=products_keyboard("info"))


async def product_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    p = product_by_id(query.data.split(":", 1)[1])
    if not p:
        return await query.edit_message_text("المنتج ده مش متاح حالياً.")
    text = f'*{p["name"]}*\n\n{p["description"]}\n\n💰 السعر: {p["price"]} جنيه / {p["unit"]}'
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 اطلب المنتج ده", callback_data=f'order:{p["id"]}')]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 للتواصل: 01000000000\n🕘 يومياً من 10 ص لـ 10 م")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("متجر متخصص في الأرضيات وبدائل السجاد، وبنوصل لكل المحافظات 🚚")


# ---------- order conversation ----------
async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry from the menu button: ask which product."""
    await update.message.reply_text("اختار المنتج اللي عاوز تطلبه:", reply_markup=products_keyboard("order"))
    return QTY


async def order_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    p = product_by_id(query.data.split(":", 1)[1])
    if not p:
        await query.edit_message_text("المنتج ده مش متاح حالياً.")
        return ConversationHandler.END
    context.user_data["order"] = {"product": p}
    await query.edit_message_text(f'اخترت: {p["name"]}\nمحتاج كام {p["unit"]}؟ (اكتب رقم)')
    return QTY


async def order_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "order" not in context.user_data:
        await update.message.reply_text("اختار المنتج من القائمة الأول 👆")
        return QTY
    text = update.message.text.strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if not text.isdigit() or not 0 < int(text) <= 1000:
        await update.message.reply_text("من فضلك اكتب رقم صحيح، مثلاً 5")
        return QTY
    context.user_data["order"]["qty"] = int(text)
    await update.message.reply_text("تمام 👍 اسمك إيه؟")
    return NAME


async def order_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["name"] = update.message.text.strip()
    await update.message.reply_text("رقم موبايلك؟")
    return PHONE


async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if not re.fullmatch(r"\+?\d{10,14}", phone.replace(" ", "")):
        await update.message.reply_text("الرقم مش مظبوط، اكتبه تاني من فضلك (مثلاً 01012345678)")
        return PHONE
    context.user_data["order"]["phone"] = phone.replace(" ", "")
    await update.message.reply_text("العنوان بالتفصيل (المحافظة، المنطقة، الشارع)؟")
    return ADDRESS


async def order_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    o = context.user_data["order"]
    o["address"] = update.message.text.strip()
    p = o["product"]
    o["total"] = p["price"] * o["qty"]
    summary = (
        "📋 *ملخص الطلب*\n\n"
        f'المنتج: {p["name"]}\nالكمية: {o["qty"]} {p["unit"]}\n'
        f'الإجمالي: {o["total"]} جنيه\n\n'
        f'الاسم: {o["name"]}\nالموبايل: {o["phone"]}\nالعنوان: {o["address"]}'
    )
    kb = ReplyKeyboardMarkup([["✅ تأكيد", "❌ إلغاء"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=kb)
    return CONFIRM


async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "تأكيد" not in update.message.text:
        return await cancel(update, context)

    o = context.user_data.pop("order")
    order_id = datetime.now().strftime("%y%m%d%H%M%S")
    record = {
        "order_id": order_id, "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "product": o["product"]["name"], "qty": o["qty"], "total": o["total"],
        "name": o["name"], "phone": o["phone"], "address": o["address"],
        "telegram_user": update.effective_user.username or update.effective_user.id,
    }
    save_order(record)
    log.info("New order %s", order_id)

    await update.message.reply_text(
        f"✅ تم تسجيل طلبك رقم {order_id}\nهنتواصل معاك قريب لتأكيد الشحن. شكراً لثقتك 🌟",
        reply_markup=MAIN_MENU,
    )
    if ADMIN_CHAT_ID:
        alert = "🔔 طلب جديد\n" + "\n".join(f"{k}: {v}" for k, v in record.items())
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=alert)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("order", None)
    await update.message.reply_text("تم إلغاء الطلب.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


# ---------- admin ----------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stats — order count and revenue (store owner only)."""
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return
    if not ORDERS_FILE.exists():
        return await update.message.reply_text("مفيش طلبات لسه.")
    with ORDERS_FILE.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    revenue = sum(float(r["total"]) for r in rows)
    await update.message.reply_text(f"📊 عدد الطلبات: {len(rows)}\n💰 الإجمالي: {revenue:,.0f} جنيه")


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/id — shows your chat id (use it as ADMIN_CHAT_ID)."""
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Put it in the .env file.")

    app = Application.builder().token(BOT_TOKEN).build()
    text = filters.TEXT & ~filters.COMMAND

    order_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("اطلب الآن"), order_start),
            CallbackQueryHandler(order_pick, pattern=r"^order:"),
        ],
        states={
            QTY: [CallbackQueryHandler(order_pick, pattern=r"^order:"), MessageHandler(text, order_qty)],
            NAME: [MessageHandler(text, order_name)],
            PHONE: [MessageHandler(text, order_phone)],
            ADDRESS: [MessageHandler(text, order_address)],
            CONFIRM: [MessageHandler(text, order_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("إلغاء"), cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("id", my_id))
    app.add_handler(order_conv)
    app.add_handler(CallbackQueryHandler(product_info, pattern=r"^info:"))
    app.add_handler(MessageHandler(filters.Regex("المنتجات"), show_products))
    app.add_handler(MessageHandler(filters.Regex("تواصل"), contact))
    app.add_handler(MessageHandler(filters.Regex("عن المتجر"), about))

    log.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
