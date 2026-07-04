
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config
from database import db
from plugins.utils import to_small_caps
import requests
import pytz

@Client.on_message(filters.private & filters.reply, group=98)
async def handle_admin_reply(client, message):
    """Handle user replies to admin messages"""
    if not (message.reply_to_message and message.reply_to_message.from_user):
        return message.continue_propagation()
    
    if message.reply_to_message.from_user.id != (await client.get_me()).id:
        return message.continue_propagation()
    
    reply_text = message.reply_to_message.text or message.reply_to_message.caption

    if not (reply_text and "ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴀᴅᴍɪɴ" in reply_text):
        return message.continue_propagation()
    
    # Handle admin message reply
    user = await db.col.find_one({'id': message.from_user.id})
    user_name = user.get('name', 'Unknown') if user else 'Unknown'

    reply_msg = message.text or message.caption or "[ᴍᴇᴅɪᴀ]"

    from datetime import datetime
    ist = pytz.timezone('Asia/Kolkata')
    ist_time = datetime.now(ist)
    date_str = ist_time.strftime('%d-%m-%Y')
    time_str = ist_time.strftime('%I:%M:%S %p')

    notification = f"""#ᴜsᴇʀ_ʀᴇᴘʟʏ 💬

👤 {to_small_caps('from')}: <a href="tg://user?id={message.from_user.id}">{user_name}</a>
⚡ {to_small_caps('user id')}: <code>{message.from_user.id}</code>

💬 {to_small_caps('message')}:
{reply_msg}

📅 {to_small_caps('date')}: {date_str}
⏰ {to_small_caps('time')}: {time_str}"""

    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": Config.LOG_CHANNEL,
            "text": notification,
            "parse_mode": "HTML"
        }, timeout=5)

        await db.db.admin_logs.insert_one({
            "message": f"💬 {to_small_caps('user reply')}: {user_name} ({message.from_user.id}) - {reply_msg[:100]}",
            "log_type": "info",
            "timestamp": datetime.utcnow(),
            "admin": to_small_caps("user reply"),
            "read": False,
            "user_id": message.from_user.id,
            "full_message": reply_msg
        })

        await db.db.chats.insert_one({
            "user_id": message.from_user.id,
            "sender_type": "user",
            "sender_name": user_name,
            "message": reply_msg,
            "timestamp": datetime.utcnow(),
            "read": False,
            "notification_type": "reply"
        })

        await message.reply(f"✅ {to_small_caps('your message has been sent to the admin!')}")
    except Exception as e:
        await message.reply(f"❌ {to_small_caps('failed to send reply')}")

@Client.on_callback_query(filters.regex(r'^open_admin_panel'))
async def open_admin_panel_callback(client, query):
    """Handle open admin panel button click"""
    import os
    repl_slug = os.environ.get('REPL_SLUG')
    repl_owner = os.environ.get('REPL_OWNER')

    if repl_slug and repl_owner:
        full_panel_url = f"https://{repl_slug}.{repl_owner}.repl.co"
    else:
        full_panel_url = os.environ.get('PANEL_URL', 'https://ftm-fwdbot-op2ov.sevalla.app/')

    await query.answer(f"🌐 {to_small_caps('opening admin panel...')}", show_alert=False)

    await query.message.reply(
        f"<b>🎛️ {to_small_caps('admin panel')}</b>\n\n"
        f"<b>🌐 {to_small_caps('url')}:</b>\n<code>{full_panel_url}</code>\n\n"
        f"<i>💡 {to_small_caps('use the button below to open the panel')}</i>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"🌐 {to_small_caps('open admin panel')}", 
                web_app={"url": full_panel_url}
            )],
            [InlineKeyboardButton(
                f"🔗 {to_small_caps('open in browser')}", 
                url=full_panel_url
            )]
        ])
    )

@Client.on_callback_query(filters.regex(r'^send_panel_link_'))
async def send_panel_link_callback(client, query):
    """Send admin panel link to the new admin"""
    user_id = int(query.data.split('_')[-1])

    import os
    repl_slug = os.environ.get('REPL_SLUG')
    repl_owner = os.environ.get('REPL_OWNER')

    if repl_slug and repl_owner:
        full_panel_url = f"https://{repl_slug}.{repl_owner}.repl.co"
    else:
        full_panel_url = os.environ.get('PANEL_URL', 'https://ftm-fwdbot-op2ov.sevalla.app/')

    await query.answer(f"{to_small_caps('sending panel link to user...')}", show_alert=False)

    try:
        await client.send_message(
            user_id,
            f"<b>🌐 {to_small_caps('admin panel access')}</b>\n\n"
            f"<b>🌐 {to_small_caps('panel url')}:</b>\n<code>{full_panel_url}</code>\n\n"
            f"<i>💡 {to_small_caps('click the button below to access the admin panel')}</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"🌐 {to_small_caps('open admin panel')}", 
                    web_app={"url": full_panel_url}
                )],
                [InlineKeyboardButton(
                    f"🔗 {to_small_caps('open in browser')}", 
                    url=full_panel_url
                )]
            ])
        )
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ {to_small_caps('link sent!')}", callback_data="noop")
            ]])
        )
    except Exception as e:
        await query.answer(f"❌ {to_small_caps('failed to send link')}", show_alert=True)
    except Exception:
        pass
