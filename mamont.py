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
API_TOKEN = 'YOUR_NFT_BOT_TOKEN'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Подключение к SQLite
conn = sqlite3.connect('nft_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS nfts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    photo TEXT,
    description TEXT,
    price REAL,
    sold BOOLEAN DEFAULT FALSE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 10000
)
''')
conn.commit()

# Состояния для FSM
class NFTStates(StatesGroup):
    sell_price = State()
    create_name = State()
    create_photo = State()
    create_description = State()

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    await message.answer("Добро пожаловать в NFT бот! Используйте /sell для продажи NFT или /create для создания NFT.")

# Продажа NFT
@dp.message_handler(commands=['sell'])
async def cmd_sell(message: types.Message):
    await NFTStates.sell_price.set()
    await message.answer("Введите цену продажи NFT:")

@dp.message_handler(state=NFTStates.sell_price)
async def process_sell_price(message: types.Message, state: FSMContext):
    price = float(message.text)
    user_id = message.from_user.id
    cursor.execute('INSERT INTO nfts (user_id, price) VALUES (?, ?)', (user_id, price))
    conn.commit()
    await message.answer(f"Ваш NFT выставлен на продажу за {price}.")
    await state.finish()

# Создание NFT
@dp.message_handler(commands=['create'])
async def cmd_create(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    if balance >= 10000:
        cursor.execute('UPDATE users SET balance = balance - 10000 WHERE user_id = ?', (user_id,))
        await NFTStates.create_name.set()
        await message.answer("Введите название NFT:")
    else:
        await message.answer("Недостаточно средств для создания NFT.")

@dp.message_handler(state=NFTStates.create_name)
async def process_create_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await NFTStates.create_photo.set()
    await message.answer("Отправьте фото NFT:")

@dp.message_handler(content_types=['photo'], state=NFTStates.create_photo)
async def process_create_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await NFTStates.create_description.set()
    await message.answer("Введите описание NFT:")

@dp.message_handler(state=NFTStates.create_description)
async def process_create_description(message: types.Message, state: FSMContext):
    description = message.text
    data = await state.get_data()
    user_id = message.from_user.id
    cursor.execute('INSERT INTO nfts (user_id, name, photo, description, price) VALUES (?, ?, ?, ?, ?)',
                   (user_id, data['name'], data['photo'], description, 0.0001))
    conn.commit()
    await message.answer("Ваш NFT успешно создан и добавлен в 'Мои NFT'.")
    await state.finish()

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
