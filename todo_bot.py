import telebot
import sqlite3
from datetime import datetime, timedelta
import threading
import time

BOT_TOKEN = 'TOKEN'

bot = telebot.TeleBot(BOT_TOKEN)

# Koneksi database SQLite
def create_connection():
    conn = sqlite3.connect('todo_list.db', check_same_thread=False)
    return conn

# Membuat tabel todo 
def create_table():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task TEXT,
            deadline TEXT,
            completed BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# Handler untuk perintah /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_message = (
        "👋 Selamat datang di Todo List Bot! 📋\n\n"
        "Bot ini membantu Anda mengelola daftar tugas dengan mudah.\n\n"
        "🤖 Deskripsi Bot:\n"
        "- Tambah, lihat, dan hapus tugas\n"
        "- Pengingat otomatis untuk deadline\n\n"
        "👤 Author: @ninewanwann\n\n"
        "Gunakan /help untuk melihat daftar perintah yang tersedia."
    )
    bot.reply_to(message, welcome_message)

# Handler untuk perintah /help
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = (
        "🆘 Panduan Penggunaan Todo List Bot 🆘\n\n"
        "Perintah Tersedia:\n"
        "• /start - Memulai bot dan melihat deskripsi\n"
        "• /help - Menampilkan panduan penggunaan\n"
        "• /addtask - Menambah tugas baru\n"
        "   Contoh: `/addtask BelajarPython 20/12/2024`\n"
        "• /viewtask - Melihat daftar tugas aktif\n"
        "• /removetask - Menghapus tugas berdasarkan ID\n"
        "   Contoh: `/removetask 1`\n\n"
        "⚠️ Catatan:\n"
        "- Gunakan format tanggal DD/MM/YYYY\n"
        "- ID tugas dapat dilihat di /viewtask\n"
        "- Bot akan mengirim pengingat 1 hari sebelum deadline"
    )
    bot.reply_to(message, help_message)

# Fungsi menambah tugas
@bot.message_handler(commands=['addtask'])
def add_task(message):
    try:
        # Parsing perintah: /addtask Tugas [deadline]
        parts = message.text.split(' ', 2)
        if len(parts) < 2:
            bot.reply_to(message, "Format salah. Gunakan: /addtask NamaTugas [deadline]")
            return

        task = parts[1]
        deadline = None

        # Cek deadline
        if len(parts) == 3:
            try:
                deadline = datetime.strptime(parts[2], '%d/%m/%Y').strftime('%d/%m/%Y')
            except ValueError:
                bot.reply_to(message, "Format deadline salah. Gunakan DD/MM/YYYY")
                return

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO todos (user_id, task, deadline) VALUES (?, ?, ?)', 
            (message.from_user.id, task, deadline)
        )
        conn.commit()
        conn.close()

        bot.reply_to(message, f"Tugas '{task}' berhasil ditambahkan!")
    
    except Exception as e:
        bot.reply_to(message, f"Terjadi kesalahan: {str(e)}")

# Fungsi melihat daftar tugas
@bot.message_handler(commands=['viewtask'])
def view_tasks(message):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, task, deadline FROM todos WHERE user_id = ? AND completed = 0 ORDER BY deadline', 
        (message.from_user.id,)
    )
    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        bot.reply_to(message, "📋 Daftar tugas kosong. Ayo tambahkan tugas baru!")
        return

    # Tampilan daftar tugas
    response = "📋 *Daftar Tugas Aktif* 📋\n\n"
    
    for task in tasks:
        task_id, task_name, deadline = task
        
        # Format deadline
        if deadline:
            # Hitung sisa hari hingga deadline
            try:
                deadline_date = datetime.strptime(deadline, '%d/%m/%Y')
                today = datetime.now()
                days_left = (deadline_date - today).days
                
                # Warna dan emoji berdasarkan sisa hari
                if days_left < 0:
                    deadline_info = f"🔴 Lewat deadline {abs(days_left)} hari"
                elif days_left == 0:
                    deadline_info = f"🟠 Deadline hari ini"
                elif days_left <= 3:
                    deadline_info = f"🟡 Tersisa {days_left} hari"
                else:
                    deadline_info = f"🟢 Tersisa {days_left} hari"
            except:
                deadline_info = f"📅 {deadline}"
        else:
            deadline_info = "🕒 Tanpa deadline"
        
        # Format tugas
        response += (
            f"🔹 *ID {task_id}*: {task_name}\n"
            f"   {deadline_info}\n\n"
        )
    
    # Statistik tambahan
    response += (
        f"📊 Total Tugas Aktif: {len(tasks)}\n"
        f"💡 Gunakan /help untuk bantuan lebih lanjut"
    )

    # Kirim dengan parse_mode markdown untuk format teks
    bot.reply_to(message, response, parse_mode='Markdown')

# Fungsi menghapus tugas
@bot.message_handler(commands=['removetask'])
def remove_task(message):
    try:
        # Parsing perintah: /removetask ID
        parts = message.text.split(' ')
        if len(parts) != 2:
            bot.reply_to(message, "Format salah. Gunakan: /removetask ID")
            return

        task_id = parts[1]

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM todos WHERE id = ? AND user_id = ?', 
            (task_id, message.from_user.id)
        )
        
        if cursor.rowcount > 0:
            conn.commit()
            bot.reply_to(message, f"Tugas dengan ID {task_id} berhasil dihapus.")
        else:
            bot.reply_to(message, f"Tugas dengan ID {task_id} tidak ditemukan.")
        
        conn.close()
    
    except Exception as e:
        bot.reply_to(message, f"Terjadi kesalahan: {str(e)}")

# Fungsi notifikasi deadline
def check_deadlines():
    while True:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Ambil tugas yang mendekati deadline
        today = datetime.now().strftime('%d/%m/%Y')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')
        
        cursor.execute('''
            SELECT id, user_id, task, deadline 
            FROM todos 
            WHERE deadline IN (?, ?) AND completed = 0
        ''', (today, tomorrow))
        
        tasks = cursor.fetchall()
        
        for task in tasks:
            task_id, user_id, task_name, deadline = task
            
            # Kirim notifikasi
            try:
                bot.send_message(
                    user_id, 
                    f"🚨 Pengingat: Tugas '{task_name}' akan segera mencapai deadline!"
                )
            except Exception as e:
                print(f"Gagal mengirim notifikasi: {e}")
        
        conn.close()
        
        # Tunggu 1 jam sebelum pengecekan berikutnya
        time.sleep(3600)

# Jalankan tabel dan notifikasi
create_table()
notification_thread = threading.Thread(target=check_deadlines)
notification_thread.daemon = True
notification_thread.start()

# Mulai bot
print("Bot Todo List siap digunakan!")
bot.polling()