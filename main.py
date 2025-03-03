import telebot
import sqlite3
import time
import threading
from telebot import types

bot = telebot.TeleBot("7642647034:AAG6yAZa04apmOPJF52aB98NBCzSi6jMWO8")

# Инициализация базы данных
conn = sqlite3.connect('genotcoin.db', check_same_thread=False)
cursor = conn.cursor()


def init_db():
    # Создание таблицы пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        mining_speed REAL DEFAULT 0.2,
        coins REAL DEFAULT 0.0,
        last_mined INTEGER DEFAULT 0,
        equipment TEXT DEFAULT ''
    )''')

    # Создание таблицы оборудования
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        level INTEGER,
        cost REAL,
        speed REAL,
        description TEXT,
        upgrade_cost REAL,
        upgrade_speed REAL
    )''')

    # Заполнение оборудования
    equipment_data = [
        (1, 'NVIDIA 3080', 'GPU', 1, 100, 0.5, 'Базовая видеокарта', 200, 0.3),
        (2, 'AMD RX 6800 XT', 'GPU', 1, 80, 0.4, 'Энергоэффективное оборудование', 150, 0.2),
        (3, 'Antminer S19', 'ASIC', 2, 500, 2.0, 'ASIC-майнер для Bitcoin', 1000, 0.8),
        (4, 'Intel i9-12900K', 'CPU', 1, 300, 1.2, 'Процессор с Hyper-Threading', 500, 0.5),
        (5, 'NVIDIA 4090', 'GPU', 3, 1000, 3.0, 'Флагманская модель', 2000, 1.0),
        (6, 'Bitmain WhatsMiner M30S', 'ASIC', 3, 2000, 8.0, 'Экспертный ASIC-майнер', 5000, 2.5),
        (7, 'Radeon VII', 'GPU', 2, 400, 1.5, 'Поддержка Equihash', 800, 0.7),
        (8, 'Xilinx Alveo U50', 'FPGA', 1, 150, 0.7, 'Современные FPGA-чипы', 300, 0.4)
    ]
    cursor.executemany('INSERT OR IGNORE INTO equipment VALUES (?,?,?,?,?,?,?,?,?)', equipment_data)
    conn.commit()


init_db()


# Генерация главного меню
def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📊 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🏆 Рейтинг", callback_data="rating")
    )
    markup.row(types.InlineKeyboardButton("🛠️ Прокачка", callback_data="upgrade_menu"))
    return markup


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    cursor.execute('INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)',
                   (user_id, message.from_user.username))
    conn.commit()
    bot.send_message(user_id, "🚀 Добро пожаловать в GenotCoin Майнинг!", reply_markup=main_menu())


# Фоновая задача майнинга
def mine_coins():
    while True:
        try:
            current_time = int(time.time())
            cursor.execute('SELECT id, mining_speed, last_mined FROM users')
            users = cursor.fetchall()

            for user in users:
                user_id, speed, last_mined = user

                if last_mined == 0:  # Первая инициализация
                    cursor.execute('UPDATE users SET last_mined = ? WHERE id = ?',
                                   (current_time, user_id))
                    continue

                elapsed = current_time - last_mined
                if elapsed > 0:
                    coins_earned = speed * (elapsed / 60)  # Начисление в минутах
                    cursor.execute('''
                        UPDATE users 
                        SET coins = coins + ?, 
                            last_mined = ?
                        WHERE id = ?
                    ''', (coins_earned, current_time, user_id))

            conn.commit()
            time.sleep(10)  # Проверка каждые 10 секунд

        except Exception as e:
            print(f"Ошибка майнинга: {e}")


# Показать профиль
@bot.callback_query_handler(func=lambda call: call.data == 'profile')
def show_profile(call):
    try:
        cursor.execute('''
            SELECT name, mining_speed, coins, equipment 
            FROM users 
            WHERE id = ?
        ''', (call.from_user.id,))
        result = cursor.fetchone()

        if not result:
            bot.answer_callback_query(call.id, "Профиль не найден!", show_alert=True)
            return

        name, speed, coins, equipment = result
        equipment_list = []

        if equipment:
            for eq in equipment.split(','):
                if eq:
                    parts = eq.split('|')
                    if len(parts) >= 2:
                        equipment_list.append(f"{parts[0]} (Ур. {parts[1]})")

        response_text = (
            f"🔷 Ваш профиль:\n\n"
            f"👤 Имя: {name or 'Аноним'}\n"
            f"⚡ Скорость майнинга: {speed:.2f} GenoCoin/мин\n"
            f"💰 Баланс: {coins:.2f} GenoCoin\n"
            f"🛠 Оборудование: {', '.join(equipment_list) or 'Отсутствует'}"
        )

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response_text,
            reply_markup=main_menu()
        )

    except Exception as e:
        print(f"Ошибка профиля: {e}")
        bot.answer_callback_query(call.id, "Ошибка загрузки профиля", show_alert=True)


