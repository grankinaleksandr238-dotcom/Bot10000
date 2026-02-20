# ==================== ЧАСТЬ 1: ИМПОРТЫ, НАСТРОЙКИ, БАЗА ДАННЫХ, БЕЗОПАСНАЯ ОТПРАВКА ====================

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
    InlineKeyboardButton, InputFile, CallbackQuery, Message
)
from aiogram.utils.exceptions import (
    BotBlocked, UserDeactivated, ChatNotFound, RetryAfter,
    TelegramAPIError, MessageNotModified, TerminatedByOtherGetUpdates,
    MessageToDeleteNotFound, MessageCantBeDeleted
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

if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

# Настройки по умолчанию (сбалансированы на долгую игру)
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

    # Казино и игры (шансы снижены)
    "casino_win_chance": "40",
    "casino_min_bet": "1",
    "casino_max_bet": "1000",
    "casino_multiplier": "2",
    "dice_multiplier": "2",
    "dice_win_threshold": "7",
    "guess_multiplier": "5",
    "guess_reputation": "1",
    "slots_multiplier_three": "3",
    "slots_multiplier_diamond": "5",
    "slots_multiplier_seven": "10",
    "slots_min_bet": "1",
    "slots_max_bet": "500",
    "slots_win_probability": "25",
    "roulette_color_multiplier": "2",
    "roulette_green_multiplier": "18",
    "roulette_number_multiplier": "36",
    "roulette_min_bet": "1",
    "roulette_max_bet": "500",

    # Уведомления
    "chat_notify_big_win": "1",
    "chat_notify_big_purchase": "1",
    "chat_notify_giveaway": "1",

    # Подгон
    "gift_amount": "30",
    "gift_limit_per_day": "3",
    "gift_global_limit_per_user": "4",
    "gift_cooldown": "60",

    # Рефералы
    "referral_bonus": "50",
    "referral_reputation": "2",
    "referral_required_thefts": "15",

    # Опыт
    "exp_per_casino_win": "2",
    "exp_per_casino_lose": "1",
    "exp_per_dice_win": "3",
    "exp_per_dice_lose": "1",
    "exp_per_guess_win": "4",
    "exp_per_guess_lose": "1",
    "exp_per_slots_win": "6",
    "exp_per_slots_lose": "2",
    "exp_per_roulette_win": "5",
    "exp_per_roulette_lose": "1",
    "exp_per_theft_success": "8",
    "exp_per_theft_fail": "2",
    "exp_per_theft_defense": "5",
    "exp_per_game_win": "12",
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

    # Качалка
    "gym_strength_cost": "10",
    "gym_agility_cost": "10",
    "gym_defense_cost": "10",

    # Бизнесы
    "business_base_price": "5000",
    "business_price_increase": "1.5",
    "business_income_per_level": "3",
    "business_upgrade_cost_per_level": "2500",

    # Контрабанда
    "smuggle_min_duration": "30",
    "smuggle_max_duration": "120",
    "smuggle_success_chance": "55",
    "smuggle_caught_chance": "30",
    "smuggle_lost_chance": "15",
    "smuggle_base_amount": "8",
    "smuggle_authority_multiplier": "0.1",
    "smuggle_cooldown_minutes": "60",
    "smuggle_fail_penalty_minutes": "30",

    # Очистка логов (в днях)
    "cleanup_days_fight_logs": "7",
    "cleanup_days_bosses": "7",
    "cleanup_days_auctions": "30",
    "cleanup_days_purchases": "30",
    "cleanup_days_giveaways": "30",
    "cleanup_days_user_tasks": "30",
    "cleanup_days_smuggle": "30",
    "cleanup_days_authority_offers": "30",

    # Автоудаление команд (секунд)
    "auto_delete_commands_seconds": "30",

    # Продажа авторитета
    "min_authority_price": "1",
}

# Константы
ITEMS_PER_PAGE = 10
BIG_WIN_THRESHOLD = 100
BIG_PURCHASE_THRESHOLD = 100
MAX_ROOMS = 20
MIN_PLAYERS = 2
MAX_PLAYERS = 5
MIN_BET = 3
MAX_COMPLETED_GIVEAWAYS = 10

# Права админов
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

# ==================== ТЕКСТОВЫЕ ФРАЗЫ (расширенные) ====================
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

SMUGGLE_START_PHRASES = [
    "🛥 Ты отправился в контрабандный рейс! В этот раз груз – {cargo}. Вернёшься примерно {end_time}.",
    "📦 Груз загружен, судно вышло в море. Капитан обещает вернуться к {end_time}. Груз: {cargo}.",
    "🚤 Ты взял курс на нейтральные воды. На борту – {cargo}. Финиш ориентировочно {end_time}.",
    "⚓ Под покровом ночи ты вышел в море. Товар: {cargo}. Жди возвращения к {end_time}.",
]

SMUGGLE_CARGO = [
    "ящики с сигарами", "партия виски", "контрабандное оружие", "драгоценные камни",
    "золотые слитки", "антиквариат", "редкие лекарства", "элитный алкоголь",
    "техника без пошлин", "запрещённые книги", "экзотические животные", "наркотические вещества"
]

SMUGGLE_SUCCESS_PHRASES = [
    "✅ Рейс завершён успешно! Ты привёз {amount} ед. контрабанды. Таможня не заметила.",
    "💰 Товар доставлен заказчику. Твоя доля: {amount} ед. Отличная работа!",
    "🎉 Пограничников удалось обмануть! +{amount} контрабанды.",
    "🚢 Корабль благополучно вернулся в порт. Груз цел: {amount} ед.",
]

SMUGGLE_CAUGHT_PHRASES = [
    "🚨 Береговая охрана перехватила твоё судно! Ты потерял груз и теперь отсиживаешься.",
    "⛓ Полиция накрыла явочную квартиру. Придётся залечь на дно (кулдаун увеличен).",
    "👮‍♂️ Менты вышли на след. Контрабанда конфискована. Тебя объявили в розыск.",
    "🔫 Перестрелка с таможенниками! Пришлось бросить груз и спасаться бегством.",
]

