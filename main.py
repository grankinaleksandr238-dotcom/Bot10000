# ==================== ЧАСТЬ 1: ИМПОРТЫ, НАСТРОЙКИ, БАЗА ДАННЫХ, ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И ТЕКСТОВЫЕ ФРАЗЫ ====================

import asyncio
import logging
import random
import os
import time
import string
import csv
import io
import json
import html
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Union
from collections import defaultdict

import asyncpg
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
    InlineKeyboardButton, InputFile
)
from aiogram.utils.exceptions import (
    BotBlocked, UserDeactivated, ChatNotFound, RetryAfter,
    TelegramAPIError, MessageNotModified, TerminatedByOtherGetUpdates
)
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from aiogram.utils import executor

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

SUPER_ADMINS_STR = os.getenv("SUPER_ADMINS", "")
SUPER_ADMINS = [int(x.strip()) for x in SUPER_ADMINS_STR.split(",") if x.strip()]

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан. Создайте PostgreSQL базу.")

# Добавляем sslmode если нет
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

# Настройки по умолчанию (расширенные и структурированные)
DEFAULT_SETTINGS = {
    # Кража
    "random_attack_cost": "0",
    "targeted_attack_cost": "50",
    "theft_cooldown_minutes": "30",
    "theft_success_chance": "40",
    "theft_defense_chance": "20",
    "theft_defense_penalty": "10",
    "min_theft_amount": "5",
    "max_theft_amount": "15",

    # Казино и игры
    "casino_win_chance": "25",
    "casino_min_bet": "50",
    "casino_max_bet": "1000",
    "casino_multiplier": "4",
    "dice_multiplier": "2",
    "guess_multiplier": "5",
    "guess_reputation": "1",
    "slots_multiplier_three": "3",
    "slots_multiplier_diamond": "5",
    "slots_multiplier_seven": "10",
    "slots_min_bet": "1",
    "slots_max_bet": "500",
    "roulette_color_multiplier": "2",
    "roulette_green_multiplier": "18",
    "roulette_number_multiplier": "36",
    "roulette_min_bet": "1",
    "roulette_max_bet": "500",

    # Уведомления
    "chat_notify_big_win": "1",
    "chat_notify_big_purchase": "1",
    "chat_notify_giveaway": "1",

    # Подгон (gift)
    "gift_amount": "30",
    "gift_limit_per_day": "3",
    "gift_global_limit_per_user": "4",
    "gift_cooldown": "60",

    # Рефералы
    "referral_bonus": "50",
    "referral_reputation": "2",

    # Опыт
    "exp_per_casino_win": "5",
    "exp_per_casino_lose": "1",
    "exp_per_dice_win": "3",
    "exp_per_dice_lose": "1",
    "exp_per_guess_win": "4",
    "exp_per_guess_lose": "1",
    "exp_per_slots_win": "6",
    "exp_per_slots_lose": "2",
    "exp_per_roulette_win": "5",
    "exp_per_roulette_lose": "1",
    "exp_per_theft_success": "10",
    "exp_per_theft_fail": "2",
    "exp_per_theft_defense": "5",
    "exp_per_game_win": "15",
    "exp_per_game_lose": "3",

    # Уровни
    "level_multiplier": "100",
    "level_reward_coins": "30",
    "level_reward_reputation": "3",
    "level_reward_coins_increment": "5",
    "level_reward_reputation_increment": "1",

    # Репутация
    "reputation_theft_bonus": "0.5",
    "reputation_defense_bonus": "0.5",

    # Боссы
    "boss_spawn_chance": "20",
    "boss_min_interval": "360",
    "boss_max_per_day": "2",
    "boss_hp_multiplier": "200",
    "boss_attack_cooldown": "3",
    "boss_base_damage": "20",
    "boss_reward_coins": "500",
    "boss_reward_coins_variance": "200",

    # Статы за уровень
    "stat_strength_per_level": "1",
    "stat_agility_per_level": "1",
    "stat_defense_per_level": "1",

    # Аукцион
    "auction_min_bid_step": "10",
    "auction_commission": "0",
    "auction_notify_chats": "1",

    # Бой в чатах
    "fight_cooldown_minutes": "30",
    "fight_base_damage": "5",
    "fight_damage_variance": "3",
    "fight_authority_min": "1",
    "fight_authority_max": "3",

    # Качалка (gym)
    "gym_strength_cost": "10",
    "gym_agility_cost": "10",
    "gym_defense_cost": "10",

    # Очистка логов
    "cleanup_days_fight_logs": "7",
    "cleanup_days_bosses": "7",
    "cleanup_days_auctions": "30",
    "cleanup_days_purchases": "30",
    "cleanup_days_giveaways": "30",
    "cleanup_days_user_tasks": "30",

    # Автоудаление команд
    "auto_delete_commands_seconds": "30",

    # Продажа авторитета
    "min_authority_price": "1",

    # Контрабанда
    "smuggle_min_duration": "30",
    "smuggle_max_duration": "120",
    "smuggle_success_chance": "60",
    "smuggle_caught_chance": "30",
    "smuggle_lost_chance": "10",
    "smuggle_base_amount": "10",
    "smuggle_authority_multiplier": "0.1",
    "smuggle_cooldown_minutes": "60",
    "smuggle_fail_penalty_minutes": "30",
    "cleanup_days_smuggle": "30",
}

# Константы
ITEMS_PER_PAGE = 10
BIG_WIN_THRESHOLD = 100
BIG_PURCHASE_THRESHOLD = 100
MAX_ROOMS = 20
MIN_PLAYERS = 2
MAX_PLAYERS = 5
MIN_BET = 3

# Список всех доступных прав для админов
PERMISSIONS_LIST = [
    "manage_users",
    "manage_shop",
    "manage_giveaways",
    "manage_channels",
    "manage_promocodes",
    "manage_tasks",
    "manage_chats",
    "manage_bosses",
    "manage_helpers",
    "manage_auctions",
    "manage_ads",
    "view_stats",
    "manage_bans",
    "broadcast",
    "cleanup",
    "edit_settings",
    "manage_admins"
]

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

# Глобальные переменные
db_pool = None
settings_cache = {}
last_settings_update = 0
channels_cache = []
last_channels_update = 0
confirmed_chats_cache = {}
last_confirmed_chats_update = 0

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==================== ТЕКСТОВЫЕ ФРАЗЫ ====================
BONUS_PHRASES = [
    "🎉 Отлично, лови +{bonus} баксов!",
    "💰 Ты сегодня богат! +{bonus} баксов!",
    "🌟 Удача улыбнулась! +{bonus} баксов в карман!",
    "🍀 Держи +{bonus} баксов на удачу!",
    "🎁 Поздравляю! +{bonus} баксов твои!"
]

CASINO_WIN_PHRASES = [
    "🎰 Ура! Ты выиграл {win} баксов (чистыми {profit})!",
    "🍒 Джекпот! +{profit} баксов!",
    "💫 Фортуна на твоей стороне! +{profit} баксов!",
    "🎲 Победа! {profit} баксов твои!",
    "✨ Ты обыграл казино! +{profit} баксов!"
]

CASINO_LOSE_PHRASES = [
    "😢 Обидно, потерял {loss} баксов.",
    "💔 Не повезло, минус {loss}.",
    "📉 Проигрыш -{loss} баксов.",
    "🍂 В следующий раз повезёт, а пока -{loss}.",
    "⚡️ Увы, -{loss} баксов."
]

PURCHASE_PHRASES = [
    "✅ Куплено! Админ скоро свяжется.",
    "🛒 Товар твой! Жди админа.",
    "🎁 Отличная покупка! Админ уже в курсе.",
    "💎 Приятной игры! Админ напишет."
]

DICE_WIN_PHRASES = [
    "🎲 {dice1} + {dice2} = {total} — Победа! +{profit} баксов!",
    "🎲 Круто! {dice1}+{dice2}={total}, ты выиграл {profit}!",
    "🎲 Хороший бросок! {total} очков, выигрыш {profit}!"
]

DICE_LOSE_PHRASES = [
    "🎲 {dice1} + {dice2} = {total} — Проигрыш. -{loss} баксов.",
    "🎲 Эх, {total} очков, не повезло. -{loss}.",
    "🎲 В следующий раз повезёт, -{loss} баксов."
]

