from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config, temp
from database import db
from plugins.utils import to_small_caps
from plugins.logger import BotLogger
from datetime import datetime, timedelta
import aiohttp
import random
import string
import logging


SARCASTIC_MESSAGES = [
    "😏 ᴀʀᴇ ʙʜᴀɪ, ᴇᴋ ʙᴀᴀʀ ᴋᴀ ʟɪɴᴋ ᴅᴏ ʙᴀᴀʀ ᴜsᴇ ᴋᴀʀ ʀʜᴇ ʜᴏ? ᴛᴜᴍ ᴛᴏ ʙᴀᴅᴇ ʜᴇᴀᴠʏ ᴅʀɪᴠᴇʀ ʜᴏ! 🚗💨",
    "🤣 ʙʜᴀɪ ʏᴇ ᴄᴏᴜᴘᴏɴ ᴇxᴘɪʀᴇ ʜᴏ ɢʏᴀ, ᴅᴜᴋᴀᴀɴ ʙᴜɴᴅ ʜᴏ ɢᴀʏɪ! 🏪❌",
    "😂 ᴇᴋ ᴛɪᴄᴋᴇᴛ sᴇ ᴅᴏ ʙᴀᴀʀ ᴇɴᴛʀʏ? ᴛᴜᴍʜᴀʀᴀ ʟᴏɢɪᴄ ᴛᴏ ᴏᴜᴛ ᴏғ ᴛʜɪs ᴡᴏʀʟᴅ ʜᴀɪ! 🌍🚀",
    "🙄 ʏᴇ ʟɪɴᴋ ᴛᴏ ᴘᴇʜʟᴇ ʜɪ ᴜsᴇ ʜᴏ ɢᴀʏᴀ, ᴀʙ ᴋʏᴀ ᴅᴏᴏsʀᴀ ɢᴇɴᴇʀᴀᴛᴇ ᴋᴀʀᴏ! 🔄",
    "😜 ʙʜᴀɪ ʀᴇᴄʏᴄʟᴇ ᴋᴀʀɴᴀ ᴀᴄᴄʜᴀ ʜᴀɪ, ᴘᴀʀ ʟɪɴᴋ ᴋᴀ ɴᴀʜɪ! ♻️❌",
    "🤭 ᴀʀᴇ ʙᴀʙᴀ, ʏᴇ ʟɪɴᴋ ᴇᴋ ʙᴀᴀʀ ᴋᴀ ᴍᴀᴢᴀ ʜᴀɪ, ʟɪғᴇᴛɪᴍᴇ ᴋᴀ ɴᴀʜɪ! 🎭",
    "😅 ʙʜᴀɪ ᴇᴋ ʙᴀᴀʀ ᴋᴀ ᴍᴀᴛʟᴀʙ sᴀᴍᴀᴊʜᴛᴇ ʜᴏ? ᴏɴᴇ ᴛɪᴍᴇ = ᴇᴋ ᴅᴀғᴀ! 1️⃣",
    "🤡 ᴛᴜᴍ ᴅᴏ ʙᴀᴀʀ ᴜsᴇ ᴋᴀʀ ʟᴏɢᴇ, ᴍᴀɪɴ ᴛᴜᴍʜᴇ ᴅᴇᴋʜ ʟᴜɴɢᴀ? ᴄʜᴀʟ ɴʏᴀ /free ᴋᴀʀ! 🔁"
]

