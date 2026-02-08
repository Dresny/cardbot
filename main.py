
import os
import random
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from config import Config
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()


class CardBot:
    def __init__(self):
        self.config = Config()
        self.app = Application.builder().token(self.config.TOKEN).build()

        # Регистрация обработчиков
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("cards", self.show_cards_command))
        self.app.add_handler(CommandHandler("sell", self.sell_card_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))

        # Запуск бота
        logger.info("Бот запущен!")

    async def check_subscription(self, user_id: int) -> bool:
        """Проверка подписки на канал"""
        try:
            member = await self.app.bot.get_chat_member(
                chat_id=self.config.CHANNEL_ID,
                user_id=user_id
            )
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки: {e}")
            return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        db.add_user(user.id, user.username)

        # Проверка подписки
        if not await self.check_subscription(user.id):
            keyboard = [
                [InlineKeyboardButton("📢 Подписаться на канал",
                                      url=f"https://t.me/podslusheno2120")],
                [InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "👋 Привет! Для использования бота нужно подписаться на наш канал.\n"
                "Подпишись и нажми кнопку ниже 👇",
                reply_markup=reply_markup
            )
            return

        await self.show_main_menu(update, context)

    async def get_channel_username(self):
        """Получение username канала"""
        try:
            chat = await self.app.bot.get_chat(self.config.CHANNEL_ID)
            return chat.username
        except:
            return "your_channel"

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                             message_id: int = None):
        """Показать главное меню"""
        user = update.effective_user
        user_data = db.get_user(user.id)

        keyboard = [
            [InlineKeyboardButton("🎁 Открыть ящик", callback_data="open_box")],
            [InlineKeyboardButton("🃏 Мои карточки", callback_data="my_cards")],
            [InlineKeyboardButton("🏆 Топ 10", callback_data="top_players")],
            [InlineKeyboardButton("💰 Баланс", callback_data="show_balance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"🎮 Добро пожаловать, {user.first_name}!\n\n"
            f"💰 Баланс: {user_data['balance'] if user_data else 0} тенге\n"
            f"🃏 Карточек в коллекции: {db.get_card_count(user.id)}\n\n"
            "Выберите действие:"
        )

        if message_id:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup
            )
        else:
            if update.callback_query:
                await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)

    async def open_box(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Открытие ящика с карточкой"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        # Проверка подписки
        if not await self.check_subscription(user_id):
            await query.message.reply_text("❌ Вы отписались от канала! Подпишитесь снова.")
            return

        # Проверка времени
        if not db.can_open_box(user_id):
            user_data = db.get_user(user_id)
            last_opened = datetime.fromisoformat(user_data['last_opened'])
            next_time = last_opened + timedelta(hours=1)
            time_left = next_time - datetime.now()

            minutes = int(time_left.total_seconds() // 60)
            seconds = int(time_left.total_seconds() % 60)

            await query.message.reply_text(
                f"⏳ Следующее открытие через: {minutes} мин {seconds} сек"
            )
            return

        # Получение случайной карточки
        card_info = self.get_random_card()
        if not card_info:
            await query.message.reply_text("❌ Ошибка: карточки не найдены!")
            return

        # Сохранение карточки в БД
        db.add_card(user_id, card_info['name'], card_info['rarity'], card_info['path'])
        db.update_last_opened(user_id)

        # Отправка карточки
        with open(card_info['path'], 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=(
                    f"🎉 Вы получили карточку!\n\n"
                    f"🏷 Название: {card_info['name']}\n"
                    f"⭐ Редкость: {card_info['rarity']}\n"
                    f"💰 Цена продажи: {self.config.PRICES[card_info['rarity']]} тенге\n\n"
                    f"ID карточки: {db.get_user_cards(user_id)[0]['id']}"
                )
            )

        await self.show_main_menu(update, context, query.message.message_id)

    def get_random_card(self):
        """Получение случайной карточки из папок"""
        try:
            # Веса для разных редкостей (можно настроить)
            rarities = ["Обычный", "Редкий", "Легендарный", "Мифик", "Секрет"]
            weights = [40, 30, 15, 10, 5]  # в процентах

            chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]
            rarity_path = os.path.join(self.config.CARDS_PATH, chosen_rarity)

            # Получение всех карточек в папке
            cards = [f for f in os.listdir(rarity_path)
                     if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]

            if not cards:
                return None

            chosen_card = random.choice(cards)
            card_path = os.path.join(rarity_path, chosen_card)
            card_name = os.path.splitext(chosen_card)[0]

            return {
                'name': card_name,
                'rarity': chosen_rarity,
                'path': card_path
            }
        except Exception as e:
            logger.error(f"Ошибка при получении карточки: {e}")
            return None

    async def show_cards_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /cards"""
        user = update.effective_user
        await self.show_cards(user.id, update.message.chat.id, context)

    async def show_cards(self, user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                         message_id: int = None):
        """Показать карточки пользователя"""
        cards = db.get_user_cards(user_id)

        if not cards:
            text = "📭 У вас пока нет карточек!"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        else:
            text = "🃏 Ваши карточки:\n\n"
            for i, card in enumerate(cards, 1):
                price = self.config.PRICES.get(card['rarity'], 0)
                text += f"{i}. {card['card_name']}\n"
                text += f"   ⭐ Редкость: {card['rarity']}\n"
                text += f"   💰 Цена: {price} тенге\n"
                text += f"   🆔 ID: {card['id']}\n\n"

            text += "\nДля продажи карточки используйте команду: /sell <id>"

            keyboard = [
                [InlineKeyboardButton("💰 Продать все", callback_data="sell_all")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup
            )

    async def sell_card_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Продажа карточки по ID"""
        if not context.args:
            await update.message.reply_text("Использование: /sell <id_карточки>")
            return

        try:
            card_id = int(context.args[0])
            user_id = update.effective_user.id

            # Продажа карточки
            rarity = db.sell_card(card_id, user_id)

            if rarity:
                price = self.config.PRICES[rarity]
                db.update_balance(user_id, price)
                user_data = db.get_user(user_id)

                await update.message.reply_text(
                    f"✅ Карточка продана за {price} тенге!\n"
                    f"💰 Новый баланс: {user_data['balance']} тенге\n"
                    f"🃏 Осталось карточек: {db.get_card_count(user_id)}"
                )
            else:
                await update.message.reply_text("❌ Карточка не найдена или уже продана!")

        except ValueError:
            await update.message.reply_text("❌ Неверный ID карточки! Используйте число.")
        except Exception as e:
            logger.error(f"Ошибка при продаже: {e}")
            await update.message.reply_text("❌ Произошла ошибка при продаже!")

    async def show_top_players(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать топ-10 игроков"""
        query = update.callback_query
        if query:
            await query.answer()

        top_players = db.get_top_players(10)

        if not top_players:
            text = "🏆 Топ игроков пока пуст!"
        else:
            text = "🏆 Топ 10 игроков:\n\n"
            emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

            for i, player in enumerate(top_players):
                if i < len(emojis):
                    emoji = emojis[i]
                else:
                    emoji = f"{i + 1}."

                username = player['username'] or f"User_{player['user_id']}"
                text += (
                    f"{emoji} @{username}\n"
                    f"   💰 Баланс: {player['balance']} тенге\n"
                    f"   🃏 Карточек: {player['card_count']}\n\n"
                )

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.message.edit_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать баланс"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        user_data = db.get_user(user_id)

        text = (
            f"💰 Ваш баланс: {user_data['balance']} тенге\n"
            f"🃏 Карточек в коллекции: {db.get_card_count(user_id)}"
        )

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(text, reply_markup=reply_markup)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        data = query.data

        await query.answer()  # Убираем "часики" на кнопке

        if data == "check_subscription":
            if await self.check_subscription(query.from_user.id):
                await self.show_main_menu(update, context, query.message.message_id)
            else:
                await query.answer("Вы ещё не подписались!", show_alert=True)

        elif data == "open_box":
            await self.open_box(update, context)

        elif data == "my_cards":
            await self.show_cards(query.from_user.id, query.message.chat.id, context,
                                  query.message.message_id)

        elif data == "top_players":
            await self.show_top_players(update, context)

        elif data == "show_balance":
            await self.show_balance(update, context)

        elif data == "main_menu":
            await self.show_main_menu(update, context, query.message.message_id)

        elif data == "sell_all":
            # Дополнительная функция: продать все карточки
            user_id = query.from_user.id
            cards = db.get_user_cards(user_id)

            if not cards:
                await query.answer("У вас нет карточек для продажи!", show_alert=True)
                return

            total_price = 0
            sold_count = 0

            for card in cards:
                rarity = card['rarity']
                price = self.config.PRICES.get(rarity, 0)
                db.sell_card(card['id'], user_id)
                db.update_balance(user_id, price)
                total_price += price
                sold_count += 1

            user_data = db.get_user(user_id)
            await query.message.edit_text(
                f"💰 Продано {sold_count} карточек за {total_price} тенге!\n"
                f"💵 Новый баланс: {user_data['balance']} тенге"
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда помощи"""
        help_text = (
            "🎮 *Помощь по боту*\n\n"
            "📌 *Основные команды:*\n"
            "/start - Начать работу с ботом\n"
            "/cards - Показать ваши карточки\n"
            "/sell <id> - Продать карточку по ID\n"
            "/help - Показать это сообщение\n\n"
            "📋 *Как работает бот:*\n"
            "1️⃣ Подпишитесь на канал\n"
            "2️⃣ Каждый час можно открыть ящик\n"
            "3️⃣ Получайте карточки разной редкости\n"
            "4️⃣ Продавайте карточки или собирайте коллекцию\n"
            "5️⃣ Соревнуйтесь с другими в топе\n\n"
            "💰 *Цены карточек:*\n"
            f"Обычный: {self.config.PRICES['Обычный']} тенге\n"
            f"Редкий: {self.config.PRICES['Редкий']} тенге\n"
            f"Мифик: {self.config.PRICES['Мифик']} тенге\n"
            f"Легендарный: {self.config.PRICES['Легендарный']} тенге\n"
            f"Секрет: {self.config.PRICES['Секрет']} тенге"
        )

        await update.message.reply_text(help_text, parse_mode='Markdown')

    def run(self):
        """Запуск бота"""
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    bot = CardBot()
    bot.run()