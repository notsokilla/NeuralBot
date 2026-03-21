#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 Универсальный AI-помощник для Telegram
Функционал: Математика • Поиск • Обучение • Игры • Новости
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Загрузка переменных окружения
load_dotenv()

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NEURAL_API_KEY = os.getenv("NEURAL_API_KEY")
NEURAL_BASE_URL = os.getenv("NEURAL_BASE_URL", "https://openrouter.ai/api/v1")
NEURAL_MODEL = os.getenv("NEURAL_MODEL", "meta-llama/llama-3.1-70b-instruct")
PROXY_URL = os.getenv("PROXY_URL", "")

# Инициализация
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

client = AsyncOpenAI(
    api_key=NEURAL_API_KEY,
    base_url=NEURAL_BASE_URL
)

# ================= СИСТЕМНЫЕ ПРОМПТЫ ПО КАТЕГОРИЯМ =================
PROMPTS = {
    "math": """
Ты — эксперт-математик и преподаватель.
Твоя задача: решать математические задачи ЛЮБОЙ сложности с ПОШАГОВЫМ объяснением.

ПРАВИЛА:
1. Всегда показывай ход решения шаг за шагом
2. Объясняй каждую операцию простым языком
3. Используй формулы в читаемом формате: x², √, ∫, ∑
4. Проверяй ответ на логику и разумность
5. Если задача неполная — уточни, что нужно знать

КАТЕГОРИИ: Алгебра • Геометрия • Статистика • Матанализ • Теорвер
    """,

    "search": """
Ты — аналитик и исследователь с доступом к обширным знаниям.
Твоя задача: находить, анализировать и структурировать информацию.

ПРАВИЛА:
1. Давай точные факты с указанием источников (если известны)
2. Разделяй факты и мнения
3. Структурируй ответ: заголовки, списки, таблицы
4. Указывай дату актуальности информации
5. Если данных недостаточно — честно скажи об этом

ТЕМЫ: Наука • Технологии • История • Политика • Культура • Бизнес
    """,

    "consult": """
Ты — универсальный консультант с энциклопедическими знаниями.
Твоя задача: давать развёрнутые, полезные ответы на любые вопросы.

ПРАВИЛА:
1. Адаптируй сложность ответа под уровень вопроса
2. Давай практические рекомендации, а не только теорию
3. Предупреждай о рисках и ограничениях советов
4. Предлагай альтернативные варианты решения
5. Будь вежлив, объективен и нейтрален в спорных темах
    """,

    "learn": """
Ты — опытный педагог и репетитор.
Твоя задача: объяснять сложные темы просто, помогать в учёбе.

ПРАВИЛА:
1. Используй аналогии и примеры из жизни
2. Разбивай сложные концепции на простые шаги
3. Предлагай проверочные вопросы для закрепления
4. Давай советы по запоминанию и подготовке к экзаменам
5. Поддерживай мотивацию ученика

ФОРМАТЫ: Конспекты • Тесты • Шпаргалки • Разбор ошибок • Планы обучения
    """,

    "game": """
Ты — профессиональный геймер и киберспортивный аналитик.
Твоя задача: помогать с играми — билды, стратегии, мета, гайды.

ПРАВИЛА:
1. Указывай актуальность информации (патч, сезон, мета)
2. Давай конкретные цифры и тайминги, когда возможно
3. Объясняй "почему" этот билд/стратегия работает
4. Предлагай альтернативы под разные стили игры
5. Используй игровой сленг уместно, но не перегружай

ИГРЫ: Dota 2 • CS2 • LoL • Valorant • WoW • Genshin • Minecraft • и другие
    """,

    "news": """
Ты — аналитик трендов и новостной обозреватель.
Твоя задача: предоставлять актуальную информацию и анализ событий.

ПРАВИЛА:
1. Указывай дату и источник информации
2. Разделяй факты, мнения и прогнозы
3. Показывай разные точки зрения на событие
4. Выделяй ключевые тренды и их последствия
5. Предупреждай, если информация может быть устаревшей

ТЕМЫ: Технологии • Игры • Киберспорт • Наука • Общество
    """
}

