# ==================== ЧАСТЬ 1: ИМПОРТЫ, НАСТРОЙКИ, БД, ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

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

# ==================== НАСТРОЙКИ ПО УМОЛЧАНИЮ ====================
DEFAULT_SETTINGS = {
    # ----- КРАЖА -----
    "random_attack_cost": "0",
    "targeted_attack_cost": "50",
    "theft_cooldown_minutes": "30",
    "theft_success_chance": "40",
    "theft_defense_chance": "20",
    "theft_defense_penalty": "10",
    "min_theft_amount": "5",
    "max_theft_amount": "15",

    # ----- КАЗИНО И ИГРЫ -----
    "casino_win_chance": "40.0",
    "casino_min_bet": "1",
    "casino_max_bet": "1000",
    "casino_multiplier": "2.0",
    "dice_multiplier": "2.0",
    "dice_win_threshold": "7",
    "guess_multiplier": "5.0",
    "guess_reputation": "1",
    "slots_multiplier_three": "3.0",
    "slots_multiplier_diamond": "5.0",
    "slots_multiplier_seven": "10.0",
    "slots_win_probability": "25.0",
    "slots_min_bet": "1",
    "slots_max_bet": "500",
    "roulette_color_multiplier": "2.0",
    "roulette_green_multiplier": "18.0",
    "roulette_number_multiplier": "36.0",
    "roulette_min_bet": "1",
    "roulette_max_bet": "500",
    "multiplayer_min_bet": "5",
    "multiplayer_max_bet": "1000",

    # ----- ОГРАНИЧЕНИЯ ПО УРОВНЮ ДЛЯ ИГР -----
    "min_level_casino": "1",
    "min_level_dice": "1",
    "min_level_guess": "1",
    "min_level_slots": "3",
    "min_level_roulette": "5",
    "min_level_multiplayer": "7",

    # ----- УВЕДОМЛЕНИЯ -----
    "chat_notify_big_win": "1",
    "chat_notify_big_purchase": "1",
    "chat_notify_giveaway": "1",

    # ----- ПОДГОН -----
    "gift_amount": "30",
    "gift_limit_per_day": "3",
    "gift_global_limit_per_user": "4",
    "gift_cooldown": "60",

    # ----- РЕФЕРАЛЫ -----
    "referral_bonus": "50",
    "referral_reputation": "2",
    "referral_required_thefts": "15",

    # ----- ОПЫТ -----
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
    "exp_per_fight": "5",
    "exp_per_smuggle": "10",

    # ----- УРОВНИ -----
    "level_multiplier": "100",
    "level_reward_coins": "30",
    "level_reward_reputation": "3",
    "level_reward_coins_increment": "5",
    "level_reward_reputation_increment": "1",

    # ----- РЕПУТАЦИЯ -----
    "reputation_theft_bonus": "0.5",
    "reputation_defense_bonus": "0.5",
    "reputation_smuggle_bonus": "0.2",
    "reputation_smuggle_success_bonus": "0.1",
    "reputation_max_bonus_percent": "30",

    # ----- БОССЫ -----
    "boss_spawn_chance": "20",
    "boss_min_interval": "360",
    "boss_max_per_day": "2",
    "boss_hp_multiplier": "200",
    "boss_attack_cooldown": "3",
    "boss_base_damage": "20",
    "boss_reward_coins": "500",
    "boss_reward_coins_variance": "200",
    "boss_reward_bitcoin": "10",
    "boss_reward_bitcoin_variance": "5",

    # ----- СТАТЫ ЗА УРОВЕНЬ -----
    "stat_strength_per_level": "1",
    "stat_agility_per_level": "1",
    "stat_defense_per_level": "1",

    # ----- АУКЦИОН -----
    "auction_min_bid_step": "10",
    "auction_commission": "0",
    "auction_notify_chats": "1",

    # ----- БОЙ В ЧАТАХ -----
    "fight_cooldown_minutes": "30",
    "fight_base_damage": "5",
    "fight_damage_variance": "3",
    "fight_authority_min": "1",
    "fight_authority_max": "3",
    "fight_bitcoin_reward": "1",

    # ----- КАЧАЛКА (АВТОРИТЕТ) -----
    "gym_strength_cost": "10",
    "gym_agility_cost": "10",
    "gym_defense_cost": "10",

    # ----- БИЗНЕСЫ -----
    "business_upgrade_cost_per_level": "10",

    # ----- КОНТРАБАНДА -----
    "smuggle_min_duration": "30",
    "smuggle_max_duration": "120",
    "smuggle_success_chance": "55",
    "smuggle_caught_chance": "30",
    "smuggle_lost_chance": "15",
    "smuggle_base_amount": "8",
    "smuggle_authority_multiplier": "0.1",
    "smuggle_cooldown_minutes": "60",
    "smuggle_fail_penalty_minutes": "30",

    # ----- БИТКОИНЫ -----
    "bitcoin_per_theft": "1",
    "bitcoin_per_fight": "1",
    "bitcoin_per_casino_win": "2",
    "bitcoin_per_slots_win": "3",
    "bitcoin_per_roulette_win": "2",
    "bitcoin_per_dice_win": "1",
    "bitcoin_per_guess_win": "1",
    "bitcoin_per_boss_participation": "2",

    # ----- БИТКОИН-БИРЖА -----
    "exchange_min_price": "1",
    "exchange_max_price": "0",
    "exchange_commission_percent": "0",
    "exchange_commission_side": "seller",
    "exchange_commission_destination": "burn",
    "exchange_min_amount_btc": "0.001",

    # ----- ОЧИСТКА ЛОГОВ (ДНИ) -----
    "cleanup_days_fight_logs": "7",
    "cleanup_days_bosses": "7",
    "cleanup_days_auctions": "30",
    "cleanup_days_purchases": "30",
    "cleanup_days_giveaways": "30",
    "cleanup_days_user_tasks": "30",
    "cleanup_days_smuggle": "30",
    "cleanup_days_bitcoin_orders": "30",

    # ----- АВТОУДАЛЕНИЕ КОМАНД (СЕКУНД) -----
    "auto_delete_commands_seconds": "30",

    # ----- СТАРТОВЫЙ БОНУС -----
    "new_user_bonus": "50",

    # ----- ГЛОБАЛЬНЫЙ КУЛДАУН (секунды) -----
    "global_cooldown_seconds": "3",

    # ----- ЛИМИТ НА ВВОД ЧИСЕЛ -----
    "max_input_number": "1000000",
}

# ==================== КОНСТАНТЫ ====================
ITEMS_PER_PAGE = 10
BIG_WIN_THRESHOLD = 100
BIG_PURCHASE_THRESHOLD = 100
MAX_ROOMS = 20
MIN_PLAYERS = 2
MAX_PLAYERS = 5
MIN_BET = 3
MAX_COMPLETED_GIVEAWAYS = 10

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
    "manage_admins",
    "manage_businesses",
    "manage_exchange",
    "manage_media",
]

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

# ==================== ТЕКСТОВЫЕ ФРАЗЫ (ПОЛНЫЙ СПИСОК) ====================
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
    "✅ Рейс завершён успешно! Ты привёз {amount} BTC. Чёрный рынок доволен.",
    "💰 Товар сбыт с хорошей наценкой! +{amount} BTC осело в кармане.",
    "🎉 Пограничников удалось обмануть! Выручка: {amount} BTC.",
    "🚢 Корабль вернулся в порт, груз продан. Твоя доля: {amount} BTC.",
]

SMUGGLE_CAUGHT_PHRASES = [
    "🚨 Береговая охрана перехватила судно! Всё конфисковано. Ты в бегах.",
    "⛓ Полиция накрыла явочную квартиру. Придётся залечь на дно (кулдаун увеличен).",
    "👮‍♂️ Менты вышли на след. Контрабанда конфискована. Объявлен в розыск.",
    "🔫 Перестрелка с таможенниками! Пришлось бросить груз и спасаться бегством.",
]

SMUGGLE_LOST_PHRASES = [
    "🌊 Шторм уничтожил твоё судно! Груз утонул.",
    "💥 Корабль напоролся на рифы. Все ящики на дне.",
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
    "✅ Ты приобрёл бизнес «{name}»! Он будет приносить доход в баксах.",
    "🏪 Поздравляю с покупкой! Теперь у тебя есть {name}.",
]

