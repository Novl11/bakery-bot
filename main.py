import os
import asyncio
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError):
    ADMIN_ID = None

def load_bakery_data():
    try:
        if os.path.exists("bakery_info.txt"):
            with open("bakery_info.txt", "r", encoding="utf-8") as f:
                return f.read()
        return ""
    except Exception:
        return "Error reading data."

BAKERY_DATA = load_bakery_data()

SYSTEM_PROMPT = f"""
You are a manager for ermachenkova.dessert. Your task is to consult and collect order data.
Bakery data:
{BAKERY_DATA}

Workflow:
1. If the client wants to order, step-by-step ask for: Item, Quantity, Design, Date, Phone.
2. If the client asks about the menu/prices, provide info from Bakery data.
3. Be polite and helpful.
4. When ALL order data is collected, summarize the order and end with: [CONFIRMATION_REQUIRED]
"""

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

async def get_gemini_response(user_id, text):
    chat = model.start_chat(history=[])
    response = chat.send_message(f"{SYSTEM_PROMPT}\n\nUser: {text}")
    return response.text

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Hello! I am your bakery assistant. How can I help you today?")

@dp.message()
async def handle_message(message: types.Message):
    response_text = await get_gemini_response(message.from_user.id, message.text)
    if "[CONFIRMATION_REQUIRED]" in response_text and ADMIN_ID:
        clean_text = response_text.replace("[CONFIRMATION_REQUIRED]", "").strip()
        await message.answer(clean_text)
        builder = InlineKeyboardBuilder()
        builder.button(text="Confirm", callback_data=f"confirm_{message.from_user.id}")
        builder.button(text="Reject", callback_data=f"reject_{message.from_user.id}")
        await bot.send_message(ADMIN_ID, f"New order from {message.from_user.full_name}:\n{clean_text}", reply_markup=builder.as_markup())
    else:
        await message.answer(response_text)

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_order(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[1]
    await bot.send_message(user_id, "Your order has been confirmed by the confectioner!")
    await callback.message.edit_text(callback.message.text + "\n\n[X] **ORDER CONFIRMED**")
    await callback.answer("Order confirmed")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[1]
    await bot.send_message(user_id, "Unfortunately, the confectioner cannot accept this order.")
    await callback.message.edit_text(callback.message.text + "\n\n[X] **ORDER REJECTED**")
    await callback.answer("Order rejected")

async def handle_health_check(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    asyncio.create_task(start_web_server())
    print("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
