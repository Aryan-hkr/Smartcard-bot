import telebot
from telebot import types
import os
import sqlite3
from datetime import datetime, timedelta
import logging
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import schedule
import time
import threading

# Bot token and admin ID
BOT_TOKEN = "8060499016:AAGzVVlRiux_KLce2wlG4aXcHRD4j9qXBWw"
ADMIN_ID = 7122689824  # Your Telegram user ID

bot = telebot.TeleBot(BOT_TOKEN)

# Logging setup
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        plan TEXT,
        expiry_date TEXT,
        name TEXT,
        email TEXT,
        business TEXT,
        address TEXT,
        phone TEXT,
        alt_phone TEXT,
        slogan TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        path TEXT,
        is_premium INTEGER
    )''')
    # Sample templates
    c.execute("SELECT COUNT(*) FROM templates")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO templates (name, path, is_premium) VALUES (?, ?, ?)", 
                 ("Template 1", "templates/template1.jpg", 0))
        c.execute("INSERT INTO templates (name, path, is_premium) VALUES (?, ?, ?)", 
                 ("Template 2", "templates/template2.jpg", 1))
    conn.commit()
    conn.close()

# User plan check
def get_user_plan(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT plan, expiry_date FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result and result[1] and datetime.fromisoformat(result[1]) > datetime.now():
        return result[0]
    return "free"

# Update user plan
def update_user_plan(user_id, plan, expiry):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET plan = ?, expiry_date = ? WHERE user_id = ?", 
             (plan, expiry.isoformat() if expiry else None, user_id))
    conn.commit()
    conn.close()

# Start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    logging.info(f"User {message.chat.id} started bot")
    bot.send_message(
        message.chat.id,
        "👋 Welcome to SmartCard Generator Bot!\n\n"
        "I will help you create professional business cards.\n\n"
        "👉 To begin, click the button below 👇",
        reply_markup=start_buttons()
    )

# Start buttons
def start_buttons():
    markup = types.InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        types.InlineKeyboardButton("📝 Register Info", callback_data="register"),
        types.InlineKeyboardButton("ℹ️ About", callback_data="about"),
        types.InlineKeyboardButton("🎨 Templates", callback_data="templates")
    )
    return markup

# Handle button clicks
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    bot.answer_callback_query(call.id)
    if call.data == "register":
        bot.send_message(call.message.chat.id, "Let's collect your details step by step.")
        ask_name(call.message)
    elif call.data == "about":
        bot.send_message(call.message.chat.id, "🔹 This bot creates professional business cards.\n🔒 Free and Premium plans available.\nCreated by Aryan Sharma.")
    elif call.data == "templates":
        show_templates(call.message)
    elif call.data.startswith("template_"):
        generate_card(call)
    elif call.data == "locked":
        bot.send_message(call.message.chat.id, "This template is premium. Contact the admin to upgrade your plan.")

# Info collection step-by-step
user_info = {}

def ask_name(message):
    try:
        msg = bot.send_message(message.chat.id, "📛 What is your full name?")
        bot.register_next_step_handler(msg, ask_email)
    except Exception as e:
        logging.error(f"Error in ask_name: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

def ask_email(message):
    try:
        if message.text.startswith('/'):  # Prevent commands during input
            bot.send_message(message.chat.id, "Please enter a name, not a command. Use /cancel to stop.")
            ask_name(message)
            return
        user_info[message.chat.id] = {"name": message.text}
        msg = bot.send_message(message.chat.id, "📧 Enter your email:")
        bot.register_next_step_handler(msg, ask_work)
    except Exception as e:
        logging.error(f"Error in ask_email: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

def ask_work(message):
    try:
        user_info[message.chat.id]["email"] = message.text
        msg = bot.send_message(message.chat.id, "💼 Enter your work or business name:")
        bot.register_next_step_handler(msg, ask_address)
    except Exception as e:
        logging.error(f"Error in ask_work: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

def ask_address(message):
    try:
        user_info[message.chat.id]["work"] = message.text
        msg = bot.send_message(message.chat.id, "📍 Enter your address:")
        bot.register_next_step_handler(msg, ask_phone)
    except Exception as e:
        logging.error(f"Error in ask_address: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

def ask_phone(message):
    try:
        user_info[message.chat.id]["address"] = message.text
        msg = bot.send_message(message.chat.id, "📱 Enter your contact number:")
        bot.register_next_step_handler(msg, ask_alt_phone)
    except Exception as e:
        logging.error(f"Error in ask_phone: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

def ask_alt_phone(message):
    try:
        user_info[message.chat.id]["phone"] = message.text
        msg = bot.send_message(message.chat.id, "📞 Enter an alternate contact number (or type 'None'):")
        bot.register_next_step_handler(msg, ask_slogan)
    except Exception as e:
        logging.error(f"Error in ask_alt_phone: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

def ask_slogan(message):
    try:
        user_info[message.chat.id]["alt_phone"] = message.text
        msg = bot.send_message(message.chat.id, "💬 Enter a slogan or tagline for your card (or type 'None'):")
        bot.register_next_step_handler(msg, complete_registration)
    except Exception as e:
        logging.error(f"Error in ask_slogan: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

def complete_registration(message):
    try:
        user_info[message.chat.id]["slogan"] = message.text
        data = user_info[message.chat.id]
        user_id = message.chat.id
        # Save to DB
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO users 
            (user_id, plan, name, email, business, address, phone, alt_phone, slogan) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, 'free', data['name'], data['email'], data['work'], data['address'],
             data['phone'], data['alt_phone'], data['slogan']))
        conn.commit()
        conn.close()
        # Show summary
        summary = (
            f"✅ Your details:\n\n"
            f"Name: {data['name']}\n"
            f"Email: {data['email']}\n"
            f"Business: {data['work']}\n"
            f"Address: {data['address']}\n"
            f"Phone: {data['phone']}\n"
            f"Alternate Phone: {data['alt_phone']}\n"
            f"Slogan: {data['slogan']}"
        )
        bot.send_message(message.chat.id, summary)
        bot.send_message(message.chat.id, "🎉 Registration complete! You can now generate your card. Use /templates to choose a template.")
        logging.info(f"User {user_id} registered info")
        del user_info[message.chat.id]  # Clear temp data
    except Exception as e:
        logging.error(f"Error in complete_registration: {e}")
        bot.send_message(message.chat.id, "Something went wrong. Please start again with /start.")

# Cancel command
@bot.message_handler(commands=['cancel'])
def cancel(message):
    if message.chat.id in user_info:
        del user_info[message.chat.id]
    bot.send_message(message.chat.id, "Registration canceled. Start again with /start.")

# Show templates
def show_templates(message):
    user_id = message.chat.id
    plan = get_user_plan(user_id)
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, name, path, is_premium FROM templates")
    templates = c.fetchall()
    conn.close()
    markup = types.InlineKeyboardMarkup()
    for temp in templates:
        tid, name, path, is_premium = temp
        if is_premium and plan == 'free':
            markup.add(types.InlineKeyboardButton(f"{name} (Locked)", callback_data='locked'))
            bot.send_photo(user_id, open(path, 'rb'), caption=f"{name} (Premium)")
        else:
            markup.add(types.InlineKeyboardButton(name, callback_data=f"template_{tid}"))
            bot.send_photo(user_id, open(path, 'rb'), caption=name)
    bot.send_message(user_id, "Choose a template:", reply_markup=markup)

# Generate card
def generate_card(call):
    user_id = call.message.chat.id
    template_id = int(call.data.split('_')[1])
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT path FROM templates WHERE id = ?", (template_id,))
    template_path = c.fetchone()[0]
    c.execute("SELECT name, email, business, address, phone, alt_phone, slogan FROM users WHERE user_id = ?", (user_id,))
    user_info = c.fetchone()
    conn.close()
    if not user_info:
        bot.send_message(user_id, "Please register your info first using /start.")
        return
    output_path = create_card(template_path, user_info, user_id)
    bot.send_photo(user_id, open(output_path, 'rb'), caption="Here is your business card (JPEG)")
    pdf_path = export_to_pdf(output_path, user_id)
    bot.send_document(user_id, open(pdf_path, 'rb'), caption="Here is your business card (PDF)")
    logging.info(f"User {user_id} generated card with template {template_id}")

# Create card image
def create_card(template_path, user_info, user_id):
    img = Image.open(template_path)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 20)  # Arial font required
    y = 50
    for field in user_info:
        if field and field != 'None':
            draw.text((50, y), field, font=font, fill="black")
            y += 30
    output_path = f"cards/{user_id}_card.jpg"
    os.makedirs("cards", exist_ok=True)
    img.save(output_path, "JPEG")
    return output_path

# Export to PDF
def export_to_pdf(image_path, user_id):
    output_path = f"cards/{user_id}_card.pdf"
    c = canvas.Canvas(output_path, pagesize=letter)
    c.drawImage(image_path, 100, 500, width=200, height=100)
    c.save()
    return output_path

# Admin commands
@bot.message_handler(commands=['adduser'])
def add_user(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "You are not an admin!")
        return
    try:
        args = message.text.split()[1:]  # /adduser user_id plan days
        user_id, plan, days = int(args[0]), args[1], int(args[2])
        expiry = datetime.now() + timedelta(days=days)
        update_user_plan(user_id, plan, expiry)
        bot.send_message(message.chat.id, f"User {user_id} added to {plan} plan, expiry: {expiry}")
        logging.info(f"Admin added user {user_id} to {plan} for {days} days")
    except:
        bot.send_message(message.chat.id, "Invalid command. Usage: /adduser <user_id> <plan> <days>")

@bot.message_handler(commands=['expireuser'])
def expire_user(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "You are not an admin!")
        return
    try:
        user_id = int(message.text.split()[1])
        update_user_plan(user_id, 'free', None)
        bot.send_message(message.chat.id, f"User {user_id}'s plan has been expired.")
        logging.info(f"Admin expired user {user_id}")
    except:
        bot.send_message(message.chat.id, "Invalid command. Usage: /expireuser <user_id>")

# Auto expiry
def check_expiries():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id, expiry_date FROM users WHERE expiry_date IS NOT NULL")
    users = c.fetchall()
    for user_id, expiry in users:
        if datetime.fromisoformat(expiry) < datetime.now():
            update_user_plan(user_id, 'free', None)
            logging.info(f"User {user_id} plan expired automatically")
            bot.send_message(user_id, "Your plan has expired. Contact the admin to get a new plan.")
    conn.close()

def run_scheduler():
    schedule.every().day.at("00:00").do(check_expiries)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start bot
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("🤖 Bot is running...")
    bot.infinity_polling()
