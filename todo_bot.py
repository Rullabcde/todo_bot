from telebot import types
import telebot
import sqlite3
from datetime import datetime, timedelta
import threading
import time

BOT_TOKEN = 'TOKEN'
bot = telebot.TeleBot(BOT_TOKEN)

# Menyimpan status pengguna (sederhana menggunakan dictionary)
user_states = {}

# Koneksi database SQLite
def create_connection():
    conn = sqlite3.connect('todo_list.db', check_same_thread=False)
    return conn

# Membuat tabel todo
def create_table():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS todos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        task TEXT,
                        deadline TEXT,
                        completed BOOLEAN DEFAULT 0)''')
    conn.commit()
    conn.close()

# Fungsi untuk safely mengirim pesan dengan retry
def safe_send_message(chat_id, text, **kwargs):
    try:
        bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

# Handler untuk /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_message = (
        "👋 Selamat datang di Todo List Bot! 📋\n\n"
        "Bot ini membantu Anda mengelola daftar tugas dengan mudah.\n\n"
        "Gunakan /help untuk melihat daftar perintah yang tersedia."
    )
    safe_send_message(message.chat.id, welcome_message)

# Handler untuk /help
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = (
        "🖘 Panduan Penggunaan Todo List Bot 🖘\n\n"
        "Perintah Tersedia:\n"
        "• /start - Memulai bot\n"
        "• /help - Panduan penggunaan\n"
        "• /addtask - Tambah tugas baru\n"
        "• /viewtask - Lihat daftar tugas\n"
        "• /removetask - Hapus tugas berdasarkan ID\n"
        "• /complete - Tandai tugas selesai"
    )
    safe_send_message(message.chat.id, help_message)

# Fungsi untuk /addtask
@bot.message_handler(commands=['addtask'])
def add_task(message):
    user_states[message.from_user.id] = {'state': 'waiting_for_task_name'}
    safe_send_message(message.chat.id, "📝 Silakan kirimkan nama tugas yang ingin ditambahkan.")

# Fungsi untuk menerima nama tugas
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get('state') == 'waiting_for_task_name')
def receive_task_name(message):
    task_name = message.text
    user_states[message.from_user.id] = {'task_name': task_name, 'state': 'waiting_for_task_deadline'}
    safe_send_message(message.chat.id, "📅 Sekarang, berikan deadline tugas dalam format DD/MM/YYYY.")

# Fungsi untuk menerima deadline tugas
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get('state') == 'waiting_for_task_deadline')
def receive_task_deadline(message):
    deadline_text = message.text
    task_name = user_states[message.from_user.id]['task_name']

    try:
        deadline = datetime.strptime(deadline_text, '%d/%m/%Y').strftime('%d/%m/%Y')
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO todos (user_id, task, deadline) VALUES (?, ?, ?)', (message.from_user.id, task_name, deadline))
        conn.commit()
        conn.close()
        
        safe_send_message(message.chat.id, f"Tugas '{task_name}' dengan deadline {deadline} berhasil ditambahkan!")
        del user_states[message.from_user.id]  # Menghapus state setelah tugas ditambahkan
    except ValueError:
        safe_send_message(message.chat.id, "❌ Format tanggal salah. Gunakan format DD/MM/YYYY.")

# Fungsi untuk /removetask
@bot.message_handler(commands=['removetask'])
def remove_task(message):
    user_states[message.from_user.id] = {'state': 'waiting_for_task_id'}
    safe_send_message(message.chat.id, "🔴 Kirimkan ID tugas yang ingin dihapus.")

# Fungsi untuk menerima ID tugas yang ingin dihapus
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get('state') == 'waiting_for_task_id')
def receive_task_id_for_removal(message):
    try:
        task_id = int(message.text)
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM todos WHERE id = ? AND user_id = ?', (task_id, message.from_user.id))
        conn.commit()
        conn.close()

        if cursor.rowcount > 0:
            safe_send_message(message.chat.id, f"Tugas dengan ID {task_id} berhasil dihapus.")
        else:
            safe_send_message(message.chat.id, f"Tugas dengan ID {task_id} tidak ditemukan.")
        
        del user_states[message.from_user.id]  # Menghapus state setelah penghapusan selesai
    except ValueError:
        safe_send_message(message.chat.id, "❌ ID tugas harus berupa angka.")

# Fungsi untuk /complete
@bot.message_handler(commands=['complete'])
def complete_task(message):
    user_states[message.from_user.id] = {'state': 'waiting_for_task_id_complete'}
    safe_send_message(message.chat.id, "✅ Kirimkan ID tugas yang ingin ditandai selesai.")

# Fungsi untuk menerima ID tugas yang akan ditandai selesai
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get('state') == 'waiting_for_task_id_complete')
def receive_task_id_for_complete(message):
    try:
        task_id = int(message.text)
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE todos SET completed = 1 WHERE id = ? AND user_id = ?', (task_id, message.from_user.id))
        conn.commit()
        conn.close()

        if cursor.rowcount > 0:
            safe_send_message(message.chat.id, f"Tugas dengan ID {task_id} berhasil ditandai sebagai selesai.")
        else:
            safe_send_message(message.chat.id, f"Tugas dengan ID {task_id} tidak ditemukan atau sudah selesai.")
        
        del user_states[message.from_user.id]  # Menghapus state setelah selesai
    except ValueError:
        safe_send_message(message.chat.id, "❌ ID tugas harus berupa angka.")

# Fungsi untuk melihat daftar tugas
@bot.message_handler(commands=['viewtask'])
def view_tasks(message):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, task, deadline FROM todos WHERE user_id = ? AND completed = 0 ORDER BY deadline', (message.from_user.id,))
    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        safe_send_message(message.chat.id, "📋 Daftar tugas kosong. Tambahkan tugas baru dengan /addtask.")
        return

    response = "📋 *Daftar Tugas Aktif* 📋\n\n"
    for task in tasks:
        task_id, task_name, deadline = task
        days_left = (datetime.strptime(deadline, '%d/%m/%Y') - datetime.now()).days
        status = "🟢" if days_left > 3 else "🟡" if days_left > 0 else "🔴"
        response += f"🔹 *{task_name}* (ID: {task_id}) - {status} Deadline: {deadline}\n"
    safe_send_message(message.chat.id, response, parse_mode='Markdown')

# Thread untuk mengirim pengingat
def check_deadlines():
    while True:
        try:
            conn = create_connection()
            cursor = conn.cursor()
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')
            cursor.execute('SELECT user_id, task, deadline FROM todos WHERE deadline = ? AND completed = 0', (tomorrow,))
            tasks = cursor.fetchall()
            conn.close()

            for user_id, task_name, deadline in tasks:
                safe_send_message(user_id, f"🛒 Pengingat: Tugas '{task_name}' memiliki deadline besok: {deadline}.")
        except Exception as e:
            print(f"Error checking deadlines: {e}")
        time.sleep(3600)

# Mulai thread pengingat
create_table()
threading.Thread(target=check_deadlines, daemon=True).start()

# Mulai bot
print("Bot berjalan...")
while True:
    try:
        bot.polling(non_stop=True, timeout=60)
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(5)
