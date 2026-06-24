import telebot, instaloader, time, os, pyotp, threading, sys
from telebot import types, apihelper
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request

# ================= [ SETTINGS ] =================

apihelper.ENABLE_MIDDLEWARE = True

BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
bot = telebot.TeleBot(BOT_TOKEN)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

user_sessions = {}

# ================= [ BUTTONS ] =================

def start_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("♻️ START PROCESS ♻️")
    return markup

def cancel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("❌ CANCEL")
    return markup

# ================= [ RESET SESSION ] =================

def reset_user(chat_id):
    user_sessions.pop(chat_id, None)
    bot.clear_step_handler_by_chat_id(chat_id)

# ================= [ SUCCESS SAVE ] =================

def save_success(chat_id, loader, username, password):

    if chat_id not in user_sessions:
        return

    cookies = loader.context._session.cookies.get_dict()

    cookie_str = "; ".join(
        [f"{k}={v}" for k, v in cookies.items()]
    )

    user_sessions[chat_id]["results"].append(
        f"{username}|{password}|{cookie_str}"
    )

    bot.send_message(
        chat_id,
        f"✅ SUCCESS LOGIN\n👤 Username: `{username}`",
        parse_mode="Markdown"
    )

# ================= [ LOGIN ENGINE ] =================

def login_worker(chat_id, username, password, key):

    if chat_id not in user_sessions:
        return

    L = instaloader.Instaloader(
        quiet=True,
        max_connection_attempts=1
    )

    L.context._session.headers.update({
        "User-Agent": UA
    })

    try:
        L.login(username, password)

        save_success(chat_id, L, username, password)

    except:

        try:
            totp = pyotp.TOTP(key.replace(" ", ""))

            code = totp.now()

            L.two_factor_login(code)

            save_success(chat_id, L, username, password)

        except:

            if chat_id in user_sessions:

                bot.send_message(
                    chat_id,
                    f"❌ FAILED : `{username}`",
                    parse_mode="Markdown"
                )

# ================= [ START COMMAND ] =================

@bot.message_handler(commands=["start"])

def start_command(message):

    chat_id = message.chat.id

    reset_user(chat_id)

    intro = """
🔥 *HOSSAIN COOKIE BOT*

━━━━━━━━━━━━━━━
⚡ Multi Account Processor
🔐 2FA Login Supported
🚀 Fast & Stable System
━━━━━━━━━━━━━━━

📌 Click Below Button To Start
"""

    bot.send_message(
        chat_id,
        intro,
        parse_mode="Markdown",
        reply_markup=start_markup()
    )

# ================= [ CANCEL ] =================

@bot.message_handler(func=lambda m: m.text == "❌ CANCEL")

def cancel_process(message):

    chat_id = message.chat.id

    reset_user(chat_id)

    bot.send_message(
        chat_id,
        "🚫 Process Cancelled Successfully.",
        reply_markup=start_markup()
    )

# ================= [ STEP 1 ] =================

@bot.message_handler(func=lambda m: m.text == "♻️ START PROCESS ♻️")

def process_step_1(message):

    chat_id = message.chat.id

    reset_user(chat_id)

    msg = bot.send_message(
        chat_id,
        "👤 Send Username List\n\nOne username per line.",
        reply_markup=cancel_markup()
    )

    bot.register_next_step_handler(msg, process_step_2)

# ================= [ STEP 2 ] =================

def process_step_2(message):

    if message.text == "❌ CANCEL":
        cancel_process(message)
        return

    chat_id = message.chat.id

    usernames = [
        u.strip()
        for u in message.text.splitlines()
        if u.strip()
    ]

    user_sessions[chat_id] = {
        "usernames": usernames,
        "results": []
    }

    msg = bot.send_message(
        chat_id,
        "🔑 Send Common Password",
        reply_markup=cancel_markup()
    )

    bot.register_next_step_handler(msg, process_step_3)

# ================= [ STEP 3 ] =================

def process_step_3(message):

    if message.text == "❌ CANCEL":
        cancel_process(message)
        return

    chat_id = message.chat.id

    user_sessions[chat_id]["password"] = message.text.strip()

    msg = bot.send_message(
        chat_id,
        "🔐 Send 2FA Keys\n\nOne key per line.",
        reply_markup=cancel_markup()
    )

    bot.register_next_step_handler(msg, final_step)

# ================= [ FINAL STEP ] =================

def final_step(message):

    if message.text == "❌ CANCEL":
        cancel_process(message)
        return

    chat_id = message.chat.id

    keys = [
        k.strip()
        for k in message.text.splitlines()
        if k.strip()
    ]

    usernames = user_sessions[chat_id]["usernames"]

    password = user_sessions[chat_id]["password"]

    if len(usernames) != len(keys):

        bot.send_message(
            chat_id,
            "⚠️ Username & 2FA Key Count Not Matched.",
            reply_markup=start_markup()
        )

        reset_user(chat_id)

        return

    bot.send_message(
        chat_id,
        f"⏳ Processing {len(usernames)} Accounts..."
    )

    executor = ThreadPoolExecutor(max_workers=50)

    for i in range(len(usernames)):

        executor.submit(
            login_worker,
            chat_id,
            usernames[i],
            password,
            keys[i]
        )

    def finalize():

        executor.shutdown(wait=True)

        if chat_id not in user_sessions:
            return

        results = user_sessions[chat_id]["results"]

        if results:

            filename = f"cookies_{chat_id}.txt"

            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(results))

            with open(filename, "rb") as file:

                bot.send_document(
                    chat_id,
                    file,
                    caption=f"""
🏁 PROCESS COMPLETED

✅ Success : {len(results)}
❌ Failed : {len(usernames)-len(results)}
🗯️ সাবমিট লিংক 🗯️

http://skysysx.net/e/boss

🗯️ উপরের লিংকে ফাইল সাবমিট করুন 🗯️""",
                    reply_markup=start_markup()
                )

            os.remove(filename)

        else:

            bot.send_message(
                chat_id,
                "❌ No Cookies Found.",
                reply_markup=start_markup()
            )

        reset_user(chat_id)

    threading.Thread(target=finalize).start()

if __name__ == "__main__":
    # যদি এনভায়রনমেন্টে URL থাকে, তবেই সেট হবে
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
        
    # রেন্ডার পোর্টের জন্য ডায়নামিক পোর্ট সেট করা
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
