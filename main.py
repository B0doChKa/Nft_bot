import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
API_TOKEN = 'YOUR_BOT_TOKEN'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Подключение к SQLite
conn = sqlite3.connect('mammoth_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0,
    blocked BOOLEAN DEFAULT FALSE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS actions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# Состояния для FSM
class ManageMammoth(StatesGroup):
    mammoth_id = State()
    action = State()
    amount = State()

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    await message.answer("Добро пожаловать! Используйте /manage для управления мамонтами.")

# Команда /manage
@dp.message_handler(commands=['manage'])
async def cmd_manage(message: types.Message):
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    keyboard = InlineKeyboardMarkup(row_width=2)
    for user in users:
        keyboard.add(InlineKeyboardButton(text=f"Мамонт {user[0]}", callback_data=f"mammoth_{user[0]}"))
    await message.answer("Выберите мамонта:", reply_markup=keyboard)

# Обработка выбора мамонта
@dp.callback_query_handler(lambda c: c.data.startswith('mammoth_'))
async def process_mammoth(callback_query: types.CallbackQuery):
    mammoth_id = int(callback_query.data.split('_')[1])
    await ManageMammoth.mammoth_id.set()
    state = Dispatcher.get_current().current_state()
    await state.update_data(mammoth_id=mammoth_id)

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(text="Информация", callback_data="info"))
    keyboard.add(InlineKeyboardButton(text="Заблокировать", callback_data="block"))
    keyboard.add(InlineKeyboardButton(text="Разблокировать", callback_data="unblock"))
    keyboard.add(InlineKeyboardButton(text="Изменить баланс", callback_data="change_balance"))
    keyboard.add(InlineKeyboardButton(text="История действий", callback_data="action_history"))

    await callback_query.message.answer("Выберите действие:", reply_markup=keyboard)

# Обработка действий
@dp.callback_query_handler(state=ManageMammoth.mammoth_id)
async def process_action(callback_query: types.CallbackQuery, state: FSMContext):
    action = callback_query.data
    data = await state.get_data()
    mammoth_id = data['mammoth_id']

    if action == "info":
        cursor.execute('SELECT balance, blocked FROM users WHERE user_id = ?', (mammoth_id,))
        user_data = cursor.fetchone()
        await callback_query.message.answer(f"Информация о мамонте {mammoth_id}:\nБаланс: {user_data[0]}\nСтатус: {'Заблокирован' if user_data[1] else 'Активен'}")
    elif action == "block":
        cursor.execute('UPDATE users SET blocked = TRUE WHERE user_id = ?', (mammoth_id,))
        conn.commit()
        await callback_query.message.answer(f"Мамонт {mammoth_id} заблокирован.")
    elif action == "unblock":
        cursor.execute('UPDATE users SET blocked = FALSE WHERE user_id = ?', (mammoth_id,))
        conn.commit()
        await callback_query.message.answer(f"Мамонт {mammoth_id} разблокирован.")
    elif action == "change_balance":
        await ManageMammoth.amount.set()
        await callback_query.message.answer("Введите сумму для изменения баланса:")
    elif action == "action_history":
        cursor.execute('SELECT action, timestamp FROM actions_log WHERE user_id = ?', (mammoth_id,))
        logs = cursor.fetchall()
        log_text = "\n".join([f"{log[0]} ({log[1]})" for log in logs])
        await callback_query.message.answer(f"История действий мамонта {mammoth_id}:\n{log_text}")

    await state.finish()

# Обработка изменения баланса
@dp.message_handler(state=ManageMammoth.amount)
async def process_amount(message: types.Message, state: FSMContext):
    amount = float(message.text)
    data = await state.get_data()
    mammoth_id = data['mammoth_id']
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, mammoth_id))
    cursor.execute('INSERT INTO actions_log (user_id, action) VALUES (?, ?)', (mammoth_id, f"Баланс изменен на {amount}"))
    conn.commit()
    await message.answer(f"Баланс мамонта {mammoth_id} изменен на {amount}.")
    await state.finish()

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