BUSINESS_COLLECT_PHRASES = [
    "💰 Ты собрал {coins} баксов с бизнеса «{name}».",
    "💵 Прибыль от {name}: {coins} баксов.",
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

BOSS_ANGRY_PHRASES = [
    "Ты думал, что в нашем районе можно просто так ходить? Получи {damage} урона!",
    "Я закопаю тебя в пустыне! Держи {damage}!",
    "Ты подписал себе смертный приговор! Атака {damage}!",
    "Мои парни сейчас разберутся с тобой! {damage} урона!",
    "Ты пожалеешь, что связался с мафией! Получай {damage}!",
]

BOSS_HAPPY_PHRASES = [
    "Ха, слабак! Мой авторитет не пошатнуть! Осталось {hp_remaining} HP.",
    "Ты всего лишь муравей. У меня ещё {hp_remaining} здоровья!",
    "Мои люди скоро придут на помощь! HP: {hp_remaining}",
    "Я видал и не такое. HP осталось: {hp_remaining}",
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
    "🦹‍♂️ Удачная кража! +{amount} баксов!",
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

# ==================== МИДЛВАРЬ ====================
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

dp.middleware.setup(ThrottlingMiddleware(rate_limit=0.5))

# ==================== БЕЗОПАСНАЯ ОТПРАВКА ====================
async def safe_send_message(user_id: int, text: str, **kwargs):
    # Экранируем HTML-теги в пользовательском тексте, если parse_mode=HTML
    if kwargs.get('parse_mode') == 'HTML':
        text = html.escape(text)
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

# ==================== АВТОУДАЛЕНИЕ ====================
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

# ==================== ПОДКЛЮЧЕНИЕ К БД ====================
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
        # ---- Таблица users ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TEXT,
                balance NUMERIC(12,2) DEFAULT 0,
                reputation INTEGER DEFAULT 0,
                total_spent NUMERIC(12,2) DEFAULT 0,
                negative_balance NUMERIC(12,2) DEFAULT 0,
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
                smuggle_success INTEGER DEFAULT 0,
                smuggle_fail INTEGER DEFAULT 0,
                bitcoin_balance NUMERIC(12,4) DEFAULT 0,
                authority_balance INTEGER DEFAULT 0
            )
        ''')

        # ---- Таблица бизнесов пользователей ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_businesses (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                business_type_id INTEGER NOT NULL,
                level INTEGER DEFAULT 1,
                last_collection TEXT,
                accumulated INTEGER DEFAULT 0,
                UNIQUE(user_id, business_type_id)
            )
        ''')

        # ---- Таблица типов бизнесов ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS business_types (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                emoji TEXT NOT NULL,
                base_price_btc NUMERIC(10,2) NOT NULL,
                base_income_cents INTEGER NOT NULL,
                description TEXT,
                max_level INTEGER DEFAULT 10,
                available BOOLEAN DEFAULT TRUE
            )
        ''')

        # ---- Таблица последних ставок ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_last_bets (
                user_id BIGINT,
                game TEXT,
                bet_amount NUMERIC(12,2),
                bet_data JSONB,
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (user_id, game)
            )
        ''')

        # ---- Таблица подтверждённых чатов ----
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

        # ---- Запросы на подтверждение чатов ----
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

        # ---- Боссы ----
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
                reward_bitcoin INTEGER,
                participants BIGINT[] DEFAULT '{}',
                status TEXT DEFAULT 'active',
                image_file_id TEXT,
                description TEXT
            )
        ''')

        # ---- Атаки на босса ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS boss_attacks (
                boss_id INTEGER,
                user_id BIGINT,
                damage INTEGER,
                attack_time TEXT,
                PRIMARY KEY (boss_id, user_id)
            )
        ''')

        # ---- Каналы для подписки ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                chat_id TEXT UNIQUE,
                title TEXT,
                invite_link TEXT
            )
        ''')

        # ---- Рефералы ----
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

        # ---- Товары магазина ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                price NUMERIC(12,2),
                stock INTEGER DEFAULT -1,
                photo_file_id TEXT
            )
        ''')

        # ---- Покупки ----
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

        # ---- Промокоды ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward NUMERIC(12,2),
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')

        # ---- Активации промокодов ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS promo_activations (
                user_id BIGINT,
                promo_code TEXT,
                activated_at TEXT,
                PRIMARY KEY (user_id, promo_code)
            )
        ''')

        # ---- Розыгрыши ----
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

        # ---- Участники розыгрышей ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                user_id BIGINT,
                giveaway_id INTEGER,
                PRIMARY KEY (user_id, giveaway_id)
            )
        ''')

        # ---- Админы ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_by BIGINT,
                added_date TEXT,
                permissions TEXT DEFAULT '[]'
            )
        ''')

        # ---- Забаненные ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id BIGINT PRIMARY KEY,
                banned_by BIGINT,
                banned_date TEXT,
                reason TEXT
            )
        ''')

        # ---- Настройки ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # ---- Задания ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                name TEXT,
                description TEXT,
                task_type TEXT,
                target_id TEXT,
                reward_coins NUMERIC(12,2) DEFAULT 0,
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

        # ---- Выполненные задания ----
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

        # ---- Мультиплеерные игры ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS multiplayer_games (
                game_id TEXT PRIMARY KEY,
                host_id BIGINT,
                max_players INTEGER,
                bet_amount NUMERIC(12,2),
                status TEXT DEFAULT 'waiting',
                deck TEXT,
                created_at TEXT,
                current_player_index INTEGER DEFAULT 0
            )
        ''')

        # ---- Игроки в мультиплеере ----
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

        # ---- Награды за уровень ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS level_rewards (
                level INTEGER PRIMARY KEY,
                coins NUMERIC(12,2),
                reputation INTEGER
            )
        ''')

        # ---- Аукционы ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS auctions (
                id SERIAL PRIMARY KEY,
                item_name TEXT NOT NULL,
                description TEXT,
                start_price NUMERIC(12,2) NOT NULL,
                current_price NUMERIC(12,2) NOT NULL,
                start_time TIMESTAMP NOT NULL DEFAULT NOW(),
                end_time TIMESTAMP,
                target_price NUMERIC(12,2),
                status TEXT DEFAULT 'active',
                winner_id BIGINT,
                created_by BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                photo_file_id TEXT
            )
        ''')

        # ---- Ставки на аукционе ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS auction_bids (
                id SERIAL PRIMARY KEY,
                auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                bid_amount NUMERIC(12,2) NOT NULL,
                bid_time TIMESTAMP DEFAULT NOW()
            )
        ''')

        # ---- Авторитет в чатах ----
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

        # ---- Кулдауны боёв ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fight_cooldowns (
                chat_id BIGINT,
                user_id BIGINT,
                last_fight TIMESTAMP,
                PRIMARY KEY (chat_id, user_id)
            )
        ''')

        # ---- Глобальные кулдауны ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS global_cooldowns (
                user_id BIGINT,
                command TEXT,
                last_used TIMESTAMP,
                PRIMARY KEY (user_id, command)
            )
        ''')

        # ---- Логи боёв ----
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

        # ---- Реклама ----
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

        # ---- Заявки на биткоин-бирже ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bitcoin_orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('buy', 'sell')),
                amount NUMERIC(12,4) NOT NULL CHECK (amount > 0),
                price INTEGER NOT NULL CHECK (price >= 1),
                total_locked NUMERIC(12,4) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled'))
            )
        ''')

        # ---- Сделки ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bitcoin_trades (
                id SERIAL PRIMARY KEY,
                buy_order_id INTEGER REFERENCES bitcoin_orders(id),
                sell_order_id INTEGER REFERENCES bitcoin_orders(id),
                amount NUMERIC(12,4) NOT NULL,
                price INTEGER NOT NULL,
                buyer_id BIGINT NOT NULL,
                seller_id BIGINT NOT NULL,
                traded_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # ---- Контрабандные рейсы ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS smuggle_runs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                chat_id BIGINT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                status TEXT DEFAULT 'in_progress',
                result TEXT,
                smuggle_amount NUMERIC(12,4) DEFAULT 0,
                notified BOOLEAN DEFAULT FALSE
            )
        ''')

        # ---- Кулдауны контрабанды ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS smuggle_cooldowns (
                user_id BIGINT PRIMARY KEY,
                cooldown_until TIMESTAMP
            )
        ''')

        # ---- Медиафайлы ----
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS media (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                file_id TEXT NOT NULL,
                description TEXT
            )
        ''')

        # ---- Индексы ----
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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_bitcoin_orders_user ON bitcoin_orders(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_bitcoin_orders_status ON bitcoin_orders(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_bitcoin_orders_type ON bitcoin_orders(type)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_smuggle_runs_user ON smuggle_runs(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_smuggle_runs_end ON smuggle_runs(end_time)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_businesses_user ON user_businesses(user_id)")

    # Заполняем настройки
    await init_settings()
    await init_level_rewards()
    await init_business_types()

    logging.info("✅ Таблицы в PostgreSQL проверены/обновлены")

async def init_settings():
    async with db_pool.acquire() as conn:
        for key, value in DEFAULT_SETTINGS.items():
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                key, value
            )

async def init_level_rewards():
    async with db_pool.acquire() as conn:
        for lvl in range(1, 101):
            exists = await conn.fetchval("SELECT level FROM level_rewards WHERE level=$1", lvl)
            if not exists:
                coins = int(DEFAULT_SETTINGS["level_reward_coins"]) + (lvl-1) * int(DEFAULT_SETTINGS["level_reward_coins_increment"])
                rep = int(DEFAULT_SETTINGS["level_reward_reputation"]) + (lvl-1) * int(DEFAULT_SETTINGS["level_reward_reputation_increment"])
                await conn.execute(
                    "INSERT INTO level_rewards (level, coins, reputation) VALUES ($1, $2, $3)",
                    lvl, float(coins), rep
                )

async def init_business_types():
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM business_types")
        if count == 0:
            businesses = [
                ("🥙 Ларёк с шаурмой", "🥙", 5.0, 60, "Уличная точка быстрого питания. Приносит стабильный, но небольшой доход.", 10),
                ("🏪 Магазин у дома", "🏪", 15.0, 120, "Небольшой продуктовый магазин. Доход выше, чем у ларька.", 10),
                ("🚗 Автомойка", "🚗", 30.0, 180, "Мойка самообслуживания. Требует вложений, но окупается.", 10),
                ("☕ Кафе", "☕", 50.0, 220, "Уютное кафе в центре. Хороший пассивный доход.", 10),
                ("🏨 Мини-отель", "🏨", 80.0, 260, "Небольшая гостиница. Доход позволяет не работать.", 10),
                ("🏬 Торговый центр", "🏬", 150.0, 298, "Крупный торговый комплекс. Максимальный доход (до 500 баксов/неделю).", 10),
            ]
            for name, emoji, price, income, desc, max_lvl in businesses:
                await conn.execute(
                    "INSERT INTO business_types (name, emoji, base_price_btc, base_income_cents, description, max_level, available) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    name, emoji, price, income, desc, max_lvl, True
                )

# ==================== РАБОТА С НАСТРОЙКАМИ ====================
async def get_setting(key: str) -> str:
    global settings_cache, last_settings_update
    now = time.time()
    if now - last_settings_update > 60 or not settings_cache:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM settings")
            settings_cache = {row['key']: row['value'] for row in rows}
        last_settings_update = now
    value = settings_cache.get(key)
    if value is None:
        value = DEFAULT_SETTINGS.get(key, "")
        if value:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                    key, value
                )
            settings_cache[key] = value
    return value

async def get_setting_float(key: str) -> float:
    val = await get_setting(key)
    try:
        return float(val)
    except:
        return 0.0

async def get_setting_int(key: str) -> int:
    val = await get_setting(key)
    try:
        return int(val)
    except:
        return 0

async def set_setting(key: str, value: str):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE settings SET value=$1 WHERE key=$2", value, key)
    settings_cache[key] = value
    global last_settings_update
    last_settings_update = 0

# ==================== ФУНКЦИИ ДЛЯ ЧАТОВ И КАНАЛОВ ====================
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

# ==================== ПРОВЕРКА ПОДПИСКИ ====================
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

# ----- НОВАЯ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ МЕДИАФАЙЛОВ -----
async def get_media_file_id(key: str) -> Optional[str]:
    """Возвращает file_id из таблицы media по ключу, или None, если не найдено."""
    async with db_pool.acquire() as conn:
        file_id = await conn.fetchval("SELECT file_id FROM media WHERE key=$1", key)
        return file_id

# ==================== ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ====================
async def ensure_user_exists(user_id: int, username: str = None, first_name: str = None):
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM users WHERE user_id=$1", user_id)
        if not exists:
            bonus = await get_setting_float("new_user_bonus")
            await conn.execute(
                "INSERT INTO users (user_id, username, first_name, joined_date, balance, reputation, total_spent, negative_balance, exp, level, strength, agility, defense, bitcoin_balance, authority_balance) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)",
                user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                bonus, 0, 0, 0, 0, 1, 1, 1, 1, 0.0, 0
            )
            return True, bonus
    return False, 0

async def get_user_balance(user_id: int) -> float:
    async with db_pool.acquire() as conn:
        balance = await conn.fetchval("SELECT balance FROM users WHERE user_id=$1", user_id)
        return float(balance) if balance is not None else 0.0

async def update_user_balance(user_id: int, delta: float, conn=None):
    delta = float(delta)  # преобразуем на всякий случай
    async def _update(conn):
        row = await conn.fetchrow("SELECT balance, negative_balance FROM users WHERE user_id=$1", user_id)
        if not row:
            await ensure_user_exists(user_id)
            row = {'balance': 0.0, 'negative_balance': 0.0}
        balance = float(row['balance'])
        negative = float(row['negative_balance']) if row['negative_balance'] else 0.0

        new_balance = balance + delta
        if new_balance < 0:
            negative += abs(new_balance)
            new_balance = 0.0
        new_balance = round(new_balance, 2)
        negative = round(negative, 2)
        await conn.execute(
            "UPDATE users SET balance=$1, negative_balance=$2 WHERE user_id=$3",
            new_balance, negative, user_id
        )
    if conn:
        await _update(conn)
    else:
        async with db_pool.acquire() as new_conn:
            await _update(new_conn)

async def get_user_bitcoin(user_id: int) -> float:
    async with db_pool.acquire() as conn:
        btc = await conn.fetchval("SELECT bitcoin_balance FROM users WHERE user_id=$1", user_id)
        return float(btc) if btc is not None else 0.0

async def update_user_bitcoin(user_id: int, delta: float, conn=None):
    delta = float(delta)
    async def _update(conn):
        row = await conn.fetchrow("SELECT bitcoin_balance FROM users WHERE user_id=$1", user_id)
        if not row:
            await ensure_user_exists(user_id)
            row = {'bitcoin_balance': 0.0}
        current = float(row['bitcoin_balance'])
        new_balance = current + delta
        if new_balance < 0:
            raise ValueError("Недостаточно биткоинов")
        new_balance = round(new_balance, 4)
        await conn.execute(
            "UPDATE users SET bitcoin_balance=$1 WHERE user_id=$2",
            new_balance, user_id
        )
    if conn:
        await _update(conn)
    else:
        async with db_pool.acquire() as new_conn:
            await _update(new_conn)

async def get_user_authority(user_id: int) -> int:
    async with db_pool.acquire() as conn:
        auth = await conn.fetchval("SELECT authority_balance FROM users WHERE user_id=$1", user_id)
        return auth if auth is not None else 0

async def update_user_authority(user_id: int, delta: int, conn=None):
    async def _update(conn):
        await conn.execute(
            "UPDATE users SET authority_balance = authority_balance + $1 WHERE user_id=$2",
            delta, user_id
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
        level_mult = await get_setting_int("level_multiplier")
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
            str_inc = await get_setting_int("stat_strength_per_level") * levels_gained
            agi_inc = await get_setting_int("stat_agility_per_level") * levels_gained
            def_inc = await get_setting_int("stat_defense_per_level") * levels_gained
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
            await update_user_balance(user_id, float(reward['coins']), conn=conn)
            await update_user_reputation(user_id, reward['reputation'])
            await safe_send_message(
                user_id,
                f"🎉 Поздравляем! Ты достиг {new_level} уровня!\n"
                f"Награда: +{reward['coins']} баксов, +{reward['reputation']} репутации!\n"
                f"Твои статы увеличены: сила +{await get_setting_int('stat_strength_per_level')}, ловкость +{await get_setting_int('stat_agility_per_level')}, защита +{await get_setting_int('stat_defense_per_level')}."
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

async def update_user_total_spent(user_id: int, amount: float):
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

# ==================== ФУНКЦИИ ДЛЯ ГЛОБАЛЬНОГО КУЛДАУНА ====================
async def check_global_cooldown(user_id: int, command: str) -> Tuple[bool, int]:
    cooldown = await get_setting_int("global_cooldown_seconds")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_used FROM global_cooldowns WHERE user_id=$1 AND command=$2", user_id, command)
        if row and row['last_used']:
            diff = datetime.now() - row['last_used']
            remaining = cooldown - diff.total_seconds()
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

# ==================== ФУНКЦИИ ДЛЯ БИЗНЕСОВ ====================
async def get_business_type_list(only_available: bool = True) -> List[dict]:
    async with db_pool.acquire() as conn:
        if only_available:
            rows = await conn.fetch("SELECT * FROM business_types WHERE available = TRUE ORDER BY base_price_btc")
        else:
            rows = await conn.fetch("SELECT * FROM business_types ORDER BY base_price_btc")
        return [dict(r) for r in rows]

async def get_business_type(business_type_id: int) -> Optional[dict]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM business_types WHERE id=$1", business_type_id)
        return dict(row) if row else None

async def get_user_businesses(user_id: int) -> List[dict]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT ub.*, bt.name, bt.emoji, bt.base_price_btc, bt.base_income_cents, bt.max_level
            FROM user_businesses ub
            JOIN business_types bt ON ub.business_type_id = bt.id
            WHERE ub.user_id = $1
            ORDER BY bt.base_price_btc
        """, user_id)
        return [dict(r) for r in rows]

async def get_user_business(user_id: int, business_type_id: int) -> Optional[dict]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT ub.*, bt.name, bt.emoji, bt.base_price_btc, bt.base_income_cents, bt.max_level
            FROM user_businesses ub
            JOIN business_types bt ON ub.business_type_id = bt.id
            WHERE ub.user_id = $1 AND ub.business_type_id = $2
        """, user_id, business_type_id)
        return dict(row) if row else None

async def get_business_price(business_type: dict, level: int) -> float:
    # business_type['base_price_btc'] может быть Decimal, преобразуем в float
    base_price = float(business_type['base_price_btc'])
    if level == 1:
        return base_price
    else:
        upgrade_base = await get_setting_float("business_upgrade_cost_per_level")
        cost = upgrade_base * (level ** 1.5)
        return round(cost, 2)

async def get_business_income(business_type: dict, level: int) -> int:
    return business_type['base_income_cents'] * level

async def create_user_business(user_id: int, business_type_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_businesses (user_id, business_type_id, level, last_collection, accumulated) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (user_id, business_type_id) DO NOTHING",
            user_id, business_type_id, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0
        )

async def update_business_income(user_id: int, conn=None):
    async def _update(conn):
        now = datetime.now()
        businesses = await conn.fetch(
            "SELECT ub.*, bt.base_income_cents FROM user_businesses ub JOIN business_types bt ON ub.business_type_id = bt.id WHERE ub.user_id=$1",
            user_id
        )
        for biz in businesses:
            if biz['last_collection']:
                try:
                    last_col = datetime.strptime(biz['last_collection'], "%Y-%m-%d %H:%M:%S")
                    hours_passed = int((now - last_col).total_seconds() // 3600)
                    if hours_passed > 0:
                        income_per_hour = biz['base_income_cents'] * biz['level']
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

async def collect_business_income(user_id: int, business_id: int) -> Tuple[bool, str]:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            biz = await conn.fetchrow("SELECT * FROM user_businesses WHERE id=$1 AND user_id=$2", business_id, user_id)
            if not biz:
                return False, "Бизнес не найден."
            if biz['accumulated'] == 0:
                return False, "Нет дохода для сбора."
            amount_cents = biz['accumulated']
            coins = amount_cents // 100
            remainder = amount_cents % 100
            if coins > 0:
                await update_user_balance(user_id, float(coins), conn=conn)
            await conn.execute(
                "UPDATE user_businesses SET accumulated=$1, last_collection=$2 WHERE id=$3",
                remainder, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), business_id
            )
            return True, f"Собрано {coins} баксов и {remainder} центов."

async def upgrade_business(user_id: int, business_id: int) -> Tuple[bool, str]:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            biz = await conn.fetchrow("""
                SELECT ub.*, bt.base_price_btc, bt.base_income_cents, bt.max_level 
                FROM user_businesses ub 
                JOIN business_types bt ON ub.business_type_id = bt.id 
                WHERE ub.id=$1 AND ub.user_id=$2
            """, business_id, user_id)
            if not biz:
                return False, "Бизнес не найден."
            if biz['level'] >= biz['max_level']:
                return False, f"Бизнес уже максимального уровня ({biz['max_level']})."
            # преобразуем base_price_btc в float
            base_price = float(biz['base_price_btc'])
            cost = await get_business_price({'base_price_btc': base_price}, biz['level'] + 1)
            btc_balance = await get_user_bitcoin(user_id)
            if btc_balance < cost - 0.0001:
                return False, f"Недостаточно биткоинов. Нужно {cost:.2f} BTC, у вас {btc_balance:.4f}."
            await update_user_bitcoin(user_id, -cost, conn=conn)
            await conn.execute(
                "UPDATE user_businesses SET level = level + 1 WHERE id=$1",
                business_id
            )
            return True, f"✅ Бизнес улучшен до уровня {biz['level'] + 1}! Потрачено {cost:.2f} BTC."

# ==================== ФУНКЦИИ ДЛЯ ЧАТОВОГО АВТОРИТЕТА ====================
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
    cooldown = await get_setting_int("fight_cooldown_minutes")
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

async def spawn_boss(chat_id: int, level: int = None, image_file_id: str = None):
    if level is None:
        level = random.randint(1, 5)
    name = random.choice(BOSS_NAMES)
    description = random.choice(BOSS_DESCRIPTIONS)
    hp_mult = await get_setting_int("boss_hp_multiplier")
    hp = level * hp_mult * random.randint(5, 10)
    base_reward_coins = await get_setting_int("boss_reward_coins")
    variance_coins = await get_setting_int("boss_reward_coins_variance")
    reward_coins = base_reward_coins + random.randint(-variance_coins, variance_coins)
    base_reward_btc = await get_setting_int("boss_reward_bitcoin")
    variance_btc = await get_setting_int("boss_reward_bitcoin_variance")
    reward_btc = base_reward_btc + random.randint(-variance_btc, variance_btc)
    now = datetime.now()
    expires_at = now + timedelta(hours=2)
    async with db_pool.acquire() as conn:
        boss_id = await conn.fetchval(
            "INSERT INTO bosses (chat_id, name, level, hp, max_hp, spawned_at, expires_at, reward_coins, reward_bitcoin, participants, status, image_file_id, description) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) RETURNING id",
            chat_id, name, level, hp, hp, now.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at.strftime("%Y-%m-%d %H:%M:%S"), reward_coins, reward_btc, [], 'active', image_file_id, description
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
        reward_coins = boss['reward_coins']
        reward_btc = boss['reward_bitcoin']
        coins_per_player = reward_coins // len(participants)
        btc_per_player = reward_btc // len(participants)
        remainder_coins = reward_coins % len(participants)
        remainder_btc = reward_btc % len(participants)
        for i, uid in enumerate(participants):
            coins = coins_per_player + (1 if i < remainder_coins else 0)
            btc = btc_per_player + (1 if i < remainder_btc else 0)
            await update_user_balance(uid, float(coins), conn=conn)
            await update_user_bitcoin(uid, float(btc), conn=conn)
            exp = await get_setting_int("exp_per_game_win")
            await add_exp(uid, exp, conn=conn)
        await conn.execute("UPDATE bosses SET status='defeated' WHERE id=$1", boss_id)
        phrase = random.choice(BOSS_DEATH_PHRASES)
        await safe_send_chat(boss['chat_id'], f"{phrase}\nУчастники получили по {coins_per_player} баксов и {btc_per_player} BTC!")

# ==================== ФУНКЦИИ ДЛЯ РАСЧЁТА УРОНА ====================
async def calculate_fight_damage(strength: int) -> int:
    base = await get_setting_int("fight_base_damage")
    variance = await get_setting_int("fight_damage_variance")
    damage = base + strength // 2 + random.randint(-variance, variance)
    return max(1, damage)

async def calculate_fight_authority() -> int:
    min_auth = await get_setting_int("fight_authority_min")
    max_auth = await get_setting_int("fight_authority_max")
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

# ==================== ФУНКЦИИ ДЛЯ ИГР ====================
async def slots_spin() -> Tuple[List[str], float, bool]:
    symbols = ['🍒', '🍋', '🍊', '7️⃣', '💎']
    result = [random.choice(symbols) for _ in range(3)]
    win_prob = await get_setting_float("slots_win_probability")
    win = random.random() * 100 <= win_prob
    if not win:
        while result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            result = [random.choice(symbols) for _ in range(3)]
        return result, 0, False
    else:
        if random.random() < 0.1:
            sym = random.choice(symbols)
            result = [sym, sym, sym]
        else:
            sym = random.choice(symbols)
            pos = random.randint(0, 2)
            result = [random.choice(symbols) for _ in range(3)]
            result[pos] = sym
            result[(pos+1)%3] = sym
        if result[0] == result[1] == result[2]:
            if result[0] == '7️⃣':
                multiplier = await get_setting_float("slots_multiplier_seven")
            elif result[0] == '💎':
                multiplier = await get_setting_float("slots_multiplier_diamond")
            else:
                multiplier = await get_setting_float("slots_multiplier_three")
            return result, multiplier, True
        else:
            return result, 2.0, True

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
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT cooldown_until FROM smuggle_cooldowns WHERE user_id=$1", user_id)
        if row and row['cooldown_until']:
            cooldown_until = row['cooldown_until']
            if isinstance(cooldown_until, str):
                cooldown_until = datetime.strptime(cooldown_until, "%Y-%m-%d %H:%M:%S")
            remaining = (cooldown_until - datetime.now()).total_seconds()
            if remaining > 0:
                return False, int(remaining)
    return True, 0

async def set_smuggle_cooldown(user_id: int, penalty: int = 0):
    base = await get_setting_int("smuggle_cooldown_minutes")
    cooldown_until = datetime.now() + timedelta(minutes=base + penalty)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO smuggle_cooldowns (user_id, cooldown_until)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET cooldown_until = $2
        ''', user_id, cooldown_until)

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
    days_bosses = await get_setting_int("cleanup_days_bosses")
    days_auctions = await get_setting_int("cleanup_days_auctions")
    days_purchases = await get_setting_int("cleanup_days_purchases")
    days_giveaways = await get_setting_int("cleanup_days_giveaways")
    days_tasks = await get_setting_int("cleanup_days_user_tasks")
    days_fight = await get_setting_int("cleanup_days_fight_logs")
    days_smuggle = await get_setting_int("cleanup_days_smuggle")
    days_orders = await get_setting_int("cleanup_days_bitcoin_orders")

    now = datetime.now()
    cutoff_bosses = (now - timedelta(days=days_bosses)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_purchases = (now - timedelta(days=days_purchases)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_giveaways = (now - timedelta(days=days_giveaways)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_tasks = (now - timedelta(days=days_tasks)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_smuggle = (now - timedelta(days=days_smuggle)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_auctions = now - timedelta(days=days_auctions)
    cutoff_fight = now - timedelta(days=days_fight)
    cutoff_orders = now - timedelta(days=days_orders)

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM bosses WHERE status IN ('defeated', 'expired') AND spawned_at < $1", cutoff_bosses)
        await conn.execute("DELETE FROM boss_attacks WHERE attack_time < $1", cutoff_bosses)
        await conn.execute("DELETE FROM purchases WHERE status IN ('completed','rejected') AND purchase_date < $1", cutoff_purchases)
        await conn.execute("DELETE FROM giveaways WHERE status='completed' AND end_date < $1", cutoff_giveaways)
        await conn.execute("DELETE FROM user_tasks WHERE expires_at IS NOT NULL AND expires_at < $1", cutoff_tasks)
        await conn.execute("DELETE FROM smuggle_runs WHERE status IN ('completed', 'failed') AND end_time < $1", cutoff_smuggle)
        await conn.execute("DELETE FROM auctions WHERE status='ended' AND end_time < $1", cutoff_auctions)
        await conn.execute("DELETE FROM fight_logs WHERE timestamp < $1", cutoff_fight)
        await conn.execute("DELETE FROM bitcoin_orders WHERE status IN ('completed', 'cancelled') AND created_at < $1", cutoff_orders)

        cooldown_minutes = await get_setting_int("fight_cooldown_minutes")
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

ALLOWED_TABLES = ['users', 'purchases', 'bosses', 'auctions', 'giveaways', 'tasks', 'chat_authority', 'fight_logs', 'bitcoin_orders']
async def export_table_to_csv(table: str) -> Optional[bytes]:
    if table not in ALLOWED_TABLES:
        return None
    async with db_pool.acquire() as conn:
        try:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
                table
            )
            if not exists:
                return None
            # Имя таблицы проверено по белому списку, можно безопасно подставить
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

# ==================== ФУНКЦИИ ДЛЯ БИТКОИН-БИРЖИ (ПОЛНОЦЕННЫЙ СТАКАН) ====================
async def get_order_book() -> Dict[str, List[Dict]]:
    async with db_pool.acquire() as conn:
        buy_orders = await conn.fetch("""
            SELECT price, SUM(amount) as total_amount, COUNT(*) as count
            FROM bitcoin_orders
            WHERE type='buy' AND status='active'
            GROUP BY price
            ORDER BY price DESC
        """)
        sell_orders = await conn.fetch("""
            SELECT price, SUM(amount) as total_amount, COUNT(*) as count
            FROM bitcoin_orders
            WHERE type='sell' AND status='active'
            GROUP BY price
            ORDER BY price ASC
        """)
        # Преобразуем Decimal в float для последующего использования
        bids = []
        for r in buy_orders:
            bids.append({
                'price': r['price'],
                'total_amount': float(r['total_amount']),
                'count': r['count']
            })
        asks = []
        for r in sell_orders:
            asks.append({
                'price': r['price'],
                'total_amount': float(r['total_amount']),
                'count': r['count']
            })
        return {
            'bids': bids,
            'asks': asks
        }

async def get_active_orders(order_type: str = None) -> List[dict]:
    async with db_pool.acquire() as conn:
        if order_type == 'buy':
            rows = await conn.fetch("SELECT * FROM bitcoin_orders WHERE type='buy' AND status='active' ORDER BY price DESC, created_at ASC")
        elif order_type == 'sell':
            rows = await conn.fetch("SELECT * FROM bitcoin_orders WHERE type='sell' AND status='active' ORDER BY price ASC, created_at ASC")
        else:
            rows = await conn.fetch("SELECT * FROM bitcoin_orders WHERE status='active' ORDER BY created_at DESC")
        # Преобразуем Decimal в float
        result = []
        for r in rows:
            d = dict(r)
            d['amount'] = float(d['amount'])
            d['total_locked'] = float(d['total_locked'])
            result.append(d)
        return result

async def create_bitcoin_order(user_id: int, order_type: str, amount: float, price: int) -> int:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            if order_type == 'sell':
                current_btc = await get_user_bitcoin(user_id)
                if current_btc < amount - 0.0001:
                    raise ValueError("Недостаточно BTC")
                await update_user_bitcoin(user_id, -amount, conn=conn)
                total_locked = amount
            else:
                total_cost = amount * price
                current_balance = await get_user_balance(user_id)
                if current_balance < total_cost - 0.01:
                    raise ValueError("Недостаточно баксов")
                await update_user_balance(user_id, -total_cost, conn=conn)
                total_locked = total_cost

            order_id = await conn.fetchval(
                "INSERT INTO bitcoin_orders (user_id, type, amount, price, total_locked) VALUES ($1, $2, $3, $4, $5) RETURNING id",
                user_id, order_type, amount, price, total_locked
            )
            # После создания заявки пытаемся сразу исполнить её
            await match_orders(conn)
            return order_id

async def cancel_bitcoin_order(order_id: int, user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow("SELECT * FROM bitcoin_orders WHERE id=$1 AND user_id=$2 AND status='active'", order_id, user_id)
            if not order:
                return False
            total_locked = float(order['total_locked'])  # преобразуем в float
            if order['type'] == 'sell':
                await update_user_bitcoin(user_id, total_locked, conn=conn)
            else:
                await update_user_balance(user_id, total_locked, conn=conn)
            await conn.execute("UPDATE bitcoin_orders SET status='cancelled' WHERE id=$1", order_id)
            return True

async def match_orders(conn):
    while True:
        buy = await conn.fetchrow("""
            SELECT id, user_id, price, amount, total_locked
            FROM bitcoin_orders
            WHERE type='buy' AND status='active'
            ORDER BY price DESC, created_at ASC
            LIMIT 1
        """)
        sell = await conn.fetchrow("""
            SELECT id, user_id, price, amount, total_locked
            FROM bitcoin_orders
            WHERE type='sell' AND status='active'
            ORDER BY price ASC, created_at ASC
            LIMIT 1
        """)
        if not buy or not sell or buy['price'] < sell['price']:
            break

        # Преобразуем Decimal в float
        buy_amount = float(buy['amount'])
        buy_total_locked = float(buy['total_locked'])
        sell_amount = float(sell['amount'])
        sell_total_locked = float(sell['total_locked'])
        trade_price = sell['price']

        trade_amount = min(buy_amount, sell_amount)
        total_cost = trade_amount * trade_price

        buyer_id = buy['user_id']
        seller_id = sell['user_id']

        await update_user_balance(seller_id, total_cost, conn=conn)
        await update_user_bitcoin(buyer_id, trade_amount, conn=conn)

        new_buy_amount = buy_amount - trade_amount
        new_sell_amount = sell_amount - trade_amount
        new_buy_locked = buy_total_locked - total_cost
        new_sell_locked = sell_total_locked - trade_amount

        if new_buy_amount <= 0.0001:
            await conn.execute("UPDATE bitcoin_orders SET status='completed', amount=0, total_locked=0 WHERE id=$1", buy['id'])
        else:
            await conn.execute("UPDATE bitcoin_orders SET amount=$1, total_locked=$2 WHERE id=$3", new_buy_amount, new_buy_locked, buy['id'])

        if new_sell_amount <= 0.0001:
            await conn.execute("UPDATE bitcoin_orders SET status='completed', amount=0, total_locked=0 WHERE id=$1", sell['id'])
        else:
            await conn.execute("UPDATE bitcoin_orders SET amount=$1, total_locked=$2 WHERE id=$3", new_sell_amount, new_sell_locked, sell['id'])

        await conn.execute(
            "INSERT INTO bitcoin_trades (buy_order_id, sell_order_id, amount, price, buyer_id, seller_id) VALUES ($1, $2, $3, $4, $5, $6)",
            buy['id'], sell['id'], trade_amount, trade_price, buyer_id, seller_id
        )

# ==================== КОНЕЦ ЧАСТИ 1 ====================
# ==================== ЧАСТЬ 2: СОСТОЯНИЯ FSM И КЛАВИАТУРЫ ====================

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

class AddBitcoin(StatesGroup):
    user_id = State()
    amount = State()

class RemoveBitcoin(StatesGroup):
    user_id = State()
    amount = State()

class AddAuthority(StatesGroup):
    user_id = State()
    amount = State()

class RemoveAuthority(StatesGroup):
    user_id = State()
    amount = State()

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

class EditAd(StatesGroup):
    ad_id = State()
    field = State()
    value = State()

class SellBitcoin(StatesGroup):
    amount = State()
    price = State()

class BuyBitcoin(StatesGroup):
    amount = State()
    price = State()

class CancelBitcoinOrder(StatesGroup):
    order_id = State()

# ----- НОВЫЕ СОСТОЯНИЯ ДЛЯ БИЗНЕСОВ (АДМИНКА) -----
class AddBusiness(StatesGroup):
    name = State()
    emoji = State()
    price = State()
    income = State()
    description = State()
    max_level = State()

class EditBusiness(StatesGroup):
    business_id = State()
    field = State()
    value = State()

class ToggleBusiness(StatesGroup):
    business_id = State()
    confirm = State()

# ----- СОСТОЯНИЯ ДЛЯ ПОКУПКИ/УЛУЧШЕНИЯ БИЗНЕСОВ -----
class BuyBusiness(StatesGroup):
    business_type_id = State()
    confirming = State()

class UpgradeBusiness(StatesGroup):
    business_id = State()
    confirming = State()

class AddMedia(StatesGroup):
    key = State()
    file = State()

class RemoveMedia(StatesGroup):
    key = State()

# ----- СОСТОЯНИЕ ДЛЯ УДАЛЕНИЯ РЕКЛАМЫ -----
class DeleteAd(StatesGroup):
    ad_id = State()

# ----- СОСТОЯНИЯ ДЛЯ БЫСТРОЙ ПОКУПКИ/ПРОДАЖИ ПО ЦЕНЕ (ИЗ СТАКАНА) -----
class BuyFromPrice(StatesGroup):
    price = State()
    orders = State()
    total_available = State()
    amount = State()

class SellToPrice(StatesGroup):
    price = State()
    orders = State()
    total_available = State()
    amount = State()

# ==================== КЛАВИАТУРЫ ====================

# ----- Общие клавиатуры -----
def back_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Назад")]], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def main_menu_keyboard(is_admin: bool = False):
    buttons = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус")],
        [KeyboardButton(text="🛒 Магазин подарков"), KeyboardButton(text="🎰 Казино")],
        [KeyboardButton(text="🎟 Промокод"), KeyboardButton(text="🏆 Топ игроков")],
        [KeyboardButton(text="💰 Мои покупки"), KeyboardButton(text="🔫 Ограбить")],
        [KeyboardButton(text="📋 Задания"), KeyboardButton(text="🔗 Рефералка")],
        [KeyboardButton(text="🎁 Розыгрыши"), KeyboardButton(text="📊 Уровень")],
        [KeyboardButton(text="🏷 Аукцион"), KeyboardButton(text="🏪 Мои бизнесы")],
        [KeyboardButton(text="💼 Биткоин-биржа")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ----- Клавиатуры для казино и игр -----
def casino_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎰 Играть в казино"), KeyboardButton(text="🎲 Кости")],
        [KeyboardButton(text="🔢 Угадай число"), KeyboardButton(text="🍒 Слоты")],
        [KeyboardButton(text="🎡 Рулетка"), KeyboardButton(text="👥 Мультиплеер 21")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def multiplayer_lobby_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Создать комнату")],
        [KeyboardButton(text="🔍 Найти комнату")],
        [KeyboardButton(text="📋 Список комнат")],
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

# ----- Клавиатуры для биткоин-биржи -----
def bitcoin_exchange_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📈 Купить BTC"), KeyboardButton(text="📉 Продать BTC")],
        [KeyboardButton(text="📋 Мои заявки"), KeyboardButton(text="📊 Стакан заявок")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def order_book_keyboard(book: Dict[str, List[Dict]]):
    kb = []
    if book['asks']:
        kb.append([InlineKeyboardButton(text="📉 Продажа (ASK) - лучшие цены", callback_data="noop")])
        for ask in book['asks'][:5]:
            kb.append([InlineKeyboardButton(
                text=f"💰 {ask['price']} $ | {ask['total_amount']:.4f} BTC ({ask['count']} заявок)",
                callback_data=f"buy_from_{ask['price']}"
            )])
    else:
        kb.append([InlineKeyboardButton(text="Нет активных продаж", callback_data="noop")])
    
    if book['bids']:
        kb.append([InlineKeyboardButton(text="📈 Покупка (BID) - лучшие цены", callback_data="noop")])
        for bid in book['bids'][:5]:
            kb.append([InlineKeyboardButton(
                text=f"💰 {bid['price']} $ | {bid['total_amount']:.4f} BTC ({bid['count']} заявок)",
                callback_data=f"sell_to_{bid['price']}"
            )])
    else:
        kb.append([InlineKeyboardButton(text="Нет активных покупок", callback_data="noop")])
    
    kb.append([InlineKeyboardButton(text="« Назад", callback_data="exchange_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def bitcoin_orders_keyboard(orders: List[dict], order_type: str, page: int = 1, total_pages: int = 1):
    kb = []
    for order in orders:
        kb.append([InlineKeyboardButton(
            text=f"{order['amount']:.4f} BTC @ {order['price']} $ (ID: {order['id']})",
            callback_data=f"{order_type}_order_{order['id']}"
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{order_type}_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{order_type}_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("« Назад", callback_data="exchange_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def my_orders_keyboard(orders: List[dict], page: int = 1, total_pages: int = 1):
    kb = []
    for order in orders:
        order_type_emoji = "📈" if order['type'] == 'buy' else "📉"
        kb.append([InlineKeyboardButton(
            text=f"{order_type_emoji} {order['amount']:.4f} BTC @ {order['price']} $",
            callback_data=f"myorder_{order['id']}"
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"myorders_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"myorders_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("« Назад", callback_data="exchange_back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ----- Клавиатуры для бизнесов -----
def business_main_keyboard(businesses: List[dict]):
    kb = []
    for biz in businesses:
        kb.append([InlineKeyboardButton(
            text=f"{biz['emoji']} {biz['name']} (ур. {biz['level']}) | Накоплено: {biz['accumulated']//100} баксов",
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

def business_buy_keyboard(business_types: List[dict]):
    kb = []
    for bt in business_types:
        kb.append([InlineKeyboardButton(
            text=f"{bt['emoji']} {bt['name']} – {bt['base_price_btc']} BTC",
            callback_data=f"buy_biz_{bt['id']}"
        )])
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
        display = f"#{gw['id']} | {gw['prize']} | {gw['winners_list'][:20]}" if gw['winners_list'] else f"#{gw['id']} | {gw['prize']}"
        kb.append([InlineKeyboardButton(text=display, callback_data=f"completed_gw_{gw['id']}")])
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

# ----- Клавиатуры для повтора ставок -----
def repeat_bet_keyboard(game: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"repeat_{game}")]
    ])

# ----- Административные клавиатуры (полные) -----
def admin_main_keyboard(permissions: List[str]):
    buttons = []
    row1 = []
    if "manage_users" in permissions:
        row1.append(KeyboardButton("👥 Пользователи"))
    if "manage_shop" in permissions:
        row1.append(KeyboardButton("🛒 Магазин"))
    if "manage_giveaways" in permissions:
        row1.append(KeyboardButton("🎁 Розыгрыши"))
    if row1:
        buttons.append(row1)

    row2 = []
    if "manage_bosses" in permissions:
        row2.append(KeyboardButton("👾 Боссы"))
    if "manage_businesses" in permissions:
        row2.append(KeyboardButton("🏪 Бизнесы"))
    if "manage_auctions" in permissions:
        row2.append(KeyboardButton("🏷 Аукцион"))
    if row2:
        buttons.append(row2)

    row3 = []
    if "manage_channels" in permissions:
        row3.append(KeyboardButton("📢 Каналы"))
    if "manage_chats" in permissions:
        row3.append(KeyboardButton("🤖 Чаты"))
    if "manage_promocodes" in permissions:
        row3.append(KeyboardButton("🎫 Промокоды"))
    if row3:
        buttons.append(row3)

    row4 = []
    if "manage_ads" in permissions:
        row4.append(KeyboardButton("📢 Реклама"))
    if "manage_exchange" in permissions:
        row4.append(KeyboardButton("💼 Биржа"))
    if "manage_media" in permissions:
        row4.append(KeyboardButton("🖼 Медиа"))
    if row4:
        buttons.append(row4)

    row5 = []
    if "manage_bans" in permissions:
        row5.append(KeyboardButton("🔨 Блокировки"))
    if "manage_admins" in permissions:
        row5.append(KeyboardButton("➕ Админы"))
    if row5:
        buttons.append(row5)

    row6 = []
    if "view_stats" in permissions:
        row6.append(KeyboardButton("📊 Статистика"))
    if "broadcast" in permissions:
        row6.append(KeyboardButton("📢 Рассылка"))
    if "cleanup" in permissions:
        row6.append(KeyboardButton("🧹 Очистка"))
    if row6:
        buttons.append(row6)

    row7 = []
    if "edit_settings" in permissions:
        row7.append(KeyboardButton("⚙️ Настройки"))
    row7.append(KeyboardButton("◀️ Назад в главное меню"))
    buttons.append(row7)

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_users_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("💰 Начислить баксы"), KeyboardButton("💸 Списать баксы")],
        [KeyboardButton("⭐️ Начислить репутацию"), KeyboardButton("🔻 Снять репутацию")],
        [KeyboardButton("📈 Начислить опыт"), KeyboardButton("🔝 Установить уровень")],
        [KeyboardButton("₿ Начислить биткоины"), KeyboardButton("₿ Списать биткоины")],
        [KeyboardButton("⚔️ Начислить авторитет"), KeyboardButton("⚔️ Списать авторитет")],
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

def admin_exchange_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("📋 Активные заявки")],
        [KeyboardButton("❌ Удалить заявку (по ID)")],
        [KeyboardButton("📊 История сделок")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_business_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("📋 Список бизнесов")],
        [KeyboardButton("➕ Добавить бизнес")],
        [KeyboardButton("✏️ Редактировать бизнес")],
        [KeyboardButton("🔄 Переключить доступность")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_media_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("➕ Добавить медиа")],
        [KeyboardButton("➖ Удалить медиа")],
        [KeyboardButton("📋 Список медиа")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def admin_helper_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("📋 Активные помощники")],
        [KeyboardButton("📊 Топы чатов")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def settings_categories_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton("⚙️ Кража")],
        [KeyboardButton("⚙️ Казино и игры")],
        [KeyboardButton("⚙️ Ограничения по уровню")],
        [KeyboardButton("⚙️ Уведомления")],
        [KeyboardButton("⚙️ Подгон")],
        [KeyboardButton("⚙️ Рефералы")],
        [KeyboardButton("⚙️ Опыт и уровни")],
        [KeyboardButton("⚙️ Репутация")],
        [KeyboardButton("⚙️ Боссы")],
        [KeyboardButton("⚙️ Статы за уровень")],
        [KeyboardButton("⚙️ Аукцион")],
        [KeyboardButton("⚙️ Бой в чатах")],
        [KeyboardButton("⚙️ Качалка (авторитет)")],
        [KeyboardButton("⚙️ Бизнесы")],
        [KeyboardButton("⚙️ Контрабанда")],
        [KeyboardButton("⚙️ Биткоины")],
        [KeyboardButton("⚙️ Биткоин-биржа")],
        [KeyboardButton("⚙️ Очистка логов")],
        [KeyboardButton("⚙️ Автоудаление")],
        [KeyboardButton("⚙️ Стартовый бонус")],
        [KeyboardButton("⚙️ Глобальный кулдаун")],
        [KeyboardButton("◀️ Назад в админку")]
    ], resize_keyboard=True)

def settings_param_keyboard(params: List[Tuple[str, str]], category: str):
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

def cancel_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])

# ==================== КОНЕЦ ЧАСТИ 2 ====================
# ==================== ЧАСТЬ 3: ПОЛЬЗОВАТЕЛЬСКИЕ ХЕНДЛЕРЫ (ЛИЧНЫЕ СООБЩЕНИЯ) ====================

# ----- Вспомогательная функция для отправки с медиа -----
async def send_with_media(chat_id: int, text: str, media_key: str = None, **kwargs):
    """
    Отправляет сообщение с возможным прикреплением фото из таблицы media.
    Если media_key указан и в таблице есть file_id, отправляется фото с caption=text.
    Иначе отправляется обычное текстовое сообщение.
    """
    if media_key:
        file_id = await get_media_file_id(media_key)
        if file_id:
            try:
                await bot.send_photo(chat_id, file_id, caption=text, **kwargs)
                return
            except Exception as e:
                logging.error(f"Ошибка отправки фото с ключом {media_key}: {e}")
                # fallback на текстовое сообщение
    await safe_send_message(chat_id, text, **kwargs)

# ==================== ГЛОБАЛЬНЫЙ ОБРАБОТЧИК /cancel ====================
@dp.message_handler(commands=['cancel'], state='*')
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    user_id = message.from_user.id
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    await message.answer("❌ Действие отменено.", reply_markup=main_menu_keyboard(await is_admin(user_id)))

# ==================== УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК КНОПКИ "НАЗАД" ====================
@dp.message_handler(lambda message: message.text == "◀️ Назад", state='*')
async def universal_back_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    user_id = message.from_user.id
    is_admin_user = await is_admin(user_id)

    if current_state is None:
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard(is_admin_user))
        return

    # Определяем группу состояний
    if current_state.startswith('CasinoBet') or current_state.startswith('DiceBet') or \
       current_state.startswith('GuessBet') or current_state.startswith('SlotsBet') or \
       current_state.startswith('RouletteBet'):
        await state.finish()
        await casino_menu(message)

    elif current_state.startswith('AddBalance') or current_state.startswith('RemoveBalance') or \
         current_state.startswith('AddReputation') or current_state.startswith('RemoveReputation') or \
         current_state.startswith('AddExp') or current_state.startswith('SetLevel') or \
         current_state.startswith('AddBitcoin') or current_state.startswith('RemoveBitcoin') or \
         current_state.startswith('AddAuthority') or current_state.startswith('RemoveAuthority') or \
         current_state.startswith('FindUser'):
        await state.finish()
        await admin_users_menu(message)

    elif current_state.startswith('AddShopItem') or current_state.startswith('RemoveShopItem') or \
         current_state.startswith('EditShopItem'):
        await state.finish()
        await admin_shop_menu(message)

    elif current_state.startswith('CreateGiveaway') or current_state.startswith('CompleteGiveaway'):
        await state.finish()
        await admin_giveaway_menu(message)

    elif current_state.startswith('AddChannel') or current_state.startswith('RemoveChannel'):
        await state.finish()
        await admin_channel_menu(message)

    elif current_state.startswith('CreatePromocode'):
        await state.finish()
        await admin_promo_menu(message)

    elif current_state.startswith('CreateTask') or current_state.startswith('DeleteTask'):
        await state.finish()
        await admin_tasks_menu(message)

    elif current_state.startswith('BlockUser') or current_state.startswith('UnblockUser'):
        await state.finish()
        await admin_ban_menu(message)

    elif current_state.startswith('AddJuniorAdmin') or current_state.startswith('RemoveJuniorAdmin') or \
         current_state.startswith('EditAdminPermissions'):
        await state.finish()
        await admin_admins_menu(message)

    elif current_state.startswith('BossSpawn') or current_state.startswith('DeleteBoss'):
        await state.finish()
        await admin_boss_menu(message)

    elif current_state.startswith('CreateAuction') or current_state.startswith('AuctionBid') or \
         current_state.startswith('CancelAuction'):
        await state.finish()
        await admin_auction_menu(message)

    elif current_state.startswith('CreateAd') or current_state.startswith('EditAd') or \
         current_state.startswith('DeleteAd'):
        await state.finish()
        await admin_ad_menu(message)

    elif current_state.startswith('SellBitcoin') or current_state.startswith('BuyBitcoin') or \
         current_state.startswith('CancelBitcoinOrder') or current_state.startswith('BuyFromPrice') or \
         current_state.startswith('SellToPrice'):
        await state.finish()
        await bitcoin_exchange_menu(message)

    elif current_state.startswith('BuyBusiness') or current_state.startswith('UpgradeBusiness'):
        await state.finish()
        await my_businesses(message)

    elif current_state.startswith('AddBusiness') or current_state.startswith('EditBusiness') or \
         current_state.startswith('ToggleBusiness'):
        await state.finish()
        await admin_business_menu(message)

    elif current_state.startswith('AddMedia') or current_state.startswith('RemoveMedia'):
        await state.finish()
        await admin_media_menu(message)

    elif current_state.startswith('MultiplayerGame') or current_state.startswith('RoomChat'):
        await state.finish()
        await multiplayer_menu(message)

    elif current_state.startswith('TheftTarget'):
        await state.finish()
        await theft_menu(message)

    elif current_state.startswith('PromoActivate'):
        await state.finish()
        await promo_handler(message)

    else:
        await state.finish()
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard(is_admin_user))

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

    # Создаём пользователя (с бонусом)
    created, bonus = await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    if created:
        await message.answer(f"🎁 Вам начислен стартовый бонус: {bonus} баксов!")

    # Отправляем приветственную картинку из медиа
    welcome_text = "Добро пожаловать в Malboro GAME!"
    await send_with_media(user_id, welcome_text, media_key='welcome')

    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer(
            "❗️ Для использования бота необходимо подписаться на наши каналы:",
            reply_markup=subscription_inline(not_subscribed)
        )
        return

    is_admin_user = await is_admin(user_id)
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в <b>Malboro GAME</b>! 🚬\n"
        f"Тут ты найдёшь: казино, розыгрыши, магазин, аукцион, биткоин-биржу.\n"
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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    text = (
        "📚 <b>Доступные команды и разделы</b>\n\n"
        "👤 Профиль – статистика и характеристики\n"
        "🎁 Бонус – ежедневный бонус\n"
        "🛒 Магазин подарков – покупка подарков\n"
        "🎰 Казино – азартные игры (кости, угадайка, слоты, рулетка, мультиплеер 21)\n"
        "🎟 Промокод – активация промокодов\n"
        "🏆 Топ игроков – рейтинг по баксам, репутации, биткоинам и т.д.\n"
        "💰 Мои покупки – история заказов\n"
        "🔫 Ограбить – укради баксы у другого\n"
        "📋 Задания – выполняй и получай награды\n"
        "🔗 Рефералка – приглашай друзей\n"
        "📊 Уровень – твой прогресс\n"
        "🎁 Розыгрыши – активные и завершённые\n"
        "🏷 Аукцион – участвуй в торгах\n"
        "🏪 Мои бизнесы – управление бизнесом (покупка за BTC)\n"
        "💼 Биткоин-биржа – продавай и покупай BTC за баксы\n"
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
    await ensure_user_exists(user_id, callback.from_user.username, callback.from_user.first_name)
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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
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
                "COALESCE(smuggle_success, 0) as smuggle_success, "
                "COALESCE(smuggle_fail, 0) as smuggle_fail, "
                "bitcoin_balance, authority_balance "
                "FROM users WHERE user_id=$1",
                user_id
            )
        if row:
            balance = float(row['balance'] or 0)
            rep = row['reputation'] or 0
            spent = float(row['total_spent'] or 0)
            neg = float(row['negative_balance'] or 0)
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
            smuggle_success = row['smuggle_success'] or 0
            smuggle_fail = row['smuggle_fail'] or 0
            bitcoin = float(row['bitcoin_balance']) if row['bitcoin_balance'] is not None else 0.0
            authority = row['authority_balance'] or 0

            neg_text = f" (долг: {neg:.2f})" if neg > 0 else ""
            level_mult = await get_setting_int("level_multiplier")
            exp_needed = level * level_mult
            bar = progress_bar(exp, exp_needed, 10)

            total_authority_chat = await get_total_user_authority(user_id)
            total_fights, total_damage = await get_total_user_fights(user_id)

            joined_str = joined if joined else 'неизвестно'

            text = (
                f"👤 <b>Твой профиль</b>\n"
                f"📊 <b>Уровень:</b> {level}\n"
                f"📈 <b>Опыт:</b> {exp}/{exp_needed}\n{bar}\n"
                f"💪 Сила: {strength} | 🏃 Ловкость: {agility} | 🛡 Защита: {defense}\n"
                f"💰 Баланс: {balance:.2f} баксов{neg_text}\n"
                f"₿ Биткоины: {bitcoin:.4f} BTC\n"
                f"⭐️ Репутация: {rep}\n"
                f"⚔️ Авторитет (прокачка): {authority}\n"
                f"🗣 Авторитет в чатах: {total_authority_chat} (боёв: {total_fights}, урон: {total_damage})\n"
                f"💸 Всего потрачено: {spent:.2f} баксов\n"
                f"📅 Зарегистрирован: {joined_str}\n"
                f"🔫 Ограблений: {attempts} (успешно: {success}, провал: {failed})\n"
                f"🛡 Отбито атак: {protected}\n"
                f"🎰 Казино: побед {cw}, поражений {cl}\n"
                f"🎲 Кости: побед {dw}, поражений {dl}\n"
                f"🔢 Угадайка: побед {gw}, поражений {gl}\n"
                f"🍒 Слоты: побед {sw}, поражений {sl}\n"
                f"🎡 Рулетка: побед {rw}, поражений {rl}\n"
                f"👥 Мультиплеер: побед {mpw}, поражений {mpl}\n"
                f"📦 Контрабанда: успешно {smuggle_success}, провал {smuggle_fail}"
            )
        else:
            text = "Профиль не найден"
    except Exception as e:
        logging.error(f"Profile error: {e}")
        text = "❌ Ошибка загрузки профиля. Подробности в логах."

    # Отправляем с картинкой, если есть медиа с ключом 'profile'
    await send_with_media(user_id, text, media_key='profile', reply_markup=main_menu_keyboard(await is_admin(user_id)))

# ==================== УРОВЕНЬ ====================
@dp.message_handler(lambda message: message.text == "📊 Уровень")
async def level_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    level = await get_user_level(user_id)
    exp = await get_user_exp(user_id)
    level_mult = await get_setting_int("level_multiplier")
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
        f"Следующая награда: +{next_coins:.2f} баксов, +{next_rep} репутации."
    )
    await message.answer(text, reply_markup=main_menu_keyboard(await is_admin(user_id)))

async def get_level_reward_coins(level: int) -> float:
    async with db_pool.acquire() as conn:
        val = await conn.fetchval("SELECT coins FROM level_rewards WHERE level=$1", level)
        return float(val) if val else 0.0

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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    rep = await get_user_reputation(user_id)
    theft_bonus = float(await get_setting_float("reputation_theft_bonus")) * rep
    defense_bonus = float(await get_setting_float("reputation_defense_bonus")) * rep
    smuggle_bonus = float(await get_setting_float("reputation_smuggle_bonus")) * rep
    smuggle_success_bonus = float(await get_setting_float("reputation_smuggle_success_bonus")) * rep
    max_bonus = await get_setting_float("reputation_max_bonus_percent")
    
    theft_bonus = min(theft_bonus, max_bonus)
    defense_bonus = min(defense_bonus, max_bonus)
    smuggle_success_bonus = min(smuggle_success_bonus, max_bonus)
    
    await message.answer(
        f"⭐️ Твоя репутация: {rep}\n\n"
        f"Репутация увеличивает шансы и добычу (макс. +{max_bonus}%):\n"
        f"🔫 Бонус к грабежу: +{theft_bonus:.1f}%\n"
        f"🛡 Бонус к защите: +{defense_bonus:.1f}%\n"
        f"📦 Бонус к добыче BTC: +{smuggle_bonus:.1f} BTC\n"
        f"🚤 Бонус к успеху контрабанды: +{smuggle_success_bonus:.1f}%\n\n"
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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Самые богатые")],
        [KeyboardButton(text="💸 Транжиры")],
        [KeyboardButton(text="🔫 Крадуны")],
        [KeyboardButton(text="⭐️ По репутации")],
        [KeyboardButton(text="₿ По биткоинам")],
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
            if order_field == 'bitcoin_balance':
                order_expr = "bitcoin_balance"
            else:
                order_expr = order_field
            total = await conn.fetchval(f"SELECT COUNT(*) FROM users")
            rows = await conn.fetch(
                f"SELECT first_name, {order_expr} as value FROM users ORDER BY value DESC LIMIT $1 OFFSET $2",
                ITEMS_PER_PAGE, offset
            )
        if not rows:
            await message.answer("Нет данных.")
            return
        text = f"{title} (страница {page}):\n\n"
        for idx, row in enumerate(rows, start=offset+1):
            val = row['value']
            if order_field == 'bitcoin_balance':
                val = f"{float(val):.4f}"
            elif order_field in ['balance', 'total_spent']:
                val = f"{float(val):.2f}"
            text += f"{idx}. {row['first_name']} – {val}\n"
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

@dp.message_handler(lambda message: message.text == "₿ По биткоинам")
async def top_bitcoin_handler(message: types.Message):
    await show_top(message, "bitcoin_balance", "₿ По биткоинам")

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
        "bitcoin_balance": "₿ По биткоинам",
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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    min_level = await get_setting_int("min_level_casino")
    level = await get_user_level(user_id)
    if level < min_level:
        await message.answer(f"❌ Для доступа к казино нужен {min_level} уровень. Твой уровень: {level}")
        return
    # Отправляем картинку казино, если есть
    await send_with_media(user_id, "Выбери игру:", media_key='casino', reply_markup=casino_menu_keyboard())

# ----- Казино (простое) с анимацией -----
@dp.message_handler(lambda message: message.text == "🎰 Играть в казино")
async def casino_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    min_level = await get_setting_int("min_level_casino")
    level = await get_user_level(user_id)
    if level < min_level:
        await message.answer(f"❌ Для этой игры нужен {min_level} уровень. Твой уровень: {level}")
        return
    await message.answer("Введи сумму ставки (можно дробную, например 10.50):", reply_markup=back_keyboard())
    await CasinoBet.amount.set()

async def save_last_bet(user_id: int, game: str, amount: float, bet_data: dict = None):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_last_bets (user_id, game, bet_amount, bet_data, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id, game) DO UPDATE SET
                bet_amount = EXCLUDED.bet_amount,
                bet_data = EXCLUDED.bet_data,
                updated_at = NOW()
        """, user_id, game, amount, json.dumps(bet_data) if bet_data else None)

@dp.message_handler(state=CasinoBet.amount)
async def casino_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    
    # Проверка глобального кулдауна (перенесена в начало)
    ok, remaining = await check_global_cooldown(message.from_user.id, "casino")
    if not ok:
        await message.answer(f"⏳ Подожди ещё {remaining} сек перед следующей игрой.")
        return
    
    try:
        amount = float(message.text)
        if amount <= 0 or amount % 0.01 != 0:
            raise ValueError
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Введи положительное число с точностью до сотых (например, 10.50).")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    min_bet = await get_setting_float("casino_min_bet")
    max_bet = await get_setting_float("casino_max_bet")
    max_input = await get_setting_float("max_input_number")
    if amount < min_bet or amount > max_bet:
        await message.answer(f"❌ Ставка должна быть от {min_bet:.2f} до {max_bet:.2f}.")
        return
    if amount > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return

    win_chance = await get_setting_float("casino_win_chance")
    multiplier = await get_setting_float("casino_multiplier")

    anim = await message.answer("🎰 Крутим барабан...")
    await asyncio.sleep(1)
    await anim.edit_text("🎰 🎰 🎰")
    await asyncio.sleep(1)

    win = random.random() * 100 <= win_chance

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'casino', win, conn=conn)

        if win:
            profit = amount * (multiplier - 1)
            await update_user_balance(user_id, amount * multiplier, conn=conn)
            exp = await get_setting_int("exp_per_casino_win")
            btc_reward = await get_setting_int("bitcoin_per_casino_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
                btc_text = f" и {btc_reward} BTC"
            else:
                btc_text = ""
            phrase = get_random_phrase(CASINO_WIN_PHRASES, win=amount*multiplier, profit=profit)
            if amount * multiplier >= BIG_WIN_THRESHOLD and await get_setting("chat_notify_big_win") == "1":
                await notify_chats(f"🔥 {message.from_user.first_name} сорвал куш в казино: +{amount * multiplier:.2f} баксов!{btc_text}")
        else:
            exp = await get_setting_int("exp_per_casino_lose")
            phrase = get_random_phrase(CASINO_LOSE_PHRASES, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'casino', amount)
    await set_global_cooldown(user_id, "casino")

    await anim.edit_text(phrase, reply_markup=repeat_bet_keyboard('casino'))
    await state.finish()

# ----- Кости -----
@dp.message_handler(lambda message: message.text == "🎲 Кости")
async def dice_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    min_level = await get_setting_int("min_level_dice")
    level = await get_user_level(user_id)
    if level < min_level:
        await message.answer(f"❌ Для этой игры нужен {min_level} уровень. Твой уровень: {level}")
        return
    await send_with_media(user_id, "Введи сумму ставки (можно дробную):", media_key='dice', reply_markup=back_keyboard())
    await DiceBet.amount.set()

@dp.message_handler(state=DiceBet.amount)
async def dice_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    
    ok, remaining = await check_global_cooldown(message.from_user.id, "dice")
    if not ok:
        await message.answer(f"⏳ Подожди ещё {remaining} сек.")
        return
    
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Введи положительное число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    min_bet = 1.0
    max_bet = await get_setting_float("casino_max_bet")  # используем общий максимум казино
    max_input = await get_setting_float("max_input_number")
    if amount < min_bet:
        await message.answer(f"❌ Минимальная ставка {min_bet:.2f} бакса.")
        return
    if amount > max_bet:
        await message.answer(f"❌ Максимальная ставка {max_bet:.2f}.")
        return
    if amount > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return

    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    threshold = await get_setting_int("dice_win_threshold")
    win = total > threshold

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'dice', win, conn=conn)
        if win:
            multiplier = await get_setting_float("dice_multiplier")
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = await get_setting_int("exp_per_dice_win")
            btc_reward = await get_setting_int("bitcoin_per_dice_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(DICE_WIN_PHRASES, dice1=dice1, dice2=dice2, total=total, profit=profit)
        else:
            exp = await get_setting_int("exp_per_dice_lose")
            phrase = get_random_phrase(DICE_LOSE_PHRASES, dice1=dice1, dice2=dice2, total=total, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'dice', amount)
    await set_global_cooldown(user_id, "dice")

    await message.answer(phrase, reply_markup=repeat_bet_keyboard('dice'))
    await state.finish()

# ----- Угадай число -----
@dp.message_handler(lambda message: message.text == "🔢 Угадай число")
async def guess_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    min_level = await get_setting_int("min_level_guess")
    level = await get_user_level(user_id)
    if level < min_level:
        await message.answer(f"❌ Для этой игры нужен {min_level} уровень. Твой уровень: {level}")
        return
    await send_with_media(user_id, "Введи сумму ставки (можно дробную):", media_key='guess', reply_markup=back_keyboard())
    await GuessBet.amount.set()

@dp.message_handler(state=GuessBet.amount)
async def guess_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    
    ok, remaining = await check_global_cooldown(message.from_user.id, "guess")
    if not ok:
        await message.answer(f"⏳ Подожди ещё {remaining} сек.")
        return
    
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Введи положительное число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    min_bet = 1.0
    max_bet = await get_setting_float("casino_max_bet")
    max_input = await get_setting_float("max_input_number")
    if amount < min_bet:
        await message.answer(f"❌ Минимальная ставка {min_bet:.2f}.")
        return
    if amount > max_bet:
        await message.answer(f"❌ Максимальная ставка {max_bet:.2f}.")
        return
    if amount > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
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
            multiplier = await get_setting_float("guess_multiplier")
            rep_reward = await get_setting_int("guess_reputation")
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            await update_user_reputation(user_id, rep_reward)
            exp = await get_setting_int("exp_per_guess_win")
            btc_reward = await get_setting_int("bitcoin_per_guess_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(GUESS_WIN_PHRASES, secret=secret, profit=profit, rep=rep_reward)
            bet_data = {'number': guess}
        else:
            exp = await get_setting_int("exp_per_guess_lose")
            phrase = get_random_phrase(GUESS_LOSE_PHRASES, secret=secret, loss=amount)
            bet_data = {'number': guess}
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'guess', amount, bet_data)
    await set_global_cooldown(user_id, "guess")

    await message.answer(phrase, reply_markup=repeat_bet_keyboard('guess'))
    await state.finish()

# ----- Слоты -----
@dp.message_handler(lambda message: message.text == "🍒 Слоты")
async def slots_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    min_level = await get_setting_int("min_level_slots")
    level = await get_user_level(user_id)
    if level < min_level:
        await message.answer(f"❌ Для этой игры нужен {min_level} уровень. Твой уровень: {level}")
        return
    await send_with_media(user_id, "Введи сумму ставки (можно дробную):", media_key='slots', reply_markup=back_keyboard())
    await SlotsBet.amount.set()

@dp.message_handler(state=SlotsBet.amount)
async def slots_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    
    ok, remaining = await check_global_cooldown(message.from_user.id, "slots")
    if not ok:
        await message.answer(f"⏳ Подожди ещё {remaining} сек.")
        return
    
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Введи положительное число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    min_bet = await get_setting_float("slots_min_bet")
    max_bet = await get_setting_float("slots_max_bet")
    max_input = await get_setting_float("max_input_number")
    if amount < min_bet or amount > max_bet:
        await message.answer(f"❌ Ставка должна быть от {min_bet:.2f} до {max_bet:.2f}.")
        return
    if amount > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
        return
    if amount > balance:
        await message.answer("❌ Недостаточно баксов.")
        return

    anim = await message.answer("🍒 Запускаем слоты...")
    stages = [
        "🍒 | 🍋 | 🍊",
        "🍋 | 🍊 | 7️⃣",
        "🍊 | 7️⃣ | 💎",
        "7️⃣ | 💎 | 🍒",
    ]
    for stage in stages:
        await asyncio.sleep(0.3)
        await anim.edit_text(stage)

    symbols, multiplier, win = await slots_spin()
    result_str = format_slots_result(symbols)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'slots', win, conn=conn)
        if win:
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = await get_setting_int("exp_per_slots_win")
            btc_reward = await get_setting_int("bitcoin_per_slots_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(SLOTS_WIN_PHRASES, combo=result_str, multiplier=multiplier, profit=profit)
        else:
            exp = await get_setting_int("exp_per_slots_lose")
            phrase = get_random_phrase(SLOTS_LOSE_PHRASES, combo=result_str, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'slots', amount)
    await set_global_cooldown(user_id, "slots")

    await anim.edit_text(phrase, reply_markup=repeat_bet_keyboard('slots'))
    await state.finish()

# ----- Рулетка -----
@dp.message_handler(lambda message: message.text == "🎡 Рулетка")
async def roulette_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    min_level = await get_setting_int("min_level_roulette")
    level = await get_user_level(user_id)
    if level < min_level:
        await message.answer(f"❌ Для этой игры нужен {min_level} уровень. Твой уровень: {level}")
        return
    await send_with_media(user_id, "Введи сумму ставки (можно дробную):", media_key='roulette', reply_markup=back_keyboard())
    await RouletteBet.amount.set()

@dp.message_handler(state=RouletteBet.amount)
async def roulette_bet_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await casino_menu(message)
        return
    
    ok, remaining = await check_global_cooldown(message.from_user.id, "roulette")
    if not ok:
        await message.answer(f"⏳ Подожди ещё {remaining} сек.")
        return
    
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Введи положительное число.")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    min_bet = await get_setting_float("roulette_min_bet")
    max_bet = await get_setting_float("roulette_max_bet")
    max_input = await get_setting_float("max_input_number")
    if amount < min_bet or amount > max_bet:
        await message.answer(f"❌ Ставка должна быть от {min_bet:.2f} до {max_bet:.2f}.")
        return
    if amount > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
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

    anim = await message.answer("🎡 Крутим рулетку...")
    for _ in range(3):
        await asyncio.sleep(0.5)
        await anim.edit_text("🎡 • •")
        await asyncio.sleep(0.5)
        await anim.edit_text("• 🎡 •")
        await asyncio.sleep(0.5)
        await anim.edit_text("• • 🎡")

    number, color, win = await roulette_spin(bet_type, bet_number)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'roulette', win, conn=conn)
        if win:
            if bet_type == 'number':
                multiplier = await get_setting_float("roulette_number_multiplier")
            elif bet_type == 'green':
                multiplier = await get_setting_float("roulette_green_multiplier")
            else:
                multiplier = await get_setting_float("roulette_color_multiplier")
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = await get_setting_int("exp_per_roulette_win")
            btc_reward = await get_setting_int("bitcoin_per_roulette_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(ROULETTE_WIN_PHRASES, number=number, color=color, profit=profit)
            bet_data = {'bet_type': bet_type, 'number': bet_number}
        else:
            exp = await get_setting_int("exp_per_roulette_lose")
            phrase = get_random_phrase(ROULETTE_LOSE_PHRASES, number=number, color=color, loss=amount)
            bet_data = {'bet_type': bet_type, 'number': bet_number}
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'roulette', amount, bet_data)
    await set_global_cooldown(user_id, "roulette")

    await anim.edit_text(phrase, reply_markup=repeat_bet_keyboard('roulette'))
    await state.finish()

# ----- Обработчик повтора ставки (с сохранением данных) -----
@dp.callback_query_handler(lambda c: c.data.startswith("repeat_"))
async def repeat_bet_callback(callback: types.CallbackQuery, state: FSMContext):
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id
    await ensure_user_exists(user_id, callback.from_user.username, callback.from_user.first_name)
    
    # Сначала проверяем глобальный кулдаун
    ok, remaining = await check_global_cooldown(user_id, game)
    if not ok:
        await callback.answer(f"⏳ Подожди ещё {remaining} сек.", show_alert=True)
        return
    
    async with db_pool.acquire() as conn:
        last = await conn.fetchrow(
            "SELECT bet_amount, bet_data FROM user_last_bets WHERE user_id=$1 AND game=$2",
            user_id, game
        )
        if not last:
            await callback.answer("У тебя нет сохранённой ставки для этой игры.", show_alert=True)
            return
        
        amount = float(last['bet_amount'])
        bet_data = json.loads(last['bet_data']) if last['bet_data'] else {}
    
    balance = await get_user_balance(user_id)
    if amount > balance:
        await callback.answer("❌ Недостаточно баксов для повтора ставки.", show_alert=True)
        return
    
    # Для игр, требующих параметры, проверяем их наличие
    if game == 'guess' and 'number' not in bet_data:
        await callback.answer("❌ Нет сохранённого числа для повтора.", show_alert=True)
        return
    if game == 'roulette' and ('bet_type' not in bet_data or (bet_data.get('bet_type') == 'number' and 'number' not in bet_data)):
        await callback.answer("❌ Нет сохранённых параметров для повтора.", show_alert=True)
        return
    
    # Запускаем соответствующую игру
    if game == 'casino':
        await process_casino_repeat(user_id, amount, callback.message)
    elif game == 'dice':
        await process_dice_repeat(user_id, amount, callback.message)
    elif game == 'guess':
        number = bet_data.get('number')
        await process_guess_repeat(user_id, amount, number, callback.message)
    elif game == 'slots':
        await process_slots_repeat(user_id, amount, callback.message)
    elif game == 'roulette':
        bet_type = bet_data.get('bet_type')
        number = bet_data.get('number')
        await process_roulette_repeat(user_id, amount, bet_type, number, callback.message)
    
    await set_global_cooldown(user_id, game)
    await callback.answer()

# Вспомогательные функции для повтора
async def process_casino_repeat(user_id: int, amount: float, message: types.Message):
    win_chance = await get_setting_float("casino_win_chance")
    multiplier = await get_setting_float("casino_multiplier")
    
    anim = await message.answer("🎰 Повторяем...")
    await asyncio.sleep(1)
    await anim.edit_text("🎰 🎰 🎰")
    await asyncio.sleep(1)
    
    win = random.random() * 100 <= win_chance
    
    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'casino', win, conn=conn)
        if win:
            profit = amount * (multiplier - 1)
            await update_user_balance(user_id, amount * multiplier, conn=conn)
            exp = await get_setting_int("exp_per_casino_win")
            btc_reward = await get_setting_int("bitcoin_per_casino_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(CASINO_WIN_PHRASES, win=amount*multiplier, profit=profit)
        else:
            exp = await get_setting_int("exp_per_casino_lose")
            phrase = get_random_phrase(CASINO_LOSE_PHRASES, loss=amount)
        await add_exp(user_id, exp, conn=conn)
    
    await save_last_bet(user_id, 'casino', amount)
    await anim.edit_text(phrase, reply_markup=repeat_bet_keyboard('casino'))

async def process_dice_repeat(user_id: int, amount: float, message: types.Message):
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    threshold = await get_setting_int("dice_win_threshold")
    win = total > threshold

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'dice', win, conn=conn)
        if win:
            multiplier = await get_setting_float("dice_multiplier")
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = await get_setting_int("exp_per_dice_win")
            btc_reward = await get_setting_int("bitcoin_per_dice_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(DICE_WIN_PHRASES, dice1=dice1, dice2=dice2, total=total, profit=profit)
        else:
            exp = await get_setting_int("exp_per_dice_lose")
            phrase = get_random_phrase(DICE_LOSE_PHRASES, dice1=dice1, dice2=dice2, total=total, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'dice', amount)
    await message.answer(phrase, reply_markup=repeat_bet_keyboard('dice'))

async def process_guess_repeat(user_id: int, amount: float, number: int, message: types.Message):
    if number is None:
        await message.answer("❌ Нет сохранённого числа для повтора.")
        return
    secret = random.randint(1, 5)
    win = (number == secret)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'guess', win, conn=conn)
        if win:
            multiplier = await get_setting_float("guess_multiplier")
            rep_reward = await get_setting_int("guess_reputation")
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            await update_user_reputation(user_id, rep_reward)
            exp = await get_setting_int("exp_per_guess_win")
            btc_reward = await get_setting_int("bitcoin_per_guess_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(GUESS_WIN_PHRASES, secret=secret, profit=profit, rep=rep_reward)
            bet_data = {'number': number}
        else:
            exp = await get_setting_int("exp_per_guess_lose")
            phrase = get_random_phrase(GUESS_LOSE_PHRASES, secret=secret, loss=amount)
            bet_data = {'number': number}
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'guess', amount, bet_data)
    await message.answer(phrase, reply_markup=repeat_bet_keyboard('guess'))

async def process_slots_repeat(user_id: int, amount: float, message: types.Message):
    symbols, multiplier, win = await slots_spin()
    result_str = format_slots_result(symbols)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'slots', win, conn=conn)
        if win:
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = await get_setting_int("exp_per_slots_win")
            btc_reward = await get_setting_int("bitcoin_per_slots_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(SLOTS_WIN_PHRASES, combo=result_str, multiplier=multiplier, profit=profit)
        else:
            exp = await get_setting_int("exp_per_slots_lose")
            phrase = get_random_phrase(SLOTS_LOSE_PHRASES, combo=result_str, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    await save_last_bet(user_id, 'slots', amount)
    await message.answer(phrase, reply_markup=repeat_bet_keyboard('slots'))

async def process_roulette_repeat(user_id: int, amount: float, bet_type: str, number: int, message: types.Message):
    if bet_type is None:
        await message.answer("❌ Нет сохранённых параметров для повтора.")
        return
    num, color, win = await roulette_spin(bet_type, number)

    async with db_pool.acquire() as conn:
        await update_user_balance(user_id, -amount, conn=conn)
        await update_user_game_stats(user_id, 'roulette', win, conn=conn)
        if win:
            if bet_type == 'number':
                multiplier = await get_setting_float("roulette_number_multiplier")
            elif bet_type == 'green':
                multiplier = await get_setting_float("roulette_green_multiplier")
            else:
                multiplier = await get_setting_float("roulette_color_multiplier")
            profit = amount * multiplier
            await update_user_balance(user_id, profit, conn=conn)
            exp = await get_setting_int("exp_per_roulette_win")
            btc_reward = await get_setting_int("bitcoin_per_roulette_win")
            if btc_reward > 0:
                await update_user_bitcoin(user_id, float(btc_reward), conn=conn)
            phrase = get_random_phrase(ROULETTE_WIN_PHRASES, number=num, color=color, profit=profit)
        else:
            exp = await get_setting_int("exp_per_roulette_lose")
            phrase = get_random_phrase(ROULETTE_LOSE_PHRASES, number=num, color=color, loss=amount)
        await add_exp(user_id, exp, conn=conn)

    bet_data = {'bet_type': bet_type, 'number': number}
    await save_last_bet(user_id, 'roulette', amount, bet_data)
    await message.answer(phrase, reply_markup=repeat_bet_keyboard('roulette'))

# ==================== КОНЕЦ ЧАСТИ 3 ====================
# ==================== ЧАСТЬ 4: МАГАЗИН, ПРОМОКОДЫ, ОГРАБЛЕНИЕ, РЕФЕРАЛЫ, ЗАДАНИЯ, АУКЦИОН ====================

# ==================== МАГАЗИН ПОДАРКОВ ====================
@dp.message_handler(lambda message: message.text == "🛒 Магазин подарков")
async def shop_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
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
            price = float(row['price'])
            stock = row['stock']
            stock_info = f" (в наличии: {stock})" if stock != -1 else ""
            text += f"🔹 {name}\n{desc}\n💰 {price:.2f} баксов{stock_info}\n\n"
            button_text = f"Купить {name}"
            kb.append([InlineKeyboardButton(text=button_text, callback_data=f"buy_{item_id}")])
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop_page_{page-1}"))
        if offset + ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"shop_page_{page+1}"))
        if nav_buttons:
            kb.append(nav_buttons)
        # Отправляем с картинкой магазина, если есть
        await send_with_media(message.chat.id, text, media_key='shop', reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
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
    await ensure_user_exists(user_id, callback.from_user.username, callback.from_user.first_name)
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
            name, price, stock = row['name'], float(row['price']), row['stock']
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
        # Отправляем картинку покупки, если есть
        await send_with_media(user_id, f"✅ Покупка совершена! {phrase}", media_key='purchase')
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Purchase error: {e}")
        await callback.answer("❌ Ошибка при покупке. Попробуй позже.", show_alert=True)

async def notify_admins_about_purchase(user: types.User, item_name: str, price: float):
    admins = SUPER_ADMINS.copy()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM admins")
        for row in rows:
            admins.append(row['user_id'])
    for admin_id in admins:
        await safe_send_message(admin_id,
            f"🛒 Покупка: пользователь {user.full_name} (@{user.username})\n"
            f"<a href=\"tg://user?id={user.id}\">Ссылка</a> купил {item_name} за {price:.2f} баксов."
        )

# ==================== МОИ ПОКУПКИ ====================
@dp.message_handler(lambda message: message.text == "💰 Мои покупки")
async def my_purchases(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    # Можно отправить картинку промокода, если есть
    await send_with_media(user_id, "Введи промокод:", media_key='promo', reply_markup=back_keyboard())
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
            reward = float(row['reward'])
            max_uses = row['max_uses']
            used = row['used_count']
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
            f"✅ Промокод активирован! Ты получил {reward:.2f} баксов.",
            reply_markup=main_menu_keyboard(await is_admin(user_id))
        )
    except Exception as e:
        logging.error(f"Promo error: {e}")
        await message.answer("❌ Ошибка активации промокода.")
    await state.finish()

# ==================== ОГРАБЛЕНИЕ ====================
async def get_theft_success_chance(attacker_id: int) -> float:
    base = await get_setting_float("theft_success_chance")
    rep = await get_user_reputation(attacker_id)
    bonus = float(await get_setting_float("reputation_theft_bonus")) * rep
    max_bonus = await get_setting_float("reputation_max_bonus_percent")
    bonus = min(bonus, max_bonus)
    return base + bonus

async def get_defense_chance(victim_id: int) -> float:
    base = await get_setting_float("theft_defense_chance")
    rep = await get_user_reputation(victim_id)
    bonus = float(await get_setting_float("reputation_defense_bonus")) * rep
    max_bonus = await get_setting_float("reputation_max_bonus_percent")
    bonus = min(bonus, max_bonus)
    return base + bonus

async def perform_theft(message: types.Message, robber_id: int, victim_id: int, cost: float = 0):
    success_chance = await get_theft_success_chance(robber_id)
    defense_chance = await get_defense_chance(victim_id)
    defense_penalty = await get_setting_int("theft_defense_penalty")
    min_amount = await get_setting_float("min_theft_amount")
    max_amount = await get_setting_float("max_theft_amount")
    bitcoin_reward = await get_setting_int("bitcoin_per_theft")

    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                robber_balance = await get_user_balance(robber_id)
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
                victim_balance = float(victim_row['balance'])
                victim_username = victim_row['username']
                victim_first = victim_row['first_name']
                victim_name = victim_first if victim_first else str(victim_id)

                if cost > 0:
                    await update_user_balance(robber_id, -cost, conn=conn)
                    robber_balance -= cost

                defense_triggered = random.random() * 100 <= defense_chance
                if defense_triggered:
                    penalty = min(defense_penalty, robber_balance)
                    if penalty > 0:
                        await update_user_balance(robber_id, -penalty, conn=conn)
                        await update_user_balance(victim_id, penalty, conn=conn)
                    await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_failed = theft_failed + 1 WHERE user_id=$1", robber_id)
                    await conn.execute("UPDATE users SET theft_protected = theft_protected + 1 WHERE user_id=$1", victim_id)
                    await conn.execute("UPDATE users SET last_theft_time = $1 WHERE user_id=$2", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), robber_id)

                    exp_defense = await get_setting_int("exp_per_theft_defense")
                    await add_exp(victim_id, exp_defense, conn=conn)
                    exp_fail = await get_setting_int("exp_per_theft_fail")
                    await add_exp(robber_id, exp_fail, conn=conn)

                    robber_phrase = get_random_phrase(THEFT_DEFENSE_PHRASES, target=victim_name, penalty=penalty)
                    victim_phrase = get_random_phrase(THEFT_VICTIM_DEFENSE_PHRASES, attacker=message.from_user.first_name, penalty=penalty)
                    await message.answer(robber_phrase, reply_markup=main_menu_keyboard(await is_admin(robber_id)))
                    await safe_send_message(victim_id, victim_phrase)
                    return

                success = random.random() * 100 <= success_chance
                if success and victim_balance > 0:
                    if victim_balance < min_amount:
                        steal_amount = 0
                    else:
                        max_possible = min(max_amount, victim_balance)
                        steal_amount = round(random.uniform(min_amount, max_possible), 2)

                    if steal_amount > 0:
                        await update_user_balance(victim_id, -steal_amount, conn=conn)
                        await update_user_balance(robber_id, steal_amount, conn=conn)
                        if bitcoin_reward > 0:
                            await update_user_bitcoin(robber_id, float(bitcoin_reward), conn=conn)
                        await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_success = theft_success + 1 WHERE user_id=$1", robber_id)

                        exp_success = await get_setting_int("exp_per_theft_success")
                        await add_exp(robber_id, exp_success, conn=conn)

                        required_thefts = await get_setting_int("referral_required_thefts")
                        new_success = await conn.fetchval("SELECT theft_success FROM users WHERE user_id=$1", robber_id)
                        if new_success == required_thefts:
                            ref = await conn.fetchrow("SELECT referrer_id FROM referrals WHERE referred_id=$1 AND reward_given=FALSE", robber_id)
                            if ref:
                                referrer_id = ref['referrer_id']
                                bonus_coins = await get_setting_float("referral_bonus")
                                bonus_rep = await get_setting_int("referral_reputation")
                                await update_user_balance(referrer_id, bonus_coins, conn=conn)
                                await update_user_reputation(referrer_id, bonus_rep)
                                await conn.execute("UPDATE referrals SET reward_given=TRUE WHERE referred_id=$1", robber_id)
                                await conn.execute("UPDATE referrals SET active=TRUE WHERE referred_id=$1", robber_id)
                                await safe_send_message(referrer_id, f"🎉 Ваш реферал совершил {required_thefts} успешных ограблений! Вы получили {bonus_coins:.2f} баксов и {bonus_rep} репутации.")

                        btc_text = f" и {bitcoin_reward} BTC" if bitcoin_reward > 0 else ""
                        phrase = get_random_phrase(THEFT_SUCCESS_PHRASES, amount=steal_amount, target=victim_name)
                        await message.answer(f"{phrase}{btc_text}", reply_markup=main_menu_keyboard(await is_admin(robber_id)))
                        await safe_send_message(victim_id, f"🔫 Вас ограбили! {message.from_user.first_name} украл {steal_amount:.2f} баксов.")
                    else:
                        await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_failed = theft_failed + 1 WHERE user_id=$1", robber_id)
                        exp_fail = await get_setting_int("exp_per_theft_fail")
                        await add_exp(robber_id, exp_fail, conn=conn)
                        phrase = get_random_phrase(THEFT_FAIL_PHRASES, target=victim_name)
                        await message.answer(phrase, reply_markup=main_menu_keyboard(await is_admin(robber_id)))
                else:
                    await conn.execute("UPDATE users SET theft_attempts = theft_attempts + 1, theft_failed = theft_failed + 1 WHERE user_id=$1", robber_id)
                    exp_fail = await get_setting_int("exp_per_theft_fail")
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
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    phrase = get_random_phrase(THEFT_CHOICE_PHRASES)
    await send_with_media(user_id, phrase, media_key='theft', reply_markup=theft_choice_keyboard())

@dp.message_handler(lambda message: message.text == "🎲 Случайная цель")
async def theft_random(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    cooldown_minutes = await get_setting_int("theft_cooldown_minutes")
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
    cost = await get_setting_float("random_attack_cost")
    await perform_theft(message, user_id, target_id, cost)

@dp.message_handler(lambda message: message.text == "👤 Выбрать пользователя")
async def theft_choose_user(message: types.Message, state: FSMContext):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    cooldown_minutes = await get_setting_int("theft_cooldown_minutes")
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

    cost = await get_setting_float("targeted_attack_cost")
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
    bonus_coins = await get_setting_float("referral_bonus")
    bonus_rep = await get_setting_int("referral_reputation")
    required_thefts = await get_setting_int("referral_required_thefts")

    async with db_pool.acquire() as conn:
        clicks = await conn.fetchval("SELECT SUM(clicks) FROM referrals WHERE referrer_id=$1", user_id) or 0
        active = await conn.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id=$1 AND active=TRUE", user_id) or 0
        earned = active * bonus_coins

    text = (
        f"🔗 Твоя реферальная ссылка:\n{link}\n\n"
        f"📊 Статистика:\n"
        f"• Переходов: {clicks}\n"
        f"• Активных рефералов: {active}\n"
        f"• Заработано баксов: {earned:.2f}\n\n"
        f"Бонус: {bonus_coins:.2f} баксов и {bonus_rep} репутации за каждого активного реферала ({required_thefts} успешных краж)."
    )
    await send_with_media(user_id, text, media_key='referral', reply_markup=main_menu_keyboard(await is_admin(user_id)))

# ==================== ЗАДАНИЯ (ОБЪЕДИНЕННЫЙ ХЕНДЛЕР С ПРОВЕРКОЙ ПРАВ) ====================
@dp.message_handler(lambda message: message.text == "📋 Задания")
async def tasks_unified_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return

    if await has_permission(user_id, "manage_tasks"):
        await admin_tasks_menu(message)
    else:
        await user_tasks_menu(message)

async def user_tasks_menu(message: types.Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, description, reward_coins, reward_reputation, max_completions, completed_count FROM tasks WHERE active=TRUE")
    if not rows:
        await message.answer("📋 Пока нет доступных заданий.", reply_markup=main_menu_keyboard(await is_admin(message.from_user.id)))
        return

    text = "📋 Доступные задания:\n\n"
    kb = []
    for row in rows:
        progress = f" (выполнено {row['completed_count']}/{row['max_completions']})" if row['max_completions'] > 1 else ""
        text += f"🔹 {row['name']}{progress}\n{row['description']}\nНаграда: {float(row['reward_coins']):.2f} баксов, {row['reward_reputation']} репутации\n\n"
        kb.append([InlineKeyboardButton(text=f"Выполнить {row['name']}", callback_data=f"task_{row['id']}")])
    await send_with_media(message.chat.id, text, media_key='tasks', reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

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
                await update_user_balance(user_id, float(task['reward_coins']), conn=conn)
                await update_user_reputation(user_id, task['reward_reputation'])
                expires_at = (datetime.now() + timedelta(days=task['required_days'])).strftime("%Y-%m-%d %H:%M:%S") if task['required_days'] > 0 else None
                await conn.execute(
                    "INSERT INTO user_tasks (user_id, task_id, completed_at, expires_at, status) VALUES ($1, $2, $3, $4, $5)",
                    user_id, task_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), expires_at, 'completed'
                )
                await conn.execute("UPDATE tasks SET completed_count = completed_count + 1 WHERE id=$1", task_id)

            await callback.answer(f"✅ Задание выполнено! +{float(task['reward_coins']):.2f} баксов, +{task['reward_reputation']} репутации", show_alert=True)
            await callback.message.delete()
        else:
            await callback.answer("Этот тип заданий пока не поддерживается.", show_alert=True)

# ==================== АУКЦИОН (ОБЪЕДИНЕННЫЙ ХЕНДЛЕР С ПРОВЕРКОЙ ПРАВ) ====================
@dp.message_handler(lambda message: message.text == "🏷 Аукцион")
async def auction_unified_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return

    if await has_permission(user_id, "manage_auctions"):
        await admin_auction_menu(message)
    else:
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
        text += f"🆔 {row['id']} | {row['item_name']} | Текущая ставка: {float(row['current_price']):.2f}\n"
        if row['end_time']:
            remaining = row['end_time'] - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                text += f"⏳ Осталось: {hours}ч {minutes}м\n"
        if row['target_price']:
            text += f"🎯 Целевая цена: {float(row['target_price']):.2f}\n"
        text += "\n"
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    kb = auction_list_keyboard(rows, page, total_pages)
    # Отправляем с картинкой аукциона, если есть
    await send_with_media(message.chat.id, text, media_key='auction', reply_markup=kb)

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
        f"💰 Стартовая цена: {float(auction['start_price']):.2f}\n"
        f"💵 Текущая ставка: {float(auction['current_price']):.2f}\n"
    )
    if auction['end_time']:
        remaining = auction['end_time'] - datetime.now()
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            text += f"⏳ Окончание через: {hours}ч {minutes}м\n"
    if auction['target_price']:
        text += f"🎯 Целевая цена: {float(auction['target_price']):.2f}\n"
    text += "\n📊 Последние ставки:\n"
    if bids:
        for bid in bids:
            user = await conn.fetchval("SELECT first_name FROM users WHERE user_id=$1", bid['user_id'])
            text += f"• {user or 'Неизвестно'}: {float(bid['bid_amount']):.2f} баксов ({bid['bid_time'].strftime('%Y-%m-%d %H:%M')})\n"
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
    await callback.message.answer("Введи сумму ставки (можно дробную):", reply_markup=back_keyboard())
    await AuctionBid.amount.set()
    await callback.answer()

@dp.message_handler(state=AuctionBid.amount)
async def auction_bid_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await auction_unified_handler(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
    except ValueError:
        await message.answer("❌ Введи положительное число с точностью до сотых.")
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

        current_leader = await conn.fetchval(
            "SELECT user_id FROM auction_bids WHERE auction_id=$1 ORDER BY bid_amount DESC, bid_time ASC LIMIT 1",
            auction_id
        )
        if current_leader == user_id:
            await message.answer("❌ Ты уже являешься лидером этого аукциона. Нельзя повышать свою ставку.")
            await state.finish()
            return

        min_step = await get_setting_int("auction_min_bid_step")
        min_bid = float(auction['current_price']) + min_step
        if amount < min_bid:
            await message.answer(f"❌ Ставка должна быть не меньше {min_bid:.2f} (текущая цена + минимальный шаг).")
            return
        max_input = await get_setting_float("max_input_number")
        if amount > max_input:
            await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
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
            auction_id, user_id, amount, datetime.now()
        )
        if auction['target_price'] and amount >= float(auction['target_price']):
            await conn.execute("UPDATE auctions SET status='ended', winner_id=$1 WHERE id=$2", user_id, auction_id)
            await safe_send_message(user_id, f"🎉 Поздравляем! Ты выиграл аукцион «{auction['item_name']}» с ценой {amount:.2f} баксов. Админ скоро свяжется для передачи товара.")
            await safe_send_message(auction['created_by'], f"🏁 Аукцион «{auction['item_name']}» завершён по достижению целевой цены. Победитель: {message.from_user.first_name} (ID: {user_id}) с суммой {amount:.2f} баксов.")
            await message.answer("✅ Аукцион завершён! Ты победитель.")
        else:
            await message.answer(f"✅ Ставка принята! Ты теперь лидер с ценой {amount:.2f} баксов.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "auction_list")
async def auction_list_back(callback: types.CallbackQuery):
    await list_auctions(callback.message)
    await callback.answer()

# ==================== КОНЕЦ ЧАСТИ 4 ====================
# ==================== ЧАСТЬ 5: БИЗНЕСЫ, РОЗЫГРЫШИ, БИТКОИН-БИРЖА (ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ) ====================

# ==================== БИЗНЕСЫ ====================

@dp.message_handler(lambda message: message.text == "🏪 Мои бизнесы")
async def my_businesses(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return

    # Обновляем доход (на всякий случай)
    async with db_pool.acquire() as conn:
        await update_business_income(user_id, conn)
        businesses = await get_user_businesses(user_id)

    if not businesses:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏪 Купить бизнес", callback_data="buy_business_menu")]
        ])
        await send_with_media(user_id, "📭 У тебя пока нет бизнеса. Хочешь купить за биткоины?", media_key='business', reply_markup=kb)
        return

    kb = business_main_keyboard(businesses)
    await send_with_media(user_id, "🏪 Твои бизнесы:", media_key='business', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "buy_business_menu")
async def buy_business_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    all_types = await get_business_type_list(only_available=True)
    async with db_pool.acquire() as conn:
        owned = await conn.fetch("SELECT business_type_id FROM user_businesses WHERE user_id=$1", user_id)
        owned_ids = [r['business_type_id'] for r in owned]
    available = [bt for bt in all_types if bt['id'] not in owned_ids]
    if not available:
        await callback.answer("Ты уже купил все доступные бизнесы!", show_alert=True)
        return
    kb = business_buy_keyboard(available)
    await callback.message.edit_text("Выбери бизнес для покупки:", reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("buy_biz_"))
async def buy_business_choose(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "buy_biz_cancel":
        await callback.message.delete()
        await callback.answer()
        return
    biz_type_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    biz_type = await get_business_type(biz_type_id)
    if not biz_type:
        await callback.answer("Бизнес не найден.", show_alert=True)
        return
    if not biz_type.get('available', True):
        await callback.answer("Этот бизнес временно недоступен для покупки.", show_alert=True)
        return
    existing = await get_user_business(user_id, biz_type_id)
    if existing:
        await callback.answer("У тебя уже есть такой бизнес!", show_alert=True)
        return
    # base_price_btc может быть Decimal, преобразуем в float
    price = float(biz_type['base_price_btc'])
    btc_balance = await get_user_bitcoin(user_id)
    if btc_balance < price - 0.0001:
        await callback.answer(f"Недостаточно биткоинов. Нужно {price:.2f} BTC, у тебя {btc_balance:.4f}.", show_alert=True)
        return
    await state.update_data(biz_type_id=biz_type_id, price=price, biz_name=biz_type['name'], biz_emoji=biz_type['emoji'])
    await callback.message.answer(f"Ты уверен, что хочешь купить бизнес «{biz_type['emoji']} {biz_type['name']}» за {price:.2f} BTC? (да/нет)", reply_markup=back_keyboard())
    await BuyBusiness.confirming.set()
    await callback.answer()

@dp.message_handler(state=BuyBusiness.confirming)
async def buy_business_confirm(message: types.Message, state: FSMContext):
    if message.text.lower() == 'нет' or message.text == "◀️ Назад":
        await state.finish()
        await my_businesses(message)
        return
    if message.text.lower() == 'да':
        data = await state.get_data()
        biz_type_id = data['biz_type_id']
        price = data['price']
        biz_name = data['biz_name']
        user_id = message.from_user.id
        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    btc = await get_user_bitcoin(user_id)
                    if btc < price - 0.0001:
                        await message.answer("❌ Недостаточно биткоинов.")
                        await state.finish()
                        return
                    await update_user_bitcoin(user_id, -price, conn=conn)
                    await create_user_business(user_id, biz_type_id)
            phrase = get_random_phrase(BUSINESS_BUY_PHRASES, name=biz_name)
            await message.answer(f"✅ {phrase}", reply_markup=main_menu_keyboard(await is_admin(user_id)))
        except Exception as e:
            logging.error(f"Buy business error: {e}")
            await message.answer("❌ Ошибка при покупке бизнеса.")
        await state.finish()
    else:
        await message.answer("Введи 'да' или 'нет'.")

@dp.callback_query_handler(lambda c: c.data.startswith("biz_view_"))
async def business_view(callback: types.CallbackQuery):
    biz_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        await update_business_income(user_id, conn)
        biz = await conn.fetchrow("""
            SELECT ub.*, bt.name, bt.emoji, bt.base_price_btc, bt.base_income_cents, bt.max_level
            FROM user_businesses ub
            JOIN business_types bt ON ub.business_type_id = bt.id
            WHERE ub.id = $1 AND ub.user_id = $2
        """, biz_id, user_id)
        if not biz:
            await callback.answer("Бизнес не найден", show_alert=True)
            return
    accum_bucks = biz['accumulated'] // 100
    accum_cents = biz['accumulated'] % 100
    income_per_hour = biz['base_income_cents'] * biz['level']
    income_bucks = income_per_hour // 100
    income_cents = income_per_hour % 100
    # base_price_btc преобразуем в float для вычислений
    base_price = float(biz['base_price_btc'])
    upgrade_cost = await get_business_price({'base_price_btc': base_price}, biz['level'] + 1) if biz['level'] < biz['max_level'] else 0
    text = (
        f"{biz['emoji']} <b>{biz['name']}</b> (ур. {biz['level']}/{biz['max_level']})\n\n"
        f"📈 Доход в час: {income_bucks} баксов {income_cents} центов\n"
        f"💰 Накоплено: {accum_bucks} баксов {accum_cents} центов\n"
    )
    if biz['level'] < biz['max_level']:
        text += f"⬆️ Стоимость улучшения до ур.{biz['level']+1}: {upgrade_cost:.2f} BTC"
    else:
        text += "✅ Бизнес максимального уровня."
    await callback.message.edit_text(text, reply_markup=business_actions_keyboard(biz_id))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("biz_collect_"))
async def business_collect(callback: types.CallbackQuery):
    biz_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    success, result = await collect_business_income(user_id, biz_id)
    if success:
        await callback.answer(f"✅ {result}", show_alert=True)
    else:
        await callback.answer(f"❌ {result}", show_alert=True)
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

@dp.callback_query_handler(lambda c: c.data == "biz_back_to_main")
async def business_back_to_main(callback: types.CallbackQuery):
    await my_businesses(callback.message)
    await callback.answer()

# ==================== РОЗЫГРЫШИ (ОБЪЕДИНЕННЫЙ ХЕНДЛЕР С ПРОВЕРКОЙ ПРАВ) ====================

@dp.message_handler(lambda message: message.text == "🎁 Розыгрыши")
async def giveaways_unified_handler(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return

    if await has_permission(user_id, "manage_giveaways"):
        await admin_giveaway_menu(message)
    else:
        await user_giveaways_menu(message)

async def user_giveaways_menu(message: types.Message):
    await send_with_media(message.chat.id, "🎁 Розыгрыши:", media_key='giveaway', reply_markup=giveaways_user_keyboard())

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

@dp.callback_query_handler(lambda c: c.data.startswith("active_gw_") and not c.data.startswith("active_gw_page_"))
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

# ==================== БИТКОИН-БИРЖА (ПОЛНОЦЕННЫЙ СТАКАН) ====================

@dp.message_handler(lambda message: message.text == "💼 Биткоин-биржа")
async def bitcoin_exchange_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    await send_with_media(user_id, "💼 Биткоин-биржа: продавай и покупай BTC за баксы.", media_key='exchange', reply_markup=bitcoin_exchange_keyboard())

# ----- Просмотр стакана заявок -----
@dp.message_handler(lambda message: message.text == "📊 Стакан заявок")
async def exchange_order_book(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    book = await get_order_book()
    text = "📊 <b>Биржевой стакан</b>\n\n"
    text += "📉 <b>Продажа (ASK)</b>:\n"
    if book['asks']:
        for ask in book['asks'][:10]:
            text += f"• {ask['price']} $ | {ask['total_amount']:.4f} BTC ({ask['count']} заявок)\n"
    else:
        text += "Нет активных заявок на продажу.\n"
    text += "\n📈 <b>Покупка (BID)</b>:\n"
    if book['bids']:
        for bid in book['bids'][:10]:
            text += f"• {bid['price']} $ | {bid['total_amount']:.4f} BTC ({bid['count']} заявок)\n"
    else:
        text += "Нет активных заявок на покупку.\n"
    text += "\nВыбери действие ниже:"
    await message.answer(text, reply_markup=order_book_keyboard(book))

@dp.callback_query_handler(lambda c: c.data.startswith("buy_from_"))
async def buy_from_price(callback: types.CallbackQuery, state: FSMContext):
    price = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        orders = await conn.fetch(
            "SELECT * FROM bitcoin_orders WHERE type='sell' AND status='active' AND price=$1 ORDER BY created_at ASC",
            price
        )
    if not orders:
        await callback.answer("Заявок по этой цене больше нет.", show_alert=True)
        return
    # Преобразуем Decimal в float для последующих расчётов
    orders_list = []
    total_available = 0.0
    for o in orders:
        d = dict(o)
        d['amount'] = float(d['amount'])
        d['total_locked'] = float(d['total_locked'])
        orders_list.append(d)
        total_available += d['amount']
    await state.update_data(price=price, orders=orders_list, total_available=total_available)
    await callback.message.answer(
        f"📉 Продажа по цене {price} $/BTC. Доступно всего: {total_available:.4f} BTC.\n"
        f"Введи количество BTC, которое хочешь купить (можно дробное):",
        reply_markup=back_keyboard()
    )
    await BuyFromPrice.amount.set()
    await callback.answer()

@dp.message_handler(state=BuyFromPrice.amount)
async def buy_from_price_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await bitcoin_exchange_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 4)
    except:
        await message.answer("❌ Введи положительное число.")
        return
    data = await state.get_data()
    price = data['price']
    orders = data['orders']
    total_available = data['total_available']
    if amount > total_available + 0.0001:
        await message.answer(f"❌ Недостаточно BTC для покупки. Доступно {total_available:.4f} BTC.")
        return
    user_id = message.from_user.id
    total_cost = amount * price
    balance = await get_user_balance(user_id)
    if balance < total_cost:
        await message.answer(f"❌ Недостаточно баксов. Нужно {total_cost:.2f}.")
        return
    max_input = await get_setting_float("max_input_number")
    if total_cost > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
        return
    # Исполняем покупку, снимая с ордеров по очереди
    remaining = amount
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            for order in orders:
                if remaining <= 0.0001:
                    break
                order_id = order['id']
                seller_id = order['user_id']
                order_amount = order['amount']
                take = min(remaining, order_amount)
                # Проверяем, что ордер ещё активен
                current = await conn.fetchrow("SELECT * FROM bitcoin_orders WHERE id=$1 AND status='active'", order_id)
                if not current or float(current['amount']) < take - 0.0001:
                    continue
                # Обновляем балансы
                await update_user_balance(user_id, -take * price, conn=conn)
                await update_user_bitcoin(user_id, take, conn=conn)
                await update_user_balance(seller_id, take * price, conn=conn)
                # Обновляем ордер
                new_amount = float(current['amount']) - take
                new_locked = float(current['total_locked']) - take
                if new_amount <= 0.0001:
                    await conn.execute("UPDATE bitcoin_orders SET status='completed', amount=0, total_locked=0 WHERE id=$1", order_id)
                else:
                    await conn.execute("UPDATE bitcoin_orders SET amount=$1, total_locked=$2 WHERE id=$3", new_amount, new_locked, order_id)
                # Записываем сделку
                await conn.execute(
                    "INSERT INTO bitcoin_trades (sell_order_id, amount, price, buyer_id, seller_id) VALUES ($1, $2, $3, $4, $5)",
                    order_id, take, price, user_id, seller_id
                )
                remaining -= take
    await message.answer(f"✅ Ты купил {amount:.4f} BTC за {total_cost:.2f} баксов.", reply_markup=bitcoin_exchange_keyboard())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("sell_to_"))
async def sell_to_price(callback: types.CallbackQuery, state: FSMContext):
    price = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        orders = await conn.fetch(
            "SELECT * FROM bitcoin_orders WHERE type='buy' AND status='active' AND price=$1 ORDER BY created_at ASC",
            price
        )
    if not orders:
        await callback.answer("Заявок по этой цене больше нет.", show_alert=True)
        return
    orders_list = []
    total_available = 0.0
    for o in orders:
        d = dict(o)
        d['amount'] = float(d['amount'])
        d['total_locked'] = float(d['total_locked'])
        orders_list.append(d)
        total_available += d['amount']
    await state.update_data(price=price, orders=orders_list, total_available=total_available)
    await callback.message.answer(
        f"📈 Покупка по цене {price} $/BTC. Требуется всего: {total_available:.4f} BTC.\n"
        f"Введи количество BTC, которое хочешь продать (можно дробное):",
        reply_markup=back_keyboard()
    )
    await SellToPrice.amount.set()
    await callback.answer()

@dp.message_handler(state=SellToPrice.amount)
async def sell_to_price_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await bitcoin_exchange_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 4)
    except:
        await message.answer("❌ Введи положительное число.")
        return
    data = await state.get_data()
    price = data['price']
    orders = data['orders']
    total_available = data['total_available']
    if amount > total_available + 0.0001:
        await message.answer(f"❌ Спрос меньше. Максимум можно продать {total_available:.4f} BTC.")
        return
    user_id = message.from_user.id
    btc_balance = await get_user_bitcoin(user_id)
    if btc_balance < amount:
        await message.answer(f"❌ Недостаточно BTC. У тебя {btc_balance:.4f} BTC.")
        return
    total_profit = amount * price
    max_input = await get_setting_float("max_input_number")
    if total_profit > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
        return
    # Исполняем продажу
    remaining = amount
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            for order in orders:
                if remaining <= 0.0001:
                    break
                order_id = order['id']
                buyer_id = order['user_id']
                order_amount = order['amount']
                take = min(remaining, order_amount)
                current = await conn.fetchrow("SELECT * FROM bitcoin_orders WHERE id=$1 AND status='active'", order_id)
                if not current or float(current['amount']) < take - 0.0001:
                    continue
                await update_user_balance(user_id, take * price, conn=conn)
                await update_user_bitcoin(user_id, -take, conn=conn)
                await update_user_bitcoin(buyer_id, take, conn=conn)
                new_amount = float(current['amount']) - take
                new_locked = float(current['total_locked']) - take * price
                if new_amount <= 0.0001:
                    await conn.execute("UPDATE bitcoin_orders SET status='completed', amount=0, total_locked=0 WHERE id=$1", order_id)
                else:
                    await conn.execute("UPDATE bitcoin_orders SET amount=$1, total_locked=$2 WHERE id=$3", new_amount, new_locked, order_id)
                await conn.execute(
                    "INSERT INTO bitcoin_trades (buy_order_id, amount, price, buyer_id, seller_id) VALUES ($1, $2, $3, $4, $5)",
                    order_id, take, price, buyer_id, user_id
                )
                remaining -= take
    await message.answer(f"✅ Ты продал {amount:.4f} BTC за {total_profit:.2f} баксов.", reply_markup=bitcoin_exchange_keyboard())
    await state.finish()

# ----- Создание заявки на продажу -----
@dp.message_handler(lambda message: message.text == "📉 Продать BTC")
async def sell_bitcoin_start(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    btc_balance = await get_user_bitcoin(user_id)
    min_amount = await get_setting_float("exchange_min_amount_btc")
    await message.answer(
        f"У тебя {btc_balance:.4f} BTC.\n"
        f"Минимальная сумма заявки: {min_amount} BTC.\n"
        f"Введи количество BTC, которое хочешь продать (можно дробное, например 0.5):",
        reply_markup=back_keyboard()
    )
    await SellBitcoin.amount.set()

@dp.message_handler(state=SellBitcoin.amount)
async def sell_bitcoin_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await bitcoin_exchange_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 4)
    except ValueError:
        await message.answer("❌ Введи положительное число (можно дробное).")
        return
    user_id = message.from_user.id
    btc_balance = await get_user_bitcoin(user_id)
    if btc_balance < amount - 0.0001:
        await message.answer(f"❌ Недостаточно BTC. У тебя {btc_balance:.4f} BTC.")
        return
    min_amount = await get_setting_float("exchange_min_amount_btc")
    if amount < min_amount:
        await message.answer(f"❌ Минимальное количество для продажи: {min_amount} BTC.")
        return
    await state.update_data(amount=amount)
    await message.answer("Введи цену в баксах за 1 BTC (целое число):")
    await SellBitcoin.price.set()

@dp.message_handler(state=SellBitcoin.price)
async def sell_bitcoin_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await bitcoin_exchange_menu(message)
        return
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи целое положительное число.")
        return
    min_price = await get_setting_int("exchange_min_price")
    max_price = await get_setting_int("exchange_max_price")
    if price < min_price:
        await message.answer(f"❌ Цена не может быть меньше {min_price}.")
        return
    if max_price > 0 and price > max_price:
        await message.answer(f"❌ Цена не может быть больше {max_price}.")
        return
    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id
    try:
        order_id = await create_bitcoin_order(user_id, 'sell', amount, price)
        await message.answer(
            f"✅ Заявка на продажу {amount:.4f} BTC по цене {price} $/BTC создана!\n"
            f"ID заявки: {order_id}",
            reply_markup=bitcoin_exchange_keyboard()
        )
    except ValueError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        logging.error(f"Sell bitcoin error: {e}")
        await message.answer("❌ Ошибка при создании заявки.")
    await state.finish()

# ----- Создание заявки на покупку -----
@dp.message_handler(lambda message: message.text == "📈 Купить BTC")
async def buy_bitcoin_start(message: types.Message):
    if message.chat.type != 'private':
        return
    min_amount = await get_setting_float("exchange_min_amount_btc")
    await message.answer(
        f"Минимальная сумма заявки: {min_amount} BTC.\n"
        f"Введи количество BTC, которое хочешь купить (можно дробное, например 0.5):",
        reply_markup=back_keyboard()
    )
    await BuyBitcoin.amount.set()

@dp.message_handler(state=BuyBitcoin.amount)
async def buy_bitcoin_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await bitcoin_exchange_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 4)
    except ValueError:
        await message.answer("❌ Введи положительное число (можно дробное).")
        return
    min_amount = await get_setting_float("exchange_min_amount_btc")
    if amount < min_amount:
        await message.answer(f"❌ Минимальное количество для покупки: {min_amount} BTC.")
        return
    await state.update_data(amount=amount)
    await message.answer("Введи цену в баксах за 1 BTC (целое число):")
    await BuyBitcoin.price.set()

@dp.message_handler(state=BuyBitcoin.price)
async def buy_bitcoin_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await bitcoin_exchange_menu(message)
        return
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи целое положительное число.")
        return
    min_price = await get_setting_int("exchange_min_price")
    max_price = await get_setting_int("exchange_max_price")
    if price < min_price:
        await message.answer(f"❌ Цена не может быть меньше {min_price}.")
        return
    if max_price > 0 and price > max_price:
        await message.answer(f"❌ Цена не может быть больше {max_price}.")
        return
    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id
    try:
        order_id = await create_bitcoin_order(user_id, 'buy', amount, price)
        await message.answer(
            f"✅ Заявка на покупку {amount:.4f} BTC по цене {price} $/BTC создана!\n"
            f"ID заявки: {order_id}",
            reply_markup=bitcoin_exchange_keyboard()
        )
    except ValueError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        logging.error(f"Buy bitcoin error: {e}")
        await message.answer("❌ Ошибка при создании заявки.")
    await state.finish()

# ----- Просмотр моих заявок -----
@dp.message_handler(lambda message: message.text == "📋 Мои заявки")
async def my_orders(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM bitcoin_orders WHERE user_id=$1 AND status='active' ORDER BY created_at DESC",
            user_id
        )
    if not rows:
        await message.answer("У тебя нет активных заявок.", reply_markup=bitcoin_exchange_keyboard())
        return
    # Преобразуем Decimal в float
    orders = []
    for r in rows:
        d = dict(r)
        d['amount'] = float(d['amount'])
        d['total_locked'] = float(d['total_locked'])
        orders.append(d)
    # Разбивка по страницам
    page = 1
    total_pages = (len(orders) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_orders = orders[start:end]
    kb = my_orders_keyboard(page_orders, page, total_pages)
    await message.answer("Твои активные заявки:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("myorder_"))
async def my_order_detail(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    async with db_pool.acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM bitcoin_orders WHERE id=$1", order_id)
    if not order or order['status'] != 'active':
        await callback.answer("Заявка не найдена или уже не активна.", show_alert=True)
        return
    # Преобразуем Decimal в float
    amount = float(order['amount'])
    total_locked = float(order['total_locked'])
    text = (
        f"📄 Заявка #{order['id']}\n"
        f"Тип: {'📈 Покупка' if order['type']=='buy' else '📉 Продажа'}\n"
        f"Количество: {amount:.4f} BTC\n"
        f"Цена: {order['price']} $/BTC\n"
        f"Всего: {amount * order['price']:.2f} $\n"
        f"Создана: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_order_{order_id}")],
        [InlineKeyboardButton(text="« Назад", callback_data="my_orders_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_order_"))
async def cancel_order_callback(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    success = await cancel_bitcoin_order(order_id, user_id)
    if success:
        await callback.answer("✅ Заявка отменена, средства возвращены.", show_alert=True)
    else:
        await callback.answer("❌ Не удалось отменить заявку.", show_alert=True)
    await my_orders(callback.message)

@dp.callback_query_handler(lambda c: c.data == "my_orders_back")
async def my_orders_back(callback: types.CallbackQuery):
    await my_orders(callback.message)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("myorders_page_"))
async def myorders_page_callback(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    # Изменяем текст сообщения, чтобы my_orders отобразил нужную страницу
    callback.message.text = f"📋 Мои заявки {page}"
    await my_orders(callback.message)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "exchange_back")
async def exchange_back(callback: types.CallbackQuery):
    await bitcoin_exchange_menu(callback.message)
    await callback.answer()

# ==================== КОНЕЦ ЧАСТИ 5 ====================
# ==================== ЧАСТЬ 6: МУЛЬТИПЛЕЕР (ИГРА 21) ====================

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ МУЛЬТИПЛЕЕРА ====================

async def get_multiplayer_game(game_id: str) -> Optional[dict]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
        return dict(row) if row else None

async def get_game_players(game_id: str) -> List[dict]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM game_players WHERE game_id=$1 ORDER BY joined_at", game_id)
        return [dict(r) for r in rows]

async def add_player_to_game(game_id: str, user_id: int, username: str):
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1 AND status='waiting'", game_id)
        if not game:
            raise ValueError("Игра не найдена или уже началась")
        players_count = await conn.fetchval("SELECT COUNT(*) FROM game_players WHERE game_id=$1", game_id)
        if players_count >= game['max_players']:
            raise ValueError("Комната уже полная")
        await conn.execute(
            "INSERT INTO game_players (game_id, user_id, username, cards, value, stopped, joined_at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            game_id, user_id, username, '', 0, False, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

async def remove_player_from_game(game_id: str, user_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM game_players WHERE game_id=$1 AND user_id=$2", game_id, user_id)
        remaining = await conn.fetchval("SELECT COUNT(*) FROM game_players WHERE game_id=$1", game_id)
        if remaining == 0:
            await conn.execute("DELETE FROM multiplayer_games WHERE game_id=$1", game_id)

async def start_game(game_id: str):
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1 AND status='waiting'", game_id)
            if not game:
                raise ValueError("Игра не найдена или уже началась")
            players = await conn.fetch("SELECT * FROM game_players WHERE game_id=$1 ORDER BY joined_at", game_id)
            if len(players) < 2:
                raise ValueError("Недостаточно игроков")
            
            # bet_amount из таблицы может быть Decimal, преобразуем в float
            bet_amount = float(game['bet_amount'])
            for player in players:
                balance = await get_user_balance(player['user_id'])
                if balance < bet_amount - 0.01:
                    raise ValueError(f"У игрока {player['username']} недостаточно баксов")
            
            for player in players:
                await update_user_balance(player['user_id'], -bet_amount, conn=conn)
            
            deck = create_deck()
            deck_str = ','.join(deck)
            for player in players:
                cards = [deck.pop(), deck.pop()]
                value = calculate_hand_value(cards)
                await conn.execute(
                    "UPDATE game_players SET cards=$1, value=$2 WHERE game_id=$3 AND user_id=$4",
                    ','.join(cards), value, game_id, player['user_id']
                )
            await conn.execute(
                "UPDATE multiplayer_games SET status='playing', deck=$1, current_player_index=0 WHERE game_id=$2",
                deck_str, game_id
            )
            return game_id

async def get_current_player(game_id: str) -> Optional[dict]:
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
        if not game or game['status'] != 'playing':
            return None
        players = await conn.fetch("SELECT * FROM game_players WHERE game_id=$1 ORDER BY joined_at", game_id)
        if not players:
            return None
        idx = game['current_player_index']
        if idx >= len(players):
            return None
        return dict(players[idx])

async def next_player(game_id: str) -> Optional[int]:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
            if not game:
                return -1
            players = await conn.fetch("SELECT * FROM game_players WHERE game_id=$1 ORDER BY joined_at", game_id)
            if not players:
                return -1
            all_stopped = all(p['stopped'] or p['surrendered'] or p['value'] > 21 for p in players)
            if all_stopped:
                await finish_game(game_id)
                return -1
            current_idx = game['current_player_index']
            next_idx = current_idx
            for _ in range(len(players)):
                next_idx = (next_idx + 1) % len(players)
                p = players[next_idx]
                if not p['stopped'] and not p['surrendered'] and p['value'] <= 21:
                    await conn.execute("UPDATE multiplayer_games SET current_player_index=$1 WHERE game_id=$2", next_idx, game_id)
                    return next_idx
            await finish_game(game_id)
            return -1

async def finish_game(game_id: str):
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
            if not game or game['status'] != 'playing':
                return
            players = await conn.fetch("SELECT * FROM game_players WHERE game_id=$1", game_id)
            if not players:
                await conn.execute("DELETE FROM multiplayer_games WHERE game_id=$1", game_id)
                return
            best_value = -1
            winner_id = None
            for p in players:
                val = p['value']
                if val <= 21 and val > best_value:
                    best_value = val
                    winner_id = p['user_id']
            bet_amount = float(game['bet_amount'])
            pot = bet_amount * len(players)
            if winner_id:
                await update_user_balance(winner_id, pot, conn=conn)
                await update_user_game_stats(winner_id, 'multiplayer', win=True, conn=conn)
                for p in players:
                    if p['user_id'] != winner_id:
                        await update_user_game_stats(p['user_id'], 'multiplayer', win=False, conn=conn)
                exp_win = await get_setting_int("exp_per_game_win")
                exp_lose = await get_setting_int("exp_per_game_lose")
                await add_exp(winner_id, exp_win, conn=conn)
                for p in players:
                    if p['user_id'] != winner_id:
                        await add_exp(p['user_id'], exp_lose, conn=conn)
                for p in players:
                    if p['user_id'] == winner_id:
                        await safe_send_message(p['user_id'], f"🎉 Ты выиграл в игре 21! Твой выигрыш: {pot:.2f} баксов.")
                    else:
                        await safe_send_message(p['user_id'], f"😢 Ты проиграл в игре 21. Твоя ставка {bet_amount:.2f} баксов потеряна.")
            else:
                for p in players:
                    await update_user_balance(p['user_id'], bet_amount, conn=conn)
                    await update_user_game_stats(p['user_id'], 'multiplayer', win=False, conn=conn)
                    await add_exp(p['user_id'], await get_setting_int("exp_per_game_lose"), conn=conn)
                    await safe_send_message(p['user_id'], f"🤝 В игре 21 ничья. Твоя ставка {bet_amount:.2f} баксов возвращена.")
            await conn.execute("DELETE FROM multiplayer_games WHERE game_id=$1", game_id)
            await conn.execute("DELETE FROM game_players WHERE game_id=$1", game_id)

# ==================== ХЕНДЛЕРЫ МУЛЬТИПЛЕЕРА ====================

@dp.message_handler(lambda message: message.text == "👥 Мультиплеер 21")
async def multiplayer_menu(message: types.Message):
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        return
    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    ok, not_subscribed = await check_subscription(user_id)
    if not ok:
        await message.answer("❗️ Сначала подпишись на каналы.", reply_markup=subscription_inline(not_subscribed))
        return
    min_level = await get_setting_int("min_level_multiplayer")
    level = await get_user_level(user_id)
    if level < min_level:
        await message.answer(f"❌ Для игры в мультиплеер нужен {min_level} уровень. Твой уровень: {level}")
        return
    # Отправляем картинку мультиплеера, если есть
    await send_with_media(user_id, "🎮 Мультиплеер 21 (очко)", media_key='multiplayer', reply_markup=multiplayer_lobby_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать комнату")
async def create_room_start(message: types.Message):
    if message.chat.type != 'private':
        return
    await message.answer("Введи максимальное количество игроков (2-5):", reply_markup=back_keyboard())
    await MultiplayerGame.create_max_players.set()

@dp.message_handler(state=MultiplayerGame.create_max_players)
async def create_room_max_players(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await multiplayer_menu(message)
        return
    try:
        max_players = int(message.text)
        if max_players < 2 or max_players > 5:
            raise ValueError
    except:
        await message.answer("❌ Введи число от 2 до 5.")
        return
    await state.update_data(max_players=max_players)
    await message.answer("Введи ставку (можно дробную, например 10.50):")
    await MultiplayerGame.create_bet.set()

@dp.message_handler(state=MultiplayerGame.create_bet)
async def create_room_bet(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await multiplayer_menu(message)
        return
    try:
        bet = float(message.text)
        if bet <= 0:
            raise ValueError
        bet = round(bet, 2)
    except ValueError:
        await message.answer("❌ Введи положительное число с точностью до сотых.")
        return
    min_bet = await get_setting_float("multiplayer_min_bet")
    max_bet = await get_setting_float("multiplayer_max_bet")
    max_input = await get_setting_float("max_input_number")
    if bet < min_bet or bet > max_bet:
        await message.answer(f"❌ Ставка должна быть от {min_bet:.2f} до {max_bet:.2f}.")
        return
    if bet > max_input:
        await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
        return
    user_id = message.from_user.id
    balance = await get_user_balance(user_id)
    if balance < bet:
        await message.answer("❌ Недостаточно баксов.")
        return
    data = await state.get_data()
    max_players = data['max_players']
    game_id = generate_game_id()
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO multiplayer_games (game_id, host_id, max_players, bet_amount, status, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
            game_id, user_id, max_players, bet, 'waiting', datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        await conn.execute(
            "INSERT INTO game_players (game_id, user_id, username, cards, value, stopped, joined_at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            game_id, user_id, message.from_user.username or "Player", '', 0, False, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    await state.finish()
    text = (
        f"🎮 Комната {game_id} создана!\n"
        f"Ставка: {bet:.2f} баксов\n"
        f"Игроков: 1/{max_players}\n"
        f"Поделись этим ID с друзьями, чтобы они присоединились."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Присоединиться", url=f"https://t.me/{(await bot.me).username}?start=join_{game_id}")],
        [InlineKeyboardButton(text="❌ Закрыть комнату", callback_data=f"close_room_{game_id}")]
    ])
    await send_with_media(user_id, text, media_key='multiplayer', reply_markup=kb)

@dp.message_handler(lambda message: message.text == "🔍 Найти комнату")
async def join_room_by_code(message: types.Message):
    if message.chat.type != 'private':
        return
    await message.answer("Введи код комнаты (например, ABC123):", reply_markup=back_keyboard())
    await MultiplayerGame.join_code.set()

@dp.message_handler(state=MultiplayerGame.join_code)
async def join_room_code(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await multiplayer_menu(message)
        return
    game_id = message.text.strip().upper()
    user_id = message.from_user.id
    try:
        game = await get_multiplayer_game(game_id)
        if not game or game['status'] != 'waiting':
            await message.answer("❌ Комната не найдена или уже началась.")
            return
        players = await get_game_players(game_id)
        if len(players) >= game['max_players']:
            await message.answer("❌ Комната уже полная.")
            return
        if any(p['user_id'] == user_id for p in players):
            await message.answer("❌ Ты уже в этой комнате.")
            return
        balance = await get_user_balance(user_id)
        bet_amount = float(game['bet_amount'])
        if balance < bet_amount:
            await message.answer(f"❌ Недостаточно баксов для ставки {bet_amount:.2f}.")
            return
        await add_player_to_game(game_id, user_id, message.from_user.username or "Player")
        await message.answer(f"✅ Ты присоединился к комнате {game_id}.\nСтавка: {bet_amount:.2f} баксов.\nОжидаем начала игры.")
        host_id = game['host_id']
        await safe_send_message(host_id, f"🔔 Новый игрок {message.from_user.first_name} присоединился к комнате {game_id}. Текущий состав: {len(players)+1}/{game['max_players']}")
    except Exception as e:
        logging.error(f"Join room error: {e}")
        await message.answer("❌ Ошибка при присоединении.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список комнат")
async def list_rooms(message: types.Message):
    if message.chat.type != 'private':
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM multiplayer_games WHERE status='waiting' ORDER BY created_at DESC LIMIT 10")
    if not rows:
        await message.answer("Нет открытых комнат.")
        return
    text = "📋 Открытые комнаты:\n\n"
    for row in rows:
        players = await get_game_players(row['game_id'])
        text += f"🆔 {row['game_id']} | Ставка: {float(row['bet_amount']):.2f} | Игроков: {len(players)}/{row['max_players']}\n"
    await message.answer(text, reply_markup=multiplayer_lobby_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith("close_room_"))
async def close_room_callback(callback: types.CallbackQuery):
    game_id = callback.data.split("_")[2]
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
        if not game or game['host_id'] != user_id:
            await callback.answer("❌ Только создатель может закрыть комнату.", show_alert=True)
            return
        await conn.execute("DELETE FROM multiplayer_games WHERE game_id=$1", game_id)
        await conn.execute("DELETE FROM game_players WHERE game_id=$1", game_id)
    await callback.message.edit_text("❌ Комната закрыта.")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("start_game_"))
async def start_game_callback(callback: types.CallbackQuery):
    game_id = callback.data.split("_")[2]
    user_id = callback.from_user.id
    try:
        game = await get_multiplayer_game(game_id)
        if not game or game['host_id'] != user_id:
            await callback.answer("❌ Только создатель может начать игру.", show_alert=True)
            return
        if game['status'] != 'waiting':
            await callback.answer("❌ Игра уже началась.", show_alert=True)
            return
        players = await get_game_players(game_id)
        if len(players) < 2:
            await callback.answer("❌ Недостаточно игроков (минимум 2).", show_alert=True)
            return
        await start_game(game_id)
        for p in players:
            await safe_send_message(p['user_id'], f"🎮 Игра {game_id} началась! Твой ход будет объявлен.")
        await show_current_turn(game_id, callback.message)
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Start game error: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

async def show_current_turn(game_id: str, message: types.Message = None, user_id: int = None):
    game = await get_multiplayer_game(game_id)
    if not game or game['status'] != 'playing':
        return
    current_player = await get_current_player(game_id)
    if not current_player:
        return
    players = await get_game_players(game_id)
    text = f"🎮 Игра {game_id}\n\n"
    for p in players:
        cards = p['cards'].split(',') if p['cards'] else []
        card_str = ' '.join(cards) if cards else '❓'
        status = "✅" if p['stopped'] else "⏳" if p['user_id'] == current_player['user_id'] else "⏸️"
        if p['surrendered']:
            status = "🏳️"
        elif p['value'] > 21:
            status = "💥"
        text += f"{status} {p['username']}: {card_str} = {p['value'] if p['value']>0 else '?'}\n"
    text += f"\n💰 Твоя ставка: {float(game['bet_amount']):.2f} баксов"
    kb = room_action_keyboard(can_double=not current_player['doubled'])
    if user_id:
        await bot.send_message(user_id, text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data in ["room_hit", "room_stand", "room_double", "room_surrender", "room_chat"])
async def room_action_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        game_row = await conn.fetchrow("""
            SELECT g.* FROM multiplayer_games g
            JOIN game_players p ON g.game_id = p.game_id
            WHERE p.user_id=$1 AND g.status='playing'
        """, user_id)
    if not game_row:
        await callback.answer("❌ Ты не участвуешь в активной игре.", show_alert=True)
        return
    game_id = game_row['game_id']
    action = callback.data.split("_")[1] if "_" in callback.data else callback.data
    current = await get_current_player(game_id)
    if not current or current['user_id'] != user_id:
        await callback.answer("❌ Сейчас не твой ход.", show_alert=True)
        return
    
    if action == "hit":
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
                deck = game['deck'].split(',')
                if not deck:
                    await callback.answer("❌ Колода закончилась!", show_alert=True)
                    return
                card = deck.pop()
                new_deck = ','.join(deck)
                player = await conn.fetchrow("SELECT * FROM game_players WHERE game_id=$1 AND user_id=$2", game_id, user_id)
                cards = player['cards'].split(',') if player['cards'] else []
                cards.append(card)
                value = calculate_hand_value(cards)
                await conn.execute(
                    "UPDATE game_players SET cards=$1, value=$2 WHERE game_id=$3 AND user_id=$4",
                    ','.join(cards), value, game_id, user_id
                )
                await conn.execute("UPDATE multiplayer_games SET deck=$1 WHERE game_id=$2", new_deck, game_id)
                if value > 21:
                    await conn.execute("UPDATE game_players SET stopped=TRUE WHERE game_id=$1 AND user_id=$2", game_id, user_id)
                    await next_player(game_id)
        await callback.answer()
        await show_current_turn(game_id, user_id=user_id)
        
    elif action == "stand":
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE game_players SET stopped=TRUE WHERE game_id=$1 AND user_id=$2", game_id, user_id)
            await next_player(game_id)
        await callback.answer()
        await show_current_turn(game_id, user_id=user_id)
        
    elif action == "double":
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                player = await conn.fetchrow("SELECT * FROM game_players WHERE game_id=$1 AND user_id=$2", game_id, user_id)
                if player['doubled']:
                    await callback.answer("❌ Ты уже удваивал ставку.", show_alert=True)
                    return
                game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
                bet = float(game['bet_amount'])
                balance = await get_user_balance(user_id)
                if balance < bet:
                    await callback.answer("❌ Недостаточно баксов для удвоения.", show_alert=True)
                    return
                await update_user_balance(user_id, -bet, conn=conn)
                await conn.execute("UPDATE game_players SET doubled=TRUE WHERE game_id=$1 AND user_id=$2", game_id, user_id)
                deck = game['deck'].split(',')
                if deck:
                    card = deck.pop()
                    new_deck = ','.join(deck)
                    cards = player['cards'].split(',') if player['cards'] else []
                    cards.append(card)
                    value = calculate_hand_value(cards)
                    await conn.execute(
                        "UPDATE game_players SET cards=$1, value=$2, stopped=TRUE WHERE game_id=$3 AND user_id=$4",
                        ','.join(cards), value, game_id, user_id
                    )
                    await conn.execute("UPDATE multiplayer_games SET deck=$1 WHERE game_id=$2", new_deck, game_id)
                else:
                    await conn.execute("UPDATE game_players SET stopped=TRUE WHERE game_id=$1 AND user_id=$2", game_id, user_id)
                await next_player(game_id)
        await callback.answer()
        await show_current_turn(game_id, user_id=user_id)
        
    elif action == "surrender":
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE game_players SET surrendered=TRUE WHERE game_id=$1 AND user_id=$2", game_id, user_id)
            await next_player(game_id)
        await callback.answer()
        await show_current_turn(game_id, user_id=user_id)
        
    elif action == "chat":
        await callback.message.answer("💬 Введи сообщение для всех игроков комнаты (или /cancel для выхода):", reply_markup=cancel_keyboard())
        await RoomChat.message.set()
        await state.update_data(game_id=game_id)

@dp.message_handler(state=RoomChat.message)
async def room_chat_message(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await multiplayer_menu(message)
        return
    data = await state.get_data()
    game_id = data['game_id']
    players = await get_game_players(game_id)
    for p in players:
        if p['user_id'] != message.from_user.id:
            await safe_send_message(p['user_id'], f"💬 {message.from_user.first_name}: {message.text}")
    await message.answer("✅ Сообщение отправлено всем игрокам комнаты.")
    await state.finish()
    await show_current_turn(game_id, user_id=message.from_user.id)

@dp.callback_query_handler(lambda c: c.data.startswith("leave_room_"))
async def leave_room_callback(callback: types.CallbackQuery):
    game_id = callback.data.split("_")[2]
    user_id = callback.from_user.id
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow("SELECT * FROM multiplayer_games WHERE game_id=$1", game_id)
        if game and game['status'] == 'waiting':
            await remove_player_from_game(game_id, user_id)
            await callback.answer("✅ Ты покинул комнату.")
            await callback.message.delete()
        else:
            await callback.answer("❌ Нельзя покинуть комнату после начала игры.", show_alert=True)

# ==================== КОНЕЦ ЧАСТИ 6 ====================
# ==================== ЧАСТЬ 7: ГРУППОВЫЕ ХЕНДЛЕРЫ (КОМАНДЫ С ПРЕФИКСОМ /mlb_) ====================

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ГРУПП ====================
async def check_chat(message: types.Message) -> bool:
    """Проверяет, что сообщение из группы и чат активирован."""
    if message.chat.type == 'private':
        await message.reply("❌ Эта команда работает только в группах.")
        return False
    if not await is_chat_confirmed(message.chat.id):
        await message.reply("❌ Этот чат не активирован. Используйте /activate_chat для запроса активации.")
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

# ==================== КОМАНДА /activate_chat ====================
@dp.message_handler(commands=['activate_chat'])
async def activate_chat_command(message: types.Message):
    if message.chat.type == 'private':
        await message.reply("❌ Эта команда работает только в группах.")
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if await is_chat_confirmed(chat_id):
        await message.reply("✅ Этот чат уже активирован!")
        return
    
    await create_chat_confirmation_request(
        chat_id, 
        message.chat.title or "Без названия", 
        message.chat.type, 
        user_id
    )
    
    await message.reply("📨 Запрос на активацию чата отправлен администраторам!")
    
    admins = SUPER_ADMINS.copy()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM admins")
        admins.extend([r['user_id'] for r in rows])
    
    for admin_id in admins:
        await safe_send_message(
            admin_id,
            f"🔔 Запрос на активацию чата!\n"
            f"Чат: {message.chat.title} (ID: {chat_id})\n"
            f"Запросил: {message.from_user.first_name} (ID: {user_id})"
        )

# ==================== КОМАНДА /mlb_fight ====================
@dp.message_handler(commands=['mlb_fight'])
async def cmd_fight(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(message.from_user.id, 'fight')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'fight')
    
    await auto_delete_message(message)

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
    bitcoin_reward = await get_setting_int("bitcoin_per_fight")

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
        await update_user_balance(user_id, -float(counter_damage))
        outcome = "counter"
        phrase_list = FIGHT_COUNTER_PHRASES

    await add_chat_authority(chat_id, user_id, authority, damage)
    if bitcoin_reward > 0:
        await update_user_bitcoin(user_id, float(bitcoin_reward))
    await set_fight_cooldown(chat_id, user_id)
    await log_fight(chat_id, user_id, damage, authority, outcome)

    exp = await get_setting_int("exp_per_fight")
    await add_exp(user_id, exp)

    if outcome == "counter":
        phrase = get_random_phrase(phrase_list, damage=counter_damage)
        extra = f"\n💸 Ты потерял {counter_damage} баксов."
    else:
        phrase = get_random_phrase(phrase_list, damage=damage, authority=authority)
        extra = f"\n₿ +{bitcoin_reward} BTC" if bitcoin_reward > 0 else ""

    # Отправляем картинку боя, если есть
    text = f"{username}, {phrase}{extra}\nТвой авторитет в этом чате: {await get_chat_authority(chat_id, user_id)}"
    # В групповых чатах используем auto_delete_reply, но с медиа не получится, поэтому просто отправляем текст
    # Можно отправить фото отдельно перед текстом, но тогда не будет автоудаления.
    # Для простоты оставим как есть.
    await auto_delete_reply(message, text)

# ==================== КОМАНДА /mlb_gym ====================
@dp.message_handler(commands=['mlb_gym'])
async def cmd_gym(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(message.from_user.id, 'gym')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'gym')
    
    await auto_delete_message(message)

    chat_id = message.chat.id
    user_id = message.from_user.id
    authority = await get_chat_authority(chat_id, user_id)

    strength_cost = await get_setting_int("gym_strength_cost")
    agility_cost = await get_setting_int("gym_agility_cost")
    defense_cost = await get_setting_int("gym_defense_cost")

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

    await ensure_user_exists(user_id, callback.from_user.username, callback.from_user.first_name)

    action = callback.data.split("_")[1]

    if action == "cancel":
        await callback.message.delete()
        await callback.answer()
        return

    if action == "strength":
        cost = await get_setting_int("gym_strength_cost")
        stat = "strength"
    elif action == "agility":
        cost = await get_setting_int("gym_agility_cost")
        stat = "agility"
    elif action == "defense":
        cost = await get_setting_int("gym_defense_cost")
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

# ==================== КОМАНДА /mlb_status ====================
@dp.message_handler(commands=['mlb_status'])
async def cmd_status(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(message.from_user.id, 'status')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'status')
    
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

# ==================== КОМАНДА /mlb_top ====================
@dp.message_handler(commands=['mlb_top'])
async def cmd_top(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(message.from_user.id, 'top')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'top')
    
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

# ==================== КОМАНДА /mlb_help В ЧАТЕ ====================
@dp.message_handler(commands=['mlb_help'])
async def cmd_help_chat(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(message.from_user.id, 'help')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'help')
    
    await auto_delete_message(message)

    text = (
        "📋 <b>Доступные команды в чате:</b>\n\n"
        "⚔️ <b>Боевые команды:</b>\n"
        "/mlb_fight – Атаковать банду (кулдаун 30 мин)\n"
        "/mlb_status – Твой статус в этом чате\n"
        "/mlb_top [страница] – Топ чата (по авторитету/урону/боям)\n"
        "/mlb_gym – Улучшить характеристики за авторитет\n\n"
        "👾 <b>Боссы:</b>\n"
        "/mlb_boss_status – Текущее состояние босса\n"
        "/mlb_boss_attack – Атаковать активного босса\n\n"
        "📦 <b>Контрабанда:</b>\n"
        "/mlb_smuggle_chat – Отправиться в контрабандный рейс\n\n"
        "🎁 <b>Подгон:</b>\n"
        "Кнопка \"🎁 Подгон\" появляется в чате после активации\n\n"
        "ℹ️ <b>Другое:</b>\n"
        "/mlb_help – Это сообщение\n"
        "/activate_chat – Запросить активацию чата\n\n"
        "<i>Команды работают только в активированных чатах</i>"
    )
    await auto_delete_reply(message, text)

# ==================== КОМАНДА /mlb_boss_status ====================
@dp.message_handler(commands=['mlb_boss_status'])
async def cmd_boss_status(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(message.from_user.id, 'boss_status')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'boss_status')
    
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
        f"💰 Награда: {boss['reward_coins']} баксов, ₿ {boss['reward_bitcoin']} BTC"
    )
    await update_boss_status_time(chat_id)

    # Отправляем с картинкой босса, если есть общая картинка для статуса или изображение босса
    image_file_id = boss['image_file_id'] or await get_media_file_id('boss_status')
    if image_file_id:
        await bot.send_photo(chat_id, image_file_id, caption=text)
    else:
        await safe_send_chat(chat_id, text)

# ==================== КОМАНДА /mlb_boss_attack ====================
@dp.message_handler(commands=['mlb_boss_attack'])
async def cmd_boss_attack(message: types.Message):
    if not await check_chat(message):
        return
    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return
    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    ok, remaining = await check_global_cooldown(message.from_user.id, 'boss_attack')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'boss_attack')
    await auto_delete_message(message)

    chat_id = message.chat.id
    user_id = message.from_user.id

    async with db_pool.acquire() as conn:
        boss = await conn.fetchrow(
            "SELECT * FROM bosses WHERE chat_id=$1 AND status='active'",
            chat_id
        )
        if not boss:
            await auto_delete_reply(message, "❌ В этом чате нет активного босса.")
            return

        existing = await conn.fetchval(
            "SELECT 1 FROM boss_attacks WHERE boss_id=$1 AND user_id=$2",
            boss['id'], user_id
        )
        if existing:
            await auto_delete_reply(message, "⏳ Ты уже атаковал этого босса. Жди следующего.")
            return

        stats = await get_user_stats(user_id)
        damage = stats['strength'] * 2 + random.randint(1, 10)
        new_hp = boss['hp'] - damage
        if new_hp < 0:
            new_hp = 0

        await conn.execute(
            "UPDATE bosses SET hp=$1 WHERE id=$2",
            new_hp, boss['id']
        )
        await conn.execute(
            "INSERT INTO boss_attacks (boss_id, user_id, damage, attack_time) VALUES ($1, $2, $3, $4)",
            boss['id'], user_id, damage, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        participants = boss['participants'] or []
        if user_id not in participants:
            participants.append(user_id)
            await conn.execute(
                "UPDATE bosses SET participants=$1 WHERE id=$2",
                participants, boss['id']
            )

        if new_hp <= 0:
            await finish_boss_fight(boss['id'])
            await auto_delete_reply(message, f"💥 Ты нанёс {damage} урона и убил босса! Босс повержен.")
        else:
            await auto_delete_reply(message, f"💥 Ты нанёс {damage} урона! У босса осталось {new_hp} HP.")

# ==================== ПОДГОН (GIFT) В ЧАТЕ ====================
@dp.message_handler(lambda message: message.chat.type != 'private' and message.text == "🎁 Подгон")
async def chat_gift(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if await is_banned(user_id) and not await is_admin(user_id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return
    if not await is_chat_confirmed(chat_id):
        await auto_delete_reply(message, "❌ Этот чат ещё не активирован. Используйте /activate_chat для запроса.")
        return

    await ensure_user_exists(user_id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(user_id, 'gift')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(user_id, 'gift')
    
    await auto_delete_message(message)

    gift_amount = await get_setting_float("gift_amount")
    gift_limit_per_chat = await get_setting_int("gift_limit_per_day")
    gift_global_limit = await get_setting_int("gift_global_limit_per_user")
    gift_cooldown = await get_setting_int("gift_cooldown")
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
                f"Счастливчик: {recipient.first_name} получает {gift_amount:.2f} баксов! 🎉\n"
                f"📊 Сегодня в этом чате осталось подгонов: {remaining_chat}"
            )

# ==================== КОМАНДА /mlb_smuggle_chat ====================
@dp.message_handler(commands=['mlb_smuggle_chat'])
async def cmd_smuggle_chat(message: types.Message):
    if not await check_chat(message):
        return

    if await is_banned(message.from_user.id) and not await is_admin(message.from_user.id):
        await auto_delete_reply(message, "⛔ Вы заблокированы.")
        return

    await ensure_user_exists(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    ok, remaining = await check_global_cooldown(message.from_user.id, 'smuggle_chat')
    if not ok:
        await auto_delete_reply(message, f"⏳ Глобальный кулдаун. Подожди {remaining} сек.")
        return
    await set_global_cooldown(message.from_user.id, 'smuggle_chat')
    
    await auto_delete_message(message)

    user_id = message.from_user.id
    chat_id = message.chat.id

    ok, remaining = await check_smuggle_cooldown(user_id)
    if not ok:
        minutes = remaining // 60
        seconds = remaining % 60
        await auto_delete_reply(message, f"⏳ Ты ещё не вернулся из рейса. Подожди {minutes} мин {seconds} сек.")
        return

    min_dur = await get_setting_int("smuggle_min_duration")
    max_dur = await get_setting_int("smuggle_max_duration")
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
    # Отправляем картинку контрабанды, если есть
    file_id = await get_media_file_id('smuggle')
    if file_id:
        await bot.send_photo(chat_id, file_id, caption=f"🚤 {message.from_user.first_name}, {phrase}")
    else:
        await auto_delete_reply(message, f"🚤 {message.from_user.first_name}, {phrase}")

# ==================== КОНЕЦ ЧАСТИ 7 ====================
# ==================== ЧАСТЬ 8: АДМИНИСТРАТИВНАЯ ПАНЕЛЬ ====================

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ АДМИНКИ ====================
async def check_admin_permissions(user_id: int, permission: str) -> bool:
    return await has_permission(user_id, permission)

# ==================== КАТЕГОРИИ НАСТРОЕК ====================
SETTINGS_CATEGORIES = {
    "⚙️ Кража": [
        ("random_attack_cost", "💰 Стоимость случайной кражи"),
        ("targeted_attack_cost", "🎯 Стоимость целевой кражи"),
        ("theft_cooldown_minutes", "⏳ Кулдаун кражи (минуты)"),
        ("theft_success_chance", "✅ Шанс успеха кражи (%)"),
        ("theft_defense_chance", "🛡 Шанс защиты жертвы (%)"),
        ("theft_defense_penalty", "💸 Штраф при защите"),
        ("min_theft_amount", "⬇️ Мин. сумма кражи"),
        ("max_theft_amount", "⬆️ Макс. сумма кражи"),
    ],
    "⚙️ Казино и игры": [
        ("casino_win_chance", "🎰 Шанс выигрыша в казино (%)"),
        ("casino_min_bet", "🎰 Мин. ставка в казино"),
        ("casino_max_bet", "🎰 Макс. ставка в казино"),
        ("casino_multiplier", "🎰 Множитель выигрыша"),
        ("dice_multiplier", "🎲 Множитель в костях"),
        ("dice_win_threshold", "🎲 Порог победы (сумма костей)"),
        ("guess_multiplier", "🔢 Множитель в угадайке"),
        ("guess_reputation", "🔢 Репутация за победу"),
        ("slots_multiplier_three", "🍒 Множитель 3 символа"),
        ("slots_multiplier_diamond", "💎 Множитель бриллианты"),
        ("slots_multiplier_seven", "7️⃣ Множитель семерки"),
        ("slots_win_probability", "🍒 Шанс выигрыша в слотах (%)"),
        ("slots_min_bet", "🍒 Мин. ставка в слотах"),
        ("slots_max_bet", "🍒 Макс. ставка в слотах"),
        ("roulette_color_multiplier", "🎡 Множитель на цвет"),
        ("roulette_green_multiplier", "🎡 Множитель на зеленый"),
        ("roulette_number_multiplier", "🎡 Множитель на число"),
        ("roulette_min_bet", "🎡 Мин. ставка в рулетке"),
        ("roulette_max_bet", "🎡 Макс. ставка в рулетке"),
        ("multiplayer_min_bet", "👥 Мин. ставка в мультиплеере"),
        ("multiplayer_max_bet", "👥 Макс. ставка в мультиплеере"),
    ],
    "⚙️ Ограничения по уровню": [
        ("min_level_casino", "🎰 Мин. уровень для казино"),
        ("min_level_dice", "🎲 Мин. уровень для костей"),
        ("min_level_guess", "🔢 Мин. уровень для угадайки"),
        ("min_level_slots", "🍒 Мин. уровень для слотов"),
        ("min_level_roulette", "🎡 Мин. уровень для рулетки"),
        ("min_level_multiplayer", "👥 Мин. уровень для мультиплеера"),
    ],
    "⚙️ Уведомления": [
        ("chat_notify_big_win", "🔥 Уведомлять о крупных выигрышах (1/0)"),
        ("chat_notify_big_purchase", "🛒 Уведомлять о крупных покупках (1/0)"),
        ("chat_notify_giveaway", "🎁 Уведомлять о розыгрышах (1/0)"),
    ],
    "⚙️ Подгон": [
        ("gift_amount", "🎁 Сумма подгона"),
        ("gift_limit_per_day", "📊 Лимит подгонов в чате в день"),
        ("gift_global_limit_per_user", "🌐 Глобальный лимит подгонов на пользователя"),
        ("gift_cooldown", "⏳ Кулдаун подгона (минуты)"),
    ],
    "⚙️ Рефералы": [
        ("referral_bonus", "💰 Бонус за реферала"),
        ("referral_reputation", "⭐ Репутация за реферала"),
        ("referral_required_thefts", "🔫 Требуется краж для активации"),
    ],
    "⚙️ Опыт и уровни": [
        ("exp_per_casino_win", "🎰 Опыт за победу в казино"),
        ("exp_per_casino_lose", "🎰 Опыт за проигрыш в казино"),
        ("exp_per_dice_win", "🎲 Опыт за победу в кости"),
        ("exp_per_dice_lose", "🎲 Опыт за проигрыш в кости"),
        ("exp_per_guess_win", "🔢 Опыт за победу в угадайке"),
        ("exp_per_guess_lose", "🔢 Опыт за проигрыш в угадайке"),
        ("exp_per_slots_win", "🍒 Опыт за победу в слотах"),
        ("exp_per_slots_lose", "🍒 Опыт за проигрыш в слотах"),
        ("exp_per_roulette_win", "🎡 Опыт за победу в рулетке"),
        ("exp_per_roulette_lose", "🎡 Опыт за проигрыш в рулетке"),
        ("exp_per_theft_success", "🔫 Опыт за успешную кражу"),
        ("exp_per_theft_fail", "🔫 Опыт за провал кражи"),
        ("exp_per_theft_defense", "🛡 Опыт за защиту"),
        ("exp_per_game_win", "👥 Опыт за победу в мультиплеере"),
        ("exp_per_game_lose", "👥 Опыт за проигрыш в мультиплеере"),
        ("exp_per_fight", "⚔️ Опыт за бой"),
        ("exp_per_smuggle", "📦 Опыт за контрабанду"),
        ("level_multiplier", "📊 Множитель опыта для уровня"),
        ("level_reward_coins", "💰 База награды за уровень"),
        ("level_reward_reputation", "⭐ База репутации за уровень"),
        ("level_reward_coins_increment", "📈 Прирост баксов за уровень"),
        ("level_reward_reputation_increment", "📈 Прирост репутации за уровень"),
    ],
    "⚙️ Репутация": [
        ("reputation_theft_bonus", "🔫 Бонус репутации к краже (% за единицу)"),
        ("reputation_defense_bonus", "🛡 Бонус репутации к защите (% за единицу)"),
        ("reputation_smuggle_bonus", "📦 Бонус репутации к BTC (за единицу)"),
        ("reputation_smuggle_success_bonus", "🚤 Бонус репутации к успеху контрабанды (% за единицу)"),
        ("reputation_max_bonus_percent", "📊 Макс. бонус от репутации (%)"),
    ],
    "⚙️ Боссы": [
        ("boss_spawn_chance", "🎲 Шанс спавна босса (%)"),
        ("boss_min_interval", "⏳ Мин. интервал между спавнами (минуты)"),
        ("boss_max_per_day", "📊 Макс. боссов в день на чат"),
        ("boss_hp_multiplier", "❤️ Множитель HP"),
        ("boss_attack_cooldown", "⏳ Кулдаун атаки (секунды)"),
        ("boss_base_damage", "💥 База урона"),
        ("boss_reward_coins", "💰 База награды баксами"),
        ("boss_reward_coins_variance", "🎲 Вариация награды баксами"),
        ("boss_reward_bitcoin", "₿ База награды BTC"),
        ("boss_reward_bitcoin_variance", "🎲 Вариация награды BTC"),
    ],
    "⚙️ Статы за уровень": [
        ("stat_strength_per_level", "💪 Силы за уровень"),
        ("stat_agility_per_level", "🏃 Ловкости за уровень"),
        ("stat_defense_per_level", "🛡 Защиты за уровень"),
    ],
    "⚙️ Аукцион": [
        ("auction_min_bid_step", "📈 Мин. шаг ставки"),
        ("auction_commission", "💸 Комиссия аукциона (%)"),
        ("auction_notify_chats", "📢 Уведомлять о торгах (1/0)"),
    ],
    "⚙️ Бой в чатах": [
        ("fight_cooldown_minutes", "⏳ Кулдаун боя (минуты)"),
        ("fight_base_damage", "💥 База урона"),
        ("fight_damage_variance", "🎲 Вариация урона"),
        ("fight_authority_min", "⬇️ Мин. авторитет за бой"),
        ("fight_authority_max", "⬆️ Макс. авторитет за бой"),
        ("fight_bitcoin_reward", "₿ BTC за бой"),
    ],
    "⚙️ Качалка (авторитет)": [
        ("gym_strength_cost", "💪 Стоимость силы"),
        ("gym_agility_cost", "🏃 Стоимость ловкости"),
        ("gym_defense_cost", "🛡 Стоимость защиты"),
    ],
    "⚙️ Бизнесы": [
        ("business_upgrade_cost_per_level", "📈 База стоимости улучшения"),
    ],
    "⚙️ Контрабанда": [
        ("smuggle_min_duration", "⏳ Мин. длительность (минуты)"),
        ("smuggle_max_duration", "⏳ Макс. длительность (минуты)"),
        ("smuggle_success_chance", "✅ Шанс успеха (%)"),
        ("smuggle_caught_chance", "🚨 Шанс попасться (%)"),
        ("smuggle_lost_chance", "💥 Шанс потерять груз (%)"),
        ("smuggle_base_amount", "₿ База BTC"),
        ("smuggle_authority_multiplier", "⚔️ Множитель авторитета"),
        ("smuggle_cooldown_minutes", "⏳ Базовый кулдаун (минуты)"),
        ("smuggle_fail_penalty_minutes", "💔 Штраф при провале (минуты)"),
    ],
    "⚙️ Биткоины": [
        ("bitcoin_per_theft", "🔫 BTC за кражу"),
        ("bitcoin_per_fight", "⚔️ BTC за бой"),
        ("bitcoin_per_casino_win", "🎰 BTC за победу в казино"),
        ("bitcoin_per_slots_win", "🍒 BTC за победу в слотах"),
        ("bitcoin_per_roulette_win", "🎡 BTC за победу в рулетке"),
        ("bitcoin_per_dice_win", "🎲 BTC за победу в кости"),
        ("bitcoin_per_guess_win", "🔢 BTC за победу в угадайке"),
        ("bitcoin_per_boss_participation", "👾 BTC за участие в боссе"),
    ],
    "⚙️ Биткоин-биржа": [
        ("exchange_min_price", "⬇️ Мин. цена BTC"),
        ("exchange_max_price", "⬆️ Макс. цена BTC (0 - без лимита)"),
        ("exchange_commission_percent", "💸 Комиссия биржи (%)"),
        ("exchange_commission_side", "🔁 Сторона комиссии (buyer/seller/both)"),
        ("exchange_commission_destination", "📍 Куда идет комиссия (burn/balance)"),
        ("exchange_min_amount_btc", "⬇️ Мин. сумма заявки (BTC)"),
    ],
    "⚙️ Очистка логов": [
        ("cleanup_days_fight_logs", "⚔️ Хранить логи боев (дней)"),
        ("cleanup_days_bosses", "👾 Хранить боссов (дней)"),
        ("cleanup_days_auctions", "🏷 Хранить аукционы (дней)"),
        ("cleanup_days_purchases", "🛒 Хранить покупки (дней)"),
        ("cleanup_days_giveaways", "🎁 Хранить розыгрыши (дней)"),
        ("cleanup_days_user_tasks", "📋 Хранить задания (дней)"),
        ("cleanup_days_smuggle", "📦 Хранить контрабанду (дней)"),
        ("cleanup_days_bitcoin_orders", "₿ Хранить заявки (дней)"),
    ],
    "⚙️ Автоудаление": [
        ("auto_delete_commands_seconds", "⏳ Автоудаление команд (секунд)"),
    ],
    "⚙️ Стартовый бонус": [
        ("new_user_bonus", "🎁 Стартовый бонус"),
    ],
    "⚙️ Глобальный кулдаун": [
        ("global_cooldown_seconds", "🌐 Глобальный кулдаун (секунд)"),
    ],
    "⚙️ Лимиты ввода": [
        ("max_input_number", "🔢 Максимальная сумма ввода"),
    ],
}

# ==================== ГЛАВНОЕ МЕНЮ АДМИНКИ ====================
@dp.message_handler(lambda message: message.text == "⚙️ Админ панель")
async def admin_panel(message: types.Message):
    if message.chat.type != 'private':
        return
    if not await is_admin(message.from_user.id):
        await message.answer("У тебя нет прав администратора.")
        return
    permissions = await get_admin_permissions(message.from_user.id)
    await send_with_media(message.chat.id, "Панель администратора:", media_key='admin', reply_markup=admin_main_keyboard(permissions))

@dp.message_handler(lambda message: message.text == "◀️ Назад в админку")
async def back_to_admin(message: types.Message):
    if message.chat.type != 'private':
        return
    if not await is_admin(message.from_user.id):
        return
    permissions = await get_admin_permissions(message.from_user.id)
    await send_with_media(message.chat.id, "Панель администратора:", media_key='admin', reply_markup=admin_main_keyboard(permissions))

# ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================
@dp.message_handler(lambda message: message.text == "👥 Пользователи")
async def admin_users_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление пользователями:", media_key='admin_users', reply_markup=admin_users_keyboard())

@dp.message_handler(lambda message: message.text == "💰 Начислить баксы")
async def add_balance_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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
    await message.answer("Введи сумму начисления (можно дробную, например 10.50):")
    await AddBalance.amount.set()

@dp.message_handler(state=AddBalance.amount)
async def add_balance_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
        max_input = await get_setting_float("max_input_number")
        if amount > max_input:
            await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
            return
    except ValueError:
        await message.answer("❌ Введи положительное число с точностью до сотых.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_balance(uid, amount)
        await message.answer(f"✅ Пользователю {uid} начислено {amount:.2f} баксов.")
        await safe_send_message(uid, f"💰 Вам начислено {amount:.2f} баксов администратором.")
    except Exception as e:
        logging.error(f"Add balance error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "💸 Списать баксы")
async def remove_balance_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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
    await message.answer("Введи сумму списания (можно дробную):")
    await RemoveBalance.amount.set()

@dp.message_handler(state=RemoveBalance.amount)
async def remove_balance_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 2)
        max_input = await get_setting_float("max_input_number")
        if amount > max_input:
            await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
            return
    except ValueError:
        await message.answer("❌ Введи положительное число.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_balance(uid, -amount)
        await message.answer(f"✅ У пользователя {uid} списано {amount:.2f} баксов.")
        await safe_send_message(uid, f"💸 У вас списано {amount:.2f} баксов администратором.")
    except Exception as e:
        logging.error(f"Remove balance error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "⭐️ Начислить репутацию")
async def add_reputation_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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

@dp.message_handler(lambda message: message.text == "₿ Начислить биткоины")
async def add_bitcoin_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await AddBitcoin.user_id.set()

@dp.message_handler(state=AddBitcoin.user_id)
async def add_bitcoin_user(message: types.Message, state: FSMContext):
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
    await message.answer("Введи количество биткоинов (можно дробное, например 1.5):")
    await AddBitcoin.amount.set()

@dp.message_handler(state=AddBitcoin.amount)
async def add_bitcoin_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 4)
        max_input = await get_setting_float("max_input_number")
        if amount > max_input:
            await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.4f}).")
            return
    except ValueError:
        await message.answer("❌ Введи положительное число (можно дробное).")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_bitcoin(uid, amount)
        await message.answer(f"✅ Пользователю {uid} начислено {amount:.4f} BTC.")
        await safe_send_message(uid, f"₿ Вам начислено {amount:.4f} BTC администратором.")
    except Exception as e:
        logging.error(f"Add bitcoin error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "₿ Списать биткоины")
async def remove_bitcoin_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await RemoveBitcoin.user_id.set()

@dp.message_handler(state=RemoveBitcoin.user_id)
async def remove_bitcoin_user(message: types.Message, state: FSMContext):
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
    await message.answer("Введи количество биткоинов для списания:")
    await RemoveBitcoin.amount.set()

@dp.message_handler(state=RemoveBitcoin.amount)
async def remove_bitcoin_amount(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_users_menu(message)
        return
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        amount = round(amount, 4)
        max_input = await get_setting_float("max_input_number")
        if amount > max_input:
            await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.4f}).")
            return
    except ValueError:
        await message.answer("❌ Введи положительное число.")
        return
    data = await state.get_data()
    uid = data['user_id']
    try:
        await update_user_bitcoin(uid, -amount)
        await message.answer(f"✅ У пользователя {uid} списано {amount:.4f} BTC.")
        await safe_send_message(uid, f"₿ У вас списано {amount:.4f} BTC администратором.")
    except Exception as e:
        logging.error(f"Remove bitcoin error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "⚔️ Начислить авторитет")
async def add_authority_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await AddAuthority.user_id.set()

@dp.message_handler(state=AddAuthority.user_id)
async def add_authority_user(message: types.Message, state: FSMContext):
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
    await message.answer("Введи количество авторитета (целое число):")
    await AddAuthority.amount.set()

@dp.message_handler(state=AddAuthority.amount)
async def add_authority_amount(message: types.Message, state: FSMContext):
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
        await update_user_authority(uid, amount)
        await message.answer(f"✅ Пользователю {uid} начислено {amount} авторитета.")
        await safe_send_message(uid, f"⚔️ Вам начислено {amount} авторитета администратором.")
    except Exception as e:
        logging.error(f"Add authority error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "⚔️ Списать авторитет")
async def remove_authority_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
        await message.answer("❌ Недостаточно прав.")
        return
    await message.answer("Введи ID или @username пользователя:", reply_markup=back_keyboard())
    await RemoveAuthority.user_id.set()

@dp.message_handler(state=RemoveAuthority.user_id)
async def remove_authority_user(message: types.Message, state: FSMContext):
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
    await message.answer("Введи количество авторитета для снятия:")
    await RemoveAuthority.amount.set()

@dp.message_handler(state=RemoveAuthority.amount)
async def remove_authority_amount(message: types.Message, state: FSMContext):
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
        await update_user_authority(uid, -amount)
        await message.answer(f"✅ У пользователя {uid} снято {amount} авторитета.")
        await safe_send_message(uid, f"⚔️ У вас снято {amount} авторитета администратором.")
    except Exception as e:
        logging.error(f"Remove authority error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "👥 Найти пользователя")
async def find_user_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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
    bal = float(user_data['balance'])
    rep = user_data['reputation']
    spent = float(user_data['total_spent'])
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
    bitcoin = float(user_data['bitcoin_balance']) if user_data['bitcoin_balance'] is not None else 0.0
    authority = user_data['authority_balance'] or 0
    smuggle_success = user_data.get('smuggle_success', 0)
    smuggle_fail = user_data.get('smuggle_fail', 0)
    banned = await is_banned(uid)
    ban_status = "⛔ Заблокирован" if banned else "✅ Активен"
    text = (
        f"👤 Пользователь: {name} (ID: {uid})\n"
        f"📊 Уровень: {level}, опыт: {exp}\n"
        f"💪 Сила: {strength} | 🏃 Ловкость: {agility} | 🛡 Защита: {defense}\n"
        f"💰 Баланс: {bal:.2f} баксов\n"
        f"₿ Биткоины: {bitcoin:.4f} BTC\n"
        f"⚔️ Авторитет: {authority}\n"
        f"⭐️ Репутация: {rep}\n"
        f"💸 Потрачено: {spent:.2f} баксов\n"
        f"📅 Регистрация: {joined}\n"
        f"🔫 Ограблений: {attempts} (успешно: {success}, провал: {failed})\n"
        f"🛡 Отбито атак: {protected}\n"
        f"📦 Контрабанда: успешно {smuggle_success}, провал {smuggle_fail}\n"
        f"Статус: {ban_status}"
    )
    await message.answer(text)
    await state.finish()

@dp.message_handler(lambda message: message.text == "📊 Экспорт пользователей")
async def export_users(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_users"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_shop"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление магазином:", media_key='admin_shop', reply_markup=admin_shop_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить товар")
async def add_shop_item_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_shop"):
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
    await message.answer("Введи цену (можно дробную):")
    await AddShopItem.next()

@dp.message_handler(state=AddShopItem.price)
async def add_shop_item_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_shop_menu(message)
        return
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        price = round(price, 2)
        max_input = await get_setting_float("max_input_number")
        if price > max_input:
            await message.answer(f"❌ Цена слишком большая (максимум {max_input:.2f}).")
            return
    except ValueError:
        await message.answer("❌ Цена должна быть положительным числом (можно дробным).")
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
    if not await check_admin_permissions(message.from_user.id, "manage_shop"):
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

@dp.message_handler(lambda message: message.text == "✏️ Редактировать товар")
async def edit_shop_item_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_shop"):
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
    await message.answer("Что хочешь изменить? (price/stock)")
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
        data = await state.get_data()
        if data['field'] == 'price':
            value = float(message.text)
            if value <= 0:
                raise ValueError
            value = round(value, 2)
            max_input = await get_setting_float("max_input_number")
            if value > max_input:
                await message.answer(f"❌ Цена слишком большая (максимум {max_input:.2f}).")
                return
        else:
            value = int(message.text)
    except ValueError:
        await message.answer("❌ Введи корректное число.")
        return
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

@dp.message_handler(lambda message: message.text == "📋 Список товаров")
async def list_shop_items(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_shop"):
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
            text += f"\nID {item['id']} | {item['name']}\n{item['description']}\n💰 {float(item['price']):.2f} | наличие: {item['stock'] if item['stock']!=-1 else '∞'}\n"
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

@dp.message_handler(lambda message: message.text == "🛍️ Список покупок")
async def admin_purchases(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_shop"):
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
    if not await check_admin_permissions(callback.from_user.id, "manage_shop"):
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
    if not await check_admin_permissions(callback.from_user.id, "manage_shop"):
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

# ==================== УПРАВЛЕНИЕ КАНАЛАМИ ====================
@dp.message_handler(lambda message: message.text == "📢 Каналы")
async def admin_channel_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_channels"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление каналами:", media_key='admin_channels', reply_markup=admin_channel_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить канал")
async def add_channel_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_channels"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_channels"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_channels"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_promocodes"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление промокодами:", media_key='admin_promo', reply_markup=admin_promo_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать промокод")
async def create_promo_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_promocodes"):
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
    await message.answer("Введи количество баксов, которые даёт промокод (можно дробно):")
    await CreatePromocode.next()

@dp.message_handler(state=CreatePromocode.reward)
async def create_promo_reward(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_promo_menu(message)
        return
    try:
        reward = float(message.text)
        if reward <= 0:
            raise ValueError
        reward = round(reward, 2)
        max_input = await get_setting_float("max_input_number")
        if reward > max_input:
            await message.answer(f"❌ Сумма слишком большая (максимум {max_input:.2f}).")
            return
    except ValueError:
        await message.answer("❌ Введи положительное число (можно дробное).")
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
    if not await check_admin_permissions(message.from_user.id, "manage_promocodes"):
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
            text += f"• {row['code']}: {float(row['reward']):.2f} баксов, использовано {row['used_count']}/{row['max_uses']}\n"
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

# ==================== УПРАВЛЕНИЕ БЛОКИРОВКАМИ ====================
@dp.message_handler(lambda message: message.text == "🔨 Блокировки")
async def admin_ban_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_bans"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление блокировками:", media_key='admin_ban', reply_markup=admin_ban_keyboard())

@dp.message_handler(lambda message: message.text == "🔨 Заблокировать пользователя")
async def block_user_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_bans"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_bans"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_bans"):
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
@dp.message_handler(lambda message: message.text == "➕ Админы")
async def admin_admins_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_admins"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление админами:", media_key='admin_admins', reply_markup=admin_admins_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить админа")
async def add_admin_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_admins"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_admins"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_admins"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_admins"):
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

# ==================== УПРАВЛЕНИЕ ЧАТАМИ ====================
@dp.message_handler(lambda message: message.text == "🤖 Чаты")
async def admin_chats_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_chats"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление чатами:", media_key='admin_chats', reply_markup=admin_chats_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Список запросов на подтверждение")
async def list_pending_requests(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_chats"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_chats"):
        return
    await message.answer("Введи ID чата, который хочешь подтвердить:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    await state.update_data(action="confirm")

@dp.message_handler(lambda message: message.text == "❌ Отклонить запрос")
async def reject_chat_manual(message: types.Message, state: FSMContext):
    if not await check_admin_permissions(message.from_user.id, "manage_chats"):
        return
    await message.answer("Введи ID чата, запрос которого хочешь отклонить:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    await state.update_data(action="reject")

@dp.message_handler(lambda message: message.text == "🗑 Удалить чат из подтверждённых")
async def remove_confirmed_chat_start(message: types.Message, state: FSMContext):
    if not await check_admin_permissions(message.from_user.id, "manage_chats"):
        return
    await message.answer("Введи ID чата, который нужно удалить из подтверждённых:", reply_markup=back_keyboard())
    await ManageChats.chat_id.set()
    await state.update_data(action="remove")

@dp.message_handler(lambda message: message.text == "📋 Список подтверждённых чатов")
async def list_confirmed_chats(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_chats"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_bosses"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление боссами:", media_key='admin_boss', reply_markup=admin_boss_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Активные боссы")
async def list_active_bosses(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_bosses"):
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
    if not await check_admin_permissions(callback.from_user.id, "manage_bosses"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_bosses"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_bosses"):
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

# ==================== УПРАВЛЕНИЕ АУКЦИОНАМИ (админские функции) ====================
@dp.message_handler(lambda message: message.text == "🏷 Аукцион")
async def admin_auction_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_auctions"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление аукционами:", media_key='admin_auction', reply_markup=admin_auction_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать аукцион")
async def create_auction_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_auctions"):
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
    await message.answer("Введи стартовую цену (можно дробную):")
    await CreateAuction.next()

@dp.message_handler(state=CreateAuction.start_price)
async def create_auction_start_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_auction_menu(message)
        return
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        price = round(price, 2)
        max_input = await get_setting_float("max_input_number")
        if price > max_input:
            await message.answer(f"❌ Цена слишком большая (максимум {max_input:.2f}).")
            return
    except:
        await message.answer("❌ Введи положительное число (можно дробное).")
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
            end_time = datetime.now() + timedelta(hours=hours)
        except:
            await message.answer("❌ Введи целое положительное число часов или 'нет'.")
            return
    await state.update_data(end_time=end_time)
    await message.answer("Введи целевую цену (число) или 'нет', если не нужна:")
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
            target_price = float(message.text)
            if target_price <= 0:
                raise ValueError
            target_price = round(target_price, 2)
            max_input = await get_setting_float("max_input_number")
            if target_price > max_input:
                await message.answer(f"❌ Цена слишком большая (максимум {max_input:.2f}).")
                return
        except:
            await message.answer("❌ Введи положительное число или 'нет'.")
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
    if not await check_admin_permissions(message.from_user.id, "manage_auctions"):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM auctions WHERE status='active' ORDER BY created_at")
    if not rows:
        await message.answer("Нет активных аукционов.")
        return
    text = "Активные аукционы:\n"
    for row in rows:
        text += f"ID {row['id']}: {row['item_name']} | Текущая цена: {float(row['current_price']):.2f} | Создатель: {row['created_by']}\n"
    await message.answer(text)

@dp.message_handler(lambda message: message.text == "❌ Отменить аукцион")
async def cancel_auction_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_auctions"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_ads"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление рекламой:", media_key='admin_ad', reply_markup=admin_ad_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Создать рекламу")
async def create_ad_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_ads"):
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
    if not await check_admin_permissions(message.from_user.id, "manage_ads"):
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

@dp.message_handler(lambda message: message.text == "✏️ Редактировать рекламу")
async def edit_ad_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_ads"):
        return
    await message.answer("Введи ID рекламы для редактирования:", reply_markup=back_keyboard())
    await EditAd.ad_id.set()

@dp.message_handler(state=EditAd.ad_id)
async def edit_ad_id(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ad_menu(message)
        return
    try:
        ad_id = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    async with db_pool.acquire() as conn:
        ad = await conn.fetchrow("SELECT * FROM ads WHERE id=$1", ad_id)
        if not ad:
            await message.answer("❌ Реклама не найдена.")
            await state.finish()
            return
    await state.update_data(ad_id=ad_id)
    await message.answer("Что хочешь изменить? (text/interval/target/enabled)")
    await EditAd.field.set()

@dp.message_handler(state=EditAd.field)
async def edit_ad_field(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ad_menu(message)
        return
    field = message.text.lower()
    allowed = ['text', 'interval', 'target', 'enabled']
    if field not in allowed:
        await message.answer(f"❌ Можно изменить только: {', '.join(allowed)}")
        return
    await state.update_data(field=field)
    if field == 'enabled':
        await message.answer("Введи новое значение (True/False):")
    elif field == 'interval':
        await message.answer("Введи новый интервал (минуты):")
    else:
        await message.answer(f"Введи новое значение для {field}:")
    await EditAd.value.set()

@dp.message_handler(state=EditAd.value)
async def edit_ad_value(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ad_menu(message)
        return
    data = await state.get_data()
    ad_id = data['ad_id']
    field = data['field']

    if field == 'enabled':
        val = message.text.lower() in ['true', '1', 'да', 'yes']
    elif field == 'interval':
        try:
            val = int(message.text)
            if val <= 0:
                raise ValueError
        except:
            await message.answer("❌ Введи целое положительное число.")
            return
    else:
        val = message.text

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(f"UPDATE ads SET {field}=$1 WHERE id=$2", val, ad_id)
        await message.answer("✅ Реклама обновлена.", reply_markup=admin_ad_keyboard())
    except Exception as e:
        logging.error(f"Edit ad error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "❌ Удалить рекламу")
async def delete_ad_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_ads"):
        return
    await message.answer("Введи ID рекламы для удаления:", reply_markup=back_keyboard())
    await DeleteAd.ad_id.set()

@dp.message_handler(state=DeleteAd.ad_id)
async def delete_ad_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_ad_menu(message)
        return
    try:
        ad_id = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM ads WHERE id=$1", ad_id)
    await message.answer("✅ Реклама удалена, если существовала.", reply_markup=admin_ad_keyboard())
    await state.finish()

# ==================== УПРАВЛЕНИЕ БИРЖЕЙ ====================
@dp.message_handler(lambda message: message.text == "💼 Биржа")
async def admin_exchange_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_exchange"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление биткоин-биржей:", media_key='admin_exchange', reply_markup=admin_exchange_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Активные заявки")
async def admin_list_orders(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_exchange"):
        return
    orders = await get_active_orders()
    if not orders:
        await message.answer("Нет активных заявок.")
        return
    text = "📋 Активные заявки:\n\n"
    for o in orders:
        text += f"ID {o['id']}: {'📈' if o['type']=='buy' else '📉'} {o['amount']:.4f} BTC @ {o['price']} $ (пользователь {o['user_id']})\n"
    await message.answer(text, reply_markup=admin_exchange_keyboard())

@dp.message_handler(lambda message: message.text == "❌ Удалить заявку (по ID)")
async def admin_remove_order_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_exchange"):
        return
    await message.answer("Введи ID заявки для удаления:", reply_markup=back_keyboard())
    await CancelBitcoinOrder.order_id.set()

@dp.message_handler(state=CancelBitcoinOrder.order_id)
async def admin_remove_order_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_exchange_menu(message)
        return
    try:
        order_id = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow("SELECT * FROM bitcoin_orders WHERE id=$1 AND status='active'", order_id)
            if not order:
                await message.answer("❌ Заявка не найдена или уже не активна.")
                await state.finish()
                return
            total_locked = float(order['total_locked'])
            if order['type'] == 'sell':
                await update_user_bitcoin(order['user_id'], total_locked, conn=conn)
            else:
                await update_user_balance(order['user_id'], total_locked, conn=conn)
            await conn.execute("UPDATE bitcoin_orders SET status='cancelled' WHERE id=$1", order_id)
    await message.answer(f"✅ Заявка {order_id} отменена, средства возвращены пользователю.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📊 История сделок")
async def admin_trade_history(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_exchange"):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM bitcoin_trades ORDER BY traded_at DESC LIMIT 50")
    if not rows:
        await message.answer("Нет сделок.")
        return
    text = "📊 Последние сделки:\n\n"
    for r in rows:
        text += f"ID {r['id']}: {float(r['amount']):.4f} BTC @ {r['price']} $ (покупатель {r['buyer_id']}, продавец {r['seller_id']}) в {r['traded_at'].strftime('%Y-%m-%d %H:%M')}\n"
    await message.answer(text, reply_markup=admin_exchange_keyboard())

# ==================== УПРАВЛЕНИЕ БИЗНЕСАМИ ====================
@dp.message_handler(lambda message: message.text == "🏪 Бизнесы")
async def admin_business_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_businesses"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление бизнесами:", media_key='admin_business', reply_markup=admin_business_keyboard())

@dp.message_handler(lambda message: message.text == "📋 Список бизнесов")
async def admin_list_businesses(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_businesses"):
        return
    types = await get_business_type_list(only_available=False)
    if not types:
        await message.answer("Нет типов бизнесов.")
        return
    text = "🏪 Типы бизнесов:\n\n"
    for bt in types:
        available = "✅" if bt['available'] else "❌"
        text += f"{available} ID {bt['id']}: {bt['emoji']} {bt['name']}\n"
        text += f"  Цена: {bt['base_price_btc']:.2f} BTC, доход: {bt['base_income_cents']} центов/час\n"
        text += f"  Описание: {bt['description']}\n"
        text += f"  Макс. уровень: {bt['max_level']}\n\n"
    await message.answer(text, reply_markup=admin_business_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить бизнес")
async def add_business_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_businesses"):
        return
    await message.answer("Введи название бизнеса (например, 'Супермаркет'):", reply_markup=back_keyboard())
    await AddBusiness.name.set()

@dp.message_handler(state=AddBusiness.name)
async def add_business_name(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    await state.update_data(name=message.text)
    await message.answer("Введи эмодзи для бизнеса (один символ, например, 🏪):")
    await AddBusiness.next()

@dp.message_handler(state=AddBusiness.emoji)
async def add_business_emoji(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    await state.update_data(emoji=message.text)
    await message.answer("Введи цену в BTC (можно дробную, например 15.50):")
    await AddBusiness.next()

@dp.message_handler(state=AddBusiness.price)
async def add_business_price(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        price = round(price, 2)
        max_input = await get_setting_float("max_input_number")
        if price > max_input:
            await message.answer(f"❌ Цена слишком большая (максимум {max_input:.2f}).")
            return
    except:
        await message.answer("❌ Введи положительное число (можно дробное).")
        return
    await state.update_data(price=price)
    await message.answer("Введи базовый доход в центах в час (целое число, например 120):")
    await AddBusiness.next()

@dp.message_handler(state=AddBusiness.income)
async def add_business_income(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    try:
        income = int(message.text)
        if income <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введи положительное целое число.")
        return
    await state.update_data(income=income)
    await message.answer("Введи описание бизнеса:")
    await AddBusiness.next()

@dp.message_handler(state=AddBusiness.description)
async def add_business_description(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    await state.update_data(description=message.text)
    await message.answer("Введи максимальный уровень прокачки (целое число, например 10):")
    await AddBusiness.next()

@dp.message_handler(state=AddBusiness.max_level)
async def add_business_max_level(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    try:
        max_level = int(message.text)
        if max_level < 1:
            raise ValueError
    except:
        await message.answer("❌ Введи положительное целое число.")
        return
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO business_types (name, emoji, base_price_btc, base_income_cents, description, max_level, available) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                data['name'], data['emoji'], data['price'], data['income'], data['description'], max_level, True
            )
        await message.answer("✅ Бизнес успешно добавлен!", reply_markup=admin_business_keyboard())
    except asyncpg.UniqueViolationError:
        await message.answer("❌ Бизнес с таким названием уже существует.")
    except Exception as e:
        logging.error(f"Add business error: {e}")
        await message.answer("❌ Ошибка при добавлении бизнеса.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "✏️ Редактировать бизнес")
async def edit_business_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_businesses"):
        return
    await message.answer("Введи ID бизнеса для редактирования:", reply_markup=back_keyboard())
    await EditBusiness.business_id.set()

@dp.message_handler(state=EditBusiness.business_id)
async def edit_business_id(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    try:
        bid = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    biz = await get_business_type(bid)
    if not biz:
        await message.answer("❌ Бизнес с таким ID не найден.")
        return
    await state.update_data(business_id=bid)
    await message.answer("Что хочешь изменить? (name/emoji/price/income/description/max_level/available)")
    await EditBusiness.field.set()

@dp.message_handler(state=EditBusiness.field)
async def edit_business_field(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    field = message.text.lower()
    allowed = ['name', 'emoji', 'price', 'income', 'description', 'max_level', 'available']
    if field not in allowed:
        await message.answer(f"❌ Можно изменить только: {', '.join(allowed)}")
        return
    await state.update_data(field=field)
    if field == 'available':
        await message.answer("Введи новое значение (True/False):")
    elif field == 'price':
        await message.answer("Введи новую цену в BTC (дробное число):")
    elif field == 'income':
        await message.answer("Введи новый базовый доход в центах/час (целое число):")
    elif field == 'max_level':
        await message.answer("Введи новый максимальный уровень (целое число):")
    else:
        await message.answer(f"Введи новое значение для {field}:")
    await EditBusiness.value.set()

@dp.message_handler(state=EditBusiness.value)
async def edit_business_value(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    data = await state.get_data()
    bid = data['business_id']
    field = data['field']

    if field == 'available':
        val = message.text.lower() in ['true', '1', 'да', 'yes']
    elif field == 'price':
        try:
            val = float(message.text)
            if val <= 0:
                raise ValueError
            val = round(val, 2)
            max_input = await get_setting_float("max_input_number")
            if val > max_input:
                await message.answer(f"❌ Цена слишком большая (максимум {max_input:.2f}).")
                return
        except:
            await message.answer("❌ Введи положительное число.")
            return
    elif field in ['income', 'max_level']:
        try:
            val = int(message.text)
            if val <= 0:
                raise ValueError
        except:
            await message.answer("❌ Введи положительное целое число.")
            return
    else:
        val = message.text

    try:
        async with db_pool.acquire() as conn:
            column_map = {
                'name': 'name',
                'emoji': 'emoji',
                'price': 'base_price_btc',
                'income': 'base_income_cents',
                'description': 'description',
                'max_level': 'max_level',
                'available': 'available'
            }
            db_column = column_map[field]
            await conn.execute(f"UPDATE business_types SET {db_column}=$1 WHERE id=$2", val, bid)
        await message.answer(f"✅ Поле {field} обновлено.", reply_markup=admin_business_keyboard())
    except Exception as e:
        logging.error(f"Edit business error: {e}")
        await message.answer("❌ Ошибка при обновлении.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "🔄 Переключить доступность")
async def toggle_business_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_businesses"):
        return
    await message.answer("Введи ID бизнеса, доступность которого нужно переключить:", reply_markup=back_keyboard())
    await ToggleBusiness.business_id.set()

@dp.message_handler(state=ToggleBusiness.business_id)
async def toggle_business_confirm(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    try:
        bid = int(message.text)
    except:
        await message.answer("❌ Введи число.")
        return
    biz = await get_business_type(bid)
    if not biz:
        await message.answer("❌ Бизнес не найден.")
        await state.finish()
        return
    current = biz['available']
    new_status = not current
    await state.update_data(business_id=bid, new_status=new_status)
    await message.answer(f"Текущий статус: {'✅ доступен' if current else '❌ недоступен'}. Переключить на {'❌ недоступен' if current else '✅ доступен'}? (да/нет)")
    await ToggleBusiness.confirm.set()

@dp.message_handler(state=ToggleBusiness.confirm)
async def toggle_business_finish(message: types.Message, state: FSMContext):
    if message.text.lower() == 'нет' or message.text == "◀️ Назад":
        await state.finish()
        await admin_business_menu(message)
        return
    if message.text.lower() == 'да':
        data = await state.get_data()
        bid = data['business_id']
        new_status = data['new_status']
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("UPDATE business_types SET available=$1 WHERE id=$2", new_status, bid)
            await message.answer(f"✅ Доступность бизнеса изменена на {'✅ доступен' if new_status else '❌ недоступен'}.", reply_markup=admin_business_keyboard())
        except Exception as e:
            logging.error(f"Toggle business error: {e}")
            await message.answer("❌ Ошибка.")
        await state.finish()
    else:
        await message.answer("Введи 'да' или 'нет'.")

# ==================== УПРАВЛЕНИЕ МЕДИА ====================
@dp.message_handler(lambda message: message.text == "🖼 Медиа")
async def admin_media_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_media"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Управление медиафайлами:", media_key='admin_media', reply_markup=admin_media_keyboard())

@dp.message_handler(lambda message: message.text == "➕ Добавить медиа")
async def add_media_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_media"):
        return
    await message.answer("Введи ключ (например, 'profile', 'casino', 'welcome'):", reply_markup=back_keyboard())
    await AddMedia.key.set()

@dp.message_handler(state=AddMedia.key)
async def add_media_key(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_media_menu(message)
        return
    key = message.text.strip()
    await state.update_data(key=key)
    await message.answer("Отправь фото (или документ/видео):")
    await AddMedia.file.set()

@dp.message_handler(state=AddMedia.file, content_types=['photo', 'document', 'video'])
async def add_media_file(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_media_menu(message)
        return
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    else:
        await message.answer("❌ Отправь фото, документ или видео.")
        return
    data = await state.get_data()
    key = data['key']
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO media (key, file_id, description) VALUES ($1, $2, $3) ON CONFLICT (key) DO UPDATE SET file_id=$2",
                key, file_id, f"Медиа для {key}"
            )
        await message.answer(f"✅ Медиа с ключом '{key}' сохранено.")
    except Exception as e:
        logging.error(f"Add media error: {e}")
        await message.answer("❌ Ошибка сохранения.")
    await state.finish()
    await admin_media_menu(message)

@dp.message_handler(lambda message: message.text == "➖ Удалить медиа")
async def remove_media_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_media"):
        return
    await message.answer("Введи ключ медиа для удаления:", reply_markup=back_keyboard())
    await RemoveMedia.key.set()

@dp.message_handler(state=RemoveMedia.key)
async def remove_media_finish(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await admin_media_menu(message)
        return
    key = message.text.strip()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM media WHERE key=$1", key)
        await message.answer(f"✅ Медиа с ключом '{key}' удалено, если существовало.")
    except Exception as e:
        logging.error(f"Remove media error: {e}")
        await message.answer("❌ Ошибка.")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Список медиа")
async def list_media(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "manage_media"):
        return
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, description FROM media ORDER BY key")
    if not rows:
        await message.answer("Нет сохранённых медиа.")
        return
    text = "🖼 Сохранённые медиа:\n\n"
    for row in rows:
        text += f"• {row['key']}: {row['description']}\n"
    await message.answer(text, reply_markup=admin_media_keyboard())

# ==================== НАСТРОЙКИ ИГРЫ ====================

@dp.message_handler(lambda message: message.text == "⚙️ Настройки")
async def settings_menu(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "edit_settings"):
        await message.answer("❌ Недостаточно прав.")
        return
    await send_with_media(message.chat.id, "Выбери категорию настроек:", media_key='admin_settings', reply_markup=settings_categories_keyboard())

@dp.message_handler(lambda message: message.text in SETTINGS_CATEGORIES.keys())
async def settings_category_handler(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "edit_settings"):
        await message.answer("❌ Недостаточно прав.")
        return
    
    category = message.text
    params = SETTINGS_CATEGORIES.get(category, [])
    
    text = f"<b>{category}</b>\n\n"
    kb_params = []
    for key, desc in params:
        value = await get_setting(key)
        text += f"{desc}: <code>{value}</code>\n"
        kb_params.append((key, desc))
    
    kb = settings_param_keyboard(kb_params, category)
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("settings_back_"))
async def settings_back_callback(callback: types.CallbackQuery):
    category = callback.data.split("_", 2)[2]
    await callback.message.delete()
    await settings_menu(callback.message)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("edit_"))
async def edit_setting_start(callback: types.CallbackQuery, state: FSMContext):
    if not await check_admin_permissions(callback.from_user.id, "edit_settings"):
        await callback.answer("❌ Недостаточно прав.", show_alert=True)
        return
    
    key = callback.data[5:]
    current_value = await get_setting(key)
    
    await state.update_data(key=key)
    await callback.message.answer(
        f"⚙️ Редактирование <b>{key}</b>\n"
        f"Текущее значение: <code>{current_value}</code>\n\n"
        f"Введи новое значение:",
        reply_markup=back_keyboard()
    )
    await EditSettings.key.set()
    await callback.answer()

@dp.message_handler(state=EditSettings.key)
async def edit_setting_value(message: types.Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.finish()
        await settings_menu(message)
        return
    
    data = await state.get_data()
    key = data['key']
    new_value = message.text.strip()
    
    try:
        await set_setting(key, new_value)
        await message.answer(f"✅ Настройка <b>{key}</b> обновлена!\nНовое значение: <code>{new_value}</code>")
    except Exception as e:
        logging.error(f"Error setting {key}: {e}")
        await message.answer("❌ Ошибка при сохранении настройки.")
    
    await state.finish()
    await settings_menu(message)

# ==================== СТАТИСТИКА ====================
@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def stats_handler(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "view_stats"):
        await message.answer("❌ Недостаточно прав.")
        return
    try:
        async with db_pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_balance = await conn.fetchval("SELECT SUM(balance) FROM users") or 0.0
            total_reputation = await conn.fetchval("SELECT SUM(reputation) FROM users") or 0
            total_spent = await conn.fetchval("SELECT SUM(total_spent) FROM users") or 0.0
            total_bitcoin = await conn.fetchval("SELECT SUM(bitcoin_balance) FROM users") or 0.0
            active_giveaways = await conn.fetchval("SELECT COUNT(*) FROM giveaways WHERE status='active'") or 0
            shop_items = await conn.fetchval("SELECT COUNT(*) FROM shop_items") or 0
            purchases_pending = await conn.fetchval("SELECT COUNT(*) FROM purchases WHERE status='pending'") or 0
            total_thefts = await conn.fetchval("SELECT SUM(theft_attempts) FROM users") or 0
            total_thefts_success = await conn.fetchval("SELECT SUM(theft_success) FROM users") or 0
            promos = await conn.fetchval("SELECT COUNT(*) FROM promocodes") or 0
            banned = await conn.fetchval("SELECT COUNT(*) FROM banned_users") or 0
            total_bosses = await conn.fetchval("SELECT COUNT(*) FROM bosses") or 0
            active_bosses = await conn.fetchval("SELECT COUNT(*) FROM bosses WHERE status='active'") or 0
            confirmed_chats = await conn.fetchval("SELECT COUNT(*) FROM confirmed_chats") or 0
            active_orders = await conn.fetchval("SELECT COUNT(*) FROM bitcoin_orders WHERE status='active'") or 0
            total_businesses = await conn.fetchval("SELECT COUNT(*) FROM user_businesses") or 0
        text = (
            f"📊 <b>Статистика:</b>\n"
            f"👥 Пользователей: {users}\n"
            f"💰 Всего баксов: {float(total_balance):.2f}\n"
            f"₿ Всего биткоинов: {float(total_bitcoin):.4f}\n"
            f"⭐️ Всего репутации: {total_reputation}\n"
            f"💸 Всего потрачено: {float(total_spent):.2f}\n"
            f"🎁 Активных розыгрышей: {active_giveaways}\n"
            f"🛒 Товаров в магазине: {shop_items}\n"
            f"🛍️ Ожидающих покупок: {purchases_pending}\n"
            f"🔫 Всего ограблений: {total_thefts} (успешно: {total_thefts_success})\n"
            f"🎫 Промокодов создано: {promos}\n"
            f"⛔ Заблокировано: {banned}\n"
            f"👾 Всего боссов: {total_bosses} (активных: {active_bosses})\n"
            f"✅ Подтверждённых чатов: {confirmed_chats}\n"
            f"💼 Активных заявок на бирже: {active_orders}\n"
            f"🏪 Всего бизнесов у игроков: {total_businesses}"
        )
        permissions = await get_admin_permissions(message.from_user.id)
        await message.answer(text, reply_markup=admin_main_keyboard(permissions))
    except Exception as e:
        logging.error(f"Stats error: {e}")
        await message.answer("❌ Ошибка получения статистики.")

# ==================== РАССЫЛКА ====================
@dp.message_handler(lambda message: message.text == "📢 Рассылка")
async def broadcast_start(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "broadcast"):
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
@dp.message_handler(lambda message: message.text == "🧹 Очистка")
async def cleanup_old_data(message: types.Message):
    if not await check_admin_permissions(message.from_user.id, "cleanup"):
        return
    await perform_cleanup(manual=True)
    await message.answer("✅ Старые записи очищены согласно настройкам.")

# ==================== КОНЕЦ ЧАСТИ 8 ====================
# ==================== ЧАСТЬ 9: ФОНОВЫЕ ЗАДАЧИ И ЗАПУСК БОТА ====================

# ==================== ФОНОВАЯ ЗАДАЧА: ОБРАБОТКА КОНТРАБАНДНЫХ РЕЙСОВ ====================
async def process_smuggle_runs():
    while True:
        try:
            await asyncio.sleep(30)
            now = datetime.now()
            async with db_pool.acquire() as conn:
                runs = await conn.fetch("""
                    SELECT * FROM smuggle_runs
                    WHERE status = 'in_progress' AND end_time::timestamp <= $1 AND notified = FALSE
                """, now)

                for run in runs:
                    user_id = run['user_id']
                    chat_id = run['chat_id']

                    rep = await get_user_reputation(user_id)

                    success_chance = await get_setting_float("smuggle_success_chance")
                    caught_chance = await get_setting_float("smuggle_caught_chance")
                    lost_chance = await get_setting_float("smuggle_lost_chance")

                    rep_success_bonus = float(await get_setting_float("reputation_smuggle_success_bonus")) * rep
                    max_bonus = await get_setting_float("reputation_max_bonus_percent")
                    rep_success_bonus = min(rep_success_bonus, max_bonus)
                    
                    total_success_chance = min(success_chance + rep_success_bonus, 100)
                    remaining = 100 - total_success_chance
                    if remaining < 0:
                        remaining = 0
                    
                    total_base_catch_lost = caught_chance + lost_chance
                    if total_base_catch_lost > 0:
                        adjusted_caught = int(remaining * caught_chance / total_base_catch_lost)
                        adjusted_lost = remaining - adjusted_caught
                    else:
                        adjusted_caught = 0
                        adjusted_lost = 0

                    rand = random.randint(1, 100)
                    result_text = ""
                    status = ""
                    amount = 0.0
                    penalty = 0

                    if rand <= total_success_chance:
                        base_amount = await get_setting_float("smuggle_base_amount")
                        rep_bonus = float(await get_setting_float("reputation_smuggle_bonus")) * rep
                        amount = base_amount + rep_bonus
                        await update_user_bitcoin(user_id, amount, conn=conn)
                        await conn.execute(
                            "UPDATE users SET smuggle_success = smuggle_success + 1 WHERE user_id = $1",
                            user_id
                        )
                        result_text = get_random_phrase(SMUGGLE_SUCCESS_PHRASES, amount=amount)
                        status = 'completed'
                        penalty = 0
                    elif rand <= total_success_chance + adjusted_caught:
                        penalty = await get_setting_int("smuggle_fail_penalty_minutes")
                        await conn.execute(
                            "UPDATE users SET smuggle_fail = smuggle_fail + 1 WHERE user_id = $1",
                            user_id
                        )
                        result_text = get_random_phrase(SMUGGLE_CAUGHT_PHRASES)
                        status = 'failed'
                    else:
                        await conn.execute(
                            "UPDATE users SET smuggle_fail = smuggle_fail + 1 WHERE user_id = $1",
                            user_id
                        )
                        result_text = get_random_phrase(SMUGGLE_LOST_PHRASES)
                        status = 'failed'
                        penalty = 0

                    await conn.execute(
                        "UPDATE smuggle_runs SET status = $1, notified = TRUE, result = $2, smuggle_amount = $3 WHERE id = $4",
                        status, result_text, amount, run['id']
                    )

                    if chat_id:
                        try:
                            user = await conn.fetchrow("SELECT first_name FROM users WHERE user_id=$1", user_id)
                            name = user['first_name'] if user else f"ID {user_id}"
                            # Отправляем с картинкой, если есть
                            file_id = await get_media_file_id('smuggle_result')
                            if file_id:
                                await bot.send_photo(chat_id, file_id, caption=f"{result_text}\n(для {name})")
                            else:
                                await bot.send_message(chat_id, f"{result_text}\n(для {name})")
                        except:
                            await safe_send_message(user_id, result_text)
                    else:
                        await safe_send_message(user_id, result_text)

                    await set_smuggle_cooldown(user_id, penalty)

                    exp = await get_setting_int("exp_per_smuggle")
                    await add_exp(user_id, exp, conn=conn)

        except Exception as e:
            logging.error(f"Error in process_smuggle_runs: {e}")
            await asyncio.sleep(60)

# ==================== ФОНОВАЯ ЗАДАЧА: ПРОВЕРКА АУКЦИОНОВ ====================
async def check_auctions():
    while True:
        try:
            await asyncio.sleep(60)
            now = datetime.now()
            async with db_pool.acquire() as conn:
                expired = await conn.fetch("""
                    SELECT * FROM auctions
                    WHERE status = 'active' AND end_time IS NOT NULL AND end_time <= $1
                """, now)

                for auction in expired:
                    auction_id = auction['id']
                    winner_bid = await conn.fetchrow("""
                        SELECT user_id, bid_amount FROM auction_bids
                        WHERE auction_id = $1
                        ORDER BY bid_amount DESC, bid_time ASC
                        LIMIT 1
                    """, auction_id)

                    if winner_bid:
                        winner_id = winner_bid['user_id']
                        final_price = float(winner_bid['bid_amount'])
                        await conn.execute(
                            "UPDATE auctions SET status = 'ended', winner_id = $1, current_price = $2 WHERE id = $3",
                            winner_id, final_price, auction_id
                        )
                        await safe_send_message(
                            winner_id,
                            f"🎉 Поздравляем! Вы выиграли аукцион «{auction['item_name']}» с ценой {final_price:.2f} баксов. Админ скоро свяжется."
                        )
                        await safe_send_message(
                            auction['created_by'],
                            f"🏁 Аукцион «{auction['item_name']}» завершён. Победитель: {winner_id}, цена: {final_price:.2f}."
                        )
                    else:
                        await conn.execute(
                            "UPDATE auctions SET status = 'ended', winner_id = NULL WHERE id = $1",
                            auction_id
                        )
                        await safe_send_message(
                            auction['created_by'],
                            f"🏁 Аукцион «{auction['item_name']}» завершён без ставок."
                        )

        except Exception as e:
            logging.error(f"Error in check_auctions: {e}")
            await asyncio.sleep(60)

# ==================== ФОНОВАЯ ЗАДАЧА: СПАВН БОССОВ ====================
async def boss_spawn_scheduler():
    while True:
        try:
            await asyncio.sleep(1800)  # проверка раз в 30 минут
            spawn_chance = await get_setting_int("boss_spawn_chance")
            if random.randint(1, 100) > spawn_chance:
                continue

            async with db_pool.acquire() as conn:
                chat_row = await conn.fetchrow("""
                    SELECT chat_id FROM confirmed_chats 
                    WHERE boss_spawn_count < (SELECT value::int FROM settings WHERE key='boss_max_per_day')
                    ORDER BY RANDOM() LIMIT 1
                """)
                if not chat_row:
                    continue
                chat_id = chat_row['chat_id']

            max_per_day = await get_setting_int("boss_max_per_day")
            today = date.today().isoformat()
            
            async with db_pool.acquire() as conn2:
                chat_data = await conn2.fetchrow(
                    "SELECT boss_last_spawn, boss_spawn_count FROM confirmed_chats WHERE chat_id = $1",
                    chat_id
                )
                if chat_data:
                    last_spawn_str = chat_data['boss_last_spawn']
                    spawn_count = chat_data['boss_spawn_count']
                    
                    if last_spawn_str:
                        try:
                            last_spawn_date = datetime.strptime(last_spawn_str, "%Y-%m-%d %H:%M:%S").date()
                            if last_spawn_date == date.today():
                                if spawn_count >= max_per_day:
                                    continue
                            else:
                                await conn2.execute(
                                    "UPDATE confirmed_chats SET boss_spawn_count = 0 WHERE chat_id = $1",
                                    chat_id
                                )
                        except:
                            pass

                existing = await conn2.fetchval(
                    "SELECT 1 FROM bosses WHERE chat_id = $1 AND status = 'active'",
                    chat_id
                )
                if existing:
                    continue

            # Получаем изображение по умолчанию для босса из медиа
            image_file_id = await get_media_file_id('boss_default')

            level = random.randint(1, 5)
            await spawn_boss(chat_id, level=level, image_file_id=image_file_id)

        except Exception as e:
            logging.error(f"Error in boss_spawn_scheduler: {e}")
            await asyncio.sleep(60)

# ==================== ФОНОВАЯ ЗАДАЧА: РАССЫЛКА РЕКЛАМЫ ====================
async def ad_sender():
    while True:
        try:
            await asyncio.sleep(300)  # проверка раз в 5 минут
            now = datetime.now()
            async with db_pool.acquire() as conn:
                ads = await conn.fetch("SELECT * FROM ads WHERE enabled = TRUE")
                for ad in ads:
                    last_sent = ad['last_sent']
                    interval = ad['interval_minutes']
                    if last_sent:
                        try:
                            if isinstance(last_sent, str):
                                last = datetime.strptime(last_sent, "%Y-%m-%d %H:%M:%S.%f")
                            else:
                                last = last_sent
                            if (now - last).total_seconds() < interval * 60:
                                continue
                        except:
                            pass

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
                        await asyncio.sleep(0.05)

                    await conn.execute(
                        "UPDATE ads SET last_sent = $1 WHERE id = $2",
                        now, ad['id']
                    )
                    logging.info(f"Ad {ad['id']} sent to {sent_count} recipients")

        except Exception as e:
            logging.error(f"Error in ad_sender: {e}")
            await asyncio.sleep(60)

# ==================== ПЕРИОДИЧЕСКАЯ ОЧИСТКА СТАРЫХ ЗАПИСЕЙ ====================
async def periodic_cleanup():
    while True:
        try:
            await asyncio.sleep(86400)  # раз в сутки
            await perform_cleanup(manual=False)
        except Exception as e:
            logging.error(f"Error in periodic_cleanup: {e}")
            await asyncio.sleep(3600)

# ==================== ФОНОВАЯ ЗАДАЧА: АВТОМАТИЧЕСКОЕ НАЧИСЛЕНИЕ ДОХОДА БИЗНЕСОВ ====================
async def update_all_businesses_income():
    while True:
        await asyncio.sleep(3600)  # раз в час
        try:
            async with db_pool.acquire() as conn:
                businesses = await conn.fetch("""
                    SELECT ub.*, bt.base_income_cents 
                    FROM user_businesses ub
                    JOIN business_types bt ON ub.business_type_id = bt.id
                """)
                for biz in businesses:
                    income_per_hour = biz['base_income_cents'] * biz['level']
                    new_accum = biz['accumulated'] + income_per_hour
                    await conn.execute(
                        "UPDATE user_businesses SET accumulated = $1 WHERE id = $2",
                        new_accum, biz['id']
                    )
                logging.info("Автоматическое начисление дохода по бизнесам выполнено.")
        except Exception as e:
            logging.error(f"Ошибка в update_all_businesses_income: {e}")

# ==================== ЗАПУСК БОТА ====================
async def on_startup(dp):
    await bot.set_my_commands([
        types.BotCommand("start", "🚀 Запустить бота"),
        types.BotCommand("help", "📚 Помощь и команды"),
        types.BotCommand("profile", "👤 Мой профиль"),
        types.BotCommand("bonus", "🎁 Ежедневный бонус"),
        types.BotCommand("shop", "🛒 Магазин подарков"),
        types.BotCommand("casino", "🎰 Казино и игры"),
        types.BotCommand("top", "🏆 Топ игроков"),
        types.BotCommand("theft", "🔫 Ограбить"),
        types.BotCommand("tasks", "📋 Задания"),
        types.BotCommand("referral", "🔗 Реферальная ссылка"),
        types.BotCommand("giveaways", "🎁 Розыгрыши"),
        types.BotCommand("auction", "🏷 Аукцион"),
        types.BotCommand("business", "🏪 Мои бизнесы"),
        types.BotCommand("exchange", "💼 Биткоин-биржа"),
        types.BotCommand("cancel", "❌ Отменить действие"),
        types.BotCommand("activate_chat", "🔔 Активировать чат")
    ])
    logging.info("Бот запущен!")

async def on_shutdown(dp):
    await db_pool.close()
    logging.info("Бот остановлен, соединения закрыты.")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_pool())
    loop.run_until_complete(init_db())

    loop.create_task(process_smuggle_runs())
    loop.create_task(check_auctions())
    loop.create_task(boss_spawn_scheduler())
    loop.create_task(ad_sender())
    loop.create_task(periodic_cleanup())
    loop.create_task(update_all_businesses_income())

    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)

# ==================== КОНЕЦ ЧАСТИ 9 ====================
# ==================== КОНЕЦ ПОЛНОГО КОДА ====================