# Показать рейтинг
@bot.callback_query_handler(func=lambda call: call.data == 'rating')
def show_rating(call):
    try:
        cursor.execute('''
            SELECT name, coins 
            FROM users 
            WHERE coins > 0 
            ORDER BY coins DESC 
            LIMIT 10
        ''')
        top_users = cursor.fetchall()

        if not top_users:
            bot.answer_callback_query(call.id, "Рейтинг пока пуст! Станьте первым!", show_alert=True)
            return

        rating_text = "🏆 Топ-10 майнеров:\n\n"
        for index, (username, coins) in enumerate(top_users, 1):
            rating_text += f"{index}. {username or 'Аноним'} — {coins:.2f} GenoCoin\n"

        rating_text += f"\n🕒 Обновлено: {time.strftime('%H:%M:%S')}"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=rating_text,
            reply_markup=main_menu()
        )

    except Exception as e:
        print(f"Ошибка рейтинга: {e}")
        bot.answer_callback_query(call.id, "Ошибка загрузки рейтинга", show_alert=True)


# Меню прокачки
@bot.callback_query_handler(func=lambda call: call.data == 'upgrade_menu')
def show_upgrade_menu(call):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🌱 Уровень 1", callback_data="level_1"),
        types.InlineKeyboardButton("✨ Уровень 2", callback_data="level_2")
    )
    markup.row(
        types.InlineKeyboardButton("🔥 Уровень 3", callback_data="level_3"),
        types.InlineKeyboardButton("⇦ Назад", callback_data="back_to_menu")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Выберите уровень оборудования:",
        reply_markup=markup
    )


# Показать оборудование по уровням
@bot.callback_query_handler(func=lambda call: call.data.startswith('level_'))
def show_equipment(call):
    try:
        level = call.data.split('_')[1]
        cursor.execute('SELECT * FROM equipment WHERE level = ?', (level,))
        equipment = cursor.fetchall()

        if not equipment:
            bot.answer_callback_query(call.id, "Оборудование этого уровня пока недоступно!", show_alert=True)
            return

        markup = types.InlineKeyboardMarkup()
        for item in equipment:
            btn_text = (
                f"{item[1]} | 💰{item[4]} | "
                f"⚡{item[5]}/мин | {item[6]}"
            )
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_{item[0]}"))

        markup.add(types.InlineKeyboardButton("⇦ Назад", callback_data="upgrade_menu"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🛠 Оборудование {level} уровня:",
            reply_markup=markup
        )

    except Exception as e:
        print(f"Ошибка оборудования: {e}")
        bot.answer_callback_query(call.id, "Ошибка загрузки оборудования", show_alert=True)


# Покупка оборудования
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_equipment(call):
    try:
        eq_id = int(call.data.split('_')[1])
        cursor.execute('SELECT * FROM equipment WHERE id = ?', (eq_id,))
        eq = cursor.fetchone()

        if not eq:
            bot.answer_callback_query(call.id, "Оборудование не найдено!", show_alert=True)
            return

        user_id = call.from_user.id
        cursor.execute('SELECT coins, equipment FROM users WHERE id = ?', (user_id,))
        balance, equipment = cursor.fetchone()

        if balance < eq[4]:
            bot.answer_callback_query(call.id, "Недостаточно средств!", show_alert=True)
            return

        # Обновляем оборудование
        new_equipment = f"{equipment},{eq[1]}|{eq[3]}" if equipment else f"{eq[1]}|{eq[3]}"

        cursor.execute('''
            UPDATE users 
            SET coins = coins - ?,
                mining_speed = mining_speed + ?,
                equipment = ?
            WHERE id = ?
        ''', (eq[4], eq[5], new_equipment, user_id))

        conn.commit()
        bot.answer_callback_query(call.id, f"✅ Успешная покупка: {eq[1]}!", show_alert=True)
        show_equipment(call)  # Возвращаемся к списку оборудования

    except Exception as e:
        print(f"Ошибка покупки: {e}")
        bot.answer_callback_query(call.id, "Ошибка при покупке", show_alert=True)


# Возврат в главное меню
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_menu')
def back_to_menu(call):
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Главное меню",
        reply_markup=main_menu()
    )


# Запуск бота
if __name__ == "__main__":
    mining_thread = threading.Thread(target=mine_coins)
    mining_thread.daemon = True
    mining_thread.start()

    print("Бот запущен!")
    bot.polling(none_stop=True)