# ================= МАШИНА СОСТОЯНИЙ ДЛЯ ДИАЛОГОВ =================
class QueryMode(StatesGroup):
    waiting_for_math = State()
    waiting_for_search = State()
    waiting_for_game = State()
    waiting_for_learn = State()

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================

def detect_category(text: str) -> str:
    """
    Автоматически определяет категорию запроса по ключевым словам.
    Возвращает: 'math', 'search', 'consult', 'learn', 'game', 'news' или 'auto'
    """
    text_lower = text.lower()

    # Математика
    math_keywords = ['реши', 'уравнение', 'формула', 'интеграл', 'производная',
                     'треугольник', 'вероятность', 'среднее', 'математик', 'посчитай',
                     'алгебра', 'геометрия', 'статистика', '√', '∫', '∑', '²']
    if any(kw in text_lower for kw in math_keywords):
        return 'math'

    # Игры
    game_keywords = ['билд', 'сборка', 'мета', 'патч', 'гайд', 'стратегия', 'тактика',
                     'дота', 'cs2', 'контра', 'валорант', 'лол', 'genshin', 'майнкрафт',
                     'прокачка', 'апгрейд', 'киберспорт', 'турнир', 'матч', 'реплей']
    if any(kw in text_lower for kw in game_keywords):
        return 'game'

    # Обучение
    learn_keywords = ['объясни', 'как понять', 'конспект', 'экзамен', 'тест',
                      'подготовка', 'тема', 'урок', 'учебник', 'шпаргалка', 'запомнить']
    if any(kw in text_lower for kw in learn_keywords):
        return 'learn'

    # Новости/тренды
    news_keywords = ['новости', 'тренд', 'обзор', 'событие', 'аналитика',
                     'что нового', 'последнее', 'обновление', 'релиз']
    if any(kw in text_lower for kw in news_keywords):
        return 'news'

    # Поиск информации
    search_keywords = ['найди', 'информация', 'данные', 'факты', 'источник',
                       'статистика', 'исследование', 'анализ', 'сравнение']
    if any(kw in text_lower for kw in search_keywords):
        return 'search'

    # По умолчанию — универсальная консультация
    return 'consult'


def format_math_response(text: str) -> str:
    """Форматирует математический ответ для лучшего отображения в Telegram"""
    # Заменяем ** на ² для степеней
    text = re.sub(r'\*\*(\d+)\*\*', r'²', text)
    # Добавляем моноширинный шрифт для формул в ``
    text = re.sub(r'`([^`]+)`', r'`\1`', text)
    return text


async def call_neural_api(prompt_type: str, user_query: str, context: str = "") -> str:
    """
    Отправляет запрос в нейросеть с соответствующим системным промптом.
    """
    system_prompt = PROMPTS.get(prompt_type, PROMPTS['consult'])

    full_context = f"Контекст диалога: {context}\n" if context else ""

    try:
        response = await client.chat.completions.create(
            model=NEURAL_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{full_context}Вопрос пользователя: {user_query}"}
            ],
            temperature=0.7,
            max_tokens=1500,
            # Дополнительные параметры для стабильности
            extra_body={
                "repetition_penalty": 1.1
            } if "openrouter" in NEURAL_BASE_URL else {}
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"API Error: {e}")
        return f"⚠️ Ошибка связи с нейросетью: {type(e).__name__}\nПопробуйте позже или перефразируйте вопрос."


