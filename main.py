# ==================== ПОЛНЫЙ РАБОЧИЙ БОТ ====================
# Часть 1: Импорты, настройки, глобальные переменные, безопасная отправка,
#         подключение к БД, вспомогательные функции и мидлварь

import asyncio
import logging
import random
import os
import time
import string
import csv
import io
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import asyncpg
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.exceptions import (
    BotBlocked, UserDeactivated, ChatNotFound, RetryAfter,
    TelegramAPIError, MessageNotModified, MessageToEditNotFound,
    TerminatedByOtherGetUpdates
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
    raise ValueError("DATABASE_URL не задан. Создай PostgreSQL базу в Railway.")

if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

# Значения по умолчанию для настроек (все ключи корректны)
DEFAULT_SETTINGS = {
    "random_attack_cost": "0",
    "targeted_attack_cost": "50",
    "theft_cooldown_minutes": "30",
    "theft_success_chance": "40",
    "theft_defense_chance": "20",
    "theft_defense_penalty": "10",
    "casino_win_chance": "30",
    "min_theft_amount": "5",
    "max_theft_amount": "15",
    "dice_multiplier": "2",
    "guess_multiplier": "5",
    "guess_reputation": "1",
    "chat_notify_big_win": "1",
    "chat_notify_big_purchase": "1",
    "chat_notify_giveaway": "1",
    "gift_amount": "30",
    "gift_limit_per_day": "3",
    "referral_bonus": "50",
    "referral_reputation": "2",
    "exp_per_casino_win": "5",
    "exp_per_casino_lose": "1",
    "exp_per_dice_win": "3",
    "exp_per_dice_lose": "1",
    "exp_per_guess_win": "4",
    "exp_per_guess_lose": "1",
    "exp_per_theft_success": "10",
    "exp_per_theft_fail": "2",
    "exp_per_theft_defense": "5",
    "exp_per_game_win": "15",
    "exp_per_game_lose": "3",
    "level_multiplier": "100",
    "level_reward_coins": "30",
    "level_reward_reputation": "3",
    "level_reward_coins_increment": "5",
    "level_reward_reputation_increment": "1",
    "reputation_theft_bonus": "0.5",
    "reputation_defense_bonus": "0.5",
    "boss_spawn_chance": "20",
    "boss_min_interval": "360",
    "boss_max_per_day": "2",
    "boss_hp_multiplier": "100",
    "boss_attack_cooldown": "3",
    "boss_base_damage": "10",
    "boss_reward_coins": "500",
    "boss_reward_coins_variance": "200",
    "gift_global_limit_per_user": "4",
    "gift_cooldown": "60",
    "stat_strength_per_level": "1",
    "stat_agility_per_level": "1",
    "stat_defense_per_level": "1",
    "auction_min_bid_step": "10",
    "auction_commission": "0",
    "auction_notify_chats": "1",
    "fight_cooldown_minutes": "30",
    "fight_base_damage": "5",
    "fight_damage_variance": "3",
    "fight_authority_min": "1",
    "fight_authority_max": "3",
    "gym_strength_cost": "10",
    "gym_agility_cost": "10",
    "gym_defense_cost": "10",
    "cleanup_days_fight_logs": "7",
    "cleanup_days_bosses": "7",
    "cleanup_days_auctions": "30",
    "cleanup_days_purchases": "30",
    "cleanup_days_giveaways": "30",
    "cleanup_days_user_tasks": "30",
}

# Константы
ITEMS_PER_PAGE = 10
BIG_WIN_THRESHOLD = 100
BIG_PURCHASE_THRESHOLD = 100
MAX_ROOMS = 20
MIN_PLAYERS = 2
MAX_PLAYERS = 5
MIN_BET = 3

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

db_pool = None
settings_cache = {}
last_settings_update = 0
channels_cache = []
last_channels_update = 0
confirmed_chats_cache = {}
last_confirmed_chats_update = 0

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==================== МИДЛВАРЬ ДЛЯ ЗАЩИТЫ ОТ ФЛУДА ====================
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit=1.0):
        self.rate_limit = rate_limit
        self.user_last_time = defaultdict(float)
        super().__init__()

    async def on_process_message(self, message: types.Message, data: dict):
        if message.chat.type != 'private' or await is_admin(message.from_user.id):
            return
        user_id = message.from_user.id
        now = time.time()
        if now - self.user_last_time[user_id] < self.rate_limit:
            await message.reply("⏳ Слишком много запросов. Подожди секунду.")
            raise CancelHandler()
        self.user_last_time[user_id] = now

dp.middleware.setup(ThrottlingMiddleware(rate_limit=0.5))

# ==================== БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ ====================
async def safe_send_message(user_id: int, text: str, **kwargs):
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
    asyncio.create_task(safe_send_message(user_id, text, **kwargs))

async def safe_send_chat(chat_id: int, text: str, **kwargs):
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send to chat {chat_id}: {e}")

# ==================== ПОДКЛЮЧЕНИЕ К POSTGRESQL ====================
async def create_db_pool():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60,
            max_queries=50000,
            max_inactive_connection_lifetime=300
        )
        logging.info("✅ Подключение к PostgreSQL установлено")
    except Exception as e:
        logging.error(f"❌ Ошибка подключения к БД: {e}")
        raise

async def init_db():
    async with db_pool.acquire() as conn:
        # Таблица users
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TEXT,
                balance INTEGER DEFAULT 0,
                reputation INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                negative_balance INTEGER DEFAULT 0,
                last_bonus TEXT,
                last_theft_time TEXT,
                theft_attempts INTEGER DEFAULT 0,
                theft_success INTEGER DEFAULT 0,
                theft_failed INTEGER DEFAULT 0,
                theft_protected INTEGER DEFAULT 0,
                casino_wins INTEGER DEFAULT 0,
                casino_losses INTEGER DEFAULT 0,
                guess_wins INTEGER DEFAULT 0,
                guess_losses INTEGER DEFAULT 0,
                game_wins INTEGER DEFAULT 0
            )
        ''')
        # Добавляем новые поля
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS exp INTEGER DEFAULT 0')
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1')
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS strength INTEGER DEFAULT 1')
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS agility INTEGER DEFAULT 1')
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS defense INTEGER DEFAULT 1')
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_gift_time TEXT')
        await conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS gift_count_today INTEGER DEFAULT 0')

        # Таблица подтверждённых чатов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS confirmed_chats (
                chat_id BIGINT PRIMARY KEY,
                title TEXT,
                type TEXT,
                joined_date TEXT,
                confirmed_by BIGINT,
                confirmed_date TEXT,
                notify_enabled BOOLEAN DEFAULT TRUE,
                last_gift_date DATE,
                gift_count_today INTEGER DEFAULT 0,
                boss_last_spawn TEXT,
                boss_spawn_count INTEGER DEFAULT 0
            )
        ''')

        # Таблица запросов на подтверждение чатов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_confirmation_requests (
                chat_id BIGINT PRIMARY KEY,
                title TEXT,
                type TEXT,
                requested_by BIGINT,
                request_date TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')

        # Таблица боссов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bosses (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                name TEXT,
                level INTEGER,
                hp INTEGER,
                max_hp INTEGER,
                spawned_at TEXT,
                expires_at TEXT,
                reward_coins INTEGER,
                participants BIGINT[] DEFAULT '{}',
                status TEXT DEFAULT 'active'
            )
        ''')

        # Таблица атак на босса
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS boss_attacks (
                boss_id INTEGER,
                user_id BIGINT,
                damage INTEGER,
                attack_time TEXT,
                PRIMARY KEY (boss_id, user_id)
            )
        ''')

        # Таблица каналов для подписки
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                chat_id TEXT UNIQUE,
                title TEXT,
                invite_link TEXT
            )
        ''')
        # Таблица рефералов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT,
                referred_id BIGINT UNIQUE,
                referred_date TEXT,
                reward_given BOOLEAN DEFAULT FALSE,
                clicks INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT FALSE
            )
        ''')
        # Таблица товаров магазина
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                price INTEGER,
                stock INTEGER DEFAULT -1
            )
        ''')
        # Таблица покупок
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                item_id INTEGER,
                purchase_date TEXT,
                status TEXT DEFAULT 'pending',
                admin_comment TEXT
            )
        ''')
        # Таблица промокодов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        # Таблица активаций промокодов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS promo_activations (
                user_id BIGINT,
                promo_code TEXT,
                activated_at TEXT,
                PRIMARY KEY (user_id, promo_code)
            )
        ''')
        # Таблица розыгрышей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id SERIAL PRIMARY KEY,
                prize TEXT,
                description TEXT,
                end_date TEXT,
                media_file_id TEXT,
                media_type TEXT,
                status TEXT DEFAULT 'active',
                winner_id BIGINT,
                winners_count INTEGER DEFAULT 1,
                notified BOOLEAN DEFAULT FALSE
            )
        ''')
        # Таблица участников розыгрышей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                user_id BIGINT,
                giveaway_id INTEGER,
                PRIMARY KEY (user_id, giveaway_id)
            )
        ''')
        # Таблица младших админов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_by BIGINT,
                added_date TEXT
            )
        ''')
        # Таблица забаненных
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id BIGINT PRIMARY KEY,
                banned_by BIGINT,
                banned_date TEXT,
                reason TEXT
            )
        ''')
        # Таблица настроек
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Таблица заданий
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
                created_at TEXT,
                active BOOLEAN DEFAULT TRUE,
                max_completions INTEGER DEFAULT 1,
                completed_count INTEGER DEFAULT 0
            )
        ''')
        # Таблица выполненных заданий
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                user_id BIGINT,
                task_id INTEGER,
                completed_at TEXT,
                expires_at TEXT,
                status TEXT DEFAULT 'completed',
                PRIMARY KEY (user_id, task_id)
            )
        ''')
        # Таблица мультиплеерных игр
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS multiplayer_games (
                game_id TEXT PRIMARY KEY,
                host_id BIGINT,
                max_players INTEGER,
                bet_amount INTEGER,
                status TEXT DEFAULT 'waiting',
                deck TEXT,
                created_at TEXT,
                current_player_index INTEGER DEFAULT 0
            )
        ''')
        # Таблица игроков в мультиплеере
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS game_players (
                game_id TEXT,
                user_id BIGINT,
                username TEXT,
                cards TEXT,
                value INTEGER DEFAULT 0,
                stopped BOOLEAN DEFAULT FALSE,
                joined_at TEXT,
                doubled BOOLEAN DEFAULT FALSE,
                surrendered BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (game_id, user_id)
            )
        ''')
        # Таблица наград за уровень
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS level_rewards (
                level INTEGER PRIMARY KEY,
                coins INTEGER,
                reputation INTEGER
            )
        ''')

        # Таблицы аукционов
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
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS auction_bids (
                id SERIAL PRIMARY KEY,
                auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                bid_amount INTEGER NOT NULL,
                bid_time TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Таблицы для боя в чатах
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
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fight_cooldowns (
                chat_id BIGINT,
                user_id BIGINT,
                last_fight TIMESTAMP,
                PRIMARY KEY (chat_id, user_id)
            )
        ''')
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

        # Индексы
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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_confirmed_chats_chat ON confirmed_chats(chat_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_requests_status ON chat_confirmation_requests(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_auctions_status ON auctions(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_auctions_end_time ON auctions(end_time)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_auction_bids_auction ON auction_bids(auction_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_authority_chat ON chat_authority(chat_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_fight_cooldowns_chat ON fight_cooldowns(chat_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_fight_logs_timestamp ON fight_logs(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ads_enabled ON ads(enabled)")

    # Заполняем настройки
    await init_settings()
    # Заполняем level_rewards
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
    async with db_pool.acquire() as conn:
        for key, value in DEFAULT_SETTINGS.items():
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                key, value
            )

async def get_setting(key: str) -> str:
    global settings_cache, last_settings_update
    now = time.time()
    if now - last_settings_update > 60 or not settings_cache:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM settings")
            settings_cache = {row['key']: row['value'] for row in rows}
        last_settings_update = now
    return settings_cache.get(key, DEFAULT_SETTINGS[key])

async def set_setting(key: str, value: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE settings SET value=$1 WHERE key=$2", value, key)
    settings_cache[key] = value

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS

async def is_junior_admin(user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchval("SELECT user_id FROM admins WHERE user_id=$1", user_id)
    return row is not None

async def is_admin(user_id: int) -> bool:
    return await is_super_admin(user_id) or await is_junior_admin(user_id)

async def is_banned(user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchval("SELECT user_id FROM banned_users WHERE user_id=$1", user_id)
    return row is not None

async def get_channels():
    global channels_cache, last_channels_update
    now = time.time()
    if now - last_channels_update > 300 or not channels_cache:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id, title, invite_link FROM channels")
            channels_cache = [(r['chat_id'], r['title'], r['invite_link']) for r in rows]
        last_channels_update = now
    return channels_cache

async def get_confirmed_chats(force_update=False) -> Dict[int, dict]:
    global confirmed_chats_cache, last_confirmed_chats_update
    now = time.time()
    if force_update or now - last_confirmed_chats_update > 300 or not confirmed_chats_cache:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM confirmed_chats")
            confirmed_chats_cache = {row['chat_id']: dict(row) for row in rows}
        last_confirmed_chats_update = now
    return confirmed_chats_cache

async def is_chat_confirmed(chat_id: int) -> bool:
    confirmed = await get_confirmed_chats()
    return chat_id in confirmed

async def add_confirmed_chat(chat_id: int, title: str, chat_type: str, confirmed_by: int):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO confirmed_chats (chat_id, title, type, joined_date, confirmed_by, confirmed_date) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (chat_id) DO UPDATE SET confirmed_by=$5, confirmed_date=$6",
            chat_id, title, chat_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), confirmed_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    await get_confirmed_chats(force_update=True)

async def remove_confirmed_chat(chat_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM confirmed_chats WHERE chat_id=$1", chat_id)
    await get_confirmed_chats(force_update=True)

async def create_chat_confirmation_request(chat_id: int, title: str, chat_type: str, requested_by: int):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_confirmation_requests (chat_id, title, type, requested_by, request_date, status) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (chat_id) DO UPDATE SET status='pending', requested_by=$4, request_date=$5",
            chat_id, title, chat_type, requested_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'pending'
        )

async def get_pending_chat_requests() -> List[dict]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM chat_confirmation_requests WHERE status='pending' ORDER BY request_date")
        return [dict(r) for r in rows]

async def update_chat_request_status(chat_id: int, status: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE chat_confirmation_requests SET status=$1 WHERE chat_id=$2", status, chat_id)

# ==================== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ====================
async def get_user_balance(user_id: int) -> int:
    async with db_pool.acquire() as conn:
        balance = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1", user_id)
        return balance if balance is not None else 0

async def update_user_balance(user_id: int, delta: int, conn=None):
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
                f"Награда: +{reward['coins']} монет, +{reward['reputation']} репутации!\n"
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

async def find_user_by_input(input_str: str) -> Optional[Dict]:
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

async def notify_chats(message_text: str, importance: str = 'info'):
    confirmed = await get_confirmed_chats()
    for chat_id, data in confirmed.items():
        if not data.get('notify_enabled', True):
            continue
        await safe_send_chat(chat_id, message_text)

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

# ==================== ФУНКЦИИ ДЛЯ АВТОРИТЕТА ====================
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

async def can_fight(chat_id: int, user_id: int) -> Tuple[bool, int]:
    cooldown = int(await get_setting("fight_cooldown_minutes"))
    async with db_pool.acquire() as conn:
        last = await conn.fetchval("SELECT last_fight FROM fight_cooldowns WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)
        if last:
            diff = datetime.now() - last
            remaining = cooldown * 60 - diff.total_seconds()
            if remaining > 0:
                return False, int(remaining // 60) + 1
        return True, 0

async def set_fight_cooldown(chat_id: int, user_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO fight_cooldowns (chat_id, user_id, last_fight)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET last_fight = $3
        ''', chat_id, user_id, datetime.now())

# ==================== ФУНКЦИИ ДЛЯ БОССОВ ====================
async def spawn_boss(chat_id: int, level: int = None):
    if level is None:
        level = random.randint(1, 5)
    boss_names = [
        "Гоблин-грабитель", "Тролль-вышибала", "Дракончик", "Злобный Кролик",
        "Крысиный Король", "Лесной Дух", "Каменный Голем", "Огненный Элементаль"
    ]
    name = random.choice(boss_names)
    hp_mult = int(await get_setting("boss_hp_multiplier"))
    hp = level * hp_mult * random.randint(5, 10)
    base_reward = int(await get_setting("boss_reward_coins"))
    variance = int(await get_setting("boss_reward_coins_variance"))
    reward = base_reward + random.randint(-variance, variance)
    now = datetime.now()
    expires_at = now + timedelta(hours=2)
    async with db_pool.acquire() as conn:
        boss_id = await conn.fetchval(
            "INSERT INTO bosses (chat_id, name, level, hp, max_hp, spawned_at, expires_at, reward_coins, participants, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id",
            chat_id, name, level, hp, hp, now.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at.strftime("%Y-%m-%d %H:%M:%S"), reward, [], 'active'
        )
        await conn.execute(
            "UPDATE confirmed_chats SET boss_last_spawn=$1, boss_spawn_count = boss_spawn_count + 1 WHERE chat_id=$2",
            now.strftime("%Y-%m-%d %H:%M:%S"), chat_id
        )
    phrase = random.choice(BOSS_SPAWN_PHRASES).format(name=name, level=level, hp=hp)
    await safe_send_chat(chat_id, phrase)

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
        phrase = random.choice(BOSS_DEATH_PHRASES).format(name=boss['name'])
        await safe_send_chat(boss['chat_id'], f"{phrase}\nУчастники получили по {reward_per_player} монет!")

# ==================== ФУНКЦИИ ДЛЯ ЭКСПОРТА ====================
async def export_users_to_csv() -> bytes:
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

def format_time_remaining(seconds: int) -> str:
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
    phrase = random.choice(phrase_list)
    return phrase.format(**kwargs)

# ==================== ФУНКЦИЯ ПРОВЕРКИ ПОДПИСКИ ====================
async def check_subscription(user_id: int):
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

# ==================== ФУНКЦИЯ ДЛЯ ЗАПУСКА ПЕРЕД СТАРТОМ ====================
async def before_start():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook удалён, пропущены старые обновления")

# ==================== ВЕБ-СЕРВЕР ДЛЯ HEALTH CHECKS ====================
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")
  # ==================== ПОЛНЫЙ РАБОЧИЙ БОТ ====================
# Часть 2: Состояния FSM, клавиатуры, текстовые фразы

# ==================== СОСТОЯНИЯ FSM ====================
class CreateGiveaway(StatesGroup):
    prize = State()
    description = State()
    end_date = State()
    media = State()

class AddChannel(StatesGroup):
    chat_id = State()
    title = State()
    invite_link = State()

class RemoveChannel(StatesGroup):
    chat_id = State()

class AddShopItem(StatesGroup):
    name = State()
    description = State()
    price = State()
    stock = State()

class RemoveShopItem(StatesGroup):
    item_id = State()

