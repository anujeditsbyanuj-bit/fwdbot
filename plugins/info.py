
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from .utils import to_small_caps
from database import db


@Client.on_message(filters.private & filters.command(['info']))
async def info_command(client, message):
    """Show user information"""
    user = message.from_user
    
    # Get user's data center
    dc_id = user.dc_id if user.dc_id else "Unknown"
    
    # Format names
    first_name = user.first_name if user.first_name else "None"
    last_name = user.last_name if user.last_name else "None"
    username = f"@{user.username}" if user.username else "None"
    
    # Create user link
    user_link = f"tg://user?id={user.id}"
    
    # Get registration date from database
    user_doc = await db.col.find_one({'id': int(user.id)})
    joined_at = user_doc.get('joined_at') if user_doc else None
    
    text = (
        f"<b>👤 {to_small_caps('user information')} 👤</b>\n\n"
        f"➲ <b>{to_small_caps('first name')}:</b> {first_name}\n"
        f"➲ <b>{to_small_caps('last name')}:</b> {last_name}\n"
        f"➲ <b>{to_small_caps('telegram id')}:</b> <code>{user.id}</code>\n"
        f"➲ <b>{to_small_caps('data centre')}:</b> {dc_id}\n"
        f"➲ <b>{to_small_caps('user name')}:</b> {username}\n"
        f"➲ <b>{to_small_caps('user link')}:</b> <a href='{user_link}'>Click Here</a>\n"
    )
    
    # Add registration date if available
    if joined_at:
        registration_date = joined_at.strftime('%d-%m-%Y')
        registration_time = joined_at.strftime('%I:%M:%S %p')
        text += f"➲ <b>📅 {to_small_caps('registration date')}:</b> {registration_date}\n"
        text += f"➲ <b>🕐 {to_small_caps('registration time')}:</b> {registration_time}\n"
    
    buttons = [
        [InlineKeyboardButton(f"💳 {to_small_caps('my plan')}", callback_data='sub#my_plan')],
        [InlineKeyboardButton(f"⫷ {to_small_caps('close')}", callback_data='close')]
    ]
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r'^close$'))
async def close_callback(client, query):
    """Handle close button"""
    await query.message.delete()
    await query.answer()