WRONG_USER_MESSAGES = [
    "🚫 ᴀʀᴇ ᴘᴀɢʟᴇ, ʏᴇ ᴛᴇʀᴀ ʟɪɴᴋ ɴᴀʜɪ ʜᴀɪ! ᴅᴏᴏsʀᴇ ᴋᴀ ᴍᴀᴀʟ ᴄʜᴜʀᴀ ʀʜᴀ ʜᴀɪ? 🤨",
    "😤 ʙʜᴀɪ ᴀᴘɴᴀ ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇ ᴋᴀʀᴏ, ᴅᴏᴏsʀᴇ ᴋᴀ ᴋʏᴜ ᴜsᴇ ᴋᴀʀ ʀʜᴇ ʜᴏ? 🙃",
    "🤔 ᴛᴜᴍʜᴀʀᴀ ʟɪɴᴋ ᴛᴏ ᴅᴜsʀᴀ ʜᴀɪ ʙʜᴀɪ, ʏᴇ ᴋɪsɪ ᴀᴜʀ ᴋᴀ ʜᴀɪ! 🎭",
    "😏 ʀᴇ ʙʜᴀɪ, ᴀᴘɴᴀ ᴅᴇᴋʜᴏ, ᴅᴏᴏsʀᴇ ᴋᴀ ᴋʏᴜ ᴛᴀᴘᴋᴀ ʀʜᴇ ʜᴏ? 🤦",
    "🙅 ɴᴀ ʙʜᴀɪ ɴᴀ! ᴀᴘɴᴀ ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇ ᴋᴀʀᴏ /free sᴇ! 🔐"
]


def generate_verify_token():
    """Generate 8 digit numeric token"""
    return ''.join(random.choices(string.digits, k=8))


def generate_alias():
    """Generate short alias for shortened URL"""
    import uuid
    return uuid.uuid4().hex[:8]


async def shorten_link(destination_url: str, alias: str) -> str:
    """Shorten URL using InstantLinks API"""
    api_key = Config.INSTANT_LINKS_API_KEY
    api_url = f"https://instantlinks.co/api?api={api_key}&url={destination_url}&alias={alias}&format=json"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'success':
                        return data.get('shortenedUrl') or data.get('shorturl') or data.get('short')
                    else:
                        logging.error(f"InstantLinks API error: {data}")
                        return None
                else:
                    logging.error(f"InstantLinks API HTTP error: {response.status}")
                    return None
    except Exception as e:
        logging.error(f"Error shortening link: {e}")
        return None