GUESS_WIN_PHRASES = [
    "🔢 Ты угадал! Было {secret}. Выигрыш: +{profit} баксов и +{rep} репутации!",
    "🔢 Красава! Число {secret}, твой выигрыш {profit} баксов!",
    "🔢 Удача! +{profit} баксов, репутация +{rep}!"
]

GUESS_LOSE_PHRASES = [
    "🔢 Не угадал. Было {secret}. -{loss} баксов.",
    "🔢 Увы, загадано {secret}. Теряешь {loss} баксов.",
    "🔢 Не повезло, правильный ответ {secret}. -{loss}."
]

SLOTS_WIN_PHRASES = [
    "🍒 {combo} — Ура! Выигрыш x{multiplier}! +{profit} баксов!",
    "🍋 Джекпот! {combo} приносит {profit} баксов!",
    "🍊 Крутая комбинация! x{multiplier}, +{profit} баксов!",
    "💎 Бриллианты! Твой выигрыш: {profit} баксов!"
]

SLOTS_LOSE_PHRASES = [
    "🍒 {combo} — Не повезло. -{loss} баксов.",
    "🍋 Мимо. Потеряно {loss} баксов.",
    "🍊 В следующий раз повезёт. -{loss}."
]

ROULETTE_WIN_PHRASES = [
    "🎡 Выпало {number} {color}! Ты выиграл {profit} баксов!",
    "🎡 Удача! Ставка сыграла, +{profit} баксов!",
    "🎡 Круто! {profit} баксов твои!"
]

ROULETTE_LOSE_PHRASES = [
    "🎡 Выпало {number} {color}. Твоя ставка не сыграла. -{loss} баксов.",
    "🎡 Увы, не в этот раз. Потеряно {loss} баксов.",
    "🎡 Мимо кассы. -{loss}."
]

FIGHT_HIT_PHRASES = [
    "💥 Ты нанёс {damage} урона банде! Заработал {authority} авторитета.",
    "⚡️ Твой удар точный! +{damage} урона, +{authority} авторитета.",
    "🔥 Ты нанёс {damage} урона и получил {authority} авторитета.",
    "🤜 Хрясь! Банда получила {damage} урона. Твой авторитет +{authority}.",
    "👊 Смачный удар! {damage} урона, {authority} авторитета.",
]

FIGHT_CRIT_PHRASES = [
    "💢 СОКРУШИТЕЛЬНЫЙ УДАР! Ты нанёс {damage} урона (крит!) и заработал {authority} авторитета.",
    "🌟 Ты в ярости! Критический урон {damage}, авторитет +{authority}.",
    "⚡️ МОЛНИЕНОСНЫЙ ВЫПАД! {damage} урона, +{authority} авторитета.",
]

FIGHT_COUNTER_PHRASES = [
    "😵 Банда контратаковала! Ты потерял {damage} баксов и не получил авторитет.",
    "💥 Ответный удар! Ты потерял {damage} баксов.",
    "👊 Тебя самого ударили! Минус {damage} баксов.",
]

AUTHORITY_SELL_PHRASES = [
    "💰 Продажа {amount} авторитета по {price} баксов/ед.",
    "💼 Предложение создано! ID: {offer_id}",
    "✅ Покупка совершена! Ты получил {amount} авторитета.",
]

SMUGGLE_SUCCESS_PHRASES = [
    "✅ Рейс завершён успешно! Ты привёз {amount} ед. контрабанды.",
    "💰 Товар доставлен заказчику. Твоя доля: {amount} ед.",
    "🎉 Таможню пройдено! +{amount} контрабанды.",
]

SMUGGLE_CAUGHT_PHRASES = [
    "🚨 Береговая охрана перехватила твоё судно! Ты потерял груз и теперь отсиживаешься.",
    "⛓ Полиция накрыла явочную квартиру. Придётся залечь на дно (кулдаун увеличен).",
    "👮‍♂️ Менты вышли на след. Контрабанда конфискована.",
]

SMUGGLE_LOST_PHRASES = [
    "🌊 Шторм уничтожил твоё судно! Ты ничего не привёз.",
    "💥 Корабль напоролся на рифы. Груз утонул.",
    "🔥 Двигатель взорвался. Придётся начинать сначала.",
]

MULTIPLAYER_PHRASES = [
    "🎮 Комната {game_id} создана!",
    "👥 Игроки: {players}",
    "🎯 Твой ход!",
    "🏆 Победитель: {winner}",
]

BUSINESS_BUY_PHRASES = [
    "✅ Ты приобрёл бизнес «{name}»! Он будет приносить доход.",
    "🏪 Поздравляю с покупкой! Теперь у тебя есть {name}.",
]

BUSINESS_COLLECT_PHRASES = [
    "💰 Ты собрал {coins} баксов и {cents} центов с бизнеса «{name}».",
    "💵 Прибыль от {name}: {coins} баксов {cents} центов.",
]

BUSINESS_NO_INCOME = [
    "⏳ В твоих бизнесах пока нет дохода. Загляни позже.",
]

GIVEAWAY_COMPLETED_PHRASE = [
    "🏁 Розыгрыш #{id} завершён! Победитель: {winner}",
    "🎉 Розыгрыш «{prize}» окончен! Список победителей: {winners}",
]

# ==================== МИДЛВАРЬ ДЛЯ ТРОТТЛИНГА ====================
class ThrottlingMiddleware(BaseMiddleware):
    """Ограничивает частоту сообщений от пользователя (кроме суперадминов)."""
    def __init__(self, rate_limit=1.0):
        self.rate_limit = rate_limit
        self.user_last_time = defaultdict(float)
        super().__init__()

    async def on_process_message(self, message: types.Message, data: dict):
        if message.chat.type != 'private' or await is_super_admin(message.from_user.id):
            return
        user_id = message.from_user.id
        now = time.time()
        if now - self.user_last_time[user_id] < self.rate_limit:
            await message.reply("⏳ Слишком много запросов. Подожди секунду.")
            raise CancelHandler()
        self.user_last_time[user_id] = now

dp.middleware.setup(ThrottlingMiddleware(rate_limit=0.5))