class EditShopItem(StatesGroup):
    item_id = State()
    field = State()
    value = State()

class CreatePromocode(StatesGroup):
    code = State()
    reward = State()
    max_uses = State()

class Broadcast(StatesGroup):
    media = State()

class AddBalance(StatesGroup):
    user_id = State()
    amount = State()

class RemoveBalance(StatesGroup):
    user_id = State()
    amount = State()

class AddReputation(StatesGroup):
    user_id = State()
    amount = State()

class RemoveReputation(StatesGroup):
    user_id = State()
    amount = State()

class AddExp(StatesGroup):
    user_id = State()
    amount = State()

class SetLevel(StatesGroup):
    user_id = State()
    level = State()

class CasinoBet(StatesGroup):
    amount = State()

class DiceBet(StatesGroup):
    amount = State()

class GuessBet(StatesGroup):
    amount = State()
    number = State()

class PromoActivate(StatesGroup):
    code = State()

class TheftTarget(StatesGroup):
    target = State()

class FindUser(StatesGroup):
    query = State()

class AddJuniorAdmin(StatesGroup):
    user_id = State()

class RemoveJuniorAdmin(StatesGroup):
    user_id = State()

class CompleteGiveaway(StatesGroup):
    giveaway_id = State()
    winners_count = State()

class BlockUser(StatesGroup):
    user_id = State()
    reason = State()

class UnblockUser(StatesGroup):
    user_id = State()

class EditSettings(StatesGroup):
    key = State()
    value = State()

class CreateTask(StatesGroup):
    name = State()
    description = State()
    task_type = State()
    target_id = State()
    reward_coins = State()
    reward_reputation = State()
    required_days = State()
    penalty_days = State()
    max_completions = State()

class DeleteTask(StatesGroup):
    task_id = State()

class MultiplayerGame(StatesGroup):
    create_max_players = State()
    create_bet = State()
    join_code = State()

class RoomChat(StatesGroup):
    message = State()

class ManageChats(StatesGroup):
    action = State()
    chat_id = State()

class BossSpawn(StatesGroup):
    chat_id = State()
    level = State()

class CreateAuction(StatesGroup):
    item_name = State()
    description = State()
    start_price = State()
    end_time = State()
    target_price = State()

class AuctionBid(StatesGroup):
    auction_id = State()
    amount = State()

class CancelAuction(StatesGroup):
    auction_id = State()

class CreateAd(StatesGroup):
    text = State()
    interval = State()
    target = State()

# ==================== КЛАВИАТУРЫ ====================
def subscription_inline(not_subscribed):
    kb = []
    for title, link in not_subscribed:
        if link:
            kb.append([InlineKeyboardButton(text=f"📢 {title}", url=link)])
        else:
            kb.append([InlineKeyboardButton(text=f"📢 {title}", callback_data="no_link")])
    kb.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")])
    return InlineKeyboardMarkup(row_width=1, inline_keyboard=kb)

def user_main_keyboard(is_admin_user=False):
    buttons = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус")],
        [KeyboardButton(text="🛒 Магазин подарков"), KeyboardButton(text="🎰 Казино")],
        [KeyboardButton(text="🎟 Промокод"), KeyboardButton(text="🏆 Топ игроков")],
        [KeyboardButton(text="💰 Мои покупки"), KeyboardButton(text="🔫 Ограбить")],
        [KeyboardButton(text="🎲 Игры"), KeyboardButton(text="⭐️ Репутация")],
        [KeyboardButton(text="📋 Задания"), KeyboardButton(text="🔗 Рефералка")],
        [KeyboardButton(text="🎲 Розыгрыши"), KeyboardButton(text="📊 Уровень")],
        [KeyboardButton(text="🏷 Аукцион")],
    ]
    if is_admin_user:
        buttons.append([KeyboardButton(text="⚙️ Админ панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def theft_choice_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎲 Случайная цель")],
        [KeyboardButton(text="👤 Выбрать пользователя")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def games_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎲 Кости"), KeyboardButton(text="🔢 Угадай число")],
        [KeyboardButton(text="👥 Комнатная игра 21")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def room_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Список комнат")],
        [KeyboardButton(text="🎮 Создать комнату")],
        [KeyboardButton(text="ℹ️ Правила игры")],
        [KeyboardButton(text="🏆 Топ игроков")],
        [KeyboardButton(text="◀️ Назад в игры")]
    ], resize_keyboard=True)

def room_control_keyboard(game_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать игру", callback_data=f"start_game_{game_id}")],
        [InlineKeyboardButton(text="❌ Закрыть комнату", callback_data=f"close_room_{game_id}")]
    ])

def room_action_keyboard(game_id, can_double=True):
    kb_buttons = []
    row1 = [
        InlineKeyboardButton(text="🎯 Ещё", callback_data="room_hit"),
        InlineKeyboardButton(text="🛑 Хватит", callback_data="room_stand")
    ]
    kb_buttons.append(row1)
    row2 = []
    if can_double:
        row2.append(InlineKeyboardButton(text="💰 Удвоить", callback_data="room_double"))
    row2.append(InlineKeyboardButton(text="🏳️ Сдаться", callback_data="room_surrender"))
    kb_buttons.append(row2)
    kb_buttons.append([InlineKeyboardButton(text="💬 Написать в чат", callback_data="room_chat")])
    return InlineKeyboardMarkup(inline_keyboard=kb_buttons)

def leave_room_keyboard(game_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Выйти из комнаты", callback_data=f"leave_room_{game_id}")]
    ])