def create_main_keyboard() -> types.ReplyKeyboardMarkup:
    """Создаёт главное меню с кнопками"""
    keyboard = [
        [
            types.KeyboardButton(text="🧮 Математика"),
            types.KeyboardButton(text="🔍 Поиск")
        ],
        [
            types.KeyboardButton(text="🎓 Обучение"),
            types.KeyboardButton(text="🎮 Игры")
        ],
        [
            types.KeyboardButton(text="📰 Новости"),
            types.KeyboardButton(text="💬 Консультация")
        ],
        [
            types.KeyboardButton(text="❓ Помощь")
        ]
    ]
    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def create_inline_categories() -> types.InlineKeyboardMarkup:
    """Кнопки для быстрого выбора категории"""
    buttons = [
        [
            types.InlineKeyboardButton(text="🧮 Математика", callback_data="cat_math"),
            types.InlineKeyboardButton(text="🎮 Игры", callback_data="cat_game")
        ],
        [
            types.InlineKeyboardButton(text="🎓 Учеба", callback_data="cat_learn"),
            types.InlineKeyboardButton(text="🔍 Поиск", callback_data="cat_search")
        ],
        [
            types.InlineKeyboardButton(text="📰 Новости", callback_data="cat_news")
        ]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


# ================= ОБРАБОТЧИКИ КОМАНД =================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик /start"""
    await message.answer(
        f"🤖 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        "Я — универсальный AI-помощник. Могу:\n"
        "🧮 Решать математические задачи с объяснением\n"
        "🔍 Искать и анализировать информацию\n"
        "🎓 Помогать с учёбой и объяснять сложное просто\n"
        "🎮 Давать гайды, билды и стратегии по играм\n"
        "📰 Рассказывать о новостях и трендах\n"
        "💬 Отвечать на любые вопросы\n\n"
        "<b>Как использовать:</b>\n"
        "• Просто напиши вопрос — я сам пойму тему\n"
        "• Или выбери категорию в меню ниже 👇",
        reply_markup=create_main_keyboard(),
        parse_mode="HTML"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик /help"""
    help_text = """
📋 <b>СПРАВКА ПО БОТУ</b>

<b>🔹 Автоматический режим</b>
Просто напиши вопрос — бот сам определит тему:
• "Реши ∫x²dx" → Математика
• "Билд на Phantom Assassin" → Игры
• "Объясни теорию относительности" → Обучение

<b>🔹 Команды</b>
• /math — режим решения задач
• /search — поиск информации
• /learn — учебные вопросы
• /game — игровые гайды
• /news — новости и тренды
• /clear — очистить историю диалога

<b>🔹 Примеры запросов</b>
🧮 "Найди корни уравнения: x² - 5x + 6 = 0"
🎮 "Какая мета в патче 7.35 для мидеров в Доте?"
🎓 "Как быстро запомнить даты Второй мировой?"
🔍 "Сравни характеристики RTX 4070 и RX 7800 XT"
📰 "Какие тренды в инди-играх?"

💡 <i>Совет: Чем конкретнее вопрос — тем точнее ответ!</i>
    """
    await message.answer(help_text, parse_mode="HTML")


@dp.message(Command("clear"))
async def cmd_clear(message: Message, state: FSMContext):
    """Очистка контекста диалога"""
    await state.clear()
    await message.answer("🗑️ История диалога очищена. Начнём с чистого листа!")


# ================= КОМАНДЫ ДЛЯ РЕЖИМОВ =================

@dp.message(Command("math"))
async def cmd_math(message: Message, state: FSMContext):
    """Вход в режим математики"""
    await state.set_state(QueryMode.waiting_for_math)
    await message.answer(
        "🧮 <b>Режим: Математика</b>\n\n"
        "Напиши задачу — я решу её с пошаговым объяснением.\n"
        "Примеры:\n"
        "• Реши уравнение: 2x + 5 = 15\n"
        "• Найди площадь круга радиусом 7 см\n"
        "• Вычисли ∫(3x² + 2x)dx\n\n"
        "Чтобы выйти: /clear",
        parse_mode="HTML"
    )


@dp.message(Command("game"))
async def cmd_game(message: Message, state: FSMContext):
    """Вход в режим игр"""
    await state.set_state(QueryMode.waiting_for_game)
    await message.answer(
        "🎮 <b>Режим: Игры</b>\n\n"
        "Спроси про билды, стратегии, мету или гайды.\n"
        "Примеры:\n"
        "• Сборка на Снайпера против магического урона\n"
        "• Как контрить раст на А-сайде в Мираже (CS2)\n"
        "• Лучший билд на Арлекино в 4.2 (Genshin)\n\n"
        "Чтобы выйти: /clear",
        parse_mode="HTML"
    )


@dp.message(Command("learn"))
async def cmd_learn(message: Message, state: FSMContext):
    """Вход в режим обучения"""
    await state.set_state(QueryMode.waiting_for_learn)
    await message.answer(
        "🎓 <b>Режим: Обучение</b>\n\n"
        "Я объясню сложное просто и помогу с учёбой.\n"
        "Примеры:\n"
        "• Объясни квантовую запутанность как для 5-классника\n"
        "• Составь план подготовки к ЕГЭ по математике на 3 месяца\n"
        "• Сделай конспект по теме 'Фотосинтез'\n\n"
        "Чтобы выйти: /clear",
        parse_mode="HTML"
    )


# ================= ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ =================

@dp.message()
async def handle_message(message: Message, state: FSMContext):
    """Основной обработчик сообщений"""
    user_text = message.text.strip()

    # Получаем текущий режим (если установлен)
    current_state = await state.get_state()

    # Определяем категорию
    if current_state == QueryMode.waiting_for_math.state:
        category = 'math'
    elif current_state == QueryMode.waiting_for_game.state:
        category = 'game'
    elif current_state == QueryMode.waiting_for_learn.state:
        category = 'learn'
    else:
        # Автоматическое определение
        category = detect_category(user_text)

    # Показываем индикатор "печатает..."
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Отправляем запрос в нейросеть
    ai_response = await call_neural_api(category, user_text)

    # Форматируем ответ для математики
    if category == 'math':
        ai_response = format_math_response(ai_response)

    # Добавляем подпись категории для наглядности
    category_emoji = {
        'math': '🧮', 'search': '🔍', 'consult': '💬',
        'learn': '🎓', 'game': '🎮', 'news': '📰'
    }

    # Отправляем ответ
    await message.answer(
        f"{category_emoji.get(category, '🤖')} <b>Ответ:</b>\n\n{ai_response}",
        parse_mode="HTML",
        reply_markup=create_inline_categories()
    )

@dp.callback_query(F.data.startswith("cat_"))
async def handle_category_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик нажатий на категории"""
    category_map = {
        'cat_math': ('math', '🧮 Математика', QueryMode.waiting_for_math),
        'cat_game': ('game', '🎮 Игры', QueryMode.waiting_for_game),
        'cat_learn': ('learn', '🎓 Обучение', QueryMode.waiting_for_learn),
        'cat_search': ('search', '🔍 Поиск', None),
        'cat_news': ('news', '📰 Новости', None),
    }

    if callback.data not in category_map:
        await callback.answer("Неизвестная категория", show_alert=True)
        return

    cat_key, cat_name, fsm_state = category_map[callback.data]

    # Устанавливаем состояние если нужно
    if fsm_state:
        await state.set_state(fsm_state)

    await callback.message.edit_text(
        f"{cat_name} — выберите режим:\n\n"
        "• Напишите вопрос прямо сейчас, или\n"
        "• Используйте /clear для смены режима",
        reply_markup=None
    )
    await callback.answer()

async def main():
    """Точка входа"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Если указан прокси — настраиваем сессию
    if PROXY_URL:
        from aiohttp_socks import ProxyConnector
        connector = ProxyConnector.from_url(PROXY_URL)
        bot.session = aiohttp.ClientSession(connector=connector)
        logging.info(f"✅ Прокси настроен: {PROXY_URL}")

    logging.info("🚀 Запуск бота...")
    print(f"✅ Бот запущен! (@{(await bot.get_me()).username})")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())