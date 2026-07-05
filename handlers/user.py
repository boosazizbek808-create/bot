import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from database import add_user, get_channels, get_movie
from keyboards import subscribe_keyboard, main_menu_keyboard

user_router = Router()


async def get_not_subscribed_channels(bot: Bot, user_id: int) -> list:
    """Foydalanuvchi hali obuna bo'lmagan kanal/guruhlar ro'yxatini qaytaradi."""
    channels = await get_channels()
    not_subscribed = []
    for chat_id, title, username, invite_link, chat_type in channels:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            logging.info(f"[SUBCHECK] chat={title} ({chat_id}) user={user_id} status={member.status}")
            if member.status in ("left", "kicked"):
                not_subscribed.append((chat_id, title, username, invite_link, chat_type))
        except TelegramBadRequest as e:
            logging.warning(f"[SUBCHECK-ERROR] chat={title} ({chat_id}) user={user_id} error={e}")
            # Xavfsizlik uchun: tekshirib bo'lmasa, obuna bo'lmagan deb hisoblaymiz
            not_subscribed.append((chat_id, title, username, invite_link, chat_type))
    return not_subscribed


@user_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await add_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name
    )

    not_subscribed = await get_not_subscribed_channels(bot, message.from_user.id)

    if not_subscribed:
        await message.answer(
            "👋 Assalomu alaykum!\n\n"
            "Botdan foydalanish uchun quyidagi kanal/guruh(lar)ga obuna bo'ling, "
            "so'ngra <b>✅ Tekshirish</b> tugmasini bosing:",
            reply_markup=subscribe_keyboard(not_subscribed)
        )
    else:
        await message.answer(
            "✅ Xush kelibsiz! Quyidagi menyudan foydalanishingiz mumkin:",
            reply_markup=main_menu_keyboard()
        )


@user_router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    not_subscribed = await get_not_subscribed_channels(bot, callback.from_user.id)

    if not_subscribed:
        await callback.answer(
            "❌ Siz hali barcha kanal/guruhlarga obuna bo'lmadingiz!",
            show_alert=True
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=subscribe_keyboard(not_subscribed))
        except TelegramBadRequest:
            pass
    else:
        await callback.message.delete()
        await callback.message.answer(
            "✅ Rahmat! Endi botdan to'liq foydalanishingiz mumkin:",
            reply_markup=main_menu_keyboard()
        )


# ---------- ASOSIY MENYU TUGMALARI ----------

@user_router.message(F.text == "🎬 Kino olish")
async def ask_for_code(message: Message, bot: Bot):
    not_subscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if not_subscribed:
        await message.answer(
            "❌ Avval majburiy kanal/guruhlarga obuna bo'ling:",
            reply_markup=subscribe_keyboard(not_subscribed)
        )
        return
    await message.answer("🔑 Kino kodini yuboring (masalan: <code>7</code>):")


@user_router.message(F.text == "ℹ️ Bot haqida")
async def about_bot(message: Message):
    await message.answer("Bu bot orqali kino kodi yordamida film olishingiz mumkin. Sozlamalarni admin boshqaradi.")


# ---------- KINO KODINI QIDIRISH ----------
# Diqqat: bu handler eng oxirida turishi kerak, chunki u har qanday
# matnni "kod" deb qabul qiladi (yuqoridagi aniq tugmalar bundan mustasno)

@user_router.message(F.text)
async def handle_possible_code(message: Message, bot: Bot):
    not_subscribed = await get_not_subscribed_channels(bot, message.from_user.id)
    if not_subscribed:
        await message.answer(
            "❌ Avval majburiy kanal/guruhlarga obuna bo'ling, so'ngra kodni qayta yuboring:",
            reply_markup=subscribe_keyboard(not_subscribed)
        )
        return

    code = message.text.strip()
    movie = await get_movie(code)

    if movie is None:
        await message.answer("❌ Bunday kodli kino topilmadi. Kodni tekshirib, qaytadan yuboring.")
        return

    _, title, file_id = movie
    try:
        await message.answer_video(file_id, caption=f"🎬 {title}")
    except TelegramBadRequest:
        await message.answer("⚠️ Videoni yuborishda xatolik yuz berdi. Admin bilan bog'laning.")
