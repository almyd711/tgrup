import logging
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime
import random

# ✅ إعدادات
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6964741705
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

# ✅ الأزواج المسموحة
CURRENCY_PAIRS = [
    "USD/CHF", "AUD/USD", "USD/JPY",
    "USD/CAD", "EUR/JPY", "EUR/CAD",
    "EUR/USD", "EUR/CHF", "EUR/AUD"
]

# ✅ حالة المستخدمين
approved_users = set()
pending_users = {}
user_selected_pair = {}

# ✅ قائمة الانتظار
pending_requests = {}

# ✅ دالة لجلب البيانات من Alpha Vantage
def fetch_data(symbol):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=1min&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        time_series = data.get("Time Series (1min)", {})
        latest_time = sorted(time_series.keys())[-1]
        close_price = float(time_series[latest_time]["4. close"])
        return close_price
    except:
        return None

# ✅ رسالة الدفع
payment_info = (
    "💳 *للدخول الكامل، يرجى دفع 5 USDT فقط:*\n\n"
    "🔗 *USDT (BEP20)*\n`0x3a5db3aec7c262017af9423219eb64b5eb6643d7`\n\n"
    "🔗 *USDT (TRC20)*\n`THrV9BLydZTYKox1MnnAivqitHBEz3xKiq`\n\n"
    "💼 *Payeer:*\n`P1113622813`\n\n"
    "🔁 بعد الدفع اضغط على الزر أدناه لإرسال إثبات الدفع."
)

# ✅ لوحة الدفع
def get_payment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تم الدفع", callback_data="paid")],
    ])

# ✅ قائمة أزواج العملات
def get_pairs_keyboard():
    keyboard = []
    row = []
    for i, pair in enumerate(CURRENCY_PAIRS, 1):
        row.append(InlineKeyboardButton(pair, callback_data=f"pair_{pair}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

# ✅ بدء الاستخدام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID or user_id in approved_users:
        await update.message.reply_text("✅ مرحباً بك، يمكنك الآن اختيار زوج العملة:", reply_markup=get_pairs_keyboard())
    elif user_id in pending_users:
        await update.message.reply_text("⏳ طلبك قيد المراجعة من قبل المطور، الرجاء الانتظار.")
    else:
        pending_users[user_id] = update.effective_user
        await update.message.reply_text(
            "👋 أهلاً بك!\nلبدء الاستخدام يرجى دفع رسوم الاشتراك:\n\n" + payment_info,
            reply_markup=get_payment_keyboard(),
            parse_mode="Markdown"
        )

# ✅ عند إرسال إثبات الدفع
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "paid":
        await query.message.reply_text("📸 أرسل الآن صورة إثبات الدفع.")
    elif query.data.startswith("pair_"):
        pair = query.data.split("_", 1)[1]
        user_selected_pair[user_id] = pair
        await query.message.reply_text(f"🔄 تم اختيار الزوج: {pair}\n📊 جاري توليد التوصية...")
        await send_recommendation(user_id, context)

# ✅ استقبال إثبات الدفع (صورة)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in approved_users:
        await update.message.reply_text("✅ أنت بالفعل مشترك.")
        return

    pending_requests[user.id] = {
        "name": user.full_name,
        "username": user.username,
        "user_id": user.id,
    }

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📥 طلب اشتراك جديد:\n\n"
            f"👤 الاسم: {user.full_name}\n"
            f"🔗 المعرف: @{user.username}\n"
            f"🆔 ID: `{user.id}`\n\n"
            f"📎 أرسل صورة إثبات الدفع"
        ),
        parse_mode="Markdown"
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id)

# ✅ قبول أو رفض المستخدم
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not pending_requests:
        await update.message.reply_text("✅ لا يوجد طلبات معلقة.")
        return

    for user_id, info in pending_requests.items():
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ قبول", callback_data=f"accept_{user_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")
            ]
        ])
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"👤 الاسم: {info['name']}\n"
                f"🔗 @{info['username']}\n"
                f"🆔 {info['user_id']}"
            ),
            reply_markup=keyboard
        )

async def decision_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = int(data.split("_")[1])

    if "accept" in data:
        approved_users.add(user_id)
        await context.bot.send_message(chat_id=user_id, text="✅ تم قبول اشتراكك، يمكنك الآن استخدام البوت.")
        await query.message.reply_text("✅ تم القبول.")
    elif "reject" in data:
        await context.bot.send_message(chat_id=user_id, text="❌ تم رفض طلبك من قبل الإدارة.")
        await query.message.reply_text("❌ تم الرفض.")

    if user_id in pending_requests:
        del pending_requests[user_id]

# ✅ توليد توصية (تجريبية حالياً)
async def send_recommendation(user_id, context):
    pair = user_selected_pair.get(user_id, "EUR/USD")
    now = datetime.now().strftime("%I:%M %p")
    direction = random.choice(["شراء (CALL)", "بيع (PUT)"])
    rsi = round(random.uniform(45, 70), 2)

    recommendation = (
        f"📊 التوصية: {direction}\n"
        f"💱 الزوج: {pair}\n"
        f"🔍 التحليل:\n"
        f"🔸 RSI = {rsi}\n"
        f"✅ منطقة تداول {'صاعدة' if rsi > 50 else 'هابطة'}\n\n"
        f"⏱️ الفريم: 1 دقيقة\n"
        f"⏰ التوقيت: {now}"
    )

    await context.bot.send_message(chat_id=user_id, text=recommendation)

# ✅ تشغيل البوت
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CallbackQueryHandler(decision_callback, pattern="^(accept|reject)_"))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("✅ Bot started...")
    app.run_polling()