SMUGGLE_LOST_PHRASES = [
    "🌊 Шторм уничтожил твоё судно! Ты ничего не привёз.",
    "💥 Корабль напоролся на рифы. Груз утонул.",
    "🔥 Двигатель взорвался. Придётся начинать сначала.",
    "🏝 Ты сел на мель на необитаемом острове. Спасся, но без груза.",
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

THEFT_CHOICE_PHRASES = [
    "🔫 Выбери цель:",
    "💢 Кого будем грабить?",
    "😈 Куда направим бандитские лапы?"
]

THEFT_COOLDOWN_PHRASES = [
    "⏳ Ты ещё не остыл. Подожди {minutes} мин.",
    "🕐 Полегче! Отдохни {minutes} минут.",
    "😴 Слишком часто. Возвращайся через {minutes} мин."
]

THEFT_NO_MONEY_PHRASES = [
    "😕 У тебя нет баксов на подготовку к краже!",
    "💸 Сначала заработай!",
    "💰 Пустой карман – не до криминала."
]

THEFT_SUCCESS_PHRASES = [
    "🔫 Отлично! Ты украл {amount} баксов у {target}!",
    "💰 Хорошо пошло! {amount} баксов у {target} теперь твои!",
    "🦹‍♂️ Удачная кража! +{amount} от {target}",
    "😈 Ты невидимка! +{amount} баксов!"
]

THEFT_FAIL_PHRASES = [
    "😢 Облом, тебя спалили! Ничего не украл.",
    "🚨 {target} оказался бдительным!",
    "👮‍♂️ Пришлось сваливать, 0 баксов.",
    "💔 Не фортануло."
]

THEFT_DEFENSE_PHRASES = [
    "🛡️ {target} отразил атаку! Ты потерял {penalty} баксов.",
    "💥 Бабах! {target} выставил защиту, ты лишился {penalty} баксов.",
    "😱 Засада! Ты потерял {penalty} баксов."
]

THEFT_VICTIM_DEFENSE_PHRASES = [
    "🛡️ Твоя защита сработала! {attacker} ничего не украл и потерял {penalty} баксов.",
    "💪 Отлично! Отбил атаку {attacker} и получил {penalty} баксов.",
    "😎 Ха! {attacker} думал поживиться, а сам потерял {penalty} баксов."
]

CHAT_WIN_PHRASES = [
    "🔥 {name} только что выиграл {amount} баксов в казино!",
    "💰 Удача на стороне {name}: +{amount} баксов!",
    "🎰 {name} сорвал куш — {amount} баксов!"
]

CHAT_PURCHASE_PHRASES = [
    "🛒 {name} купил {item} за {price} баксов!",
    "🎁 {name} приобрёл {item}! Админ уже в пути.",
    "💎 {name} потратил {price} баксов на {item}!"
]

CHAT_GIVEAWAY_PHRASES = [
    "🎁 Не пропусти розыгрыш! Осталось {time}",
    "⏰ Напоминание: розыгрыш {prize} заканчивается через {time}",
    "🔥 Участвуй в розыгрыше {prize}! Осталось {time}"
]

# ==================== МИДЛВАРЬ ДЛЯ ТРОТТЛИНГА ====================
class ThrottlingMiddleware(BaseMiddleware):
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

# Мидлварь будет установлен после определения функций is_super_admin

# ==================== ФУНКЦИИ ПРОВЕРКИ ПРАВ ====================
async def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS

async def is_junior_admin(user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchval("SELECT user_id FROM admins WHERE user_id=$1", user_id)
    return row is not None

async def is_admin(user_id: int) -> bool:
    return await is_super_admin(user_id) or await is_junior_admin(user_id)

async def has_permission(user_id: int, permission: str) -> bool:
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
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE admins SET permissions=$1 WHERE user_id=$2",
            json.dumps(permissions), user_id
        )

# Устанавливаем мидлварь после определения функций
dp.middleware.setup(ThrottlingMiddleware(rate_limit=0.5))

# ==================== БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ ====================
async def safe_send_message(user_id: int, text: str, **kwargs):
    if kwargs.get('parse_mode') == 'HTML':
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
    asyncio.create_task(safe_send_message(user_id, text, **kwargs))

async def safe_send_chat(chat_id: int, text: str, **kwargs):
    if kwargs.get('parse_mode') == 'HTML':
        text = html.escape(text).replace('&#x27;', "'")
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send to chat {chat_id}: {e}")

# ==================== АВТОУДАЛЕНИЕ СООБЩЕНИЙ ====================
async def can_delete_message(chat_id: int, message: types.Message) -> bool:
    try:
        if chat_id > 0:
            return message.from_user.id == bot.id
        else:
            member = await bot.get_chat_member(chat_id, bot.id)
            return member.status in ['administrator', 'creator']
    except:
        return False

async def delete_after(message: types.Message, seconds: int):
    await asyncio.sleep(seconds)
    if await can_delete_message(message.chat.id, message):
        try:
            await message.delete()
        except (MessageToDeleteNotFound, MessageCantBeDeleted):
            pass
        except Exception:
            pass

async def auto_delete_reply(message: types.Message, text: str, delete_seconds: int = None, **kwargs):
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
    if message.chat.type == 'private':
        return
    if delete_seconds is None:
        delete_seconds = int(await get_setting("auto_delete_commands_seconds"))
    confirmed = await get_confirmed_chats()
    chat_data = confirmed.get(message.chat.id)
    if chat_data and not chat_data.get('auto_delete_enabled', True):
        return
    asyncio.create_task(delete_after(message, delete_seconds))

# ==================== ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ С ПОВТОРНЫМИ ПОПЫТКАМИ ====================
async def create_db_pool(retries: int = 5, delay: int = 3):
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
                raise

# ==================== ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ ====================
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
                last_gift_time TEXT,
                gift_count_today INTEGER DEFAULT 0,
                global_authority INTEGER DEFAULT 0,
                smuggle_goods INTEGER DEFAULT 0,
                smuggle_success INTEGER DEFAULT 0,
                smuggle_fail INTEGER DEFAULT 0
            )
        ''')

        # Таблица бизнесов пользователей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_businesses (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                business_name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                last_collection TEXT,
                accumulated INTEGER DEFAULT 0,
                UNIQUE(user_id, business_name)
            )
        ''')

        # Таблица подтверждённых чатов (с колонкой last_boss_status_time)
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
                boss_spawn_count INTEGER DEFAULT 0,
                auto_delete_enabled BOOLEAN DEFAULT TRUE,
                last_boss_status_time TEXT
            )
        ''')

        # Запросы на подтверждение чатов
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

        # Боссы
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
                attack_time TEXT,
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
                referred_date TEXT,
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
                purchase_date TEXT,
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
                created_at TEXT
            )
        ''')

        # Активации промокодов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS promo_activations (
                user_id BIGINT,
                promo_code TEXT,
                activated_at TEXT,
                PRIMARY KEY (user_id, promo_code)
            )
        ''')

        # Розыгрыши
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
                winners_list TEXT,
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
                added_date TEXT,
                permissions TEXT DEFAULT '[]'
            )
        ''')

        # Забаненные
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id BIGINT PRIMARY KEY,
                banned_by BIGINT,
                banned_date TEXT,
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
                created_at TEXT,
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
                completed_at TEXT,
                expires_at TEXT,
                status TEXT DEFAULT 'completed',
                PRIMARY KEY (user_id, task_id)
            )
        ''')

        # Мультиплеерные игры
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

        # Игроки в мультиплеере
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

        # Кулдауны боёв
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fight_cooldowns (
                chat_id BIGINT,
                user_id BIGINT,
                last_fight TIMESTAMP,
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

        # Контрабандные рейсы
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS smuggle_runs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                chat_id BIGINT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                status TEXT DEFAULT 'in_progress',
                result TEXT,
                smuggle_amount INTEGER DEFAULT 0,
                notified BOOLEAN DEFAULT FALSE
            )
        ''')
                # Контрабандные рейсы
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS smuggle_runs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                chat_id BIGINT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                status TEXT DEFAULT 'in_progress',
                result TEXT,
                smuggle_amount INTEGER DEFAULT 0,
                notified BOOLEAN DEFAULT FALSE
            )
        ''')

        # ========== ВСТАВЬ ЭТОТ КОД СЮДА ==========
        # Таблица кулдаунов контрабанды
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS smuggle_cooldowns (
                user_id BIGINT PRIMARY KEY,
                cooldown_until TIMESTAMP
            )
        ''')
        # =========================================

        # Индексы для ускорения
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC)")
        # ... остальные индексы

        # Индексы для ускорения
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_reputation ON users(reputation DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_total_spent ON users(total_spent DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username_lower ON users(LOWER(username))")
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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_fight_cooldowns_chat ON fight_cooldowns(chat_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_fight_logs_timestamp ON fight_logs(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ads_enabled ON ads(enabled)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_authority_offers_status ON authority_offers(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_authority_offers_seller ON authority_offers(seller_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_smuggle_runs_user ON smuggle_runs(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_smuggle_runs_end ON smuggle_runs(end_time)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_businesses_user ON user_businesses(user_id)")

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
    async with db_pool.acquire() as conn:
        for key, value in DEFAULT_SETTINGS.items():
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                key, value
            )

# ==================== РАБОТА С НАСТРОЙКАМИ (КЭШИРОВАНИЕ) ====================
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

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ЧАТАМИ И КАНАЛАМИ ====================
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

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def progress_bar(current, total, length=10):
    if total <= 0:
        return "⬜" * length
    filled = int(current / total * length)
    return "🟩" * filled + "⬜" * (length - filled)

def format_time_remaining(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
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

async def notify_chats(message_text: str):
    confirmed = await get_confirmed_chats()
    for chat_id, data in confirmed.items():
        if not data.get('notify_enabled', True):
            continue
        await safe_send_chat(chat_id, message_text)

async def is_banned(user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchval("SELECT user_id FROM banned_users WHERE user_id=$1", user_id)
    return row is not None

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
          # ==================== ЧАСТЬ 2: ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ====================

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

# ==================== ФУНКЦИИ ДЛЯ БИЗНЕСОВ ====================

async def get_business_price(base_price: int, level: int) -> int:
    increase = float(await get_setting("business_price_increase"))
    return int(base_price * (increase ** (level - 1)))

async def get_business_income(level: int) -> int:
    per_level = int(await get_setting("business_income_per_level"))
    return level * per_level

async def get_upgrade_cost(level: int) -> int:
    base_upgrade = int(await get_setting("business_upgrade_cost_per_level"))
    increase = float(await get_setting("business_price_increase"))
    return int(base_upgrade * (increase ** (level - 1)))

async def create_user_business(user_id: int, business_name: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_businesses (user_id, business_name, level, last_collection, accumulated) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (user_id, business_name) DO NOTHING",
            user_id, business_name, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0
        )

async def update_business_income(user_id: int, conn=None):
    async def _update(conn):
        now = datetime.now()
        businesses = await conn.fetch(
            "SELECT * FROM user_businesses WHERE user_id=$1",
            user_id
        )
        for biz in businesses:
            if biz['last_collection']:
                try:
                    last_col = datetime.strptime(biz['last_collection'], "%Y-%m-%d %H:%M:%S")
                    hours_passed = int((now - last_col).total_seconds() // 3600)
                    if hours_passed > 0:
                        income_per_hour = await get_business_income(biz['level'])
                        new_accum = biz['accumulated'] + hours_passed * income_per_hour
                        await conn.execute(
                            "UPDATE user_businesses SET accumulated=$1, last_collection=$2 WHERE id=$3",
                            new_accum, now.strftime("%Y-%m-%d %H:%M:%S"), biz['id']
                        )
                except:
                    pass
    if conn:
        await _update(conn)
    else:
        async with db_pool.acquire() as new_conn:
            await _update(new_conn)

async def collect_business_income(user_id: int, business_id: int) -> Optional[int]:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            biz = await conn.fetchrow("SELECT * FROM user_businesses WHERE id=$1 AND user_id=$2", business_id, user_id)
            if not biz or biz['accumulated'] == 0:
                return None
            amount_cents = biz['accumulated']
            coins = amount_cents // 100
            remainder = amount_cents % 100
            await update_user_balance(user_id, coins, conn=conn)
            await conn.execute(
                "UPDATE user_businesses SET accumulated=$1, last_collection=$2 WHERE id=$3",
                remainder, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), business_id
            )
            return coins

async def upgrade_business(user_id: int, business_id: int) -> Tuple[bool, str]:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            biz = await conn.fetchrow("SELECT * FROM user_businesses WHERE id=$1 AND user_id=$2", business_id, user_id)
            if not biz:
                return False, "Бизнес не найден."
            current_level = biz['level']
            cost = await get_upgrade_cost(current_level)
            balance = await get_user_balance(user_id)
            if balance < cost:
                return False, f"Недостаточно баксов. Нужно {cost}."
            await update_user_balance(user_id, -cost, conn=conn)
            await conn.execute(
                "UPDATE user_businesses SET level = level + 1 WHERE id=$1",
                business_id
            )
            return True, f"✅ Бизнес улучшен до уровня {current_level + 1}!"

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

async def can_fight(chat_id: int, user_id: int) -> Tuple[bool, int]:
    cooldown = int(await get_setting("fight_cooldown_minutes"))
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_fight FROM fight_cooldowns WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)
        if row and row['last_fight']:
            diff = datetime.now() - row['last_fight']
            remaining = cooldown * 60 - diff.total_seconds()
            if remaining > 0:
                return False, int(remaining)
        return True, 0

async def set_fight_cooldown(chat_id: int, user_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO fight_cooldowns (chat_id, user_id, last_fight)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET last_fight = $3
        ''', chat_id, user_id, datetime.now())

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
    "Сальваторе Теста", "Карло Гамбино", "Пол Кастеллано", "Винсент Джиганте",
    "Крёстный отец", "Мафиози", "Гангстер", "Рэкетир"
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
            chat_id, name, level, hp, hp, now.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at.strftime("%Y-%m-%d %H:%M:%S"), reward, [], 'active', image_file_id, description
        )
        await conn.execute(
            "UPDATE confirmed_chats SET boss_last_spawn=$1, boss_spawn_count = boss_spawn_count + 1 WHERE chat_id=$2",
            now.strftime("%Y-%m-%d %H:%M:%S"), chat_id
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

async def slots_spin() -> Tuple[List[str], int, bool]:
    symbols = ['🍒', '🍋', '🍊', '7️⃣', '💎']
    result = [random.choice(symbols) for _ in range(3)]
    if result[0] == result[1] == result[2]:
        if result[0] == '7️⃣':
            multiplier = int(await get_setting("slots_multiplier_seven"))
        elif result[0] == '💎':
            multiplier = int(await get_setting("slots_multiplier_diamond"))
        else:
            multiplier = int(await get_setting("slots_multiplier_three"))
        return result, multiplier, True
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        return result, 2, True
    else:
        return result, 0, False

def format_slots_result(symbols: List[str]) -> str:
    return " | ".join(symbols)

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

# ==================== ФУНКЦИИ ДЛЯ КОНТРАБАНДЫ ====================

async def check_smuggle_cooldown(user_id: int) -> Tuple[bool, int]:
    """
    Проверяет, может ли пользователь отправиться в новый рейс.
    Возвращает (можно ли, сколько секунд осталось).
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT cooldown_until FROM smuggle_cooldowns WHERE user_id=$1", user_id)
        if row and row['cooldown_until']:
            if isinstance(row['cooldown_until'], str):
                cooldown_until = datetime.strptime(row['cooldown_until'], "%Y-%m-%d %H:%M:%S")
            else:
                cooldown_until = row['cooldown_until']
            
            remaining = (cooldown_until - datetime.now()).total_seconds()
            if remaining > 0:
                return False, int(remaining)
    return True, 0

async def set_smuggle_cooldown(user_id: int, penalty: int = 0):
    """
    Устанавливает кулдаун для команды smuggle с учётом штрафа.
    """
    base = int(await get_setting("smuggle_cooldown_minutes"))
    cooldown_until = datetime.now() + timedelta(minutes=base + penalty)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO smuggle_cooldowns (user_id, cooldown_until)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET cooldown_until = $2
        ''', user_id, cooldown_until.strftime("%Y-%m-%d %H:%M:%S"))

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
    days_bosses = int(await get_setting("cleanup_days_bosses"))
    days_auctions = int(await get_setting("cleanup_days_auctions"))
    days_purchases = int(await get_setting("cleanup_days_purchases"))
    days_giveaways = int(await get_setting("cleanup_days_giveaways"))
    days_tasks = int(await get_setting("cleanup_days_user_tasks"))
    days_fight = int(await get_setting("cleanup_days_fight_logs"))
    days_smuggle = int(await get_setting("cleanup_days_smuggle"))
    days_offers = int(await get_setting("cleanup_days_authority_offers"))

    now = datetime.now()
    # Для текстовых дат
    cutoff_bosses = (now - timedelta(days=days_bosses)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_purchases = (now - timedelta(days=days_purchases)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_giveaways = (now - timedelta(days=days_giveaways)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_tasks = (now - timedelta(days=days_tasks)).strftime("%Y-%m-%d %H:%M:%S")
    # Для TIMESTAMP
    cutoff_auctions = now - timedelta(days=days_auctions)
    cutoff_fight = now - timedelta(days=days_fight)
    cutoff_offers = now - timedelta(days=days_offers)
    # Для smuggle_runs (поле end_time TEXT) – оставляем строку
    cutoff_smuggle = (now - timedelta(days=days_smuggle)).strftime("%Y-%m-%d %H:%M:%S")

    async with db_pool.acquire() as conn:
        # Таблицы с TEXT датами
        await conn.execute("DELETE FROM bosses WHERE status IN ('defeated', 'expired') AND spawned_at < $1", cutoff_bosses)
        await conn.execute("DELETE FROM boss_attacks WHERE attack_time < $1", cutoff_bosses)
        await conn.execute("DELETE FROM purchases WHERE status IN ('completed','rejected') AND purchase_date < $1", cutoff_purchases)
        await conn.execute("DELETE FROM giveaways WHERE status='completed' AND end_date < $1", cutoff_giveaways)
        await conn.execute("DELETE FROM user_tasks WHERE expires_at IS NOT NULL AND expires_at < $1", cutoff_tasks)
        await conn.execute("DELETE FROM smuggle_runs WHERE status IN ('completed', 'failed') AND end_time < $1", cutoff_smuggle)

        # Таблицы с TIMESTAMP
        await conn.execute("DELETE FROM auctions WHERE status='ended' AND end_time < $1", cutoff_auctions)
        await conn.execute("DELETE FROM fight_logs WHERE timestamp < $1", cutoff_fight)
        await conn.execute("DELETE FROM authority_offers WHERE status='active' AND created_at < $1", cutoff_offers)
        await conn.execute("DELETE FROM authority_offers WHERE status IN ('sold', 'cancelled')")

        # Очистка старых кулдаунов
        cooldown_minutes = int(await get_setting("fight_cooldown_minutes"))
        cutoff_cooldown = now - timedelta(minutes=cooldown_minutes * 2)
        await conn.execute("DELETE FROM global_cooldowns WHERE last_used < $1", cutoff_cooldown)

    if manual:
        logging.info("Ручная очистка выполнена.")
    else:
        logging.info("Автоматическая очистка выполнена.")

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
      # ==================== ЧАСТЬ 3: СОСТОЯНИЯ FSM И КЛАВИАТУРЫ ====================

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
    photo = State()

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

class SlotsBet(StatesGroup):
    amount = State()

class RouletteBet(StatesGroup):
    amount = State()
    bet_type = State()
    number = State()

class PromoActivate(StatesGroup):
    code = State()

class TheftTarget(StatesGroup):
    target = State()

class FindUser(StatesGroup):
    query = State()

class AddJuniorAdmin(StatesGroup):
    user_id = State()
    permissions = State()

class EditAdminPermissions(StatesGroup):
    user_id = State()
    selecting_permissions = State()
    confirm = State()

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
    image = State()

class DeleteBoss(StatesGroup):
    boss_id = State()
    confirm = State()

class CreateAuction(StatesGroup):
    item_name = State()
    description = State()
    start_price = State()
    end_time = State()
    target_price = State()
    photo = State()

class AuctionBid(StatesGroup):
    auction_id = State()
    amount = State()

class CancelAuction(StatesGroup):
    auction_id = State()

class CreateAd(StatesGroup):
    text = State()
    interval = State()
    target = State()

class SellAuthority(StatesGroup):
    amount = State()
    price = State()

class BuyAuthority(StatesGroup):
    offer_id = State()

class EditAd(StatesGroup):
    text = State()
    interval = State()
    target = State()

class BuyBusiness(StatesGroup):
    business_name = State()
    confirming = State()

class UpgradeBusiness(StatesGroup):
    business_id = State()
    confirming = State()

# ==================== КЛАВИАТУРЫ ====================

# ----- Общие клавиатуры -----
def back_keyboard():
    """Простая клавиатура с кнопкой 'Назад'."""
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Назад")]], resize_keyboard=True)

def main_menu_keyboard(is_admin: bool = False):
    """Главное меню пользователя."""
    buttons = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус")],
        [KeyboardButton(text="🛒 Магазин подарков"), KeyboardButton(text="🎰 Казино")],
        [KeyboardButton(text="🎟 Промокод"), KeyboardButton(text="🏆 Топ игроков")],
        [KeyboardButton(text="💰 Мои покупки"), KeyboardButton(text="🔫 Ограбить")],
        [KeyboardButton(text="🎲 Игры"), KeyboardButton(text="⭐️ Репутация")],
        [KeyboardButton(text="📋 Задания"), KeyboardButton(text="🔗 Рефералка")],
        [KeyboardButton(text="🎁 Розыгрыши"), KeyboardButton(text="📊 Уровень")],
        [KeyboardButton(text="🏷 Аукцион"), KeyboardButton(text="🏪 Мои бизнесы")],
        [KeyboardButton(text="💼 Продажа авторитета")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def cancel_keyboard():
    """Клавиатура с кнопкой отмены (для FSM)."""
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

# ----- Клавиатуры для казино и игр -----
def casino_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎰 Играть в казино"), KeyboardButton(text="🎲 Кости")],
        [KeyboardButton(text="🔢 Угадай число"), KeyboardButton(text="🍒 Слоты")],
        [KeyboardButton(text="🎡 Рулетка"), KeyboardButton(text="◀️ Назад")],
    ], resize_keyboard=True)

def games_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Комнатная игра 21")],
        [KeyboardButton(text="📋 Список комнат")],
        [KeyboardButton(text="🏆 Топ мультиплеера")],
        [KeyboardButton(text="ℹ️ Правила игры")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def room_control_keyboard(game_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать игру", callback_data=f"start_game_{game_id}")],
        [InlineKeyboardButton(text="❌ Закрыть комнату", callback_data=f"close_room_{game_id}")]
    ])

def room_action_keyboard(can_double: bool = True):
    buttons = [
        [InlineKeyboardButton(text="🎯 Ещё", callback_data="room_hit"),
         InlineKeyboardButton(text="🛑 Хватит", callback_data="room_stand")]
    ]
    second_row = []
    if can_double:
        second_row.append(InlineKeyboardButton(text="💰 Удвоить", callback_data="room_double"))
    second_row.append(InlineKeyboardButton(text="🏳️ Сдаться", callback_data="room_surrender"))
    buttons.append(second_row)
    buttons.append([InlineKeyboardButton(text="💬 Написать в чат", callback_data="room_chat")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def leave_room_keyboard(game_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Выйти из комнаты", callback_data=f"leave_room_{game_id}")]
    ])

# ----- Клавиатуры для кражи -----
def theft_choice_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎲 Случайная цель")],
        [KeyboardButton(text="👤 Выбрать пользователя")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

# ----- Клавиатуры для авторитета -----
def authority_shop_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Продать авторитет")],
        [KeyboardButton(text="🛒 Купить авторитет")],
        [KeyboardButton(text="📋 Мои активные предложения")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def authority_offers_keyboard(offers: List[dict]):
    kb = []
    for offer in offers:
        kb.append([InlineKeyboardButton(
            text=f"ID {offer['id']}: {offer['amount']} ед. по {offer['price_per_unit']} баксов/ед.",
            callback_data=f"buy_offer_{offer['id']}"
        )])
    kb.append([InlineKeyboardButton(text="« Назад", callback_data="authority_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ----- Клавиатуры для бизнесов -----
def business_main_keyboard(businesses: List[dict]):
    kb = []
    for biz in businesses:
        kb.append([InlineKeyboardButton(
            text=f"{biz['business_name']} (ур. {biz['level']}) | Накоплено: {biz['accumulated']//100} баксов",
            callback_data=f"biz_view_{biz['id']}"
        )])
    kb.append([InlineKeyboardButton(text="🛒 Купить новый бизнес", callback_data="buy_business_menu")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="biz_back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def business_actions_keyboard(business_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Собрать доход", callback_data=f"biz_collect_{business_id}")],
        [InlineKeyboardButton(text="⬆️ Улучшить", callback_data=f"biz_upgrade_{business_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="biz_back")]
    ])

def business_buy_keyboard(available_names: List[str]):
    kb = []
    for name in available_names:
        kb.append([InlineKeyboardButton(text=name, callback_data=f"buy_biz_{name}")])
    kb.append([InlineKeyboardButton(text="◀️ Отмена", callback_data="buy_biz_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ----- Клавиатуры для розыгрышей -----
def giveaways_user_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Активные розыгрыши")],
        [KeyboardButton(text="🏁 Завершённые розыгрыши")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def active_giveaways_keyboard(giveaways: List[dict], page: int, total_pages: int):
    kb = []
    for gw in giveaways:
        kb.append([InlineKeyboardButton(
            text=f"#{gw['id']} | {gw['prize']} | до {gw['end_date']}",
            callback_data=f"active_gw_{gw['id']}"
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"active_gw_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"active_gw_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("« Назад", callback_data="active_gw_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def completed_giveaways_keyboard(giveaways: List[dict], page: int, total_pages: int):
    kb = []
    for gw in giveaways:
        kb.append([InlineKeyboardButton(
            text=f"#{gw['id']} | {gw['prize']} | Победители: {gw['winners_list'][:20]}",
            callback_data=f"completed_gw_{gw['id']}"
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"completed_gw_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"completed_gw_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("« Назад", callback_data="completed_gw_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def giveaway_detail_keyboard(giveaway_id: int, is_participant: bool):
    kb = []
    if not is_participant:
        kb.append([InlineKeyboardButton("✅ Участвовать", callback_data=f"join_giveaway_{giveaway_id}")])
    else:
        kb.append([InlineKeyboardButton("❌ Отказаться", callback_data=f"leave_giveaway_{giveaway_id}")])
    kb.append([InlineKeyboardButton("« Назад", callback_data="active_gw_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ----- Клавиатуры для аукционов -----
def auction_list_keyboard(auctions: List[dict], page: int, total_pages: int):
    kb = []
    for a in auctions:
        kb.append([InlineKeyboardButton(
            text=f"{a['item_name']} | Текущая ставка: {a['current_price']}",
            callback_data=f"auction_view_{a['id']}"
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"auction_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"auction_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("« Назад", callback_data="auction_list_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def auction_detail_keyboard(auction_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💰 Сделать ставку", callback_data=f"auction_bid_{auction_id}")],
        [InlineKeyboardButton("« Назад", callback_data="auction_list")]
    ])

# ----- Клавиатуры для подтверждения чатов -----
def confirm_chat_inline(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_chat_{chat_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_chat_{chat_id}")]
    ])

def subscription_inline(not_subscribed: List[Tuple[str, str]]):
    kb = []
    for title, link in not_subscribed:
        if link:
            kb.append([InlineKeyboardButton(text=f"📢 {title}", url=link)])
        else:
            kb.append([InlineKeyboardButton(text=f"📢 {title}", callback_data="no_link")])
    kb.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")])
    return InlineKeyboardMarkup(row_width=1, inline_keyboard=kb)

# ----- Административные клавиатуры -----
def admin_main_keyboard(permissions: List[str]):
    buttons = []
    row = []
    if "manage_users" in permissions:
        row.append(KeyboardButton("👥 Пользователи"))
    if "manage_shop" in permissions:
        row.append(KeyboardButton("🛒 Магазин"))
    if "manage_auctions" in permissions:
        row.append(KeyboardButton("🏷 Аукцион"))
    if row:
        buttons.append(row)

    row = []
    if "manage_bosses" in permissions:
        row.append(KeyboardButton("👾 Боссы"))
    if "manage_tasks" in permissions:
        row.append(KeyboardButton("📋 Задания"))
    if "manage_giveaways" in permissions:
        row.append(KeyboardButton("🎁 Розыгрыши"))
    if row:
        buttons.append(row)

    row = []
    if "manage_channels" in permissions:
        row.append(KeyboardButton("📢 Каналы"))
    if "manage_chats" in permissions:
        row.append(KeyboardButton("🤖 Чаты"))
    if "manage_helpers" in permissions:
        row.append(KeyboardButton("⚔️ Помощники"))
    if row:
        buttons.append(row)

    row = []
    if "manage_promocodes" in permissions:
        row.append(KeyboardButton("🎫 Промокоды"))
    if "manage_ads" in permissions:
        row.append(KeyboardButton("📢 Реклама"))
    if row:
        buttons.append(row)

    row = []
    if "manage_bans" in permissions:
        row.append(KeyboardButton("🔨 Блокировки"))
    if "broadcast" in permissions:
        row.append(KeyboardButton("📢 Рассылка"))
    if row:
        buttons.append(row)

    row = []
    if "view_stats" in permissions:
        row.append(KeyboardButton("📊 Статистика"))
    if "edit_settings" in permissions:
        row.append(KeyboardButton("⚙️ Настройки"))
    if "cleanup" in permissions:
        row.append(KeyboardButton("🧹 Очистка"))
    if "manage_admins" in permissions:
        row.append(KeyboardButton("➕ Админы"))
    if row:
        buttons.append(row)

    buttons.append([KeyboardButton("◀️ Назад в главное меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_users_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("💰 Начислить баксы"), KeyboardButton("💸 Списать баксы")],
        [KeyboardButton("⭐️ Начислить репутацию"), KeyboardButton("🔻 Снять репутацию")],
        [KeyboardButton("📈 Начислить опыт"), KeyboardButton("🔝 Установить уровень")],
        [KeyboardButton("👥 Найти пользователя")],
        [KeyboardButton("📊 Экспорт пользователей")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_shop_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Добавить товар")],
        [KeyboardButton("➖ Удалить товар")],
        [KeyboardButton("✏️ Редактировать товар")],
        [KeyboardButton("📋 Список товаров")],
        [KeyboardButton("🛍️ Список покупок")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_giveaway_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Создать розыгрыш")],
        [KeyboardButton("📋 Активные розыгрыши")],
        [KeyboardButton("✅ Завершить розыгрыш")],
        [KeyboardButton("📋 Завершённые розыгрыши (админ)")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_channel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Добавить канал")],
        [KeyboardButton("➖ Удалить канал")],
        [KeyboardButton("📋 Список каналов")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_promo_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Создать промокод")],
        [KeyboardButton("📋 Список промокодов")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_tasks_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Создать задание")],
        [KeyboardButton("📋 Список заданий")],
        [KeyboardButton("❌ Удалить задание")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_ban_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("🔨 Заблокировать пользователя")],
        [KeyboardButton("🔓 Разблокировать пользователя")],
        [KeyboardButton("📋 Список заблокированных")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_admins_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Добавить админа")],
        [KeyboardButton("✏️ Редактировать права админа")],
        [KeyboardButton("➖ Удалить админа")],
        [KeyboardButton("📋 Список админов")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_chats_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("📋 Список запросов на подтверждение")],
        [KeyboardButton("✅ Подтвердить чат")],
        [KeyboardButton("❌ Отклонить запрос")],
        [KeyboardButton("📋 Список подтверждённых чатов")],
        [KeyboardButton("🗑 Удалить чат из подтверждённых")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_boss_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("📋 Активные боссы")],
        [KeyboardButton("⚔️ Создать босса вручную")],
        [KeyboardButton("❌ Удалить босса (по ID)")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_auction_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Создать аукцион")],
        [KeyboardButton("📋 Активные аукционы")],
        [KeyboardButton("❌ Отменить аукцион")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_ad_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Создать рекламу")],
        [KeyboardButton("📋 Список рекламы")],
        [KeyboardButton("✏️ Редактировать рекламу")],
        [KeyboardButton("❌ Удалить рекламу")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_helper_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("📋 Активные помощники")],
        [KeyboardButton("📊 Топы чатов")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def settings_categories_keyboard():
    """Клавиатура категорий настроек."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("⚙️ Кража")],
        [KeyboardButton("⚙️ Казино и игры")],
        [KeyboardButton("⚙️ Опыт и уровни")],
        [KeyboardButton("⚙️ Боссы")],
        [KeyboardButton("⚙️ Помощники")],
        [KeyboardButton("⚙️ Аукцион")],
        [KeyboardButton("⚙️ Подгон")],
        [KeyboardButton("⚙️ Контрабанда")],
        [KeyboardButton("⚙️ Рефералы")],
        [KeyboardButton("⚙️ Очистка логов")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def settings_param_keyboard(params: List[Tuple[str, str]], category: str):
    """Инлайн-клавиатура с параметрами категории для редактирования."""
    kb = []
    for key, desc in params:
        kb.append([InlineKeyboardButton(text=desc, callback_data=f"edit_{key}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"settings_back_{category}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def purchase_action_keyboard(purchase_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"purchase_done_{purchase_id}"),
         InlineKeyboardButton(text="❌ Отказ", callback_data=f"purchase_reject_{purchase_id}")]
    ])

# ----- Вспомогательная клавиатура для топа в чате (инлайн) -----
def chat_top_navigation(order: str, page: int, has_prev: bool, has_next: bool):
    kb = []
    row = []
    if has_prev:
        row.append(InlineKeyboardButton("⬅️", callback_data=f"chat_top_page_{order}_{page-1}"))
    row.append(InlineKeyboardButton(f"{page}", callback_data="noop"))
    if has_next:
        row.append(InlineKeyboardButton("➡️", callback_data=f"chat_top_page_{order}_{page+1}"))
    kb.append(row)
    kb.append([
        InlineKeyboardButton("📊 По авторитету", callback_data="chat_top_authority_1"),
        InlineKeyboardButton("💥 По урону", callback_data="chat_top_damage_1"),
        InlineKeyboardButton("⚔️ По боям", callback_data="chat_top_fights_1")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ----- Клавиатура для отмены в состояниях (inline, если нужно) -----
def cancel_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])
  # ==================== ЧАСТЬ 4: ПОЛЬЗОВАТЕЛЬСКИЕ ХЕНДЛЕРЫ (ЛИЧНЫЕ СООБЩЕНИЯ) ====================

# ==================== ГЛОБАЛЬНЫЙ ОБРАБОТЧИК /cancel ====================
@dp.message_handler(commands=['cancel'], state='*')
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.answer("❌ Действие отменено.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))

# ==================== СТАРТ И ГЛАВНОЕ МЕНЮ ====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        await message.answer("⛔ Вы заблокированы в боте.")
        return

    # Реферальная система
    args = message.get_args()
    if args and args.startswith('ref'):
        try:
            referrer_id = int(args[3:])
            if referrer_id != user_id:
                async with db_pool.acquire() as conn:
                    referrer_exists = await conn.fetchval("SELECT 1 FROM users WHERE user_id=$1", referrer_id)
                    if referrer_exists and not await is_banned(referrer_id):
                        existing = await conn.fetchval("SELECT 1 FROM referrals WHERE referred_id=$1", user_id)
                        if not existing:
                            await conn.execute(
                                "INSERT INTO referrals (referrer_id, referred_id, referred_date, reward_given, clicks) VALUES ($1, $2, $3, $4, 1) ON CONFLICT (referred_id) DO NOTHING",
                                referrer_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), False
                            )
                            await conn.execute("UPDATE referrals SET clicks = clicks + 1 WHERE referred_id=$1", user_id)
                            await safe_send_message(referrer_id, f"🔗 Новый пользователь {message.from_user.first_name} зарегистрировался по вашей ссылке! Награда будет выдана после того, как он совершит {await get_setting('referral_required_thefts')} успешных ограблений.")
        except:
            pass

    username = message.from_user.username
    first_name = message.from_user.first_name
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id, username, first_name, joined_date, balance, reputation, total_spent, negative_balance, exp, level, strength, agility, defense) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) "
                "ON CONFLICT (user_id) DO NOTHING",
                user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                0, 0, 0, 0, 0, 1, 1, 1, 1
            )
    except Exception as e:
        logging.error(f"DB error in start: {e}")
        await message.answer("❌ Ошибка базы данных. Попробуй позже.")
        return

    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer(
            "❗️ Для использования бота необходимо подписаться на наши каналы:",
            reply_markup=subscription_inline(not_subscribed)
        )
        return

    is_admin_user = await is_admin(user_id)
    await message.answer(
        f"Привет, {first_name}!\n"
        f"Добро пожаловать в <b>Malboro GAME</b>! 🚬\n"
        f"Тут ты найдёшь: казино, розыгрыши, магазин, аукцион.\n"
        f"А ещё можешь грабить других – случайно или по username!\n"
        f"У тебя 1 уровень. Зарабатывай опыт и повышай уровень!\n\n"
        f"Канал: @lllMALBOROlll (подпишись!)",
        reply_markup=main_menu_keyboard(is_admin_user)
    )

@dp.message_handler(commands=['help'])
async def cmd_help_private(message: types.Message):
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
        "📚 <b>Доступные команды и разделы</b>\n\n"
        "👤 Профиль – статистика и характеристики\n"
        "🎁 Бонус – ежедневный бонус\n"
        "🛒 Магазин подарков – покупка подарков\n"
        "🎰 Казино – азартные игры\n"
        "🎟 Промокод – активация промокодов\n"
        "🏆 Топ игроков – рейтинг по баксам, репутации, уровню и т.д.\n"
        "💰 Мои покупки – история заказов\n"
        "🔫 Ограбить – укради баксы у другого\n"
        "🎲 Игры – кости, угадай число, мультиплеер 21\n"
        "⭐️ Репутация – твой авторитет\n"
        "📋 Задания – выполняй и получай награды\n"
        "🔗 Рефералка – приглашай друзей\n"
        "📊 Уровень – твой прогресс\n"
        "🎁 Розыгрыши – активные и завершённые\n"
        "🏷 Аукцион – участвуй в торгах\n"
        "🏪 Мои бизнесы – управление бизнесом\n"
        "💼 Продажа авторитета – торговля глобальным авторитетом\n"
        "⚙️ Админ панель – для администраторов"
    )
    await message.answer(text)

# ==================== ПРОВЕРКА ПОДПИСКИ (ИНЛАЙН) ====================
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        await callback.answer("⛔ Вы заблокированы.", show_alert=True)
        return
    ok, not_subscribed = await check_subscription(user_id)
    if ok:
        await callback.message.delete()
        is_admin_user = await is_admin(user_id)
        await callback.message.answer(
            "✅ Спасибо за подписку! Добро пожаловать.",
            reply_markup=main_menu_keyboard(is_admin_user)
        )
    else:
        await callback.answer("❌ Ты ещё не подписался на все каналы!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=subscription_inline(not_subscribed))

@dp.callback_query_handler(lambda c: c.data == "no_link")
async def no_link_callback(callback: types.CallbackQuery):
    await callback.answer("Ссылка отсутствует. Подпишись вручную.", show_alert=True)

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
                "SELECT balance, reputation, total_spent, negative_balance, joined_date, "
                "theft_attempts, theft_success, theft_failed, theft_protected, "
                "casino_wins, casino_losses, dice_wins, dice_losses, guess_wins, guess_losses, "
                "slots_wins, slots_losses, roulette_wins, roulette_losses, "
                "COALESCE(multiplayer_wins, 0) as multiplayer_wins, "
                "COALESCE(multiplayer_losses, 0) as multiplayer_losses, "
                "exp, level, strength, agility, defense, "
                "COALESCE(global_authority, 0) as global_authority, "
                "COALESCE(smuggle_goods, 0) as smuggle_goods, "
                "COALESCE(smuggle_success, 0) as smuggle_success, "
                "COALESCE(smuggle_fail, 0) as smuggle_fail "
                "FROM users WHERE user_id=$1",
                user_id
            )
        if row:
            balance = row['balance'] or 0
            rep = row['reputation'] or 0
            spent = row['total_spent'] or 0
            neg = row['negative_balance'] or 0
            joined = row['joined_date']
            attempts = row['theft_attempts'] or 0
            success = row['theft_success'] or 0
            failed = row['theft_failed'] or 0
            protected = row['theft_protected'] or 0
            cw = row['casino_wins'] or 0
            cl = row['casino_losses'] or 0
            dw = row['dice_wins'] or 0
            dl = row['dice_losses'] or 0
            gw = row['guess_wins'] or 0
            gl = row['guess_losses'] or 0
            sw = row['slots_wins'] or 0
            sl = row['slots_losses'] or 0
            rw = row['roulette_wins'] or 0
            rl = row['roulette_losses'] or 0
            mpw = row['multiplayer_wins'] or 0
            mpl = row['multiplayer_losses'] or 0
            exp = row['exp'] or 0
            level = row['level'] or 1
            strength = row['strength'] or 1
            agility = row['agility'] or 1
            defense = row['defense'] or 1
            global_auth = row['global_authority'] or 0
            smuggle_goods = row['smuggle_goods'] or 0
            smuggle_success = row['smuggle_success'] or 0
            smuggle_fail = row['smuggle_fail'] or 0

            neg_text = f" (долг: {neg})" if neg > 0 else ""
            level_mult = int(await get_setting("level_multiplier"))
            exp_needed = level * level_mult
            bar = progress_bar(exp, exp_needed, 10)

            total_authority = await get_total_user_authority(user_id)
            total_fights, total_damage = await get_total_user_fights(user_id)

            joined_str = joined if joined else 'неизвестно'

            text = (
                f"👤 <b>Твой профиль</b>\n"
                f"📊 <b>Уровень:</b> {level}\n"
                f"📈 <b>Опыт:</b> {exp}/{exp_needed}\n{bar}\n"
                f"💪 Сила: {strength} | 🏃 Ловкость: {agility} | 🛡 Защита: {defense}\n"
                f"💰 Баланс: {balance} баксов{neg_text}\n"
                f"⭐️ Репутация: {rep}\n"
                f"👑 Глобальный авторитет (для продажи): {global_auth}\n"
                f"⚔️ Очки прокачки (авторитет в чатах): {total_authority} (боёв: {total_fights}, урон: {total_damage})\n"
                f"💸 Всего потрачено: {spent} баксов\n"
                f"📅 Зарегистрирован: {joined_str}\n"
                f"🔫 Ограблений: {attempts} (успешно: {success}, провал: {failed})\n"
                f"🛡 Отбито атак: {protected}\n"
                f"🎰 Казино: побед {cw}, поражений {cl}\n"
                f"🎲 Кости: побед {dw}, поражений {dl}\n"
                f"🔢 Угадайка: побед {gw}, поражений {gl}\n"
                f"🍒 Слоты: побед {sw}, поражений {sl}\n"
                f"🎡 Рулетка: побед {rw}, поражений {rl}\n"
                f"👥 Мультиплеер: побед {mpw}, поражений {mpl}\n"
                f"📦 Контрабанда: {smuggle_goods} ед. (рейсов: успешно {smuggle_success}, провал {smuggle_fail})"
            )
        else:
            text = "Профиль не найден"
    except Exception as e:
        logging.error(f"Profile error: {e}")
        text = "❌ Ошибка загрузки профиля. Подробности в логах."
    await message.answer(text, reply_markup=main_menu_keyboard(await is_admin(user_id)))

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
    bar = progress_bar(exp, exp_needed, 10)
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
    next_coins = await get_level_reward_coins(level+1)
    next_rep = await get_level_reward_rep(level+1)
    text = (
        f"📊 <b>{level_name}</b>\n\n"
        f"Уровень: {level}\n"
        f"Опыт: {exp} / {exp_needed}\n"
        f"{bar}\n\n"
        f"За повышение уровня ты получаешь баксы, репутацию и очки статов!\n"
        f"Следующая награда: +{next_coins} баксов, +{next_rep} репутации."
    )
    await message.answer(text, reply_markup=main_menu_keyboard(await is_admin(user_id)))

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
        reply_markup=main_menu_keyboard(await is_admin(user_id))
    )

# ==================== ЕЖЕДНЕВНЫЙ БОНУС ====================
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

    async with db_pool.acquire() as conn:
        last_bonus_str = await conn.fetchval("SELECT last_bonus FROM users WHERE user_id=$1", user_id)

        now = datetime.now()
        if last_bonus_str:
            try:
                last_bonus = datetime.strptime(last_bonus_str, "%Y-%m-%d %H:%M:%S")
                if last_bonus.date() == now.date():
                    next_bonus = last_bonus + timedelta(days=1)
                    time_left = next_bonus - now
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    await message.answer(f"⏳ Бонус уже получен сегодня. Следующий через {hours} ч {minutes} мин.")
                    return
            except:
                pass

        bonus = random.randint(10, 50)
        phrase = get_random_phrase(BONUS_PHRASES, bonus=bonus)

        await conn.execute(
            "UPDATE users SET balance = balance + $1, last_bonus = $2 WHERE user_id=$3",
            bonus, now.strftime("%Y-%m-%d %H:%M:%S"), user_id
        )
    await message.answer(phrase, reply_markup=main_menu_keyboard(await is_admin(user_id)))

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
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Самые богатые")],
        [KeyboardButton(text="💸 Транжиры")],
        [KeyboardButton(text="🔫 Крадуны")],
        [KeyboardButton(text="⭐️ По репутации")],
        [KeyboardButton(text="👥 Победы в мультиплеере")],
        [KeyboardButton(text="📈 По уровню")],
        [KeyboardButton(text="💪 По силе")],
        [KeyboardButton(text="🏃 По ловкости")],
        [KeyboardButton(text="🛡 По защите")],
        [KeyboardButton(text="◀️ Назад")]
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
            if order_field == 'multiplayer_wins':
                order_expr = "COALESCE(multiplayer_wins, 0)"
            else:
                order_expr = order_field
            rows = await conn.fetch(
                f"SELECT first_name, {order_expr} as value FROM users ORDER BY value DESC LIMIT $1 OFFSET $2",
                ITEMS_PER_PAGE, offset
            )
        if not rows:
            await message.answer("Нет данных.")
            return
        text = f"{title} (страница {page}):\n\n"
        for idx, row in enumerate(rows, start=offset+1):
            text += f"{idx}. {row['first_name']} – {row['value']}\n"
        kb = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"top:{order_field}:{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"top:{order_field}:{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        if kb:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
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
    await show_top(message, "multiplayer_wins", "👥 Победы в мультиплеере")

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
        "multiplayer_wins": "👥 Победы в мультиплеере",
        "level": "📈 По уровню",
        "strength": "💪 По силе",
        "agility": "🏃 По ловкости",
        "defense": "🛡 По защите"
    }
    title = titles.get(field, "Топ")
    await show_top(callback.message, field, title)
    await callback.answer()

# ==================== КАЗИНО И ИГРЫ ====================
@dp.message_handler(lambda message: message.text == "🎰 Казино")
async def casino_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    await message.answer("Выбери игру:", reply_markup=casino_menu_keyboard())

@dp.message_handler(lambda message: message.text == "◀️ Назад", state='*')
async def back_from_games(message: types.Message, state: FSMContext):
    await state.finish()
    await casino_menu(message)

# ----- Казино (простое) с анимацией -----
@dp.message_handler(lambda message: message.text == "🎰 Играть в казино")
async def casino_start(message: types.Message):
    if message.chat.type != 'private':
        return
    await message.answer("Введи сумму ставки:", reply_markup=back_keyboard())
    await CasinoBet.amount.set()

@dp.message_handler(state=CasinoBet.amount)
async def casino_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    try:
        min_bet = int(await get_setting("casino_min_bet"))
        max_bet = int(await get_setting("casino_max_bet"))
    except (ValueError, TypeError):
        min_bet = 1
        max_bet = 1000
    if amount < min_bet or amount > max_bet:
        await message.answer(f"❌ Ставка должна быть от {min_bet} до {max_bet}.")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return

    try:
        win_chance = int(await get_setting("casino_win_chance"))
        multiplier = int(await get_setting("casino_multiplier"))
    except (ValueError, TypeError):
        win_chance = 40
        multiplier = 2

    # Анимация
    anim = await message.answer("🎰 Крутим барабан...")
    await asyncio.sleep(1)
    await anim.edit_text("🎰 🎰 🎰")
    await asyncio.sleep(1)

    win = random.randint(1, 100) <= win_chance

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'casino', win, conn=conn)

        if win:
            profit = amount * (multiplier - 1)
            await update_user_balance(user_id, amount * multiplier, conn=conn)
            exp = int(await get_setting("exp_per_casino_win"))
            phrase = get_random_phrase(CASINO_WIN_PHRASES, win=amount*multiplier, profit=profit)
            if amount * multiplier >= BIG_WIN_THRESHOLD and await get_setting("chat_notify_big_win") == "1":
                await notify_chats(f"🔥 {message.from_user.first_name} сорвал куш в казино: +{amount * multiplier} баксов!")
        else:
            exp = int(await get_setting("exp_per_casino_lose"))
            phrase = get_random_phrase(CASINO_LOSE_PHRASES, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await anim.edit_text(phrase)
    await state.finish()

# ----- Кости -----
@dp.message_handler(lambda message: message.text == "🎲 Кости")
async def dice_start(message: types.Message):
    if message.chat.type != 'private':
        return
    await message.answer("Введи сумму ставки:", reply_markup=back_keyboard())
    await DiceBet.amount.set()

@dp.message_handler(state=DiceBet.amount)
async def dice_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    if amount < 1:
        await message.answer("❌ Минимальная ставка 1 бакс.")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return

    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    threshold = int(await get_setting("dice_win_threshold"))
    win = total > threshold

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'dice', win, conn=conn)
        if win:
            try:
                multiplier = int(await get_setting("dice_multiplier"))
            except (ValueError, TypeError):
                multiplier = 2
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = int(await get_setting("exp_per_dice_win"))
            phrase = get_random_phrase(DICE_WIN_PHRASES, dice1=dice1, dice2=dice2, total=total, profit=profit)
        else:
            exp = int(await get_setting("exp_per_dice_lose"))
            phrase = get_random_phrase(DICE_LOSE_PHRASES, dice1=dice1, dice2=dice2, total=total, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await message.answer(phrase)
    await state.finish()

# ----- Угадай число -----
@dp.message_handler(lambda message: message.text == "🔢 Угадай число")
async def guess_start(message: types.Message):
    if message.chat.type != 'private':
        return
    await message.answer("Введи сумму ставки:", reply_markup=back_keyboard())
    await GuessBet.amount.set()

@dp.message_handler(state=GuessBet.amount)
async def guess_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    if amount < 1:
        await message.answer("❌ Минимальная ставка 1 бакс.")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return

    await state.update_data(amount=amount)
    await message.answer("Загадано число от 1 до 5. Введи свой вариант:")
    await GuessBet.number.set()

@dp.message_handler(state=GuessBet.number)
async def guess_number(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    try:
        guess = int(message.text)
        if guess < 1 or guess > 5:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 1 до 5.")
        return
    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id

    secret = random.randint(1, 5)
    win = (guess == secret)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'guess', win, conn=conn)
        if win:
            try:
                multiplier = int(await get_setting("guess_multiplier"))
                rep_reward = int(await get_setting("guess_reputation"))
            except (ValueError, TypeError):
                multiplier = 5
                rep_reward = 1
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            await update_user_reputation(user_id, rep_reward)
            exp = int(await get_setting("exp_per_guess_win"))
            phrase = get_random_phrase(GUESS_WIN_PHRASES, secret=secret, profit=profit, rep=rep_reward)
        else:
            exp = int(await get_setting("exp_per_guess_lose"))
            phrase = get_random_phrase(GUESS_LOSE_PHRASES, secret=secret, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await message.answer(phrase)
    await state.finish()

# ----- Слоты с улучшенной анимацией -----
@dp.message_handler(lambda message: message.text == "🍒 Слоты")
async def slots_start(message: types.Message):
    if message.chat.type != 'private':
        return
    await message.answer("Введи сумму ставки:", reply_markup=back_keyboard())
    await SlotsBet.amount.set()

@dp.message_handler(state=SlotsBet.amount)
async def slots_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    try:
        min_bet = int(await get_setting("slots_min_bet"))
        max_bet = int(await get_setting("slots_max_bet"))
    except (ValueError, TypeError):
        min_bet = 1
        max_bet = 500
    if amount < min_bet or amount > max_bet:
        await message.answer(f"❌ Ставка должна быть от {min_bet} до {max_bet}.")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return

    # Анимация слотов (несколько этапов)
    anim = await message.answer("🍒 Запускаем слоты...")
    await asyncio.sleep(0.5)
    stages = [
        "🍒 | 🍋 | 🍊",
        "🍋 | 🍊 | 7️⃣",
        "🍊 | 7️⃣ | 💎",
        "7️⃣ | 💎 | 🍒",
    ]
    for stage in stages:
        await anim.edit_text(stage)
        await asyncio.sleep(0.5)

    symbols, multiplier, win = await slots_spin()
    result_str = format_slots_result(symbols)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'slots', win, conn=conn)
        if win:
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = int(await get_setting("exp_per_slots_win"))
            phrase = get_random_phrase(SLOTS_WIN_PHRASES, combo=result_str, multiplier=multiplier, profit=profit)
        else:
            exp = int(await get_setting("exp_per_slots_lose"))
            phrase = get_random_phrase(SLOTS_LOSE_PHRASES, combo=result_str, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await anim.edit_text(phrase)
    await state.finish()

# ----- Рулетка -----
@dp.message_handler(lambda message: message.text == "🎡 Рулетка")
async def roulette_start(message: types.Message):
    if message.chat.type != 'private':
        return
    await message.answer("Введи сумму ставки:", reply_markup=back_keyboard())
    await RouletteBet.amount.set()

@dp.message_handler(state=RouletteBet.amount)
async def roulette_bet_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    try:
        min_bet = int(await get_setting("roulette_min_bet"))
        max_bet = int(await get_setting("roulette_max_bet"))
    except (ValueError, TypeError):
        min_bet = 1
        max_bet = 500
    if amount < min_bet or amount > max_bet:
        await message.answer(f"❌ Ставка должна быть от {min_bet} до {max_bet}.")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return
    await state.update_data(amount=amount)
    await message.answer("На что ставим? (red/black/green/number)", reply_markup=back_keyboard())
    await RouletteBet.bet_type.set()

@dp.message_handler(state=RouletteBet.bet_type)
async def roulette_bet_type(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    bet_type = message.text.lower()
    if bet_type not in ['red', 'black', 'green', 'number']:
        await message.answer("❌ Выбери: red, black, green или number.")
        return
    await state.update_data(bet_type=bet_type)
    if bet_type == 'number':
        await message.answer("Введи число от 0 до 36:")
        await RouletteBet.number.set()
    else:
        await state.update_data(number=None)
        await process_roulette_bet(message, state)

@dp.message_handler(state=RouletteBet.number)
async def roulette_bet_number(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    try:
        number = int(message.text)
        if number < 0 or number > 36:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 0 до 36.")
        return
    await state.update_data(number=number)
    await process_roulette_bet(message, state)

async def process_roulette_bet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data['amount']
    bet_type = data['bet_type']
    bet_number = data.get('number')
    user_id = message.from_user.id

    # Анимация
    anim = await message.answer("🎡 Крутим рулетку...")
    await asyncio.sleep(1.5)

    number, color, win = await roulette_spin(bet_type, bet_number)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'roulette', win, conn=conn)
        if win:
            try:
                if bet_type == 'number':
                    multiplier = int(await get_setting("roulette_number_multiplier"))
                elif bet_type == 'green':
                    multiplier = int(await get_setting("roulette_green_multiplier"))
                else:
                    multiplier = int(await get_setting("roulette_color_multiplier"))
            except (ValueError, TypeError):
                multiplier = 2 if bet_type in ('red','black') else (18 if bet_type=='green' else 36)
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = int(await get_setting("exp_per_roulette_win"))
            phrase = get_random_phrase(ROULETTE_WIN_PHRASES, number=number, color=color, profit=profit)
        else:
            exp = int(await get_setting("exp_per_roulette_lose"))
            phrase = get_random_phrase(ROULETTE_LOSE_PHRASES, number=number, color=color, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await anim.edit_text(phrase)
    await state.finish()

# ==================== ОБРАБОТКА КНОПКИ "НАЗАД" В ГЛАВНОЕ МЕНЮ ====================
@dp.message_handler(lambda message: message.text == "◀️ Назад в главное меню")
async def back_to_main(message: types.Message):
    if message.chat.type != 'private':
        return
    admin_flag = await is_admin(message.from_user.id)
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard(admin_flag))

@dp.message_handler(lambda message: message.text == "◀️ Назад")
async def back_from_submenu(message: types.Message):
    if message.chat.type != 'private':
        return
    admin_flag = await is_admin(message.from_user.id)
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard(admin_flag))

# ==================== ОБРАБОТКА "ОТМЕНА" В FSM (ДОПОЛНИТЕЛЬНО) ====================
@dp.message_handler(lambda message: message.text == "❌ Отмена", state='*')
async def cancel_fsm(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.answer("❌ Действие отменено.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
  # ==================== ЧАСТЬ 5: ПОЛЬЗОВАТЕЛЬСКИЕ ХЕНДЛЕРЫ (ПРОДОЛЖЕНИЕ) ====================

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
                "SELECT id, name, description, price, stock, photo_file_id FROM shop_items ORDER BY id LIMIT $1 OFFSET $2",
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
            text += f"🔹 {name}\n{desc}\n💰 {price} баксов{stock_info}\n\n"
            button_text = f"Купить {name}"
            kb.append([InlineKeyboardButton(text=button_text, callback_data=f"buy_{item_id}")])
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"shop_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
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
                await callback.answer("Не хватает баксов!", show_alert=True)
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
            await notify_chats(chat_phrase)

        asyncio.create_task(notify_admins_about_purchase(callback.from_user, name, price))
        try:
            await callback.message.edit_text(f"✅ Покупка совершена!")
        except:
            pass
        await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard(await is_admin(user_id)))
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
            f"<a href=\"tg://user?id={user.id}\">Ссылка</a> купил {item_name} за {price} баксов."
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
            await message.answer("У тебя пока нет покупок.", reply_markup=main_menu_keyboard(await is_admin(user_id)))
            return
        text = f"📦 Твои покупки (страница {page}):\n\n"
        for row in rows:
            pid, name, date, status, comment = row['id'], row['name'], row['purchase_date'], row['status'], row['admin_comment']
            status_emoji = "⏳" if status == 'pending' else "✅" if status == 'completed' else "❌"
            text += f"{status_emoji} {name} от {date}\n"
            if comment:
                text += f"   Комментарий: {comment}\n"
            text += "\n"
        kb = []
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"mypurchases_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"mypurchases_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        if kb:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await message.answer(text, reply_markup=main_menu_keyboard(await is_admin(user_id)))
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
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
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
            f"✅ Промокод активирован! Ты получил {reward} баксов.",
            reply_markup=main_menu_keyboard(await is_admin(user_id))
        )
    except Exception as e:
        logging.error(f"Promo error: {e}")
        await message.answer("❌ Ошибка активации промокода.")
    await state.finish()

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

async def perform_theft(message: types.Message, robber_id: int, victim_id: int, cost: int = 0):
    success_chance = await get_theft_success_chance(robber_id)
    defense_chance = await get_defense_chance(victim_id)
    defense_penalty = int(await get_setting("theft_defense_penalty"))
    min_amount = int(await get_setting("min_theft_amount"))
    max_amount = int(await get_setting("max_theft_amount"))

    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                robber_balance = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1", robber_id)
                if robber_balance is None:
                    await message.answer("❌ Ошибка: ваш профиль не найден.")
                    return
                if robber_balance < cost:
                    await message.answer(get_random_phrase(THEFT_NO_MONEY_PHRASES), reply_markup=main_menu_keyboard(await is_admin(robber_id)))
                    return

                victim_row = await conn.fetchrow("SELECT balance, username, first_name FROM users WHERE user_id=$1", victim_id)
                if not victim_row:
                    await message.answer("❌ Цель не найдена в базе.")
                    return
                victim_balance, victim_username, victim_first = victim_row['balance'], victim_row['username'], victim_row['first_name']
                victim_name = victim_first if victim_first else str(victim_id)

                if cost > 0:
                    await update_user_balance(robber_id, -cost, conn=conn)
                    robber_balance -= cost

                defense_triggered = random.randint(1, 100) <= defense_chance
                if defense_triggered:
                    penalty = min(defense_penalty, robber_balance)
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
                    await message.answer(robber_phrase, reply_markup=main_menu_keyboard(await is_admin(robber_id)))
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

                    required_thefts = int(await get_setting("referral_required_thefts"))
                    new_success = await conn.fetchval("SELECT theft_success FROM users WHERE user_id=$1", robber_id)
                    if new_success == required_thefts:
                        ref = await conn.fetchrow("SELECT referrer_id FROM referrals WHERE referred_id=$1 AND reward_given=FALSE", robber_id)
                        if ref:
                            referrer_id = ref['referrer_id']
                            bonus_coins = int(await get_setting("referral_bonus"))
                            bonus_rep = int(await get_setting("referral_reputation"))
                            await update_user_balance(referrer_id, bonus_coins, conn=conn)
                            await update_user_reputation(referrer_id, bonus_rep)
                            await conn.execute("UPDATE referrals SET reward_given=TRUE WHERE referred_id=$1", robber_id)
                            await conn.execute("UPDATE referrals SET active=TRUE WHERE referred_id=$1", robber_id)
                            await safe_send_message(referrer_id, f"🎉 Ваш реферал совершил {required_thefts} успешных ограблений! Вы получили {bonus_coins} баксов и {bonus_rep} репутации.")

                    phrase = get_random_phrase(THEFT_SUCCESS_PHRASES, amount=steal_amount, target=victim_name)
                    await message.answer(phrase, reply_markup=main_menu_keyboard(await is_admin(robber_id)))
                    await safe_send_message(victim_id, f"🔫 Вас ограбили! {message.from_user.first_name} украл {steal_amount} баксов.")
                else:
                    await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_failed = theft_failed + 1 WHERE user_id=$1", robber_id)
                    exp_fail = int(await get_setting("exp_per_theft_fail"))
                    await add_exp(robber_id, exp_fail, conn=conn)
                    phrase = get_random_phrase(THEFT_FAIL_PHRASES, target=victim_name)
                    await message.answer(phrase, reply_markup=main_menu_keyboard(await is_admin(robber_id)))

                await conn.execute("UPDATE users SET last_theft_time = $1 WHERE user_id=$2", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), robber_id)

    except Exception as e:
        logging.error(f"Theft error: {e}")
        await message.answer("❌ Ошибка при ограблении.")

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
            try:
                last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
                diff = datetime.now() - last_time
                if diff < timedelta(minutes=cooldown_minutes):
                    remaining = cooldown_minutes - int(diff.total_seconds() // 60)
                    phrase = get_random_phrase(THEFT_COOLDOWN_PHRASES, minutes=remaining)
                    await message.answer(phrase, reply_markup=main_menu_keyboard(await is_admin(user_id)))
                    return
            except:
                pass
    target_id = await get_random_user(user_id)
    if not target_id:
        await message.answer("😕 В игре пока нет других игроков.", reply_markup=main_menu_keyboard(await is_admin(user_id)))
        return
    cost = int(await get_setting("random_attack_cost"))
    await perform_theft(message, user_id, target_id, cost)

@dp.message_handler(lambda message: message.text == "👤 Выбрать пользователя")
async def theft_choose_user(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    cooldown_minutes = int(await get_setting("theft_cooldown_minutes"))
    async with db_pool.acquire() as conn:
        last_time_str = await conn.fetchval("SELECT last_theft_time FROM users WHERE user_id=$1", user_id)
        if last_time_str:
            try:
                last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
                diff = datetime.now() - last_time
                if diff < timedelta(minutes=cooldown_minutes):
                    remaining = cooldown_minutes - int(diff.total_seconds() // 60)
                    phrase = get_random_phrase(THEFT_COOLDOWN_PHRASES, minutes=remaining)
                    await message.answer(phrase, reply_markup=main_menu_keyboard(await is_admin(user_id)))
                    return
            except:
                pass
    await message.answer("Введи @username или ID того, кого хочешь ограбить:", reply_markup=back_keyboard())
    await TheftTarget.target.set()

@dp.message_handler(state=TheftTarget.target)
async def theft_target_entered(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        await state.finish()
        return
    if message.text == "◀️ Назад":
        await state.finish()
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
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
    await perform_theft(message, robber_id, target_id, cost)
    await state.finish()

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
    required_thefts = await get_setting("referral_required_thefts")

    async with db_pool.acquire() as conn:
        clicks = await conn.fetchval("SELECT SUM(clicks) FROM referrals WHERE referrer_id=$1", user_id) or 0
        active = await conn.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id=$1 AND active=TRUE", user_id) or 0
        earned = active * int(bonus_coins)

    await message.answer(
        f"🔗 Твоя реферальная ссылка:\n{link}\n\n"
        f"📊 Статистика:\n"
        f"• Переходов: {clicks}\n"
        f"• Активных рефералов: {active}\n"
        f"• Заработано баксов: {earned}\n\n"
        f"Бонус: {bonus_coins} баксов и {bonus_rep} репутации за каждого активного реферала ({required_thefts} успешных краж)."
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
        await message.answer("📋 Пока нет доступных заданий.", reply_markup=main_menu_keyboard(await is_admin(user_id)))
        return

    text = "📋 Доступные задания:\n\n"
    kb = []
    for row in rows:
        progress = f" (выполнено {row['completed_count']}/{row['max_completions']})" if row['max_completions'] > 1 else ""
        text += f"🔹 {row['name']}{progress}\n{row['description']}\nНаграда: {row['reward_coins']} баксов, {row['reward_reputation']} репутации\n\n"
        kb.append([InlineKeyboardButton(text=f"Выполнить {row['name']}", callback_data=f"task_{row['id']}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

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

            await callback.answer(f"✅ Задание выполнено! +{task['reward_coins']} баксов, +{task['reward_reputation']} репутации", show_alert=True)
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
        await message.answer("🏷 На данный момент нет активных аукционов.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
        return
    text = f"🏷 Активные аукционы (страница {page}):\n\n"
    for row in rows:
        text += f"🆔 {row['id']} | {row['item_name']} | Текущая ставка: {row['current_price']}\n"
        if row['end_time']:
            try:
                end = datetime.strptime(row['end_time'], "%Y-%m-%d %H:%M:%S")
                remaining = end - datetime.now()
                if remaining.total_seconds() > 0:
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    text += f"⏳ Осталось: {hours}ч {minutes}м\n"
            except:
                pass
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
        try:
            end = datetime.strptime(auction['end_time'], "%Y-%m-%d %H:%M:%S")
            remaining = end - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                text += f"⏳ Окончание через: {hours}ч {minutes}м\n"
        except:
            pass
    if auction['target_price']:
        text += f"🎯 Целевая цена: {auction['target_price']}\n"
    text += "\n📊 Последние ставки:\n"
    if bids:
        for bid in bids:
            user = await conn.fetchval("SELECT first_name FROM users WHERE user_id=$1", bid['user_id'])
            text += f"• {user or 'Неизвестно'}: {bid['bid_amount']} баксов ({bid['bid_time']})\n"
    else:
        text += "Пока нет ставок.\n"
    if auction['photo_file_id']:
        await callback.message.delete()
        await callback.message.answer_photo(auction['photo_file_id'], caption=text, reply_markup=auction_detail_keyboard(auction_id))
    else:
        await callback.message.edit_text(text, reply_markup=auction_detail_keyboard(auction_id))
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
            await message.answer("❌ Недостаточно баксов.")
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
            await safe_send_message(user_id, f"🎉 Поздравляем! Ты выиграл аукцион «{auction['item_name']}» с ценой {amount} баксов. Админ скоро свяжется для передачи товара.")
            await safe_send_message(auction['created_by'], f"🏁 Аукцион «{auction['item_name']}» завершён по достижению целевой цены. Победитель: {message.from_user.first_name} (ID: {user_id}) с суммой {amount} баксов.")
            await message.answer("✅ Аукцион завершён! Ты победитель.")
        else:
            await message.answer(f"✅ Ставка принята! Ты теперь лидер с ценой {amount} баксов.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "auction_list")
async def auction_list_back(callback: types.CallbackQuery):
    await list_auctions(callback.message)
    await callback.answer()

# ==================== БИЗНЕСЫ ====================
@dp.message_handler(lambda message: message.text == "🏪 Мои бизнесы")
async def my_businesses(message: types.Message):
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
        await update_business_income(user_id, conn)
        businesses = await conn.fetch(
            "SELECT * FROM user_businesses WHERE user_id=$1 ORDER BY id",
            user_id
        )
    if not businesses:
        # Предложим купить бизнес
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏪 Купить бизнес", callback_data="buy_business_menu")]
        ])
        await message.answer("📭 У тебя пока нет бизнеса. Хочешь купить?", reply_markup=kb)
        return

    kb = business_main_keyboard(businesses)
    await message.answer("🏪 Твои бизнесы:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "buy_business_menu")
async def buy_business_menu(callback: types.CallbackQuery):
    # Список доступных для покупки бизнесов
    available = ["Магазин", "Кафе", "Мастерская", "Ферма", "Шахта"]
    kb = business_buy_keyboard(available)
    await callback.message.edit_text("Выбери бизнес для покупки:", reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("buy_biz_"))
async def buy_business_choose(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "buy_biz_cancel":
        await callback.message.delete()
        await callback.answer()
        return
    biz_name = callback.data.split("_", 2)[2]
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM user_businesses WHERE user_id=$1 AND business_name=$2", user_id, biz_name)
        if exists:
            await callback.answer("У тебя уже есть такой бизнес!", show_alert=True)
            return
        base_price = int(await get_setting("business_base_price"))
        price = await get_business_price(base_price, 1)
        balance = await get_user_balance(user_id)
        if balance < price:
            await callback.answer(f"Недостаточно баксов. Нужно {price}.", show_alert=True)
            return
        async with conn.transaction():
            await update_user_balance(user_id, -price, conn=conn)
            await create_user_business(user_id, biz_name)
    await callback.answer(f"✅ Ты приобрёл бизнес «{biz_name}»!", show_alert=True)
    await my_businesses(callback.message)

@dp.callback_query_handler(lambda c: c.data.startswith("biz_view_"))
async def business_view(callback: types.CallbackQuery):
    biz_id = int(callback.data.split("_")[2])
    async with db_pool.acquire() as conn:
        biz = await conn.fetchrow("SELECT * FROM user_businesses WHERE id=$1", biz_id)
        if not biz:
            await callback.answer("Бизнес не найден", show_alert=True)
            return
        await update_business_income(biz['user_id'], conn)
        biz = await conn.fetchrow("SELECT * FROM user_businesses WHERE id=$1", biz_id)
    accum_bucks = biz['accumulated'] // 100
    accum_cents = biz['accumulated'] % 100
    income_per_hour = await get_business_income(biz['level'])
    income_bucks = income_per_hour // 100
    income_cents = income_per_hour % 100
    upgrade_cost = await get_upgrade_cost(biz['level'])
    text = (
        f"🏪 <b>{biz['business_name']}</b> (ур. {biz['level']})\n\n"
        f"📈 Доход в час: {income_bucks} баксов {income_cents} центов\n"
        f"💰 Накоплено: {accum_bucks} баксов {accum_cents} центов\n"
        f"⬆️ Стоимость улучшения до ур.{biz['level']+1}: {upgrade_cost} баксов"
    )
    await callback.message.edit_text(text, reply_markup=business_actions_keyboard(biz_id))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("biz_collect_"))
async def business_collect(callback: types.CallbackQuery):
    biz_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    coins = await collect_business_income(user_id, biz_id)
    if coins is None:
        await callback.answer("Нет дохода для сбора", show_alert=True)
    else:
        await callback.answer(f"✅ Собрано {coins} баксов!", show_alert=True)
    await business_view(callback)

@dp.callback_query_handler(lambda c: c.data.startswith("biz_upgrade_"))
async def business_upgrade(callback: types.CallbackQuery, state: FSMContext):
    biz_id = int(callback.data.split("_")[2])
    await state.update_data(biz_id=biz_id)
    await callback.message.answer("Ты уверен, что хочешь улучшить бизнес? (да/нет)", reply_markup=back_keyboard())
    await UpgradeBusiness.confirming.set()
    await callback.answer()

@dp.message_handler(state=UpgradeBusiness.confirming)
async def upgrade_confirm(message: types.Message, state: FSMContext):
    if message.text.lower() == 'нет' or message.text == "◀️ Назад":
        await state.finish()
        await my_businesses(message)
        return
    if message.text.lower() == 'да':
        data = await state.get_data()
        biz_id = data['biz_id']
        user_id = message.from_user.id
        success, msg = await upgrade_business(user_id, biz_id)
        await message.answer(msg)
        await state.finish()
        await my_businesses(message)
    else:
        await message.answer("Введи 'да' или 'нет'.")

@dp.callback_query_handler(lambda c: c.data == "biz_back")
async def business_back(callback: types.CallbackQuery):
    await my_businesses(callback.message)
    await callback.answer()

# ==================== РОЗЫГРЫШИ (пользовательская часть) ====================
@dp.message_handler(lambda message: message.text == "🎁 Розыгрыши")
async def giveaways_user_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    await message.answer("🎁 Розыгрыши:", reply_markup=giveaways_user_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Активные розыгрыши")
async def active_giveaways_user(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM giveaways WHERE status='active'")
        rows = await conn.fetch(
            "SELECT id, prize, description, end_date FROM giveaways WHERE status='active' ORDER BY end_date LIMIT $1 OFFSET $2",
            ITEMS_PER_PAGE, offset
        )
    if not rows:
        await message.answer("Нет активных розыгрышей.")
        return
    text = f"📋 Активные розыгрыши (страница {page}):\n\n"
    for row in rows:
        text += f"🎁 #{row['id']} - {row['prize']}\n"
        text += f"{row['description']}\n"
        text += f"⏳ Окончание: {row['end_date']}\n\n"
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    kb = active_giveaways_keyboard(rows, page, total_pages)
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("active_gw_"))
async def active_giveaway_detail(callback: types.CallbackQuery):
    gw_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        gw = await conn.fetchrow("SELECT * FROM giveaways WHERE id=$1 AND status='active'", gw_id)
        if not gw:
            await callback.answer("Розыгрыш не найден или уже завершён.", show_alert=True)
            return
        participant = await conn.fetchval("SELECT 1 FROM participants WHERE user_id=$1 AND giveaway_id=$2", user_id, gw_id)
    text = (
        f"🎁 <b>{gw['prize']}</b>\n"
        f"📝 {gw['description']}\n"
        f"⏳ Окончание: {gw['end_date']}\n"
        f"👥 Победителей: {gw['winners_count']}\n"
    )
    kb = giveaway_detail_keyboard(gw_id, bool(participant))
    if gw['media_file_id'] and gw['media_type'] == 'photo':
        await callback.message.delete()
        await callback.message.answer_photo(gw['media_file_id'], caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("join_giveaway_"))
async def join_giveaway(callback: types.CallbackQuery):
    gw_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM giveaways WHERE id=$1", gw_id)
        if status != 'active':
            await callback.answer("Розыгрыш уже завершён.", show_alert=True)
            return
        exists = await conn.fetchval("SELECT 1 FROM participants WHERE user_id=$1 AND giveaway_id=$2", user_id, gw_id)
        if exists:
            await callback.answer("Ты уже участвуешь.", show_alert=True)
            return
        await conn.execute("INSERT INTO participants (user_id, giveaway_id) VALUES ($1, $2)", user_id, gw_id)
    await callback.answer("✅ Ты участвуешь в розыгрыше!", show_alert=True)
    await active_giveaway_detail(callback)

@dp.callback_query_handler(lambda c: c.data.startswith("leave_giveaway_"))
async def leave_giveaway(callback: types.CallbackQuery):
    gw_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM participants WHERE user_id=$1 AND giveaway_id=$2", user_id, gw_id)
    await callback.answer("❌ Ты отказался от участия.", show_alert=True)
    await active_giveaway_detail(callback)

@dp.callback_query_handler(lambda c: c.data == "active_gw_back")
async def active_gw_back(callback: types.CallbackQuery):
    await active_giveaways_user(callback.message)
    await callback.answer()

@dp.message_handler(lambda message: message.text == "🏁 Завершённые розыгрыши")
async def completed_giveaways_user(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    page = 1
    try:
        parts = message.text.split()
        if len(parts) > 1:
            page = int(parts[1])
    except:
        pass
    offset = (page - 1) * ITEMS_PER_PAGE
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM giveaways WHERE status='completed'")
        rows = await conn.fetch(
            "SELECT id, prize, description, end_date, winners_list FROM giveaways WHERE status='completed' ORDER BY end_date DESC LIMIT $1 OFFSET $2",
            ITEMS_PER_PAGE, offset
        )
    if not rows:
        await message.answer("Нет завершённых розыгрышей.")
        return
    text = f"🏁 Завершённые розыгрыши (страница {page}):\n\n"
    for row in rows:
        text += f"🎁 #{row['id']} - {row['prize']}\n"
        text += f"📅 Завершён: {row['end_date']}\n"
        text += f"👑 Победители: {row['winners_list'] or 'не указаны'}\n\n"
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    kb = completed_giveaways_keyboard(rows, page, total_pages)
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("completed_gw_") and not c.data.startswith("completed_gw_page_"))
async def completed_giveaway_detail(callback: types.CallbackQuery):
    gw_id = int(callback.data.split("_")[2])
    async with db_pool.acquire() as conn:
        gw = await conn.fetchrow("SELECT * FROM giveaways WHERE id=$1 AND status='completed'", gw_id)
        if not gw:
            await callback.answer("Розыгрыш не найден.", show_alert=True)
            return
        participants = await conn.fetch("SELECT user_id FROM participants WHERE giveaway_id=$1", gw_id)
    participants_list = "\n".join([f"• {p['user_id']}" for p in participants]) or "нет участников"
    text = (
        f"🏁 Розыгрыш #{gw['id']}\n"
        f"🎁 Приз: {gw['prize']}\n"
        f"📄 Описание: {gw['description']}\n"
        f"📅 Дата окончания: {gw['end_date']}\n"
        f"👑 Победители: {gw['winners_list'] or 'неизвестно'}\n\n"
        f"📋 Участники:\n{participants_list}"
    )
    if gw['media_file_id'] and gw['media_type'] == 'photo':
        await callback.message.delete()
        await callback.message.answer_photo(gw['media_file_id'], caption=text)
    else:
        await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("completed_gw_page_"))
async def completed_gw_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[3])
    callback.message.text = f"🏁 Завершённые розыгрыши {page}"
    await completed_giveaways_user(callback.message)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "completed_gw_back")
async def completed_gw_back(callback: types.CallbackQuery):
    await completed_giveaways_user(callback.message)
    await callback.answer()
  # ==================== ЧАСТЬ 6: ГРУППОВЫЕ ХЕНДЛЕРЫ И ПОДТВЕРЖДЕНИЕ ЧАТОВ ====================

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ГРУПП ====================
async def check_chat(message: types.Message) -> bool:
    """Проверяет, что сообщение из группы и чат активирован."""
    if message.chat.type == 'private':
        await message.reply("❌ Эта команда работает только в группах.")
        return False
    if not await is_chat_confirmed(message.chat.id):
        await message.reply("❌ Этот чат не активирован. Обратитесь к администратору.")
        return False
    return True

async def update_boss_status_time(chat_id: int):
    """Обновляет время последнего сообщения о состоянии босса в чате."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE confirmed_chats SET last_boss_status_time = $1 WHERE chat_id = $2",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), chat_id
        )

async def can_send_boss_status(chat_id: int) -> bool:
    """Проверяет, можно ли отправить сообщение о состоянии босса (не чаще чем раз в 15 минут)."""
    async with db_pool.acquire() as conn:
        last_time_str = await conn.fetchval("SELECT last_boss_status_time FROM confirmed_chats WHERE chat_id = $1", chat_id)
        if not last_time_str:
            return True
        try:
            last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - last_time
            return diff.total_seconds() > 15 * 60  # 15 минут
        except:
            return True

# ==================== КОМАНДА FIGHT ====================
@dp.message_handler(commands=['fight'])
async def cmd_fight(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await auto_delete_message(message)  # удаляем команду пользователя

    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.first_name

    ok, remaining = await can_fight(chat_id, user_id)
    if not ok:
        await auto_delete_reply(
            message,
            f"⏳ Ты слишком часто машешь кулаками! Подожди ещё {format_time_remaining(remaining)}."
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

    await auto_delete_reply(
        message,
        f"{username}, {phrase}\n"
        f"Твой авторитет в этом чате: {await get_chat_authority(chat_id, user_id)}"
    )

    if outcome == "counter":
        await auto_delete_reply(message, f"💸 Ты потерял {counter_damage} баксов.")

# ==================== КОМАНДА GYM ====================
@dp.message_handler(commands=['gym'])
async def cmd_gym(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await auto_delete_message(message)

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

    await auto_delete_reply(
        message,
        f"🏋️ Качалка! У тебя {authority} авторитета.\n"
        f"Что хочешь улучшить?",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("gym_"))
async def gym_callback(callback: types.CallbackQuery):
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
@dp.message_handler(commands=['status'])
async def cmd_status(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await auto_delete_message(message)

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
    await auto_delete_reply(message, text)

# ==================== КОМАНДА TOP В ЧАТЕ ====================
@dp.message_handler(commands=['top'])
async def cmd_top(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await auto_delete_message(message)

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
        await auto_delete_reply(message, "🏆 В этом чате пока нет участников.")
        return

    text = f"🏆 Топ чата (по {order}):\n"
    for i, row in enumerate(rows, start=offset+1):
        try:
            member = await bot.get_chat_member(chat_id, row['user_id'])
            name = member.user.first_name
        except:
            name = f"ID {row['user_id']}"
        text += f"{i}. {name} – Авторитет: {row['authority']}, Урон: {row['total_damage']}, Боёв: {row['fights']}\n"

    kb = chat_top_navigation(order, page, page > 1, offset + 10 < total)
    await auto_delete_reply(message, text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("chat_top_page_"))
async def chat_top_page_callback(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    order = parts[3]
    page = int(parts[4])
    chat_id = callback.message.chat.id
    await show_chat_top(chat_id, callback.message, page, order)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("chat_top_") and not c.data.startswith("chat_top_page_"))
async def chat_top_order_callback(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    order = parts[2]
    page = int(parts[3])
    chat_id = callback.message.chat.id
    await show_chat_top(chat_id, callback.message, page, order)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

# ==================== КОМАНДА HELP В ЧАТЕ ====================
@dp.message_handler(commands=['help'])
async def cmd_help_chat(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await auto_delete_message(message)

    text = (
        "📚 Доступные команды в этом чате:\n"
        "/fight – атаковать банду (раз в 30 мин)\n"
        "/gym – улучшить характеристики за авторитет\n"
        "/status – твой статус\n"
        "/top – топ чата\n"
        "/boss_status – текущее HP босса\n"
        "/smuggle_chat – отправиться в контрабандный рейс (результат будет в чате)\n"
        "/help – это сообщение\n"
        "Также есть кнопка 🎁 Подгон (для администраторов чата)"
    )
    await auto_delete_reply(message, text)

# ==================== КОМАНДА BOSS_STATUS ====================
@dp.message_handler(commands=['boss_status'])
async def cmd_boss_status(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await auto_delete_message(message)

    chat_id = message.chat.id

    if not await can_send_boss_status(chat_id):
        await auto_delete_reply(message, "⏳ Информация о боссе обновляется не чаще раза в 15 минут. Подожди немного.")
        return

    async with db_pool.acquire() as conn:
        boss = await conn.fetchrow(
            "SELECT * FROM bosses WHERE chat_id=$1 AND status='active'",
            chat_id
        )
    if not boss:
        await auto_delete_reply(message, "❌ В этом чате нет активного босса.")
        return

    bar_length = 10
    remaining_ratio = boss['hp'] / boss['max_hp'] if boss['max_hp'] > 0 else 0
    filled = int(remaining_ratio * bar_length)
    bar = "🟩" * filled + "⬜" * (bar_length - filled)

    text = (
        f"👾 <b>{boss['name']}</b> (Уровень {boss['level']})\n"
        f"📖 {boss['description'] or 'Без описания'}\n"
        f"❤️ HP: {boss['hp']}/{boss['max_hp']}\n"
        f"{bar}\n"
        f"💰 Награда: {boss['reward_coins']} баксов"
    )
    await update_boss_status_time(chat_id)

    if boss['image_file_id']:
        await bot.send_photo(chat_id, boss['image_file_id'], caption=text)
    else:
        await safe_send_chat(chat_id, text)

# ==================== ПОДГОН (GIFT) ====================
@dp.message_handler(lambda message: message.chat.type != 'private' and message.text == "🎁 Подгон")
async def chat_gift(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return
    if not await is_chat_confirmed(chat_id):
        await auto_delete_reply(message, "❌ Этот чат ещё не активирован. Ожидайте подтверждения администратора.")
        return

    await auto_delete_message(message)

    gift_amount = int(await get_setting("gift_amount"))
    gift_limit_per_chat = int(await get_setting("gift_limit_per_day"))
    gift_global_limit = int(await get_setting("gift_global_limit_per_user"))
    gift_cooldown = int(await get_setting("gift_cooldown"))
    today = date.today().isoformat()
    now = datetime.now()

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            chat_info = await conn.fetchrow("SELECT * FROM confirmed_chats WHERE chat_id=$1", chat_id)
            if not chat_info:
                return
            last_gift_date = chat_info['last_gift_date']
            gift_count_today = chat_info['gift_count_today'] if last_gift_date == today else 0

            if gift_count_today >= gift_limit_per_chat:
                await auto_delete_reply(message, f"❌ Сегодня в этом чате уже использовано {gift_count_today} из {gift_limit_per_chat} подгонов.")
                return

            user = await conn.fetchrow("SELECT last_gift_time, gift_count_today FROM users WHERE user_id=$1", user_id)
            if not user:
                await conn.execute(
                    "INSERT INTO users (user_id, username, first_name, joined_date) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                    user_id, message.from_user.username, message.from_user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                user = {'last_gift_time': None, 'gift_count_today': 0}
            if user['last_gift_time'] and user['last_gift_time'].startswith(today):
                user_gift_count = user['gift_count_today']
            else:
                user_gift_count = 0

            if user_gift_count >= gift_global_limit:
                await auto_delete_reply(message, f"❌ Сегодня ты уже получил {user_gift_count} из {gift_global_limit} подгонов во всех чатах.")
                return

            if user['last_gift_time']:
                try:
                    last_gift = datetime.strptime(user['last_gift_time'], "%Y-%m-%d %H:%M:%S")
                    diff = (now - last_gift).total_seconds() / 60
                    if diff < gift_cooldown:
                        remaining = int(gift_cooldown - diff)
                        await auto_delete_reply(message, f"⏳ Подгон можно будет использовать через {remaining} мин.")
                        return
                except:
                    pass

            try:
                admins = await bot.get_chat_administrators(chat_id)
                eligible = [a.user for a in admins if a.user.id != user_id and a.user.id != (await bot.me).id and not await is_banned(a.user.id)]
                if not eligible:
                    await auto_delete_reply(message, "❌ Нет подходящих получателей для подарка.")
                    return
                recipient = random.choice(eligible)
            except Exception as e:
                logging.error(f"Gift error: {e}")
                await auto_delete_reply(message, "❌ Не удалось выбрать получателя.")
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

            new_user_gift_count = user_gift_count + 1
            await conn.execute(
                "UPDATE users SET last_gift_time=$1, gift_count_today=$2 WHERE user_id=$3",
                now.strftime("%Y-%m-%d %H:%M:%S"), new_user_gift_count, user_id
            )

            remaining_chat = gift_limit_per_chat - (gift_count_today + 1)
            await auto_delete_reply(message,
                f"🎁 {message.from_user.first_name} активировал подгон!\n"
                f"Счастливчик: {recipient.first_name} получает {gift_amount} баксов! 🎉\n"
                f"📊 Сегодня в этом чате осталось подгонов: {remaining_chat}"
            )

# ==================== КОМАНДА SMUGGLE_CHAT (КОНТРАБАНДА В ЧАТЕ) ====================
@dp.message_handler(commands=['smuggle_chat'])
async def cmd_smuggle_chat(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await auto_delete_message(message)

    user_id = message.from_user.id
    chat_id = message.chat.id

    ok, remaining = await check_smuggle_cooldown(user_id)
    if not ok:
        minutes = remaining // 60
        seconds = remaining % 60
        await auto_delete_reply(message, f"⏳ Ты ещё не вернулся из рейса. Подожди {minutes} мин {seconds} сек.")
        return

    min_dur = int(await get_setting("smuggle_min_duration"))
    max_dur = int(await get_setting("smuggle_max_duration"))
    duration = random.randint(min_dur, max_dur)
    end_time = datetime.now() + timedelta(minutes=duration)
    cargo = random.choice(SMUGGLE_CARGO)

    async with db_pool.acquire() as conn:
        run_id = await conn.fetchval(
            "INSERT INTO smuggle_runs (user_id, start_time, end_time, chat_id) VALUES ($1, $2, $3, $4) RETURNING id",
            user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S"), chat_id
        )
    await set_smuggle_cooldown(user_id, 0)

    end_time_str = end_time.strftime("%H:%M %d.%m.%Y")
    phrase = get_random_phrase(SMUGGLE_START_PHRASES, cargo=cargo, end_time=end_time_str)
    await auto_delete_reply(message, f"🚤 {message.from_user.first_name}, {phrase}")

# ==================== ОБРАБОТЧИК ДОБАВЛЕНИЯ БОТА В ЧАТ ====================
@dp.message_handler(content_types=['new_chat_members'])
async def bot_added_to_chat(message: types.Message):
    bot_user = await bot.me
    if bot_user.id not in [user.id for user in message.new_chat_members]:
        return
    chat = message.chat
    user_id = message.from_user.id
    await create_chat_confirmation_request(chat.id, chat.title, chat.type, user_id)

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

# ==================== ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК ПОДТВЕРЖДЕНИЯ ЧАТА ====================
@dp.callback_query_handler(lambda c: c.data.startswith("confirm_chat_"))
async def confirm_chat_callback(callback: types.CallbackQuery):
    if not await is_super_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    chat_id = int(callback.data.split("_")[2])
    async with db_pool.acquire() as conn:
        request = await conn.fetchrow("SELECT * FROM chat_confirmation_requests WHERE chat_id=$1", chat_id)
        if not request:
            await callback.answer("❌ Запрос не найден", show_alert=True)
            return
        await add_confirmed_chat(chat_id, request['title'], request['type'], callback.from_user.id)
        await update_chat_request_status(chat_id, 'approved')
        await callback.message.edit_text(f"✅ Чат «{request['title']}» подтверждён!")
        await safe_send_message(request['requested_by'], f"✅ Ваш чат «{request['title']}» активирован!")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("reject_chat_"))
async def reject_chat_callback(callback: types.CallbackQuery):
    if not await is_super_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    chat_id = int(callback.data.split("_")[2])
    async with db_pool.acquire() as conn:
        request = await conn.fetchrow("SELECT * FROM chat_confirmation_requests WHERE chat_id=$1", chat_id)
        if not request:
            await callback.answer("❌ Запрос не найден", show_alert=True)
            return
        await update_chat_request_status(chat_id, 'rejected')
        await callback.message.edit_text(f"❌ Запрос для чата «{request['title']}» отклонён.")
        await safe_send_message(request['requested_by'], f"❌ Запрос на активацию чата «{request['title']}» отклонён.")
    await callback.answer()

# ==================== ОБРАБОТКА СООБЩЕНИЙ В ЧАТЕ (ДЛЯ АТАКИ БОССА) ====================
@dp.message_handler(lambda message: message.chat.type != 'private')
async def chat_message_handler(message: types.Message):
    if not await is_chat_confirmed(message.chat.id):
        return

    if message.from_user.is_bot:
        return

    async with db_pool.acquire() as conn:
        boss = await conn.fetchrow(
            "SELECT * FROM bosses WHERE chat_id=$1 AND status='active'",
            message.chat.id
        )
        if not boss:
            return

        attack = await conn.fetchrow(
            "SELECT damage FROM boss_attacks WHERE boss_id=$1 AND user_id=$2",
            boss['id'], message.from_user.id
        )

        stats = await get_user_stats(message.from_user.id)
        strength = stats['strength']
        base_damage = int(await get_setting("boss_base_damage"))
        damage = base_damage + strength // 2 + random.randint(-3, 3)
        damage = max(1, damage)

        new_hp = boss['hp'] - damage
        if new_hp < 0:
            new_hp = 0

        await conn.execute(
            "UPDATE bosses SET hp=$1 WHERE id=$2",
            new_hp, boss['id']
        )

        if not attack:
            participants = boss['participants'] + [message.from_user.id]
            await conn.execute(
                "UPDATE bosses SET participants=$1 WHERE id=$2",
                participants, boss['id']
            )

        await conn.execute(
            "INSERT INTO boss_attacks (boss_id, user_id, damage, attack_time) VALUES ($1, $2, $3, $4) ON CONFLICT (boss_id, user_id) DO UPDATE SET damage = boss_attacks.damage + $3",
            boss['id'], message.from_user.id, damage, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        if await can_send_boss_status(message.chat.id):
            if random.choice([True, False]):
                phrase = random.choice(BOSS_ANGRY_PHRASES)
            else:
                phrase = random.choice(BOSS_HAPPY_PHRASES)

            bar_length = 10
            remaining_ratio = new_hp / boss['max_hp'] if boss['max_hp'] > 0 else 0
            filled = int(remaining_ratio * bar_length)
            bar = "🟩" * filled + "⬜" * (bar_length - filled)

            reply_text = f"{phrase.format(damage=damage, hp_remaining=new_hp)}\n{bar} {new_hp}/{boss['max_hp']} HP"
            await auto_delete_reply(message, reply_text, delete_seconds=10)
            await update_boss_status_time(message.chat.id)

        if new_hp <= 0:
            await finish_boss_fight(boss['id'])

# ==================== ОБРАБОТКА НЕИЗВЕСТНЫХ КОМАНД В ЧАТЕ ====================
@dp.message_handler(lambda message: message.text and message.text.startswith('/'))
async def unknown_command(message: types.Message):
    if message.chat.type == 'private':
        return
    if not await is_chat_confirmed(message.chat.id):
        return
    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return
    await auto_delete_reply(message, "❌ Неизвестная команда. Введи /help для списка доступных.")
  # ==================== ЧАСТЬ 7: АДМИНИСТРАТИВНЫЕ ХЕНДЛЕРЫ ====================

# ==================== ВХОД В АДМИН-ПАНЕЛЬ ====================
@dp.message_handler(lambda message: message.text == "⚙️ Админ панель")
async def admin_panel(message: types.Message):
    if message.chat.type != 'private':
        return
    if not await is_admin(message.from_user.id):
        await message.answer("У тебя нет прав администратора.")
        return
    permissions = await get_admin_permissions(message.from_user.id)
    await message.answer("Панель администратора:", reply_markup=admin_main_keyboard(permissions))

# ==================== КНОПКА "НАЗАД В АДМИНКУ" ====================
@dp.message_handler(lambda message: message.text == "◀️ Назад в админку")
async def back_to_admin(message: types.Message):
    if message.chat.type != 'private':
        return
    if not await is_admin(message.from_user.id):
        return
    permissions = await get_admin_permissions(message.from_user.id)
    await message.answer("Панель администратора:", reply_markup=admin_main_keyboard(permissions))

# ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================
@dp.message_handler(lambda message: message.text == "👥 Пользователи")
async def admin_users_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ У тебя нет прав на управление пользователями.")
        return
    await message.answer("Управление пользователями:", reply_markup=admin_users_keyboard())

@dp.message_handler(lambda message: message.text == "💰 Начислить баксы")
async def add_balance_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
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
        await message.answer(f"✅ Пользователю {uid} начислено {amount} баксов.")
        await safe_send_message(uid, f"💰 Вам начислено {amount} баксов администратором.")
    except Exception as e:
        logging.error(f"Add balance error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "💸 Списать баксы")
async def remove_balance_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
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
        await message.answer(f"✅ У пользователя {uid} списано {amount} баксов.")
        await safe_send_message(uid, f"💸 У тебя списано {amount} баксов администратором.")
    except Exception as e:
        logging.error(f"Remove balance error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "⭐️ Начислить репутацию")
async def add_reputation_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await FindUser.query.set()

@dp.message_handler(state=FindUser.query)
async def find_user_result(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        permissions = await get_admin_permissions(message.from_user.id)
        await message.answer("Панель администратора:", reply_markup=admin_main_keyboard(permissions))
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
    smuggle_goods = user_data.get('smuggle_goods', 0)
    smuggle_success = user_data.get('smuggle_success', 0)
    smuggle_fail = user_data.get('smuggle_fail', 0)
    banned = await is_banned(uid)
    ban_status = "⛔ Заблокирован" if banned else "✅ Активен"
    text = (
        f"👤 Пользователь: {name} (ID: {uid})\n"
        f"📊 Уровень: {level}, опыт: {exp}\n"
        f"💪 Сила: {strength} | 🏃 Ловкость: {agility} | 🛡 Защита: {defense}\n"
        f"💰 Баланс: {bal} баксов\n"
        f"⭐️ Репутация: {rep}\n"
        f"💸 Потрачено: {spent} баксов\n"
        f"📅 Регистрация: {joined}\n"
        f"🔫 Ограблений: {attempts} (успешно: {success}, провал: {failed})\n"
        f"⚔️ Отбито атак: {protected}\n"
        f"📦 Контрабанда: {smuggle_goods} ед. (рейсов: успешно {smuggle_success}, провал {smuggle_fail})\n"
        f"Статус: {ban_status}"
    )
    await message.answer(text)
    await state.finish()

@dp.message_handler(lambda message: message.text == "📊 Экспорт пользователей")
async def export_users(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
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
@dp.message_handler(lambda message: message.text == "🛒 Магазин")
async def admin_shop_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_shop"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление магазином:", reply_markup=admin_shop_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить товар")
async def add_shop_item_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_shop"):
        await message.answer("❌ Недостаточно прав.")
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
    await state.update_data(stock=stock)
    await message.answer("Отправь фото для товара (или 'нет'):")
    await AddShopItem.photo.set()

@dp.message_handler(state=AddShopItem.photo, content_types=['photo', 'text'])
async def add_shop_item_photo(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    photo_file_id = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.text and message.text.lower() == 'нет':
        pass
    else:
        await message.answer("Отправь фото или 'нет'.")
        return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO shop_items (name, description, price, stock, photo_file_id) VALUES ($1, $2, $3, $4, $5)",
                data['name'], data['description'], data['price'], data['stock'], photo_file_id
            )
        await message.answer("✅ Товар добавлен!", reply_markup=admin_shop_keyboard())
    except Exception as e:
        logging.error(f"Add shop item error: {e}")
        await message.answer("❌ Ошибка при добавлении товара.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "➖ Удалить товар")
async def remove_shop_item_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_shop"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_shop"):
        await message.answer("❌ Недостаточно прав.")
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
                "SELECT id, name, description, price, stock, photo_file_id FROM shop_items ORDER BY id LIMIT $1 OFFSET $2",
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
    if not await has_permission(message.from_user.id, "manage_shop"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_shop"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(callback.from_user.id, "manage_shop"):
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
    if not await has_permission(callback.from_user.id, "manage_shop"):
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
@dp.message_handler(lambda message: message.text == "🎁 Розыгрыши")
async def admin_giveaway_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_giveaways"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление розыгрышами:", reply_markup=admin_giveaway_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать розыгрыш")
async def create_giveaway_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_giveaways"):
        await message.answer("❌ Недостаточно прав.")
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
    await CreateGiveaway.next()

@dp.message_handler(state=CreateGiveaway.description)
async def create_giveaway_description(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_giveaway_menu(message)
        return
    await state.update_data(description=message.text)
    await message.answer("Введи дату окончания в формате ДД.ММ.ГГГГ ЧЧ:ММ (например, 31.12.2025 23:59):")
    await CreateGiveaway.next()

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
                "INSERT INTO giveaways (prize, description, end_date, media_file_id, media_type, winners_count) VALUES ($1, $2, $3, $4, $5, $6)",
                data['prize'], data['description'], data['end_date'], media_file_id, media_type, 1
            )
        await message.answer("✅ Розыгрыш создан!", reply_markup=admin_giveaway_keyboard())
    except Exception as e:
        logging.error(f"Create giveaway error: {e}")
        await message.answer("❌ Ошибка при создании розыгрыша.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Активные розыгрыши")
async def list_active_giveaways(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_giveaways"):
        await message.answer("❌ Недостаточно прав.")
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
            rows = await conn.fetch("""
                SELECT g.id, g.prize, g.end_date, g.description,
                       (SELECT COUNT(*) FROM participants WHERE giveaway_id = g.id) as participants
                FROM giveaways g
                WHERE g.status='active'
                ORDER BY g.end_date
                LIMIT $1 OFFSET $2
            """, ITEMS_PER_PAGE, offset)
        if not rows:
            await message.answer("Нет активных розыгрышей.")
            return
        text = f"Активные розыгрыши (страница {page}):\n"
        for row in rows:
            text += f"ID: {row['id']} | {row['prize']} | до {row['end_date']} | 👥 {row['participants']} участников\n{row['description']}\n\n"
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
    if not await has_permission(message.from_user.id, "manage_giveaways"):
        await message.answer("❌ Недостаточно прав.")
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
            winner_names = []
            for wid in winners:
                user = await conn.fetchrow("SELECT first_name FROM users WHERE user_id=$1", wid)
                name = user['first_name'] if user else str(wid)
                winner_names.append(f"{name} (ID {wid})")
                await safe_send_message(wid, f"🎉 Поздравляем! Ты выиграл в розыгрыше #{gid}! Свяжись с админом.")
            winners_list = ', '.join(winner_names)
            await conn.execute(
                "UPDATE giveaways SET status='completed', winner_id=$1, winners_list=$2 WHERE id=$3",
                winners[0], winners_list, gid
            )
            # Удаляем старые завершённые розыгрыши, оставляя только последние MAX_COMPLETED_GIVEAWAYS
            await conn.execute("""
                DELETE FROM giveaways WHERE status='completed' AND id NOT IN (
                    SELECT id FROM giveaways WHERE status='completed' ORDER BY end_date DESC LIMIT $1
                )
            """, MAX_COMPLETED_GIVEAWAYS)
        await message.answer(f"🏆 Победители выбраны! ({winners_list})", reply_markup=admin_giveaway_keyboard())
    except Exception as e:
        logging.error(f"Finish giveaway error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Завершённые розыгрыши (админ)")
async def completed_giveaways_admin(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_giveaways"):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, prize, end_date, winners_list FROM giveaways WHERE status='completed' ORDER BY end_date DESC LIMIT 50")
    if not rows:
        await message.answer("Нет завершённых розыгрышей.")
        return
    text = "🏁 Завершённые розыгрыши:\n\n"
    for row in rows:
        text += f"#{row['id']}: {row['prize']} — {row['end_date']}\nПобедители: {row['winners_list'] or 'не указаны'}\n\n"
    await message.answer(text)

# ==================== УПРАВЛЕНИЕ КАНАЛАМИ ====================
@dp.message_handler(lambda message: message.text == "📢 Каналы")
async def admin_channel_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_channels"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление каналами:", reply_markup=admin_channel_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить канал")
async def add_channel_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_channels"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_channels"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_channels"):
        await message.answer("❌ Недостаточно прав.")
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
@dp.message_handler(lambda message: message.text == "🎫 Промокоды")
async def admin_promo_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_promocodes"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление промокодами:", reply_markup=admin_promo_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать промокод")
async def create_promo_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_promocodes"):
        await message.answer("❌ Недостаточно прав.")
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
    await message.answer("Введи количество баксов, которые даёт промокод:")
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
    if not await has_permission(message.from_user.id, "manage_promocodes"):
        await message.answer("❌ Недостаточно прав.")
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
            text += f"• {row['code']}: {row['reward']} баксов, использовано {row['used_count']}/{row['max_uses']}\n"
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
@dp.message_handler(lambda message: message.text == "📋 Задания")
async def admin_tasks_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_tasks"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление заданиями:", reply_markup=admin_tasks_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать задание")
async def create_task_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_tasks"):
        await message.answer("❌ Недостаточно прав.")
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
    await message.answer("Введи награду (баксы):")
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
    if not await has_permission(message.from_user.id, "manage_tasks"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_tasks"):
        await message.answer("❌ Недостаточно прав.")
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
@dp.message_handler(lambda message: message.text == "🤖 Чаты")
async def admin_chats_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_chats"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление чатами:", reply_markup=admin_chats_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Список запросов на подтверждение")
async def list_pending_requests(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_chats"):
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
    if not await has_permission(message.from_user.id, "manage_chats"):
        return
    await message.answer("Введи ID чата, который хочешь подтвердить:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    await state.update_data(action="confirm")

@dp.message_handler(lambda message: message.text == "❌ Отклонить запрос")
async def reject_chat_manual(message: types.Message, state: FSMContext):
    if not await has_permission(message.from_user.id, "manage_chats"):
        return
    await message.answer("Введи ID чата, запрос которого хочешь отклонить:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    await state.update_data(action="reject")

@dp.message_handler(lambda message: message.text == "🗑 Удалить чат из подтверждённых")
async def remove_confirmed_chat_start(message: types.Message, state: FSMContext):
    if not await has_permission(message.from_user.id, "manage_chats"):
        return
    await message.answer("Введи ID чата, который нужно удалить из подтверждённых:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    await state.update_data(action="remove")

@dp.message_handler(lambda message: message.text == "📋 Список подтверждённых чатов")
async def list_confirmed_chats(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_chats"):
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
@dp.message_handler(lambda message: message.text == "👾 Боссы")
async def admin_boss_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_bosses"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление боссами:", reply_markup=admin_boss_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Активные боссы")
async def list_active_bosses(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_bosses"):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM bosses WHERE status='active' ORDER BY spawned_at")
    if not rows:
        await message.answer("Нет активных боссов.")
        return
    text = "👾 Активные боссы:\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for row in rows:
        text += f"ID {row['id']}: {row['name']} (ур. {row['level']}) в чате {row['chat_id']}, HP {row['hp']}/{row['max_hp']}\n"
        kb.add(InlineKeyboardButton(f"❌ Удалить босса ID {row['id']}", callback_data=f"delete_boss_{row['id']}"))
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("delete_boss_"))
async def delete_boss_callback(callback: types.CallbackQuery):
    if not await has_permission(callback.from_user.id, "manage_bosses"):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    boss_id = int(callback.data.split("_")[2])
    async with db_pool.acquire() as conn:
        boss = await conn.fetchrow("SELECT * FROM bosses WHERE id=$1", boss_id)
        if not boss:
            await callback.answer("❌ Босс не найден", show_alert=True)
            return
        await conn.execute("DELETE FROM bosses WHERE id=$1", boss_id)
        await conn.execute("DELETE FROM boss_attacks WHERE boss_id=$1", boss_id)
    await callback.answer(f"✅ Босс {boss['name']} полностью удалён", show_alert=True)
    await callback.message.delete()

@dp.message_handler(lambda message: message.text == "⚔️ Создать босса вручную")
async def manual_spawn_boss_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_bosses"):
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
    await state.update_data(level=level)
    await message.answer("Отправь фото для босса (или отправь 'нет'):")
    await BossSpawn.image.set()

@dp.message_handler(state=BossSpawn.image, content_types=['photo', 'text'])
async def manual_spawn_boss_image(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_boss_menu(message)
        return
    image_file_id = None
    if message.photo:
        image_file_id = message.photo[-1].file_id
    elif message.text and message.text.lower() == 'нет':
        pass
    else:
        await message.answer("Отправь фото или 'нет'.")
        return

    data = await state.get_data()
    chat_id = data['chat_id']
    level = data['level']
    await spawn_boss(chat_id, level=level, image_file_id=image_file_id)
    await message.answer(f"✅ Босс {level} уровня создан в чате {chat_id}.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "❌ Удалить босса (по ID)")
async def delete_boss_by_id_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_bosses"):
        return
    await message.answer("Введи ID босса для удаления:", reply_markup=back_keyboard())
    await DeleteBoss.boss_id.set()

@dp.message_handler(state=DeleteBoss.boss_id)
async def delete_boss_by_id_confirm(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_boss_menu(message)
        return
    try:
        boss_id = int(message.text)
    except ValueError:
        await message.answer("❌ Введи целое число.")
        return
    await state.update_data(boss_id=boss_id)
    await message.answer(f"Ты уверен, что хочешь удалить босса с ID {boss_id}? (да/нет)", reply_markup=back_keyboard())
    await DeleteBoss.confirm.set()

@dp.message_handler(state=DeleteBoss.confirm)
async def delete_boss_by_id_final(message: types.Message, state: FSMContext):
    if message.text.lower() == 'нет' or message.text == "◀️ Назад":
        await state.finish()
        await admin_boss_menu(message)
        return
    if message.text.lower() == 'да':
        data = await state.get_data()
        boss_id = data['boss_id']
        async with db_pool.acquire() as conn:
            boss = await conn.fetchrow("SELECT * FROM bosses WHERE id=$1", boss_id)
            if not boss:
                await message.answer("❌ Босс с таким ID не найден.")
                await state.finish()
                return
            await conn.execute("DELETE FROM bosses WHERE id=$1", boss_id)
            await conn.execute("DELETE FROM boss_attacks WHERE boss_id=$1", boss_id)
        await message.answer(f"✅ Босс {boss['name']} удалён.")
        await state.finish()
        await admin_boss_menu(message)
    else:
        await message.answer("Введи 'да' или 'нет'.")

# ==================== УПРАВЛЕНИЕ ПОМОЩНИКАМИ ====================
@dp.message_handler(lambda message: message.text == "⚔️ Помощники")
async def admin_helper_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_helpers"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление помощниками:", reply_markup=admin_helper_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Активные помощники")
async def list_active_helpers(message: types.Message):
    await message.answer("Функция в разработке.")

@dp.message_handler(lambda message: message.text == "📊 Топы чатов")
async def chat_tops(message: types.Message):
    await message.answer("Функция в разработке.")

# ==================== УПРАВЛЕНИЕ АУКЦИОНАМИ ====================
@dp.message_handler(lambda message: message.text == "🏷 Аукцион")
async def admin_auction_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_auctions"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление аукционами:", reply_markup=admin_auction_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать аукцион")
async def create_auction_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_auctions"):
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
    await state.update_data(target_price=target_price)
    await message.answer("Отправь фото для аукциона (или 'нет'):")
    await CreateAuction.photo.set()

@dp.message_handler(state=CreateAuction.photo, content_types=['photo', 'text'])
async def create_auction_photo(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    photo_file_id = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.text and message.text.lower() == 'нет':
        pass
    else:
        await message.answer("❌ Отправь фото или 'нет'.")
        return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO auctions (item_name, description, start_price, current_price, end_time, target_price, created_by, photo_file_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                data['item_name'], data['description'], data['start_price'], data['start_price'], data['end_time'], data['target_price'], message.from_user.id, photo_file_id
            )
        await message.answer("✅ Аукцион создан!", reply_markup=admin_auction_keyboard())
    except Exception as e:
        logging.error(f"Create auction error: {e}")
        await message.answer("❌ Ошибка при создании аукциона.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Активные аукционы")
async def list_active_auctions(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_auctions"):
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
    if not await has_permission(message.from_user.id, "manage_auctions"):
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
        exists = await conn.fetchval("SELECT 1 FROM auctions WHERE id=$1", auction_id)
        if not exists:
            await message.answer("❌ Аукцион с таким ID не найден.")
            await state.finish()
            return
        await conn.execute("UPDATE auctions SET status='cancelled' WHERE id=$1", auction_id)
    await message.answer(f"✅ Аукцион {auction_id} отменён.")
    await state.finish()

# ==================== УПРАВЛЕНИЕ РЕКЛАМОЙ ====================
@dp.message_handler(lambda message: message.text == "📢 Реклама")
async def admin_ad_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_ads"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление рекламой:", reply_markup=admin_ad_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать рекламу")
async def create_ad_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_ads"):
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
    if not await has_permission(message.from_user.id, "manage_ads"):
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

# ==================== СТАТИСТИКА ====================
@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def stats_handler(message: types.Message):
    if not await has_permission(message.from_user.id, "view_stats"):
        await message.answer("❌ Недостаточно прав.")
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
            f"📊 <b>Статистика:</b>\n"
            f"👥 Пользователей: {users}\n"
            f"💰 Всего баксов: {total_balance}\n"
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
        permissions = await get_admin_permissions(message.from_user.id)
        await message.answer(text, reply_markup=admin_main_keyboard(permissions))
    except Exception as e:
        logging.error(f"Stats error: {e}")
        await message.answer("❌ Ошибка получения статистики.")

# ==================== БЛОКИРОВКИ ====================
@dp.message_handler(lambda message: message.text == "🔨 Блокировки")
async def admin_ban_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_bans"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Управление блокировками:", reply_markup=admin_ban_keyboard())

@dp.message_handler(lambda message: message.text == "🔨 Заблокировать пользователя")
async def block_user_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_bans"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_bans"):
        await message.answer("❌ Недостаточно прав.")
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
    if not await has_permission(message.from_user.id, "manage_bans"):
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

# ==================== РАССЫЛКА ====================
@dp.message_handler(lambda message: message.text == "📢 Рассылка")
async def broadcast_start(message: types.Message):
    if not await has_permission(message.from_user.id, "broadcast"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Отправь сообщение для рассылки (текст, фото, видео или документ).", reply_markup=back_keyboard())
    await Broadcast.media.set()

@dp.message_handler(state=Broadcast.media, content_types=['text', 'photo', 'video', 'document'])
async def broadcast_media(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        permissions = await get_admin_permissions(message.from_user.id)
        await message.answer("Панель администратора:", reply_markup=admin_main_keyboard(permissions))
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
@dp.message_handler(lambda message: message.text == "🧹 Очистка старых записей")
async def cleanup_old_data(message: types.Message):
    if not await has_permission(message.from_user.id, "cleanup"):
        return
    await perform_cleanup(manual=True)
    await message.answer("✅ Старые записи очищены согласно настройкам.")

# ==================== НАСТРОЙКИ ИГРЫ ====================
@dp.message_handler(lambda message: message.text == "⚙️ Настройки")
async def settings_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Выбери категорию настроек:", reply_markup=settings_categories_keyboard())

# Категории настроек с инлайн-кнопками
@dp.message_handler(lambda message: message.text == "⚙️ Кража")
async def settings_theft(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("random_attack_cost", "💰 Стоимость случайной кражи"),
        ("targeted_attack_cost", "🎯 Стоимость целевой кражи"),
        ("theft_cooldown_minutes", "⏳ Кулдаун кражи (мин)"),
        ("theft_success_chance", "✅ Шанс успеха (%)"),
        ("theft_defense_chance", "🛡 Шанс защиты (%)"),
        ("theft_defense_penalty", "💸 Штраф при защите"),
        ("min_theft_amount", "🔽 Мин. сумма кражи"),
        ("max_theft_amount", "🔼 Макс. сумма кражи")
    ]
    await show_settings_category(message, params, "theft")

@dp.message_handler(lambda message: message.text == "⚙️ Казино и игры")
async def settings_casino(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("casino_win_chance", "🎰 Шанс выигрыша в казино (%)"),
        ("casino_min_bet", "🔽 Мин. ставка в казино"),
        ("casino_max_bet", "🔼 Макс. ставка в казино"),
        ("casino_multiplier", "🎰 Множитель выигрыша в казино"),
        ("dice_multiplier", "🎲 Множитель выигрыша в кости"),
        ("dice_win_threshold", "🎲 Порог победы (сумма >)"),
        ("guess_multiplier", "🔢 Множитель выигрыша в угадайку"),
        ("guess_reputation", "⭐️ Репутация за победу в угадайке"),
        ("slots_multiplier_three", "🍒 Множитель за три одинаковых"),
        ("slots_multiplier_diamond", "💎 Множитель за три 💎"),
        ("slots_multiplier_seven", "7️⃣ Множитель за три 7️⃣"),
        ("slots_win_probability", "🍒 Общий шанс выигрыша (%)"),
        ("slots_min_bet", "🍒 Мин. ставка в слотах"),
        ("slots_max_bet", "🍒 Макс. ставка в слотах"),
        ("roulette_color_multiplier", "🎡 Множитель на цвет"),
        ("roulette_green_multiplier", "🎡 Множитель на зеро"),
        ("roulette_number_multiplier", "🎡 Множитель на число"),
        ("roulette_min_bet", "🎡 Мин. ставка в рулетке"),
        ("roulette_max_bet", "🎡 Макс. ставка в рулетке"),
    ]
    await show_settings_category(message, params, "casino")

@dp.message_handler(lambda message: message.text == "⚙️ Опыт и уровни")
async def settings_exp(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("exp_per_casino_win", "🎰 Опыт за победу в казино"),
        ("exp_per_casino_lose", "😢 Опыт за проигрыш в казино"),
        ("exp_per_dice_win", "🎲 Опыт за победу в кости"),
        ("exp_per_dice_lose", "📉 Опыт за проигрыш в кости"),
        ("exp_per_guess_win", "🔢 Опыт за победу в угадайку"),
        ("exp_per_guess_lose", "❌ Опыт за проигрыш в угадайку"),
        ("exp_per_slots_win", "🍒 Опыт за победу в слотах"),
        ("exp_per_slots_lose", "🍒 Опыт за проигрыш в слотах"),
        ("exp_per_roulette_win", "🎡 Опыт за победу в рулетке"),
        ("exp_per_roulette_lose", "🎡 Опыт за проигрыш в рулетке"),
        ("exp_per_theft_success", "🔫 Опыт за успешную кражу"),
        ("exp_per_theft_fail", "💔 Опыт за провал кражи"),
        ("exp_per_theft_defense", "🛡 Опыт за защиту от кражи"),
        ("exp_per_game_win", "👥 Опыт за победу в мультиплеере"),
        ("exp_per_game_lose", "👤 Опыт за поражение в мультиплеере"),
        ("level_multiplier", "📊 Множитель опыта для уровня"),
        ("stat_strength_per_level", "💪 Силы за уровень"),
        ("stat_agility_per_level", "🏃 Ловкости за уровень"),
        ("stat_defense_per_level", "🛡 Защиты за уровень")
    ]
    await show_settings_category(message, params, "exp")

@dp.message_handler(lambda message: message.text == "⚙️ Боссы")
async def settings_boss(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("boss_spawn_chance", "👾 Шанс спавна босса (%)"),
        ("boss_min_interval", "⏳ Мин. интервал между спавнами (мин)"),
        ("boss_max_per_day", "📅 Макс. боссов в день"),
        ("boss_hp_multiplier", "❤️ Множитель HP босса"),
        ("boss_attack_cooldown", "⚔️ Кулдаун атак босса (сек)"),
        ("boss_base_damage", "💥 Базовый урон босса"),
        ("boss_reward_coins", "💰 Базовая награда"),
        ("boss_reward_coins_variance", "🎲 Вариация награды")
    ]
    await show_settings_category(message, params, "boss")

@dp.message_handler(lambda message: message.text == "⚙️ Помощники")
async def settings_helper(message: types.Message):
    await message.answer("⚙️ Настройки помощников пока не реализованы.")

@dp.message_handler(lambda message: message.text == "⚙️ Аукцион")
async def settings_auction(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("auction_min_bid_step", "📈 Мин. шаг ставки"),
        ("auction_commission", "💸 Комиссия аукциона (%)"),
        ("auction_notify_chats", "🔔 Уведомлять о новых аукционах (1/0)")
    ]
    await show_settings_category(message, params, "auction")

@dp.message_handler(lambda message: message.text == "⚙️ Подгон")
async def settings_gift(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("gift_amount", "🎁 Сумма подгона"),
        ("gift_limit_per_day", "📅 Лимит подгонов в чате в день"),
        ("gift_global_limit_per_user", "👤 Лимит подгонов на пользователя в день"),
        ("gift_cooldown", "⏳ Кулдаун подгона (мин)")
    ]
    await show_settings_category(message, params, "gift")

@dp.message_handler(lambda message: message.text == "⚙️ Контрабанда")
async def settings_smuggle(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("smuggle_min_duration", "⏱ Мин. длительность рейса (мин)"),
        ("smuggle_max_duration", "⏱ Макс. длительность рейса (мин)"),
        ("smuggle_success_chance", "✅ Шанс успеха (%)"),
        ("smuggle_caught_chance", "🚨 Шанс быть пойманным (%)"),
        ("smuggle_lost_chance", "🌊 Шанс потерять груз (%)"),
        ("smuggle_base_amount", "📦 Базовая добыча контрабанды"),
        ("smuggle_authority_multiplier", "📈 Множитель от авторитета"),
        ("smuggle_cooldown_minutes", "⏳ Кулдаун между рейсами (мин)"),
        ("smuggle_fail_penalty_minutes", "➕ Доп. кулдаун при провале (мин)")
    ]
    await show_settings_category(message, params, "smuggle")

@dp.message_handler(lambda message: message.text == "⚙️ Рефералы")
async def settings_referral(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("referral_bonus", "💰 Бонус за активного реферала"),
        ("referral_reputation", "⭐️ Репутация за активного реферала"),
        ("referral_required_thefts", "🔫 Требуемое число успешных краж")
    ]
    await show_settings_category(message, params, "referral")

@dp.message_handler(lambda message: message.text == "⚙️ Очистка логов")
async def settings_cleanup(message: types.Message):
    if not await has_permission(message.from_user.id, "edit_settings"):
        return
    params = [
        ("cleanup_days_fight_logs", "⚔️ Дни хранения логов боёв"),
        ("cleanup_days_bosses", "👾 Дни хранения побеждённых боссов"),
        ("cleanup_days_auctions", "🏷 Дни хранения завершённых аукционов"),
        ("cleanup_days_purchases", "🛒 Дни хранения покупок"),
        ("cleanup_days_giveaways", "🎁 Дни хранения розыгрышей"),
        ("cleanup_days_user_tasks", "📋 Дни хранения выполненных заданий"),
        ("cleanup_days_smuggle", "📦 Дни хранения рейсов"),
        ("cleanup_days_authority_offers", "💼 Дни хранения предложений авторитета")
    ]
    await show_settings_category(message, params, "cleanup")

async def show_settings_category(message: types.Message, params: List[Tuple[str, str]], category: str):
    text = f"⚙️ Настройки категории:\n\n"
    for key, desc in params:
        value = await get_setting(key)
        text += f"{desc}: {value}\n"
    text += "\nНажми на кнопку для изменения параметра."
    kb = settings_param_keyboard(params, category)
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("edit_"))
async def edit_setting_callback(callback: types.CallbackQuery, state: FSMContext):
    if not await has_permission(callback.from_user.id, "edit_settings"):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    key = callback.data[5:]
    await state.update_data(setting_key=key)
    await callback.message.edit_text(f"✏️ Введи новое значение для параметра `{key}` (текущее: {await get_setting(key)}):")
    await EditSettings.value.set()
    await callback.answer()

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
    await message.answer(f"✅ Параметр {key} обновлён на {value}.")
    await state.finish()
    await settings_menu(message)

@dp.callback_query_handler(lambda c: c.data.startswith("settings_back_"))
async def settings_back_callback(callback: types.CallbackQuery):
    await settings_menu(callback.message)
    await callback.answer()

# ==================== УПРАВЛЕНИЕ АДМИНАМИ ====================
@dp.message_handler(lambda message: message.text == "➕ Админы")
async def admin_admins_menu(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_admins"):
        await message.answer("❌ У тебя нет прав на управление админами.")
        return
    await message.answer("Управление админами:", reply_markup=admin_admins_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить админа")
async def add_admin_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_admins"):
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
    await state.update_data(user_id=uid)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for perm in PERMISSIONS_LIST:
        kb.add(types.InlineKeyboardButton(text=perm, callback_data=f"addadmin_perm:{perm}"))
    kb.add(types.InlineKeyboardButton(text="✅ Готово", callback_data="addadmin_done"))
    await message.answer("Выбери права для нового админа (можно несколько):", reply_markup=kb)
    await AddJuniorAdmin.permissions.set()
    await state.update_data(selected_perms=[])

@dp.callback_query_handler(lambda c: c.data.startswith("addadmin_perm:"), state=AddJuniorAdmin.permissions)
async def add_admin_toggle_perm(callback: types.CallbackQuery, state: FSMContext):
    perm = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get('selected_perms', [])
    if perm in selected:
        selected.remove(perm)
        await callback.answer(f"❌ Право {perm} убрано")
    else:
        selected.append(perm)
        await callback.answer(f"✅ Право {perm} добавлено")
    await state.update_data(selected_perms=selected)

@dp.callback_query_handler(lambda c: c.data == "addadmin_done", state=AddJuniorAdmin.permissions)
async def add_admin_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = data['user_id']
    perms = data.get('selected_perms', [])
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO admins (user_id, added_by, added_date, permissions) VALUES ($1, $2, $3, $4) ON CONFLICT (user_id) DO UPDATE SET permissions=$4",
                uid, callback.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(perms)
            )
        await callback.message.edit_text(f"✅ Пользователь {uid} теперь младший админ с правами: {', '.join(perms) if perms else 'нет прав'}.")
        await safe_send_message(uid, f"🔔 Вам назначены права администратора!\nВаши права: {', '.join(perms) if perms else 'нет прав'}.\nПожалуйста, нажмите /start для обновления меню.")
    except Exception as e:
        logging.error(f"Add admin error: {e}")
        await callback.message.edit_text("❌ Ошибка при добавлении админа.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "✏️ Редактировать права админа")
async def edit_admin_permissions_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_admins"):
        return
    await message.answer("Введи ID или @username админа, чьи права хочешь изменить:", reply_markup=back_keyboard())
    await EditAdminPermissions.user_id.set()

@dp.message_handler(state=EditAdminPermissions.user_id)
async def edit_admin_permissions_user(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_admins_menu(message)
        return
    user_data = await find_user_by_input(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден.")
        return
    uid = user_data['user_id']
    if await is_super_admin(uid):
        await message.answer("❌ Нельзя редактировать права суперадмина.")
        await state.finish()
        return
    if not await is_junior_admin(uid):
        await message.answer("❌ Этот пользователь не является младшим админом. Сначала добавьте его через «Добавить админа».")
        await state.finish()
        return
    current_perms = await get_admin_permissions(uid)
    await state.update_data(user_id=uid, current_perms=current_perms)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for perm in PERMISSIONS_LIST:
        status = "✅ " if perm in current_perms else "❌ "
        kb.add(types.InlineKeyboardButton(text=f"{status}{perm}", callback_data=f"editadmin_perm:{perm}"))
    kb.add(types.InlineKeyboardButton(text="✅ Сохранить", callback_data="editadmin_save"))
    await message.answer("Выбери права (нажимай для переключения):", reply_markup=kb)
    await EditAdminPermissions.selecting_permissions.set()
    await state.update_data(selected_perms=current_perms.copy())

@dp.callback_query_handler(lambda c: c.data.startswith("editadmin_perm:"), state=EditAdminPermissions.selecting_permissions)
async def edit_admin_toggle_perm(callback: types.CallbackQuery, state: FSMContext):
    perm = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get('selected_perms', data['current_perms'].copy())
    if perm in selected:
        selected.remove(perm)
        await callback.answer(f"❌ Право {perm} убрано")
    else:
        selected.append(perm)
        await callback.answer(f"✅ Право {perm} добавлено")
    await state.update_data(selected_perms=selected)

@dp.callback_query_handler(lambda c: c.data == "editadmin_save", state=EditAdminPermissions.selecting_permissions)
async def edit_admin_save(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = data['user_id']
    selected = data.get('selected_perms', data['current_perms'])
    await update_admin_permissions(uid, selected)
    await safe_send_message(uid, f"🔔 Ваши права администратора изменены!\nНовые права: {', '.join(selected) if selected else 'нет прав'}.\nПожалуйста, нажмите /start для обновления меню.")
    await callback.message.edit_text(f"✅ Права пользователя {uid} обновлены: {', '.join(selected)}")
    await state.finish()

@dp.message_handler(lambda message: message.text == "➖ Удалить админа")
async def remove_admin_start(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_admins"):
        return
    await message.answer("Введи ID или @username админа, которого хочешь удалить:", reply_markup=back_keyboard())
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
    if await is_super_admin(uid):
        await message.answer("❌ Нельзя удалить суперадмина.")
        await state.finish()
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM admins WHERE user_id=$1", uid)
        await message.answer(f"✅ Пользователь {uid} больше не админ, если был им.")
        await safe_send_message(uid, "🔔 Ваши права администратора были отозваны.")
    except Exception as e:
        logging.error(f"Remove admin error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список админов")
async def list_admins(message: types.Message):
    if not await has_permission(message.from_user.id, "manage_admins"):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, added_date, permissions FROM admins ORDER BY added_date")
    if not rows:
        await message.answer("Нет младших админов.")
        return
    text = "👥 Младшие админы:\n"
    for row in rows:
        perms = json.loads(row['permissions'])
        perms_str = ', '.join(perms) if perms else 'нет прав'
        text += f"• ID: {row['user_id']}, назначен: {row['added_date']}\n  Права: {perms_str}\n"
    await message.answer(text)
# ==================== НЕДОСТАЮЩИЕ ФУНКЦИИ ДЛЯ КОНТРАБАНДЫ ====================


async def process_smuggle_runs():
    """
    Фоновая задача: проверяет завершённые рейсы контрабанды,
    вычисляет результат и начисляет награду или штраф.
    """
    while True:
        try:
            await asyncio.sleep(30)  # проверяем каждые 30 секунд
            now = datetime.now()
            async with db_pool.acquire() as conn:
                # Находим рейсы, которые должны были завершиться и ещё не обработаны
                runs = await conn.fetch("""
                    SELECT * FROM smuggle_runs
                    WHERE status = 'in_progress' AND end_time <= $1 AND notified = FALSE
                """, now.strftime("%Y-%m-%d %H:%M:%S"))

                for run in runs:
                    user_id = run['user_id']
                    chat_id = run['chat_id']

                    # Определяем исход рейса
                    success_chance = int(await get_setting("smuggle_success_chance"))
                    caught_chance = int(await get_setting("smuggle_caught_chance"))
                    lost_chance = int(await get_setting("smuggle_lost_chance"))

                    rand = random.randint(1, 100)
                    if rand <= success_chance:
                        # Успех
                        base_amount = int(await get_setting("smuggle_base_amount"))
                        authority_mult = float(await get_setting("smuggle_authority_multiplier"))
                        global_authority = await get_user_global_authority(user_id)
                        amount = base_amount + int(global_authority * authority_mult)
                        await update_user_global_authority(user_id, amount)
                        await conn.execute("UPDATE users SET smuggle_goods = smuggle_goods + $1, smuggle_success = smuggle_success + 1 WHERE user_id = $2", amount, user_id)
                        result_text = get_random_phrase(SMUGGLE_SUCCESS_PHRASES, amount=amount)
                        status = 'completed'
                        penalty = 0
                    elif rand <= success_chance + caught_chance:
                        # Пойман
                        penalty = int(await get_setting("smuggle_fail_penalty_minutes"))
                        await conn.execute("UPDATE users SET smuggle_fail = smuggle_fail + 1 WHERE user_id = $1", user_id)
                        result_text = get_random_phrase(SMUGGLE_CAUGHT_PHRASES)
                        status = 'failed'
                    else:
                        # Потерян груз
                        await conn.execute("UPDATE users SET smuggle_fail = smuggle_fail + 1 WHERE user_id = $1", user_id)
                        result_text = get_random_phrase(SMUGGLE_LOST_PHRASES)
                        status = 'failed'
                        penalty = 0

                    # Отмечаем рейс как обработанный
                    await conn.execute("UPDATE smuggle_runs SET status = $1, notified = TRUE, result = $2 WHERE id = $3",
                                       status, result_text, run['id'])

                    # Отправляем результат пользователю
                    if chat_id:
                        # Если рейс был начат в чате, отвечаем в чат (упоминаем пользователя)
                        try:
                            await bot.send_message(chat_id, f"{result_text}\n(для @{run['user_id']})")
                        except:
                            pass
                    else:
                        await safe_send_message(user_id, result_text)

                    # Устанавливаем кулдаун с учётом штрафа
                    await set_smuggle_cooldown(user_id, penalty)

        except Exception as e:
            logging.error(f"Error in process_smuggle_runs: {e}")
            await asyncio.sleep(60)

# ==================== ФОНОВАЯ ЗАДАЧА ДЛЯ АУКЦИОНОВ ====================
async def check_auctions():
    """
    Проверяет аукционы, у которых истекло время, и завершает их.
    """
    while True:
        try:
            await asyncio.sleep(60)  # раз в минуту
            now = datetime.now()
            async with db_pool.acquire() as conn:
                # Активные аукционы с истекшим end_time
                expired = await conn.fetch("""
                    SELECT * FROM auctions
                    WHERE status = 'active' AND end_time IS NOT NULL AND end_time <= $1
                """, now.strftime("%Y-%m-%d %H:%M:%S"))

                for auction in expired:
                    auction_id = auction['id']
                    # Определяем победителя (последняя ставка)
                    winner_bid = await conn.fetchrow("""
                        SELECT user_id, bid_amount FROM auction_bids
                        WHERE auction_id = $1
                        ORDER BY bid_amount DESC, bid_time ASC
                        LIMIT 1
                    """, auction_id)

                    if winner_bid:
                        winner_id = winner_bid['user_id']
                        final_price = winner_bid['bid_amount']
                        await conn.execute(
                            "UPDATE auctions SET status = 'ended', winner_id = $1, current_price = $2 WHERE id = $3",
                            winner_id, final_price, auction_id
                        )
                        # Уведомляем победителя и создателя
                        await safe_send_message(winner_id, f"🎉 Поздравляем! Вы выиграли аукцион «{auction['item_name']}» с ценой {final_price} баксов. Админ скоро свяжется.")
                        await safe_send_message(auction['created_by'], f"🏁 Аукцион «{auction['item_name']}» завершён. Победитель: {winner_id}, цена: {final_price}.")
                    else:
                        # Нет ставок
                        await conn.execute("UPDATE auctions SET status = 'ended', winner_id = NULL WHERE id = $1", auction_id)
                        await safe_send_message(auction['created_by'], f"🏁 Аукцион «{auction['item_name']}» завершён без ставок.")

        except Exception as e:
            logging.error(f"Error in check_auctions: {e}")
            await asyncio.sleep(60)

# ==================== ФОНОВАЯ ЗАДАЧА ДЛЯ БОССОВ (СПАВН ПО РАСПИСАНИЮ) ====================
async def boss_spawn_scheduler():
    """
    Периодически пытается создать босса в случайном подтверждённом чате
    с учётом настроек (шанс, интервал, лимит в день).
    """
    while True:
        try:
            # Проверяем каждые 30 минут (можно настроить)
            await asyncio.sleep(1800)  # 30 минут
            spawn_chance = int(await get_setting("boss_spawn_chance"))
            if random.randint(1, 100) > spawn_chance:
                continue

            # Получаем список подтверждённых чатов
            confirmed = await get_confirmed_chats()
            if not confirmed:
                continue

            # Выбираем случайный чат
            chat_id = random.choice(list(confirmed.keys()))
            chat_data = confirmed[chat_id]

            # Проверяем, не превышен ли лимит боссов в день
            max_per_day = int(await get_setting("boss_max_per_day"))
            today = date.today().isoformat()
            last_spawn_str = chat_data.get('boss_last_spawn')
            spawn_count = chat_data.get('boss_spawn_count', 0)

            if last_spawn_str:
                try:
                    last_spawn_date = datetime.strptime(last_spawn_str, "%Y-%m-%d %H:%M:%S").date()
                    if last_spawn_date == date.today():
                        if spawn_count >= max_per_day:
                            continue
                    else:
                        # Новый день, сбрасываем счётчик
                        async with db_pool.acquire() as conn:
                            await conn.execute("UPDATE confirmed_chats SET boss_spawn_count = 0 WHERE chat_id = $1", chat_id)
                except:
                    pass

            # Проверяем, нет ли уже активного босса в чате
            async with db_pool.acquire() as conn:
                existing = await conn.fetchval("SELECT 1 FROM bosses WHERE chat_id = $1 AND status = 'active'", chat_id)
                if existing:
                    continue

            # Спавним босса
            level = random.randint(1, 5)
            await spawn_boss(chat_id, level=level)

        except Exception as e:
            logging.error(f"Error in boss_spawn_scheduler: {e}")
            await asyncio.sleep(60)

# ==================== ФОНОВАЯ ЗАДАЧА ДЛЯ РАССЫЛКИ РЕКЛАМЫ ====================
async def ad_sender():
    """
    Периодически отправляет рекламные сообщения в соответствии с настройками.
    """
    while True:
        try:
            # Проверяем каждые 5 минут
            await asyncio.sleep(300)
            now = datetime.now()
            async with db_pool.acquire() as conn:
                ads = await conn.fetch("SELECT * FROM ads WHERE enabled = TRUE")
                for ad in ads:
                    last_sent = ad['last_sent']
                    interval = ad['interval_minutes']
                    if last_sent:
                        try:
                            last = datetime.strptime(last_sent, "%Y-%m-%d %H:%M:%S.%f")
                        except:
                            last = datetime.strptime(last_sent, "%Y-%m-%d %H:%M:%S")
                        if (now - last).total_seconds() < interval * 60:
                            continue

                    # Определяем целевую аудиторию
                    target = ad['target']
                    recipients = []

                    if target in ('chats', 'all'):
                        confirmed = await get_confirmed_chats()
                        for chat_id in confirmed.keys():
                            recipients.append(('chat', chat_id))
                    if target in ('private', 'all'):
                        async with db_pool.acquire() as conn2:
                            users = await conn2.fetch("SELECT user_id FROM users")
                            for u in users:
                                recipients.append(('user', u['user_id']))

                    # Отправляем
                    sent_count = 0
                    for typ, dest in recipients:
                        try:
                            if typ == 'chat':
                                await bot.send_message(dest, ad['text'])
                            else:
                                await safe_send_message(dest, ad['text'])
                            sent_count += 1
                        except:
                            pass
                        await asyncio.sleep(0.05)  # небольшая задержка

                    # Обновляем время последней отправки
                    await conn.execute("UPDATE ads SET last_sent = $1 WHERE id = $2", now, ad['id'])
                    logging.info(f"Ad {ad['id']} sent to {sent_count} recipients")

        except Exception as e:
            logging.error(f"Error in ad_sender: {e}")
            await asyncio.sleep(60)

# ==================== ПЕРИОДИЧЕСКАЯ ОЧИСТКА СТАРЫХ ЗАПИСЕЙ ====================
async def periodic_cleanup():
    """
    Раз в сутки запускает очистку старых записей.
    """
    while True:
        try:
            await asyncio.sleep(86400)  # 24 часа
            await perform_cleanup(manual=False)
        except Exception as e:
            logging.error(f"Error in periodic_cleanup: {e}")
            await asyncio.sleep(3600)

# ==================== ЗАПУСК БОТА ====================
async def on_startup(dp):
    logging.info("Бот запущен!")

async def on_shutdown(dp):
    await db_pool.close()
    logging.info("Бот остановлен, соединения закрыты.")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # Создаём пул соединений
    loop.run_until_complete(create_db_pool())
    # Инициализируем таблицы
    loop.run_until_complete(init_db())

    # Запускаем фоновые задачи
    loop.create_task(process_smuggle_runs())
    loop.create_task(check_auctions())
    loop.create_task(boss_spawn_scheduler())
    loop.create_task(ad_sender())
    loop.create_task(periodic_cleanup())

    # Запускаем поллинг
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