# ==================== ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ С ПОВТОРНЫМИ ПОПЫТКАМИ ====================
async def create_db_pool(retries: int = 5, delay: int = 3):
    """Создаёт пул соединений с БД, повторяя попытки при ошибках."""
    global db_pool
    for attempt in range(1, retries + 1):
        try:
            db_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=60,
                max_queries=50000,
                max_inactive_connection_lifetime=300
            )
            logging.info(f"✅ Подключение к PostgreSQL установлено (попытка {attempt})")
            return
        except Exception as e:
            logging.error(f"❌ Ошибка подключения к БД (попытка {attempt}/{retries}): {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                raise  # после всех попыток пробрасываем исключение дальше

# ==================== ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ ====================
async def init_db():
    """Создаёт все необходимые таблицы и индексы, если их нет."""
    async with db_pool.acquire() as conn:
        # Таблица users
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TIMESTAMP,
                balance INTEGER DEFAULT 0,
                reputation INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                negative_balance INTEGER DEFAULT 0,
                last_bonus TIMESTAMP,
                last_theft_time TIMESTAMP,
                theft_attempts INTEGER DEFAULT 0,
                theft_success INTEGER DEFAULT 0,
                theft_failed INTEGER DEFAULT 0,
                theft_protected INTEGER DEFAULT 0,
                casino_wins INTEGER DEFAULT 0,
                casino_losses INTEGER DEFAULT 0,
                dice_wins INTEGER DEFAULT 0,
                dice_losses INTEGER DEFAULT 0,
                guess_wins INTEGER DEFAULT 0,
                guess_losses INTEGER DEFAULT 0,
                slots_wins INTEGER DEFAULT 0,
                slots_losses INTEGER DEFAULT 0,
                roulette_wins INTEGER DEFAULT 0,
                roulette_losses INTEGER DEFAULT 0,
                multiplayer_wins INTEGER DEFAULT 0,
                multiplayer_losses INTEGER DEFAULT 0,
                exp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                strength INTEGER DEFAULT 1,
                agility INTEGER DEFAULT 1,
                defense INTEGER DEFAULT 1,
                last_gift_time TIMESTAMP,
                gift_count_today INTEGER DEFAULT 0,
                global_authority INTEGER DEFAULT 0,
                smuggle_goods INTEGER DEFAULT 0,
                smuggle_success INTEGER DEFAULT 0,
                smuggle_fail INTEGER DEFAULT 0
            )
        ''')

        # Таблица подтверждённых чатов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS confirmed_chats (
                chat_id BIGINT PRIMARY KEY,
                title TEXT,
                type TEXT,
                joined_date TIMESTAMP,
                confirmed_by BIGINT,
                confirmed_date TIMESTAMP,
                notify_enabled BOOLEAN DEFAULT TRUE,
                last_gift_date DATE,
                gift_count_today INTEGER DEFAULT 0,
                boss_last_spawn TIMESTAMP,
                boss_spawn_count INTEGER DEFAULT 0,
                auto_delete_enabled BOOLEAN DEFAULT TRUE
            )
        ''')

        # Запросы на подтверждение чатов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_confirmation_requests (
                chat_id BIGINT PRIMARY KEY,
                title TEXT,
                type TEXT,
                requested_by BIGINT,
                request_date TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')

        # Боссы
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bosses (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                name TEXT,
                level INTEGER,
                hp INTEGER,
                max_hp INTEGER,
                spawned_at TIMESTAMP,
                expires_at TIMESTAMP,
                reward_coins INTEGER,
                participants BIGINT[] DEFAULT '{}',
                status TEXT DEFAULT 'active',
                image_file_id TEXT,
                description TEXT
            )
        ''')

        # Атаки на босса
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS boss_attacks (
                boss_id INTEGER,
                user_id BIGINT,
                damage INTEGER,
                attack_time TIMESTAMP,
                PRIMARY KEY (boss_id, user_id)
            )
        ''')

        # Каналы для подписки
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                chat_id TEXT UNIQUE,
                title TEXT,
                invite_link TEXT
            )
        ''')

        # Рефералы
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT,
                referred_id BIGINT UNIQUE,
                referred_date TIMESTAMP,
                reward_given BOOLEAN DEFAULT FALSE,
                clicks INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT FALSE
            )
        ''')

        # Товары магазина
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                price INTEGER,
                stock INTEGER DEFAULT -1,
                photo_file_id TEXT
            )
        ''')

        # Покупки
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                item_id INTEGER,
                purchase_date TIMESTAMP,
                status TEXT DEFAULT 'pending',
                admin_comment TEXT
            )
        ''')

        # Промокоды
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0,
                created_at TIMESTAMP
            )
        ''')

        # Активации промокодов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS promo_activations (
                user_id BIGINT,
                promo_code TEXT,
                activated_at TIMESTAMP,
                PRIMARY KEY (user_id, promo_code)
            )
        ''')

        # Розыгрыши
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id SERIAL PRIMARY KEY,
                prize TEXT,
                description TEXT,
                end_date TIMESTAMP,
                media_file_id TEXT,
                media_type TEXT,
                status TEXT DEFAULT 'active',
                winner_id BIGINT,
                winners_count INTEGER DEFAULT 1,
                notified BOOLEAN DEFAULT FALSE
            )
        ''')

        # Участники розыгрышей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                user_id BIGINT,
                giveaway_id INTEGER,
                PRIMARY KEY (user_id, giveaway_id)
            )
        ''')

        # Админы
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_by BIGINT,
                added_date TIMESTAMP,
                permissions TEXT DEFAULT '[]'
            )
        ''')

        # Забаненные
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id BIGINT PRIMARY KEY,
                banned_by BIGINT,
                banned_date TIMESTAMP,
                reason TEXT
            )
        ''')

        # Настройки
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Задания
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                task_type TEXT,
                target_id TEXT,
                reward_coins INTEGER DEFAULT 0,
                reward_reputation INTEGER DEFAULT 0,
                required_days INTEGER DEFAULT 0,
                penalty_days INTEGER DEFAULT 0,
                created_by BIGINT,
                created_at TIMESTAMP,
                active BOOLEAN DEFAULT TRUE,
                max_completions INTEGER DEFAULT 1,
                completed_count INTEGER DEFAULT 0
            )
        ''')

        # Выполненные задания
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                user_id BIGINT,
                task_id INTEGER,
                completed_at TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'completed',
                PRIMARY KEY (user_id, task_id)
            )
        ''')

        # Мультиплеерные игры (комнаты)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS multiplayer_games (
                game_id TEXT PRIMARY KEY,
                host_id BIGINT,
                max_players INTEGER,
                bet_amount INTEGER,
                status TEXT DEFAULT 'waiting',
                deck TEXT,
                created_at TIMESTAMP,
                current_player_index INTEGER DEFAULT 0
            )
        ''')

        # Игроки в мультиплеере
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS game_players (
                game_id TEXT,
                user_id BIGINT,
                username TEXT,
                cards TEXT,
                value INTEGER DEFAULT 0,
                stopped BOOLEAN DEFAULT FALSE,
                joined_at TIMESTAMP,
                doubled BOOLEAN DEFAULT FALSE,
                surrendered BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (game_id, user_id)
            )
        ''')

        # Награды за уровень
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS level_rewards (
                level INTEGER PRIMARY KEY,
                coins INTEGER,
                reputation INTEGER
            )
        ''')

        # Аукционы
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS auctions (
                id SERIAL PRIMARY KEY,
                item_name TEXT NOT NULL,
                description TEXT,
                start_price INTEGER NOT NULL,
                current_price INTEGER NOT NULL,
                start_time TIMESTAMP NOT NULL DEFAULT NOW(),
                end_time TIMESTAMP,
                target_price INTEGER,
                status TEXT DEFAULT 'active',
                winner_id BIGINT,
                created_by BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                photo_file_id TEXT
            )
        ''')

        # Ставки на аукционе
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS auction_bids (
                id SERIAL PRIMARY KEY,
                auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                bid_amount INTEGER NOT NULL,
                bid_time TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Авторитет в чатах
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_authority (
                chat_id BIGINT,
                user_id BIGINT,
                authority INTEGER DEFAULT 0,
                total_damage INTEGER DEFAULT 0,
                fights INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        ''')

        # Глобальные кулдауны
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS global_cooldowns (
                user_id BIGINT,
                command TEXT,
                last_used TIMESTAMP,
                PRIMARY KEY (user_id, command)
            )
        ''')

        # Логи боёв
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fight_logs (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                user_id BIGINT,
                timestamp TIMESTAMP DEFAULT NOW(),
                damage INTEGER,
                authority_gained INTEGER,
                outcome TEXT
            )
        ''')

        # Реклама
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS ads (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                interval_minutes INTEGER DEFAULT 60,
                last_sent TIMESTAMP,
                enabled BOOLEAN DEFAULT TRUE,
                target TEXT DEFAULT 'chats'
            )
        ''')

        # Предложения продажи авторитета
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS authority_offers (
                id SERIAL PRIMARY KEY,
                seller_id BIGINT NOT NULL,
                amount INTEGER NOT NULL CHECK (amount > 0),
                price_per_unit INTEGER NOT NULL CHECK (price_per_unit >= 1),
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                buyer_id BIGINT,
                bought_at TIMESTAMP
            )
        ''')

        # Контрабандные рейсы (с полем chat_id)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS smuggle_runs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                chat_id BIGINT,
                start_time TIMESTAMP NOT NULL DEFAULT NOW(),
                end_time TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'in_progress',
                result TEXT,
                smuggle_amount INTEGER DEFAULT 0,
                notified BOOLEAN DEFAULT FALSE
            )
        ''')

        # Типы бизнесов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS business_types (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                cost_smuggle INTEGER NOT NULL,
                income_per_hour INTEGER NOT NULL,
                max_storage INTEGER NOT NULL,
                required_authority INTEGER DEFAULT 0
            )
        ''')

        # Бизнесы пользователей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_businesses (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                business_type_id INTEGER REFERENCES business_types(id),
                level INTEGER DEFAULT 1,
                last_collection TIMESTAMP,
                accumulated INTEGER DEFAULT 0,
                UNIQUE(user_id, business_type_id)
            )
        ''')

        # Индексы для ускорения
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_reputation ON users(reputation DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_total_spent ON users(total_spent DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_status ON giveaways(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_promo_activations_user ON promo_activations(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_expires ON user_tasks(expires_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_active ON tasks(active)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_multiplayer_games_status ON multiplayer_games(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_level ON users(level)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_exp ON users(exp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_bosses_chat_status ON bosses(chat_id, status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_boss_attacks_boss ON boss_attacks(boss_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_boss_attacks_user ON boss_attacks(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_confirmed_chats_chat ON confirmed_chats(chat_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_requests_status ON chat_confirmation_requests(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_auctions_status ON auctions(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_auctions_end_time ON auctions(end_time)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_auction_bids_auction ON auction_bids(auction_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_authority_chat ON chat_authority(chat_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_global_cooldowns_user ON global_cooldowns(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_fight_logs_timestamp ON fight_logs(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ads_enabled ON ads(enabled)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_giveaway ON participants(giveaway_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_authority_offers_status ON authority_offers(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_authority_offers_seller ON authority_offers(seller_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_smuggle_runs_user ON smuggle_runs(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_smuggle_runs_end ON smuggle_runs(end_time)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_businesses_user ON user_businesses(user_id)")
        # Индекс для поиска по username без учёта регистра
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username_lower ON users(LOWER(username))")

    # Заполняем настройки значениями по умолчанию
    await init_settings()
    # Заполняем level_rewards для уровней 1-100
    async with db_pool.acquire() as conn:
        for lvl in range(1, 101):
            exists = await conn.fetchval("SELECT level FROM level_rewards WHERE level=$1", lvl)
            if not exists:
                coins = int(DEFAULT_SETTINGS["level_reward_coins"]) + (lvl-1) * int(DEFAULT_SETTINGS["level_reward_coins_increment"])
                rep = int(DEFAULT_SETTINGS["level_reward_reputation"]) + (lvl-1) * int(DEFAULT_SETTINGS["level_reward_reputation_increment"])
                await conn.execute(
                    "INSERT INTO level_rewards (level, coins, reputation) VALUES ($1, $2, $3)",
                    lvl, coins, rep
                )
    logging.info("✅ Таблицы в PostgreSQL проверены/обновлены")

async def init_settings():
    """Заполняет таблицу settings значениями по умолчанию, если их нет."""
    async with db_pool.acquire() as conn:
        for key, value in DEFAULT_SETTINGS.items():
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                key, value
            )

# ==================== БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ ====================
async def safe_send_message(user_id: int, text: str, **kwargs):
    """Отправляет сообщение пользователю, обрабатывая возможные ошибки."""
    if kwargs.get('parse_mode') == 'HTML':
        # Экранируем HTML-сущности, чтобы избежать ошибок
        text = html.escape(text).replace('&#x27;', "'")
    try:
        await bot.send_message(user_id, text, **kwargs)
    except BotBlocked:
        logging.warning(f"Bot blocked by user {user_id}")
    except UserDeactivated:
        logging.warning(f"User {user_id} deactivated")
    except ChatNotFound:
        logging.warning(f"Chat {user_id} not found")
    except RetryAfter as e:
        logging.warning(f"Flood limit exceeded. Retry after {e.timeout} seconds")
        await asyncio.sleep(e.timeout)
        try:
            await bot.send_message(user_id, text, **kwargs)
        except Exception as ex:
            logging.warning(f"Still failed after retry: {ex}")
    except TelegramAPIError as e:
        logging.warning(f"Telegram API error for user {user_id}: {e}")
    except Exception as e:
        logging.warning(f"Failed to send message to {user_id}: {e}")

def safe_send_message_task(user_id: int, text: str, **kwargs):
    """Запускает safe_send_message как фоновую задачу."""
    asyncio.create_task(safe_send_message(user_id, text, **kwargs))

async def safe_send_chat(chat_id: int, text: str, **kwargs):
    """Отправляет сообщение в чат, обрабатывая ошибки."""
    if kwargs.get('parse_mode') == 'HTML':
        text = html.escape(text).replace('&#x27;', "'")
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send to chat {chat_id}: {e}")

# ==================== АВТОУДАЛЕНИЕ СООБЩЕНИЙ ====================
async def can_delete_message(chat_id: int, message: types.Message) -> bool:
    """Проверяет, может ли бот удалить это сообщение."""
    try:
        if chat_id > 0:
            return message.from_user.id == bot.id
        else:
            member = await bot.get_chat_member(chat_id, bot.id)
            return member.status in ['administrator', 'creator']
    except:
        return False

async def delete_after(message: types.Message, seconds: int):
    """Удаляет сообщение через заданное количество секунд."""
    await asyncio.sleep(seconds)
    if await can_delete_message(message.chat.id, message):
        try:
            await message.delete()
        except Exception:
            pass

async def auto_delete_reply(message: types.Message, text: str, delete_seconds: int = None, **kwargs):
    """Отвечает на сообщение и автоматически удаляет ответ через заданное время."""
    if delete_seconds is None:
        delete_seconds = int(await get_setting("auto_delete_commands_seconds"))
    sent = await message.reply(text, **kwargs)
    if message.chat.type != 'private':
        confirmed = await get_confirmed_chats()
        chat_data = confirmed.get(message.chat.id)
        if chat_data and not chat_data.get('auto_delete_enabled', True):
            return
    asyncio.create_task(delete_after(sent, delete_seconds))

async def auto_delete_message(message: types.Message, delete_seconds: int = None):
    """Автоматически удаляет исходное сообщение (если оно в группе)."""
    if message.chat.type == 'private':
        return
    if delete_seconds is None:
        delete_seconds = int(await get_setting("auto_delete_commands_seconds"))
    confirmed = await get_confirmed_chats()
    chat_data = confirmed.get(message.chat.id)
    if chat_data and not chat_data.get('auto_delete_enabled', True):
        return
    asyncio.create_task(delete_after(message, delete_seconds))

# ==================== РАБОТА С НАСТРОЙКАМИ (КЭШИРОВАНИЕ) ====================
async def get_setting(key: str) -> str:
    """Возвращает значение настройки по ключу (с кэшированием на 60 секунд)."""
    global settings_cache, last_settings_update
    now = time.time()
    if now - last_settings_update > 60 or not settings_cache:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM settings")
            settings_cache = {row['key']: row['value'] for row in rows}
        last_settings_update = now
    return settings_cache.get(key, DEFAULT_SETTINGS[key])

async def set_setting(key: str, value: str):
    """Устанавливает значение настройки и обновляет кэш."""
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE settings SET value=$1 WHERE key=$2", value, key)
    settings_cache[key] = value

# ==================== РАБОТА С КАНАЛАМИ И ЧАТАМИ (КЭШ) ====================
async def get_channels():
    """Возвращает список каналов для подписки (кэш на 5 минут)."""
    global channels_cache, last_channels_update
    now = time.time()
    if now - last_channels_update > 300 or not channels_cache:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id, title, invite_link FROM channels")
            channels_cache = [(r['chat_id'], r['title'], r['invite_link']) for r in rows]
        last_channels_update = now
    return channels_cache

async def get_confirmed_chats(force_update=False) -> Dict[int, dict]:
    """Возвращает словарь подтверждённых чатов (кэш на 5 минут)."""
    global confirmed_chats_cache, last_confirmed_chats_update
    now = time.time()
    if force_update or now - last_confirmed_chats_update > 300 or not confirmed_chats_cache:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM confirmed_chats")
            confirmed_chats_cache = {row['chat_id']: dict(row) for row in rows}
        last_confirmed_chats_update = now
    return confirmed_chats_cache

async def is_chat_confirmed(chat_id: int) -> bool:
    """Проверяет, подтверждён ли чат."""
    confirmed = await get_confirmed_chats()
    return chat_id in confirmed

async def add_confirmed_chat(chat_id: int, title: str, chat_type: str, confirmed_by: int):
    """Добавляет чат в список подтверждённых."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO confirmed_chats (chat_id, title, type, joined_date, confirmed_by, confirmed_date) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (chat_id) DO UPDATE SET confirmed_by=$5, confirmed_date=$6",
            chat_id, title, chat_type, datetime.now(), confirmed_by, datetime.now()
        )
    await get_confirmed_chats(force_update=True)

async def remove_confirmed_chat(chat_id: int):
    """Удаляет чат из списка подтверждённых."""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM confirmed_chats WHERE chat_id=$1", chat_id)
    await get_confirmed_chats(force_update=True)

async def create_chat_confirmation_request(chat_id: int, title: str, chat_type: str, requested_by: int):
    """Создаёт запрос на подтверждение чата."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_confirmation_requests (chat_id, title, type, requested_by, request_date, status) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (chat_id) DO UPDATE SET status='pending', requested_by=$4, request_date=$5",
            chat_id, title, chat_type, requested_by, datetime.now(), 'pending'
        )

async def get_pending_chat_requests() -> List[dict]:
    """Возвращает список ожидающих запросов на подтверждение."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM chat_confirmation_requests WHERE status='pending' ORDER BY request_date")
        return [dict(r) for r in rows]

async def update_chat_request_status(chat_id: int, status: str):
    """Обновляет статус запроса на подтверждение чата."""
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE chat_confirmation_requests SET status=$1 WHERE chat_id=$2", status, chat_id)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def is_super_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь суперадмином."""
    return user_id in SUPER_ADMINS

async def is_junior_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь младшим админом."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchval("SELECT user_id FROM admins WHERE user_id=$1", user_id)
    return row is not None

async def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом (супер или младшим)."""
    return await is_super_admin(user_id) or await is_junior_admin(user_id)

async def has_permission(user_id: int, permission: str) -> bool:
    """Проверяет, есть ли у пользователя конкретное право."""
    if await is_super_admin(user_id):
        return True
    async with db_pool.acquire() as conn:
        perms_json = await conn.fetchval("SELECT permissions FROM admins WHERE user_id=$1", user_id)
    if not perms_json:
        return False
    try:
        perms = json.loads(perms_json)
        return permission in perms
    except:
        return False

async def get_admin_permissions(user_id: int) -> List[str]:
    """Возвращает список прав пользователя."""
    if await is_super_admin(user_id):
        return PERMISSIONS_LIST.copy()
    async with db_pool.acquire() as conn:
        perms_json = await conn.fetchval("SELECT permissions FROM admins WHERE user_id=$1", user_id)
    if not perms_json:
        return []
    try:
        return json.loads(perms_json)
    except:
        return []

async def update_admin_permissions(user_id: int, permissions: List[str]):
    """Обновляет права администратора."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE admins SET permissions=$1 WHERE user_id=$2",
            json.dumps(permissions), user_id
        )

async def is_banned(user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchval("SELECT user_id FROM banned_users WHERE user_id=$1", user_id)
    return row is not None

async def check_subscription(user_id: int):
    """Проверяет подписку пользователя на обязательные каналы."""
    channels = await get_channels()
    if not channels:
        return True, []
    not_subscribed = []
    for chat_id, title, link in channels:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append((title, link))
        except Exception:
            not_subscribed.append((title, link))
    return len(not_subscribed) == 0, not_subscribed

def progress_bar(current, total, length=15):
    """Генерирует символьную полоску прогресса."""
    if total <= 0:
        return "░" * length
    filled = int(current / total * length)
    return "█" * filled + "░" * (length - filled)

def format_time_remaining(seconds: int) -> str:
    """Форматирует оставшееся время в минутах/часах."""
    if seconds < 60:
        return "меньше минуты"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    minutes %= 60
    if minutes == 0:
        return f"{hours} ч"
    return f"{hours} ч {minutes} мин"

def get_random_phrase(phrase_list: List[str], **kwargs) -> str:
    """Выбирает случайную фразу и подставляет аргументы."""
    phrase = random.choice(phrase_list)
    return phrase.format(**kwargs)

async def notify_chats(message_text: str, importance: str = 'info'):
    """Отправляет уведомление во все подтверждённые чаты (с включёнными уведомлениями)."""
    confirmed = await get_confirmed_chats()
    for chat_id, data in confirmed.items():
        if not data.get('notify_enabled', True):
            continue
        await safe_send_chat(chat_id, message_text)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ПОИСКА ПОЛЬЗОВАТЕЛЯ ====================
async def find_user_by_input(input_str: str) -> Optional[Dict]:
    """Ищет пользователя по ID или username (с @ или без). Возвращает словарь с данными или None."""
    input_str = input_str.strip()
    try:
        uid = int(input_str)
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)
            return dict(row) if row else None
    except ValueError:
        username = input_str.lower()
        if username.startswith('@'):
            username = username[1:]
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE LOWER(username)=$1", username)
            return dict(row) if row else None

# ==================== ФУНКЦИИ ЭКСПОРТА ====================
async def export_users_to_csv() -> bytes:
    """Экспортирует всех пользователей в CSV."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users ORDER BY user_id")
    if not rows:
        return b""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(dict(rows[0]).keys())
    for row in rows:
        writer.writerow(dict(row).values())
    return output.getvalue().encode('utf-8')

ALLOWED_TABLES = ['users', 'purchases', 'bosses', 'auctions', 'giveaways', 'tasks', 'chat_authority', 'fight_logs']
async def export_table_to_csv(table: str) -> Optional[bytes]:
    """Экспортирует указанную таблицу в CSV (если разрешена)."""
    if table not in ALLOWED_TABLES:
        return None
    async with db_pool.acquire() as conn:
        try:
            rows = await conn.fetch(f"SELECT * FROM {table} ORDER BY id")
        except Exception:
            return None
        if not rows:
            return None
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(dict(rows[0]).keys())
        for row in rows:
            writer.writerow(dict(row).values())
        return output.getvalue().encode('utf-8')

# ==================== ИНИЦИАЛИЗАЦИЯ БИЗНЕС-ТИПОВ ====================
async def init_business_types():
    """Заполняет таблицу business_types начальными данными, если она пуста."""
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM business_types")
        if count == 0:
            businesses = [
                ("Уличная забегаловка", "Маленькое кафе на районе, приносит стабильный, но скромный доход.", 5000, 10, 240, 0),
                ("Нелегальная мастерская", "Подпольная мастерская по переделке техники. Риск выше, но и доход больше.", 15000, 30, 720, 50),
                ("Контрабандный склад", "Склад для хранения товара. Позволяет накапливать больше дохода.", 30000, 50, 1200, 150),
                ("Фрахтовый корабль", "Небольшое судно для перевозок. Хороший пассивный доход.", 50000, 80, 1920, 300),
                ("Подпольное казино", "Нелегальное игорное заведение. Очень прибыльно, но требует авторитета.", 100000, 150, 3600, 500),
            ]
            for name, desc, cost, income, storage, req_auth in businesses:
                await conn.execute(
                    "INSERT INTO business_types (name, description, cost_smuggle, income_per_hour, max_storage, required_authority) VALUES ($1, $2, $3, $4, $5, $6)",
                    name, desc, cost, income, storage, req_auth
                )
            logging.info("✅ Таблица business_types инициализирована")
        else:
            logging.info("✅ Таблица business_types уже содержит данные")
# ==================== ЧАСТЬ 2: НЕДОСТАЮЩИЕ ФУНКЦИИ (РАБОТА С ПОЛЬЗОВАТЕЛЯМИ, АВТОРИТЕТОМ, БОССАМИ, ИГРАМИ) ====================

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ====================

async def get_user_balance(user_id: int) -> int:
    """Возвращает баланс пользователя."""
    async with db_pool.acquire() as conn:
        balance = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1", user_id)
        return balance if balance is not None else 0

async def update_user_balance(user_id: int, delta: int, conn=None):
    """Обновляет баланс пользователя (положительное или отрицательное изменение)."""
    async def _update(conn):
        row = await conn.fetchrow("SELECT balance, negative_balance FROM users WHERE user_id=$1", user_id)
        if not row:
            await conn.execute(
                "INSERT INTO users (user_id, balance, negative_balance) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                user_id, 0, 0
            )
            row = {'balance': 0, 'negative_balance': 0}
        balance, negative = row['balance'], row['negative_balance']
        new_balance = balance + delta
        if new_balance < 0:
            negative += abs(new_balance)
            new_balance = 0
        await conn.execute(
            "UPDATE users SET balance=$1, negative_balance=$2 WHERE user_id=$3",
            new_balance, negative, user_id
        )
    if conn:
        await _update(conn)
    else:
        async with db_pool.acquire() as new_conn:
            await _update(new_conn)

async def get_user_reputation(user_id: int) -> int:
    async with db_pool.acquire() as conn:
        rep = await conn.fetchval("SELECT reputation FROM users WHERE user_id=$1", user_id)
        return rep if rep is not None else 0

async def update_user_reputation(user_id: int, delta: int):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET reputation = reputation + $1 WHERE user_id=$2", delta, user_id)

async def get_user_global_authority(user_id: int) -> int:
    async with db_pool.acquire() as conn:
        auth = await conn.fetchval("SELECT global_authority FROM users WHERE user_id=$1", user_id)
        return auth if auth is not None else 0

async def update_user_global_authority(user_id: int, delta: int, conn=None):
    async def _update(conn):
        await conn.execute("UPDATE users SET global_authority = global_authority + $1 WHERE user_id=$2", delta, user_id)
    if conn:
        await _update(conn)
    else:
        async with db_pool.acquire() as new_conn:
            await _update(new_conn)

async def get_user_stats(user_id: int) -> dict:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT level, strength, agility, defense FROM users WHERE user_id=$1", user_id)
        if row:
            return dict(row)
        return {'level': 1, 'strength': 1, 'agility': 1, 'defense': 1}

async def update_user_stats(user_id: int, strength_delta=0, agility_delta=0, defense_delta=0):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET strength = strength + $1, agility = agility + $2, defense = defense + $3 WHERE user_id=$4",
            strength_delta, agility_delta, defense_delta, user_id
        )

async def update_user_game_stats(user_id: int, game: str, win: bool, conn=None):
    async def _update(conn):
        if win:
            if game == 'casino':
                await conn.execute("UPDATE users SET casino_wins = casino_wins + 1 WHERE user_id=$1", user_id)
            elif game == 'dice':
                await conn.execute("UPDATE users SET dice_wins = dice_wins + 1 WHERE user_id=$1", user_id)
            elif game == 'guess':
                await conn.execute("UPDATE users SET guess_wins = guess_wins + 1 WHERE user_id=$1", user_id)
            elif game == 'slots':
                await conn.execute("UPDATE users SET slots_wins = slots_wins + 1 WHERE user_id=$1", user_id)
            elif game == 'roulette':
                await conn.execute("UPDATE users SET roulette_wins = roulette_wins + 1 WHERE user_id=$1", user_id)
            elif game == 'multiplayer':
                await conn.execute("UPDATE users SET multiplayer_wins = multiplayer_wins + 1 WHERE user_id=$1", user_id)
        else:
            if game == 'casino':
                await conn.execute("UPDATE users SET casino_losses = casino_losses + 1 WHERE user_id=$1", user_id)
            elif game == 'dice':
                await conn.execute("UPDATE users SET dice_losses = dice_losses + 1 WHERE user_id=$1", user_id)
            elif game == 'guess':
                await conn.execute("UPDATE users SET guess_losses = guess_losses + 1 WHERE user_id=$1", user_id)
            elif game == 'slots':
                await conn.execute("UPDATE users SET slots_losses = slots_losses + 1 WHERE user_id=$1", user_id)
            elif game == 'roulette':
                await conn.execute("UPDATE users SET roulette_losses = roulette_losses + 1 WHERE user_id=$1", user_id)
            elif game == 'multiplayer':
                await conn.execute("UPDATE users SET multiplayer_losses = multiplayer_losses + 1 WHERE user_id=$1", user_id)
    if conn:
        await _update(conn)
    else:
        async with db_pool.acquire() as new_conn:
            await _update(new_conn)

async def add_exp(user_id: int, exp: int, conn=None):
    async def _add(conn):
        user = await conn.fetchrow("SELECT exp, level FROM users WHERE user_id=$1", user_id)
        if not user:
            return
        new_exp = user['exp'] + exp
        level = user['level']
        level_mult = int(await get_setting("level_multiplier"))
        levels_gained = 0
        while new_exp >= level * level_mult:
            new_exp -= level * level_mult
            level += 1
            levels_gained += 1
        await conn.execute(
            "UPDATE users SET exp=$1, level=$2 WHERE user_id=$3",
            new_exp, level, user_id
        )
        if levels_gained > 0:
            str_inc = int(await get_setting("stat_strength_per_level")) * levels_gained
            agi_inc = int(await get_setting("stat_agility_per_level")) * levels_gained
            def_inc = int(await get_setting("stat_defense_per_level")) * levels_gained
            await update_user_stats(user_id, str_inc, agi_inc, def_inc)
            for lvl in range(level - levels_gained + 1, level + 1):
                await reward_level_up(user_id, lvl, conn)
    if conn:
        await _add(conn)
    else:
        async with db_pool.acquire() as conn2:
            await _add(conn2)

async def reward_level_up(user_id: int, new_level: int, conn=None):
    async def _reward(conn):
        reward = await conn.fetchrow(
            "SELECT coins, reputation FROM level_rewards WHERE level=$1",
            new_level
        )
        if reward:
            await update_user_balance(user_id, reward['coins'], conn=conn)
            await update_user_reputation(user_id, reward['reputation'])
            await safe_send_message(
                user_id,
                f"🎉 Поздравляем! Ты достиг {new_level} уровня!\n"
                f"Награда: +{reward['coins']} баксов, +{reward['reputation']} репутации!\n"
                f"Твои статы увеличены: сила +{int(await get_setting('stat_strength_per_level'))}, ловкость +{int(await get_setting('stat_agility_per_level'))}, защита +{int(await get_setting('stat_defense_per_level'))}."
            )
    if conn:
        await _reward(conn)
    else:
        async with db_pool.acquire() as conn2:
            await _reward(conn2)

async def get_user_level(user_id: int) -> int:
    async with db_pool.acquire() as conn:
        level = await conn.fetchval("SELECT level FROM users WHERE user_id=$1", user_id)
        return level if level is not None else 1

async def get_user_exp(user_id: int) -> int:
    async with db_pool.acquire() as conn:
        exp = await conn.fetchval("SELECT exp FROM users WHERE user_id=$1", user_id)
        return exp if exp is not None else 0

async def update_user_total_spent(user_id: int, amount: int):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET total_spent = total_spent + $1 WHERE user_id=$2", amount, user_id)

async def get_random_user(exclude_id: int):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT user_id FROM users 
            WHERE user_id != $1 AND user_id NOT IN (SELECT user_id FROM banned_users)
            ORDER BY RANDOM() LIMIT 1
        """, exclude_id)
        return row['user_id'] if row else None

# ==================== ФУНКЦИИ ДЛЯ АВТОРИТЕТА В ЧАТАХ ====================

async def get_chat_authority(chat_id: int, user_id: int) -> int:
    async with db_pool.acquire() as conn:
        val = await conn.fetchval("SELECT authority FROM chat_authority WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)
        return val if val is not None else 0

async def add_chat_authority(chat_id: int, user_id: int, amount: int, damage: int = 0):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO chat_authority (chat_id, user_id, authority, total_damage, fights)
            VALUES ($1, $2, $3, $4, 1)
            ON CONFLICT (chat_id, user_id) DO UPDATE
            SET authority = chat_authority.authority + $3,
                total_damage = chat_authority.total_damage + $4,
                fights = chat_authority.fights + 1
        ''', chat_id, user_id, amount, damage)

async def get_total_user_authority(user_id: int) -> int:
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT SUM(authority) FROM chat_authority WHERE user_id=$1", user_id)
        return total or 0

async def get_total_user_fights(user_id: int) -> Tuple[int, int]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT SUM(fights) as total_fights, SUM(total_damage) as total_damage FROM chat_authority WHERE user_id=$1",
            user_id
        )
        return (row['total_fights'] or 0, row['total_damage'] or 0)

async def spend_chat_authority(chat_id: int, user_id: int, amount: int) -> bool:
    current = await get_chat_authority(chat_id, user_id)
    if current < amount:
        return False
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE chat_authority SET authority = authority - $1 WHERE chat_id=$2 AND user_id=$3", amount, chat_id, user_id)
    return True

async def log_fight(chat_id: int, user_id: int, damage: int, authority: int, outcome: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO fight_logs (chat_id, user_id, timestamp, damage, authority_gained, outcome) VALUES ($1, $2, $3, $4, $5, $6)",
            chat_id, user_id, datetime.now(), damage, authority, outcome
        )

# ==================== ФУНКЦИИ ДЛЯ ГЛОБАЛЬНЫХ КУЛДАУНОВ ====================

async def check_global_cooldown(user_id: int, command: str, cooldown_minutes: int) -> Tuple[bool, int]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_used FROM global_cooldowns WHERE user_id=$1 AND command=$2", user_id, command)
        if row and row['last_used']:
            diff = datetime.now() - row['last_used']
            remaining = cooldown_minutes * 60 - diff.total_seconds()
            if remaining > 0:
                return False, int(remaining)
    return True, 0

async def set_global_cooldown(user_id: int, command: str):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO global_cooldowns (user_id, command, last_used)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, command) DO UPDATE SET last_used = $3
        ''', user_id, command, datetime.now())

# ==================== ФУНКЦИИ ДЛЯ БОССОВ ====================

BOSS_NAMES = [
    "Дон Корлеоне", "Крёстный отец", "Аль Капоне", "Люциано", "Гамбино",
    "Джон Готти", "Фрэнк Костелло", "Мейер Лански", "Багси Сигел",
    "Сальваторе Теста", "Карло Гамбино", "Пол Кастеллано", "Винсент Джиганте"
]

BOSS_DESCRIPTIONS = [
    "Глава мафиозного клана, держит в страхе весь район.",
    "Безжалостный гангстер, правая рука дона.",
    "Известный рэкетир, контролирует подпольный бизнес.",
    "Старый вор в законе, уважаемый в криминальном мире.",
    "Молодой и амбициозный лидер банды.",
    "Торговец оружием, всегда при деньгах.",
    "Налётчик со стажем, его боятся даже полицейские.",
    "Киллер, на счету которого десятки жертв.",
    "Хозяин подпольных казино и притонов.",
    "Смотрящий за городом, решает все вопросы."
]

BOSS_ANGRY_PHRASES = [
    "Ты думал, что в нашем районе можно просто так ходить? Получи {damage} урона!",
    "Я закопаю тебя в пустыне! Держи {damage}!",
    "Ты подписал себе смертный приговор! Атака {damage}!",
    "Мои парни сейчас разберутся с тобой! {damage} урона!",
    "Ты пожалеешь, что связался с мафией! Получай {damage}!",
    "Это тебе за моих пацанов! {damage} в ответ!",
    "Ты кто такой, чтобы против меня идти? Держи {damage}!",
    "Я сотру тебя в порошок! Урон {damage}!",
    "Ты даже не представляешь, на кого напал! Вот тебе {damage}!",
]

BOSS_HAPPY_PHRASES = [
    "Ха, слабак! Мой авторитет не пошатнуть! Осталось {hp_remaining} HP.",
    "Ты всего лишь муравей. У меня ещё {hp_remaining} здоровья!",
    "Мои люди скоро придут на помощь! HP: {hp_remaining}",
    "Я видал и не такое. HP осталось: {hp_remaining}",
    "Плохой удар. У меня ещё {hp_remaining}!",
    "Ты даже не поцарапал меня. HP: {hp_remaining}",
    "Это всё, на что ты способен? Атакуй ещё! (HP: {hp_remaining})",
    "Моя броня крепка. HP осталось: {hp_remaining}",
]

BOSS_DEATH_PHRASES = [
    "Я ещё вернусь... Семья отомстит за меня!",
    "Вы победили... но это не конец...",
    "Коза ностра... бессмертна...",
    "Мои парни разберутся с вами...",
    "Это ещё не конец, я ещё вернусь!",
    "Вы пожалеете об этом дне!",
    "Семья не простит вам этого!",
]

async def spawn_boss(chat_id: int, level: int = None, image_file_id: str = None):
    if level is None:
        level = random.randint(1, 5)
    name = random.choice(BOSS_NAMES)
    description = random.choice(BOSS_DESCRIPTIONS)
    hp_mult = int(await get_setting("boss_hp_multiplier"))
    hp = level * hp_mult * random.randint(5, 10)
    base_reward = int(await get_setting("boss_reward_coins"))
    variance = int(await get_setting("boss_reward_coins_variance"))
    reward = base_reward + random.randint(-variance, variance)
    now = datetime.now()
    expires_at = now + timedelta(hours=2)
    async with db_pool.acquire() as conn:
        boss_id = await conn.fetchval(
            "INSERT INTO bosses (chat_id, name, level, hp, max_hp, spawned_at, expires_at, reward_coins, participants, status, image_file_id, description) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) RETURNING id",
            chat_id, name, level, hp, hp, now, expires_at, reward, [], 'active', image_file_id, description
        )
        await conn.execute(
            "UPDATE confirmed_chats SET boss_last_spawn=$1, boss_spawn_count = boss_spawn_count + 1 WHERE chat_id=$2",
            now, chat_id
        )
    caption = f"⚠️ ВНИМАНИЕ! В чате появился {name} (Уровень {level})!\n📖 {description}\n❤️ Здоровье: {hp}"
    if image_file_id:
        await bot.send_photo(chat_id, image_file_id, caption=caption)
    else:
        await safe_send_chat(chat_id, caption)

async def finish_boss_fight(boss_id: int):
    async with db_pool.acquire() as conn:
        boss = await conn.fetchrow("SELECT * FROM bosses WHERE id=$1", boss_id)
        if not boss or boss['status'] != 'active':
            return
        participants = boss['participants'] or []
        if not participants:
            await conn.execute("UPDATE bosses SET status='defeated' WHERE id=$1", boss_id)
            return
        reward_total = boss['reward_coins']
        reward_per_player = reward_total // len(participants)
        remainder = reward_total % len(participants)
        for i, uid in enumerate(participants):
            reward = reward_per_player + (1 if i < remainder else 0)
            await update_user_balance(uid, reward, conn=conn)
            exp = int(await get_setting("exp_per_game_win"))
            await add_exp(uid, exp, conn=conn)
        await conn.execute("UPDATE bosses SET status='defeated' WHERE id=$1", boss_id)
        phrase = random.choice(BOSS_DEATH_PHRASES)
        await safe_send_chat(boss['chat_id'], f"{phrase}\nУчастники получили по {reward_per_player} баксов!")

# ==================== ФУНКЦИИ ДЛЯ РАСЧЁТА УРОНА ====================

async def calculate_fight_damage(strength: int) -> int:
    base = int(await get_setting("fight_base_damage"))
    variance = int(await get_setting("fight_damage_variance"))
    damage = base + strength // 2 + random.randint(-variance, variance)
    return max(1, damage)

async def calculate_fight_authority() -> int:
    min_auth = int(await get_setting("fight_authority_min"))
    max_auth = int(await get_setting("fight_authority_max"))
    return random.randint(min_auth, max_auth)

def is_critical(strength: int, agility: int) -> bool:
    chance = 5 + agility * 2
    if chance > 50:
        chance = 50
    return random.randint(1, 100) <= chance

def is_counter(defense: int) -> bool:
    chance = 5 + defense * 1
    if chance > 40:
        chance = 40
    return random.randint(1, 100) <= chance

# ==================== ФУНКЦИИ ДЛЯ ИГР (СЛОТЫ, РУЛЕТКА) ====================

async def slots_spin() -> Tuple[str, int, bool]:
    symbols = ['🍒', '🍋', '🍊', '7️⃣', '💎']
    result = [random.choice(symbols) for _ in range(3)]
    combo = ''.join(result)
    if result[0] == result[1] == result[2]:
        if result[0] == '7️⃣':
            multiplier = int(await get_setting("slots_multiplier_seven"))
        elif result[0] == '💎':
            multiplier = int(await get_setting("slots_multiplier_diamond"))
        else:
            multiplier = int(await get_setting("slots_multiplier_three"))
        return combo, multiplier, True
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        return combo, 2, True
    else:
        return combo, 0, False

async def roulette_spin(bet_type: str, bet_number: int = None) -> Tuple[int, str, bool]:
    number = random.randint(0, 36)
    color = 'green' if number == 0 else ('red' if number % 2 == 0 else 'black')
    if bet_type == 'number':
        if bet_number == number:
            return number, color, True
        else:
            return number, color, False
    elif bet_type == 'red':
        if color == 'red':
            return number, color, True
        else:
            return number, color, False
    elif bet_type == 'black':
        if color == 'black':
            return number, color, True
        else:
            return number, color, False
    elif bet_type == 'green':
        if color == 'green':
            return number, color, True
        else:
            return number, color, False
    else:
        return number, color, False

# ==================== ФУНКЦИИ ДЛЯ БИЗНЕСА ====================

async def update_business_income(user_id: int, conn=None):
    async def _update(conn):
        now = datetime.now()
        businesses = await conn.fetch(
            "SELECT ub.*, bt.income_per_hour, bt.max_storage FROM user_businesses ub "
            "JOIN business_types bt ON ub.business_type_id = bt.id WHERE ub.user_id=$1",
            user_id
        )
        for biz in businesses:
            if biz['last_collection']:
                hours_passed = int((now - biz['last_collection']).total_seconds() // 3600)
                if hours_passed > 0:
                    new_accum = biz['accumulated'] + hours_passed * biz['income_per_hour']
                    if new_accum > biz['max_storage']:
                        new_accum = biz['max_storage']
                    await conn.execute(
                        "UPDATE user_businesses SET accumulated=$1, last_collection=$2 WHERE id=$3",
                        new_accum, now, biz['id']
                    )
    if conn:
        await _update(conn)
    else:
        async with db_pool.acquire() as new_conn:
            await _update(new_conn)

# ==================== ФУНКЦИИ ДЛЯ АУКЦИОНА ====================

async def get_active_auctions(page: int = 1):
    offset = (page - 1) * ITEMS_PER_PAGE
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM auctions WHERE status='active'")
        auctions = await conn.fetch(
            "SELECT * FROM auctions WHERE status='active' ORDER BY end_time NULLS LAST LIMIT $1 OFFSET $2",
            ITEMS_PER_PAGE, offset
        )
        return total, [dict(a) for a in auctions]

async def place_bid(auction_id: int, user_id: int, amount: int) -> Tuple[bool, str]:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            auction = await conn.fetchrow("SELECT * FROM auctions WHERE id=$1 AND status='active' FOR UPDATE", auction_id)
            if not auction:
                return False, "Аукцион не активен или не существует"
            if amount <= auction['current_price']:
                return False, f"Ставка должна быть больше текущей цены ({auction['current_price']})"
            min_step = int(await get_setting("auction_min_bid_step"))
            if amount - auction['current_price'] < min_step:
                return False, f"Минимальный шаг ставки: {min_step}"
            user_balance = await get_user_balance(user_id)
            if user_balance < amount:
                return False, "Недостаточно средств"
            await update_user_balance(user_id, -amount, conn=conn)
            await conn.execute(
                "INSERT INTO auction_bids (auction_id, user_id, bid_amount) VALUES ($1, $2, $3)",
                auction_id, user_id, amount
            )
            await conn.execute(
                "UPDATE auctions SET current_price=$1 WHERE id=$2",
                amount, auction_id
            )
            if auction['target_price'] and amount >= auction['target_price']:
                await conn.execute("UPDATE auctions SET status='ended', winner_id=$1 WHERE id=$2", user_id, auction_id)
                return True, "Поздравляем! Вы достигли целевой цены и выиграли аукцион!"
            return True, "Ставка принята!"

# ==================== ФУНКЦИИ ДЛЯ ПРОДАЖИ АВТОРИТЕТА ====================

async def create_authority_offer(seller_id: int, amount: int, price_per_unit: int) -> int:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            auth = await get_user_global_authority(seller_id)
            if auth < amount:
                return 0
            await update_user_global_authority(seller_id, -amount, conn=conn)
            offer_id = await conn.fetchval(
                "INSERT INTO authority_offers (seller_id, amount, price_per_unit) VALUES ($1, $2, $3) RETURNING id",
                seller_id, amount, price_per_unit
            )
            return offer_id

async def buy_authority(buyer_id: int, offer_id: int) -> Tuple[bool, str]:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            offer = await conn.fetchrow("SELECT * FROM authority_offers WHERE id=$1 AND status='active' FOR UPDATE", offer_id)
            if not offer:
                return False, "Предложение не найдено или уже неактивно"
            total_price = offer['amount'] * offer['price_per_unit']
            buyer_balance = await get_user_balance(buyer_id)
            if buyer_balance < total_price:
                return False, "Недостаточно средств"
            await update_user_balance(buyer_id, -total_price, conn=conn)
            await update_user_balance(offer['seller_id'], total_price, conn=conn)
            await update_user_global_authority(buyer_id, offer['amount'], conn=conn)
            await conn.execute(
                "UPDATE authority_offers SET status='sold', buyer_id=$1, bought_at=$2 WHERE id=$3",
                buyer_id, datetime.now(), offer_id
            )
            return True, "Покупка успешна!"

# ==================== ФУНКЦИИ ДЛЯ КОНТРАБАНДЫ ====================

async def get_smuggle_cooldown(user_id: int) -> Tuple[bool, int]:
    cooldown = int(await get_setting("smuggle_cooldown_minutes"))
    return await check_global_cooldown(user_id, "smuggle", cooldown)

async def set_smuggle_cooldown(user_id: int, penalty: int = 0):
    cooldown = int(await get_setting("smuggle_cooldown_minutes")) + penalty
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO global_cooldowns (user_id, command, last_used)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, command) DO UPDATE SET last_used = $3
        ''', user_id, "smuggle", datetime.now())

# ==================== ФУНКЦИИ ДЛЯ МУЛЬТИПЛЕЕРА ====================

def generate_game_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def calculate_hand_value(cards):
    value = 0
    aces = 0
    for card in cards:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            aces += 1
            value += 11
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

def create_deck():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f"{rank}{suit}" for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

# ==================== ФУНКЦИИ ДЛЯ ОЧИСТКИ ====================

async def perform_cleanup(manual=False):
    """Удаляет старые записи согласно настройкам."""
    days_bosses = int(await get_setting("cleanup_days_bosses"))
    days_auctions = int(await get_setting("cleanup_days_auctions"))
    days_purchases = int(await get_setting("cleanup_days_purchases"))
    days_giveaways = int(await get_setting("cleanup_days_giveaways"))
    days_tasks = int(await get_setting("cleanup_days_user_tasks"))
    days_fight = int(await get_setting("cleanup_days_fight_logs"))
    days_smuggle = int(await get_setting("cleanup_days_smuggle"))

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM bosses WHERE status IN ('defeated', 'expired') AND spawned_at < NOW() - INTERVAL '1 day' * $1", days_bosses)
        await conn.execute("DELETE FROM boss_attacks WHERE attack_time < NOW() - INTERVAL '1 day' * $1", days_bosses)
        await conn.execute("DELETE FROM auctions WHERE status='ended' AND end_time < NOW() - INTERVAL '1 day' * $1", days_auctions)
        await conn.execute("DELETE FROM purchases WHERE status IN ('completed','rejected') AND purchase_date < NOW() - INTERVAL '1 day' * $1", days_purchases)
        await conn.execute("DELETE FROM giveaways WHERE status='completed' AND end_date < NOW() - INTERVAL '1 day' * $1", days_giveaways)
        await conn.execute("DELETE FROM user_tasks WHERE expires_at IS NOT NULL AND expires_at < NOW()")
        await conn.execute("DELETE FROM fight_logs WHERE timestamp < NOW() - INTERVAL '1 day' * $1", days_fight)
        cooldown = int(await get_setting("fight_cooldown_minutes"))
        await conn.execute("DELETE FROM global_cooldowns WHERE last_used < NOW() - INTERVAL '1 minute' * $1", cooldown * 2)
        await conn.execute("DELETE FROM authority_offers WHERE status IN ('sold', 'cancelled')")
        await conn.execute("DELETE FROM authority_offers WHERE status='active' AND created_at < NOW() - INTERVAL '30 days'")
        await conn.execute("DELETE FROM smuggle_runs WHERE status IN ('completed', 'failed') AND end_time < NOW() - INTERVAL '1 day' * $1", days_smuggle)

    if manual:
        logging.info("Ручная очистка выполнена.")
    else:
        logging.info("Автоматическая очистка логов выполнена.")