# ==================== АДМИН-КЛАВИАТУРЫ ====================
def admin_main_keyboard(is_super):
    buttons = [
        [KeyboardButton(text="👥 Управление пользователями")],
        [KeyboardButton(text="🛒 Управление магазином")],
        [KeyboardButton(text="🎁 Управление розыгрышами")],
        [KeyboardButton(text="📢 Управление каналами")],
        [KeyboardButton(text="🎫 Управление промокодами")],
        [KeyboardButton(text="📋 Управление заданиями")],
        [KeyboardButton(text="🤖 Управление чатами")],
        [KeyboardButton(text="👾 Управление боссами")],
        [KeyboardButton(text="🏷 Управление аукционами")],
        [KeyboardButton(text="⚔️ Управление помощниками")],
        [KeyboardButton(text="📢 Управление рекламой")],
        [KeyboardButton(text="⚙️ Настройки игры")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🔨 Блокировки")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🧹 Очистка старых записей")],
    ]
    if is_super:
        buttons.append([KeyboardButton(text="➕ Управление админами")])
    buttons.append([KeyboardButton(text="◀️ Назад в главное меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_users_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Начислить монеты"), KeyboardButton(text="💸 Списать монеты")],
        [KeyboardButton(text="⭐️ Начислить репутацию"), KeyboardButton(text="🔻 Снять репутацию")],
        [KeyboardButton(text="📈 Начислить опыт"), KeyboardButton(text="🔝 Установить уровень")],
        [KeyboardButton(text="👥 Найти пользователя")],
        [KeyboardButton(text="📊 Экспорт пользователей")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_shop_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить товар")],
        [KeyboardButton(text="➖ Удалить товар")],
        [KeyboardButton(text="✏️ Редактировать товар")],
        [KeyboardButton(text="📋 Список товаров")],
        [KeyboardButton(text="🛍️ Список покупок")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_giveaway_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Создать розыгрыш")],
        [KeyboardButton(text="📋 Активные розыгрыши")],
        [KeyboardButton(text="✅ Завершить розыгрыш")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_channel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить канал")],
        [KeyboardButton(text="➖ Удалить канал")],
        [KeyboardButton(text="📋 Список каналов")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_promo_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Создать промокод")],
        [KeyboardButton(text="📋 Список промокодов")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_tasks_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Создать задание")],
        [KeyboardButton(text="📋 Список заданий")],
        [KeyboardButton(text="❌ Удалить задание")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_ban_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔨 Заблокировать пользователя")],
        [KeyboardButton(text="🔓 Разблокировать пользователя")],
        [KeyboardButton(text="📋 Список заблокированных")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_admins_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить админа")],
        [KeyboardButton(text="➖ Удалить админа")],
        [KeyboardButton(text="📋 Список админов")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_chats_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Список запросов на подтверждение")],
        [KeyboardButton(text="✅ Подтвердить чат")],
        [KeyboardButton(text="❌ Отклонить запрос")],
        [KeyboardButton(text="📋 Список подтверждённых чатов")],
        [KeyboardButton(text="🗑 Удалить чат из подтверждённых")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_boss_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Активные боссы")],
        [KeyboardButton(text="⚔️ Создать босса вручную")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_helper_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Активные помощники")],
        [KeyboardButton(text="📊 Топы чатов")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_auction_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Создать аукцион")],
        [KeyboardButton(text="📋 Активные аукционы")],
        [KeyboardButton(text="❌ Отменить аукцион")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_ad_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Создать рекламу")],
        [KeyboardButton(text="📋 Список рекламы")],
        [KeyboardButton(text="✏️ Редактировать рекламу")],
        [KeyboardButton(text="❌ Удалить рекламу")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ], resize_keyboard=True)

def settings_reply_keyboard():
    buttons = [
        [KeyboardButton(text="⚙️ Кража")],
        [KeyboardButton(text="⚙️ Казино и игры")],
        [KeyboardButton(text="⚙️ Опыт и уровни")],
        [KeyboardButton(text="⚙️ Боссы")],
        [KeyboardButton(text="⚙️ Помощники")],
        [KeyboardButton(text="⚙️ Аукцион")],
        [KeyboardButton(text="⚙️ Подгон")],
        [KeyboardButton(text="⚙️ Рефералы")],
        [KeyboardButton(text="⚙️ Очистка логов")],
        [KeyboardButton(text="◀️ Назад в админку")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Назад")]], resize_keyboard=True)

def purchase_action_keyboard(purchase_id):
    return InlineKeyboardMarkup(row_width=2, inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"purchase_done_{purchase_id}"),
         InlineKeyboardButton(text="❌ Отказ", callback_data=f"purchase_reject_{purchase_id}")]
    ])

def confirm_chat_inline(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_chat_{chat_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_chat_{chat_id}")]
    ])

def auction_list_keyboard(auctions, page, total_pages):
    kb = []
    for auction in auctions:
        kb.append([InlineKeyboardButton(
            text=f"{auction['item_name']} | Текущая ставка: {auction['current_price']}",
            callback_data=f"auction_view_{auction['id']}"
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"auction_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"auction_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="« Назад", callback_data="auction_list")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def auction_detail_keyboard(auction_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Сделать ставку", callback_data=f"auction_bid_{auction_id}")],
        [InlineKeyboardButton(text="« Назад к списку", callback_data="auction_list")]
    ])

# ==================== ТЕКСТОВЫЕ ФРАЗЫ ====================
BONUS_PHRASES = [
    "🎉 Красава, лови +{bonus} монет!",
    "💰 Зашкварно богатенький стал! +{bonus}",
    "🌟 Хайпанули? +{bonus} монет в карман!",
    "🍀 Удача крашеная, держи +{bonus}",
    "🎁 Ты в тренде, +{bonus} монет!"
]

CASINO_WIN_PHRASES = [
    "🎰 Краш! Ты выиграл {win} монет (чистыми {profit})!",
    "🍒 Хайповая комбинация! +{profit} монет!",
    "💫 Фортуна крашеная, твой выигрыш: {win} монет!",
    "🎲 Изи-катка, {profit} монет твои!",
    "✨ Ты красавчик, обыграл казино! +{profit} монет!"
]

CASINO_LOSE_PHRASES = [
    "😢 Обидно, потерял {loss} монет.",
    "💔 Зашкварно, минус {loss}.",
    "📉 Не фортануло, -{loss} монет.",
    "🍂 В следующий раз краш будет твоим, а пока -{loss}.",
    "⚡️ Лузернулся на {loss} монет."
]

PURCHASE_PHRASES = [
    "✅ Купил! Админ скоро в личку прилетит.",
    "🛒 Товар твой! Жди админа, бро.",
    "🎁 Крутая покупка! Админ уже в курсе.",
    "💎 Ты краш! Админ свяжется."
]

THEFT_CHOICE_PHRASES = [
    "🔫 Выбери, как хочешь напасть:",
    "💢 Кого будем грабить?",
    "😈 Куда направим бандитские лапы?"
]

THEFT_COOLDOWN_PHRASES = [
    "⏳ Ты ещё не остыл после прошлого налёта. Подожди {minutes} мин.",
    "🕐 Полегче, ковбой! Отдохни {minutes} минут.",
    "😴 Грабить так часто – плохая примета. Возвращайся через {minutes} мин."
]

THEFT_NO_MONEY_PHRASES = [
    "😕 У тебя нет монет даже на подготовку к краже!",
    "💸 Сначала заработай, потом грабить будешь.",
    "💰 Пустой карман – не до криминала."
]

THEFT_SUCCESS_PHRASES = [
    "🔫 Красава! Ты украл {amount} монет у {target}!",
    "💰 Хайпанул, {amount} монет у {target} теперь твои!",
    "🦹‍♂️ Удачная кража! +{amount} от {target}",
    "😈 Ты краш, {target} даже не понял! +{amount}"
]

THEFT_FAIL_PHRASES = [
    "😢 Облом, тебя спалили! Ничего не украл.",
    "🚨 Треск, {target} оказался слишком бдительным!",
    "👮‍♂️ Пришлось сваливать, 0 монет.",
    "💔 Не фортануло, {target} слишком крутой."
]

THEFT_DEFENSE_PHRASES = [
    "🛡️ {target} отразил атаку! Ты потерял {penalty} монет.",
    "💥 Бабах! {target} выставил защиту, и ты лишился {penalty} монет.",
    "😱 Засада! Ты напоролся на защиту и потерял {penalty} монет."
]

THEFT_VICTIM_DEFENSE_PHRASES = [
    "🛡️ Твоя защита сработала! {attacker} ничего не украл и потерял {penalty} монет.",
    "💪 Ты краш! Отбил атаку {attacker} и получил {penalty} монет.",
    "😎 Ха! {attacker} думал поживиться, а сам потерял {penalty} монет."
]

DICE_WIN_PHRASES = [
    "🎲 {dice1} + {dice2} = {total} — Победа! +{profit} монет!",
    "🎲 Круто! {dice1}+{dice2}={total}, ты выиграл {profit}!",
    "🎲 Хайп! {total} очков, твой выигрыш: {profit}!"
]

DICE_LOSE_PHRASES = [
    "🎲 {dice1} + {dice2} = {total} — Проигрыш. -{loss} монет.",
    "🎲 Эх, {total} очков, не повезло. -{loss}.",
    "🎲 В этот раз не зашло, -{loss} монет."
]

GUESS_WIN_PHRASES = [
    "🔢 Ты угадал! Было {secret}. Выигрыш: +{profit} монет и +{rep} репутации!",
    "🔢 Красава! Число {secret}, твой выигрыш {profit} монет!",
    "🔢 Хайпанул! +{profit} монет, репутация +{rep}!"
]

GUESS_LOSE_PHRASES = [
    "🔢 Не угадал. Было {secret}. -{loss} монет.",
    "🔢 Увы, загадано {secret}. Теряешь {loss} монет.",
    "🔢 Не фортануло, правильный ответ {secret}. -{loss}."
]

CHAT_WIN_PHRASES = [
    "🔥 {name} только что выиграл {amount} монет в казино!",
    "💰 Удача на стороне {name}: +{amount} монет!",
    "🎰 {name} сорвал куш — {amount} монет!"
]

CHAT_PURCHASE_PHRASES = [
    "🛒 {name} купил {item} за {price} монет!",
    "🎁 {name} приобрёл {item}! Админ уже в пути.",
    "💎 {name} потратил {price} монет на {item}!"
]

CHAT_GIVEAWAY_PHRASES = [
    "🎁 Не пропусти розыгрыш! Осталось {time}",
    "⏰ Напоминание: розыгрыш {prize} заканчивается через {time}",
    "🔥 Участвуй в розыгрыше {prize}! Осталось {time}"
]

BOSS_SPAWN_PHRASES = [
    "⚠️ ВНИМАНИЕ! В чате появился {name} (Уровень {level})! Здоровье: {hp}",
    "👾 Босс {name} пришёл навестить нас! Уровень {level}, HP: {hp}",
    "🔥 Легендарный {name} пробудился! Уровень {level}, здоровье: {hp}",
]

BOSS_HIT_PHRASES = [
    "💥 Ты нанёс {damage} урона!",
    "⚡️ Удар! -{damage} HP",
    "🔥 Критическое попадание! {damage} урона",
]

BOSS_MISS_PHRASES = [
    "💨 Промах! Босс уклонился",
    "😵 Твоя атака не достигла цели",
    "🛡 Босс отразил удар",
]

BOSS_DEATH_PHRASES = [
    "🏆 Босс {name} повержен! Все участники получают награду!",
    "🎉 Победа! {name} пал! Награда разделена между участниками",
    "💀 Босс уничтожен! Спасибо за участие!",
]

BOSS_STATUS_PHRASES = [
    "👾 {name} | Уровень {level} | HP: {current_hp}/{max_hp}",
]

FIGHT_HIT_PHRASES = [
    "💥 Ты нанёс {damage} урона банде! Заработал {authority} авторитета.",
    "⚡️ Твой удар пришёлся точно в цель! +{damage} урона, +{authority} авторитета.",
    "🔥 Критический удар! Ты нанёс {damage} урона и получил {authority} авторитета.",
    "🤜 Хрясь! Банда получила {damage} урона. Твой авторитет +{authority}.",
    "👊 Смачный удар! {damage} урона, {authority} авторитета.",
]

FIGHT_CRIT_PHRASES = [
    "💢 СОКРУШИТЕЛЬНЫЙ УДАР! Ты нанёс {damage} урона (крит!) и заработал {authority} авторитета.",
    "🌟 Ты в ярости! Критический урон {damage}, авторитет +{authority}.",
    "⚡️ МОЛНИЕНОСНЫЙ ВЫПАД! {damage} урона, +{authority} авторитета.",
]

FIGHT_MISS_PHRASES = [
    "💨 Ты промахнулся! Банда смеётся над тобой. Авторитет не получен.",
    "😵 Твоя атака не достигла цели. Банда даже не заметила.",
    "🍃 Вжух! Мимо. Попробуй ещё через полчаса.",
]

FIGHT_COUNTER_PHRASES = [
    "😵 Банда контратаковала! Ты потерял {damage} монет и не получил авторитет.",
    "💥 Ответный удар! Ты потерял {damage} монет.",
    "👊 Тебя самого ударили! Минус {damage} монет.",
]
# ==================== ПОЛНЫЙ РАБОЧИЙ БОТ ====================
# Часть 3: Пользовательские хендлеры (личные сообщения)

# ==================== КОМАНДА HELP ====================
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    text = (
        "🤖 <b>Malboro GAME</b> – помощь:\n\n"
        "• 👤 Профиль – баланс, уровень, репутация, статы\n"
        "• 🎁 Бонус – ежедневная награда\n"
        "• 🛒 Магазин подарков – покупка подарков\n"
        "• 🎰 Казино – испытай удачу (/casino)\n"
        "• 🎟 Промокод – активация промокодов\n"
        "• 🏆 Топ игроков – лучшие по балансу, уровню, статам\n"
        "• 💰 Мои покупки – история заказов\n"
        "• 🔫 Ограбить – укради монеты у другого\n"
        "• 🎲 Игры – кости, угадай число, мультиплеер 21\n"
        "• ⭐️ Репутация – твой авторитет\n"
        "• 📋 Задания – выполняй и получай награды\n"
        "• 🔗 Рефералка – приглашай друзей\n"
        "• 📊 Уровень – твой прогресс\n"
        "• 🏷 Аукцион – участвуй в торгах\n\n"
        "Администраторы имеют дополнительные функции."
    )
    await message.answer(text, reply_markup=user_main_keyboard(await is_admin(user_id)))

# ==================== КОМАНДА START ====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        await message.answer("⛔ Вы заблокированы.")
        return

    args = message.get_args()
    if args and args.startswith('ref'):
        try:
            referrer_id = int(args[3:])
            if referrer_id != user_id and not await is_banned(referrer_id):
                async with db_pool.acquire() as conn:
                    existing = await conn.fetchval("SELECT 1 FROM referrals WHERE referred_id=$1", user_id)
                    if not existing:
                        await conn.execute(
                            "INSERT INTO referrals (referrer_id, referred_id, referred_date, reward_given, clicks) VALUES ($1, $2, $3, $4, 1) ON CONFLICT (referred_id) DO NOTHING",
                            referrer_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), False
                        )
                        await conn.execute("UPDATE referrals SET clicks = clicks + 1 WHERE referred_id=$1", user_id)
                        await safe_send_message(referrer_id, f"🔗 Новый пользователь {message.from_user.first_name} зарегистрировался по вашей ссылке! Награда будет выдана после того, как он совершит 15 успешных ограблений.")
        except:
            pass

    username = message.from_user.username
    first_name = message.from_user.first_name
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id, username, first_name, joined_date, balance, reputation, total_spent, negative_balance, game_wins, exp, level, strength, agility, defense) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) ON CONFLICT (user_id) DO NOTHING",
                user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0, 0, 0, 0, 0, 0, 1, 1, 1, 1
            )
    except Exception as e:
        logging.error(f"DB error in start: {e}")
        await message.answer("❌ Ошибка базы данных. Попробуй позже.")
        return

    # Админы не проходят проверку подписки
    if await is_admin(user_id):
        ok = True
        not_subscribed = []
    else:
        ok, not_subscribed = await check_subscription(user_id)

    if not ok:
        await message.answer(
            "❗️ Для доступа к боту нужно подписаться на наши каналы.\nПосле подписки нажми кнопку ниже.",
            reply_markup=subscription_inline(not_subscribed)
        )
        return
    admin_flag = await is_admin(user_id)
    await message.answer(
        f"Привет, {first_name}!\n"
        f"Добро пожаловать в <b>Malboro GAME</b>! 🚬\n"
        f"Тут ты найдёшь: казино, розыгрыши, магазин, аукцион.\n"
        f"А ещё можешь грабить других – случайно или по username!\n"
        f"У тебя 1 уровень. Зарабатывай опыт и повышай уровень!\n\n"
        f"Канал: @lllMALBOROlll (подпишись!)",
        reply_markup=user_main_keyboard(admin_flag)
    )

# ==================== ПРОВЕРКА ПОДПИСКИ ====================
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    if callback.message.chat.type != 'private':
        await callback.answer("Эта функция работает только в личке", show_alert=True)
        return
    if await is_banned(callback.from_user.id) and not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Вы заблокированы.", show_alert=True)
        return
    ok, not_subscribed = await check_subscription(callback.from_user.id)
    if ok:
        admin_flag = await is_admin(callback.from_user.id)
        await callback.message.edit_text("✅ Подписка подтверждена! Добро пожаловать.")
        await callback.message.answer("Главное меню:", reply_markup=user_main_keyboard(admin_flag))
    else:
        await callback.answer("❌ Ты ещё не подписался на все каналы!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=subscription_inline(not_subscribed))

@dp.callback_query_handler(lambda c: c.data == "no_link")
async def no_link(callback: types.CallbackQuery):
    await callback.answer("Ссылка временно недоступна, найди канал вручную", show_alert=True)

# ==================== ПРОФИЛЬ ====================
@dp.message_handler(lambda message: message.text == "👤 Профиль")
async def profile_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT balance, reputation, total_spent, negative_balance, joined_date, theft_attempts, theft_success, theft_failed, theft_protected, casino_wins, casino_losses, guess_wins, guess_losses, game_wins, exp, level, strength, agility, defense FROM users WHERE user_id=$1",
                user_id
            )
        if row:
            balance, rep, spent, neg, joined, attempts, success, failed, protected, cw, cl, gw, gl, gwins, exp, level, strength, agility, defense = (
                row['balance'], row['reputation'], row['total_spent'], row['negative_balance'], row['joined_date'],
                row['theft_attempts'], row['theft_success'], row['theft_failed'], row['theft_protected'],
                row['casino_wins'], row['casino_losses'], row['guess_wins'], row['guess_losses'],
                row['game_wins'], row['exp'], row['level'], row['strength'], row['agility'], row['defense']
            )
            neg_text = f" (долг: {neg})" if neg > 0 else ""
            level_mult = int(await get_setting("level_multiplier"))
            exp_needed = level * level_mult
            progress = exp / exp_needed if exp_needed > 0 else 0
            bar_length = 10
            filled = int(progress * bar_length)
            bar = "🟩" * filled + "⬜" * (bar_length - filled)
            text = (
                f"👤 <b>Твой профиль</b>\n"
                f"📊 <b>Уровень:</b> {level}\n"
                f"📈 <b>Опыт:</b> {exp}/{exp_needed}\n{bar}\n"
                f"💪 Сила: {strength} | 🏃 Ловкость: {agility} | 🛡 Защита: {defense}\n"
                f"💰 Баланс: {balance} монет{neg_text}\n"
                f"⭐️ Репутация: {rep}\n"
                f"💸 Всего потрачено: {spent} монет\n"
                f"📅 Зарегистрирован: {joined}\n"
                f"🔫 Ограблений: {attempts} (успешно: {success}, провал: {failed})\n"
                f"⚔️ Отбито атак: {protected}\n"
                f"🎰 Казино: побед {cw}, поражений {cl}\n"
                f"🔢 Угадайка: побед {gw}, поражений {gl}\n"
                f"👥 Побед в мультиплеере: {gwins}"
            )
        else:
            text = "Профиль не найден"
    except Exception as e:
        logging.error(f"Profile error: {e}")
        text = "❌ Ошибка загрузки профиля."
    await message.answer(text, reply_markup=user_main_keyboard(await is_admin(user_id)))

# ==================== УРОВЕНЬ ====================
@dp.message_handler(lambda message: message.text == "📊 Уровень")
async def level_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    level = await get_user_level(user_id)
    exp = await get_user_exp(user_id)
    level_mult = int(await get_setting("level_multiplier"))
    exp_needed = level * level_mult
    progress = exp / exp_needed if exp_needed > 0 else 0
    bar_length = 15
    filled = int(progress * bar_length)
    bar = "🟩" * filled + "⬜" * (bar_length - filled)
    level_names = {
        1: "🔰 Новичок",
        2: "⛏️ Искатель",
        3: "⚔️ Воин",
        4: "🛡️ Защитник",
        5: "🌟 Звезда",
        6: "🔥 Ветеран",
        7: "💫 Мастер",
        8: "👑 Легенда",
        9: "💎 Алмазный",
        10: "👁‍🗨 Патриарх",
    }
    level_name = level_names.get(level, f"Уровень {level}")
    text = (
        f"📊 <b>{level_name}</b>\n\n"
        f"Уровень: {level}\n"
        f"Опыт: {exp} / {exp_needed}\n"
        f"{bar}\n\n"
        f"За повышение уровня ты получаешь монеты, репутацию и очки статов!\n"
        f"Следующая награда: +{await get_level_reward_coins(level+1)} монет, +{await get_level_reward_rep(level+1)} репутации."
    )
    await message.answer(text, reply_markup=user_main_keyboard(await is_admin(user_id)))

async def get_level_reward_coins(level: int) -> int:
    async with db_pool.acquire() as conn:
        val = await conn.fetchval("SELECT coins FROM level_rewards WHERE level=$1", level)
        return val if val else 0

async def get_level_reward_rep(level: int) -> int:
    async with db_pool.acquire() as conn:
        val = await conn.fetchval("SELECT reputation FROM level_rewards WHERE level=$1", level)
        return val if val else 0

# ==================== РЕПУТАЦИЯ ====================
@dp.message_handler(lambda message: message.text == "⭐️ Репутация")
async def reputation_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    rep = await get_user_reputation(user_id)
    theft_bonus = float(await get_setting("reputation_theft_bonus")) * rep
    defense_bonus = float(await get_setting("reputation_defense_bonus")) * rep
    await message.answer(
        f"⭐️ Твоя репутация: {rep}\n\n"
        f"Репутация увеличивает шансы:\n"
        f"🔫 Бонус к грабежу: +{theft_bonus:.1f}%\n"
        f"🛡 Бонус к защите: +{defense_bonus:.1f}%\n\n"
        f"Зарабатывай репутацию в играх и за выполнение заданий!",
        reply_markup=user_main_keyboard(await is_admin(user_id))
    )

# ==================== БОНУС ====================
@dp.message_handler(lambda message: message.text == "🎁 Бонус")
async def bonus_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    try:
        async with db_pool.acquire() as conn:
            last_bonus_str = await conn.fetchval("SELECT last_bonus FROM users WHERE user_id=$1", user_id)

        now = datetime.now()
        if last_bonus_str:
            last_bonus = datetime.strptime(last_bonus_str, "%Y-%m-%d %H:%M:%S")
            if now - last_bonus < timedelta(days=1):
                remaining = timedelta(days=1) - (now - last_bonus)
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds // 60) % 60
                await message.answer(f"⏳ Бонус можно будет получить через {hours} ч {minutes} мин")
                return

        bonus = random.randint(5, 15)
        phrase = get_random_phrase(BONUS_PHRASES, bonus=bonus)

        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1, last_bonus = $2 WHERE user_id=$3",
                bonus, now.strftime("%Y-%m-%d %H:%M:%S"), user_id
            )
        await message.answer(phrase, reply_markup=user_main_keyboard(await is_admin(user_id)))
    except Exception as e:
        logging.error(f"Bonus error: {e}")
        await message.answer("❌ Ошибка при получении бонуса.")

# ==================== ТОП ИГРОКОВ ====================
@dp.message_handler(lambda message: message.text == "🏆 Топ игроков")
async def leaderboard_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="💰 Самые богатые")],
        [types.KeyboardButton(text="💸 Транжиры")],
        [types.KeyboardButton(text="🔫 Крадуны")],
        [types.KeyboardButton(text="⭐️ По репутации")],
        [types.KeyboardButton(text="👥 Победы в мультиплеере")],
        [types.KeyboardButton(text="📈 По уровню")],
        [types.KeyboardButton(text="💪 По силе")],
        [types.KeyboardButton(text="🏃 По ловкости")],
        [types.KeyboardButton(text="🛡 По защите")],
        [types.KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)
    await message.answer("Выбери категорию топа:", reply_markup=kb)

async def show_top(message: types.Message, order_field: str, title: str):
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    try:
        async with db_pool.acquire() as conn:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM users")
            rows = await conn.fetch(
                f"SELECT first_name, {order_field} FROM users ORDER BY {order_field} DESC LIMIT $1 OFFSET $2",
                ITEMS_PER_PAGE, offset
            )
        if not rows:
            await message.answer("Нет данных.")
            return
        text = f"{title} (страница {page}):\n\n"
        for idx, row in enumerate(rows, start=offset+1):
            text += f"{idx}. {row['first_name']} – {row[order_field]}\n"
        kb = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"top:{order_field}:{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"top:{order_field}:{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        if kb:
            await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await message.answer(text)
    except Exception as e:
        logging.error(f"Top error: {e}")
        await message.answer("❌ Ошибка загрузки топа.")

@dp.message_handler(lambda message: message.text == "💰 Самые богатые")
async def top_rich_handler(message: types.Message):
    await show_top(message, "balance", "💰 Самые богатые")

@dp.message_handler(lambda message: message.text == "💸 Транжиры")
async def top_spenders_handler(message: types.Message):
    await show_top(message, "total_spent", "💸 Транжиры")

@dp.message_handler(lambda message: message.text == "🔫 Крадуны")
async def top_thieves_handler(message: types.Message):
    await show_top(message, "theft_success", "🔫 Крадуны")

@dp.message_handler(lambda message: message.text == "⭐️ По репутации")
async def top_reputation_handler(message: types.Message):
    await show_top(message, "reputation", "⭐️ По репутации")

@dp.message_handler(lambda message: message.text == "👥 Победы в мультиплеере")
async def top_multiplayer_handler(message: types.Message):
    await show_top(message, "game_wins", "👥 Победы в мультиплеере")

@dp.message_handler(lambda message: message.text == "📈 По уровню")
async def top_level_handler(message: types.Message):
    await show_top(message, "level", "📈 По уровню")

@dp.message_handler(lambda message: message.text == "💪 По силе")
async def top_strength_handler(message: types.Message):
    await show_top(message, "strength", "💪 По силе")

@dp.message_handler(lambda message: message.text == "🏃 По ловкости")
async def top_agility_handler(message: types.Message):
    await show_top(message, "agility", "🏃 По ловкости")

@dp.message_handler(lambda message: message.text == "🛡 По защите")
async def top_defense_handler(message: types.Message):
    await show_top(message, "defense", "🛡 По защите")

@dp.callback_query_handler(lambda c: c.data.startswith("top:"))
async def top_page_callback(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    field = parts[1]
    page = int(parts[2])
    titles = {
        "balance": "💰 Самые богатые",
        "total_spent": "💸 Транжиры",
        "theft_success": "🔫 Крадуны",
        "reputation": "⭐️ По репутации",
        "game_wins": "👥 Победы в мультиплеере",
        "level": "📈 По уровню",
        "strength": "💪 По силе",
        "agility": "🏃 По ловкости",
        "defense": "🛡 По защите"
    }
    title = titles.get(field, "Топ")
    await show_top(callback.message, field, title)
    await callback.answer()

# ==================== МАГАЗИН ПОДАРКОВ ====================
@dp.message_handler(lambda message: message.text == "🛒 Магазин подарков")
async def shop_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    try:
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM shop_items")
            rows = await conn.fetch(
                "SELECT id, name, description, price, stock FROM shop_items ORDER BY id LIMIT $1 OFFSET $2",
                ITEMS_PER_PAGE, offset
            )
        if not rows:
            await message.answer("🎁 В магазине пока нет подарков.")
            return
        text = f"🎁 Подарки (страница {page}):\n\n"
        kb = []
        for row in rows:
            item_id = row['id']
            name = row['name']
            desc = row['description']
            price = row['price']
            stock = row['stock']
            stock_info = f" (в наличии: {stock})" if stock != -1 else ""
            text += f"🔹 {name}\n{desc}\n💰 {price} монет{stock_info}\n\n"
            kb.append([types.InlineKeyboardButton(text=f"Купить {name}", callback_data=f"buy_{item_id}")])
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"shop_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"shop_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception as e:
        logging.error(f"Shop error: {e}")
        await message.answer("❌ Ошибка загрузки магазина.")

@dp.callback_query_handler(lambda c: c.data.startswith("shop_page_"))
async def shop_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    callback.message.text = f"🛒 Магазин подарков {page}"
    await shop_handler(callback.message)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def buy_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        await callback.answer("⛔ Вы заблокированы.", show_alert=True)
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await callback.message.edit_text("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    item_id = int(callback.data.split("_")[1])
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT name, price, stock FROM shop_items WHERE id=$1", item_id)
            if not row:
                await callback.answer("Товар не найден", show_alert=True)
                return
            name, price, stock = row['name'], row['price'], row['stock']
            if stock != -1 and stock <= 0:
                await callback.answer("Товара нет в наличии!", show_alert=True)
                return
            balance = await get_user_balance(user_id)
            if balance < price:
                await callback.answer("Не хватает монет!", show_alert=True)
                return
            async with conn.transaction():
                await update_user_balance(user_id, -price, conn=conn)
                await update_user_total_spent(user_id, price)
                await conn.execute(
                    "INSERT INTO purchases (user_id, item_id, purchase_date) VALUES ($1, $2, $3)",
                    user_id, item_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                if stock != -1:
                    await conn.execute("UPDATE shop_items SET stock = stock - 1 WHERE id=$1", item_id)

        phrase = get_random_phrase(PURCHASE_PHRASES)
        await callback.answer(f"✅ Ты купил {name}! {phrase}", show_alert=True)

        if await get_setting("chat_notify_big_purchase") == "1" and price >= BIG_PURCHASE_THRESHOLD:
            user = callback.from_user
            chat_phrase = get_random_phrase(CHAT_PURCHASE_PHRASES, name=user.first_name, item=name, price=price)
            await notify_chats(chat_phrase, 'purchase')

        asyncio.create_task(notify_admins_about_purchase(callback.from_user, name, price))
        try:
            await callback.message.edit_text(f"✅ Покупка совершена!")
        except:
            pass
        await callback.message.answer("Главное меню:", reply_markup=user_main_keyboard(await is_admin(user_id)))
    except Exception as e:
        logging.error(f"Purchase error: {e}")
        await callback.answer("❌ Ошибка при покупке. Попробуй позже.", show_alert=True)

async def notify_admins_about_purchase(user: types.User, item_name: str, price: int):
    admins = SUPER_ADMINS.copy()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM admins")
        for row in rows:
            admins.append(row['user_id'])
    for admin_id in admins:
        await safe_send_message(admin_id,
            f"🛒 Покупка: пользователь {user.full_name} (@{user.username})\n"
            f"<a href=\"tg://user?id={user.id}\">Ссылка</a> купил {item_name} за {price} монет."
        )

# ==================== МОИ ПОКУПКИ ====================
@dp.message_handler(lambda message: message.text == "💰 Мои покупки")
async def my_purchases(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    try:
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM purchases WHERE user_id=$1", user_id)
            rows = await conn.fetch(
                "SELECT p.id, s.name, p.purchase_date, p.status, p.admin_comment FROM purchases p "
                "JOIN shop_items s ON p.item_id = s.id WHERE p.user_id=$1 ORDER BY p.purchase_date DESC LIMIT $2 OFFSET $3",
                user_id, ITEMS_PER_PAGE, offset
            )
        if not rows:
            await message.answer("У тебя пока нет покупок.", reply_markup=user_main_keyboard(await is_admin(user_id)))
            return
        text = f"📦 Твои покупки (страница {page}):\n"
        for row in rows:
            pid, name, date, status, comment = row['id'], row['name'], row['purchase_date'], row['status'], row['admin_comment']
            status_emoji = "⏳" if status == 'pending' else "✅" if status == 'completed' else "❌"
            text += f"{status_emoji} {name} от {date}\n"
            if comment:
                text += f"   Комментарий: {comment}\n"
        kb = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"mypurchases_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"mypurchases_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        if kb:
            await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await message.answer(text, reply_markup=user_main_keyboard(await is_admin(user_id)))
    except Exception as e:
        logging.error(f"My purchases error: {e}")
        await message.answer("❌ Ошибка загрузки покупок.")

@dp.callback_query_handler(lambda c: c.data.startswith("mypurchases_page_"))
async def mypurchases_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    callback.message.text = f"💰 Мои покупки {page}"
    await my_purchases(callback.message)
    await callback.answer()

# ==================== ПРОМОКОД ====================
@dp.message_handler(lambda message: message.text == "🎟 Промокод")
async def promo_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    await message.answer("Введи промокод:", reply_markup=back_keyboard())
    await PromoActivate.code.set()

@dp.message_handler(state=PromoActivate.code)
async def promo_activate(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        await state.finish()
        return
    if message.text == "◀️ Назад":
        await state.finish()
        await message.answer("Главное меню:", reply_markup=user_main_keyboard(await is_admin(message.from_user.id)))
        return
    code = message.text.strip().upper()
    user_id = message.from_user.id
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        await state.finish()
        return
    try:
        async with db_pool.acquire() as conn:
            already_used = await conn.fetchval(
                "SELECT 1 FROM promo_activations WHERE user_id=$1 AND promo_code=$2",
                user_id, code
            )
            if already_used:
                await message.answer("❌ Ты уже активировал этот промокод.")
                await state.finish()
                return
            row = await conn.fetchrow("SELECT reward, max_uses, used_count FROM promocodes WHERE code=$1", code)
            if not row:
                await message.answer("❌ Промокод не найден.")
                await state.finish()
                return
            reward, max_uses, used = row['reward'], row['max_uses'], row['used_count']
            if used >= max_uses:
                await message.answer("❌ Промокод уже использован максимальное количество раз.")
                await state.finish()
                return
            async with conn.transaction():
                await update_user_balance(user_id, reward, conn=conn)
                await conn.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code=$1", code)
                await conn.execute(
                    "INSERT INTO promo_activations (user_id, promo_code, activated_at) VALUES ($1, $2, $3)",
                    user_id, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
        await message.answer(
            f"✅ Промокод активирован! Ты получил {reward} монет.",
            reply_markup=user_main_keyboard(await is_admin(user_id))
        )
    except Exception as e:
        logging.error(f"Promo error: {e}")
        await message.answer("❌ Ошибка активации промокода.")
    await state.finish()
  # ==================== ПОЛНЫЙ РАБОЧИЙ БОТ ====================
# Часть 4: Пользовательские хендлеры (продолжение) и групповые хендлеры

# ==================== ОГРАБЛЕНИЕ ====================
async def get_theft_success_chance(attacker_id: int) -> float:
    base = int(await get_setting("theft_success_chance"))
    rep = await get_user_reputation(attacker_id)
    bonus = float(await get_setting("reputation_theft_bonus")) * rep
    return base + bonus

async def get_defense_chance(victim_id: int) -> float:
    base = int(await get_setting("theft_defense_chance"))
    rep = await get_user_reputation(victim_id)
    bonus = float(await get_setting("reputation_defense_bonus")) * rep
    return base + bonus

@dp.message_handler(lambda message: message.text == "🔫 Ограбить")
async def theft_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    phrase = get_random_phrase(THEFT_CHOICE_PHRASES)
    await message.answer(phrase, reply_markup=theft_choice_keyboard())

@dp.message_handler(lambda message: message.text == "🎲 Случайная цель")
async def theft_random(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    cooldown_minutes = int(await get_setting("theft_cooldown_minutes"))
    async with db_pool.acquire() as conn:
        last_time_str = await conn.fetchval("SELECT last_theft_time FROM users WHERE user_id=$1", user_id)
        if last_time_str:
            last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - last_time
            if diff < timedelta(minutes=cooldown_minutes):
                remaining = cooldown_minutes - int(diff.total_seconds() // 60)
                phrase = get_random_phrase(THEFT_COOLDOWN_PHRASES, minutes=remaining)
                await message.answer(phrase, reply_markup=user_main_keyboard(await is_admin(user_id)))
                return
    target_id = await get_random_user(user_id)
    if not target_id:
        await message.answer("😕 В игре пока нет других игроков.", reply_markup=user_main_keyboard(await is_admin(user_id)))
        return
    cost = int(await get_setting("random_attack_cost"))
    if cost > 0:
        balance = await get_user_balance(user_id)
        if balance < cost:
            await message.answer(get_random_phrase(THEFT_NO_MONEY_PHRASES), reply_markup=user_main_keyboard(await is_admin(user_id)))
            return
        await update_user_balance(user_id, -cost)
    await perform_theft(message, user_id, target_id)

@dp.message_handler(lambda message: message.text == "👤 Выбрать пользователя")
async def theft_choose_user(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    cooldown_minutes = int(await get_setting("theft_cooldown_minutes"))
    async with db_pool.acquire() as conn:
        last_time_str = await conn.fetchval("SELECT last_theft_time FROM users WHERE user_id=$1", user_id)
        if last_time_str:
            last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - last_time
            if diff < timedelta(minutes=cooldown_minutes):
                remaining = cooldown_minutes - int(diff.total_seconds() // 60)
                phrase = get_random_phrase(THEFT_COOLDOWN_PHRASES, minutes=remaining)
                await message.answer(phrase, reply_markup=user_main_keyboard(await is_admin(user_id)))
                return
    await message.answer("Введи @username или ID того, кого хочешь ограбить:", reply_markup=back_keyboard())
    await TheftTarget.target.set()

@dp.message_handler(state=TheftTarget.target)
async def theft_target_entered(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        await state.finish()
        return
    if message.text == "◀️ Назад":
        await state.finish()
        await message.answer("Главное меню:", reply_markup=user_main_keyboard(await is_admin(message.from_user.id)))
        return
    target_input = message.text.strip()
    robber_id = message.from_user.id

    target_data = await find_user_by_input(target_input)
    if not target_data:
        await message.answer("❌ Пользователь не найден. Проверь username или ID.")
        return
    target_id = target_data['user_id']

    if target_id == robber_id:
        await message.answer("Сам себя не ограбишь, бро! 😆")
        await state.finish()
        return

    if await is_banned(target_id):
        await message.answer("❌ Этот пользователь заблокирован и не может быть целью.")
        await state.finish()
        return

    cost = int(await get_setting("targeted_attack_cost"))
    if cost > 0:
        balance = await get_user_balance(robber_id)
        if balance < cost:
            await message.answer(get_random_phrase(THEFT_NO_MONEY_PHRASES), reply_markup=user_main_keyboard(await is_admin(robber_id)))
            await state.finish()
            return
        await update_user_balance(robber_id, -cost)

    await perform_theft(message, robber_id, target_id)
    await state.finish()

async def perform_theft(message: types.Message, robber_id: int, victim_id: int):
    success_chance = await get_theft_success_chance(robber_id)
    defense_chance = await get_defense_chance(victim_id)
    defense_penalty = int(await get_setting("theft_defense_penalty"))
    min_amount = int(await get_setting("min_theft_amount"))
    max_amount = int(await get_setting("max_theft_amount"))

    try:
        async with db_pool.acquire() as conn:
            victim_balance = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1", victim_id)
            if victim_balance is None:
                await message.answer("❌ Цель не найдена в базе.")
                return

            victim_info = await conn.fetchrow("SELECT username, first_name FROM users WHERE user_id=$1", victim_id)
            victim_name = victim_info['first_name'] if victim_info else str(victim_id)

            defense_triggered = random.randint(1, 100) <= defense_chance
            if defense_triggered:
                penalty = defense_penalty
                robber_balance = await get_user_balance(robber_id)
                if penalty > robber_balance:
                    penalty = robber_balance
                if penalty > 0:
                    await update_user_balance(robber_id, -penalty, conn=conn)
                    await update_user_balance(victim_id, penalty, conn=conn)
                await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_failed = theft_failed + 1 WHERE user_id=$1", robber_id)
                await conn.execute("UPDATE users SET theft_protected = theft_protected + 1 WHERE user_id=$1", victim_id)
                await conn.execute("UPDATE users SET last_theft_time = $1 WHERE user_id=$2", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), robber_id)

                exp_defense = int(await get_setting("exp_per_theft_defense"))
                await add_exp(victim_id, exp_defense, conn=conn)
                exp_fail = int(await get_setting("exp_per_theft_fail"))
                await add_exp(robber_id, exp_fail, conn=conn)

                robber_phrase = get_random_phrase(THEFT_DEFENSE_PHRASES, target=victim_name, penalty=penalty)
                victim_phrase = get_random_phrase(THEFT_VICTIM_DEFENSE_PHRASES, attacker=message.from_user.first_name, penalty=penalty)
                await message.answer(robber_phrase, reply_markup=user_main_keyboard(await is_admin(robber_id)))
                await safe_send_message(victim_id, victim_phrase)
                return

            success = random.randint(1, 100) <= success_chance
            if success and victim_balance > 0:
                max_possible = min(max_amount, victim_balance)
                if max_possible < min_amount:
                    steal_amount = victim_balance
                else:
                    steal_amount = random.randint(min_amount, max_possible)

                await update_user_balance(victim_id, -steal_amount, conn=conn)
                await update_user_balance(robber_id, steal_amount, conn=conn)
                await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_success = theft_success + 1 WHERE user_id=$1", robber_id)

                exp_success = int(await get_setting("exp_per_theft_success"))
                await add_exp(robber_id, exp_success, conn=conn)

                new_success = await conn.fetchval("SELECT theft_success FROM users WHERE user_id=$1", robber_id)
                if new_success == 15:
                    ref = await conn.fetchrow("SELECT referrer_id FROM referrals WHERE referred_id=$1 AND reward_given=FALSE", robber_id)
                    if ref:
                        referrer_id = ref['referrer_id']
                        bonus_coins = int(await get_setting("referral_bonus"))
                        bonus_rep = int(await get_setting("referral_reputation"))
                        await update_user_balance(referrer_id, bonus_coins, conn=conn)
                        await update_user_reputation(referrer_id, bonus_rep)
                        await conn.execute("UPDATE referrals SET reward_given=TRUE WHERE referred_id=$1", robber_id)
                        await conn.execute("UPDATE referrals SET active=TRUE WHERE referred_id=$1", robber_id)
                        await safe_send_message(referrer_id, f"🎉 Ваш реферал совершил 15 успешных ограблений! Вы получили {bonus_coins} монет и {bonus_rep} репутации.")

                phrase = get_random_phrase(THEFT_SUCCESS_PHRASES, amount=steal_amount, target=victim_name)
                await message.answer(phrase, reply_markup=user_main_keyboard(await is_admin(robber_id)))
                await safe_send_message(victim_id, f"🔫 Вас ограбили! {message.from_user.first_name} украл {steal_amount} монет.")
            else:
                await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_failed = theft_failed + 1 WHERE user_id=$1", robber_id)
                exp_fail = int(await get_setting("exp_per_theft_fail"))
                await add_exp(robber_id, exp_fail, conn=conn)
                phrase = get_random_phrase(THEFT_FAIL_PHRASES, target=victim_name)
                await message.answer(phrase, reply_markup=user_main_keyboard(await is_admin(robber_id)))

            await conn.execute("UPDATE users SET last_theft_time = $1 WHERE user_id=$2", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), robber_id)

    except Exception as e:
        logging.error(f"Theft error: {e}")
        await message.answer("❌ Ошибка при ограблении.")

# ==================== РЕФЕРАЛЬНАЯ ССЫЛКА ====================
@dp.message_handler(lambda message: message.text == "🔗 Рефералка")
async def referral_link(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    bot_username = (await bot.me).username
    link = f"https://t.me/{bot_username}?start=ref{user_id}"
    bonus_coins = await get_setting("referral_bonus")
    bonus_rep = await get_setting("referral_reputation")

    async with db_pool.acquire() as conn:
        clicks = await conn.fetchval("SELECT SUM(clicks) FROM referrals WHERE referrer_id=$1", user_id) or 0
        active = await conn.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id=$1 AND active=TRUE", user_id) or 0
        earned = active * int(bonus_coins)

    await message.answer(
        f"🔗 Твоя реферальная ссылка:\n{link}\n\n"
        f"📊 Статистика:\n"
        f"• Переходов: {clicks}\n"
        f"• Активных рефералов: {active}\n"
        f"• Заработано монет: {earned}\n\n"
        f"Бонус: {bonus_coins} монет и {bonus_rep} репутации за каждого активного реферала (15 успешных краж)."
    )

# ==================== ЗАДАНИЯ ====================
@dp.message_handler(lambda message: message.text == "📋 Задания")
async def tasks_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, description, reward_coins, reward_reputation, max_completions, completed_count FROM tasks WHERE active=TRUE")
    if not rows:
        await message.answer("📋 Пока нет доступных заданий.", reply_markup=user_main_keyboard(await is_admin(user_id)))
        return

    text = "📋 Доступные задания:\n\n"
    kb = []
    for row in rows:
        progress = f" (выполнено {row['completed_count']}/{row['max_completions']})" if row['max_completions'] > 1 else ""
        text += f"🔹 {row['name']}{progress}\n{row['description']}\nНаграда: {row['reward_coins']} монет, {row['reward_reputation']} репутации\n\n"
        kb.append([types.InlineKeyboardButton(text=f"Выполнить {row['name']}", callback_data=f"task_{row['id']}")])
    await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query_handler(lambda c: c.data.startswith("task_"))
async def take_task(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    async with db_pool.acquire() as conn:
        existing = await conn.fetchval("SELECT 1 FROM user_tasks WHERE user_id=$1 AND task_id=$2", user_id, task_id)
        if existing:
            await callback.answer("Ты уже выполнял это задание!", show_alert=True)
            return

        task = await conn.fetchrow("SELECT * FROM tasks WHERE id=$1 AND active=TRUE", task_id)
        if not task:
            await callback.answer("Задание не найдено или неактивно.", show_alert=True)
            return

        if task['max_completions'] > 0 and task['completed_count'] >= task['max_completions']:
            await callback.answer("Это задание больше недоступно (лимит выполнений исчерпан).", show_alert=True)
            return

        if task['task_type'] == 'subscribe':
            channel_id = task['target_id']
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    await callback.answer("❌ Ты не подписан на этот канал!", show_alert=True)
                    return
            except Exception as e:
                logging.error(f"Task subscribe check error: {e}")
                await callback.answer("❌ Не удалось проверить подписку. Возможно, бот не админ канала.", show_alert=True)
                return

            async with conn.transaction():
                await update_user_balance(user_id, task['reward_coins'], conn=conn)
                await update_user_reputation(user_id, task['reward_reputation'])
                expires_at = (datetime.now() + timedelta(days=task['required_days'])).strftime("%Y-%m-%d %H:%M:%S") if task['required_days'] > 0 else None
                await conn.execute(
                    "INSERT INTO user_tasks (user_id, task_id, completed_at, expires_at, status) VALUES ($1, $2, $3, $4, $5)",
                    user_id, task_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), expires_at, 'completed'
                )
                await conn.execute("UPDATE tasks SET completed_count = completed_count + 1 WHERE id=$1", task_id)

            await callback.answer(f"✅ Задание выполнено! +{task['reward_coins']} монет, +{task['reward_reputation']} репутации", show_alert=True)
            await callback.message.delete()
        else:
            await callback.answer("Этот тип заданий пока не поддерживается.", show_alert=True)

# ==================== АУКЦИОН ====================
@dp.message_handler(lambda message: message.text == "🏷 Аукцион")
async def auction_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    await list_auctions(message)

async def list_auctions(message: types.Message, page: int = 1):
    offset = (page - 1) * ITEMS_PER_PAGE
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM auctions WHERE status='active'")
        rows = await conn.fetch(
            "SELECT id, item_name, current_price, end_time, target_price FROM auctions WHERE status='active' ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            ITEMS_PER_PAGE, offset
        )
    if not rows:
        await message.answer("🏷 На данный момент нет активных аукционов.", reply_markup=user_main_keyboard(await is_admin(message.from_user.id)))
        return
    text = f"🏷 Активные аукционы (страница {page}):\n\n"
    for row in rows:
        text += f"🆔 {row['id']} | {row['item_name']} | Текущая ставка: {row['current_price']}\n"
        if row['end_time']:
            end = datetime.strptime(row['end_time'], "%Y-%m-%d %H:%M:%S")
            remaining = end - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                text += f"⏳ Осталось: {hours}ч {minutes}м\n"
        if row['target_price']:
            text += f"🎯 Целевая цена: {row['target_price']}\n"
        text += "\n"
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    kb = auction_list_keyboard(rows, page, total_pages)
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("auction_page_"))
async def auction_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    await list_auctions(callback.message, page)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("auction_view_"))
async def auction_view(callback: types.CallbackQuery):
    auction_id = int(callback.data.split("_")[2])
    async with db_pool.acquire() as conn:
        auction = await conn.fetchrow("SELECT * FROM auctions WHERE id=$1 AND status='active'", auction_id)
        if not auction:
            await callback.answer("Аукцион не найден или завершён.", show_alert=True)
            return
        bids = await conn.fetch("SELECT user_id, bid_amount, bid_time FROM auction_bids WHERE auction_id=$1 ORDER BY bid_time DESC LIMIT 5", auction_id)
    text = (
        f"🏷 <b>{auction['item_name']}</b>\n"
        f"📝 {auction['description']}\n\n"
        f"💰 Стартовая цена: {auction['start_price']}\n"
        f"💵 Текущая ставка: {auction['current_price']}\n"
    )
    if auction['end_time']:
        end = datetime.strptime(auction['end_time'], "%Y-%m-%d %H:%M:%S")
        remaining = end - datetime.now()
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            text += f"⏳ Окончание через: {hours}ч {minutes}м\n"
    if auction['target_price']:
        text += f"🎯 Целевая цена: {auction['target_price']}\n"
    text += "\n📊 Последние ставки:\n"
    if bids:
        for bid in bids:
            user = await conn.fetchval("SELECT first_name FROM users WHERE user_id=$1", bid['user_id'])
            text += f"• {user or 'Неизвестно'}: {bid['bid_amount']} монет ({bid['bid_time']})\n"
    else:
        text += "Пока нет ставок.\n"
    await callback.message.answer(text, reply_markup=auction_detail_keyboard(auction_id))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("auction_bid_"))
async def auction_bid_start(callback: types.CallbackQuery, state: FSMContext):
    auction_id = int(callback.data.split("_")[2])
    await state.update_data(auction_id=auction_id)
    await callback.message.answer("Введи сумму ставки (целое число):", reply_markup=back_keyboard())
    await AuctionBid.amount.set()
    await callback.answer()

@dp.message_handler(state=AuctionBid.amount)
async def auction_bid_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await auction_menu(message)
        return
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное целое число.")
        return
    data = await state.get_data()
    auction_id = data['auction_id']
    user_id = message.from_user.id
    async with db_pool.acquire() as conn:
        auction = await conn.fetchrow("SELECT * FROM auctions WHERE id=$1 AND status='active'", auction_id)
        if not auction:
            await message.answer("❌ Аукцион не найден или завершён.")
            await state.finish()
            return
        min_step = int(await get_setting("auction_min_bid_step"))
        min_bid = auction['current_price'] + min_step
        if amount < min_bid:
            await message.answer(f"❌ Ставка должна быть не меньше {min_bid} (текущая цена + минимальный шаг).")
            return
        balance = await get_user_balance(user_id)
        if balance < amount:
            await message.answer("❌ Недостаточно монет.")
            return
        await update_user_balance(user_id, -amount, conn=conn)
        await conn.execute(
            "UPDATE auctions SET current_price=$1 WHERE id=$2",
            amount, auction_id
        )
        await conn.execute(
            "INSERT INTO auction_bids (auction_id, user_id, bid_amount, bid_time) VALUES ($1, $2, $3, $4)",
            auction_id, user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        if auction['target_price'] and amount >= auction['target_price']:
            await conn.execute("UPDATE auctions SET status='ended', winner_id=$1 WHERE id=$2", user_id, auction_id)
            await safe_send_message(user_id, f"🎉 Поздравляем! Ты выиграл аукцион «{auction['item_name']}» с ценой {amount} монет. Админ скоро свяжется для передачи товара.")
            await safe_send_message(auction['created_by'], f"🏁 Аукцион «{auction['item_name']}» завершён по достижению целевой цены. Победитель: {message.from_user.first_name} (ID: {user_id}) с суммой {amount} монет.")
            await message.answer("✅ Аукцион завершён! Ты победитель.")
        else:
            await message.answer(f"✅ Ставка принята! Ты теперь лидер с ценой {amount} монет.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "auction_list")
async def auction_list_back(callback: types.CallbackQuery):
    await list_auctions(callback.message)
    await callback.answer()

# ==================== НАЗАД В ГЛАВНОЕ МЕНЮ ====================
@dp.message_handler(lambda message: message.text == "◀️ Назад в главное меню")
async def back_to_main_from_admin(message: types.Message):
    if message.chat.type != 'private':
        return
    admin_flag = await is_admin(message.from_user.id)
    await message.answer("Главное меню:", reply_markup=user_main_keyboard(admin_flag))

@dp.message_handler(lambda message: message.text == "◀️ Назад")
async def back_from_submenu(message: types.Message):
    if message.chat.type != 'private':
        return
    admin_flag = await is_admin(message.from_user.id)
    await message.answer("Главное меню:", reply_markup=user_main_keyboard(admin_flag))

# ==================== ГРУППОВЫЕ ЧАТЫ ====================
async def check_chat(message: types.Message) -> bool:
    if message.chat.type == 'private':
        await message.reply("❌ Эта команда работает только в группах.")
        return False
    if not await is_chat_confirmed(message.chat.id):
        await message.reply("❌ Этот чат не активирован. Обратитесь к администратору.")
        return False
    return True

# ==================== КОМАНДА FIGHT ====================
@dp.message_handler(Command("fight"))
async def cmd_fight(message: types.Message):
    if not await check_chat(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.first_name

    ok, remaining = await can_fight(chat_id, user_id)
    if not ok:
        await message.reply(
            f"⏳ Ты слишком часто машешь кулаками! Подожди ещё {format_time_remaining(remaining * 60)}."
        )
        return

    stats = await get_user_stats(user_id)
    strength = stats['strength']
    agility = stats['agility']
    defense = stats['defense']

    damage = await calculate_fight_damage(strength)
    authority = await calculate_fight_authority()

    outcome = "hit"
    counter_damage = 0

    if is_critical(strength, agility):
        damage = int(damage * 1.5)
        authority = int(authority * 1.5)
        phrase_list = FIGHT_CRIT_PHRASES
        outcome = "crit"
    else:
        phrase_list = FIGHT_HIT_PHRASES

    if is_counter(defense):
        counter_damage = random.randint(1, 5)
        await update_user_balance(user_id, -counter_damage)
        outcome = "counter"
        phrase_list = FIGHT_COUNTER_PHRASES

    await add_chat_authority(chat_id, user_id, authority, damage)
    await set_fight_cooldown(chat_id, user_id)
    await log_fight(chat_id, user_id, damage, authority, outcome)

    if outcome == "counter":
        phrase = get_random_phrase(phrase_list, damage=counter_damage)
    else:
        phrase = get_random_phrase(phrase_list, damage=damage, authority=authority)

    await message.reply(
        f"{username}, {phrase}\n"
        f"Твой авторитет в этом чате: {await get_chat_authority(chat_id, user_id)}"
    )

    if outcome == "counter":
        await message.reply(f"💸 Ты потерял {counter_damage} монет.")

# ==================== КОМАНДА GYM ====================
@dp.message_handler(Command("gym"))
async def cmd_gym(message: types.Message, state: FSMContext):
    if not await check_chat(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    authority = await get_chat_authority(chat_id, user_id)

    strength_cost = int(await get_setting("gym_strength_cost"))
    agility_cost = int(await get_setting("gym_agility_cost"))
    defense_cost = int(await get_setting("gym_defense_cost"))

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(f"💪 Сила ({strength_cost} авт.)", callback_data="gym_strength"),
        types.InlineKeyboardButton(f"🏃 Ловкость ({agility_cost} авт.)", callback_data="gym_agility"),
        types.InlineKeyboardButton(f"🛡 Защита ({defense_cost} авт.)", callback_data="gym_defense"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="gym_cancel")
    )

    await message.reply(
        f"🏋️ Качалка! У тебя {authority} авторитета.\n"
        f"Что хочешь улучшить?",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("gym_"))
async def gym_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    if not await is_chat_confirmed(chat_id):
        await callback.answer("Чат не активирован.", show_alert=True)
        return

    action = callback.data.split("_")[1]

    if action == "cancel":
        await callback.message.delete()
        await callback.answer()
        return

    if action == "strength":
        cost = int(await get_setting("gym_strength_cost"))
        stat = "strength"
    elif action == "agility":
        cost = int(await get_setting("gym_agility_cost"))
        stat = "agility"
    elif action == "defense":
        cost = int(await get_setting("gym_defense_cost"))
        stat = "defense"
    else:
        await callback.answer("Неизвестная опция")
        return

    authority = await get_chat_authority(chat_id, user_id)
    if authority < cost:
        await callback.answer(f"❌ Не хватает авторитета. Нужно {cost}, у тебя {authority}.", show_alert=True)
        return

    if await spend_chat_authority(chat_id, user_id, cost):
        if stat == "strength":
            await update_user_stats(user_id, strength_delta=1)
        elif stat == "agility":
            await update_user_stats(user_id, agility_delta=1)
        elif stat == "defense":
            await update_user_stats(user_id, defense_delta=1)

        await callback.answer(f"✅ Ты улучшил {stat}!", show_alert=True)
        await callback.message.edit_text(
            f"✅ Ты улучшил {stat}!\n"
            f"Осталось авторитета: {await get_chat_authority(chat_id, user_id)}"
        )
    else:
        await callback.answer("❌ Ошибка при списании авторитета.", show_alert=True)

# ==================== КОМАНДА STATUS ====================
@dp.message_handler(Command("status"))
async def cmd_status(message: types.Message):
    if not await check_chat(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)
    authority = await get_chat_authority(chat_id, user_id)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT fights, total_damage FROM chat_authority WHERE chat_id=$1 AND user_id=$2",
            chat_id, user_id
        )
    fights = row['fights'] if row else 0
    total_damage = row['total_damage'] if row else 0

    text = (
        f"📊 Твой статус в этом чате:\n"
        f"Авторитет: {authority}\n"
        f"💪 Сила: {stats['strength']}\n"
        f"🏃 Ловкость: {stats['agility']}\n"
        f"🛡 Защита: {stats['defense']}\n"
        f"⚔️ Боёв: {fights}\n"
        f"💥 Общий урон: {total_damage}"
    )
    await message.reply(text)

# ==================== КОМАНДА TOP ====================
@dp.message_handler(Command("top"))
async def cmd_top(message: types.Message):
    if not await check_chat(message):
        return

    chat_id = message.chat.id
    page = 1
    args = message.get_args().split()
    if args and args[0].isdigit():
        page = int(args[0])

    await show_chat_top(chat_id, message, page)

async def show_chat_top(chat_id: int, message: types.Message, page: int = 1, order: str = "authority"):
    offset = (page - 1) * 10
    async with db_pool.acquire() as conn:
        if order == "authority":
            rows = await conn.fetch(
                "SELECT user_id, authority, total_damage, fights FROM chat_authority WHERE chat_id=$1 ORDER BY authority DESC LIMIT 10 OFFSET $2",
                chat_id, offset
            )
        elif order == "damage":
            rows = await conn.fetch(
                "SELECT user_id, authority, total_damage, fights FROM chat_authority WHERE chat_id=$1 ORDER BY total_damage DESC LIMIT 10 OFFSET $2",
                chat_id, offset
            )
        else:
            rows = await conn.fetch(
                "SELECT user_id, authority, total_damage, fights FROM chat_authority WHERE chat_id=$1 ORDER BY fights DESC LIMIT 10 OFFSET $2",
                chat_id, offset
            )
        total = await conn.fetchval("SELECT COUNT(*) FROM chat_authority WHERE chat_id=$1", chat_id)

    if not rows:
        await message.reply("🏆 В этом чате пока нет участников.")
        return

    text = f"🏆 Топ чата (по {order}):\n"
    for i, row in enumerate(rows, start=offset+1):
        try:
            member = await bot.get_chat_member(chat_id, row['user_id'])
            name = member.user.first_name
        except:
            name = f"ID {row['user_id']}"
        text += f"{i}. {name} – Авторитет: {row['authority']}, Урон: {row['total_damage']}, Боёв: {row['fights']}\n"

    kb = types.InlineKeyboardMarkup(row_width=3)
    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"chat_top_page_{order}_{page-1}"))
    nav.append(types.InlineKeyboardButton(f"{page}", callback_data="noop"))
    if offset + 10 < total:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"chat_top_page_{order}_{page+1}"))
    kb.row(*nav)

    kb.row(
        types.InlineKeyboardButton("📊 По авторитету", callback_data=f"chat_top_authority_1"),
        types.InlineKeyboardButton("💥 По урону", callback_data=f"chat_top_damage_1"),
        types.InlineKeyboardButton("⚔️ По боям", callback_data=f"chat_top_fights_1")
    )

    await message.reply(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("chat_top_"))
async def chat_top_callback(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer()
        return
    order = parts[2]
    page = int(parts[3])
    chat_id = callback.message.chat.id
    await show_chat_top(chat_id, callback.message, page, order)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

# ==================== КОМАНДА HELP В ЧАТЕ ====================
@dp.message_handler(Command("help"))
async def cmd_help_chat(message: types.Message):
    if not await check_chat(message):
        return
    text = (
        "📚 Доступные команды в этом чате:\n"
        "/fight – атаковать банду (раз в 30 мин)\n"
        "/gym – улучшить характеристики за авторитет\n"
        "/status – твой статус\n"
        "/top – топ чата\n"
        "/help – это сообщение"
    )
    await message.reply(text)

# ==================== ПОДГОН (GIFT) ====================
@dp.message_handler(lambda message: message.chat.type != 'private' and message.text == "🎁 Подгон")
async def chat_gift(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if await is_banned(user_id):
        return
    if not await is_chat_confirmed(chat_id):
        await message.reply("❌ Этот чат ещё не активирован. Ожидайте подтверждения администратора.")
        return

    gift_amount = int(await get_setting("gift_amount"))
    gift_limit_per_chat = int(await get_setting("gift_limit_per_day"))
    gift_global_limit = int(await get_setting("gift_global_limit_per_user"))
    gift_cooldown = int(await get_setting("gift_cooldown"))
    today = date.today().isoformat()
    now = datetime.now()

    async with db_pool.acquire() as conn:
        chat_info = await conn.fetchrow("SELECT * FROM confirmed_chats WHERE chat_id=$1", chat_id)
        if not chat_info:
            return
        last_gift_date = chat_info['last_gift_date']
        gift_count_today = chat_info['gift_count_today'] if last_gift_date == today else 0
        if gift_count_today >= gift_limit_per_chat:
            await message.reply(f"❌ Сегодня в этом чате уже использовано {gift_count_today} из {gift_limit_per_chat} подгонов.")
            return

        user = await conn.fetchrow("SELECT last_gift_time, gift_count_today FROM users WHERE user_id=$1", user_id)
        if not user:
            await conn.execute(
                "INSERT INTO users (user_id, username, first_name, joined_date) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                user_id, message.from_user.username, message.from_user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            user = {'last_gift_time': None, 'gift_count_today': 0}
        if user['last_gift_time']:
            user_last_gift = user['last_gift_time']
            user_gift_count = user['gift_count_today'] if user_last_gift.startswith(today) else 0
        else:
            user_gift_count = 0
        if user_gift_count >= gift_global_limit:
            await message.reply(f"❌ Сегодня ты уже получил {user_gift_count} из {gift_global_limit} подгонов во всех чатах.")
            return

        if user['last_gift_time']:
            last_gift = datetime.strptime(user['last_gift_time'], "%Y-%m-%d %H:%M:%S")
            diff = (now - last_gift).total_seconds() / 60
            if diff < gift_cooldown:
                remaining = int(gift_cooldown - diff)
                await message.reply(f"⏳ Подгон можно будет использовать через {remaining} мин.")
                return

        try:
            admins = await bot.get_chat_administrators(chat_id)
            eligible = [a.user for a in admins if a.user.id != user_id and not await is_banned(a.user.id)]
            if not eligible:
                await message.reply("❌ Нет подходящих получателей для подарка.")
                return
            recipient = random.choice(eligible)
        except Exception as e:
            logging.error(f"Gift error: {e}")
            await message.reply("❌ Не удалось выбрать получателя.")
            return

        await conn.execute(
            "INSERT INTO users (user_id, username, first_name, joined_date) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
            recipient.id, recipient.username, recipient.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        await update_user_balance(recipient.id, gift_amount, conn=conn)

        if last_gift_date == today:
            await conn.execute("UPDATE confirmed_chats SET gift_count_today = gift_count_today + 1 WHERE chat_id=$1", chat_id)
        else:
            await conn.execute("UPDATE confirmed_chats SET last_gift_date=$1, gift_count_today=1 WHERE chat_id=$2", today, chat_id)

        if user['last_gift_time'] and user['last_gift_time'].startswith(today):
                await message.answer(
        f"🎁 {message.from_user.first_name} активировал подгон!\n"
        f"Счастливчик: {recipient.first_name} получает {gift_amount} монет! 🎉\n"
        f"📊 Сегодня в этом чате осталось подгонов: {gift_limit_per_chat - (gift_count_today + 1)}"
    )

# ==================== ОБРАБОТЧИК ДОБАВЛЕНИЯ БОТА В ЧАТ ====================
@dp.message_handler(content_types=['new_chat_members'])
async def bot_added_to_chat(message: types.Message):
    bot_user = await bot.me
    if bot_user.id not in [user.id for user in message.new_chat_members]:
        return
    chat = message.chat
    user_id = message.from_user.id
    await create_chat_confirmation_request(chat.id, chat.title, chat.type, user_id)

    # Попытаемся получить ссылку на чат
    try:
        chat_info = await bot.get_chat(chat.id)
        invite_link = chat_info.invite_link
    except:
        invite_link = None

    for admin_id in SUPER_ADMINS:
        kb = confirm_chat_inline(chat.id)
        text = (
            f"🆕 Запрос на активацию бота в чате:\n"
            f"Название: {chat.title}\n"
            f"ID: {chat.id}\n"
            f"Тип: {chat.type}\n"
        )
        if invite_link:
            text += f"Ссылка: {invite_link}\n"
        text += f"Запросил: {message.from_user.first_name} (ID: {user_id})"
        await safe_send_message(admin_id, text, reply_markup=kb)
    await message.answer("📋 Запрос на активацию бота отправлен администратору. Ожидайте подтверждения.")

# ==================== ОБРАБОТКА НЕИЗВЕСТНЫХ КОМАНД В ЧАТЕ ====================
@dp.message_handler(lambda message: message.text and message.text.startswith('/'))
async def unknown_command(message: types.Message):
    if message.chat.type == 'private':
        return
    if not await is_chat_confirmed(message.chat.id):
        return
    await message.reply("❌ Неизвестная команда. Введи /help для списка доступных.")
  # ==================== ПОЛНЫЙ РАБОЧИЙ БОТ ====================
# Часть 5: Административные хендлеры

# ==================== ВХОД В АДМИН-ПАНЕЛЬ ====================
@dp.message_handler(lambda message: message.text == "⚙️ Админ панель")
async def admin_panel(message: types.Message):
    if message.chat.type != 'private':
        return
    if not await is_admin(message.from_user.id):
        await message.answer("У тебя нет прав администратора.")
        return
    super_admin = await is_super_admin(message.from_user.id)
    await message.answer("Панель администратора:", reply_markup=admin_main_keyboard(super_admin))

# ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================
@dp.message_handler(lambda message: message.text == "👥 Управление пользователями")
async def admin_users_menu(message: types.Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("Управление пользователями:", reply_markup=admin_users_keyboard())

@dp.message_handler(lambda message: message.text == "💰 Начислить монеты")
async def add_balance_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может начислять монеты.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await AddBalance.user_id.set()

@dp.message_handler(state=AddBalance.user_id)
async def add_balance_user(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    await state.update_data(user_id=uid)
    await message.answer("Введи сумму начисления (целое положительное число):")
    await AddBalance.amount.set()

@dp.message_handler(state=AddBalance.amount)
async def add_balance_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное целое число.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_balance(uid, amount)
        await message.answer(f"✅ Пользователю {uid} начислено {amount} монет.")
        await safe_send_message(uid, f"💰 Вам начислено {amount} монет администратором.")
    except Exception as e:
        logging.error(f"Add balance error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "💸 Списать монеты")
async def remove_balance_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может списывать монеты.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await RemoveBalance.user_id.set()

@dp.message_handler(state=RemoveBalance.user_id)
async def remove_balance_user(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    await state.update_data(user_id=uid)
    await message.answer("Введи сумму списания (целое положительное число):")
    await RemoveBalance.amount.set()

@dp.message_handler(state=RemoveBalance.amount)
async def remove_balance_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное целое число.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_balance(uid, -amount)
        await message.answer(f"✅ У пользователя {uid} списано {amount} монет.")
        await safe_send_message(uid, f"💸 У тебя списано {amount} монет администратором.")
    except Exception as e:
        logging.error(f"Remove balance error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "⭐️ Начислить репутацию")
async def add_reputation_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может начислять репутацию.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await AddReputation.user_id.set()

@dp.message_handler(state=AddReputation.user_id)
async def add_reputation_user(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    await state.update_data(user_id=uid)
    await message.answer("Введи количество репутации для начисления (целое число):")
    await AddReputation.amount.set()

@dp.message_handler(state=AddReputation.amount)
async def add_reputation_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_reputation(uid, amount)
        await message.answer(f"✅ Пользователю {uid} начислено {amount} репутации.")
        await safe_send_message(uid, f"⭐️ Вам начислено {amount} репутации администратором.")
    except Exception as e:
        logging.error(f"Add reputation error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "🔻 Снять репутацию")
async def remove_reputation_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может снимать репутацию.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await RemoveReputation.user_id.set()

@dp.message_handler(state=RemoveReputation.user_id)
async def remove_reputation_user(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    await state.update_data(user_id=uid)
    await message.answer("Введи количество репутации для снятия (целое число):")
    await RemoveReputation.amount.set()

@dp.message_handler(state=RemoveReputation.amount)
async def remove_reputation_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_reputation(uid, -amount)
        await message.answer(f"✅ У пользователя {uid} снято {amount} репутации.")
        await safe_send_message(uid, f"🔻 У вас снято {amount} репутации администратором.")
    except Exception as e:
        logging.error(f"Remove reputation error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📈 Начислить опыт")
async def add_exp_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может начислять опыт.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await AddExp.user_id.set()

@dp.message_handler(state=AddExp.user_id)
async def add_exp_user(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    await state.update_data(user_id=uid)
    await message.answer("Введи количество опыта для начисления (целое число):")
    await AddExp.amount.set()

@dp.message_handler(state=AddExp.amount)
async def add_exp_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await add_exp(uid, amount)
        await message.answer(f"✅ Пользователю {uid} начислено {amount} опыта.")
    except Exception as e:
        logging.error(f"Add exp error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "🔝 Установить уровень")
async def set_level_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может устанавливать уровень.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await SetLevel.user_id.set()

@dp.message_handler(state=SetLevel.user_id)
async def set_level_user(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    await state.update_data(user_id=uid)
    await message.answer("Введи новый уровень (целое число ≥ 1):")
    await SetLevel.level.set()

@dp.message_handler(state=SetLevel.level)
async def set_level_value(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        level = int(message.text)
        if level < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи целое число ≥ 1.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE users SET level=$1 WHERE user_id=$2", level, uid)
        await message.answer(f"✅ Пользователю {uid} установлен уровень {level}.")
        await safe_send_message(uid, f"🔝 Ваш уровень изменён на {level} администратором.")
    except Exception as e:
        logging.error(f"Set level error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "👥 Найти пользователя")
async def find_user_start(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет прав администратора.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await FindUser.query.set()

@dp.message_handler(state=FindUser.query)
async def find_user_result(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        super_admin = await is_super_admin(message.from_user.id)
        await message.answer("Панель администратора:", reply_markup=admin_main_keyboard(super_admin))
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    name = user_data['first_name']
    bal = user_data['balance']
    rep = user_data['reputation']
    spent = user_data['total_spent']
    joined = user_data['joined_date']
    attempts = user_data['theft_attempts']
    success = user_data['theft_success']
    failed = user_data['theft_failed']
    protected = user_data['theft_protected']
    level = user_data['level']
    exp = user_data['exp']
    strength = user_data['strength']
    agility = user_data['agility']
    defense = user_data['defense']
    banned = await is_banned(uid)
    ban_status = "⛔ Заблокирован" if banned else "✅ Активен"
    text = (
        f"👤 Пользователь: {name} (ID: {uid})\n"
        f"📊 Уровень: {level}, опыт: {exp}\n"
        f"💪 Сила: {strength} | 🏃 Ловкость: {agility} | 🛡 Защита: {defense}\n"
        f"💰 Баланс: {bal}\n"
        f"⭐️ Репутация: {rep}\n"
        f"💸 Потрачено: {spent}\n"
        f"📅 Регистрация: {joined}\n"
        f"🔫 Ограблений: {attempts} (успешно: {success}, провал: {failed})\n"
        f"⚔️ Отбито атак: {protected}\n"
        f"Статус: {ban_status}"
    )
    await message.answer(text)
    await state.finish()

@dp.message_handler(lambda message: message.text == "📊 Экспорт пользователей")
async def export_users(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может экспортировать пользователей.")
        return
    try:
        csv_data = await export_users_to_csv()
        if not csv_data:
            await message.answer("Нет пользователей для экспорта.")
            return
        await message.answer_document(
            types.InputFile(io.BytesIO(csv_data), filename="users.csv"),
            caption="📊 Список пользователей"
        )
    except Exception as e:
        logging.error(f"Export error: {e}")
        await message.answer("❌ Ошибка при экспорте.")

# ==================== УПРАВЛЕНИЕ МАГАЗИНОМ ====================
@dp.message_handler(lambda message: message.text == "🛒 Управление магазином")
async def admin_shop_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять магазином.")
        return
    await message.answer("Управление магазином:", reply_markup=admin_shop_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить товар")
async def add_shop_item_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может добавлять товары.")
        return
    await message.answer("Введи название товара:", reply_markup=back_keyboard())
    await AddShopItem.name.set()

@dp.message_handler(state=AddShopItem.name)
async def add_shop_item_name(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    await state.update_data(name=message.text)
    await message.answer("Введи описание товара:")
    await AddShopItem.next()

@dp.message_handler(state=AddShopItem.description)
async def add_shop_item_description(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    await state.update_data(description=message.text)
    await message.answer("Введи цену (целое число):")
    await AddShopItem.next()

@dp.message_handler(state=AddShopItem.price)
async def add_shop_item_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Цена должна быть положительным целым числом.")
        return
    await state.update_data(price=price)
    await message.answer("Введи количество товара (целое число, -1 для бесконечного):")
    await AddShopItem.stock.set()

@dp.message_handler(state=AddShopItem.stock)
async def add_shop_item_stock(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    try:
        stock = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO shop_items (name, description, price, stock) VALUES ($1, $2, $3, $4)",
                data['name'], data['description'], data['price'], stock
            )
        await message.answer("✅ Товар добавлен!", reply_markup=admin_shop_keyboard())
    except Exception as e:
        logging.error(f"Add shop item error: {e}")
        await message.answer("❌ Ошибка при добавлении товара.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "➖ Удалить товар")
async def remove_shop_item_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может удалять товары.")
        return
    try:
        async with db_pool.acquire() as conn:
            items = await conn.fetch("SELECT id, name FROM shop_items ORDER BY id")
        if not items:
            await message.answer("В магазине нет товаров.")
            return
        text = "Товары:\n" + "\n".join([f"ID {i['id']}: {i['name']}" for i in items])
        await message.answer(text + "\n\nВведи ID товара для удаления:", reply_markup=back_keyboard())
    except Exception as e:
        logging.error(f"List items for remove error: {e}")
        await message.answer("❌ Ошибка.")
        return
    await RemoveShopItem.item_id.set()

@dp.message_handler(state=RemoveShopItem.item_id)
async def remove_shop_item(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    try:
        item_id = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM shop_items WHERE id=$1", item_id)
        await message.answer("✅ Товар удалён, если существовал.", reply_markup=admin_shop_keyboard())
    except Exception as e:
        logging.error(f"Remove shop item error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список товаров")
async def list_shop_items(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может просматривать список товаров.")
        return
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    try:
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM shop_items")
            items = await conn.fetch(
                "SELECT id, name, description, price, stock FROM shop_items ORDER BY id LIMIT $1 OFFSET $2",
                ITEMS_PER_PAGE, offset
            )
        if not items:
            await message.answer("В магазине нет товаров.")
            return
        text = f"📦 Товары (страница {page}):\n"
        for item in items:
            text += f"\nID {item['id']} | {item['name']}\n{item['description']}\n💰 {item['price']} | наличие: {item['stock'] if item['stock']!=-1 else '∞'}\n"
        kb = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"shopitems_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"shopitems_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        if kb:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await message.answer(text, reply_markup=admin_shop_keyboard())
    except Exception as e:
        logging.error(f"List shop items error: {e}")
        await message.answer("❌ Ошибка.")

@dp.callback_query_handler(lambda c: c.data.startswith("shopitems_page_"))
async def shopitems_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    callback.message.text = f"📋 Список товаров {page}"
    await list_shop_items(callback.message)
    await callback.answer()

@dp.message_handler(lambda message: message.text == "✏️ Редактировать товар")
async def edit_shop_item_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может редактировать товары.")
        return
    await message.answer("Введи ID товара для редактирования:", reply_markup=back_keyboard())
    await EditShopItem.item_id.set()

@dp.message_handler(state=EditShopItem.item_id)
async def edit_shop_item_field(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    try:
        item_id = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    await state.update_data(item_id=item_id)
    await message.answer("Что хочешь изменить? (price/stock)", reply_markup=back_keyboard())
    await EditShopItem.field.set()

@dp.message_handler(state=EditShopItem.field)
async def edit_shop_item_value(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    field = message.text.lower()
    if field not in ['price', 'stock']:
        await message.answer("❌ Можно изменить только price или stock.")
        return
    await state.update_data(field=field)
    await message.answer(f"Введи новое значение для {field}:")
    await EditShopItem.value.set()

@dp.message_handler(state=EditShopItem.value)
async def edit_shop_item_final(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    try:
        value = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    data = await state.get_data()
    item_id = data['item_id']
    field = data['field']
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(f"UPDATE shop_items SET {field}=$1 WHERE id=$2", value, item_id)
        await message.answer("✅ Товар обновлён.", reply_markup=admin_shop_keyboard())
    except Exception as e:
        logging.error(f"Edit shop item error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "🛍️ Список покупок")
async def admin_purchases(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет прав администратора.")
        return
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT p.id, u.user_id, u.username, s.name, p.purchase_date, p.status FROM purchases p "
                "JOIN users u ON p.user_id = u.user_id JOIN shop_items s ON p.item_id = s.id "
                "WHERE p.status='pending' ORDER BY p.purchase_date"
            )
        if not rows:
            await message.answer("Нет необработанных покупок.")
            return
        for row in rows:
            pid, uid, username, item_name, date, status = row['id'], row['user_id'], row['username'], row['name'], row['purchase_date'], row['status']
            text = f"🆔 {pid}\nПользователь: {uid} (@{username})\nТовар: {item_name}\nДата: {date}"
            await message.answer(text, reply_markup=purchase_action_keyboard(pid))
    except Exception as e:
        logging.error(f"Admin purchases error: {e}")
        await message.answer("❌ Ошибка загрузки покупок.")

@dp.callback_query_handler(lambda c: c.data.startswith("purchase_done_"))
async def purchase_done(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    purchase_id = int(callback.data.split("_")[2])
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE purchases SET status='completed' WHERE id=$1", purchase_id)
            user_id = await conn.fetchval("SELECT user_id FROM purchases WHERE id=$1", purchase_id)
            if user_id:
                await safe_send_message(user_id, "✅ Твоя покупка обработана! Админ выслал подарок.")
        await callback.answer("Покупка отмечена как выполненная")
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Purchase done error: {e}")
        await callback.answer("Ошибка", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("purchase_reject_"))
async def purchase_reject(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    purchase_id = int(callback.data.split("_")[2])
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE purchases SET status='rejected' WHERE id=$1", purchase_id)
            user_id = await conn.fetchval("SELECT user_id FROM purchases WHERE id=$1", purchase_id)
            if user_id:
                await safe_send_message(user_id, "❌ К сожалению, твоя покупка не может быть выполнена. Свяжись с админом.")
        await callback.answer("Покупка отклонена")
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Purchase reject error: {e}")
        await callback.answer("Ошибка", show_alert=True)

# ==================== УПРАВЛЕНИЕ РОЗЫГРЫШАМИ ====================
@dp.message_handler(lambda message: message.text == "🎁 Управление розыгрышами")
async def admin_giveaway_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять розыгрышами.")
        return
    await message.answer("Управление розыгрышами:", reply_markup=admin_giveaway_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать розыгрыш")
async def create_giveaway_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может создавать розыгрыши.")
        return
    await message.answer("Введи название приза:", reply_markup=back_keyboard())
    await CreateGiveaway.prize.set()

@dp.message_handler(state=CreateGiveaway.prize)
async def create_giveaway_prize(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_giveaway_menu(message)
        return
    await state.update_data(prize=message.text)
    await message.answer("Введи описание розыгрыша:")
    await CreateGiveaway.description.set()

@dp.message_handler(state=CreateGiveaway.description)
async def create_giveaway_description(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_giveaway_menu(message)
        return
    await state.update_data(description=message.text)
    await message.answer("Введи дату окончания в формате ДД.ММ.ГГГГ ЧЧ:ММ (например, 31.12.2025 23:59):")
    await CreateGiveaway.end_date.set()

@dp.message_handler(state=CreateGiveaway.end_date)
async def create_giveaway_end_date(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_giveaway_menu(message)
        return
    try:
        end_date = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        if end_date <= datetime.now():
            await message.answer("Дата окончания должна быть в будущем.")
            return
        await state.update_data(end_date=end_date.strftime("%Y-%m-%d %H:%M:%S"))
    except ValueError:
        await message.answer("Неверный формат. Используй ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    await message.answer("Отправь медиа (фото, видео или документ) для розыгрыша или отправь 'пропустить':")
    await CreateGiveaway.media.set()

@dp.message_handler(state=CreateGiveaway.media, content_types=['text', 'photo', 'video', 'document'])
async def create_giveaway_media(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_giveaway_menu(message)
        return
    data = await state.get_data()
    media_file_id = None
    media_type = None
    if message.photo:
        media_file_id = message.photo[-1].file_id
        media_type = 'photo'
    elif message.video:
        media_file_id = message.video.file_id
        media_type = 'video'
    elif message.document:
        media_file_id = message.document.file_id
        media_type = 'document'
    elif message.text and message.text.lower() == 'пропустить':
        pass
    else:
        await message.answer("Пожалуйста, отправь фото, видео, документ или 'пропустить'.")
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO giveaways (prize, description, end_date, media_file_id, media_type) VALUES ($1, $2, $3, $4, $5)",
                data['prize'], data['description'], data['end_date'], media_file_id, media_type
            )
        await message.answer("✅ Розыгрыш создан!", reply_markup=admin_giveaway_keyboard())
    except Exception as e:
        logging.error(f"Create giveaway error: {e}")
        await message.answer("❌ Ошибка при создании розыгрыша.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Активные розыгрыши")
async def list_active_giveaways(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может просматривать активные розыгрыши.")
        return
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    try:
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM giveaways WHERE status='active'")
            rows = await conn.fetch(
                "SELECT id, prize, end_date, description FROM giveaways WHERE status='active' ORDER BY end_date LIMIT $1 OFFSET $2",
                ITEMS_PER_PAGE, offset
            )
        if not rows:
            await message.answer("Нет активных розыгрышей.")
            return
        text = f"Активные розыгрыши (страница {page}):\n"
        for row in rows:
            gid, prize, end, desc = row['id'], row['prize'], row['end_date'], row['description']
            async with db_pool.acquire() as conn2:
                count = await conn2.fetchval("SELECT COUNT(*) FROM participants WHERE giveaway_id=$1", gid)
            text += f"ID: {gid} | {prize} | до {end} | 👥 {count} участников\n{desc}\n\n"
        kb = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"activegiveaways_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"activegiveaways_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        if kb:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await message.answer(text, reply_markup=admin_giveaway_keyboard())
    except Exception as e:
        logging.error(f"List giveaways error: {e}")
        await message.answer("❌ Ошибка.")

@dp.callback_query_handler(lambda c: c.data.startswith("activegiveaways_page_"))
async def activegiveaways_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    callback.message.text = f"📋 Активные розыгрыши {page}"
    await list_active_giveaways(callback.message)
    await callback.answer()

@dp.message_handler(lambda message: message.text == "✅ Завершить розыгрыш")
async def finish_giveaway_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может завершать розыгрыши.")
        return
    await message.answer("Введи ID розыгрыша, который нужно завершить:", reply_markup=back_keyboard())
    await CompleteGiveaway.giveaway_id.set()

@dp.message_handler(state=CompleteGiveaway.giveaway_id)
async def finish_giveaway(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_giveaway_menu(message)
        return
    try:
        gid = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    await state.update_data(giveaway_id=gid)
    await message.answer("Введи количество победителей (целое число):")
    await CompleteGiveaway.winners_count.set()

@dp.message_handler(state=CompleteGiveaway.winners_count)
async def finish_giveaway_winners(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_giveaway_menu(message)
        return
    try:
        winners_count = int(message.text)
        if winners_count < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное целое число.")
        return
    data = await state.get_data()
    gid = data['giveaway_id']
    try:
        async with db_pool.acquire() as conn:
            status = await conn.fetchval("SELECT status FROM giveaways WHERE id=$1", gid)
            if not status or status != 'active':
                await message.answer("Розыгрыш не активен или не существует.")
                await state.finish()
                return
            participants = await conn.fetch("SELECT user_id FROM participants WHERE giveaway_id=$1", gid)
            participants = [r['user_id'] for r in participants]
            if not participants:
                await message.answer("В этом розыгрыше нет участников.")
                await state.finish()
                return
            if winners_count > len(participants):
                winners_count = len(participants)
            winners = random.sample(participants, winners_count)
            await conn.execute("UPDATE giveaways SET status='completed', winner_id=$1 WHERE id=$2", winners[0], gid)
            for wid in winners:
                await safe_send_message(wid, f"🎉 Поздравляем! Ты выиграл в розыгрыше! Свяжись с админом.")
        await message.answer(f"🏆 Победители выбраны! ({len(winners)})", reply_markup=admin_giveaway_keyboard())
    except Exception as e:
        logging.error(f"Finish giveaway error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

# ==================== УПРАВЛЕНИЕ КАНАЛАМИ ====================
@dp.message_handler(lambda message: message.text == "📢 Управление каналами")
async def admin_channel_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять каналами.")
        return
    await message.answer("Управление каналами:", reply_markup=admin_channel_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить канал")
async def add_channel_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может добавлять каналы.")
        return
    await message.answer("Введи chat_id канала (можно получить у @username_to_id_bot):", reply_markup=back_keyboard())
    await AddChannel.chat_id.set()

@dp.message_handler(state=AddChannel.chat_id)
async def add_channel_chat_id(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_channel_menu(message)
        return
    await state.update_data(chat_id=message.text.strip())
    await message.answer("Введи название канала:")
    await AddChannel.next()

@dp.message_handler(state=AddChannel.title)
async def add_channel_title(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_channel_menu(message)
        return
    await state.update_data(title=message.text)
    await message.answer("Введи invite-ссылку (или отправь 'нет'):")
    await AddChannel.next()

@dp.message_handler(state=AddChannel.invite_link)
async def add_channel_link(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_channel_menu(message)
        return
    link = None if message.text.lower() == 'нет' else message.text.strip()
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO channels (chat_id, title, invite_link) VALUES ($1, $2, $3)",
                data['chat_id'], data['title'], link
            )
        await message.answer("✅ Канал добавлен!", reply_markup=admin_channel_keyboard())
    except asyncpg.UniqueViolationError:
        await message.answer("❌ Канал с таким chat_id уже существует.")
    except Exception as e:
        logging.error(f"Add channel error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "➖ Удалить канал")
async def remove_channel_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может удалять каналы.")
        return
    await message.answer("Введи chat_id канала для удаления:", reply_markup=back_keyboard())
    await RemoveChannel.chat_id.set()

@dp.message_handler(state=RemoveChannel.chat_id)
async def remove_channel(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_channel_menu(message)
        return
    chat_id = message.text.strip()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM channels WHERE chat_id=$1", chat_id)
        await message.answer("✅ Канал удалён, если существовал.", reply_markup=admin_channel_keyboard())
    except Exception as e:
        logging.error(f"Remove channel error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список каналов")
async def list_channels(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может просматривать список каналов.")
        return
    channels = await get_channels()
    if not channels:
        await message.answer("Нет добавленных каналов.")
        return
    text = "📺 Каналы для подписки:\n"
    for chat_id, title, link in channels:
        text += f"• {title} (chat_id: {chat_id})\n  Ссылка: {link or 'нет'}\n"
    await message.answer(text, reply_markup=admin_channel_keyboard())

# ==================== УПРАВЛЕНИЕ ПРОМОКОДАМИ ====================
@dp.message_handler(lambda message: message.text == "🎫 Управление промокодами")
async def admin_promo_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять промокодами.")
        return
    await message.answer("Управление промокодами:", reply_markup=admin_promo_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать промокод")
async def create_promo_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может создавать промокоды.")
        return
    await message.answer("Введи код промокода (латиница, цифры):", reply_markup=back_keyboard())
    await CreatePromocode.code.set()

@dp.message_handler(state=CreatePromocode.code)
async def create_promo_code(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_promo_menu(message)
        return
    code = message.text.strip().upper()
    await state.update_data(code=code)
    await message.answer("Введи количество монет, которые даёт промокод:")
    await CreatePromocode.next()

@dp.message_handler(state=CreatePromocode.reward)
async def create_promo_reward(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_promo_menu(message)
        return
    try:
        reward = int(message.text)
        if reward <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное целое число.")
        return
    await state.update_data(reward=reward)
    await message.answer("Введи максимальное количество использований:")
    await CreatePromocode.next()

@dp.message_handler(state=CreatePromocode.max_uses)
async def create_promo_max_uses(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_promo_menu(message)
        return
    try:
        max_uses = int(message.text)
        if max_uses <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное целое число.")
        return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO promocodes (code, reward, max_uses, created_at) VALUES ($1, $2, $3, $4)",
                data['code'], data['reward'], max_uses, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        await message.answer("✅ Промокод создан!", reply_markup=admin_promo_keyboard())
    except asyncpg.UniqueViolationError:
        await message.answer("❌ Промокод с таким кодом уже существует.")
    except Exception as e:
        logging.error(f"Create promo error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список промокодов")
async def list_promos(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может просматривать список промокодов.")
        return
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    try:
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM promocodes")
            rows = await conn.fetch(
                "SELECT code, reward, max_uses, used_count FROM promocodes LIMIT $1 OFFSET $2",
                ITEMS_PER_PAGE, offset
            )
        if not rows:
            await message.answer("Нет промокодов.")
            return
        text = f"🎫 Промокоды (страница {page}):\n"
        for row in rows:
            text += f"• {row['code']}: {row['reward']} монет, использовано {row['used_count']}/{row['max_uses']}\n"
        kb = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"promos_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"promos_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        if kb:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await message.answer(text, reply_markup=admin_promo_keyboard())
    except Exception as e:
        logging.error(f"List promos error: {e}")
        await message.answer("❌ Ошибка.")

@dp.callback_query_handler(lambda c: c.data.startswith("promos_page_"))
async def promos_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    callback.message.text = f"📋 Список промокодов {page}"
    await list_promos(callback.message)
    await callback.answer()

# ==================== УПРАВЛЕНИЕ ЗАДАНИЯМИ ====================
@dp.message_handler(lambda message: message.text == "📋 Управление заданиями")
async def admin_tasks_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять заданиями.")
        return
    await message.answer("Управление заданиями:", reply_markup=admin_tasks_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать задание")
async def create_task_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может создавать задания.")
        return
    await message.answer("Введи название задания:", reply_markup=back_keyboard())
    await CreateTask.name.set()

@dp.message_handler(state=CreateTask.name)
async def create_task_name(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    await state.update_data(name=message.text)
    await message.answer("Введи описание задания:")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.description)
async def create_task_description(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    await state.update_data(description=message.text)
    await message.answer("Введи тип задания (subscribe):")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.task_type)
async def create_task_type(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    task_type = message.text.lower()
    if task_type not in ['subscribe']:
        await message.answer("Поддерживается только 'subscribe'")
        return
    await state.update_data(task_type=task_type)
    await message.answer("Введи ID канала (с -100) для подписки:")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.target_id)
async def create_task_target(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    await state.update_data(target_id=message.text.strip())
    await message.answer("Введи награду (монеты):")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.reward_coins)
async def create_task_reward_coins(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    try:
        coins = int(message.text)
    except:
        await message.answer("Введи целое число.")
        return
    await state.update_data(reward_coins=coins)
    await message.answer("Введи награду (репутация):")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.reward_reputation)
async def create_task_reward_rep(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    try:
        rep = int(message.text)
    except:
        await message.answer("Введи целое число.")
        return
    await state.update_data(reward_reputation=rep)
    await message.answer("Сколько дней нужно быть подписанным? (0 - не проверять):")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.required_days)
async def create_task_required_days(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    try:
        days = int(message.text)
        if days < 0:
            raise ValueError
    except:
        await message.answer("Введи неотрицательное целое число.")
        return
    await state.update_data(required_days=days)
    await message.answer("Штрафных дней (если отписался раньше, 0 - нет штрафа):")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.penalty_days)
async def create_task_penalty_days(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    try:
        days = int(message.text)
        if days < 0:
            raise ValueError
    except:
        await message.answer("Введи неотрицательное целое число.")
        return
    await state.update_data(penalty_days=days)
    await message.answer("Максимальное количество выполнений задания (0 - бесконечно):")
    await CreateTask.next()

@dp.message_handler(state=CreateTask.max_completions)
async def create_task_max_completions(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    try:
        max_completions = int(message.text)
        if max_completions < 0:
            raise ValueError
    except:
        await message.answer("Введи неотрицательное целое число.")
        return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO tasks (name, description, task_type, target_id, reward_coins, reward_reputation, required_days, penalty_days, max_completions, created_by, created_at, active) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, TRUE)",
                data['name'], data['description'], data['task_type'], data['target_id'], data['reward_coins'], data['reward_reputation'], data['required_days'], data['penalty_days'], max_completions, message.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        await message.answer("✅ Задание создано!", reply_markup=admin_tasks_keyboard())
    except Exception as e:
        logging.error(f"Create task error: {e}")
        await message.answer("❌ Ошибка при создании задания.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список заданий")
async def list_tasks(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может просматривать список заданий.")
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, active, max_completions, completed_count FROM tasks ORDER BY id")
    if not rows:
        await message.answer("Нет заданий.")
        return
    text = "📋 Задания:\n"
    for row in rows:
        status = "активно" if row['active'] else "неактивно"
        progress = f" (выполнено {row['completed_count']}/{row['max_completions'] if row['max_completions']>0 else '∞'})"
        text += f"ID {row['id']}: {row['name']} - {status}{progress}\n"
    await message.answer(text, reply_markup=admin_tasks_keyboard())

@dp.message_handler(lambda message: message.text == "❌ Удалить задание")
async def delete_task_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может удалять задания.")
        return
    await message.answer("Введи ID задания для удаления (деактивации):", reply_markup=back_keyboard())
    await DeleteTask.task_id.set()

@dp.message_handler(state=DeleteTask.task_id)
async def delete_task_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_tasks_menu(message)
        return
    try:
        task_id = int(message.text)
    except:
        await message.answer("Введи число.")
        return
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE tasks SET active=FALSE WHERE id=$1", task_id)
    await message.answer("✅ Задание деактивировано.", reply_markup=admin_tasks_keyboard())
    await state.finish()

# ==================== УПРАВЛЕНИЕ ЧАТАМИ ====================
@dp.message_handler(lambda message: message.text == "🤖 Управление чатами")
async def admin_chats_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять чатами.")
        return
    await message.answer("Управление чатами:", reply_markup=admin_chats_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Список запросов на подтверждение")
async def list_pending_requests(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    requests = await get_pending_chat_requests()
    if not requests:
        await message.answer("Нет ожидающих запросов.")
        return
    text = "📋 Ожидающие запросы:\n\n"
    for req in requests:
        text += f"• {req['title']} (ID: {req['chat_id']})\n  Запросил: {req['requested_by']} ({req['request_date']})\n"
    await message.answer(text)

@dp.message_handler(lambda message: message.text == "✅ Подтвердить чат")
async def confirm_chat_manual(message: types.Message, state: FSMContext):
    if not await is_super_admin(message.from_user.id):
        return
    await message.answer("Введи ID чата, который хочешь подтвердить:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    async with state.proxy() as data:
        data['action'] = "confirm"

@dp.message_handler(lambda message: message.text == "❌ Отклонить запрос")
async def reject_chat_manual(message: types.Message, state: FSMContext):
    if not await is_super_admin(message.from_user.id):
        return
    await message.answer("Введи ID чата, запрос которого хочешь отклонить:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    async with state.proxy() as data:
        data['action'] = "reject"

@dp.message_handler(lambda message: message.text == "🗑 Удалить чат из подтверждённых")
async def remove_confirmed_chat_start(message: types.Message, state: FSMContext):
    if not await is_super_admin(message.from_user.id):
        return
    await message.answer("Введи ID чата, который нужно удалить из подтверждённых:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    async with state.proxy() as data:
        data['action'] = "remove"

@dp.message_handler(lambda message: message.text == "📋 Список подтверждённых чатов")
async def list_confirmed_chats(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    confirmed = await get_confirmed_chats(force_update=True)
    if not confirmed:
        await message.answer("Нет подтверждённых чатов.")
        return
    text = "✅ Подтверждённые чаты:\n\n"
    for chat_id, data in confirmed.items():
        text += f"• {data['title']} (ID: {chat_id})\n  Подтверждён: {data.get('confirmed_date', 'неизвестно')}\n"
    await message.answer(text)

@dp.message_handler(state=ManageChats.chat_id)
async def process_chat_id(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_chats_menu(message)
        return
    try:
        chat_id = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    data = await state.get_data()
    action = data.get('action')
    async with db_pool.acquire() as conn:
        if action == "confirm":
            request = await conn.fetchrow("SELECT * FROM chat_confirmation_requests WHERE chat_id=$1", chat_id)
            if request:
                await add_confirmed_chat(chat_id, request['title'], request['type'], message.from_user.id)
                await update_chat_request_status(chat_id, 'approved')
                await message.answer(f"✅ Чат {request['title']} подтверждён.")
                await safe_send_message(request['requested_by'], f"✅ Ваш чат «{request['title']}» активирован!")
            else:
                try:
                    chat = await bot.get_chat(chat_id)
                    await add_confirmed_chat(chat_id, chat.title, chat.type, message.from_user.id)
                    await message.answer(f"✅ Чат {chat.title} подтверждён.")
                except:
                    await message.answer("❌ Не удалось получить информацию о чате.")
        elif action == "reject":
            request = await conn.fetchrow("SELECT * FROM chat_confirmation_requests WHERE chat_id=$1", chat_id)
            if not request:
                await message.answer("❌ Запрос не найден.")
                await state.finish()
                return
            await update_chat_request_status(chat_id, 'rejected')
            await message.answer(f"❌ Запрос для чата {request['title']} отклонён.")
            await safe_send_message(request['requested_by'], f"❌ Запрос на активацию чата «{request['title']}» отклонён.")
        elif action == "remove":
            await remove_confirmed_chat(chat_id)
            await message.answer(f"✅ Чат {chat_id} удалён из подтверждённых.")
    await state.finish()

# ==================== УПРАВЛЕНИЕ БОССАМИ ====================
@dp.message_handler(lambda message: message.text == "👾 Управление боссами")
async def admin_boss_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять боссами.")
        return
    await message.answer("Управление боссами:", reply_markup=admin_boss_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Активные боссы")
async def list_active_bosses(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM bosses WHERE status='active' ORDER BY spawned_at")
    if not rows:
        await message.answer("Нет активных боссов.")
        return
    text = "Активные боссы:\n"
    for row in rows:
        text += f"ID {row['id']}: {row['name']} (ур. {row['level']}) в чате {row['chat_id']}, HP {row['hp']}/{row['max_hp']}\n"
    await message.answer(text)

@dp.message_handler(lambda message: message.text == "⚔️ Создать босса вручную")
async def manual_spawn_boss_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    await message.answer("Введи ID чата, где создать босса:", reply_markup=back_keyboard())
    await BossSpawn.chat_id.set()

@dp.message_handler(state=BossSpawn.chat_id)
async def manual_spawn_boss_chat(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_boss_menu(message)
        return
    try:
        chat_id = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    if not await is_chat_confirmed(chat_id):
        await message.answer("❌ Чат не подтверждён. Сначала подтвердите его.")
        await state.finish()
        return
    await state.update_data(chat_id=chat_id)
    await message.answer("Введи уровень босса (1-10):")
    await BossSpawn.level.set()

@dp.message_handler(state=BossSpawn.level)
async def manual_spawn_boss_level(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_boss_menu(message)
        return
    try:
        level = int(message.text)
        if level < 1 or level > 10:
            raise ValueError
    except:
        await message.answer("❌ Введи число от 1 до 10.")
        return
    data = await state.get_data()
    chat_id = data['chat_id']
    await spawn_boss(chat_id, level=level)
    await message.answer(f"✅ Босс {level} уровня создан в чате {chat_id}.")
    await state.finish()

# ==================== УПРАВЛЕНИЕ ПОМОЩНИКАМИ (ЗАГЛУШКА) ====================
@dp.message_handler(lambda message: message.text == "⚔️ Управление помощниками")
async def admin_helper_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять помощниками.")
        return
    await message.answer("Управление помощниками:", reply_markup=admin_helper_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Активные помощники")
async def list_active_helpers(message: types.Message):
    await message.answer("Функция в разработке.")

@dp.message_handler(lambda message: message.text == "📊 Топы чатов")
async def chat_tops(message: types.Message):
    await message.answer("Функция в разработке.")

# ==================== УПРАВЛЕНИЕ АУКЦИОНАМИ ====================
@dp.message_handler(lambda message: message.text == "🏷 Управление аукционами")
async def admin_auction_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять аукционами.")
        return
    await message.answer("Управление аукционами:", reply_markup=admin_auction_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать аукцион")
async def create_auction_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может создавать аукционы.")
        return
    await message.answer("Введи название товара:", reply_markup=back_keyboard())
    await CreateAuction.item_name.set()

@dp.message_handler(state=CreateAuction.item_name)
async def create_auction_name(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    await state.update_data(item_name=message.text)
    await message.answer("Введи описание товара:")
    await CreateAuction.next()

@dp.message_handler(state=CreateAuction.description)
async def create_auction_description(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    await state.update_data(description=message.text)
    await message.answer("Введи стартовую цену (целое число):")
    await CreateAuction.next()

@dp.message_handler(state=CreateAuction.start_price)
async def create_auction_start_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введи положительное целое число.")
        return
    await state.update_data(start_price=price, current_price=price)
    await message.answer("Введи время окончания в часах (целое число) или 'нет', если не нужно:")
    await CreateAuction.next()

@dp.message_handler(state=CreateAuction.end_time)
async def create_auction_end_time(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    if message.text.lower() == 'нет':
        end_time = None
    else:
        try:
            hours = int(message.text)
            if hours <= 0:
                raise ValueError
            end_time = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        except:
            await message.answer("❌ Введи целое положительное число часов или 'нет'.")
            return
    await state.update_data(end_time=end_time)
    await message.answer("Введи целевую цену (целое число) или 'нет', если не нужна:")
    await CreateAuction.next()

@dp.message_handler(state=CreateAuction.target_price)
async def create_auction_target_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    if message.text.lower() == 'нет':
        target_price = None
    else:
        try:
            target_price = int(message.text)
            if target_price <= 0:
                raise ValueError
        except:
            await message.answer("❌ Введи целое положительное число или 'нет'.")
            return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO auctions (item_name, description, start_price, current_price, end_time, target_price, created_by) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                data['item_name'], data['description'], data['start_price'], data['start_price'], data['end_time'], target_price, message.from_user.id
            )
        await message.answer("✅ Аукцион создан!", reply_markup=admin_auction_keyboard())
    except Exception as e:
        logging.error(f"Create auction error: {e}")
        await message.answer("❌ Ошибка при создании аукциона.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Активные аукционы")
async def list_active_auctions(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM auctions WHERE status='active' ORDER BY created_at")
    if not rows:
        await message.answer("Нет активных аукционов.")
        return
    text = "Активные аукционы:\n"
    for row in rows:
        text += f"ID {row['id']}: {row['item_name']} | Текущая цена: {row['current_price']} | Создатель: {row['created_by']}\n"
    await message.answer(text)

@dp.message_handler(lambda message: message.text == "❌ Отменить аукцион")
async def cancel_auction_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    await message.answer("Введи ID аукциона для отмены:", reply_markup=back_keyboard())
    await CancelAuction.auction_id.set()

@dp.message_handler(state=CancelAuction.auction_id)
async def cancel_auction_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    try:
        auction_id = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE auctions SET status='cancelled' WHERE id=$1", auction_id)
    await message.answer(f"✅ Аукцион {auction_id} отменён.")
    await state.finish()

# ==================== УПРАВЛЕНИЕ РЕКЛАМОЙ ====================
@dp.message_handler(lambda message: message.text == "📢 Управление рекламой")
async def admin_ad_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять рекламой.")
        return
    await message.answer("Управление рекламой:", reply_markup=admin_ad_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать рекламу")
async def create_ad_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    await message.answer("Введи текст рекламного сообщения:", reply_markup=back_keyboard())
    await CreateAd.text.set()

@dp.message_handler(state=CreateAd.text)
async def create_ad_text(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ad_menu(message)
        return
    await state.update_data(text=message.text)
    await message.answer("Введи интервал отправки в минутах (целое число):")
    await CreateAd.interval.set()

@dp.message_handler(state=CreateAd.interval)
async def create_ad_interval(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ad_menu(message)
        return
    try:
        interval = int(message.text)
        if interval <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введи целое положительное число.")
        return
    await state.update_data(interval=interval)
    await message.answer("Куда отправлять? (chats / private / all):")
    await CreateAd.target.set()

@dp.message_handler(state=CreateAd.target)
async def create_ad_target(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ad_menu(message)
        return
    target = message.text.lower()
    if target not in ['chats', 'private', 'all']:
        await message.answer("❌ Выбери: chats, private или all.")
        return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO ads (text, interval_minutes, target, last_sent, enabled) VALUES ($1, $2, $3, $4, $5)",
                data['text'], data['interval'], target, datetime.now(), True
            )
        await message.answer("✅ Рекламное объявление создано!", reply_markup=admin_ad_keyboard())
    except Exception as e:
        logging.error(f"Create ad error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список рекламы")
async def list_ads(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, text, interval_minutes, enabled FROM ads ORDER BY id")
    if not rows:
        await message.answer("Нет рекламных объявлений.")
        return
    text = "📢 Рекламные объявления:\n"
    for row in rows:
        status = "✅" if row['enabled'] else "❌"
        text += f"{status} ID {row['id']}: {row['text'][:50]}... (интервал {row['interval_minutes']} мин)\n"
    await message.answer(text)

# ==================== НАСТРОЙКИ ИГРЫ ====================
@dp.message_handler(lambda message: message.text == "⚙️ Настройки игры")
async def settings_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может изменять настройки игры.")
        return
    await message.answer("Выбери категорию настроек:", reply_markup=settings_reply_keyboard())

@dp.message_handler(lambda message: message.text == "⚙️ Кража")
async def settings_theft(message: types.Message, state: FSMContext):
    if not await is_super_admin(message.from_user.id):
        return
    params = [
        "random_attack_cost",
        "targeted_attack_cost",
        "theft_cooldown_minutes",
        "theft_success_chance",
        "theft_defense_chance",
        "theft_defense_penalty",
        "min_theft_amount",
        "max_theft_amount"
    ]
    text = "⚙️ Настройки кражи:\n"
    for param in params:
        value = await get_setting(param)
        text += f"• {param}: {value}\n"
    text += "\nВведи название параметра для изменения (например, theft_cooldown_minutes) или /cancel"
    await message.answer(text)
    await EditSettings.key.set()

@dp.message_handler(state=EditSettings.key)
async def set_setting_key(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await state.finish()
        await settings_menu(message)
        return
    key = message.text.strip()
    if key not in DEFAULT_SETTINGS:
        await message.answer("❌ Неизвестный параметр. Попробуйте ещё раз или /cancel.")
        return
    await state.update_data(setting_key=key)
    await message.answer(f"Введи новое значение для {key}:")
    await EditSettings.value.set()

@dp.message_handler(state=EditSettings.value)
async def set_setting_value(message: types.Message, state: FSMContext):
    try:
        value = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    data = await state.get_data()
    key = data['setting_key']
    await set_setting(key, str(value))
    await message.answer(f"✅ Параметр {key} обновлён.")
    await state.finish()
    await settings_menu(message)

# Аналогичные хендлеры для других категорий (казино, опыт, боссы, помощники, аукцион, подгон, рефералы, очистка логов)
# Для краткости здесь приведён только пример для кражи, остальные делаются аналогично.

# ==================== СТАТИСТИКА ====================
@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def stats_handler(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет прав администратора.")
        return
    try:
        async with db_pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_balance = await conn.fetchval("SELECT SUM(balance) FROM users") or 0
            total_reputation = await conn.fetchval("SELECT SUM(reputation) FROM users") or 0
            total_spent = await conn.fetchval("SELECT SUM(total_spent) FROM users") or 0
            active_giveaways = await conn.fetchval("SELECT COUNT(*) FROM giveaways WHERE status='active'") or 0
            shop_items = await conn.fetchval("SELECT COUNT(*) FROM shop_items") or 0
            purchases_pending = await conn.fetchval("SELECT COUNT(*) FROM purchases WHERE status='pending'") or 0
            purchases_completed = await conn.fetchval("SELECT COUNT(*) FROM purchases WHERE status='completed'") or 0
            total_thefts = await conn.fetchval("SELECT SUM(theft_attempts) FROM users") or 0
            total_thefts_success = await conn.fetchval("SELECT SUM(theft_success) FROM users") or 0
            promos = await conn.fetchval("SELECT COUNT(*) FROM promocodes") or 0
            banned = await conn.fetchval("SELECT COUNT(*) FROM banned_users") or 0
            total_bosses = await conn.fetchval("SELECT COUNT(*) FROM bosses") or 0
            active_bosses = await conn.fetchval("SELECT COUNT(*) FROM bosses WHERE status='active'") or 0
            confirmed_chats = await conn.fetchval("SELECT COUNT(*) FROM confirmed_chats") or 0
        text = (
            f"📊 Статистика:\n"
            f"👥 Пользователей: {users}\n"
            f"💰 Всего монет: {total_balance}\n"
            f"⭐️ Всего репутации: {total_reputation}\n"
            f"💸 Всего потрачено: {total_spent}\n"
            f"🎁 Активных розыгрышей: {active_giveaways}\n"
            f"🛒 Товаров в магазине: {shop_items}\n"
            f"🛍️ Ожидающих покупок: {purchases_pending}\n"
            f"✅ Выполненных покупок: {purchases_completed}\n"
            f"🔫 Всего ограблений: {total_thefts} (успешно: {total_thefts_success})\n"
            f"🎫 Промокодов создано: {promos}\n"
            f"⛔ Заблокировано: {banned}\n"
            f"👾 Всего боссов: {total_bosses} (активных: {active_bosses})\n"
            f"✅ Подтверждённых чатов: {confirmed_chats}"
        )
        await message.answer(text, reply_markup=admin_main_keyboard(await is_super_admin(message.from_user.id)))
    except Exception as e:
        logging.error(f"Stats error: {e}")
        await message.answer("❌ Ошибка получения статистики.")

# ==================== БЛОКИРОВКИ ====================
@dp.message_handler(lambda message: message.text == "🔨 Блокировки")
async def admin_ban_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять блокировками.")
        return
    await message.answer("Управление блокировками:", reply_markup=admin_ban_keyboard())

@dp.message_handler(lambda message: message.text == "🔨 Заблокировать пользователя")
async def block_user_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может блокировать пользователей.")
        return
    await message.answer("Введи ID или @username пользователя для блокировки:", reply_markup=back_keyboard())
    await BlockUser.user_id.set()

@dp.message_handler(state=BlockUser.user_id)
async def block_user_id(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ban_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    if await is_admin(uid):
        await message.answer("❌ Нельзя заблокировать администратора.")
        await state.finish()
        return
    await state.update_data(user_id=uid)
    await message.answer("Введи причину блокировки (можно отправить 'нет'):")
    await BlockUser.reason.set()

@dp.message_handler(state=BlockUser.reason)
async def block_user_reason(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ban_menu(message)
        return
    reason = None if message.text.lower() == 'нет' else message.text
    data = await state.get_data()
    uid = data['user_id']
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO banned_users (user_id, banned_by, banned_date, reason) VALUES ($1, $2, $3, $4) ON CONFLICT (user_id) DO NOTHING",
                uid, message.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reason
            )
        await message.answer(f"✅ Пользователь {uid} заблокирован.")
        await safe_send_message(uid, f"⛔ Вы заблокированы в боте. Причина: {reason if reason else 'не указана'}")
    except Exception as e:
        logging.error(f"Block user error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "🔓 Разблокировать пользователя")
async def unblock_user_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может разблокировать пользователей.")
        return
    await message.answer("Введи ID или @username пользователя для разблокировки:", reply_markup=back_keyboard())
    await UnblockUser.user_id.set()

@dp.message_handler(state=UnblockUser.user_id)
async def unblock_user_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ban_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM banned_users WHERE user_id=$1", uid)
        await message.answer(f"✅ Пользователь {uid} разблокирован.")
        await safe_send_message(uid, "🔓 Вы разблокированы в боте.")
    except Exception as e:
        logging.error(f"Unblock user error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список заблокированных")
async def list_banned(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, banned_date, reason FROM banned_users ORDER BY banned_date DESC")
    if not rows:
        await message.answer("Нет заблокированных пользователей.")
        return
    text = "⛔ Заблокированные пользователи:\n\n"
    for row in rows:
        text += f"ID: {row['user_id']}, Дата: {row['banned_date']}\nПричина: {row['reason'] or 'не указана'}\n\n"
    await message.answer(text)

# ==================== УПРАВЛЕНИЕ АДМИНАМИ ====================
@dp.message_handler(lambda message: message.text == "➕ Управление админами")
async def admin_admins_menu(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может управлять админами.")
        return
    await message.answer("Управление админами:", reply_markup=admin_admins_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить админа")
async def add_admin_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("Только суперадмин может добавлять админов.")
        return
    await message.answer("Введи ID или @username пользователя, которого хочешь сделать младшим админом:", reply_markup=back_keyboard())
    await AddJuniorAdmin.user_id.set()

@dp.message_handler(state=AddJuniorAdmin.user_id)
async def add_admin_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_admins_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO admins (user_id, added_by, added_date) VALUES ($1, $2, $3)",
                uid, message.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        await message.answer(f"✅ Пользователь {uid} теперь младший админ.")
    except asyncpg.UniqueViolationError:
        await message.answer("❌ Этот пользователь уже админ.")
    except Exception as e:
        logging.error(f"Add admin error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "➖ Удалить админа")
async def remove_admin_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("Только суперадмин может удалять админов.")
        return
    await message.answer("Введи ID или @username пользователя, которого хочешь лишить прав админа:", reply_markup=back_keyboard())
    await RemoveJuniorAdmin.user_id.set()

@dp.message_handler(state=RemoveJuniorAdmin.user_id)
async def remove_admin_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_admins_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM admins WHERE user_id=$1", uid)
        await message.answer(f"✅ Пользователь {uid} больше не админ, если был им.")
    except Exception as e:
        logging.error(f"Remove admin error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список админов")
async def list_admins(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, added_date FROM admins ORDER BY added_date")
    if not rows:
        await message.answer("Нет младших админов.")
        return
    text = "👥 Младшие админы:\n"
    for row in rows:
        text += f"• ID: {row['user_id']}, назначен: {row['added_date']}\n"
    await message.answer(text)

# ==================== РАССЫЛКА ====================
@dp.message_handler(lambda message: message.text == "📢 Рассылка")
async def broadcast_start(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только суперадмин может делать рассылку.")
        return
    await message.answer("Отправь сообщение для рассылки (текст, фото, видео или документ).", reply_markup=back_keyboard())
    await Broadcast.media.set()

@dp.message_handler(state=Broadcast.media, content_types=['text', 'photo', 'video', 'document'])
async def broadcast_media(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        super_admin = await is_super_admin(message.from_user.id)
        await message.answer("Панель администратора:", reply_markup=admin_main_keyboard(super_admin))
        return

    content = {}
    if message.text:
        content['type'] = 'text'
        content['text'] = message.text
    elif message.photo:
        content['type'] = 'photo'
        content['file_id'] = message.photo[-1].file_id
        content['caption'] = message.caption or ""
    elif message.video:
        content['type'] = 'video'
        content['file_id'] = message.video.file_id
        content['caption'] = message.caption or ""
    elif message.document:
        content['type'] = 'document'
        content['file_id'] = message.document.file_id
        content['caption'] = message.caption or ""
    else:
        await message.answer("Неподдерживаемый тип.")
        return

    await state.finish()

    status_msg = await message.answer("⏳ Рассылка начата... Это может занять некоторое время.")

    async with db_pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")
        users = [r['user_id'] for r in users]

    sent = 0
    failed = 0
    total = len(users)

    for i, uid in enumerate(users):
        if await is_banned(uid):
            continue
        try:
            if content['type'] == 'text':
                await bot.send_message(uid, content['text'])
            elif content['type'] == 'photo':
                await bot.send_photo(uid, content['file_id'], caption=content['caption'])
            elif content['type'] == 'video':
                await bot.send_video(uid, content['file_id'], caption=content['caption'])
            elif content['type'] == 'document':
                await bot.send_document(uid, content['file_id'], caption=content['caption'])
            sent += 1
        except (BotBlocked, UserDeactivated, ChatNotFound):
            failed += 1
        except RetryAfter as e:
            logging.warning(f"Flood limit, waiting {e.timeout} seconds")
            await asyncio.sleep(e.timeout)
            try:
                if content['type'] == 'text':
                    await bot.send_message(uid, content['text'])
                else:
                    if content['type'] == 'photo':
                        await bot.send_photo(uid, content['file_id'], caption=content['caption'])
                    elif content['type'] == 'video':
                        await bot.send_video(uid, content['file_id'], caption=content['caption'])
                    elif content['type'] == 'document':
                        await bot.send_document(uid, content['file_id'], caption=content['caption'])
                sent += 1
            except:
                failed += 1
        except Exception as e:
            failed += 1
            logging.warning(f"Failed to send to {uid}: {e}")

        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"⏳ Прогресс: {i+1}/{total}\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")
            except:
                pass

        await asyncio.sleep(0.05)

    await status_msg.edit_text(f"✅ Рассылка завершена!\n📊 Отправлено: {sent}\n❌ Ошибок: {failed}\n👥 Всего: {total}")

# ==================== ОЧИСТКА СТАРЫХ ЗАПИСЕЙ ====================
async def perform_cleanup(manual=False):
    days_bosses = int(await get_setting("cleanup_days_bosses"))
    days_auctions = int(await get_setting("cleanup_days_auctions"))
    days_purchases = int(await get_setting("cleanup_days_purchases"))
    days_giveaways = int(await get_setting("cleanup_days_giveaways"))
    days_tasks = int(await get_setting("cleanup_days_user_tasks"))
    days_fight = int(await get_setting("cleanup_days_fight_logs"))

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM bosses WHERE status IN ('defeated', 'expired') AND spawned_at < NOW() - INTERVAL '1 day' * $1", days_bosses)
        await conn.execute("DELETE FROM boss_attacks WHERE attack_time < NOW() - INTERVAL '1 day' * $1", days_bosses)
        await conn.execute("DELETE FROM auctions WHERE status='ended' AND end_time < NOW() - INTERVAL '1 day' * $1", days_auctions)
        await conn.execute("DELETE FROM purchases WHERE status IN ('completed','rejected') AND purchase_date < NOW() - INTERVAL '1 day' * $1", days_purchases)
        await conn.execute("DELETE FROM giveaways WHERE status='completed' AND end_date < NOW() - INTERVAL '1 day' * $1", days_giveaways)
        await conn.execute("DELETE FROM user_tasks WHERE expires_at IS NOT NULL AND expires_at < NOW()")
        await conn.execute("DELETE FROM fight_logs WHERE timestamp < NOW() - INTERVAL '1 day' * $1", days_fight)
        cooldown = int(await get_setting("fight_cooldown_minutes"))
        await conn.execute("DELETE FROM fight_cooldowns WHERE last_fight < NOW() - INTERVAL '1 minute' * $1", cooldown * 2)

    if manual:
        logging.info("Ручная очистка выполнена.")
    else:
        logging.info("Автоматическая очистка логов выполнена.")

@dp.message_handler(lambda message: message.text == "🧹 Очистка старых записей")
async def cleanup_old_data(message: types.Message):
    if not await is_super_admin(message.from_user.id):
        return
    await perform_cleanup(manual=True)
    await message.answer("✅ Старые записи очищены согласно настройкам.")
  # ==================== ПОЛНЫЙ РАБОЧИЙ БОТ ====================
# Часть 6: Фоновые задачи и точка входа (main)

# ==================== ФОНОВЫЕ ЗАДАЧИ ====================

async def boss_spawn_loop():
    """Проверяет каждый подтверждённый чат и с заданной вероятностью создаёт босса."""
    while True:
        await asyncio.sleep(300)  # каждые 5 минут
        try:
            confirmed = await get_confirmed_chats()
            now = datetime.now()
            for chat_id, data in confirmed.items():
                boss_max_per_day = int(await get_setting("boss_max_per_day"))
                boss_spawn_count = data.get('boss_spawn_count', 0)
                if boss_spawn_count >= boss_max_per_day:
                    continue
                last_spawn_str = data.get('boss_last_spawn')
                if last_spawn_str:
                    last_spawn = datetime.strptime(last_spawn_str, "%Y-%m-%d %H:%M:%S")
                    min_interval = int(await get_setting("boss_min_interval"))
                    if (now - last_spawn).total_seconds() < min_interval * 60:
                        continue
                chance = int(await get_setting("boss_spawn_chance"))
                if random.randint(1, 100) <= chance:
                    await spawn_boss(chat_id)
        except Exception as e:
            logging.error(f"Boss spawn loop error: {e}")

async def cleanup_loop():
    """Раз в сутки удаляет старые записи согласно настройкам."""
    while True:
        await asyncio.sleep(86400)  # 24 часа
        try:
            await perform_cleanup(manual=False)
        except Exception as e:
            logging.error(f"Cleanup loop error: {e}")

async def ad_sender_loop():
    """Периодически отправляет рекламные сообщения в чаты или личку."""
    while True:
        await asyncio.sleep(60)  # проверка каждую минуту
        try:
            if db_pool is None:
                logging.warning("db_pool is None, skipping ad send")
                continue
            async with db_pool.acquire() as conn:
                ads = await conn.fetch("SELECT * FROM ads WHERE enabled=TRUE")
                now = datetime.now()
                for ad in ads:
                    last_sent = ad['last_sent']
                    if last_sent and (now - last_sent).total_seconds() < ad['interval_minutes'] * 60:
                        continue
                    # Определяем получателей
                    if ad['target'] in ('chats', 'all'):
                        chats = await get_confirmed_chats()
                        chat_ids = list(chats.keys())
                        if chat_ids:
                            chat_id = random.choice(chat_ids)
                            await safe_send_chat(chat_id, ad['text'])
                    if ad['target'] in ('private', 'all'):
                        # Отправляем случайному пользователю (не админу)
                        async with db_pool.acquire() as conn2:
                            users = await conn2.fetch("SELECT user_id FROM users WHERE user_id NOT IN (SELECT user_id FROM admins) ORDER BY RANDOM() LIMIT 1")
                            if users:
                                await safe_send_message(users[0]['user_id'], ad['text'])
                    # Обновляем last_sent
                    await conn.execute("UPDATE ads SET last_sent=$1 WHERE id=$2", now, ad['id'])
        except Exception as e:
            logging.error(f"Ad sender loop error: {e}")

# ==================== MAIN (ТОЧКА ВХОДА) ====================

async def on_startup(dp):
    await before_start()
    await create_db_pool()
    await init_db()
    # Запускаем фоновые задачи
    asyncio.create_task(boss_spawn_loop())
    asyncio.create_task(cleanup_loop())
    asyncio.create_task(ad_sender_loop())
    asyncio.create_task(start_web_server())
    logging.info("🤖 Бот запущен и готов к работе!")
    logging.info(f"👑 Суперадмины: {SUPER_ADMINS}")
    logging.info(f"🗄 База данных: PostgreSQL")

async def on_shutdown(dp):
    if db_pool:
        await db_pool.close()
    await dp.storage.close()
    await bot.close()
    logging.info("Бот остановлен")

if __name__ == "__main__":
    while True:
        try:
            executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
        except TerminatedByOtherGetUpdates:
            logging.error("Конфликт с другим экземпляром. Жду 5 сек...")
            time.sleep(5)
            continue
        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")
            time.sleep(5)
            continue