@Client.on_message(filters.private & filters.command(['free']))
async def free_verification_command(client, message):
    """Handle /free command for link verification"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    subscription = await db.get_subscription(user_id)
    plan = subscription.get('plan', 'free')
    status = subscription.get('status', 'active')
    
    if plan != 'free' and status in ['active', 'lifetime']:
        await message.reply(
            f"🎉 {to_small_caps('you already have a premium plan!')}\n\n"
            f"💎 {to_small_caps('your plan')}: {Config.SUBSCRIPTION_PLANS.get(plan, {}).get('emoji', '')} "
            f"{Config.SUBSCRIPTION_PLANS.get(plan, {}).get('name', plan)}\n\n"
            f"✨ {to_small_caps('no verification needed! enjoy your premium features.')}"
        )
        return
    
    pending_verification = await db.get_pending_verification(user_id)
    if pending_verification and pending_verification.get('is_verified'):
        expires_at = pending_verification.get('plan_expires_at')
        if expires_at and expires_at > datetime.utcnow():
            time_left = expires_at - datetime.utcnow()
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            
            await message.reply(
                f"⏳ {to_small_caps('you already have active verification bonus!')}\n\n"
                f"⭐ {to_small_caps('plan')}: ᴘʟᴜs (ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ʙᴏɴᴜs)\n"
                f"⏰ {to_small_caps('time left')}: {hours}ʜ {minutes}ᴍ\n\n"
                f"✨ {to_small_caps('use /fwd to start forwarding!')}"
            )
            return
    
    processing_msg = await message.reply(
        f"⏳ {to_small_caps('generating verification link...')}\n\n"
        f"🔐 {to_small_caps('please wait while we create your unique link.')}"
    )
    
    verify_token = generate_verify_token()
    alias = generate_alias()
    
    me = await client.get_me()
    bot_username = me.username
    
    destination_url = f"https://t.me/{bot_username}?start=l_verify_{verify_token}"
    
    shortened_url = await shorten_link(destination_url, alias)
    
    if not shortened_url:
        await processing_msg.edit(
            f"❌ {to_small_caps('failed to generate verification link!')}\n\n"
            f"🔄 {to_small_caps('please try again later or contact support.')}"
        )
        return
    
    await db.create_verification_token(
        user_id=user_id,
        token=verify_token,
        shortened_url=shortened_url
    )
    
    buttons = [
        [InlineKeyboardButton(f"🔗 {to_small_caps('click to verify')}", url=shortened_url)],
        [InlineKeyboardButton(f"📢 {to_small_caps('join updates')}", url=Config.UPDATE_CHANNEL)]
    ]
    
    await processing_msg.edit(
        f"🎁 <b>{to_small_caps('free verification')}</b> 🎁\n\n"
        f"👤 {to_small_caps('user')}: {user_name}\n"
        f"🆔 {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔐 {to_small_caps('complete verification to get:')}\n"
        f"   ⭐ <b>4 ʜᴏᴜʀs</b> {to_small_caps('of plus plan')}\n"
        f"   🚀 {to_small_caps('unlimited forwarding access')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>{to_small_caps('how to verify:')}</b>\n"
        f"   1️⃣ {to_small_caps('click the button below')}\n"
        f"   2️⃣ {to_small_caps('wait for page to load')}\n"
        f"   3️⃣ {to_small_caps('click continue/go to link')}\n"
        f"   4️⃣ {to_small_caps('you will be redirected back')}\n\n"
        f"⚠️ <b>{to_small_caps('important:')}</b>\n"
        f"   • {to_small_caps('link is one-time use only')}\n"
        f"   • {to_small_caps('valid only for you')}\n"
        f"   • {to_small_caps('expires in 30 minutes')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    
    await BotLogger.log_verification_generated(client, user_id, user_name, shortened_url)


async def handle_l_verify_callback(client, user_id, token, message):
    """Handle l_verify deep link callback"""
    user_name = message.from_user.first_name
    
    verification = await db.get_verification_by_token(token)
    
    if not verification:
        await message.reply(random.choice(SARCASTIC_MESSAGES))
        return
    
    if verification.get('used'):
        await message.reply(random.choice(SARCASTIC_MESSAGES))
        return
    
    if verification['user_id'] != user_id:
        await message.reply(random.choice(WRONG_USER_MESSAGES))
        return
    
    created_at = verification.get('created_at')
    if created_at and (datetime.utcnow() - created_at).total_seconds() > 1800:
        await message.reply(
            f"⏰ {to_small_caps('link expired!')}\n\n"
            f"😅 {to_small_caps('30 minute ho gaye bhai!')}\n"
            f"🔄 {to_small_caps('naya link generate karo')} /free {to_small_caps('se!')}"
        )
        return
    
    await db.mark_verification_used(token)
    
    expires_at = datetime.utcnow() + timedelta(hours=4)
    
    subscription_data = {
        'plan': 'plus',
        'status': 'active',
        'expires_at': expires_at,
        'purchased_at': datetime.utcnow(),
        'assigned_by': 'verification_bonus',
        'features': Config.SUBSCRIPTION_PLANS['plus']['features'],
        'is_verification_plan': True
    }
    
    await db.col.update_one(
        {'id': int(user_id)},
        {'$set': {'subscription': subscription_data}},
        upsert=True
    )
    
    await db.update_verification_plan_status(user_id, is_verified=True, plan_expires_at=expires_at)
    
    await message.reply(
        f"🎉 <b>{to_small_caps('verification successful!')}</b> 🎉\n\n"
        f"✅ {to_small_caps('congratulations!')} {user_name}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⭐ {to_small_caps('you have received:')}\n"
        f"   💎 <b>ᴘʟᴜs ᴘʟᴀɴ</b> {to_small_caps('for')} <b>4 ʜᴏᴜʀs</b>\n"
        f"   🚀 {to_small_caps('unlimited forwarding access')}\n\n"
        f"⏰ {to_small_caps('expires at')}: {expires_at.strftime('%d-%m-%Y %I:%M %p')} UTC\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📢 <b>{to_small_caps('note:')}</b>\n"
        f"   • {to_small_caps('if forwarding is running when plan expires,')}\n"
        f"     {to_small_caps('it will be paused automatically')}\n"
        f"   • {to_small_caps('use')} /free {to_small_caps('again to extend')}\n"
        f"   • {to_small_caps('or buy a plan for uninterrupted access')}\n\n"
        f"🚀 {to_small_caps('start now with')} /fwd"
    )
    
    await BotLogger.log_verification_completed(client, user_id, user_name, expires_at)
